# Shared Conventions (All Phases, All Hosts)

This file is host-neutral and applies to **every phase**. Both entrypoints (`CLAUDE.md` for Claude Code, `AGENTS.md` for Codex) point here, and phase prompts reference it as `prompts/conventions.md`. When a phase prompt and this file disagree on state schema, enums, or round numbering, **this file wins**.

## State File: `{project_dir}/.research_state.json`

The single source of truth for session resumption. Schema:

```json
{
  "project_dir": "semantic_segmentation",
  "current_phase": 1,
  "sub_step": null,
  "current_round": 0,
  "current_round_short_name": "",
  "phase_status": "in_progress",
  "project_status": "active",
  "created_at": "2026-02-12T10:00:00Z",
  "updated_at": "2026-02-12T10:00:00Z",
  "topic": {
    "broad_topic": "",
    "specific_topic": "",
    "research_question": "",
    "positioning": "",
    "target_venue": "",
    "target_dataset": [],
    "metrics": []
  },
  "literature": {"papers_reviewed": [], "future_work_ideas": [], "selected_direction": ""},
  "experiment": {
    "plan": "",
    "scripts_ready": false,
    "status": "not_started",
    "checkpoints": [],
    "estimated_time_hours": 0,
    "hardware_requirements": {},
    "active_runs": []
  },
  "results": {"raw_results_path": "", "analysis_summary": "", "user_confirmed": false},
  "manuscript": {"title": "", "abstract": "", "latex_path": "", "figures": [], "status": "not_started"},
  "phase_history": []
}
```

## Enums (use these values EXACTLY — no improvisation)

| Field | Allowed values |
|-------|----------------|
| `phase_status` | `not_started` \| `in_progress` \| `waiting_for_user` \| `completed` \| `failed` |
| `project_status` | `active` \| `completed` \| `archived` |
| `experiment.status` | `not_started` \| `running` \| `completed` \| `failed` |
| `experiment.active_runs[].status` | `running` \| `completed` \| `failed` |
| `manuscript.status` | `not_started` \| `in_progress` \| `draft_complete` \| `in_review` \| `final` |
| `sub_step` | `null` \| `"refinement"` \| `"review_reentry"` (Phase 6 only) |

## `phase_history` Entry Format

Every phase transition appends one entry. Fixed shape:

```json
{
  "timestamp": "2026-02-12T10:00:00Z",
  "phase": 5,
  "round": 2,
  "event": "phase_completed",
  "note": "optional free text"
}
```

- `timestamp`: ISO 8601 UTC.
- `phase`: the phase this entry is about.
- `round`: current round, or `null` for pre-round phases (0–3).
- `event`: one of `phase_started` | `phase_completed` | `phase_failed` | `phase4_skipped` | `new_research_plan` | `round_closed` | `note`.
- Special events: a Phase 6 → Phase 5 direct skip MUST log `phase4_skipped`; a Phase 6 → Phase 3 return MUST log `new_research_plan`.

## State Write Rules

1. **Only the MAIN agent writes** `.research_state.json`. Subagents never touch it — they write only their own output files. The main agent reads subagent outputs and updates state itself.
2. **Atomic writes.** Never write the state file in place. Write the full JSON to `.research_state.json.tmp` in the same directory, then rename over the original. This prevents a killed session from leaving a truncated file.
3. **Corrupt-state recovery.** If the state file fails to parse on read: do NOT overwrite it blindly. Reconstruct a candidate state from `summaries/` and `research_roadmap.md`, show the user what you inferred, and get confirmation before writing the reconstructed state.
4. **Session lock.** On resuming a project, write `{project_dir}/.session_lock` containing the current timestamp. If a lock newer than 4 hours already exists, warn the user that another session may be active on this project and ask before proceeding. Delete the lock when the session ends a phase cleanly (best effort — a stale lock is a warning, never a hard block).
5. **Always** update the state file at every phase transition and significant checkpoint, and append to `phase_history` per the format above. Never advance phases without a state write.

### Legacy round-identity migration

Migration applies only when the `current_round_short_name` key is absent from a legacy state. For an existing active round (`current_round > 0`), infer it only if exactly one directory matches `{project_dir}/summaries/round{current_round}_*/`. Extract the suffix after `round{current_round}_` and validate it against the naming rules below. If zero or multiple directories match, **STOP and ask the user** to identify the active round rather than guessing. The MAIN agent must persist the confirmed or uniquely inferred `current_round_short_name` atomically before any round-specific work continues.

