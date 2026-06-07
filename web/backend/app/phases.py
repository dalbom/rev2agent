from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from .codex_adapter import FakeCodexAdapter
from .database import RuntimeStore, utc_now
from .prompt_bundle import build_phase_prompt_bundle
from .prompt_bundle import phase_prompt_path
from .projects import PHASE_LABELS, load_project_state
from .safety import classify_action


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

    async def start_phase_job(
        self,
        *,
        project_dir: str,
        phase: int,
        action: str,
        prompt: str,
        approved: bool = False,
    ) -> PhaseJobResult:
        project_path = self._project_path(project_dir)
        state = load_project_state(self.repo_root, project_path)
        bundled_prompt = build_phase_prompt_bundle(
            repo_root=self.repo_root,
            project_path=project_path,
            state=state,
            user_prompt=prompt,
        )
        decision = classify_action(phase=phase, action=action)
        job_id = f"job-{uuid4().hex}"

        if decision.requires_approval and not approved:
            self.store.create_job(
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

        try:
            thread = await self.adapter.start_thread(
                project_dir=str(project_path),
                phase=phase,
                sandbox=decision.sandbox.value,
            )
        except Exception as exc:
            self.store.create_job(
                job_id=job_id,
                project_dir=project_dir,
                phase=phase,
                sub_step=None,
                role="main",
                thread_id=None,
                turn_id=None,
                status="failed",
                approval_state="approved" if approved else "not_required",
                sandbox=decision.sandbox.value,
                completed_at=utc_now(),
                last_error=str(exc),
            )
            self.store.add_event(
                job_id=job_id,
                event_type="error",
                summary=str(exc),
                raw_payload={"error": str(exc)},
            )
            return PhaseJobResult(
                job_id=job_id,
                requires_approval=False,
                status="failed",
                sandbox=decision.sandbox.value,
                message=str(exc),
            )
        self.store.create_job(
            job_id=job_id,
            project_dir=project_dir,
            phase=phase,
            sub_step=None,
            role="main",
            thread_id=thread.thread_id,
            turn_id=None,
            status="running",
            approval_state="approved" if approved else "not_required",
            sandbox=decision.sandbox.value,
        )

        turn_id: str | None = None
        stream_failure_message: str | None = None
        stream_was_interrupted = False
        try:
            async for event in self.adapter.stream_turn(
                thread.thread_id,
                bundled_prompt,
                sandbox=decision.sandbox.value,
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
                sandbox=decision.sandbox.value,
                thread_id=thread.thread_id,
                turn_id=turn_id,
            )
            raise
        except Exception as exc:
            return self._fail_job(
                job_id=job_id,
                sandbox=decision.sandbox.value,
                thread_id=thread.thread_id,
                turn_id=turn_id,
                error=exc,
            )

        if stream_failure_message:
            return self._fail_job(
                job_id=job_id,
                sandbox=decision.sandbox.value,
                thread_id=thread.thread_id,
                turn_id=turn_id,
                error=RuntimeError(stream_failure_message),
            )
        if stream_was_interrupted:
            self.store.update_job(
                job_id,
                turn_id=turn_id,
                status="interrupted",
                completed_at=utc_now(),
            )
            return PhaseJobResult(
                job_id=job_id,
                requires_approval=False,
                status="interrupted",
                sandbox=decision.sandbox.value,
                thread_id=thread.thread_id,
                turn_id=turn_id,
            )

        self.store.update_job(
            job_id,
            turn_id=turn_id,
            status="completed",
            completed_at=utc_now(),
        )
        return PhaseJobResult(
            job_id=job_id,
            requires_approval=False,
            status="completed",
            sandbox=decision.sandbox.value,
            thread_id=thread.thread_id,
            turn_id=turn_id,
        )

    async def interrupt_job(self, job_id: str) -> bool:
        job = self.store.get_job(job_id)
        thread_id = job.get("thread_id")
        turn_id = job.get("turn_id")
        if not thread_id or not turn_id:
            return False
        interrupted = await self.adapter.interrupt(thread_id, turn_id)
        if interrupted:
            self.store.update_job(
                job_id,
                status="interrupted",
                completed_at=utc_now(),
            )
            self.store.add_event(
                job_id=job_id,
                event_type="interrupted",
                summary="The user interrupted this job.",
                raw_payload={"thread_id": thread_id, "turn_id": turn_id},
            )
            return True
        if self._mark_stale_running_job_interrupted(job):
            self.store.add_event(
                job_id=job_id,
                event_type="interrupted",
                summary="The job was marked interrupted because it was stale and no active SDK turn could be interrupted.",
                raw_payload={"thread_id": thread_id, "turn_id": turn_id, "stale": True},
            )
            return True
        return interrupted

    def submit_approval(self, job_id: str, *, user_action: str) -> dict[str, Any]:
        if user_action not in {"approved", "rejected"}:
            raise ValueError("Approval action must be approved or rejected")
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
        )
        self.store.add_event(
            job_id=job_id,
            event_type=f"approval_{user_action}",
            summary=f"User {user_action} this job.",
            raw_payload={"approval_id": approval["approval_id"]},
        )
        return approval

    async def continue_job(self, job_id: str, *, action: str, prompt: str) -> PhaseJobResult:
        job = self.store.get_job(job_id)
        if job["approval_state"] != "approved":
            raise ValueError("Job cannot continue until approval is recorded")

        project_dir = job["project_dir"]
        project_path = self._project_path(project_dir)
        state = load_project_state(self.repo_root, project_path)
        bundled_prompt = build_phase_prompt_bundle(
            repo_root=self.repo_root,
            project_path=project_path,
            state=state,
            user_prompt=prompt,
        )
        decision = classify_action(phase=job["phase"], action=action)
        try:
            thread = await self.adapter.start_thread(
                project_dir=str(project_path),
                phase=job["phase"],
                sandbox=decision.sandbox.value,
            )
        except Exception as exc:
            return self._fail_job(
                job_id=job_id,
                sandbox=decision.sandbox.value,
                thread_id=None,
                turn_id=None,
                error=exc,
            )
        self.store.update_job(
            job_id,
            thread_id=thread.thread_id,
            status="running",
            sandbox=decision.sandbox.value,
        )

        turn_id: str | None = None
        stream_failure_message: str | None = None
        stream_was_interrupted = False
        try:
            async for event in self.adapter.stream_turn(
                thread.thread_id,
                bundled_prompt,
                sandbox=decision.sandbox.value,
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
                sandbox=decision.sandbox.value,
                thread_id=thread.thread_id,
                turn_id=turn_id,
            )
            raise
        except Exception as exc:
            return self._fail_job(
                job_id=job_id,
                sandbox=decision.sandbox.value,
                thread_id=thread.thread_id,
                turn_id=turn_id,
                error=exc,
            )

        if stream_failure_message:
            return self._fail_job(
                job_id=job_id,
                sandbox=decision.sandbox.value,
                thread_id=thread.thread_id,
                turn_id=turn_id,
                error=RuntimeError(stream_failure_message),
            )
        if stream_was_interrupted:
            self.store.update_job(
                job_id,
                turn_id=turn_id,
                status="interrupted",
                completed_at=utc_now(),
            )
            return PhaseJobResult(
                job_id=job_id,
                requires_approval=False,
                status="interrupted",
                sandbox=decision.sandbox.value,
                thread_id=thread.thread_id,
                turn_id=turn_id,
            )

        self.store.update_job(
            job_id,
            turn_id=turn_id,
            status="completed",
            completed_at=utc_now(),
        )
        return PhaseJobResult(
            job_id=job_id,
            requires_approval=False,
            status="completed",
            sandbox=decision.sandbox.value,
            thread_id=thread.thread_id,
            turn_id=turn_id,
        )

    def list_events(self, job_id: str) -> list[dict[str, Any]]:
        return self.store.list_events(job_id)

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
        self.store.update_job(
            job_id,
            turn_id=turn_id,
            status="failed",
            completed_at=utc_now(),
            last_error=message,
        )
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

    def _mark_stale_running_job_interrupted(self, job: dict[str, Any]) -> bool:
        if job.get("status") not in {"queued", "running", "waiting_for_approval"}:
            return False
        started_at = _parse_utc(job.get("started_at"))
        if started_at is None:
            return False
        if datetime.now(UTC) - started_at < timedelta(minutes=30):
            return False
        self.store.update_job(
            job["job_id"],
            status="interrupted",
            completed_at=utc_now(),
            last_error="Interrupted stale job after SDK interrupt returned false.",
        )
        return True

    def _cancel_job(
        self,
        *,
        job_id: str,
        sandbox: str,
        thread_id: str | None,
        turn_id: str | None,
    ) -> None:
        message = "Job cancelled before completion."
        self.store.update_job(
            job_id,
            turn_id=turn_id,
            status="cancelled",
            completed_at=utc_now(),
            last_error=message,
        )
        self.store.add_event(
            job_id=job_id,
            event_type="cancelled",
            summary=message,
            raw_payload={"thread_id": thread_id, "turn_id": turn_id, "sandbox": sandbox},
        )

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

    def _project_path(self, project_dir: str) -> Path:
        return (self.repo_root / project_dir).resolve()


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


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def format_sse_event(event: dict[str, Any]) -> str:
    event_type = str(event.get("event_type", "message"))
    payload = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"
