from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.main as main
from app.codex_adapter import FakeCodexAdapter
from app.database import RuntimeStore
from app.phases import PhaseJobService


def write_state(root: Path, project_dir: str = "demo_project", phase: int = 1) -> None:
    project = root / project_dir
    project.mkdir()
    (project / ".research_state.json").write_text(
        json.dumps(
            {
                "project_dir": project_dir,
                "current_phase": phase,
                "phase_status": "in_progress",
                "project_status": "active",
                "topic": {"specific_topic": "Synthetic data"},
            }
        ),
        encoding="utf-8",
    )


def test_host_only_setup_creates_phase_zero_config_and_gitignore(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "repository_root", lambda: tmp_path)

    response = main.complete_host_only_setup()

    config = json.loads((tmp_path / ".rev2agent_config.json").read_text(encoding="utf-8"))
    assert config["version"] == 1
    assert config["providers"] == []
    assert config["roles"]["verification"]["provider"] == "host-native"
    assert ".rev2agent_config.json" in (tmp_path / ".gitignore").read_text(encoding="utf-8")
    assert response["repository"]["config_exists"] is True


def test_create_project_requires_phase_zero_setup(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(main, "repository_root", lambda: tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        main.create_project(main.CreateProjectRequest(research_idea="closed loop data"))

    assert exc_info.value.status_code == 409
    assert "Phase 0 setup" in str(exc_info.value.detail)
    assert not (tmp_path / "_new_project_draft").exists()


def make_job(
    store: RuntimeStore,
    job_id: str,
    *,
    project_dir: str = "demo_project",
    phase: int = 2,
    status: str = "running",
) -> None:
    store.create_job(
        job_id=job_id,
        project_dir=project_dir,
        phase=phase,
        sub_step=None,
        role="main",
        thread_id=None,
        turn_id=None,
        status=status,
        approval_state="not_required",
        sandbox="workspace_write",
    )


def patch_services(tmp_path: Path, monkeypatch) -> RuntimeStore:
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FakeCodexAdapter())
    monkeypatch.setattr(main, "repository_root", lambda: tmp_path)
    monkeypatch.setattr(main, "runtime_store", lambda: store)
    monkeypatch.setattr(main, "phase_service", lambda: service)
    return store


def test_create_project_with_invalid_name_returns_400(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".rev2agent_config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(main, "repository_root", lambda: tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        main.create_project(main.CreateProjectRequest(project_name="bad name!"))

    assert exc_info.value.status_code == 400
    assert "Project name must start with a letter or digit" in str(exc_info.value.detail)


def test_create_project_with_existing_folder_returns_400(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".rev2agent_config.json").write_text("{}", encoding="utf-8")
    (tmp_path / "taken").mkdir()
    monkeypatch.setattr(main, "repository_root", lambda: tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        main.create_project(main.CreateProjectRequest(project_name="taken"))

    assert exc_info.value.status_code == 400
    assert "A folder named 'taken' already exists" in str(exc_info.value.detail)


def test_create_project_with_name_creates_named_project(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".rev2agent_config.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(main, "repository_root", lambda: tmp_path)

    project = main.create_project(
        main.CreateProjectRequest(research_idea="closed loop data", project_name="closed_loop")
    )
    state = json.loads(
        (tmp_path / "closed_loop" / ".research_state.json").read_text(encoding="utf-8")
    )

    assert project.project_dir == "closed_loop"
    assert state["project_dir"] == "closed_loop"
    assert state["topic"]["specific_topic"] == "closed loop data"


def test_start_phase_job_returns_409_when_another_job_is_active(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".rev2agent_config.json").write_text("{}", encoding="utf-8")
    write_state(tmp_path, phase=2)
    store = patch_services(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        make_job(store, "job-active", status="running")
        response = client.post(
            "/api/projects/demo_project/phase/2/jobs",
            json={"action": "Write literature search output", "prompt": "Find literature"},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Another job (job-active) is already active for this project; "
        "stop it or wait for it to finish."
    )


def test_continue_job_returns_409_when_another_project_job_is_busy(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".rev2agent_config.json").write_text("{}", encoding="utf-8")
    write_state(tmp_path, phase=2)
    store = patch_services(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        make_job(store, "job-waiting", status="waiting_to_continue")
        store.update_job("job-waiting", approval_state="approved")
        make_job(store, "job-active", status="running")
        response = client.post(
            "/api/jobs/job-waiting/continue",
            json={"action": "Write literature search output", "prompt": "Continue the search"},
        )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Another job (job-active) is already active for this project; "
        "stop it or wait for it to finish."
    )
    assert store.get_job("job-waiting")["status"] == "waiting_to_continue"


class TailEventStore(RuntimeStore):
    """Simulates finalization writes landing between the SSE drain and the status check."""

    def __init__(self, db_path: Path) -> None:
        super().__init__(db_path)
        self.get_job_calls = 0

    def get_job(self, job_id: str):
        self.get_job_calls += 1
        # Call 1 is the endpoint's existence guard; call 2 is the status check
        # inside the stream loop, right after the first events drain.
        if self.get_job_calls == 2:
            self.add_event(
                job_id=job_id,
                event_type="completion_warning",
                summary="tail warning written during finalization",
            )
            self.update_job(job_id, status="completed")
        return super().get_job(job_id)


def test_stream_drains_tail_events_written_before_terminal_status(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".rev2agent_config.json").write_text("{}", encoding="utf-8")
    write_state(tmp_path, phase=2)
    store = TailEventStore(tmp_path / "runtime.sqlite3")
    service = PhaseJobService(repo_root=tmp_path, store=store, adapter=FakeCodexAdapter())
    monkeypatch.setattr(main, "repository_root", lambda: tmp_path)
    monkeypatch.setattr(main, "runtime_store", lambda: store)
    monkeypatch.setattr(main, "phase_service", lambda: service)

    with TestClient(main.app) as client:
        make_job(store, "job-finishing", status="running")
        response = client.get("/api/jobs/job-finishing/events/stream")

    assert response.status_code == 200
    body = response.text
    assert "tail warning written during finalization" in body
    assert '"event_type":"job_status"' in body
    assert '"status":"completed"' in body
    # The tail drain must come before the synthetic close event.
    assert body.index("tail warning written during finalization") < body.index(
        '"event_type":"job_status"'
    )


def test_list_project_jobs_endpoint_filters_active_jobs_and_orders_newest_first(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / ".rev2agent_config.json").write_text("{}", encoding="utf-8")
    write_state(tmp_path, phase=2)
    store = patch_services(tmp_path, monkeypatch)

    with TestClient(main.app) as client:
        rows = (
            ("job-done", "completed", "2026-06-11T10:00:00Z"),
            ("job-waiting", "waiting_for_approval", "2026-06-11T11:00:00Z"),
            ("job-running", "running", "2026-06-11T12:00:00Z"),
        )
        for job_id, status, started_at in rows:
            make_job(store, job_id, status=status)
            store.update_job(job_id, started_at=started_at)
        make_job(store, "job-other", project_dir="other_project", status="running")

        all_response = client.get("/api/projects/demo_project/jobs")
        active_response = client.get("/api/projects/demo_project/jobs", params={"active": "true"})

    assert all_response.status_code == 200
    assert [job["job_id"] for job in all_response.json()] == [
        "job-running",
        "job-waiting",
        "job-done",
    ]
    assert all_response.json()[0]["status"] == "running"
    assert all_response.json()[0]["project_dir"] == "demo_project"
    assert active_response.status_code == 200
    assert [job["job_id"] for job in active_response.json()] == ["job-running", "job-waiting"]


def test_archive_project_endpoint_marks_project_archived(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".rev2agent_config.json").write_text("{}", encoding="utf-8")
    write_state(tmp_path)
    monkeypatch.setattr(main, "repository_root", lambda: tmp_path)

    response = main.archive_project_endpoint("demo_project")
    state = json.loads((tmp_path / "demo_project" / ".research_state.json").read_text(encoding="utf-8"))

    assert response.project_status == "archived"
    assert state["project_status"] == "archived"


@pytest.mark.asyncio
async def test_phase_job_requires_phase_zero_setup(tmp_path: Path, monkeypatch) -> None:
    write_state(tmp_path)
    monkeypatch.setattr(main, "repository_root", lambda: tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        await main.start_phase_job(
            "demo_project",
            1,
            main.StartPhaseJobRequest(action="Continue Choose Topic", prompt="Run Phase 1"),
        )

    assert exc_info.value.status_code == 409
    assert "Phase 0 setup" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_phase_job_rejects_phase_mismatch(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".rev2agent_config.json").write_text("{}", encoding="utf-8")
    write_state(tmp_path, phase=1)
    monkeypatch.setattr(main, "repository_root", lambda: tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        await main.start_phase_job(
            "demo_project",
            5,
            main.StartPhaseJobRequest(action="Continue Run Experiments", prompt="Run Phase 5"),
        )

    assert exc_info.value.status_code == 409
    assert "Current project phase is 1" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_experiment_action_is_only_allowed_in_phase_five(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".rev2agent_config.json").write_text("{}", encoding="utf-8")
    write_state(tmp_path, phase=1)
    monkeypatch.setattr(main, "repository_root", lambda: tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        await main.start_phase_job(
            "demo_project",
            1,
            main.StartPhaseJobRequest(action="Run experiment scripts", prompt="Run smoke experiment"),
        )

    assert exc_info.value.status_code == 409
    assert "Phase 5" in str(exc_info.value.detail)


@pytest.mark.asyncio
async def test_continue_job_rejects_old_experiment_job_outside_phase_five(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / ".rev2agent_config.json").write_text("{}", encoding="utf-8")
    write_state(tmp_path, phase=1)
    monkeypatch.setattr(main, "repository_root", lambda: tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    store.create_job(
        job_id="job-risk",
        project_dir="demo_project",
        phase=1,
        sub_step=None,
        role="main",
        thread_id=None,
        turn_id=None,
        status="waiting_to_continue",
        approval_state="approved",
        sandbox="workspace_write",
    )
    monkeypatch.setattr(main, "runtime_store", lambda: store)

    with pytest.raises(HTTPException) as exc_info:
        await main.continue_job(
            "job-risk",
            main.ContinueJobRequest(action="Run experiment scripts", prompt="Run smoke experiment"),
        )

    assert exc_info.value.status_code == 409
    assert "Phase 5" in str(exc_info.value.detail)
