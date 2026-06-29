from __future__ import annotations

import json
import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.codex_adapter import FakeCodexAdapter
from app.database import ProjectBusyError, RuntimeStore, utc_now
from app.phases import PhaseJobService, format_sse_event, phase_prompt_path
from app.prompt_bundle import PHASE_PROMPTS


class SpyAdapter(FakeCodexAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.started = 0

    async def start_thread(self, *, project_dir: str, phase: int, sandbox: str):
        self.started += 1
        return await super().start_thread(project_dir=project_dir, phase=phase, sandbox=sandbox)


class PromptCaptureAdapter(FakeCodexAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.prompts: list[str] = []

    async def stream_turn(self, thread_id: str, prompt: str, *, sandbox: str):
        self.prompts.append(prompt)
        async for event in super().stream_turn(thread_id, prompt, sandbox=sandbox):
            yield event


class FailingStreamAdapter(FakeCodexAdapter):
    async def stream_turn(self, thread_id: str, prompt: str, *, sandbox: str):
        raise RuntimeError("SDK stream failed")
        yield


class CancelledStreamAdapter(FakeCodexAdapter):
    async def stream_turn(self, thread_id: str, prompt: str, *, sandbox: str):
        raise asyncio.CancelledError()
        yield


class FailedTurnAdapter(FakeCodexAdapter):
    async def stream_turn(self, thread_id: str, prompt: str, *, sandbox: str):
        yield type(
            "Event",
            (),
            {
                "event_type": "turn/completed",
                "summary": "TurnStatus.failed",
                "thread_id": thread_id,
                "turn_id": "failed-turn-1",
                "raw_payload": {"status": "failed", "error": "SDK turn failed"},
            },
        )()


class InterruptedTurnAdapter(FakeCodexAdapter):
    async def stream_turn(self, thread_id: str, prompt: str, *, sandbox: str):
        yield type(
            "Event",
            (),
            {
                "event_type": "turn/completed",
                "summary": "TurnStatus.interrupted",
                "thread_id": thread_id,
                "turn_id": "interrupted-turn-1",
                "raw_payload": {"status": "interrupted"},
            },
        )()


class MissingTurnHandleAdapter(FakeCodexAdapter):
    async def interrupt(self, thread_id: str, turn_id: str) -> bool:
        return False


def write_project(root: Path, name: str = "demo_project", phase: int = 2) -> Path:
    project = root / name
    project.mkdir()
    prompts_dir = root / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    (prompts_dir / PHASE_PROMPTS[phase]).write_text(
        f"Phase {phase} test prompt.",
        encoding="utf-8",
    )
    (root / "AGENTS.md").write_text("Test AGENTS instructions.", encoding="utf-8")
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


def write_prompt_bundle_files(root: Path, phase: int = 2) -> None:
    (root / "AGENTS.md").write_text("AGENTS instructions: be sharply critical.", encoding="utf-8")
    (root / "CLAUDE.md").write_text("CLAUDE instructions should not be bundled.", encoding="utf-8")
    prompts_dir = root / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    (prompts_dir / PHASE_PROMPTS[phase]).write_text(
        "Phase prompt: search literature and narrow direction.",
        encoding="utf-8",
    )


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
        "completion_warning",
    ]


@pytest.mark.asyncio
async def test_start_phase_job_bundles_agents_phase_state_and_user_prompt(tmp_path: Path) -> None:
    write_project(tmp_path, phase=2)
    write_prompt_bundle_files(tmp_path, phase=2)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    adapter = PromptCaptureAdapter()
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=adapter)

    await service.start_phase_job(
        project_dir="demo_project",
        phase=2,
        action="Write literature search output",
        prompt="User feedback: focus on closed-loop data generation.",
    )

    bundled_prompt = adapter.prompts[0]
    assert "## Repository Instructions (AGENTS.md)" in bundled_prompt
    assert "AGENTS instructions: be sharply critical." in bundled_prompt
    assert "CLAUDE instructions should not be bundled." not in bundled_prompt
    assert "## Phase Prompt (prompts/02_literature_search.md)" in bundled_prompt
    assert "Phase prompt: search literature and narrow direction." in bundled_prompt
    assert '"current_phase": 2' in bundled_prompt
    assert "- The session working directory is already the project directory" in bundled_prompt
    assert "write paths with a {project_dir}/ prefix" in bundled_prompt
    assert "no nested demo_project/demo_project paths" in bundled_prompt
    assert "## User Prompt" in bundled_prompt
    assert bundled_prompt.rstrip().endswith("User feedback: focus on closed-loop data generation.")


