# Changelog

All notable changes to this project will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

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
