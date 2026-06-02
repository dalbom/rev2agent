# Codex SDK Browser GUI Design

## Goal

Build a local browser GUI for Rev2Agent that lets non-CS researchers create or resume projects, run Phase 0-8 through a guided interface, inspect progress and artifacts, stop or resume jobs, and keep `.research_state.json` as the research-state authority.

## Context

The current repository is a prompt-and-script project. `AGENTS.md` defines Codex routing, the startup protocol, phase labels, state schema, and the rule that only the main orchestrator writes `.research_state.json`. The phase prompts define detailed behavior. The GUI must not replace those contracts; it should expose them through a web app and use the Codex Python SDK through a narrow backend adapter.

Current upstream SDK docs verify:

- Package: `openai-codex`, Python `>=3.10`
- Runtime dependency: `openai-codex-cli-bin`
- Primary async client: `AsyncCodex`
- Thread lifecycle: `thread_start`, `thread_resume`
- Turn APIs: `thread.run` for simple completion, `thread.turn` plus `stream`, `interrupt`, and `run` for live control
- Sandbox presets: `Sandbox.read_only`, `Sandbox.workspace_write`, `Sandbox.full_access`

## Architecture

Add a contained `web/` app:

```text
web/
  backend/
    app/
      main.py
      codex_adapter.py
      database.py
      models.py
      projects.py
      phases.py
      artifacts.py
      safety.py
    tests/
    pyproject.toml
  frontend/
    package.json
    index.html
    src/
```

The FastAPI backend owns all filesystem access, SQLite runtime metadata, SDK calls, and safety checks. The React frontend only calls typed backend routes and listens to job event streams over SSE.

## Backend Components

`projects.py` implements the existing Startup Protocol:

- Check `.rev2agent_config.json`
- Scan first-level subdirectories for `.research_state.json`
- Summarize healthy and unhealthy projects
- Create a new draft project state for Phase 1 without creating Phase 0 research state
- Read project state for routing

`database.py` stores GUI runtime state in SQLite under `web/backend/.data/rev2agent_gui.sqlite3` by default. The database is not the research-state authority. It stores jobs, events, artifacts, approvals, SDK thread metadata, and resume data.

`safety.py` classifies phase/job actions before execution. It selects the narrowest SDK sandbox, identifies high-risk actions, and requires persisted GUI approval before high-risk work starts.

`codex_adapter.py` is the only module that imports `openai_codex`. It wraps `AsyncCodex`, starts or resumes phase-run threads, streams notifications into compact event records, returns turn metadata, and interrupts active turns.

`phases.py` creates one main thread per phase run and worker threads for literature/reviewer tasks. Generic launch support covers all Phase 0-8 prompts, with phase-specific metadata and sandbox defaults.

`artifacts.py` indexes safe files under known Rev2Agent project folders and exposes safe content reads for text, JSON, CSV, markdown, LaTeX, figures, and PDFs. It does not expose arbitrary file access.

## Frontend Design

The UI is a focused research operations tool, not a landing page.

Primary views:

1. Project Home: project list, setup state, current friendly step label, status, last update, active jobs, and create/resume actions.
2. Guided Phase Dashboard: current phase, plain-language explanation, primary action, stop/view/log actions, approval prompts, and output summary.
3. Live Run Console: high-level event timeline, job status, role labels, runtime, interrupt control, actionable errors, and developer details drawer.
4. Artifact Browser: tabs for summaries, literature, experiments, logs, results, manuscript, figures, tables, and PDFs.
5. Settings And Safety: Codex auth status, config status, environment checks, package manager guidance, sandbox policy, and high-risk approvals.

Visual style:

- Dense, readable dashboard layout
- Status chips and a progress timeline
- Tabs for artifacts
- Lucide icon buttons with tooltips
- 44px minimum touch targets and visible focus states
- Neutral app palette with restrained accent colors
- No marketing hero, decorative gradients, or raw terminal wall as the primary interface

## State And Safety Rules

- `.research_state.json` remains the project source of truth.
- SQLite stores only GUI runtime state.
- Worker jobs never write `.research_state.json`.
- Phase transitions verify required summary files before advancing.
- GUI approvals are the consent boundary.
- SDK sandbox is the execution boundary.
- `Sandbox.full_access` is disabled by default and requires a separate explicit approval.
- Raw secrets are never stored in SQLite events, approvals, or browser payloads.

## Error Handling

Backend responses distinguish:

- Setup/auth missing
- Invalid or unhealthy project state
- Approval required
- SDK unavailable or not authenticated
- High-risk action rejected
- Job interrupted
- Phase verification failed

Events are summarized for non-CS users, with raw event payloads stored only when safe.

## Testing Strategy

Use TDD slices for:

- Project discovery and state parsing
- New project draft creation
- Phase label/status mapping
- Job, event, approval, and artifact persistence
- Safety classification and approval gates
- Codex adapter import isolation and fake adapter behavior
- SSE event stream formatting
- Artifact indexing and safe reads
- Frontend API rendering and key user flows

## Open Questions And MVP Boundaries

- The SDK is beta. Keep assumptions contained in `codex_adapter.py` and provide clear errors when unavailable.
- Some phase-specific panels can be generic in the MVP, but every phase must be representable and launchable.
- The first GUI run can use fake adapter tests; real SDK operation is verified manually when credentials are available.
- The app should not start new real research work during development beyond small dry-run or mock test projects.
