from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.codex_adapter import FakeCodexAdapter
from app.database import RuntimeStore
from app.phases import PhaseJobService, format_sse_event, phase_prompt_path


class SpyAdapter(FakeCodexAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.started = 0

    async def start_thread(self, *, project_dir: str, phase: int, sandbox: str):
        self.started += 1
        return await super().start_thread(project_dir=project_dir, phase=phase, sandbox=sandbox)


def write_project(root: Path, name: str = "demo_project", phase: int = 2) -> Path:
    project = root / name
    project.mkdir()
    (project / ".research_state.json").write_text(
        json.dumps(
            {
                "project_dir": name,
                "current_phase": phase,
                "phase_status": "not_started",
                "topic": {"specific_topic": "Synthetic data"},
            }
        ),
        encoding="utf-8",
    )
    return project


def test_phase_prompt_paths_cover_phase_zero_to_eight(tmp_path: Path) -> None:
    for phase in range(9):
        path = phase_prompt_path(tmp_path, phase)
        assert path.name.startswith(f"{phase:02d}_") or path.name in {
            "01_interview.md",
            "02_literature_search.md",
            "03_research_plan.md",
            "04_experiment_design.md",
            "05_experiment_execution.md",
            "06_result_analysis.md",
            "07_manuscript_writing.md",
            "08_manuscript_review.md",
        }


@pytest.mark.asyncio
async def test_start_phase_job_persists_job_and_events(tmp_path: Path) -> None:
    write_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FakeCodexAdapter())

    result = await service.start_phase_job(
        project_dir="demo_project",
        phase=2,
        action="Write literature search output",
        prompt="Find literature workers",
    )

    job = store.get_job(result.job_id)
    events = store.list_events(result.job_id)
    assert result.requires_approval is False
    assert job["project_dir"] == "demo_project"
    assert job["phase"] == 2
    assert job["thread_id"].startswith("fake-thread-")
    assert job["turn_id"].startswith("fake-turn-")
    assert job["status"] == "completed"
    assert [event["event_type"] for event in events] == [
        "turn_started",
        "assistant_message",
        "turn_completed",
    ]


@pytest.mark.asyncio
async def test_high_risk_job_waits_for_gui_approval_before_starting_thread(tmp_path: Path) -> None:
    write_project(tmp_path, phase=5)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    adapter = SpyAdapter()
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=adapter)

    result = await service.start_phase_job(
        project_dir="demo_project",
        phase=5,
        action="Run experiment scripts",
        prompt="Run experiments",
    )

    job = store.get_job(result.job_id)
    approvals = store.list_approvals(result.job_id)
    assert result.requires_approval is True
    assert adapter.started == 0
    assert job["status"] == "waiting_for_approval"
    assert job["approval_state"] == "required"
    assert approvals[0]["risk_level"] == "high"


@pytest.mark.asyncio
async def test_approved_high_risk_job_can_continue_existing_job(tmp_path: Path) -> None:
    write_project(tmp_path, phase=5)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    adapter = SpyAdapter()
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=adapter)
    result = await service.start_phase_job(
        project_dir="demo_project",
        phase=5,
        action="Run experiment scripts",
        prompt="Run experiments",
    )

    approval = service.submit_approval(result.job_id, user_action="approved")
    continued = await service.continue_job(
        result.job_id,
        action="Run experiment scripts",
        prompt="Run approved experiments",
    )

    job = store.get_job(result.job_id)
    events = store.list_events(result.job_id)
    approvals = store.list_approvals(result.job_id)
    assert approval["user_action"] == "approved"
    assert continued.status == "completed"
    assert job["thread_id"].startswith("fake-thread-")
    assert job["turn_id"].startswith("fake-turn-")
    assert job["approval_state"] == "approved"
    assert adapter.started == 1
    assert approvals[0]["final_status"] == "approved"
    assert events[-1]["event_type"] == "turn_completed"


@pytest.mark.asyncio
async def test_interrupt_updates_status_and_records_event(tmp_path: Path) -> None:
    write_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FakeCodexAdapter())
    result = await service.start_phase_job(
        project_dir="demo_project",
        phase=2,
        action="Write literature search output",
        prompt="Find literature workers",
    )
    job = store.get_job(result.job_id)

    interrupted = await service.interrupt_job(result.job_id)

    updated = store.get_job(result.job_id)
    events = store.list_events(result.job_id)
    assert interrupted is True
    assert updated["status"] == "interrupted"
    assert events[-1]["event_type"] == "interrupted"
    assert job["turn_id"]


def test_format_sse_event_uses_stable_json_payload() -> None:
    event = {
        "event_id": 7,
        "event_type": "assistant_message",
        "summary": "Progress",
    }

    assert format_sse_event(event) == (
        'event: assistant_message\n'
        'data: {"event_id":7,"event_type":"assistant_message","summary":"Progress"}\n\n'
    )
