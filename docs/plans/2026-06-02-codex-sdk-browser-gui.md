# Codex SDK Browser GUI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local FastAPI and React browser GUI for Rev2Agent that runs Phase 0-8 through the Codex Python SDK while preserving `.research_state.json` as the research-state authority.

**Architecture:** Add an isolated `web/` app. The backend owns SQLite, project filesystem access, safety gating, and the Codex SDK adapter. The frontend consumes typed REST APIs and SSE streams.

**Tech Stack:** Python 3.11, FastAPI, SQLite, `openai-codex`, pytest, React, TypeScript, Vite, pnpm, Vitest, Testing Library.

---

### Task 1: Backend Project Discovery

**Files:**
- Create: `web/backend/app/models.py`
- Create: `web/backend/app/projects.py`
- Create: `web/backend/app/main.py`
- Create: `web/backend/tests/test_projects.py`
- Create: `web/backend/pyproject.toml`

**Step 1: Write failing tests**

Cover:

- `discover_projects` scans first-level directories for `.research_state.json`.
- Friendly phase labels map Phase 0-8.
- Missing or invalid state files are surfaced as unhealthy, not ignored.
- Missing `.rev2agent_config.json` returns setup-required status.

Run:

```bash
cd web/backend
python -m pytest tests/test_projects.py -v
```

Expected: FAIL because modules do not exist.

**Step 2: Implement minimal project models and discovery**

Use Pydantic response models and pathlib-based scanning. Read JSON with structured error capture. Do not write project files in this task.

**Step 3: Verify**

Run:

```bash
cd web/backend
python -m pytest tests/test_projects.py -v
```

Expected: PASS.

### Task 2: SQLite Runtime Store

**Files:**
- Create: `web/backend/app/database.py`
- Create: `web/backend/tests/test_database.py`

**Step 1: Write failing tests**

Cover:

- Database initializes tables for jobs, events, artifacts, approvals.
- Job records persist `job_id`, `project_dir`, `phase`, `thread_id`, `turn_id`, status, sandbox, approval state, timestamps, errors, and token usage.
- Event records persist compact summary and safe raw payload.

Run:

```bash
cd web/backend
python -m pytest tests/test_database.py -v
```

Expected: FAIL because `database.py` does not exist.

**Step 2: Implement minimal sqlite wrapper**

Use stdlib `sqlite3`, explicit migrations, and dictionary row access. Store timestamps as ISO 8601 UTC strings.

**Step 3: Verify**

Run backend tests.

### Task 3: Safety And Approval Gates

**Files:**
- Create: `web/backend/app/safety.py`
- Create: `web/backend/tests/test_safety.py`

**Step 1: Write failing tests**

Cover:

- Read-only state and review tasks default to `read_only`.
- Project-writing tasks default to `workspace_write`.
- Running experiments, package installs, dataset downloads, deletes, full access, network-heavy actions, and outside-repo actions require approval.
- Approval records include job, project, action, risk, sandbox, user action, timestamp, and final status.
- Secret-looking values are redacted from event/approval payloads.

Run:

```bash
cd web/backend
python -m pytest tests/test_safety.py -v
```

Expected: FAIL.

**Step 2: Implement classifier**

Return a `SafetyDecision` with risk level, sandbox, approval requirement, plain-language impact text, and audit details.

**Step 3: Verify**

Run backend tests.

### Task 4: Codex Adapter Boundary

**Files:**
- Create: `web/backend/app/codex_adapter.py`
- Create: `web/backend/tests/test_codex_adapter.py`

**Step 1: Write failing tests**

Cover:

- Importing backend without SDK installed does not crash.
- Adapter reports SDK availability and auth status.
- Fake adapter can start, resume, stream events, return turn metadata, and interrupt.
- Direct SDK imports are isolated to `codex_adapter.py`.

Run:

```bash
cd web/backend
python -m pytest tests/test_codex_adapter.py -v
```

Expected: FAIL.

**Step 2: Implement adapter interface and SDK adapter**

Use lazy imports:

```python
from openai_codex import AsyncCodex, Sandbox
```

Map local sandbox strings to SDK `Sandbox` presets. Use `thread.turn(...).stream()` for live progress and `turn.run()` for result collection.

**Step 3: Verify**

Run backend tests. If SDK is unavailable, tests use the fake adapter.

### Task 5: Phase Job Lifecycle And SSE

**Files:**
- Create: `web/backend/app/phases.py`
- Modify: `web/backend/app/main.py`
- Create: `web/backend/tests/test_phases.py`

