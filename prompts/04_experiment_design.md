# Phase 4: Experiment Design & Refinement

## Objective
Translate the research plan into a concrete experiment design with estimated resource requirements. User confirmation must precede experiment code and execution; record its scope below.

## Mode
Direct conversation. Present the plan clearly and get explicit user approval.

## Refinement Mode (sub_step: refinement)

When `sub_step` is `"refinement"` in the project's `.research_state.json`, this phase operates in **refinement mode**. This adapts the research plan and experiment design based on results or evidence discovered during prior experiment rounds, preventing "locked-in" research when evidence points to different conclusions or uncovers more important angles than initially planned.

**Refinement is an execution mode of Phase 4, not a skip.** Refinement rounds DO execute Phase 4 and DO require `phase4_experiment_design.md` in the round subfolder (see the summary checklist in `prompts/conventions.md`). Only rounds that route directly to Phase 5 with an identical config may skip Phase 4 and its summary file.

**When `sub_step` is `null`, skip this entire section and go straight to the normal design steps below.**

Before proceeding with normal experiment design, first review: the research question, hypothesis, positioning, and whether the overall framing still makes sense given the accumulated evidence.

### Evidence Review Checklist

Compare the current research plan against what has been discovered:

```
Evidence Review Checklist:
─────────────────────────
[ ] Do preliminary results support the hypothesis?
[ ] Are the chosen metrics appropriate given what we now know?
[ ] Are there confounds or artifacts in the data we didn't anticipate?
[ ] Has a critical subtopic emerged that wasn't in the original plan?
[ ] Is the original research question still well-scoped?
[ ] Do we need additional baselines or comparisons?
```

### Propose Refinements

If adaptation is needed, propose changes structured as:

```
Outline Refinement Proposal
────────────────────────────
TRIGGER: [What evidence prompted this change]
SOURCE: [Specific data/results/paper that led to this]

CHANGES:
  ADD:    [New experiments, analyses, or sections]
  MODIFY: [Adjusted scope, metrics, or methods]
  DEMOTE: [Experiments that proved less important]
  REMOVE: [Experiments no longer relevant]

IMPACT:
  Time estimate change: [+/- hours]
  New dependencies: [if any]
  Risk assessment: [low/medium/high]
```

### Refinement Constraints

- No more than 50% restructuring — if more is needed, the scope was severely mis-scoped and should escalate to the user for a potential return to Phase 3.
- Retain the original research question core — do not drift into a different topic.
- Every new addition must have supporting evidence already in hand.
- Changes must be evidence-driven, not speculative.

### Anti-Patterns

- DO NOT adapt based on speculation or "what would be interesting"
- DO NOT add experiments without supporting evidence
- DO NOT completely abandon the original research question
- DO NOT use this as an excuse to scope-creep indefinitely
- DO adapt when evidence clearly indicates better structure
- DO document rationale for every change
- DO stay within the original topic scope

### After Refinement

Document the adaptation rationale in `{project_dir}/summaries/round{N}_{short_name}/phase4_experiment_design.md`, including what changed and why. Then proceed with the normal experiment design steps below using the refined plan.

## Steps

### 4.1 Environment Assessment

First, assess the current machine's capabilities:

```bash
# GPU info
nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo "No GPU detected"

# CPU info
nproc
cat /proc/cpuinfo | grep "model name" | head -1

# RAM
free -h | grep Mem

# Disk space
df -h . | tail -1

# OS and Python
uname -a
python3 --version 2>/dev/null || python --version 2>/dev/null

# Check for conda/micromamba
which conda 2>/dev/null || which micromamba 2>/dev/null || echo "No conda/micromamba found"
```

Record these findings in `{project_dir}/.research_state.json` under `experiment.hardware_requirements`.

### 4.2 Experiment Matrix

Define every experiment that needs to be run. Structure as a table:

| Exp ID | Description | Dataset | Method | Expected Time | GPU Memory | Notes |
|--------|-------------|---------|--------|--------------|------------|-------|
| E01 | Baseline (no synthetic) | Cityscapes | DeepLabV3+ | 8h | 10GB | Control |
| E02 | + Synthetic (ours) | CS + Synth | DeepLabV3+ | 12h | 10GB | Main result |
| E03 | + Synthetic (naive) | CS + Synth | DeepLabV3+ | 12h | 10GB | Comparison |
| A01 | Ablation: no augment | CS + Synth | DeepLabV3+ | 12h | 10GB | Ablation |
| ... | ... | ... | ... | ... | ... | ... |

Each experiment must be run **N times** (typically 3-5) with different random seeds for statistical validity.

**Manuscript relevance check:** For each experiment in the matrix, answer: "Which table or figure in the manuscript will show this result?" If the answer is unclear, reconsider whether the experiment is necessary. Running experiments that do not appear in any table or figure wastes compute and risks cluttering the paper with results that are later removed.

**One run, one file:** Each experiment configuration produces exactly one canonical result file. If the same experiment needs to be referenced by multiple tables or figures, they all cite the same file — never re-run to get a "second opinion."

### 4.3 Evidence Contract (MANDATORY)

Before implementation, create one machine-readable Evidence Contract for every
experiment that may support a manuscript-facing claim:

`{project_dir}/experiment/configs/evidence_contracts/{evidence_contract_id}.json`

The shared workflow defines only universal fields. Domain-specific definitions
belong in the project-owned contract, not in shared prompts.

```json
{
  "schema_version": 1,
  "evidence_contract_id": "E01_primary_outcome",
  "research_question": "What claim is this experiment intended to test?",
  "unit_of_analysis": "What entity contributes one observation?",
  "population": "What data or cases are in scope?",
  "inputs": ["Inputs available to the procedure"],
  "procedure": ["Ordered transformations and measurements"],
  "comparison_or_control": "The reference condition or null control",
  "data_boundaries": {
    "fit": "Data used to fit or select anything",
    "evaluation": "Data reserved for final evaluation"
  },
  "outcomes": [
    {
      "outcome_id": "primary_outcome",
      "construct": "What is being measured",
      "measurement": "How it is computed",
      "aggregation": "How observations become the reported result",
      "direction": "higher|lower|two_sided|descriptive"
    }
  ],
  "decision_criteria": "Predeclared success, failure, and invalidity rules",
  "claim_scope": ["Claims this evidence may support"]
}
```

Use stable, descriptive snake-case IDs. Compute
`evidence_contract_fingerprint` as SHA-256 over canonical JSON (UTF-8, sorted
keys, stable separators) and record it in every result produced under the
contract. A semantic change to the unit, procedure, outcome, comparison,
aggregation, data boundary, decision criteria, or claim scope requires a new
contract version and fingerprint; never edit a contract in place after results
exist.

Before user confirmation, verify that every experiment matrix row points to at
least one contract and that every primary outcome has predeclared decision
criteria. Exploratory analyses may be declared as such, but must not be
presented later as predeclared confirmatory evidence.

### 4.4 Time Estimation

Calculate total time:
```
total_time = sum(per_experiment_time × num_seeds) + data_download_time + setup_time + buffer
```

Present as:
```
⏱️ Time Estimation
───────────────────
Setup (env + data download): ~X hours
Individual experiments:
  E01 (baseline × 3 seeds): 24h
  E02 (ours × 3 seeds): 36h
  E03 (comparison × 3 seeds): 36h
  A01-A03 (ablations × 3 seeds): 36h each

Total sequential time: ~X hours (~Y days)
With parallelism (if multiple GPUs): ~Z days

Buffer (20% for retries/debugging): +W hours
Estimated total: ~V days
```

### 4.5 Storage Estimation