@pytest.mark.asyncio
async def test_start_phase_job_marks_job_failed_when_stream_fails(tmp_path: Path) -> None:
    write_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FailingStreamAdapter())

    result = await service.start_phase_job(
        project_dir="demo_project",
        phase=2,
        action="Write literature search output",
        prompt="Find literature workers",
    )

    job = store.get_job(result.job_id)
    events = store.list_events(result.job_id)
    assert result.status == "failed"
    assert job["status"] == "failed"
    assert "SDK stream failed" in job["last_error"]
    assert events[-1]["event_type"] == "error"


@pytest.mark.asyncio
async def test_start_phase_job_marks_job_failed_when_sdk_turn_reports_failed(tmp_path: Path) -> None:
    write_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FailedTurnAdapter())

    result = await service.start_phase_job(
        project_dir="demo_project",
        phase=2,
        action="Write literature search output",
        prompt="Find literature workers",
    )

    job = store.get_job(result.job_id)
    events = store.list_events(result.job_id)
    assert result.status == "failed"
    assert job["status"] == "failed"
    assert job["turn_id"] == "failed-turn-1"
    assert "TurnStatus.failed" in job["last_error"]
    assert events[-1]["event_type"] == "error"


@pytest.mark.asyncio
async def test_start_phase_job_marks_job_interrupted_when_sdk_turn_reports_interrupted(tmp_path: Path) -> None:
    write_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=InterruptedTurnAdapter())

    result = await service.start_phase_job(
        project_dir="demo_project",
        phase=2,
        action="Write literature search output",
        prompt="Find literature workers",
    )

    job = store.get_job(result.job_id)
    events = store.list_events(result.job_id)
    assert result.status == "interrupted"
    assert job["status"] == "interrupted"
    assert job["turn_id"] == "interrupted-turn-1"
    assert events[-1]["event_type"] == "turn/completed"


@pytest.mark.asyncio
async def test_start_phase_job_marks_job_cancelled_when_request_is_cancelled(tmp_path: Path) -> None:
    write_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=CancelledStreamAdapter())

    with pytest.raises(asyncio.CancelledError):
        await service.start_phase_job(
            project_dir="demo_project",
            phase=2,
            action="Write literature search output",
            prompt="Find literature workers",
        )

    jobs = [row for row in store.table_names()]
    assert "jobs" in jobs
    with store._connect() as conn:
        job_id = conn.execute("select job_id from jobs").fetchone()["job_id"]
    job = store.get_job(job_id)
    events = store.list_events(job_id)
    assert job["status"] == "cancelled"
    assert job["completed_at"]
    assert events[-1]["event_type"] == "cancelled"


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
    assert events[-1]["event_type"] == "completion_warning"


@pytest.mark.asyncio
async def test_continue_job_bundles_agents_phase_state_and_user_prompt(tmp_path: Path) -> None:
    write_project(tmp_path, phase=5)
    write_prompt_bundle_files(tmp_path, phase=5)
    (tmp_path / "prompts" / "05_experiment_execution.md").write_text(
        "Phase prompt: execute verified experiments.",
        encoding="utf-8",
    )
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    adapter = PromptCaptureAdapter()
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=adapter)
    result = await service.start_phase_job(
        project_dir="demo_project",
        phase=5,
        action="Run experiment scripts",
        prompt="Initial experiment request.",
    )

    service.submit_approval(result.job_id, user_action="approved")
    await service.continue_job(
        result.job_id,
        action="Run experiment scripts",
        prompt="Approved user prompt: run the tiny smoke experiment.",
    )

    bundled_prompt = adapter.prompts[0]
    assert "## Repository Instructions (AGENTS.md)" in bundled_prompt
    assert "CLAUDE instructions should not be bundled." not in bundled_prompt
    assert "## Phase Prompt (prompts/05_experiment_execution.md)" in bundled_prompt
    assert "Phase prompt: execute verified experiments." in bundled_prompt
    assert '"current_phase": 5' in bundled_prompt
    assert bundled_prompt.rstrip().endswith("Approved user prompt: run the tiny smoke experiment.")