**Step 1: Write failing tests**

Cover:

- Starting a phase job creates a SQLite job.
- High-risk jobs return approval-required and do not start a Codex turn.
- Approved jobs create or resume the correct thread.
- Events are persisted and streamed as SSE.
- Interrupt updates job status and calls adapter interrupt.

Run:

```bash
cd web/backend
python -m pytest tests/test_phases.py -v
```

Expected: FAIL.

**Step 2: Implement routes**

Implement:

- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{project}/state`
- `GET /api/projects/{project}/phase`
- `POST /api/projects/{project}/phase/{phase}/jobs`
- `POST /api/jobs/{job_id}/continue`
- `GET /api/jobs/{job_id}/events`
- `POST /api/jobs/{job_id}/interrupt`
- `POST /api/jobs/{job_id}/approval`

**Step 3: Verify**

Run backend tests.

### Task 6: Artifact Indexing And Safe Reads

**Files:**
- Create: `web/backend/app/artifacts.py`
- Create: `web/backend/tests/test_artifacts.py`

**Step 1: Write failing tests**

Cover:

- Known project folders are indexed by artifact type.
- Unsafe paths outside the project are rejected.
- Text, markdown, JSON, CSV, LaTeX, image, and PDF metadata are exposed safely.
- Large file reads are size-limited.

Run:

```bash
cd web/backend
python -m pytest tests/test_artifacts.py -v
```

Expected: FAIL.

**Step 2: Implement artifact routes**

Implement:

- `GET /api/projects/{project}/artifacts`
- `GET /api/projects/{project}/artifacts/{artifact_id}`
- `POST /api/projects/{project}/collect-results`
- `POST /api/projects/{project}/validate-manuscript`

**Step 3: Verify**

Run backend tests.

### Task 7: Frontend Skeleton And API Client

**Files:**
- Create: `web/frontend/package.json`
- Create: `web/frontend/index.html`
- Create: `web/frontend/src/api.ts`
- Create: `web/frontend/src/App.tsx`
- Create: `web/frontend/src/main.tsx`
- Create: `web/frontend/src/styles.css`
- Create: `web/frontend/src/App.test.tsx`

**Step 1: Write failing tests**

Cover:

- Project Home renders discovered projects.
- Friendly phase labels are shown first, internal phase numbers second.
- Setup-required state routes user to Settings.

Run:

```bash
cd web/frontend
pnpm test
```

Expected: FAIL.

**Step 2: Implement minimal UI**

Use a dense app shell with sidebar navigation, status chips, project cards, and accessible buttons. Use lucide-react icons.

**Step 3: Verify**

Run frontend tests.

### Task 8: Phase Dashboard, Live Console, Artifacts, Settings

**Files:**
- Modify: `web/frontend/src/App.tsx`
- Create: `web/frontend/src/components/PhaseDashboard.tsx`
- Create: `web/frontend/src/components/LiveRunConsole.tsx`
- Create: `web/frontend/src/components/ArtifactBrowser.tsx`
- Create: `web/frontend/src/components/SettingsSafety.tsx`
- Create: component tests under `web/frontend/src/components/`

**Step 1: Write failing tests**

Cover:

- Phase dashboard shows primary and secondary actions.
- Approval dialog blocks high-risk actions until approval.
- Live console consumes SSE events.
- Artifact tabs list and preview safe content.
- Settings shows auth/config/LaTeX/Python/package-manager status.

Run:

```bash
cd web/frontend
pnpm test
```

Expected: FAIL.

**Step 2: Implement UI components**

Keep layouts stable and responsive at 375px, 768px, 1024px, and 1440px. Use focus-visible styling and no emoji icons.

**Step 3: Verify**

Run frontend tests and inspect in browser.

### Task 9: Documentation And Local Run Verification

**Files:**
- Create: `web/README.md`
- Modify: `README.md` or `INSTALL.md` with a short GUI pointer if appropriate.

**Step 1: Document run commands**

Include:

```bash
cd web/backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
uvicorn app.main:app --reload --port 8000

cd web/frontend
pnpm install
pnpm dev --host 127.0.0.1 --port 5173
```

**Step 2: Full verification**

Run:

```bash
cd web/backend
python -m pytest -v

cd web/frontend
pnpm test
pnpm build
```

Start backend and frontend dev servers and verify the app opens locally.

**Step 3: Implementation note**

Write a final note covering what was added, run commands, SDK integration, SQLite location, state preservation, verification, and limitations.
