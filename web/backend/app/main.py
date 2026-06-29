from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .artifacts import ArtifactService
from .codex_adapter import CodexSdkAdapter, get_sdk_status
from .database import ProjectBusyError, RuntimeStore
from .phases import ACTIVE_STATUSES, PhaseJobService, format_sse_event
from .project_tools import ProjectToolService
from .projects import archive_project, create_project_draft, discover_projects
from .projects import load_project_state
from .settings import build_settings_status
from .setup import complete_host_only_setup as write_host_only_setup
from .setup import setup_is_complete

EVENT_STREAM_POLL_SECONDS = 0.5


def repository_root() -> Path:
    return Path(__file__).resolve().parents[3]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Jobs from a previous backend process can no longer be running; mark them
    # interrupted so the GUI does not show phantom "running" jobs forever.
    phase_service().recover_orphaned_jobs()
    yield


app = FastAPI(title="Rev2Agent GUI", lifespan=lifespan)
_runtime_stores: dict[Path, RuntimeStore] = {}
_phase_services: dict[tuple[Path, Path], PhaseJobService] = {}


def runtime_store() -> RuntimeStore:
    db_path = Path(__file__).resolve().parents[1] / ".data" / "rev2agent_gui.sqlite3"
    if db_path not in _runtime_stores:
        _runtime_stores[db_path] = RuntimeStore(db_path)
    return _runtime_stores[db_path]


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


class CreateProjectRequest(BaseModel):
    research_idea: str = ""
    project_name: str = ""


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
    state = _load_project_state_or_http_error(root, project_dir)
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
    job = _get_job_or_404(job_id)

    job_phase = _phase_number(job.get("phase"))
    if job_phase is None:
        raise HTTPException(status_code=409, detail="Job phase is unknown; refusing to continue.")

    project_dir = str(job.get("project_dir") or "")
    state = _load_project_state_or_http_error(root, project_dir)
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


def _load_project_state_or_http_error(root: Path, project_dir: str) -> dict[str, Any]:
    try:
        return load_project_state(root, root / project_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _get_job_or_404(job_id: str) -> dict[str, Any]:
    try:
        return runtime_store().get_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}") from exc


@app.get("/api/projects")
def list_projects():
    return discover_projects(repository_root())


@app.post("/api/projects")
def create_project(request: CreateProjectRequest | None = None):
    root = repository_root()
    ensure_phase_zero_setup(root)
    try:
        return create_project_draft(
            root,
            research_idea=request.research_idea if request else "",
            project_name=request.project_name if request else "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
    return _load_project_state_or_http_error(repository_root(), project_dir)


@app.get("/api/projects/{project_dir}/phase")
def get_phase_status(project_dir: str) -> dict[str, Any]:
    try:
        return phase_service().phase_status(project_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/projects/{project_dir}/phase/{phase}/jobs")
async def start_phase_job(project_dir: str, phase: int, request: StartPhaseJobRequest):
    root = repository_root()
    ensure_phase_zero_setup(root)
    ensure_project_phase_action(root, project_dir, phase, request.action)
    try:
        return phase_service().launch_phase_job(
            project_dir=project_dir,
            phase=phase,
            action=request.action,
            prompt=request.prompt,
        )
    except ProjectBusyError as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Another job ({exc.active_job_id}) is already active for this project; "
                "stop it or wait for it to finish."
            ),
        ) from exc


@app.get("/api/projects/{project_dir}/jobs")
def list_project_jobs(project_dir: str, active: bool = False):
    return runtime_store().list_project_jobs(project_dir, active_only=active)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    return _get_job_or_404(job_id)


@app.get("/api/jobs/{job_id}/events")
def get_job_events(job_id: str):
    _get_job_or_404(job_id)
    return runtime_store().list_events(job_id)


@app.get("/api/jobs/{job_id}/events/stream")
async def stream_job_events(job_id: str, request: Request):
    store = runtime_store()
    _get_job_or_404(job_id)
    last_event_id = _phase_number(request.headers.get("last-event-id")) or 0

    async def generate():
        cursor = last_event_id
        while True:
            for event in store.list_events_after(job_id, cursor):
                cursor = event["event_id"]
                yield format_sse_event(event)
            try:
                job = store.get_job(job_id)
            except KeyError:
                return
            if job["status"] not in ACTIVE_STATUSES:
                # Finalization can write tail events (completion_warning,
                # interrupt_note, error) between the drain above and this status
                # check; drain once more so they are not dropped at close.
                for event in store.list_events_after(job_id, cursor):
                    cursor = event["event_id"]
                    yield format_sse_event(event)
                yield format_sse_event(
                    {"event_type": "job_status", "job_id": job_id, "status": job["status"]}
                )
                return
            if await request.is_disconnected():
                return
            await asyncio.sleep(EVENT_STREAM_POLL_SECONDS)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@app.post("/api/jobs/{job_id}/interrupt")
async def interrupt_job(job_id: str):
    _get_job_or_404(job_id)
    interrupted = await phase_service().interrupt_job(job_id)
    return {"job_id": job_id, "interrupted": interrupted}


@app.post("/api/jobs/{job_id}/approval")
def submit_approval(job_id: str, request: ApprovalRequest):
    _get_job_or_404(job_id)
    try:
        return phase_service().submit_approval(job_id, user_action=request.user_action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/jobs/{job_id}/continue")
async def continue_job(job_id: str, request: ContinueJobRequest):
    root = repository_root()
    ensure_phase_zero_setup(root)
    ensure_continue_action_allowed(root, job_id, request.action)
    try:
        return phase_service().launch_continue_job(
            job_id,
            action=request.action,
            prompt=request.prompt,
        )
    except ProjectBusyError as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Another job ({exc.active_job_id}) is already active for this project; "
                "stop it or wait for it to finish."
            ),
        ) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown job: {job_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/projects/{project_dir}/artifacts")
def list_artifacts(project_dir: str):
    try:
        return artifact_service().index_project(project_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown project: {project_dir}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/projects/{project_dir}/artifacts/{artifact_id}")
def read_artifact(project_dir: str, artifact_id: int):
    try:
        return artifact_service().read_artifact(project_dir, artifact_id)
    except (FileNotFoundError, KeyError) as exc:
        raise HTTPException(status_code=404, detail=f"Unknown artifact: {artifact_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/projects/{project_dir}/collect-results")
def collect_results(project_dir: str):
    try:
        return project_tool_service().collect_results(project_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/projects/{project_dir}/validate-manuscript")
def validate_manuscript(project_dir: str):
    try:
        return project_tool_service().validate_manuscript(project_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/settings")
def settings_status():
    return build_settings_status(repository_root(), sdk_status=get_sdk_status())


@app.post("/api/setup/host-only")
def complete_host_only_setup():
    root = repository_root()
    write_host_only_setup(root)
    return build_settings_status(root, sdk_status=get_sdk_status())
