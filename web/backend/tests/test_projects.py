from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.projects import (
    PHASE_LABELS,
    discover_projects,
    get_repository_status,
    load_project_state,
)


def write_state(project_dir: Path, **overrides: object) -> None:
    project_dir.mkdir()
    state = {
        "project_dir": project_dir.name,
        "current_phase": 4,
        "sub_step": None,
        "current_round": 1,
        "phase_status": "waiting_for_user",
        "project_status": "active",
        "updated_at": "2026-06-02T10:00:00Z",
        "topic": {
            "broad_topic": "Vision",
            "specific_topic": "Synthetic data for segmentation",
        },
    }
    state.update(overrides)
    (project_dir / ".research_state.json").write_text(json.dumps(state), encoding="utf-8")


def test_phase_labels_are_friendly_and_cover_all_phases() -> None:
    assert PHASE_LABELS == {
        0: "Setup",
        1: "Choose Topic",
        2: "Search Papers",
        3: "Plan Research",
        4: "Design Experiments",
        5: "Run Experiments",
        6: "Understand Results",
        7: "Write Paper",
        8: "Review Paper",
    }


def test_repository_status_reports_missing_setup_config(tmp_path: Path) -> None:
    status = get_repository_status(tmp_path)

    assert status.root == tmp_path
    assert status.config_exists is False
    assert status.setup_required is True


def test_discover_projects_summarizes_valid_project(tmp_path: Path) -> None:
    write_state(tmp_path / "synthetic_segmentation")
    (tmp_path / ".rev2agent_config.json").write_text("{}", encoding="utf-8")

    result = discover_projects(tmp_path)

    assert result.setup_required is False
    assert len(result.projects) == 1
    project = result.projects[0]
    assert project.project_dir == "synthetic_segmentation"
    assert project.phase == 4
    assert project.phase_label == "Design Experiments"
    assert project.phase_status == "waiting_for_user"
    assert project.topic == "Synthetic data for segmentation"
    assert project.healthy is True


def test_discover_projects_surfaces_invalid_state_files(tmp_path: Path) -> None:
    broken = tmp_path / "broken_project"
    broken.mkdir()
    (broken / ".research_state.json").write_text("{not json", encoding="utf-8")

    result = discover_projects(tmp_path)

    assert len(result.projects) == 1
    project = result.projects[0]
    assert project.project_dir == "broken_project"
    assert project.healthy is False
    assert "Invalid research state JSON" in project.health_message


def test_load_project_state_rejects_paths_outside_repo(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside_project"
    outside.mkdir(exist_ok=True)

    with pytest.raises(ValueError, match="outside repository"):
        load_project_state(tmp_path, outside)
