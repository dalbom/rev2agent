from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class RepositoryStatus(BaseModel):
    root: Path
    config_exists: bool
    setup_required: bool


class ProjectSummary(BaseModel):
    project_dir: str
    state_path: Path
    healthy: bool
    health_message: str | None = None
    phase: int | None = None
    phase_label: str = "Unknown"
    phase_status: str = "unknown"
    project_status: str = "unknown"
    topic: str = ""
    updated_at: str | None = None
    active_runs: int = 0


class ProjectDiscoveryResult(BaseModel):
    root: Path
    setup_required: bool
    config_exists: bool
    projects: list[ProjectSummary] = Field(default_factory=list)
