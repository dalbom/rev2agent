from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .artifacts import ArtifactService
from .codex_adapter import CodexSdkAdapter, get_sdk_status
from .database import RuntimeStore
from .phases import PhaseJobService, format_sse_event
from .project_tools import ProjectToolService
from .projects import archive_project, create_project_draft, discover_projects
from .projects import load_project_state
from .settings import build_settings_status
from .setup import complete_host_only_setup as write_host_only_setup
from .setup import setup_is_complete


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


app = FastAPI(title="Rev2Agent GUI")
_phase_services: dict[tuple[Path, Path], PhaseJobService] = {}


def runtime_store() -> RuntimeStore:
    return RuntimeStore(Path(__file__).resolve().parents[1] / ".data" / "rev2agent_gui.sqlite3")


def phase_service() -> PhaseJobService:
    root = repository_root()
    store = runtime_store()
    key = (root, store.db_path)
    if key not in _phase_services:
        _phase_services[key] = PhaseJobService(
            repo_root=root,
            store=store,
            adapter=CodexSdkAdapter(),
        )
    return _phase_services[key]


def artifact_service() -> ArtifactService:
    return ArtifactService(repo_root=repository_root(), store=runtime_store())


def project_tool_service() -> ProjectToolService:
    return ProjectToolService(repo_root=repository_root(), artifact_service=artifact_service())


class StartPhaseJobRequest(BaseModel):
    action: str
    prompt: str
    approved: bool = False


class CreateProjectRequest(BaseModel):
    research_idea: str = ""


class ContinueJobRequest(BaseModel):
    action: str
    prompt: str


class ApprovalRequest(BaseModel):
    user_action: str


def ensure_phase_zero_setup(root: Path) -> None:
    if not setup_is_complete(root):
        raise HTTPException(
            status_code=409,
            detail="Phase 0 setup must be completed before starting projects or phase jobs.",
        )


def ensure_project_phase_action(root: Path, project_dir: str, phase: int, action: str) -> None:
    state = load_project_state(root, root / project_dir)
    current_phase = _phase_number(state.get("current_phase"))
    if current_phase is None:
        raise HTTPException(
            status_code=409,
            detail="Current project phase is unknown; refresh project state before starting jobs.",
        )
    if current_phase != phase:
        raise HTTPException(
            status_code=409,
            detail=f"Current project phase is {current_phase}; refusing to run phase {phase}.",
        )
    ensure_experiment_action_is_phase_five(phase, action)


def ensure_continue_action_allowed(root: Path, job_id: str, action: str) -> None:
    try:
        job = runtime_store().get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}") from exc

    job_phase = _phase_number(job.get("phase"))
    if job_phase is None:
        raise HTTPException(status_code=409, detail="Job phase is unknown; refusing to continue.")

    project_dir = str(job.get("project_dir") or "")
    state = load_project_state(root, root / project_dir)
    current_phase = _phase_number(state.get("current_phase"))
    if current_phase != job_phase:
        raise HTTPException(
            status_code=409,
            detail=f"Current project phase is {current_phase}; refusing to continue a phase {job_phase} job.",
        )
    ensure_experiment_action_is_phase_five(job_phase, action)


def ensure_experiment_action_is_phase_five(phase: int, action: str) -> None:
    if _is_experiment_execution_action(action) and phase != 5:
        raise HTTPException(
            status_code=409,
            detail="Experiment scripts can only be run in Phase 5.",
        )


def _is_experiment_execution_action(action: str) -> bool:
    normalized = action.lower()
    return (
        "run experiment" in normalized
        or "experiment scripts" in normalized
        or "execute experiment" in normalized
    )


def _phase_number(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


@app.get("/api/projects")
def list_projects():
    return discover_projects(repository_root())


@app.post("/api/projects")
def create_project(request: CreateProjectRequest | None = None):
    root = repository_root()
    ensure_phase_zero_setup(root)
    return create_project_draft(root, research_idea=request.research_idea if request else "")


@app.post("/api/projects/{project_dir}/archive")
def archive_project_endpoint(project_dir: str):
    root = repository_root()
    ensure_phase_zero_setup(root)
    try:
        return archive_project(root, project_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/projects/{project_dir}/state")
def get_project_state(project_dir: str) -> dict[str, Any]:
    return load_project_state(repository_root(), repository_root() / project_dir)


@app.get("/api/projects/{project_dir}/phase")
def get_phase_status(project_dir: str) -> dict[str, Any]:
    return phase_service().phase_status(project_dir)


@app.post("/api/projects/{project_dir}/phase/{phase}/jobs")
async def start_phase_job(project_dir: str, phase: int, request: StartPhaseJobRequest):
    root = repository_root()
    ensure_phase_zero_setup(root)
    ensure_project_phase_action(root, project_dir, phase, request.action)
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
    root = repository_root()
    ensure_phase_zero_setup(root)
    ensure_continue_action_allowed(root, job_id, request.action)
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


@app.post("/api/setup/host-only")
def complete_host_only_setup():
    root = repository_root()
    write_host_only_setup(root)
    return build_settings_status(root, sdk_status=get_sdk_status())
