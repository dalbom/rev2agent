# Rev2Agent Browser GUI

This folder contains a local browser GUI for Rev2Agent. The existing prompt-driven workflow remains unchanged; the GUI adds a FastAPI backend, SQLite runtime state, and a React/Vite frontend that drives Rev2Agent phases through the Codex Python SDK adapter.

## Quick Start

Windows:

```text
From the repository root, double-click scripts\start-gui.bat
```

macOS:

```text
From the repository root, double-click scripts/start-gui.command
```

Both launchers create the backend Python environment, install frontend packages when needed, start the backend and frontend servers, and open `http://127.0.0.1:5173`.

If macOS blocks the `.command` file because it is not executable, run this once from the repository root:

```bash
chmod +x scripts/start-gui.command
```

## Manual Development Start

### Backend

```powershell
cd web\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The backend stores GUI runtime metadata at:

```text
web/backend/.data/rev2agent_gui.sqlite3
```

SQLite is used only for GUI jobs, SDK thread metadata, event records, approvals, and artifact indexes. Project research state remains authoritative in each project directory's `.research_state.json`.

### Frontend

```powershell
cd web\frontend
pnpm install
pnpm dev --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` requests and job event streams to the backend at `http://127.0.0.1:8000`.

## Codex SDK Integration

Direct SDK imports are isolated in `web/backend/app/codex_adapter.py`. The rest of the backend depends on local adapter methods for:

- starting and resuming phase threads
- running turns
- streaming turn events
- interrupting running work
- mapping GUI safety decisions to SDK sandboxes

The adapter uses `openai-codex` and the SDK-provided runtime. Existing Codex authentication is reused when available; secret values are not written to SQLite event or approval payloads.

## Safety Model

The GUI classifies requested actions before a Codex turn starts. Low-risk inspection uses `read_only`, normal project writing uses `workspace_write`, and high-risk operations pause for explicit browser approval before continuing. Approval decisions are persisted with job, project, action, risk, sandbox, user action, timestamp, and final status metadata.

## Project Tools

The backend exposes project-scoped tool actions for workflows that previously required terminal commands:

- `POST /api/projects/{project_dir}/collect-results` runs `scripts/collect_results.py` against `experiment/results/` and writes comparison Markdown/JSON artifacts.
- `POST /api/projects/{project_dir}/validate-manuscript` runs `scripts/validate_manuscript.py` against `manuscript/` and writes `validation_report.txt`.

Both actions use fixed script arguments, reject project path traversal, and refresh the artifact index after completion.

## Verification

```powershell
cd web\backend
.\.venv\Scripts\python.exe -m pytest tests -v

cd ..\frontend
pnpm test -- --run
pnpm build
```

## Current Limitations

- Phase-specific panels share a generic job dashboard in this first browser version.
- Settings reports environment and safety state; full in-browser Codex login and external model setup flows still need expansion.
- Real Codex phase execution requires valid local Codex authentication and the beta `openai-codex` package/runtime.
