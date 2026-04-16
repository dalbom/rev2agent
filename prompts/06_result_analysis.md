# Phase 6: Result Analysis & Round Planning

## Objective
Analyze experiment results, generate tables and figures, perform statistical tests, and present a clear summary for user review before writing the manuscript.

## Mode
**Direct + Task subagents** for parallel analysis tasks.

## Prerequisites
- All (or most) experiments completed (check `{project_dir}/experiment/results/*/COMPLETED`).
- If some experiments failed, note which ones and whether re-running is needed.
- **`phase5_experiment_log.md` must exist** in the current round's summary directory. If it does not, write it before proceeding with analysis.

## Steps

### 6.1 Result Collection (Automated)

**DO NOT manually read result files and construct tables from memory.**

Run the automated collection script FIRST:

```bash
python3 scripts/collect_results.py {project_dir}/experiment/results/ \
    --output-md {project_dir}/experiment/results/comparison_table.md \
    --output-json {project_dir}/experiment/results/comparison_table.json
```

Then read `comparison_table.md` and use it as the **sole source** for all numerical claims in this phase. If a number does not appear in the generated table, it does not exist — do not cite metrics from memory or from a quick glance at a JSON file.

If the script reports warnings (missing `_meta`, unparseable files), fix those files before proceeding.

