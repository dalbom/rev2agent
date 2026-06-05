from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import ProjectDiscoveryResult, ProjectSummary, RepositoryStatus


PHASE_LABELS: dict[int, str] = {
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


def get_repository_status(repo_root: Path) -> RepositoryStatus:
    root = repo_root.resolve()
    config_exists = (root / ".rev2agent_config.json").exists()
    return RepositoryStatus(
        root=root,
        config_exists=config_exists,
        setup_required=not config_exists,
    )


def discover_projects(repo_root: Path) -> ProjectDiscoveryResult:
    status = get_repository_status(repo_root)
    projects_by_dir: dict[str, ProjectSummary] = {}

    for child in sorted(status.root.iterdir(), key=lambda path: path.name.lower()):
        if not child.is_dir():
            continue
        state_path = child / ".research_state.json"
        if not state_path.exists():
            continue
        project = _summarize_project(status.root, child, state_path)
        if project.project_status == "archived":
            continue
        existing = projects_by_dir.get(project.project_dir)
        projects_by_dir[project.project_dir] = _preferred_project_summary(existing, project)

    return ProjectDiscoveryResult(
        root=status.root,
        setup_required=status.setup_required,
        config_exists=status.config_exists,
        projects=list(projects_by_dir.values()),
    )


def load_project_state(repo_root: Path, project_path: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    resolved_project = project_path.resolve()
    if not _is_relative_to(resolved_project, root):
        raise ValueError("Project path is outside repository")

    state_path = resolved_project / ".research_state.json"
    if not state_path.exists():
        raise FileNotFoundError(f"Missing research state: {state_path}")

    try:
        data = json.loads(state_path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid research state JSON: {exc.msg}") from exc

    if not isinstance(data, dict):
        raise ValueError("Research state must be a JSON object")
    return data


def create_project_draft(repo_root: Path, *, research_idea: str = "") -> ProjectSummary:
    root = repo_root.resolve()
    project_path = _next_available_draft_path(root)
    project_path.mkdir(exist_ok=True)
    state_path = project_path / ".research_state.json"
    idea = research_idea.strip()

    if not state_path.exists():
        now = _utc_now()
        project_dir = project_path.name
        state = {
            "project_dir": project_dir,
            "current_phase": 1,
            "sub_step": None,
            "current_round": 0,
            "phase_status": "in_progress",
            "project_status": "active",
            "created_at": now,
            "updated_at": now,
            "topic": {
                "broad_topic": "",
                "specific_topic": idea,
                "research_question": "",
                "positioning": "",
                "target_venue": "",
                "target_dataset": [],
                "metrics": [],
            },
            "phase_history": [],
        }
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    elif idea:
        state = load_project_state(root, project_path)
        topic = state.get("topic") if isinstance(state.get("topic"), dict) else {}
        topic["specific_topic"] = idea
        state["topic"] = topic
        state["updated_at"] = _utc_now()
        state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    return _summarize_project(root, project_path, state_path)


def archive_project(repo_root: Path, project_dir: str) -> ProjectSummary:
    root = repo_root.resolve()
    project_path = root / project_dir
    state = load_project_state(root, project_path)
    state["project_status"] = "archived"
    state["phase_status"] = "archived"
    state["updated_at"] = _utc_now()
    state_path = project_path.resolve() / ".research_state.json"
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    return _summarize_project(root, project_path, state_path)


def _summarize_project(root: Path, project_path: Path, state_path: Path) -> ProjectSummary:
    try:
        state = load_project_state(root, project_path)
    except ValueError as exc:
        return ProjectSummary(
            project_dir=project_path.name,
            state_path=state_path,
            healthy=False,
            health_message=str(exc),
        )

    phase = _as_int(state.get("current_phase"))
    topic = state.get("topic") if isinstance(state.get("topic"), dict) else {}
    active_runs = _count_active_runs(state)

    return ProjectSummary(
        project_dir=str(state.get("project_dir") or project_path.name),
        state_path=state_path,
        healthy=True,
        phase=phase,
        phase_label=PHASE_LABELS.get(phase, "Unknown") if phase is not None else "Unknown",
        phase_status=str(state.get("phase_status") or "unknown"),
        project_status=str(state.get("project_status") or "unknown"),
        topic=_topic_label(topic),
        updated_at=state.get("updated_at") if isinstance(state.get("updated_at"), str) else None,
        active_runs=active_runs,
    )


def _next_available_draft_path(root: Path) -> Path:
    for index in range(1, 100):
        name = "_new_project_draft" if index == 1 else f"_new_project_draft_{index}"
        candidate = root / name
        state_path = candidate / ".research_state.json"
        if not state_path.exists():
            return candidate
        try:
            state = load_project_state(root, candidate)
        except (FileNotFoundError, ValueError):
            return candidate
        if state.get("project_dir") == name and not _draft_has_artifacts(candidate):
            return candidate
    raise RuntimeError("Could not find an available draft project path")


def _draft_has_artifacts(project_path: Path) -> bool:
    for path in project_path.rglob("*"):
        if path.is_file() and path.name != ".research_state.json":
            return True
    return False


def _preferred_project_summary(
    existing: ProjectSummary | None,
    candidate: ProjectSummary,
) -> ProjectSummary:
    if existing is None:
        return candidate
    if _is_canonical_project_path(candidate) and not _is_canonical_project_path(existing):
        return candidate
    if candidate.healthy and not existing.healthy:
        return candidate
    return existing


def _is_canonical_project_path(project: ProjectSummary) -> bool:
    return project.state_path.parent.name == project.project_dir


def _topic_label(topic: dict[str, Any]) -> str:
    for key in ("specific_topic", "research_question", "broad_topic"):
        value = topic.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _count_active_runs(state: dict[str, Any]) -> int:
    experiment = state.get("experiment")
    if not isinstance(experiment, dict):
        return 0
    active_runs = experiment.get("active_runs")
    if not isinstance(active_runs, list):
        return 0
    return sum(1 for run in active_runs if isinstance(run, dict) and run.get("status") == "running")


def _as_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
