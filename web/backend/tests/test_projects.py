from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.projects import (
    PHASE_LABELS,
    archive_project,
    create_project_draft,
    discover_projects,
    get_repository_status,
    load_project_state,
)


def write_state(project_path: Path, **overrides: object) -> None:
    project_path.mkdir()
    state = {
        "project_dir": project_path.name,
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
    (project_path / ".research_state.json").write_text(json.dumps(state), encoding="utf-8")


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


def test_discover_projects_hides_archived_projects_by_default(tmp_path: Path) -> None:
    write_state(tmp_path / "active_project")
    write_state(tmp_path / "archived_project", project_status="archived")

    result = discover_projects(tmp_path)

    assert [project.project_dir for project in result.projects] == ["active_project"]


def test_discover_projects_deduplicates_finalized_draft_copy(tmp_path: Path) -> None:
    write_state(tmp_path / "_new_project_draft", **{"project_dir": "final_project"})
    write_state(tmp_path / "final_project", **{"project_dir": "final_project"})

    result = discover_projects(tmp_path)

    assert [project.project_dir for project in result.projects] == ["final_project"]
    assert result.projects[0].state_path == tmp_path / "final_project" / ".research_state.json"


def test_archive_project_marks_project_archived_and_removes_from_discovery(tmp_path: Path) -> None:
    write_state(tmp_path / "synthetic_segmentation")

    archived = archive_project(tmp_path, "synthetic_segmentation")
    state = json.loads((tmp_path / "synthetic_segmentation" / ".research_state.json").read_text(encoding="utf-8"))

    assert archived.project_status == "archived"
    assert state["project_status"] == "archived"
    assert state["phase_status"] == "archived"
    assert discover_projects(tmp_path).projects == []


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


def test_load_project_state_accepts_utf8_bom_state_files(tmp_path: Path) -> None:
    project = tmp_path / "bom_project"
    project.mkdir()
    state = {"project_dir": "bom_project", "current_phase": 6}
    (project / ".research_state.json").write_text(json.dumps(state), encoding="utf-8-sig")

    loaded = load_project_state(tmp_path, project)

    assert loaded["current_phase"] == 6


def test_create_project_draft_initializes_recoverable_phase_one_state(tmp_path: Path) -> None:
    draft = create_project_draft(tmp_path)
    state_path = tmp_path / "_new_project_draft" / ".research_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert draft.project_dir == "_new_project_draft"
    assert draft.phase == 1
    assert draft.phase_label == "Choose Topic"
    assert draft.phase_status == "in_progress"
    assert state["project_dir"] == "_new_project_draft"
    assert state["current_phase"] == 1
    assert state["phase_status"] == "in_progress"
    assert "created_at" in state


def test_create_project_draft_persists_research_idea(tmp_path: Path) -> None:
    idea = "Closed-loop synthetic data generation for downstream task improvement"

    draft = create_project_draft(tmp_path, research_idea=idea)
    state_path = tmp_path / "_new_project_draft" / ".research_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert draft.topic == idea
    assert state["topic"]["specific_topic"] == idea


def test_create_project_draft_reuses_existing_draft(tmp_path: Path) -> None:
    first = create_project_draft(tmp_path)
    second = create_project_draft(tmp_path)

    assert second.project_dir == first.project_dir
    assert len(discover_projects(tmp_path).projects) == 1


def test_create_project_draft_uses_new_draft_when_existing_draft_has_artifacts(tmp_path: Path) -> None:
    first = create_project_draft(tmp_path)
    summary_dir = tmp_path / first.project_dir / "summaries"
    summary_dir.mkdir()
    (summary_dir / "phase1_topic.md").write_text("# Old draft\n", encoding="utf-8")

    draft = create_project_draft(tmp_path, research_idea="fresh project")

    assert draft.project_dir == "_new_project_draft_2"
    state = json.loads((tmp_path / "_new_project_draft_2" / ".research_state.json").read_text(encoding="utf-8"))
    assert state["topic"]["specific_topic"] == "fresh project"


def test_create_project_draft_uses_new_draft_when_old_draft_was_finalized(tmp_path: Path) -> None:
    write_state(tmp_path / "_new_project_draft", **{"project_dir": "final_project"})
    write_state(tmp_path / "final_project", **{"project_dir": "final_project"})

    draft = create_project_draft(tmp_path, research_idea="second project")

    assert draft.project_dir == "_new_project_draft_2"
    state = json.loads((tmp_path / "_new_project_draft_2" / ".research_state.json").read_text(encoding="utf-8"))
    assert state["project_dir"] == "_new_project_draft_2"
    assert state["topic"]["specific_topic"] == "second project"
