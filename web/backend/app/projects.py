from __future__ import annotations

import json
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
    projects: list[ProjectSummary] = []

    for child in sorted(status.root.iterdir(), key=lambda path: path.name.lower()):
        if not child.is_dir():
            continue
        state_path = child / ".research_state.json"
        if not state_path.exists():
            continue
        projects.append(_summarize_project(status.root, child, state_path))

    return ProjectDiscoveryResult(
        root=status.root,
        setup_required=status.setup_required,
        config_exists=status.config_exists,
        projects=projects,
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
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid research state JSON: {exc.msg}") from exc

    if not isinstance(data, dict):
        raise ValueError("Research state must be a JSON object")
    return data


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
