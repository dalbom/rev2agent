from __future__ import annotations

from pathlib import Path

import pytest

from app.artifacts import ArtifactService
from app.database import RuntimeStore


def make_project(root: Path) -> Path:
    project = root / "demo_project"
    for folder in [
        "summaries",
        "literature",
        "experiment/configs",
        "experiment/logs",
        "experiment/results",
        "manuscript/figures",
        "manuscript/tables",
    ]:
        (project / folder).mkdir(parents=True, exist_ok=True)
    (project / ".research_state.json").write_text("{}", encoding="utf-8")
    (project / "summaries" / "phase1_topic.md").write_text("# Topic\n", encoding="utf-8")
    (project / "literature" / "survey-agent.md").write_text("Survey\n", encoding="utf-8")
    (project / "experiment" / "configs" / "plan.json").write_text("{}", encoding="utf-8")
    (project / "experiment" / "logs" / "run.log").write_text("log\n", encoding="utf-8")
    (project / "experiment" / "results" / "metrics.csv").write_text("metric,value\nacc,0.9\n", encoding="utf-8")
    (project / "manuscript" / "main.tex").write_text("\\input{sections/intro}\n", encoding="utf-8")
    (project / "manuscript" / "figures" / "fig.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (project / "manuscript" / "main.pdf").write_bytes(b"%PDF-1.7\n")
    return project


def test_index_project_artifacts_by_known_types(tmp_path: Path) -> None:
    make_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = ArtifactService(repo_root=tmp_path, store=store)

    artifacts = service.index_project("demo_project")
    types = {artifact["artifact_type"] for artifact in artifacts}

    assert {
        "summary",
        "literature",
        "experiment_config",
        "log",
        "result",
        "manuscript",
        "figure",
        "pdf",
    } <= types


def test_read_safe_text_artifact_content(tmp_path: Path) -> None:
    make_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = ArtifactService(repo_root=tmp_path, store=store)
    artifacts = service.index_project("demo_project")
    summary = next(item for item in artifacts if item["artifact_type"] == "summary")

    content = service.read_artifact("demo_project", summary["artifact_id"])

    assert content["kind"] == "text"
    assert content["content"] == "# Topic\n"
    assert content["mime_type"] == "text/markdown"


def test_read_binary_artifact_returns_metadata_only(tmp_path: Path) -> None:
    make_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = ArtifactService(repo_root=tmp_path, store=store)
    artifacts = service.index_project("demo_project")
    figure = next(item for item in artifacts if item["artifact_type"] == "figure")

    content = service.read_artifact("demo_project", figure["artifact_id"])

    assert content["kind"] == "binary"
    assert content["content"] is None
    assert content["mime_type"] == "image/png"
    assert content["size_bytes"] > 0


def test_read_artifact_rejects_project_mismatch(tmp_path: Path) -> None:
    make_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = ArtifactService(repo_root=tmp_path, store=store)
    artifact_id = service.index_project("demo_project")[0]["artifact_id"]

    with pytest.raises(ValueError, match="does not belong"):
        service.read_artifact("other_project", artifact_id)


def test_resolve_project_path_rejects_traversal(tmp_path: Path) -> None:
    make_project(tmp_path)
    store = RuntimeStore(tmp_path / "runtime.sqlite3")
    service = ArtifactService(repo_root=tmp_path, store=store)

    with pytest.raises(ValueError, match="outside project"):
        service.resolve_project_path("demo_project", "../secret.txt")
