from __future__ import annotations

import json
from pathlib import Path

from app.database import RuntimeStore


def test_runtime_store_initializes_tables(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "gui.sqlite3")
    tables = store.table_names()

    assert {"jobs", "events", "artifacts", "approvals"} <= tables


def test_job_records_persist_sdk_metadata(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "gui.sqlite3")

    store.create_job(
        job_id="job-1",
        project_dir="demo_project",
        phase=5,
        sub_step=None,
        role="main",
        thread_id="thread-1",
        turn_id="turn-1",
        status="running",
        approval_state="approved",
        sandbox="workspace_write",
        token_usage={"input_tokens": 12, "output_tokens": 4},
    )

    job = store.get_job("job-1")
    assert job["project_dir"] == "demo_project"
    assert job["phase"] == 5
    assert job["thread_id"] == "thread-1"
    assert job["turn_id"] == "turn-1"
    assert job["status"] == "running"
    assert job["sandbox"] == "workspace_write"
    assert json.loads(job["token_usage_json"]) == {"input_tokens": 12, "output_tokens": 4}
    assert job["started_at"]


def test_events_persist_summary_and_safe_raw_payload(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "gui.sqlite3")
    store.create_job(
        job_id="job-1",
        project_dir="demo_project",
        phase=2,
        sub_step=None,
        role="survey-agent",
        thread_id=None,
        turn_id=None,
        status="running",
        approval_state="not_required",
        sandbox="read_only",
    )

    event_id = store.add_event(
        job_id="job-1",
        event_type="assistant_message",
        summary="Survey worker found papers",
        raw_payload={"type": "assistant_message", "safe": True},
    )

    events = store.list_events("job-1")
    assert events[0]["event_id"] == event_id
    assert events[0]["summary"] == "Survey worker found papers"
    assert json.loads(events[0]["raw_payload_json"]) == {"type": "assistant_message", "safe": True}


def test_approval_records_are_auditable(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "gui.sqlite3")

    approval_id = store.add_approval(
        job_id="job-9",
        project_dir="demo_project",
        requested_action="Run experiment scripts",
        risk_level="high",
        requested_sandbox="workspace_write",
        user_action="approved",
        final_status="pending_execution",
        impact="Runs long experiment scripts and may modify project files.",
    )

    approvals = store.list_approvals("job-9")
    assert approvals[0]["approval_id"] == approval_id
    assert approvals[0]["risk_level"] == "high"
    assert approvals[0]["requested_sandbox"] == "workspace_write"
    assert approvals[0]["user_action"] == "approved"
    assert approvals[0]["created_at"]


def test_artifact_records_store_validation_state(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "gui.sqlite3")

    artifact_id = store.add_artifact(
        project_dir="demo_project",
        job_id="job-3",
        path="demo_project/summaries/phase1_topic.md",
        artifact_type="summary",
        title="Topic Summary",
        validation_status="valid",
    )

    artifacts = store.list_artifacts("demo_project")
    assert artifacts[0]["artifact_id"] == artifact_id
    assert artifacts[0]["artifact_type"] == "summary"
    assert artifacts[0]["validation_status"] == "valid"
