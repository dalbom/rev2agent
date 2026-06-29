from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .codex_adapter import FakeCodexAdapter
from .database import RuntimeStore, utc_now
from .prompt_bundle import build_phase_prompt_bundle
from .prompt_bundle import phase_prompt_path
from .projects import PHASE_LABELS, load_project_state
from .safety import classify_action

__all__ = ["PhaseJobService", "PhaseJobResult", "format_sse_event", "phase_prompt_path"]

ACTIVE_STATUSES = {"queued", "running"}
TERMINAL_STATUSES = {"completed", "failed", "interrupted", "cancelled", "rejected"}


@dataclass(frozen=True)
class PhaseJobResult:
    job_id: str
    requires_approval: bool
    status: str
    sandbox: str
    thread_id: str | None = None
    turn_id: str | None = None
    approval_id: int | None = None
    message: str = ""


class PhaseJobService:
    def __init__(
        self,
        *,
        repo_root: Path,
        store: RuntimeStore,
        adapter: Any | None = None,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.store = store
        self.adapter = adapter or FakeCodexAdapter()
        self._tasks: dict[str, asyncio.Task[Any]] = {}

    def recover_orphaned_jobs(self) -> int:
        return self.store.mark_active_jobs_interrupted(
            reason="Job orphaned by a backend restart before it could finish.",
        )

    async def start_phase_job(
        self,
        *,
        project_dir: str,
        phase: int,
        action: str,
        prompt: str,
        approved: bool = False,
    ) -> PhaseJobResult:
        pending = self._create_phase_job(
            project_dir=project_dir,
            phase=phase,
            action=action,
            approved=approved,
        )
        if pending.requires_approval:
            return pending
        return await self._run_phase_turn(
            job_id=pending.job_id,
            project_dir=project_dir,
            prompt=prompt,
            sandbox=pending.sandbox,
        )

    def launch_phase_job(
        self,
        *,
        project_dir: str,
        phase: int,
        action: str,
        prompt: str,
    ) -> PhaseJobResult:
        pending = self._create_phase_job(
            project_dir=project_dir,
            phase=phase,
            action=action,
            approved=False,
        )
        if pending.requires_approval:
            return pending
        self._spawn_job_task(
            pending.job_id,
            self._run_phase_turn(
                job_id=pending.job_id,
                project_dir=project_dir,
                prompt=prompt,
                sandbox=pending.sandbox,
            ),
        )
        return PhaseJobResult(
            job_id=pending.job_id,
            requires_approval=False,
            status="running",
            sandbox=pending.sandbox,
        )

    async def continue_job(self, job_id: str, *, action: str, prompt: str) -> PhaseJobResult:
        job, decision = self._validate_continue(job_id, action)
        return await self._run_phase_turn(
            job_id=job_id,
            project_dir=job["project_dir"],
            prompt=prompt,
            sandbox=decision.sandbox.value,
        )

    def launch_continue_job(self, job_id: str, *, action: str, prompt: str) -> PhaseJobResult:
        job, decision = self._validate_continue(job_id, action)
        self.store.requeue_job_exclusive(job_id, job["project_dir"])
        self._spawn_job_task(
            job_id,
            self._run_phase_turn(
                job_id=job_id,
                project_dir=job["project_dir"],
                prompt=prompt,
                sandbox=decision.sandbox.value,
            ),
        )
        return PhaseJobResult(
            job_id=job_id,
            requires_approval=False,
            status="running",
            sandbox=decision.sandbox.value,
        )

    async def interrupt_job(self, job_id: str) -> bool:
        job = self.store.get_job(job_id)
        if job.get("status") in TERMINAL_STATUSES:
            return False

        thread_id = job.get("thread_id")
        turn_id = job.get("turn_id")
        if thread_id and turn_id and await self.adapter.interrupt(thread_id, turn_id):
            ok = self.store.update_job_if_active(
                job_id,
                status="interrupted",
                completed_at=utc_now(),
            )
            if not ok:
                # The job finished while the interrupt was in flight; leave the
                # terminal row and its events untouched.
                return False
            self.store.add_event(
                job_id=job_id,
                event_type="interrupted",
                summary="The user interrupted this job.",
                raw_payload={"thread_id": thread_id, "turn_id": turn_id},
            )
            self._add_interrupt_note_if_state_advanced(
                job_id=job_id,
                project_dir=job["project_dir"],
                job_phase=job["phase"],
            )
            return True

        task = self._tasks.get(job_id)
        if task is not None and not task.done():
            task.cancel()
            self.store.add_event(
                job_id=job_id,
                event_type="interrupted",
                summary="The user interrupted this job; the in-process job task was cancelled.",
                raw_payload={"thread_id": thread_id, "turn_id": turn_id, "task_cancelled": True},
            )
            self._add_interrupt_note_if_state_advanced(
                job_id=job_id,
                project_dir=job["project_dir"],
                job_phase=job["phase"],
            )
            return True

        ok = self.store.update_job_if_active(
            job_id,
            status="interrupted",
            completed_at=utc_now(),
            last_error="Interrupted stale job with no active SDK turn (stale job or backend restart).",
        )
        if not ok:
            return False
        self.store.add_event(
            job_id=job_id,
            event_type="interrupted",
            summary="The job was marked interrupted because no active SDK turn could be interrupted.",
            raw_payload={"thread_id": thread_id, "turn_id": turn_id, "stale": True},
        )
        self._add_interrupt_note_if_state_advanced(
            job_id=job_id,
            project_dir=job["project_dir"],
            job_phase=job["phase"],
        )
        return True

    def submit_approval(self, job_id: str, *, user_action: str) -> dict[str, Any]:
        if user_action not in {"approved", "rejected"}:
            raise ValueError("Approval action must be approved or rejected")
        job = self.store.get_job(job_id)
        if job.get("status") != "waiting_for_approval":
            raise ValueError("Job is not waiting for approval")
        final_status = "approved" if user_action == "approved" else "rejected"
        approval = self.store.update_latest_approval(
            job_id,
            user_action=user_action,
            final_status=final_status,
        )
        self.store.update_job(
            job_id,
            approval_state=user_action,
            status="waiting_to_continue" if user_action == "approved" else "rejected",
            completed_at=utc_now() if user_action == "rejected" else None,
        )
        self.store.add_event(
            job_id=job_id,
            event_type=f"approval_{user_action}",
            summary=f"User {user_action} this job.",
            raw_payload={"approval_id": approval["approval_id"]},
        )
        return approval

    def list_events(self, job_id: str) -> list[dict[str, Any]]:
        return self.store.list_events(job_id)

    def phase_status(self, project_dir: str) -> dict[str, Any]:
        state = load_project_state(self.repo_root, self._project_path(project_dir))
        phase = state.get("current_phase")
        return {
            "project_dir": project_dir,
            "phase": phase,
            "phase_label": PHASE_LABELS.get(phase, "Unknown") if isinstance(phase, int) else "Unknown",
            "phase_status": state.get("phase_status", "unknown"),
            "sub_step": state.get("sub_step"),
            "current_round": state.get("current_round"),
        }

    def _create_phase_job(
        self,
        *,
        project_dir: str,
        phase: int,
        action: str,
        approved: bool,
    ) -> PhaseJobResult:
        decision = classify_action(phase=phase, action=action)
        job_id = f"job-{uuid4().hex}"

        if decision.requires_approval and not approved:
            self.store.create_job_exclusive(
                job_id=job_id,
                project_dir=project_dir,
                phase=phase,
                sub_step=None,
                role="main",
                thread_id=None,
                turn_id=None,
                status="waiting_for_approval",
                approval_state="required",
                sandbox=decision.sandbox.value,
            )
            approval_id = self.store.add_approval(
                job_id=job_id,
                project_dir=project_dir,
                requested_action=action,
                risk_level=decision.risk_level,
                requested_sandbox=decision.sandbox.value,
                user_action="pending",
                final_status="waiting_for_approval",
                impact=decision.impact,
            )
            return PhaseJobResult(
                job_id=job_id,
                requires_approval=True,
                status="waiting_for_approval",
                sandbox=decision.sandbox.value,
                approval_id=approval_id,
                message=decision.impact,
            )

        self.store.create_job_exclusive(
            job_id=job_id,
            project_dir=project_dir,
            phase=phase,
            sub_step=None,
            role="main",
            thread_id=None,
            turn_id=None,
            status="queued",
            approval_state="approved" if approved else "not_required",
            sandbox=decision.sandbox.value,
        )
        return PhaseJobResult(
            job_id=job_id,
            requires_approval=False,
            status="queued",
            sandbox=decision.sandbox.value,
        )

    def _validate_continue(self, job_id: str, action: str) -> tuple[dict[str, Any], Any]:
        job = self.store.get_job(job_id)
        if job["approval_state"] != "approved":
            raise ValueError("Job cannot continue until approval is recorded")
        if job.get("status") in TERMINAL_STATUSES or job.get("status") in ACTIVE_STATUSES:
            raise ValueError(f"Job cannot continue from status {job.get('status')}")

        approvals = self.store.list_approvals(job_id)
        latest_approval = approvals[-1] if approvals else None
        if latest_approval is not None:
            if latest_approval["final_status"] != "approved":
                raise ValueError("Job cannot continue until approval is recorded")
            if action != latest_approval["requested_action"]:
                raise ValueError(
                    "Continue action must match the approved action: "
                    f"{latest_approval['requested_action']!r}",
                )

        decision = classify_action(phase=job["phase"], action=action)
        if decision.requires_approval and latest_approval is None:
            raise ValueError("High-risk continue action requires a recorded approval")
        return job, decision

    def _spawn_job_task(self, job_id: str, coro: Any) -> None:
        task = asyncio.create_task(coro)
        self._tasks[job_id] = task
        task.add_done_callback(lambda finished: self._on_job_task_done(job_id, finished))

    def _on_job_task_done(self, job_id: str, task: asyncio.Task[Any]) -> None:
        self._tasks.pop(job_id, None)
        if task.cancelled():
            return
        # _run_phase_turn handles its own errors; this is a last-resort safety net
        # so a background job can never die without a recorded failure.
        exc = task.exception()
        if exc is not None:
            self._fail_job(
                job_id=job_id,
                sandbox="unknown",
                thread_id=None,
                turn_id=None,
                error=exc if isinstance(exc, Exception) else RuntimeError(str(exc)),
            )

    async def _run_phase_turn(
        self,
        *,
        job_id: str,
        project_dir: str,
        prompt: str,
        sandbox: str,
    ) -> PhaseJobResult:
        try:
            project_path = self._project_path(project_dir)
            state = load_project_state(self.repo_root, project_path)
            initial_state = (
                _job_phase(state),
                state.get("phase_status"),
                state.get("updated_at"),
            )
            bundled_prompt = build_phase_prompt_bundle(
                repo_root=self.repo_root,
                project_path=project_path,
                state=state,
                user_prompt=prompt,
            )
            thread = await self.adapter.start_thread(
                project_dir=str(project_path),
                phase=_job_phase(state),
                sandbox=sandbox,
            )
        except Exception as exc:
            return self._fail_job(
                job_id=job_id,
                sandbox=sandbox,
                thread_id=None,
                turn_id=None,
                error=exc,
            )

        self.store.update_job(
            job_id,
            thread_id=thread.thread_id,
            status="running",
            sandbox=sandbox,
        )

        turn_id: str | None = None
        stream_failure_message: str | None = None
        stream_was_interrupted = False
        try:
            async for event in self.adapter.stream_turn(
                thread.thread_id,
                bundled_prompt,
                sandbox=sandbox,
            ):
                if event.turn_id != turn_id:
                    turn_id = event.turn_id
                    self.store.update_job(job_id, turn_id=turn_id)
                self.store.add_event(
                    job_id=job_id,
                    event_type=event.event_type,
                    summary=event.summary,
                    raw_payload=event.raw_payload,
                )
                stream_failure_message = stream_failure_message or _stream_failure_message(event)
                stream_was_interrupted = stream_was_interrupted or _stream_interrupted(event)
        except asyncio.CancelledError:
            self._cancel_job(
                job_id=job_id,
                sandbox=sandbox,
                thread_id=thread.thread_id,
                turn_id=turn_id,
            )
            raise
        except Exception as exc:
            return self._fail_job(
                job_id=job_id,
                sandbox=sandbox,
                thread_id=thread.thread_id,
                turn_id=turn_id,
                error=exc,
            )

        if stream_failure_message:
            return self._fail_job(
                job_id=job_id,
                sandbox=sandbox,
                thread_id=thread.thread_id,
                turn_id=turn_id,
                error=RuntimeError(stream_failure_message),
            )
        if stream_was_interrupted:
            ok = self.store.update_job_if_active(
                job_id,
                turn_id=turn_id,
                status="interrupted",
                completed_at=utc_now(),
            )
            if ok:
                self._add_interrupt_note_if_state_advanced(
                    job_id=job_id,
                    project_dir=project_dir,
                    job_phase=initial_state[0],
                )
            return PhaseJobResult(
                job_id=job_id,
                requires_approval=False,
                status="interrupted",
                sandbox=sandbox,
                thread_id=thread.thread_id,
                turn_id=turn_id,
            )

        ok = self.store.update_job_if_active(
            job_id,
            turn_id=turn_id,
            status="completed",
            completed_at=utc_now(),
        )
        if ok:
            self._add_completion_warning_if_state_unchanged(
                job_id=job_id,
                project_path=project_path,
                initial_state=initial_state,
            )
        return PhaseJobResult(
            job_id=job_id,
            requires_approval=False,
            status="completed",
            sandbox=sandbox,
            thread_id=thread.thread_id,
            turn_id=turn_id,
        )

    def _add_completion_warning_if_state_unchanged(
        self,
        *,
        job_id: str,
        project_path: Path,
        initial_state: tuple[int, Any, Any],
    ) -> None:
        try:
            state = load_project_state(self.repo_root, project_path)
        except Exception:
            return
        current_state = (
            _job_phase(state),
            state.get("phase_status"),
            state.get("updated_at"),
        )
        if current_state != initial_state:
            return
        phase, phase_status, _ = current_state
        self.store.add_event(
            job_id=job_id,
            event_type="completion_warning",
            summary=(
                f"Job completed but the project state did not change "
                f"(still phase {phase}, status {phase_status}). The phase may not have "
                f"produced its required outputs; review the run log and consider retrying."
            ),
            raw_payload={"phase": phase, "phase_status": phase_status},
        )

    def _add_interrupt_note_if_state_advanced(
        self,
        *,
        job_id: str,
        project_dir: str,
        job_phase: int,
    ) -> None:
        try:
            state = load_project_state(self.repo_root, self._project_path(project_dir))
        except Exception:
            return
        current_phase = _job_phase(state)
        phase_status = state.get("phase_status")
        if current_phase == job_phase and phase_status != "completed":
            return
        # Both interrupt_job and the stream-interrupted branch can fire for one
        # interruption; only one note per job is useful.
        existing = self.store.list_events(job_id)
        if any(event["event_type"] == "interrupt_note" for event in existing):
            return
        self.store.add_event(
            job_id=job_id,
            event_type="interrupt_note",
            summary=(
                f"Note: project state shows phase {current_phase} ({phase_status}); "
                f"the phase work may have completed before this interruption."
            ),
            raw_payload={"current_phase": current_phase, "phase_status": phase_status},
        )

    def _fail_job(
        self,
        *,
        job_id: str,
        sandbox: str,
        thread_id: str | None,
        turn_id: str | None,
        error: Exception,
    ) -> PhaseJobResult:
        message = str(error) or type(error).__name__
        ok = self.store.update_job_if_active(
            job_id,
            turn_id=turn_id,
            status="failed",
            completed_at=utc_now(),
            last_error=message,
        )
        if ok:
            self.store.add_event(
                job_id=job_id,
                event_type="error",
                summary=message,
                raw_payload={"error": message},
            )
        return PhaseJobResult(
            job_id=job_id,
            requires_approval=False,
            status="failed",
            sandbox=sandbox,
            thread_id=thread_id,
            turn_id=turn_id,
            message=message,
        )

    def _cancel_job(
        self,
        *,
        job_id: str,
        sandbox: str,
        thread_id: str | None,
        turn_id: str | None,
    ) -> None:
        message = "Job cancelled before completion."
        ok = self.store.update_job_if_active(
            job_id,
            turn_id=turn_id,
            status="cancelled",
            completed_at=utc_now(),
            last_error=message,
        )
        if ok:
            self.store.add_event(
                job_id=job_id,
                event_type="cancelled",
                summary=message,
                raw_payload={"thread_id": thread_id, "turn_id": turn_id, "sandbox": sandbox},
            )

    def _project_path(self, project_dir: str) -> Path:
        return (self.repo_root / project_dir).resolve()


def _job_phase(state: dict[str, Any]) -> int:
    value = state.get("current_phase")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _stream_failure_message(event: Any) -> str | None:
    event_type = str(getattr(event, "event_type", "") or "")
    summary = str(getattr(event, "summary", "") or "")
    raw_payload = getattr(event, "raw_payload", None)
    if event_type == "error":
        return summary or "SDK stream emitted an error event."
    if event_type in {"turn/completed", "turn_completed"} and "failed" in summary.lower():
        return summary
    if isinstance(raw_payload, dict):
        raw_text = json.dumps(raw_payload, ensure_ascii=False).lower()
        if event_type in {"turn/completed", "turn_completed"} and '"failed"' in raw_text:
            return summary or "SDK turn failed."
    return None


def _stream_interrupted(event: Any) -> bool:
    event_type = str(getattr(event, "event_type", "") or "")
    summary = str(getattr(event, "summary", "") or "")
    raw_payload = getattr(event, "raw_payload", None)
    if event_type in {"turn/completed", "turn_completed"} and "interrupted" in summary.lower():
        return True
    if isinstance(raw_payload, dict):
        raw_text = json.dumps(raw_payload, ensure_ascii=False).lower()
        return event_type in {"turn/completed", "turn_completed"} and "interrupted" in raw_text
    return False


def format_sse_event(event: dict[str, Any]) -> str:
    payload = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
    event_id = event.get("event_id")
    id_line = f"id: {event_id}\n" if isinstance(event_id, int) else ""
    return f"{id_line}data: {payload}\n\n"
