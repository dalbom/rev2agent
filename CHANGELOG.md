# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

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
