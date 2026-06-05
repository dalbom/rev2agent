from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi import HTTPException

import app.main as main
from app.database import RuntimeStore


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
