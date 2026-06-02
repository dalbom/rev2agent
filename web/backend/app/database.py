from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class RuntimeStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def table_names(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "select name from sqlite_master where type = 'table'"
            ).fetchall()
        return {row["name"] for row in rows}

    def create_job(
        self,
        *,
        job_id: str,
        project_dir: str,
        phase: int,
        sub_step: str | None,
        role: str,
        thread_id: str | None,
        turn_id: str | None,
        status: str,
        approval_state: str,
        sandbox: str,
        token_usage: dict[str, Any] | None = None,
        last_error: str | None = None,
    ) -> None:
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                insert into jobs (
                    job_id, project_dir, phase, sub_step, role, thread_id, turn_id,
                    status, approval_state, sandbox, started_at, completed_at,
                    last_error, token_usage_json
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    project_dir,
                    phase,
                    sub_step,
                    role,
                    thread_id,
                    turn_id,
                    status,
                    approval_state,
                    sandbox,
                    now,
                    None,
                    last_error,
                    json_dumps(token_usage),
                ),
            )

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("select * from jobs where job_id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(job_id)
        return dict(row)

    def update_job(self, job_id: str, **fields: Any) -> None:
        if not fields:
            return
        columns = []
        values = []
        for key, value in fields.items():
            column = "token_usage_json" if key == "token_usage" else key
            columns.append(f"{column} = ?")
            values.append(json_dumps(value) if key == "token_usage" else value)
        values.append(job_id)
        with self._connect() as conn:
            conn.execute(f"update jobs set {', '.join(columns)} where job_id = ?", values)

    def add_event(
        self,
        *,
        job_id: str,
        event_type: str,
        summary: str,
        raw_payload: dict[str, Any] | None = None,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                insert into events (job_id, timestamp, event_type, summary, raw_payload_json)
                values (?, ?, ?, ?, ?)
                """,
                (job_id, utc_now(), event_type, summary, json_dumps(raw_payload)),
            )
            return int(cursor.lastrowid)

    def list_events(self, job_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from events where job_id = ? order by event_id",
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def add_approval(
        self,
        *,
        job_id: str,
        project_dir: str,
        requested_action: str,
        risk_level: str,
        requested_sandbox: str,
        user_action: str,
        final_status: str,
        impact: str,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                insert into approvals (
                    job_id, project_dir, requested_action, risk_level,
                    requested_sandbox, user_action, created_at, final_status, impact
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    project_dir,
                    requested_action,
                    risk_level,
                    requested_sandbox,
                    user_action,
                    utc_now(),
                    final_status,
                    impact,
                ),
            )
            return int(cursor.lastrowid)

    def list_approvals(self, job_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from approvals where job_id = ? order by approval_id",
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def update_latest_approval(
        self,
        job_id: str,
        *,
        user_action: str,
        final_status: str,
    ) -> dict[str, Any]:
        approvals = self.list_approvals(job_id)
        if not approvals:
            raise KeyError(job_id)
        approval_id = approvals[-1]["approval_id"]
        with self._connect() as conn:
            conn.execute(
                """
                update approvals
                set user_action = ?, final_status = ?
                where approval_id = ?
                """,
                (user_action, final_status, approval_id),
            )
        return self.list_approvals(job_id)[-1]

    def add_artifact(
        self,
        *,
        project_dir: str,
        job_id: str | None,
        path: str,
        artifact_type: str,
        title: str,
        validation_status: str,
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                insert into artifacts (
                    project_dir, job_id, path, artifact_type, title,
                    created_at, validation_status
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    project_dir,
                    job_id,
                    path,
                    artifact_type,
                    title,
                    utc_now(),
                    validation_status,
                ),
            )
            return int(cursor.lastrowid)

    def list_artifacts(self, project_dir: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "select * from artifacts where project_dir = ? order by artifact_id",
                (project_dir,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_artifact(self, artifact_id: int) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "select * from artifacts where artifact_id = ?",
                (artifact_id,),
            ).fetchone()
        if row is None:
            raise KeyError(artifact_id)
        return dict(row)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists jobs (
                    job_id text primary key,
                    project_dir text not null,
                    phase integer not null,
                    sub_step text,
                    role text not null,
                    thread_id text,
                    turn_id text,
                    status text not null,
                    approval_state text not null,
                    sandbox text not null,
                    started_at text not null,
                    completed_at text,
                    last_error text,
                    token_usage_json text
                );

                create table if not exists events (
                    event_id integer primary key autoincrement,
                    job_id text not null,
                    timestamp text not null,
                    event_type text not null,
                    summary text not null,
                    raw_payload_json text,
                    foreign key (job_id) references jobs(job_id)
                );

                create table if not exists artifacts (
                    artifact_id integer primary key autoincrement,
                    project_dir text not null,
                    job_id text,
                    path text not null,
                    artifact_type text not null,
                    title text not null,
                    created_at text not null,
                    validation_status text not null
                );

                create table if not exists approvals (
                    approval_id integer primary key autoincrement,
                    job_id text not null,
                    project_dir text not null,
                    requested_action text not null,
                    risk_level text not null,
                    requested_sandbox text not null,
                    user_action text not null,
                    created_at text not null,
                    final_status text not null,
                    impact text not null
                );
                """
            )


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def json_dumps(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, separators=(",", ":"), sort_keys=True)
