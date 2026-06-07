from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from typing import Any

from .database import RuntimeStore


TEXT_SUFFIXES = {".bib", ".csv", ".json", ".log", ".md", ".tex", ".txt", ".yaml", ".yml"}
MAX_TEXT_BYTES = 512_000


class ArtifactService:
    def __init__(self, *, repo_root: Path, store: RuntimeStore) -> None:
        self.repo_root = repo_root.resolve()
        self.store = store

    def index_project(self, project_dir: str) -> list[dict[str, Any]]:
        project_path = self._project_root(project_dir)
        if not project_path.exists():
            raise FileNotFoundError(project_dir)

        known_paths: set[str] = set()
        for artifact in self.store.list_artifacts(project_dir):
            path = (self.repo_root / artifact["path"]).resolve()
            if is_relative_to(path, project_path) and path.exists():
                known_paths.add(artifact["path"])
                continue
            self.store.delete_artifact(artifact["artifact_id"])

        for path in sorted(project_path.rglob("*"), key=natural_path_key):
            if not path.is_file() or path.name == ".research_state.json":
                continue
            artifact_type = artifact_type_for(project_path, path)
            if artifact_type is None:
                continue
            relative_repo_path = path.relative_to(self.repo_root).as_posix()
            if relative_repo_path in known_paths:
                continue
            self.store.add_artifact(
                project_dir=project_dir,
                job_id=None,
                path=relative_repo_path,
                artifact_type=artifact_type,
                title=path.name,
                validation_status="unknown",
            )
            known_paths.add(relative_repo_path)
        return sorted(self.store.list_artifacts(project_dir), key=artifact_sort_key)

    def read_artifact(self, project_dir: str, artifact_id: int) -> dict[str, Any]:
        artifact = self.store.get_artifact(artifact_id)
        if artifact["project_dir"] != project_dir:
            raise ValueError("Artifact does not belong to the requested project")

        path = (self.repo_root / artifact["path"]).resolve()
        project_root = self._project_root(project_dir)
        if not is_relative_to(path, project_root):
            raise ValueError("Artifact path is outside project")
        if not path.exists():
            raise FileNotFoundError(path)

        mime_type = mime_type_for(path)
        size = path.stat().st_size
        if is_text_artifact(path):
            if size > MAX_TEXT_BYTES:
                raise ValueError("Artifact is too large to preview safely")
            return {
                "artifact_id": artifact_id,
                "kind": "text",
                "mime_type": mime_type,
                "size_bytes": size,
                "content": path.read_text(encoding="utf-8", errors="replace"),
            }
        return {
            "artifact_id": artifact_id,
            "kind": "binary",
            "mime_type": mime_type,
            "size_bytes": size,
            "content": None,
        }

    def resolve_project_path(self, project_dir: str, relative_path: str) -> Path:
        project_root = self._project_root(project_dir)
        path = (project_root / relative_path).resolve()
        if not is_relative_to(path, project_root):
            raise ValueError("Path is outside project")
        return path

    def _project_root(self, project_dir: str) -> Path:
        path = (self.repo_root / project_dir).resolve()
        if not is_relative_to(path, self.repo_root):
            raise ValueError("Project path is outside repository")
        return path


def artifact_type_for(project_root: Path, path: Path) -> str | None:
    relative = path.relative_to(project_root).as_posix()
    suffix = path.suffix.lower()
    if relative.startswith("summaries/"):
        return "summary"
    if relative.startswith("literature/"):
        return "literature"
    if relative.startswith("experiment/configs/"):
        return "experiment_config"
    if relative.startswith("experiment/logs/"):
        return "log"
    if relative.startswith("experiment/results/"):
        return "result"
    if relative.startswith("manuscript/figures/"):
        return "figure"
    if relative.startswith("manuscript/tables/"):
        return "table"
    if relative.startswith("manuscript/") and suffix == ".pdf":
        return "pdf"
    if relative.startswith("manuscript/"):
        return "manuscript"
    return None


def is_text_artifact(path: Path) -> bool:
    return path.suffix.lower() in TEXT_SUFFIXES


def mime_type_for(path: Path) -> str:
    if path.suffix.lower() == ".md":
        return "text/markdown"
    if path.suffix.lower() == ".tex":
        return "application/x-tex"
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


def artifact_sort_key(artifact: dict[str, Any]) -> tuple[tuple[tuple[int, str | int], ...], int]:
    return natural_path_key(str(artifact["path"])), int(artifact["artifact_id"])


def natural_path_key(path: str | Path) -> tuple[tuple[int, str | int], ...]:
    return tuple((0, int(part)) if part.isdigit() else (1, part.lower()) for part in re.split(r"(\d+)", str(path)))


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