To focus on specific metrics, use `--metric-keys`:
```bash
python3 scripts/collect_results.py {project_dir}/experiment/results/ \
    --metric-keys cls_auc,recon_ssim,verif_auc \
    --output-md {project_dir}/experiment/results/comparison_table.md \
    --output-json {project_dir}/experiment/results/comparison_table.json
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

> mIoU improved from 72.3±0.4 (baseline, `round1_seed*/eval.json`)
> to 76.2±0.3 (ours, `round1_seed*/eval.json`)

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

Use Task subagent to run statistical tests:

```
For each pair of methods being compared:
1. Paired t-test (if normally distributed) or Wilcoxon signed-rank test.
2. Report p-values.
3. Mark statistically significant improvements (p < 0.05).
4. Compute effect size (Cohen's d).
5. Save results to {project_dir}/experiment/results/statistical_tests.json
```

After generating statistical test results, update `{project_dir}/experiment/results/INDEX.md` with any new result files created during analysis.

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

Apply the full **Code Verification Protocol** (defined in `prompts/05_experiment_execution.md`, also summarized as a global rule in CLAUDE.md) to every analysis, statistical-test, and figure generation script written in this phase. This is the same 3-step protocol used for Phase 5 experiment scripts:

1. **External-model logical review** — verify data flow, train/val/test splits, feature–label correspondence.
2. **Simplify code-quality pass** — unused imports, duplication, variable shadowing, memory efficiency, magic numbers.
3. **Syntax check + execution**.

**Step 1 is not optional for figure or analysis scripts.** Scripts that train decoders, compute metrics, or generate numerical values at runtime are exactly the class of scripts where the Round 5 silent-failure incident occurred (train features matched against val images). Pure-plotting scripts (read a JSON, render a figure) are exempt from Step 1 but still require Step 2.

### 6.7 Interpretation

After collecting all quantitative results, provide interpretation:

1. **Main finding**: Does the hypothesis hold? By how much?
2. **Surprises**: Any unexpected results? Explain possible reasons.
3. **Ablation insights**: Which components contribute most? Any interactions?
4. **Failure cases**: Where does the method underperform? Why?
5. **Comparison to SOTA**: How does this compare to published numbers?

### 6.8 Assess Paper Viability

Honestly assess whether the results are strong enough:
- **Strong enough for target venue**: Proceed to manuscript writing.
- **Marginal**: Suggest additional experiments or a different venue.
- **Negative results**: Discuss whether a negative-results paper is appropriate, or pivot.

## Round Planning

This section handles planning the next experiment round by consulting the persistent research roadmap. It ensures that research directions are never lost between rounds and that planning decisions are informed by the full history of ideas.

This section triggers after the analysis steps above (6.1–6.8) when the user is deciding what to do next. It also triggers after Phase 7 feedback when the user decides to run another experiment round. It does NOT trigger if the user is proceeding directly to final manuscript submission with no further experiments planned.

### 6.9 Read the Roadmap

Before proposing any options for the next round:

```
1. Read {project_dir}/research_roadmap.md in full.
2. Read the latest result analysis ({project_dir}/summaries/phase6_results.md or equivalent).
3. Read any feedback files ({project_dir}/feedback_*.md) if they exist and are newer than the last roadmap update.
```

### 6.10 Update Roadmap

Before presenting options, update the roadmap to reflect what was just learned:

1. **Move the just-completed direction from Active to Completed.** Include a one-line result summary (key metric, main finding).
2. **Re-evaluate Pending priorities.** Current results may change the expected impact of pending directions:
   - If results suggest a certain direction is now more promising, move it up.
   - If results make a direction irrelevant (e.g., a feature it depended on turned out to be uninformative), move it down or to Abandoned (see step 4).
3. **Add new directions discovered during the round.** Analysis, Grad-CAM, error analysis, or feedback often suggest new ideas. Add them to the appropriate priority tier with rationale and source.
4. **Check for abandonment candidates.** Explicitly ask: "Did this round's evidence render any Active or Pending direction unviable?" For each such direction, move it to Abandoned with a reason from the enum:
   - `falsified` — experiment disproved the hypothesis. **Evidence field is mandatory and must be a concrete path** (e.g., `experiment/results/roundN_something.json` or `summaries/roundN_*/phase6_results.md`).
   - `out_of_scope` — valid direction but outside the current project's scope.
   - `low_value` — expected payoff no longer justifies the cost, given current results.
   - `solved_elsewhere` — prior or concurrent work already addressed it.
   - `infeasible` — resource, time, or data constraints make it unworkable.
   Each entry must also include a **Revisit trigger** (condition for reconsidering it, or `"none"`). Never silently drop directions.
5. **Append a row to the Results Comparison table** with the round's key quantitative outcome (target metric, best baseline, delta, one-line finding). Never delete or modify previous rows.
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

1. **Mark the chosen direction as Active** with the round number (e.g., `[R5]`).
2. **Keep all non-chosen directions in Pending** at their current priority level.
3. **If a new direction was proposed in the options but not chosen**, add it to the appropriate Pending tier.
4. **Mid-round abandonment (special case):** If the user explicitly abandons the currently Active direction (e.g., a pivot mid-round) instead of completing it, move it directly from Active to Abandoned with a reason from the enum. It does NOT need to pass through Completed first.
5. **Config drift check**: If the chosen direction changes the project's default experimental configuration (e.g., architecture, output dimensions, number of layers, preprocessing), scan all Python scripts under `{project_dir}/` for hardcoded references to the old config. Flag any scripts that need updating — especially figure/visualization generation scripts, which are often written once and not revisited when the default config evolves. See CLAUDE.md "Config Drift Check" for details.
6. **Write the updated roadmap to disk.**
7. **Proceed to Phase 4 (Experiment Design) or Phase 5 (Experiment Execution)** as appropriate for the chosen direction.

### 6.13 Write Round Summary

After completing a round, write `round_summary.md` in the round subfolder. See CLAUDE.md "Directory Structure" for the subfolder layout and "Phase Transition Checklist" for the file existence requirements.

**Required files in the round subfolder** (per CLAUDE.md Phase Transition Checklist): `round_summary.md`, `phase5_experiment_log.md`, `phase6_results.md`. `phase4_experiment_design.md` is required only if Phase 4 was executed this round — refinement rounds may skip it. `phase7_manuscript.md` is NOT per-round; it is a single file at `summaries/phase7_manuscript.md` updated across rounds.

**`round_summary.md` contents** (mandatory — must be readable without `.research_state.json` or the conversation history):

- **Objective** — What the round aimed to test
- **Experiments** — What was run (methods, configs, baselines)
- **Results** — Key metrics in tables, comparisons to baselines
- **Key takeaway** — One paragraph: what did we learn, what does it change?
- **Files created** — Scripts, data, result files produced

## Roadmap Initialization (First-Time Setup)

If `{project_dir}/research_roadmap.md` does not exist when this phase triggers:

1. Review all phase summaries in `{project_dir}/summaries/`.
2. Review any feedback files in `{project_dir}/`.
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
  - **Evidence:** for `falsified`, path to the result file that disproved it (e.g., `experiment/results/roundN_something.json`). For other reasons, 1-2 sentence rationale.
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

**Important**: See CLAUDE.md "Research Philosophy: Impact Over Speed". If analysis reveals a fundamentally better approach, recommend looping back to Phase 3 or Phase 4 rather than settling for weak results — each iteration builds on what was learned before.

## Phase Summary

After analysis and round planning are complete, write:
- **File**: `{project_dir}/summaries/round{current_round}_{short_name}/phase6_results.md`
- **Contents**: Main results table, ablation table, statistical test results, interpretation, paper viability assessment, round planning decision.

- **File**: `{project_dir}/summaries/round{current_round}_{short_name}/round_summary.md`
- **Contents**: Objective, experiments run, results tables, key takeaway, files created.

Both files must exist before proceeding to the next phase.

## State Update

After user confirms results AND picks next direction (or confirms manuscript):

**If proceeding to another round (Phase 4):**
- `current_phase`: `4`
- `sub_step`: `null` (normal) or `"refinement"` (if reframing needed — see criteria in CLAUDE.md)
- `current_round`: increment by 1
- `phase_status`: `"not_started"`
- `project_status`: unchanged
- `experiment.status`: `"completed"`
- Populate `results.raw_results_path`, `results.analysis_summary`
- `results.user_confirmed`: `true`
- **Update roadmap:** Move current round to Completed, mark chosen direction as Active
- Append to `phase_history`

**If proceeding to manuscript (Phase 7):**
- `current_phase`: `7`
- `sub_step`: `null`
- `current_round`: unchanged
- `phase_status`: `"not_started"`
- `project_status`: unchanged
- `experiment.status`: `"completed"`
- Populate `results.raw_results_path`, `results.analysis_summary`
- `results.user_confirmed`: `true`
- **Update roadmap:** Move current round to Completed
- Append to `phase_history`

**If returning to Phase 3 (fundamental rethink):**
- `current_phase`: `3`
- `sub_step`: `null`
- `current_round`: `0` (reset — new research plan starts fresh)
- `phase_status`: `"not_started"`
- `project_status`: unchanged
- `experiment.status`: `"completed"`
- Append to `phase_history` with explanation of why rethink was needed
