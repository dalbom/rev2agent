# Rev2Agent — Autonomous Research Bot

Guide the author from a research idea through experiments to a manuscript draft.

Read `prompts/agent_workflow.md` before handling a request. It owns shared routing, authorization, delegation, and persona rules for both hosts. For research execution, follow the Startup Protocol and phase index in `prompts/conventions.md`, then read the owning phase prompt. Project structure and installation are documented in `README.md`.

## Host Adapter

Use the tools and collaboration primitives exposed by the current Codex host. Map legacy `Task`, `Agent`, and slash-command wording to available capabilities; do not assume Claude-specific commands or custom agents exist. Use isolated worker contexts when a role requires independence.

Model and effort selection belong to host settings or explicitly configured roles. Preserve provider consent and research requirements when selecting a model.