@pytest.mark.asyncio
async def test_continue_job_marks_job_cancelled_when_request_is_cancelled(tmp_path: Path) -> None:
    write_project(tmp_path, phase=5)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=CancelledStreamAdapter())
    result = await service.start_phase_job(
        project_dir="demo_project",
        phase=5,
        action="Run experiment scripts",
        prompt="Run experiments",
    )
    service.submit_approval(result.job_id, user_action="approved")

    with pytest.raises(asyncio.CancelledError):
        await service.continue_job(
            result.job_id,
            action="Run experiment scripts",
            prompt="Run approved experiments",
        )

    job = store.get_job(result.job_id)
    events = store.list_events(result.job_id)
    assert job["status"] == "cancelled"
    assert job["completed_at"]
    assert events[-1]["event_type"] == "cancelled"


@pytest.mark.asyncio
async def test_interrupt_updates_status_and_records_event(tmp_path: Path) -> None:
    write_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FakeCodexAdapter())
    store.create_job(
        job_id="job-running",
        project_dir="demo_project",
        phase=2,
        sub_step=None,
        role="main",
        thread_id="thread-1",
        turn_id="turn-1",
        status="running",
        approval_state="not_required",
        sandbox="workspace_write",
    )

    interrupted = await service.interrupt_job("job-running")

    updated = store.get_job("job-running")
    events = store.list_events("job-running")
    assert interrupted is True
    assert updated["status"] == "interrupted"
    assert events[-1]["event_type"] == "interrupted"


@pytest.mark.asyncio
async def test_interrupt_returns_false_for_finished_jobs(tmp_path: Path) -> None:
    write_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FakeCodexAdapter())
    result = await service.start_phase_job(
        project_dir="demo_project",
        phase=2,
        action="Write literature search output",
        prompt="Find literature workers",
    )
    assert result.status == "completed"

    interrupted = await service.interrupt_job(result.job_id)

    job = store.get_job(result.job_id)
    assert interrupted is False
    assert job["status"] == "completed"


class CompletesDuringInterruptAdapter(FakeCodexAdapter):
    """Finishes the job (terminal row write) while the SDK interrupt is in flight."""

    def __init__(self, store: RuntimeStore, job_id: str) -> None:
        super().__init__()
        self.store = store
        self.job_id = job_id

    async def interrupt(self, thread_id: str, turn_id: str) -> bool:
        self.store.update_job(self.job_id, status="completed", completed_at=utc_now())
        return True


@pytest.mark.asyncio
async def test_interrupt_returns_false_when_job_completes_during_interrupt(tmp_path: Path) -> None:
    write_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    adapter = CompletesDuringInterruptAdapter(store, "job-racing")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=adapter)
    store.create_job(
        job_id="job-racing",
        project_dir="demo_project",
        phase=2,
        sub_step=None,
        role="main",
        thread_id="thread-1",
        turn_id="turn-1",
        status="running",
        approval_state="not_required",
        sandbox="workspace_write",
    )

    interrupted = await service.interrupt_job("job-racing")

    job = store.get_job("job-racing")
    assert interrupted is False
    assert job["status"] == "completed"
    assert store.list_events("job-racing") == []


@pytest.mark.asyncio
async def test_interrupt_marks_stale_running_job_when_sdk_handle_is_missing(tmp_path: Path) -> None:
    write_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(
        repo_root=tmp_path,
        store=store,
        adapter=MissingTurnHandleAdapter(),
    )
    store.create_job(
        job_id="job-stale",
        project_dir="demo_project",
        phase=2,
        sub_step=None,
        role="main",
        thread_id="thread-stale",
        turn_id="turn-stale",
        status="running",
        approval_state="not_required",
        sandbox="workspace_write",
    )
    store.update_job(
        "job-stale",
        started_at=(datetime.now(UTC) - timedelta(minutes=31)).isoformat().replace("+00:00", "Z"),
    )

    interrupted = await service.interrupt_job("job-stale")

    job = store.get_job("job-stale")
    events = store.list_events("job-stale")
    assert interrupted is True
    assert job["status"] == "interrupted"
    assert job["completed_at"]
    assert "stale job" in job["last_error"]
    assert events[-1]["event_type"] == "interrupted"
    assert events[-1]["raw_payload_json"]


def test_format_sse_event_uses_stable_json_payload_with_event_id() -> None:
    event = {
        "event_id": 7,
        "event_type": "assistant_message",
        "summary": "Progress",
    }

    assert format_sse_event(event) == (
        'id: 7\n'
        'data: {"event_id":7,"event_type":"assistant_message","summary":"Progress"}\n\n'
    )


