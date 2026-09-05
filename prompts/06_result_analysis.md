# Phase 6: Result Analysis & Round Planning

## Objective
Analyze experiment results, generate tables and figures, perform statistical tests, and present a clear summary for user review before writing the manuscript.

## Mode
**Direct + Task subagents** for parallel analysis tasks.

## Entry Routing (check before prerequisites)

Read `.research_state.json` before doing any analysis. If `sub_step == "review_reentry"`, the persisted marker proves this is review-driven planning from Phase 8: preserve the existing `current_round` and `current_round_short_name`, skip the prerequisites and steps 6.1–6.8, and go directly to Round Planning with `{project_dir}/manuscript/review_synthesis.md` as an input. Do not infer re-entry from conversation history.

Keep `sub_step: "review_reentry"` while presenting options. When `review_reentry` is active, clear or change `sub_step` before leaving re-entry planning through any State Update route below; never leave the marker set after routing to Phase 3, 4, 5, or 7.

For normal analysis, require a nonempty `current_round_short_name` and define `round_dir = round{current_round}_{current_round_short_name}` once. Use that value for every current-round path below.

## Prerequisites
- All (or most) experiment × seed runs completed (check `{project_dir}/experiment/results/{round_dir}/*/seed*/COMPLETED` and validate each marker's experiment ID, seed, and fingerprint).
- If some experiments failed, note which ones and whether re-running is needed.
- **`phase5_experiment_log.md` must exist** in the current round's summary directory. If it does not, write it before proceeding with analysis.

## Steps

### 6.1 Result Collection (Automated)

**DO NOT manually read result files and construct tables from memory.**

Run the automated collection script FIRST:

```bash
python3 scripts/collect_results.py {project_dir}/experiment/results/{round_dir}/ \
    --fail-on-warnings \
    --output-md {project_dir}/experiment/results/{round_dir}/comparison_table.md \
    --output-json {project_dir}/experiment/results/{round_dir}/comparison_table.json
```

Then read `comparison_table.md` and use it as the **sole source** for all numerical claims in this phase. If a number does not appear in the generated table, it does not exist — do not cite metrics from memory or from a quick glance at a JSON file.

**Exit-code semantics:** with `--fail-on-warnings`, the script exits non-zero when any result file has a missing `_meta` field or fails to parse. A non-zero exit is a hard gate — fix the offending result files and re-run until the script exits 0 before proceeding. (The script skips its own `comparison_table*.json` outputs during ingestion, so re-runs are safe.)

To focus on specific metrics, use `--metric-keys`:
```bash
python3 scripts/collect_results.py {project_dir}/experiment/results/{round_dir}/ \
    --fail-on-warnings \
    --metric-keys accuracy,error_rate,latency \
    --output-md {project_dir}/experiment/results/{round_dir}/comparison_table.md \
    --output-json {project_dir}/experiment/results/{round_dir}/comparison_table.json
```

### 6.2 Main Results Table

Create the primary comparison table using numbers from `comparison_table.md` (generated in 6.1):

```
Table 1: Main Results on [Dataset]
─────────────────────────────────────────────────────
Method          | mIoU (↑)      | mAP (↑)       | FPS
─────────────────────────────────────────────────────
Baseline        | 72.3 ± 0.4    | 45.1 ± 0.3    | 30
Method A [ref]  | 74.1 ± 0.5    | 47.2 ± 0.4    | 28
Method B [ref]  | 73.8 ± 0.3    | 46.5 ± 0.2    | 32
Ours            | 76.2 ± 0.3    | 49.3 ± 0.4    | 29
─────────────────────────────────────────────────────
```

**Provenance rule:** Every number in sections 6.2-6.7 must trace to a specific entry in `comparison_table.json`. When writing `phase6_results.md`, include the source file path for each claim:

> mIoU improved from 72.3±0.4 (baseline, `experiment/results/{round_dir}/E01/seed*/eval_results.json`)
> to 76.2±0.3 (ours, `experiment/results/{round_dir}/E02/seed*/eval_results.json`)

### 6.3 Ablation Study Table

```
Table 2: Ablation Study
────────────────────────────────────
Configuration    | mIoU (↑)
────────────────────────────────────
Full method      | 76.2 ± 0.3
w/o component A  | 74.8 ± 0.4
w/o component B  | 75.1 ± 0.3
w/o component C  | 73.9 ± 0.5
────────────────────────────────────
```

### 6.4 Statistical Tests

Use a bounded task subagent, or work directly when unavailable, to prepare statistical tests. Before executing any analysis or figure script that computes values, complete the Code Verification Protocol in section 6.6 and Phase 5; section order is not permission to run unreviewed code. Then run the verified tests:

```
For each pair of methods being compared:
1. Paired t-test (if normally distributed) or Wilcoxon signed-rank test.
2. Report p-values.
3. Mark statistically significant improvements (p < 0.05).
4. Compute effect size (Cohen's d).
5. Save results to {project_dir}/experiment/results/{round_dir}/statistical_tests.json
```

**`_meta` requirement:** `statistical_tests.json` — and any other JSON emitted by analysis or figure tasks into `experiment/results/{round_dir}/` — must include the canonical fields `experiment_id`, `evidence_contract`, `evidence_contract_id`, `evidence_contract_fingerprint`, `outcome_id`, `analysis_protocol_id`, `script`, `log_file`, `timestamp`, `resolved_config`, `config_fingerprint`, `round`, and `seed`. `seed` is always required and must never be omitted. Per-run files use a nonnegative integer; aggregated files use `seed: "aggregate"`, and `resolved_config.contributing_seeds` must be a nonempty list of nonnegative integers. Without this metadata, the current round's `collect_results.py --fail-on-warnings` gate fails on these files. The Result File Convention in `prompts/05_experiment_execution.md` remains authoritative.

After generating statistical test results, update `{project_dir}/experiment/results/{round_dir}/INDEX.md` with any new result files created during analysis.

### 6.5 Figure Generation (via Task subagent)

Generate publication-quality figures using matplotlib:

```
Task: Generate figures for the manuscript.

Save all figures to {project_dir}/manuscript/figures/

Required figures:
1. fig_main_comparison.pdf — Bar chart or table visualization of main results.
2. fig_ablation.pdf — Ablation study visualization.
3. fig_training_curves.pdf — Training loss/metric curves across epochs for key experiments.
4. fig_qualitative.pdf — Qualitative examples (if applicable):
   - Input images
   - Ground truth
   - Baseline prediction
   - Our prediction
   Side-by-side comparison grid.

Style requirements:
- Use matplotlib with a clean, publication-ready style.
- Font size: 10-12pt for readability in a two-column paper.
- Colors: use a colorblind-friendly palette.
- Vector format (PDF) for all figures.
- Figure width: single column (~3.5in) or double column (~7in) as appropriate.
- Include proper axis labels, legends, and titles.
- No grid lines unless they aid readability.
```

### 6.6 Code Verification

Apply the full **Code Verification Protocol** (defined in `prompts/05_experiment_execution.md`) to every analysis, statistical-test, and figure generation script written in this phase. This is the same 3-step protocol used for Phase 5 experiment scripts:

1. **Independent logical review** — verify data flow, train/val/test splits, and feature-label correspondence. Use a host-native adversarial reviewer unless `.rev2agent_config.json` has `external_code_review` as the JSON boolean exactly `true`, `roles.verification` selects a configured external provider/model, and that provider's `api_key_env` is present. Otherwise no code, excerpts, or data leave the host.
2. **Simplify code-quality pass** — unused imports, duplication, variable shadowing, memory efficiency, magic numbers.
3. **Syntax check + execution**.

**Step 1 is not optional for figure or analysis scripts.** Scripts that fit auxiliary models, recompute outcomes, or generate evidence-bearing values at runtime are exactly the class of scripts where executable code can silently evaluate the wrong evidence. Pure-rendering scripts (read a validated result artifact and render it without recomputation) are exempt from Step 1 but still require Step 2.

### 6.7 Interpretation

After collecting all quantitative results, provide interpretation:

1. **Main finding**: Does the hypothesis hold? By how much?
2. **Surprises**: Any unexpected results? Explain possible reasons.
3. **Ablation insights**: Which components contribute most? Any interactions?
4. **Failure cases**: Where does the method underperform? Why?
5. **Comparison to SOTA**: How does this compare to published numbers?

### Material Deviation Gate (MANDATORY)

Compare the collected evidence with the predeclared Evidence Contract before
interpreting success. A deviation is material when it crosses a contract's
declared tolerance or invalidity rule, breaks an expected control or data-flow
assumption, or could change the conclusion, positioning, or claim scope.

On any material deviation, stop progression to manuscript writing and diagnose
the cause. Do not explain the deviation away, replace the primary outcome, or
change the comparison or aggregation after seeing results and still call the
analysis confirmatory.

A post-hoc outcome, comparator, aggregation, or interpretation change is
allowed only as an **exploratory** finding. Preserve the original result and
reason for the change, create a new Evidence Contract version, and obtain new
or independently confirmed evidence before using the changed analysis as a
central confirmatory claim.

### 6.8 Assess Paper Viability

Honestly assess whether the results are strong enough:
- **Strong enough for target venue**: Proceed to manuscript writing.
- **Marginal**: Suggest additional experiments or a different venue.
- **Negative results**: Discuss whether a negative-results paper is appropriate, or pivot.

## Round Planning

This section handles planning the next experiment round by consulting the persistent research roadmap. It ensures that research directions are never lost between rounds and that planning decisions are informed by the full history of ideas.

This section triggers after the analysis steps above (6.1–6.8) when the user is deciding what to do next. It also triggers after Phase 7 feedback when the user decides to run another experiment round. It does NOT trigger if the user is proceeding directly to final manuscript submission with no further experiments planned.

**Phase 8 re-entry mode:** The Entry Routing rule above is authoritative. `sub_step == "review_reentry"` means the previous round is already closed; its identity remains unchanged until the user confirms a State Update route for the next work.

### Review Re-entry Bookkeeping Guard (MANDATORY)

When `sub_step == "review_reentry"`, the prior round is immutable closure history:

- Do not move the prior round's Active direction to Completed again.
- Do not append a Results Comparison row for the prior round.
- Do not re-run abandonment or other normal-analysis closure bookkeeping for the prior round.
- Do not write or modify the prior round's `phase6_results.md` or `round_summary.md`.
- Preserve the prior round's existing summaries and `phase_history` entries.
- May re-prioritize Pending directions and add new Pending directions from `review_synthesis.md`.

Read the existing roadmap and review synthesis, make only those allowed planning updates, then route to the newly confirmed round. Every normal-analysis closure instruction below is subordinate to this guard.

### 6.9 Read the Roadmap

Before proposing any options for the next round:

```
1. Read {project_dir}/research_roadmap.md in full.
2. Read the latest result analysis ({project_dir}/summaries/round{N}_{short_name}/phase6_results.md, latest round).
3. Read any feedback files ({project_dir}/feedback_*.md) if they exist and are newer than the last roadmap update.
4. Read {project_dir}/manuscript/review_synthesis.md if Phase 8 has run.
```

**Feedback file convention:** the user may drop external feedback (e.g., advisor comments, real reviewer comments) into the project root as `{project_dir}/feedback_*.md` at any time. Always check for these files when planning a round.

### 6.10 Update Roadmap

Before presenting options, update the roadmap according to the active mode. In `review_reentry`, perform only Pending-priority and new-Pending updates supported by `review_synthesis.md`; the normal closure steps are skipped.

1. **Normal analysis only — skip in `review_reentry`: Move the just-completed direction from Active to Completed.** Include a one-line result summary (key metric, main finding).
2. **Re-evaluate Pending priorities.** Current results may change the expected impact of pending directions:
   - If results suggest a certain direction is now more promising, move it up.
   - If evidence makes a direction less relevant, move it down within Pending. Only normal analysis may move it to Abandoned under step 4.
3. **Add new directions discovered during the round.** Analysis, Grad-CAM, error analysis, or feedback often suggest new ideas. Add them to the appropriate priority tier with rationale and source.
4. **Normal analysis only — skip in `review_reentry`: Check for abandonment candidates.** Explicitly ask: "Did this round's evidence render any Active or Pending direction unviable?" For each such direction, move it to Abandoned with a reason from the enum:
   - `falsified` — experiment disproved the hypothesis. **Evidence field is mandatory and must be a concrete path** (e.g., `experiment/results/{round_dir}/{exp_id}/seed{seed}/eval_results.json` or `summaries/roundN_*/phase6_results.md`).
   - `out_of_scope` — valid direction but outside the current project's scope.
   - `low_value` — **judgment** call: expected payoff no longer justifies the cost, given current results. Use this when the direction is *possible* but not *worth* pursuing.
   - `solved_elsewhere` — prior or concurrent work already addressed it.
   - `infeasible` — **concrete blocker**: specific resource, time, or data constraint (e.g., no GPU ≥40GB, dataset not public, required annotation unavailable). Use this when the direction is *blocked*, not merely expensive.
   Each entry must also include a **Revisit trigger** (condition for reconsidering it, or `"none"`). Never silently drop directions.

**Distinguishing `low_value` vs `infeasible`:** If a concrete obstacle names itself ("no multi-node cluster", "annotation would cost $50k"), use `infeasible`. If the judgment is "we could do this but it's not a priority", use `low_value`. When in doubt, `infeasible` is the stricter claim — only use it when the blocker is real and namable.
5. **Normal analysis only — skip in `review_reentry`: Append a row to the Results Comparison table** with the round's key quantitative outcome (target metric, best baseline, delta, one-line finding). Never delete or modify previous rows.
6. **Write the updated roadmap to disk** before presenting options to the user.

**Legacy migration:** If the existing roadmap file uses the older `## Dropped` section, rename it to `## Abandoned` on this update and convert each entry to the structured format below (fill in reason/evidence/revisit-trigger from the entry's original rationale).

#### Theoretical Feasibility Check

Before proposing engineering solutions to a negative result, check whether a theoretical limit applies:
- If an experiment failed (e.g., an attack succeeded, a defense was broken), search for impossibility theorems or known lower bounds in the relevant literature before designing workarounds.
- If a theoretical limit exists (e.g., "utility-preserving encodings necessarily leak information"), acknowledge it and reframe the research direction rather than attempting to engineer around a mathematical impossibility.
- This prevents wasted rounds exploring dead ends that theory already rules out.

### 6.11 Present Round Options

Present 3-5 options for the next round, drawn primarily from the Pending lists. Format:

```
Next Round Options
──────────────────

Based on the roadmap and Round N results, here are the top candidates:

Option A: [Direction Name]
  From: Roadmap (High Priority)
  Rationale: [Why now, given current results]
  Expected impact: [Metric estimate or qualitative]
  Effort: [Low/Medium/High]

Option B: [Direction Name]
  From: Roadmap (Medium Priority) — promoted because [reason from current results]
  Rationale: ...
  Expected impact: ...
  Effort: ...

Option C: [New direction not on roadmap]
  From: Discovered during Round N analysis
  Rationale: [What in the results suggested this]
  Expected impact: ...
  Effort: ...

Option D: Narrative reframing + manuscript revision (no new experiments)
  Rationale: [If results are strong enough to write up as-is]

Recommendation: Option [X] because [reason].
```

**Rules for option generation:**
- At least 2 options must come from the existing Pending lists.
- At most 1 option may be newly invented (and it must be added to the roadmap regardless of whether it is chosen).
- Always include a "no new experiments / write up as-is" option if the results are publishable.
- Never discard the non-chosen options. They stay on the roadmap for future rounds.

### 6.12 Update Roadmap After User's Choice

Once the user picks a direction:

Activation is route-specific, including in `review_reentry`:

- Reserve and activate `current_round + 1` only for a Phase 4 or direct Phase 5 route.
- A Phase 7 route creates no new round and no Active next-round entry.
- A Phase 3 route creates no Active experimental round during re-entry planning; Phase 3 owns the next increment and empty short name after the new plan is confirmed, with later phases owning activation.

1. **For Phase 4 or direct Phase 5 only, mark the chosen direction Active** with the reserved next-round number (e.g., `[R5]`).
2. **Keep all non-chosen directions in Pending** at their current priority level.
3. **If a new direction was proposed in the options but not chosen**, add it to the appropriate Pending tier.
4. **Normal analysis only — skip in `review_reentry`: Mid-round abandonment (special case).** If the user explicitly abandons the currently Active direction (e.g., a pivot mid-round) instead of completing it, move it directly from Active to Abandoned with a reason from the enum. It does NOT need to pass through Completed first.
5. **Config drift check** (this prompt owns the protocol): If the chosen direction changes the project's default experimental configuration (e.g., architecture, output dimensions, number of layers, preprocessing), scan all Python scripts under `{project_dir}/` for hardcoded references to the old config (grep for the old values: dimensions, layer counts, model names, paths). Flag any scripts that need updating — especially figure/visualization generation scripts, which are often written once and not revisited when the default config evolves. List the flagged scripts to the user, update them before the next round runs, and note the config change in `{project_dir}/manuscript/data_provenance.md` if a manuscript exists (runtime-computed figure values are the highest-risk entries for drift).
6. **Write the updated roadmap to disk.**
7. **Proceed through the selected State Update route** below; do not create round state or roadmap activation that belongs to a different route.

### When to set `sub_step: "refinement"`

When routing back to Phase 4, set `sub_step` to `"refinement"` (Phase 4 then runs in Refinement Mode — see `prompts/04_experiment_design.md`) if ANY of the following holds:

- **Mandatory after Round 1** — the first round is always treated as a pilot.
- A result triggers the **Material Deviation Gate** under its predeclared Evidence Contract or would materially change the conclusion or claim scope.
- An experiment reveals the paper's **positioning must change** (e.g., an attack succeeds, a baseline beats the proposed method).
- A **confound or artifact** was discovered in the data.
- The **default config changes** (architecture, dimensions, etc.).

Otherwise set `sub_step: null` for a normal Phase 4 design round. Refinement rounds still execute Phase 4 in full and require `phase4_experiment_design.md`.

### 6.13 Write Round Summary

If `sub_step == "review_reentry"`, skip this entire section. The prior round's `round_summary.md`, `phase6_results.md`, and other closure artifacts already exist and must not be rewritten.

After completing a round, write `round_summary.md` in the round subfolder. See `prompts/conventions.md` for the subfolder layout and the summary-file checklist.

**Required files in the round subfolder** (per the checklist in `prompts/conventions.md`): `round_summary.md`, `phase5_experiment_log.md`, `phase6_results.md`. `phase4_experiment_design.md` is required only if Phase 4 was executed this round — rounds that route directly to Phase 5 (identical config) may skip it; refinement rounds always execute Phase 4 and therefore always require it. `phase7_manuscript.md` is NOT per-round; it is a single file at `summaries/phase7_manuscript.md` updated across rounds.

**`round_summary.md` contents** (mandatory — must be readable without `.research_state.json` or the conversation history):

- **Objective** — What the round aimed to test
- **Experiments** — What was run (methods, configs, baselines)
- **Results** — Key metrics in tables, comparisons to baselines
- **Key takeaway** — One paragraph: what did we learn, what does it change?
- **Files created** — Scripts, data, result files produced

## Roadmap Initialization (First-Time Setup)

If `{project_dir}/research_roadmap.md` does not exist when this phase triggers:

1. Review all phase summaries in `{project_dir}/summaries/`.
2. Review any feedback files (`{project_dir}/feedback_*.md` — external feedback such as advisor comments or real reviews that the user may drop into the project root), and `{project_dir}/manuscript/review_synthesis.md` if Phase 8 has run.
3. Review the phase history in `.research_state.json`.
4. Compile all mentioned-but-not-pursued directions into a roadmap.
5. Classify completed rounds as Completed, current work as Active, everything else as Pending.
6. Write the initial roadmap to `{project_dir}/research_roadmap.md`.

## Roadmap File Format

The roadmap uses this markdown structure:

```markdown
# Research Roadmap: [Project Name]

> Last updated: YYYY-MM-DD (after Round N / brief context)

## Results Comparison

A cross-round table tracking quantitative outcomes. Updated every round. Keeps all rounds visible for at-a-glance comparison, even when methods differ significantly between rounds.

| Round | Method | Target Metric | Best Baseline | Δ | Key Finding |
|-------|--------|--------------|---------------|-----|-------------|
| R1 | [method name] | [value ± std] | [baseline value] | [+/-diff] | [one-line takeaway] |
| R2 | [method name] | [value ± std] | [baseline value] | [+/-diff] | [one-line takeaway] |

**Table rules:**
- **Target Metric** column uses the project's primary evaluation metric (defined in Phase 3). If the metric changes between rounds, note the old metric in parentheses.
- **Best Baseline** is the strongest baseline *for that round's setup* (dataset/split may vary).
- **Δ** = Target Metric − Best Baseline (positive = our method wins).
- **Key Finding** is a single phrase capturing what the round proved or disproved.
- Rows are never deleted. Failed or negative rounds stay in the table — they are evidence too.

## Active
- **[RN] Direction Name** — Description. *Status: Running/Planning.*

## Pending (High Priority)
- **[R?] Direction Name** — Description. *Added: RN context. Source: who suggested it. Expected impact: ...*

## Pending (Medium Priority)
- ...

## Pending (Low Priority / Speculative)
- ...

## Completed
- **[RN] Direction Name** — Description. *Result: key metric or finding.*

## Abandoned
- **[RN] Direction Name** — one-line description
  - **Abandoned at:** Round N, Phase X
  - **Reason:** one of `falsified` | `out_of_scope` | `low_value` | `solved_elsewhere` | `infeasible`
  - **Evidence:** for `falsified`, path to the result file that disproved it (e.g., `experiment/results/{round_dir}/{exp_id}/seed{seed}/eval_results.json`). For other reasons, 1-2 sentence rationale.
  - **Revisit trigger:** condition that would reopen this direction, or `none`
```

**Conventions:**
- `[RN]` = assigned round number. `[R?]` = not yet assigned.
- Active / Pending / Completed entries are single bullets with bold title, em-dash, description, and italicized metadata.
- Abandoned entries use the structured multi-field format above — all four fields are mandatory.
- Keep descriptions concise (1-3 sentences). Link to detailed files if needed.
- Priority tiers are re-evaluated every round, not fixed permanently.

**Abandonment reason enum (`falsified` / `out_of_scope` / `low_value` / `solved_elsewhere` / `infeasible`)** is fixed. Do not invent new reasons without discussion — ambiguity collapses back into the old "dropped for some reason" problem this format is designed to prevent.

## Anti-Pattern Warnings

- **Do NOT invent a full slate of new options and ignore the roadmap.** The roadmap is the primary source of options. New ideas supplement it, not replace it.
- **Do NOT silently drop directions.** If a direction is no longer worth pursuing, move it to Abandoned with a reason from the enum (`falsified` / `out_of_scope` / `low_value` / `solved_elsewhere` / `infeasible`), evidence (result file path for `falsified`; rationale for others), and a revisit trigger.
- **Do NOT over-plan.** The roadmap is a living list, not a rigid Gantt chart. Keep entries lightweight.
- **Do NOT block on roadmap perfection.** If unsure about priority, make a reasonable guess and move on. Priorities get re-evaluated every round anyway.

## Output to User

```
📊 Experiment Results Summary
──────────────────────────────
Experiments completed: [N/M]
Failed experiments: [list if any]

🏆 Key Finding:
[1-2 sentence summary of the main result]

📈 Main Results:
[Table 1]

🔬 Ablation Results:
[Table 2]

📉 Statistical Significance:
[Summary of p-values — which improvements are statistically significant]

💡 Interpretation:
[3-4 sentences of analysis]

📊 Figures generated:
[List of figures with descriptions]

🎯 Assessment:
[Honest assessment of paper viability for target venue]
```

Ask: **"Here are the experiment results. The key finding is [X]. Do these results look reasonable to you? Shall I proceed with writing the manuscript?"**

## Handling Negative, Weak, or Improvable Results

If results don't support the hypothesis, or if results are positive but could be substantially stronger:
1. Don't hide it. Present honestly.
2. Propose options, **prioritizing iterative improvement over premature acceptance**:
   a. Run additional experiments with different configurations.
   b. Analyze WHY the results are negative or weak (this can itself be a contribution).
   c. **Propose architectural or methodological changes** that could improve results — even if they require going back to earlier phases (e.g., replacing the backbone, changing the feature extraction pipeline, trying new loss functions). There are no deadlines; impact matters more than speed.
   d. Pivot the narrative (e.g., from "our method improves X" to "we show that Y is harder than expected").
   e. Target a different venue (workshop, findings track).
3. Let the user decide, but **default to recommending improvements when they have clear potential**, rather than settling for weak results.

**Important**: Impact takes precedence over speed — there are no deadlines driving this work. If analysis reveals a fundamentally better approach, recommend looping back to Phase 3 or Phase 4 rather than settling for weak results — each iteration builds on what was learned before.

## Phase Summary

If `sub_step == "review_reentry"`, do not write or modify either prior-round summary file. Skip directly to the State Update after the user chooses the next route; the existing `phase6_results.md` and `round_summary.md` remain authoritative.

After analysis and round planning are complete, write:
- **File**: `{project_dir}/summaries/{round_dir}/phase6_results.md`
- **Contents**: Main results table, ablation table, statistical test results, interpretation, paper viability assessment, round planning decision.

- **File**: `{project_dir}/summaries/{round_dir}/round_summary.md`
- **Contents**: Objective, experiments run, results tables, key takeaway, files created.

Both files must exist before proceeding to the next phase.

## State Update

After normal analysis, the user confirms results and picks the next direction (or manuscript). In `review_reentry`, the user picks the next route from review-driven planning without reconfirming or rewriting prior-round results.

Round identity rules are route-specific: the Phase 4 route clears `current_round_short_name` to `""`; the direct Phase 5 route sets `current_round_short_name` to the short name confirmed during planning; Phase 7 and Phase 3 routes preserve `current_round_short_name` for the last completed round. These rules also clear or change `sub_step` when leaving `review_reentry` planning, as specified below.

For `review_reentry`, never move the prior round to Completed again. Preserve its summaries and history; never append another `round_closed` or `phase_completed` event for it. A new `note`, `phase4_skipped`, or `new_research_plan` routing event may be appended when the selected route requires one.

**If proceeding to another round (Phase 4):**
- `current_phase`: `4`
- `sub_step`: `null` (normal) or `"refinement"` (if reframing needed — see "When to set `sub_step: \"refinement\"`" above)
- `current_round`: increment by 1
- `current_round_short_name`: `""` — Phase 4 names and persists the newly confirmed round.
- `phase_status`: `"not_started"`
- `project_status`: unchanged
- `experiment.status`: `"completed"` after normal analysis; unchanged in `review_reentry`
- Normal analysis only: populate `results.raw_results_path`, `results.analysis_summary`, and set `results.user_confirmed` to `true`; preserve them in `review_reentry`
- **Update roadmap:** Normal analysis moves the just-completed round to Completed; `review_reentry` leaves the prior round unchanged. Reserve the incremented round and mark the chosen direction Active; Phase 4 will persist its short name.
- Append the Phase 6 completion event in normal analysis; for `review_reentry`, append only a `note` describing the planning route.

**If proceeding directly to Phase 5 (identical config — additional seeds/repetitions only, no design changes):**
- `current_phase`: `5`
- `sub_step`: `null`
- `current_round`: increment by 1
- `current_round_short_name`: the confirmed `short_name` assigned during this round-planning decision
- `phase_status`: `"not_started"`
- `project_status`: unchanged
- `experiment.status`: `"completed"` after normal analysis; unchanged in `review_reentry`
- Normal analysis only: populate `results.raw_results_path`, `results.analysis_summary`, and set `results.user_confirmed` to `true`; preserve them in `review_reentry`
- **Assign the round's `short_name`** during round planning (Phase 4 will not run for this round — see `prompts/conventions.md` "Round Numbering")
- **Update roadmap:** Normal analysis moves the just-completed round to Completed; `review_reentry` leaves the prior round unchanged. Reserve the incremented round and mark the chosen direction Active using the short name confirmed here.
- Append a `phase4_skipped` event to `phase_history` (entry format in `prompts/conventions.md`)

**If proceeding to manuscript (Phase 7):**
- `current_phase`: `7`
- `sub_step`: `null`
- `current_round`: unchanged
- `current_round_short_name`: unchanged
- `phase_status`: `"not_started"`
- `project_status`: unchanged
- `experiment.status`: `"completed"` after normal analysis; unchanged in `review_reentry`
- Normal analysis only: populate `results.raw_results_path`, `results.analysis_summary`, and set `results.user_confirmed` to `true`; preserve them in `review_reentry`
- **Update roadmap:** Normal analysis moves the current round to Completed; `review_reentry` makes no closure change.
- No new round is reserved and no Active next-round entry is created; `current_round` and its short name remain unchanged.
- Append the Phase 6 completion event in normal analysis; for `review_reentry`, append only a `note` describing the return to manuscript work.

**If returning to Phase 3 (fundamental rethink):**
- `current_phase`: `3`
- `sub_step`: `null`
- `current_round`: unchanged — **round numbers are monotonic and NEVER reset** (see `prompts/conventions.md` "Round Numbering"); the new plan's first round continues the sequence
- `current_round_short_name`: unchanged until Phase 3 confirms the new plan, increments the round, and clears it
- `phase_status`: `"not_started"`
- `project_status`: unchanged
- `experiment.status`: `"completed"` after normal analysis; unchanged in `review_reentry`
- Do not reserve or activate a new experimental round during re-entry planning. Phase 3 owns the increment and empty short name after the new plan is confirmed; activation follows that confirmed plan.
- Keep all existing round folders and roadmap entries; add a plan-boundary marker (section break) to `research_roadmap.md`
- Append a `new_research_plan` event to `phase_history` (entry format in `prompts/conventions.md`) with explanation of why rethink was needed
