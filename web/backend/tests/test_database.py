from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.database import ProjectBusyError, RuntimeStore


def make_job(store: RuntimeStore, job_id: str, *, project_dir: str = "demo_project", status: str = "running", exclusive: bool = False) -> None:
    create = store.create_job_exclusive if exclusive else store.create_job
    create(
        job_id=job_id,
        project_dir=project_dir,
        phase=2,
        sub_step=None,
        role="main",
        thread_id=None,
        turn_id=None,
        status=status,
        approval_state="not_required",
        sandbox="workspace_write",
    )


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


def test_list_events_after_returns_only_newer_events(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "gui.sqlite3")
    first = store.add_event(job_id="job-1", event_type="turn_started", summary="start")
    second = store.add_event(job_id="job-1", event_type="assistant_message", summary="progress")
    store.add_event(job_id="job-2", event_type="turn_started", summary="other job")

    events = store.list_events_after("job-1", first)

    assert [event["event_id"] for event in events] == [second]
    assert store.list_events_after("job-1", second) == []
    assert [event["event_id"] for event in store.list_events_after("job-1", 0)] == [first, second]


def test_mark_active_jobs_interrupted_only_touches_active_jobs(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "gui.sqlite3")
    for job_id, status in (
        ("job-running", "running"),
        ("job-queued", "queued"),
        ("job-done", "completed"),
        ("job-waiting", "waiting_for_approval"),
    ):
        store.create_job(
            job_id=job_id,
            project_dir="demo_project",
            phase=2,
            sub_step=None,
            role="main",
            thread_id=None,
            turn_id=None,
            status=status,
            approval_state="not_required",
            sandbox="workspace_write",
        )

    changed = store.mark_active_jobs_interrupted(reason="backend restart")

    assert changed == 2
    assert store.get_job("job-running")["status"] == "interrupted"
    assert store.get_job("job-queued")["status"] == "interrupted"
    assert store.get_job("job-running")["last_error"] == "backend restart"
    assert store.get_job("job-done")["status"] == "completed"
    assert store.get_job("job-waiting")["status"] == "waiting_for_approval"


@pytest.mark.parametrize(
    "active_status",
    ["queued", "running", "waiting_for_approval", "waiting_to_continue"],
)
def test_create_job_exclusive_raises_when_project_has_active_job(tmp_path: Path, active_status: str) -> None:
    store = RuntimeStore(tmp_path / "gui.sqlite3")
    make_job(store, "job-active", status=active_status)

    with pytest.raises(ProjectBusyError) as exc_info:
        make_job(store, "job-new", status="queued", exclusive=True)

    assert exc_info.value.active_job_id == "job-active"
    with pytest.raises(KeyError):
        store.get_job("job-new")


def test_create_job_exclusive_allows_jobs_when_no_active_job_blocks(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "gui.sqlite3")
    make_job(store, "job-done", status="completed")
    make_job(store, "job-rejected", status="rejected")
    make_job(store, "job-elsewhere", project_dir="other_project", status="running")

    make_job(store, "job-new", status="queued", exclusive=True)

    assert store.get_job("job-new")["status"] == "queued"


@pytest.mark.parametrize(
    "busy_status",
    ["queued", "running", "waiting_for_approval", "waiting_to_continue"],
)
def test_requeue_job_exclusive_raises_when_another_project_job_is_busy(
    tmp_path: Path, busy_status: str
) -> None:
    store = RuntimeStore(tmp_path / "gui.sqlite3")
    make_job(store, "job-waiting", status="waiting_to_continue")
    make_job(store, "job-busy", status=busy_status)

    with pytest.raises(ProjectBusyError) as exc_info:
        store.requeue_job_exclusive("job-waiting", "demo_project")

    assert exc_info.value.active_job_id == "job-busy"
    assert store.get_job("job-waiting")["status"] == "waiting_to_continue"


def test_requeue_job_exclusive_requeues_when_only_other_jobs_are_finished(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "gui.sqlite3")
    make_job(store, "job-waiting", status="waiting_to_continue")
    make_job(store, "job-done", status="completed")
    make_job(store, "job-elsewhere", project_dir="other_project", status="running")

    store.requeue_job_exclusive("job-waiting", "demo_project")

    assert store.get_job("job-waiting")["status"] == "queued"


@pytest.mark.parametrize(
    "terminal_status",
    ["completed", "failed", "interrupted", "cancelled", "rejected"],
)
def test_update_job_if_active_returns_false_for_terminal_rows(
    tmp_path: Path, terminal_status: str
) -> None:
    store = RuntimeStore(tmp_path / "gui.sqlite3")
    make_job(store, "job-final", status=terminal_status)

    updated = store.update_job_if_active("job-final", status="interrupted", last_error="late write")

    assert updated is False
    assert store.get_job("job-final")["status"] == terminal_status
    assert store.get_job("job-final")["last_error"] is None


@pytest.mark.parametrize(
    "active_status",
    ["queued", "running", "waiting_for_approval", "waiting_to_continue"],
)
def test_update_job_if_active_updates_non_terminal_rows(tmp_path: Path, active_status: str) -> None:
    store = RuntimeStore(tmp_path / "gui.sqlite3")
    make_job(store, "job-live", status=active_status)

    updated = store.update_job_if_active("job-live", status="completed", turn_id="turn-9")

    assert updated is True
    job = store.get_job("job-live")
    assert job["status"] == "completed"
    assert job["turn_id"] == "turn-9"


def test_list_project_jobs_orders_newest_first_and_filters_active(tmp_path: Path) -> None:
    store = RuntimeStore(tmp_path / "gui.sqlite3")
    rows = (
        ("job-old-done", "completed", "2026-06-11T10:00:00Z"),
        ("job-waiting", "waiting_for_approval", "2026-06-11T11:00:00Z"),
        ("job-continue", "waiting_to_continue", "2026-06-11T12:00:00Z"),
        ("job-running", "running", "2026-06-11T13:00:00Z"),
        ("job-queued", "queued", "2026-06-11T14:00:00Z"),
    )
    for job_id, status, started_at in rows:
        make_job(store, job_id, status=status)
        store.update_job(job_id, started_at=started_at)
    make_job(store, "job-other-project", project_dir="other_project", status="running")

    all_jobs = store.list_project_jobs("demo_project")
    active_jobs = store.list_project_jobs("demo_project", active_only=True)

    assert [job["job_id"] for job in all_jobs] == [
        "job-queued",
        "job-running",
        "job-continue",
        "job-waiting",
        "job-old-done",
    ]
    assert [job["job_id"] for job in active_jobs] == [
        "job-queued",
        "job-running",
        "job-continue",
        "job-waiting",
    ]


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