def test_format_sse_event_omits_id_line_for_synthetic_events() -> None:
    event = {"event_type": "job_status", "job_id": "job-1", "status": "completed"}

    assert format_sse_event(event) == (
        'data: {"event_type":"job_status","job_id":"job-1","status":"completed"}\n\n'
    )


@pytest.mark.asyncio
async def test_launch_phase_job_runs_in_background(tmp_path: Path) -> None:
    write_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FakeCodexAdapter())

    result = service.launch_phase_job(
        project_dir="demo_project",
        phase=2,
        action="Write literature search output",
        prompt="Find literature workers",
    )

    assert result.requires_approval is False
    assert result.status == "running"
    task = service._tasks[result.job_id]
    await task

    job = store.get_job(result.job_id)
    events = store.list_events(result.job_id)
    assert job["status"] == "completed"
    assert [event["event_type"] for event in events] == [
        "turn_started",
        "assistant_message",
        "turn_completed",
        "completion_warning",
    ]
    assert result.job_id not in service._tasks


@pytest.mark.asyncio
async def test_interrupt_cancels_in_process_background_job(tmp_path: Path) -> None:
    class HangingStreamAdapter(FakeCodexAdapter):
        async def stream_turn(self, thread_id: str, prompt: str, *, sandbox: str):
            await asyncio.sleep(60)
            yield

        async def interrupt(self, thread_id: str, turn_id: str) -> bool:
            return False

    write_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=HangingStreamAdapter())
    result = service.launch_phase_job(
        project_dir="demo_project",
        phase=2,
        action="Write literature search output",
        prompt="Find literature workers",
    )
    await asyncio.sleep(0)

    interrupted = await service.interrupt_job(result.job_id)
    task = service._tasks.get(result.job_id)
    if task is not None:
        with pytest.raises(asyncio.CancelledError):
            await task

    job = store.get_job(result.job_id)
    events = store.list_events(result.job_id)
    assert interrupted is True
    assert job["status"] == "cancelled"
    assert "interrupted" in {event["event_type"] for event in events}


@pytest.mark.asyncio
async def test_interrupt_marks_young_orphaned_job_without_waiting(tmp_path: Path) -> None:
    write_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(
        repo_root=tmp_path,
        store=store,
        adapter=MissingTurnHandleAdapter(),
    )
    store.create_job(
        job_id="job-young-orphan",
        project_dir="demo_project",
        phase=2,
        sub_step=None,
        role="main",
        thread_id="thread-orphan",
        turn_id="turn-orphan",
        status="running",
        approval_state="not_required",
        sandbox="workspace_write",
    )

    interrupted = await service.interrupt_job("job-young-orphan")

    job = store.get_job("job-young-orphan")
    assert interrupted is True
    assert job["status"] == "interrupted"


@pytest.mark.asyncio
async def test_continue_job_rejects_action_that_differs_from_approval(tmp_path: Path) -> None:
    write_project(tmp_path, phase=5)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=SpyAdapter())
    result = await service.start_phase_job(
        project_dir="demo_project",
        phase=5,
        action="Run experiment scripts",
        prompt="Run experiments",
    )
    service.submit_approval(result.job_id, user_action="approved")

    with pytest.raises(ValueError, match="match the approved action"):
        await service.continue_job(
            result.job_id,
            action="Delete project files",
            prompt="Do something else entirely",
        )


@pytest.mark.asyncio
async def test_submit_approval_rejects_job_not_waiting_for_approval(tmp_path: Path) -> None:
    write_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FakeCodexAdapter())
    result = await service.start_phase_job(
        project_dir="demo_project",
        phase=2,
        action="Write literature search output",
        prompt="Find literature workers",
    )

    with pytest.raises(ValueError, match="not waiting for approval"):
        service.submit_approval(result.job_id, user_action="approved")


@pytest.mark.asyncio
async def test_rejected_approval_finalizes_job(tmp_path: Path) -> None:
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

    approval = service.submit_approval(result.job_id, user_action="rejected")

    job = store.get_job(result.job_id)
    assert approval["final_status"] == "rejected"
    assert job["status"] == "rejected"
    assert job["completed_at"]
    assert adapter.started == 0
    with pytest.raises(ValueError):
        await service.continue_job(
            result.job_id,
            action="Run experiment scripts",
            prompt="Try anyway",
        )


