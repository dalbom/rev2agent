# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

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
