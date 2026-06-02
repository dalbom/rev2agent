from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from .artifacts import ArtifactService, is_relative_to


class ProjectToolService:
    def __init__(
        self,
        *,
        repo_root: Path,
        artifact_service: ArtifactService,
        python_executable: str = sys.executable,
    ) -> None:
        self.repo_root = repo_root.resolve()
        self.artifact_service = artifact_service
        self.python_executable = python_executable

    def collect_results(self, project_dir: str) -> dict[str, Any]:
        project_path = self._project_root(project_dir)
        results_dir = project_path / "experiment" / "results"
        if not results_dir.is_dir():
            raise FileNotFoundError(results_dir)

        output_md = results_dir / "comparison.md"
        output_json = results_dir / "comparison.json"
        result = self._run_script(
            [
                self._script("collect_results.py"),
                results_dir,
                "--output-md",
                output_md,
                "--output-json",
                output_json,
            ]
        )
        return {
            **result,
            "output_md": self._repo_relative(output_md),
            "output_json": self._repo_relative(output_json),
            "artifacts": self.artifact_service.index_project(project_dir),
        }

    def validate_manuscript(self, project_dir: str) -> dict[str, Any]:
        project_path = self._project_root(project_dir)
        manuscript_dir = project_path / "manuscript"
        if not manuscript_dir.is_dir():
            raise FileNotFoundError(manuscript_dir)

        report_path = manuscript_dir / "validation_report.txt"
        result = self._run_script(
            [
                self._script("validate_manuscript.py"),
                "--manuscript-dir",
                manuscript_dir,
                "--bib",
                "references.bib",
                "--output",
                report_path,
            ]
        )
        return {
            **result,
            "report": self._repo_relative(report_path),
            "artifacts": self.artifact_service.index_project(project_dir),
        }

    def _run_script(self, args: list[str | Path]) -> dict[str, Any]:
        completed = subprocess.run(
            [str(arg) for arg in [self.python_executable, *args]],
            cwd=self.repo_root,
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
        return {
            "status": "passed" if completed.returncode == 0 else "failed",
            "return_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }

    def _project_root(self, project_dir: str) -> Path:
        project_path = (self.repo_root / project_dir).resolve()
        if not is_relative_to(project_path, self.repo_root):
            raise ValueError("Project path is outside repository")
        return project_path

    def _script(self, name: str) -> Path:
        script_path = self.repo_root / "scripts" / name
        if not script_path.exists():
            raise FileNotFoundError(script_path)
        return script_path

    def _repo_relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.repo_root).as_posix()