class StateAdvancingAdapter(FakeCodexAdapter):
    """Fake adapter that advances the project state file during the turn."""

    def __init__(self, state_path: Path, *, phase: int, phase_status: str) -> None:
        super().__init__()
        self.state_path = state_path
        self.phase = phase
        self.phase_status = phase_status

    async def stream_turn(self, thread_id: str, prompt: str, *, sandbox: str):
        state = json.loads(self.state_path.read_text(encoding="utf-8"))
        state["current_phase"] = self.phase
        state["phase_status"] = self.phase_status
        self.state_path.write_text(json.dumps(state), encoding="utf-8")
        async for event in super().stream_turn(thread_id, prompt, sandbox=sandbox):
            yield event


@pytest.mark.asyncio
async def test_completed_job_warns_when_project_state_did_not_change(tmp_path: Path) -> None:
    write_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FakeCodexAdapter())

    result = await service.start_phase_job(
        project_dir="demo_project",
        phase=2,
        action="Write literature search output",
        prompt="Find literature workers",
    )

    events = store.list_events(result.job_id)
    warning = events[-1]
    assert result.status == "completed"
    assert warning["event_type"] == "completion_warning"
    assert "project state did not change" in warning["summary"]
    assert "still phase 2, status not_started" in warning["summary"]
    assert json.loads(warning["raw_payload_json"]) == {
        "phase": 2,
        "phase_status": "not_started",
    }


@pytest.mark.asyncio
async def test_completed_job_does_not_warn_when_project_state_changed(tmp_path: Path) -> None:
    project = write_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    adapter = StateAdvancingAdapter(
        project / ".research_state.json",
        phase=2,
        phase_status="completed",
    )
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=adapter)

    result = await service.start_phase_job(
        project_dir="demo_project",
        phase=2,
        action="Write literature search output",
        prompt="Find literature workers",
    )

    events = store.list_events(result.job_id)
    assert result.status == "completed"
    assert "completion_warning" not in {event["event_type"] for event in events}


def test_interrupt_note_helper_records_event_when_state_advanced(tmp_path: Path) -> None:
    project = write_project(tmp_path, phase=2)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FakeCodexAdapter())
    state = json.loads((project / ".research_state.json").read_text(encoding="utf-8"))
    state["current_phase"] = 3
    state["phase_status"] = "in_progress"
    (project / ".research_state.json").write_text(json.dumps(state), encoding="utf-8")

    service._add_interrupt_note_if_state_advanced(
        job_id="job-note",
        project_dir="demo_project",
        job_phase=2,
    )

    events = store.list_events("job-note")
    assert [event["event_type"] for event in events] == ["interrupt_note"]
    assert events[0]["summary"] == (
        "Note: project state shows phase 3 (in_progress); "
        "the phase work may have completed before this interruption."
    )
    assert json.loads(events[0]["raw_payload_json"]) == {
        "current_phase": 3,
        "phase_status": "in_progress",
    }


def test_interrupt_note_helper_records_event_when_phase_completed(tmp_path: Path) -> None:
    project = write_project(tmp_path, phase=2)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FakeCodexAdapter())
    state = json.loads((project / ".research_state.json").read_text(encoding="utf-8"))
    state["phase_status"] = "completed"
    (project / ".research_state.json").write_text(json.dumps(state), encoding="utf-8")

    service._add_interrupt_note_if_state_advanced(
        job_id="job-note",
        project_dir="demo_project",
        job_phase=2,
    )

    events = store.list_events("job-note")
    assert [event["event_type"] for event in events] == ["interrupt_note"]


def test_interrupt_note_helper_skips_duplicate_notes(tmp_path: Path) -> None:
    project = write_project(tmp_path, phase=2)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FakeCodexAdapter())
    state = json.loads((project / ".research_state.json").read_text(encoding="utf-8"))
    state["current_phase"] = 3
    state["phase_status"] = "in_progress"
    (project / ".research_state.json").write_text(json.dumps(state), encoding="utf-8")

    service._add_interrupt_note_if_state_advanced(
        job_id="job-note",
        project_dir="demo_project",
        job_phase=2,
    )
    service._add_interrupt_note_if_state_advanced(
        job_id="job-note",
        project_dir="demo_project",
        job_phase=2,
    )

    events = store.list_events("job-note")
    assert [event["event_type"] for event in events] == ["interrupt_note"]


