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
from .project_tools import ProjectToolService
from .projects import create_project_draft, discover_projects
from .projects import load_project_state
from .settings import build_settings_status


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


def project_tool_service() -> ProjectToolService:
    return ProjectToolService(repo_root=repository_root(), artifact_service=artifact_service())


class StartPhaseJobRequest(BaseModel):
    action: str
    prompt: str
    approved: bool = False


class ContinueJobRequest(BaseModel):
    action: str
    prompt: str


class ApprovalRequest(BaseModel):
    user_action: str


@app.get("/api/projects")
def list_projects():
    return discover_projects(repository_root())


@app.post("/api/projects")
def create_project():
    return create_project_draft(repository_root())


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


@app.post("/api/jobs/{job_id}/approval")
def submit_approval(job_id: str, request: ApprovalRequest):
    return phase_service().submit_approval(job_id, user_action=request.user_action)


@app.post("/api/jobs/{job_id}/continue")
async def continue_job(job_id: str, request: ContinueJobRequest):
    return await phase_service().continue_job(
        job_id,
        action=request.action,
        prompt=request.prompt,
    )


@app.get("/api/projects/{project_dir}/artifacts")
def list_artifacts(project_dir: str):
    return artifact_service().index_project(project_dir)


@app.get("/api/projects/{project_dir}/artifacts/{artifact_id}")
def read_artifact(project_dir: str, artifact_id: int):
    return artifact_service().read_artifact(project_dir, artifact_id)


@app.post("/api/projects/{project_dir}/collect-results")
def collect_results(project_dir: str):
    return project_tool_service().collect_results(project_dir)


@app.post("/api/projects/{project_dir}/validate-manuscript")
def validate_manuscript(project_dir: str):
    return project_tool_service().validate_manuscript(project_dir)


@app.get("/api/settings")
def settings_status():
    return build_settings_status(repository_root(), sdk_status=get_sdk_status())
