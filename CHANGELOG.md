# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

## [2026-06-09]

### Added
- `prompts/conventions.md` — single host-neutral home for the shared state schema, status enums, `phase_history` entry format, state write rules (atomic writes, session lock, corrupt-state recovery), round numbering rules, summary-file checklist, and error recovery; both entrypoints and all phase prompts reference it
- Test suite under `tests/` and GitHub Actions CI workflow (`.github/workflows/ci.yml`), with `pyproject.toml` for tooling configuration

### Changed
- Host-neutral migration completed: shared prompts no longer reference entrypoint files by name
- Round numbering is now strictly monotonic — round numbers never reset, including when Phase 6 routes back to Phase 3 for a new research plan (the plan boundary is logged as a `new_research_plan` event in `phase_history`)
- Phase 7 now produces a single self-contained `main.tex` (no `sections/` includes), adds a dedicated abstract-writing task, and generates LaTeX tables from collected results
- `.gitignore` now excludes user research-project directories by default (allowlist of framework dirs: `prompts/`, `scripts/`, `tests/`, `.github/`) and the `tectonic` binary at the repo root

### Fixed
- Phase 6 state-machine gaps: explicit Phase 5 direct-skip branch (identical-config rounds) and Phase 8 re-entry mode after review-driven revisions
- Script bug fixes across the shared tooling: `\cite` regex in citation extraction, BibTeX brace parsing, `collect_results.py` no longer self-ingests its own `comparison_table.json`, timezone-handling crash, `\graphicspath`/`\cref` parsing in manuscript validation, and network retries for verification API calls

## [2026-04-21]

### Added
- Codex support via new root `AGENTS.md` entrypoint, alongside the existing `CLAUDE.md` entrypoint for Claude Code
- Shared host-neutral wrapper skill names:
  - `research-deep-dive`
  - `code-quality-review`
  - `writing-humanizer`
- Explicit host-mapping guidance in both `AGENTS.md` and `CLAUDE.md` so the shared prompt set can target multiple agent hosts without duplicating phase behavior

### Changed
- Shared prompts now use host-neutral terminology for:
  - wrapper skills
  - host-native reviewers
  - fresh-session recommendations
- `prompts/00_setup.md` no longer assumes Anthropic is always redundant; same-provider API keys are now treated as host-dependent
- `prompts/compaction.md` now describes fresh-session guidance generically instead of using Claude-specific `/compact` wording
- `prompts/05_experiment_execution.md` resume instructions now refer to starting a new session in the repository instead of running `claude`
- README, Korean README, and INSTALL docs now describe both Claude Code and Codex, with separate entrypoints and host-neutral review-panel wording

## [2026-04-20]

### Added
- `INSTALL.md` — bilingual setup guide (English default, Korean in a collapsible section); README and Korean README now link to it instead of duplicating setup steps (#4)

### Changed
- Quick Start replaced terminal-centric instructions with a single agent prompt that works on any OS (#4)
- Session handling at phase boundaries: replaced the `/compact` recommendation with starting a new session — all phase outputs are persisted to disk, so a fresh session reconstructs context from state files without summary token cost (`CLAUDE.md`, `prompts/compaction.md`) (#5)

## [2026-04-19]

### Added
- Phase 2 self-critique & gap-fill loop: after initial literature synthesis, the lead agent identifies coverage gaps (claims with <3 sources, missing subfields) and spawns targeted agents to fill them (up to 2 iterations)
- Reviewer Independence Protocol in Phase 8: when the review panel re-runs after revisions, each reviewer starts with fresh context (no prior reviews, synthesis, or response docs) to prevent anchoring bias

### Fixed
- Phase routing inconsistency: added explicit 5th path for Phase 6 → Phase 5 direct skip when next round needs identical config (just more seeds), resolving mismatch between `CLAUDE.md` diagram and `06_result_analysis.md` routing logic

## [2026-04-17]

### Added
- `## Abandoned` section for `research_roadmap.md` with structured fields (Direction, Abandoned at, Reason, Evidence, Revisit trigger) and a fixed 5-value reason enum (`falsified` / `out_of_scope` / `low_value` / `solved_elsewhere` / `infeasible`)
- Phase 6 round planning now explicitly checks for abandonment candidates each round; mid-round Active → Abandoned transition supported (skips Completed)
- Phase 7 Task E (Discussion & Conclusion) reads the Abandoned section and routes entries to Limitations / Related Work / Future Work by reason; `falsified` entries are excluded from Future Work (the experiment settled them)

### Changed
- Legacy `## Dropped` section (unstructured) is migrated to `## Abandoned` on the next Phase 6 roadmap update — no action required from existing projects

## [2026-04-16]

### Added
- Crossref API as primary citation verification source (Semantic Scholar as fallback)
- `collect_results.py` — automated experiment result table generation from JSON result files
- Per-script descriptions in README project structure section

### Changed
- `verify_citations_bibtex.py` — diacritics normalization for author matching, author-overlap validation to reject wrong Crossref matches, DOI-clean skip optimization
- Renamed internal `S2_VERIFIED` constant to `EXT_VERIFIED` for clarity

### Fixed
- False-positive author mismatches on Unicode diacritics (e.g., Packhauser vs Packhäuser)
- Wrong Crossref matches with high title similarity but zero author overlap now rejected