def test_interrupt_note_helper_is_silent_when_state_did_not_advance(tmp_path: Path) -> None:
    write_project(tmp_path, phase=2)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FakeCodexAdapter())

    service._add_interrupt_note_if_state_advanced(
        job_id="job-note",
        project_dir="demo_project",
        job_phase=2,
    )

    assert store.list_events("job-note") == []


@pytest.mark.asyncio
async def test_interrupt_job_adds_note_when_state_advanced(tmp_path: Path) -> None:
    project = write_project(tmp_path, phase=2)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FakeCodexAdapter())
    store.create_job(
        job_id="job-running",
        project_dir="demo_project",
        phase=2,
        sub_step=None,
        role="main",
        thread_id="thread-1",
        turn_id="turn-1",
        status="running",
        approval_state="not_required",
        sandbox="workspace_write",
    )
    state = json.loads((project / ".research_state.json").read_text(encoding="utf-8"))
    state["current_phase"] = 3
    (project / ".research_state.json").write_text(json.dumps(state), encoding="utf-8")

    interrupted = await service.interrupt_job("job-running")

    events = store.list_events("job-running")
    assert interrupted is True
    assert [event["event_type"] for event in events] == ["interrupted", "interrupt_note"]


@pytest.mark.asyncio
async def test_create_phase_job_raises_project_busy_when_job_is_active(tmp_path: Path) -> None:
    write_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FakeCodexAdapter())
    store.create_job(
        job_id="job-active",
        project_dir="demo_project",
        phase=2,
        sub_step=None,
        role="main",
        thread_id=None,
        turn_id=None,
        status="running",
        approval_state="not_required",
        sandbox="workspace_write",
    )

    with pytest.raises(ProjectBusyError) as exc_info:
        await service.start_phase_job(
            project_dir="demo_project",
            phase=2,
            action="Write literature search output",
            prompt="Find literature workers",
        )

    assert exc_info.value.active_job_id == "job-active"


@pytest.mark.asyncio
async def test_create_phase_job_busy_guard_also_covers_approval_jobs(tmp_path: Path) -> None:
    write_project(tmp_path, phase=5)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FakeCodexAdapter())
    store.create_job(
        job_id="job-active",
        project_dir="demo_project",
        phase=5,
        sub_step=None,
        role="main",
        thread_id=None,
        turn_id=None,
        status="queued",
        approval_state="not_required",
        sandbox="workspace_write",
    )

    with pytest.raises(ProjectBusyError) as exc_info:
        await service.start_phase_job(
            project_dir="demo_project",
            phase=5,
            action="Run experiment scripts",
            prompt="Run experiments",
        )

    assert exc_info.value.active_job_id == "job-active"


@pytest.mark.asyncio
async def test_launch_continue_job_raises_project_busy_when_another_job_is_active(tmp_path: Path) -> None:
    write_project(tmp_path, phase=5)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FakeCodexAdapter())
    result = await service.start_phase_job(
        project_dir="demo_project",
        phase=5,
        action="Run experiment scripts",
        prompt="Run experiments",
    )
    service.submit_approval(result.job_id, user_action="approved")
    store.create_job(
        job_id="job-active",
        project_dir="demo_project",
        phase=5,
        sub_step=None,
        role="main",
        thread_id=None,
        turn_id=None,
        status="running",
        approval_state="not_required",
        sandbox="workspace_write",
    )

    with pytest.raises(ProjectBusyError) as exc_info:
        service.launch_continue_job(
            result.job_id,
            action="Run experiment scripts",
            prompt="Run approved experiments",
        )

    assert exc_info.value.active_job_id == "job-active"
    assert store.get_job(result.job_id)["status"] == "waiting_to_continue"
    assert result.job_id not in service._tasks


def test_recover_orphaned_jobs_marks_active_jobs_interrupted(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FakeCodexAdapter())
    for job_id, status in (("job-a", "running"), ("job-b", "queued"), ("job-c", "completed")):
        store.create_job(
            job_id=job_id,
            project_dir="demo_project",
            phase=2,
            sub_step=None,
            role="main",
            thread_id=None,
            turn_id=None,
            status=status,
            approval_state="not_required",
            sandbox="workspace_write",
        )

    recovered = service.recover_orphaned_jobs()

    assert recovered == 2
    assert store.get_job("job-a")["status"] == "interrupted"
    assert store.get_job("job-b")["status"] == "interrupted"
    assert store.get_job("job-c")["status"] == "completed"