```
📦 Storage Estimation
─────────────────────
Datasets:
  [Dataset 1]: ~XGB
  [Dataset 2]: ~YGB
  Synthetic data: ~ZGB

Checkpoints (per experiment):
  [N checkpoints × size each] × [num experiments] × [num seeds]

Logs & results: ~XGB

Total estimated storage: ~XGB
Available storage: ~YGB
Status: ✅ Sufficient / ⚠️ Tight / ❌ Insufficient
```

### 4.6 Dependency List

List all required packages and tools:
```
Core:
  - Python 3.10+
  - PyTorch 2.x + CUDA
  - torchvision

Task-specific:
  - [segmentation library, e.g., mmsegmentation]
  - [dataset-specific tools]

Utilities:
  - tensorboard
  - wandb (optional)
  - matplotlib
  - pandas
  - scipy (for statistical tests)
```

### 4.7 Risk Assessment

Identify potential issues:
- Dataset download may fail (large files, authentication required).
- GPU OOM for certain batch sizes → fallback plan.
- Training divergence → learning rate schedules to try.
- Baseline reproduction may not match reported numbers exactly → acceptable tolerance.

### 4.8 Data Integrity Checklist

Critical for paper validity:
- [ ] Training and test sets are strictly separated.
- [ ] No data leakage between synthetic generation and evaluation.
- [ ] Validation set is held out for hyperparameter tuning (not test set).
- [ ] Random seeds are fixed and recorded.
- [ ] Data preprocessing is identical across all experiments.
- [ ] Evaluation protocol matches the standard benchmark protocol.
- [ ] Every manuscript-facing experiment has a versioned Evidence Contract.
- [ ] Contract decision criteria and invalidity conditions are declared before execution.

## Output to User

Present the complete experiment design with all of the above sections.

Ask: **"Here's the detailed experiment plan, including the resource estimate of [X days] on your current hardware. Do you approve setup and execution of this experiment matrix, or setup only?"**

Record setup-only or setup-and-execution approval, the matrix, and resource
limits in `phase4_experiment_design.md`. Apply `prompts/agent_workflow.md`:
setup-only excludes launch; approved execution proceeds after Phase 5's
verification and process-safety gates without another confirmation.

If user has concerns about time/resources, discuss alternatives:
- Reduce number of seeds
- Use a smaller dataset
- Skip certain ablations
- Use mixed precision training to speed up

**Note on iteration**: This phase may be revisited across multiple rounds. Impact takes precedence over speed — loop back here whenever Phase 6 or external feedback reveals a better approach, without worrying about cycle count. There are no deadlines driving this work; never dismiss an improvement just because it requires re-running experiments.

## Round Naming

When the design is confirmed, Phase 4 assigns the round's `short_name` — 1-3 words in snake_case describing the round (e.g., `baseline`, `ablation_depth`) — and atomically persists it as `current_round_short_name` before creating round-specific files. Naming rules are in `prompts/conventions.md` "Round Numbering". (For identical-config rounds that skip Phase 4 entirely, Phase 6 assigns the `short_name` during round planning instead.)

## Phase Summary

After user confirms the experiment design, write:
- **File**: `{project_dir}/summaries/round{current_round}_{short_name}/phase4_experiment_design.md`
- **Contents**: Experiment matrix (all experiments with IDs, datasets, methods, estimated time), Evidence Contract IDs and fingerprints, time and storage estimates, dependency list, risk assessment, data integrity checklist. If in refinement mode, also include: what changed from the previous plan, evidence that triggered refinement, comparison of original vs. refined plan.

Create the round subfolder `round{current_round}_{short_name}/` if it does not exist yet.

This file must exist before proceeding to Phase 5.

## State Update

After user confirms:
- `current_phase`: `5`
- `sub_step`: `null` (refinement complete if applicable)
- `current_round`: unchanged (already set by Phase 3 or Phase 6)
- `current_round_short_name`: the confirmed round `short_name`
- `phase_status`: `"not_started"`
- `project_status`: unchanged
- Populate `experiment.plan`, `experiment.estimated_time_hours`, `experiment.hardware_requirements`
- Append to `phase_history`