If the key is present with value `""`, do not run migration. That is intentional while pending Phase 4 naming after Phase 3 or a Phase 6 → Phase 4 route. Phase 4 must persist the chosen name before creating round artifacts; Phase 5 retains its nonempty precondition and must stop if naming was not completed.

## Round Numbering (monotonic — never reset)

- Round numbers are strictly sequential integers (1, 2, 3, ...). No gaps, no sub-round suffixes (no `8b`, `9b`).
- **Round numbers NEVER reset**, including when Phase 6 routes back to Phase 3 for a new research plan. The new plan's first round continues the sequence (e.g., Round 6 after a plan change following Round 5). The plan boundary is recorded as a `new_research_plan` entry in `phase_history` and as a section break in `research_roadmap.md`.
- If a round needs additional experiments, create a NEW round that references the previous one ("Extends Round 11 with additional seeds").
- Directory name: `summaries/round{N}_{short_name}/` where `short_name` is 1–3 words in `snake_case`, no spaces or special characters.
- `current_round_short_name` stores the active round's `short_name`; together with `current_round` it is the persistent round identity used after session resumption.
- **`short_name` ownership:** Phase 3 increments `current_round` and clears `current_round_short_name`. Phase 4 assigns and persists it when the design is confirmed. For rounds that skip Phase 4 (identical-config direct-to-Phase-5), Phase 6 assigns and persists it during round planning. Phase 8 review re-entry preserves the existing identity until Phase 6 confirms the next round.

## Summary Files & Phase Transition Checklist (MANDATORY)

After the user approves each phase's results, write a self-contained markdown summary under `{project_dir}/summaries/` — readable without the state file or conversation history.

- Initial phases: `phase1_topic.md`, `phase2_literature.md`, `phase3_research_plan.md` directly in `summaries/`.
- Per-round (phases 4–6): inside `summaries/round{N}_{short_name}/` — `phase4_experiment_design.md`, `phase5_experiment_log.md`, `phase6_results.md`, plus `round_summary.md`.
- Manuscript: `summaries/phase7_manuscript.md` (single file, updated across rounds).
- Review: `summaries/phase8_review.md` (single file, updated across review cycles).

**Before advancing to the next phase, verify the required summary files exist. If any is missing, STOP and write it first.**

- Moving past Phase 3 → all three initial summaries must exist.
- Closing a round → `phase5_experiment_log.md`, `phase6_results.md`, and `round_summary.md` must exist in the round's subfolder. `phase4_experiment_design.md` is required only if Phase 4 was actually executed for that round — **rounds that route directly to Phase 5 (identical config) may skip it; refinement rounds always execute Phase 4 and therefore always require it.**
- Moving past Phase 8 → `phase8_review.md` must exist.
- The current active round may be incomplete while work is in progress.

## Error Recovery

- **Never silently skip errors.** Always log them and inform the user.
- **Experiment failure recovery:**
  1. Save the error log to the current round's immutable log directory: `{project_dir}/experiment/logs/round{current_round}_{current_round_short_name}/`.
  2. Set the run's `experiment.active_runs[].status` to `"failed"`.
  3. Decision tree:
     - **Transient error** (OOM, timeout, network): retry up to 5x with the same config.
     - **Persistent error** (code bug, data issue): fix the script, re-run, log the fix in `phase5_experiment_log.md`.
     - **Systematic failure** (wrong approach, infeasible config): skip, note in Phase 6 analysis, consider returning to Phase 4.
  4. Never delete failed experiment logs — they are diagnostic evidence.
- **Stale state recovery:** if state says `"running"` but no such process exists, mark the run `"failed"` or `"completed"` based on whether result files exist.
- **Stale kill flag:** if `{project_dir}/experiment/.kill_agent` exists at session start or before launching any experiment agent, confirm with the user and delete it first — otherwise every new agent will immediately self-terminate.

## Per-Project Paths

The `project_dir` value from the state file is the base path for ALL file operations within a project. Shared infrastructure (`prompts/`, `scripts/`, the entrypoint files) is never modified per-project.
