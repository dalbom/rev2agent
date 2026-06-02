from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .artifacts import ArtifactService
from .codex_adapter import CodexSdkAdapter, get_sdk_status
from .database import RuntimeStore
from .phases import PhaseJobService, format_sse_event
from .projects import discover_projects
from .projects import load_project_state


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


app = FastAPI(title="Rev2Agent GUI")


def runtime_store() -> RuntimeStore:
    return RuntimeStore(Path(__file__).resolve().parents[1] / ".data" / "rev2agent_gui.sqlite3")


def phase_service() -> PhaseJobService:
    return PhaseJobService(
        repo_root=repository_root(),
        store=runtime_store(),
        adapter=CodexSdkAdapter(),
    )


def artifact_service() -> ArtifactService:
    return ArtifactService(repo_root=repository_root(), store=runtime_store())


class StartPhaseJobRequest(BaseModel):
    action: str
    prompt: str
    approved: bool = False


@app.get("/api/projects")
def list_projects():
    return discover_projects(repository_root())


@app.get("/api/projects/{project_dir}/state")
def get_project_state(project_dir: str) -> dict[str, Any]:
    return load_project_state(repository_root(), repository_root() / project_dir)


@app.get("/api/projects/{project_dir}/phase")
def get_phase_status(project_dir: str) -> dict[str, Any]:
    return phase_service().phase_status(project_dir)


@app.post("/api/projects/{project_dir}/phase/{phase}/jobs")
async def start_phase_job(project_dir: str, phase: int, request: StartPhaseJobRequest):
    return await phase_service().start_phase_job(
        project_dir=project_dir,
        phase=phase,
        action=request.action,
        prompt=request.prompt,
        approved=request.approved,
    )


@app.get("/api/jobs/{job_id}/events")
def get_job_events(job_id: str):
    return runtime_store().list_events(job_id)


@app.get("/api/jobs/{job_id}/events/stream")
def stream_job_events(job_id: str):
    def generate():
        for event in runtime_store().list_events(job_id):
            yield format_sse_event(event)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/jobs/{job_id}/interrupt")
async def interrupt_job(job_id: str):
    interrupted = await phase_service().interrupt_job(job_id)
    return {"job_id": job_id, "interrupted": interrupted}


@app.get("/api/projects/{project_dir}/artifacts")
def list_artifacts(project_dir: str):
    return artifact_service().index_project(project_dir)


@app.get("/api/projects/{project_dir}/artifacts/{artifact_id}")
def read_artifact(project_dir: str, artifact_id: int):
    return artifact_service().read_artifact(project_dir, artifact_id)


@app.get("/api/settings")
def settings_status():
    status = get_sdk_status()
    return {
        "codex_sdk": status,
        "repository": {
            "root": repository_root(),
            "config_exists": (repository_root() / ".rev2agent_config.json").exists(),
        },
    }
