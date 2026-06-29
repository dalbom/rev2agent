from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.artifacts import ArtifactService
from app.database import RuntimeStore
from app.project_tools import ProjectToolService


def make_script(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(source), encoding="utf-8")


def make_project(root: Path) -> Path:
    project = root / "demo_project"
    (project / "experiment" / "results").mkdir(parents=True)
    (project / "manuscript").mkdir(parents=True)
    (project / ".research_state.json").write_text("{}", encoding="utf-8")
    (project / "experiment" / "results" / "round1.json").write_text('{"accuracy": 0.91}', encoding="utf-8")
    (project / "manuscript" / "main.tex").write_text("\\section{Introduction}\n", encoding="utf-8")
    (project / "manuscript" / "references.bib").write_text("", encoding="utf-8")
    return project


def make_service(root: Path) -> ProjectToolService:
    store = RuntimeStore(root / "runtime.sqlite3")
    artifact_service = ArtifactService(repo_root=root, store=store)
    return ProjectToolService(repo_root=root, artifact_service=artifact_service)


def test_collect_results_runs_existing_script_and_indexes_outputs(tmp_path: Path) -> None:
    make_project(tmp_path)
    make_script(
        tmp_path / "scripts" / "collect_results.py",
        """
        import argparse
        from pathlib import Path

        parser = argparse.ArgumentParser()
        parser.add_argument("results_dir")
        parser.add_argument("--output-md")
        parser.add_argument("--output-json")
        args = parser.parse_args()

        Path(args.output_md).write_text("# Results\\n", encoding="utf-8")
        Path(args.output_json).write_text('{"files_scanned": 1}\\n', encoding="utf-8")
        print(f"collected {args.results_dir}")
        """,
    )
    service = make_service(tmp_path)

    result = service.collect_results("demo_project")

    assert result["status"] == "passed"
    assert result["return_code"] == 0
    assert result["output_md"] == "demo_project/experiment/results/comparison_table.md"
    assert result["output_json"] == "demo_project/experiment/results/comparison_table.json"
    assert "collected" in result["stdout"]
    assert {artifact["title"] for artifact in result["artifacts"]} >= {"comparison_table.md", "comparison_table.json"}


def test_validate_manuscript_runs_project_scoped_report(tmp_path: Path) -> None:
    make_project(tmp_path)
    make_script(
        tmp_path / "scripts" / "validate_manuscript.py",
        """
        import argparse
        from pathlib import Path

        parser = argparse.ArgumentParser()
        parser.add_argument("--manuscript-dir")
        parser.add_argument("--bib")
        parser.add_argument("--output")
        args = parser.parse_args()

        Path(args.output).write_text("Validation passed\\n", encoding="utf-8")
        print(f"validated {args.manuscript_dir} with {args.bib}")
        """,
    )
    service = make_service(tmp_path)

    result = service.validate_manuscript("demo_project")

    assert result["status"] == "passed"
    assert result["return_code"] == 0
    assert result["report"] == "demo_project/manuscript/validation_report.txt"
    assert "validated" in result["stdout"]
    assert any(artifact["title"] == "validation_report.txt" for artifact in result["artifacts"])


def test_project_tools_reject_project_traversal(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    with pytest.raises(ValueError, match="outside repository"):
        service.collect_results("../outside")
