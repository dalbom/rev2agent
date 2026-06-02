from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from .codex_adapter import FakeCodexAdapter
from .database import RuntimeStore, utc_now
from .projects import PHASE_LABELS, load_project_state
from .safety import classify_action


PHASE_PROMPTS: dict[int, str] = {
    0: "00_setup.md",
    1: "01_interview.md",
    2: "02_literature_search.md",
    3: "03_research_plan.md",
    4: "04_experiment_design.md",
    5: "05_experiment_execution.md",
    6: "06_result_analysis.md",
    7: "07_manuscript_writing.md",
    8: "08_manuscript_review.md",
}


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
        load_project_state(self.repo_root, project_path)
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

        thread = await self.adapter.start_thread(
            project_dir=str(project_path),
            phase=phase,
            sandbox=decision.sandbox.value,
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
        async for event in self.adapter.stream_turn(
            thread.thread_id,
            prompt,
            sandbox=decision.sandbox.value,
        ):
            turn_id = event.turn_id
            self.store.add_event(
                job_id=job_id,
                event_type=event.event_type,
                summary=event.summary,
                raw_payload=event.raw_payload,
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
        return interrupted

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

    def _project_path(self, project_dir: str) -> Path:
        return (self.repo_root / project_dir).resolve()


def phase_prompt_path(repo_root: Path, phase: int) -> Path:
    try:
        filename = PHASE_PROMPTS[phase]
    except KeyError as exc:
        raise ValueError(f"Unknown phase: {phase}") from exc
    return repo_root / "prompts" / filename


def format_sse_event(event: dict[str, Any]) -> str:
    event_type = str(event.get("event_type", "message"))
    payload = json.dumps(event, separators=(",", ":"), ensure_ascii=False)
    return f"event: {event_type}\ndata: {payload}\n\n"
