# Core Gate Hardening Design

Rev2Agent's prompt-only architecture remains intact. This change strengthens the contracts that cross phase and script boundaries so that an agent cannot silently confuse rounds, combine unrelated experiments, approve incomplete citations, or expose API keys through chat.

The canonical state gains `current_round_short_name`, and `sub_step` gains a persisted `review_reentry` mode. Every experiment artifact is namespaced under `round{N}_{short_name}`. Completion markers, checkpoints, logs, and result files therefore refer to one round only. The startup protocol treats completed and archived projects as terminal instead of advancing beyond Phase 8. Prompt-invariant tests pin these contracts across both host entrypoints and the shared phase prompts.

Each result JSON must carry a complete `_meta` object with `experiment_id`, `config_fingerprint`, `script`, `log_file`, `timestamp`, `config`, and a positive integer `round`; `seed` is optional for already-aggregated results. The collector rejects malformed or non-object JSON, files without usable metrics, invalid metadata, and duplicate seed identities. Seed aggregation groups by round, experiment, configuration, method, and result group, preventing cross-experiment averages.

Citation verification distinguishes bibliographic identity from URL reachability. A reachable URL no longer satisfies strict verification. Missing title, author, or year remains a structural failure even when a DOI or external match exists. DOI metadata is compared against title, authors, year, and venue. Incomplete LaTeX scans are fatal because a partial scan cannot prove citation integrity.

Phase 0 no longer asks users to paste secrets. Configuration stores environment-variable names, never key values, and external code review is a separate opt-in because it sends unpublished source outside the host. Documentation explains how to launch the agent with provider variables already set. Tests cover every reproduced false-pass before implementation, and the full stdlib test suite remains the final gate.
