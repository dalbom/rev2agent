# Phase 5: Experiment Execution

## Objective
Set up the environment, download data, write all experiment scripts, and launch training. This phase is designed to be **fully autonomous** — the user should be able to walk away and come back when experiments are done.

## Mode
**Task (subagents)** for parallel setup work, then **direct execution** for launching experiments.

## Round Identity and Paths (MANDATORY)

Before setup, resume checks, or execution, read `.research_state.json` and require `current_round > 0`. `current_round_short_name` must be nonempty before any execution work. If the `current_round_short_name` key is absent, STOP and run the legacy migration in `prompts/conventions.md`. If the key is present with value `""`, STOP without migration: Phase 4 has not persisted the round name, so return to the owning phase instead of guessing.

After validation, define this value once and pass it to every subagent and script:

```text
round_dir = round{current_round}_{current_round_short_name}
run_dir = {round_dir}/{exp_id}/seed{seed}
```

Create one `run_dir` for every experiment ID and seed. Run artifacts are scoped under `{project_dir}/experiment/results/{run_dir}/`, `{project_dir}/experiment/checkpoints/{run_dir}/`, and `{project_dir}/experiment/logs/{run_dir}/`. Round-level aggregation artifacts remain under the corresponding `{round_dir}`. Never use a marker, checkpoint, PID, or log from another round, experiment ID, or seed.

## Code Verification Protocol (MANDATORY)

**Every experiment script MUST pass this 3-step verification before execution.** No exceptions. This protocol was established after a silent methodology failure where executable code evaluated mismatched evidence and produced incorrect conclusions.

### Scope

Verification applies to ALL scripts that produce or compute values used in the manuscript — not just scripts under `experiment/scripts/`. This explicitly includes:
- **Figure/visualization generation scripts** (e.g., under `manuscript/figures/`) that train models, compute metrics, or generate numerical results at runtime rather than reading them from result files.
- **Standalone evaluation scripts** that compute metrics independently of the main experiment pipeline.

Scripts that ONLY read pre-computed results from JSON/CSV and render them (pure plotting) are exempt from Step 1 but still require Step 2.

### Step 1: Logical Flow Verification

Before running any experiment script, use an independent adversarial reviewer to verify that the code implements the intended experimental protocol. This catches methodology bugs that ordinary code review cannot — bugs where the code runs perfectly but tests the wrong thing.

The mandatory default is a **host-native adversarial reviewer**. Sending unpublished code to an external provider is permitted only when both conditions hold:

1. `.rev2agent_config.json` contains `external_code_review` as the JSON boolean exactly `true`; and
2. `roles.verification` identifies a configured external provider/model whose `api_key_env` names an environment variable that is currently present.

Missing, `false`, string `"true"`, null, numeric, or otherwise invalid `external_code_review` values all mean `false`. A missing environment reference also forces the host-native path. In every fallback case, **Do not send the script, excerpts, diffs, data samples, or prompts containing the code to an external model.** Provider configuration for `major revision` discussions is not code-upload consent.

When the exact opt-in, `roles.verification`, and environment-reference checks all pass, report that configured external provider/model and send only the material needed for this review. Resolve the credential inside the provider-calling process; never print it or put it in a URL, log, or command argument.

**Show which model is performing the review:**
```
Code Verification — [script_name.py]
Reviewer: host-native adversarial reviewer
# Or, only after both privacy checks: [configured external model] via [provider]
```

**Prompt template:**
```
Review this experiment script for LOGICAL/METHODOLOGY correctness (not code quality).

EVIDENCE CONTRACT:
[Provide the exact contract path, evidence_contract_id, fingerprint, and content]

CRITICAL DATA FLOW TO VERIFY:
1. Does the code implement the contract's research question and unit of analysis?
2. Are samples and any labels, targets, or outcomes constructed as declared?
3. Are data used for fit, selection, or calibration separated from final evaluation as declared?
4. Do the ordered transformations and comparisons match the declared procedure?
5. Is each outcome computed and aggregated exactly as declared?
6. Do controls and comparison conditions differ only in their declared factors?
7. Could the code run successfully while measuring a different construct or population?

CODE:
[Provide the script to the selected reviewer. Keep it on-host unless the two
external-code-review checks above both pass.]

Check ONLY for logical errors in the experimental design.
Ignore code quality, style, and efficiency.
Report: PASS (no logical issues) or FAIL (describe the issue).
```

**If FAIL:** Fix the identified issue, re-verify. Do not proceed to Step 2 until PASS. **Maximum 5 attempts.** If still failing after 5 rounds, present the remaining issues to the user and ask for guidance.

### Step 2: Code Quality Review (`code-quality-review` skill)

After logical verification passes, apply the `code-quality-review` skill for code quality: unused imports, duplication, variable shadowing, memory efficiency, magic numbers.

### Step 3: Execution

Only after Steps 1-2 pass:
1. `python -m py_compile <script>` — syntax check
2. Run the experiment
3. Log which splits were used for each purpose in the output

### Automatic Enforcement

**This protocol is NOT optional.** It runs automatically every time an experiment script is written or modified, without waiting for user instruction. Never skip Steps 1-2 even if the code "looks correct." The Round 5 incident proved that correct-looking code can be silently wrong.

## Semantic Naming (MANDATORY)

Every manuscript-facing function, result key, table column, and figure label
must reveal the measurement semantics well enough to distinguish it from other
valid protocols. Include the measured construct and output statistic, plus the
unit of analysis or a material processing path when either changes the meaning.

Do not use bare ambiguous umbrella names such as `evaluate`, `eval_metric`, or
`score` for protocol-specific functions or result keys, and do not reuse a
broad domain label for multiple Evidence Contracts. Different contracts
or analysis protocols must not share one name as if they were the same
measurement. If semantics change, introduce a new descriptive name or explicit
version and update `evidence_contract_id`, `outcome_id`, and
`analysis_protocol_id` together. The logical reviewer must fail a script whose
names conceal a material difference from its contract, even when the numerical
computation itself is correct.

## Subagent Safety Protocol

A background Agent once zombified and repeatedly spawned rogue processes. Local `kill` could not stop the Agent itself, only its child processes. To prevent this:

1. **Kill flag**: When spawning long-running Agents, include this instruction in the Agent's prompt:
   ```
   Before EVERY tool call, check if the file {project_dir}/experiment/.kill_agent exists.
   If it exists, STOP immediately. Do not execute any more commands. Just return "Agent terminated by kill flag."
   ```
   The user can stop any agent instantly with `touch {project_dir}/experiment/.kill_agent`.

   **Kill flag hygiene:** Before launching ANY experiment agent, check whether `{project_dir}/experiment/.kill_agent` already exists. If it does, confirm with the user and delete it first — a stale flag means every new agent immediately self-terminates. See `prompts/conventions.md` "Stale kill flag".

2. **PID recording**: Track the round orchestrator separately from each seed-scoped run:
   - `experiment/logs/{round_dir}/run_all.pid` — written by the orchestrator launch command. Kills the whole `run_all.sh` loop.
   - `experiment/logs/{run_dir}/current_pid` — written by each individual Python script at startup so the exact experiment ID and seed can be identified and killed without taking down the orchestrator:
     ```python
     with open(LOGS_DIR / run_dir / "current_pid", "w") as f:
         f.write(str(os.getpid()))
     ```
   The user can kill either process with the matching PID file. PID files are mutable coordination files; delete them after the recorded process exits.

   **Immutable logs:** execution logs are never overwritten or reused. Write orchestrator output to `experiment/logs/{round_dir}/run_all_{timestamp}.log` and each seed attempt to `experiment/logs/{run_dir}/attempt_{attempt}_{timestamp}.log`. Markers and `_meta.log_file` record the exact immutable log path.

3. **Single-agent rule**: Only one experiment-running Agent at a time. Before spawning a new Agent, verify no existing experiment processes are alive via the PID files:
   ```bash
   for PIDFILE in {project_dir}/experiment/logs/{round_dir}/run_all.pid {project_dir}/experiment/logs/{round_dir}/*/seed*/current_pid; do
       [ -r "$PIDFILE" ] || continue
       if IFS= read -r PID < "$PIDFILE" \
          && [[ "$PID" =~ ^[1-9][0-9]*$ ]] \
          && kill -0 "$PID" 2>/dev/null; then
           echo "$PIDFILE: process still running (PID $PID)"
       fi
   done
   ```
   If either check reports a live process, do NOT spawn a new experiment agent.

## Experiment Result File Convention

Every experiment script must include a `_meta` field in its output JSON:

```json
{
  "_meta": {
    "experiment_id": "E01",
    "evidence_contract": {"...": "exact Phase 4 contract snapshot"},
    "evidence_contract_id": "E01_primary_outcome",
    "evidence_contract_fingerprint": "sha256:...",
    "outcome_id": "primary_outcome",
    "analysis_protocol_id": "primary_analysis_v1",
    "script": "scripts/run_gradient_inversion.py",
    "log_file": "experiment/logs/round12_gradient_inversion/E01/seed42/attempt_1_20260405T143000Z.log",
    "timestamp": "2026-04-05T14:30:00",
    "resolved_config": {"d": 512, "n_layers": 2, "seed": 42},
    "config_fingerprint": "sha256:...",
    "seed": 42,
    "round": 12
  },
  ... actual results ...
}
```

This enables tracing from any result file back to its Evidence Contract,
analysis meaning, generating script, log, and configuration without manual
grep. Embed the exact immutable Phase 4 contract as `evidence_contract`.
`collect_results.py` recomputes its fingerprint and verifies that
`evidence_contract_id` and `outcome_id` match the embedded snapshot.
`evidence_contract_fingerprint` uses the same `sha256:<64 lowercase hex
characters>` wire format as `config_fingerprint`. Reusing one
`evidence_contract_id` with multiple fingerprints is contract drift and stops
the strict collection gate; create a new versioned ID instead.

`_meta.seed` is always required; never omit it or set it to `null`:

- **Per-run result:** use a nonnegative integer seed, including `0` when applicable.
- **Already-aggregated analysis result:** use `"seed": "aggregate"` and include a nonempty list of nonnegative integer seeds as `resolved_config.contributing_seeds`:
  ```json
  {
    "seed": "aggregate",
    "resolved_config": {"contributing_seeds": [42, 123, 456]}
  }
  ```

No other seed representation is valid.

Before Phase 6 makes any numerical claim, run `scripts/collect_results.py` with
`--fail-on-warnings`. The collector validates this schema and rejects the entire
file when metadata is missing or ill-typed, the JSON is empty or malformed, the
top-level value is not an object, or no finite metric exists. `NaN`, infinity,
and other non-finite values are not valid result evidence. Paths are never used
to infer a missing round or seed.

Per-seed statistics are grouped only by
`(round, experiment_id, config_fingerprint, evidence_contract_id, evidence_contract_fingerprint, outcome_id, analysis_protocol_id, method, group)`. An already
aggregated file remains visible as provenance but never participates in seed
aggregation. A duplicate seeded identity exists when two result rows share that
tuple plus the same `seed`; the collector warns and suppresses that aggregate;
do not choose one file or average the duplicate observations. Any such warning
must stop the `--fail-on-warnings` gate until the duplicate provenance is
resolved.

Each aggregated metric requires at least two distinct contributing seeds; a
group having two seeds is not enough when each metric occurs in only one of
them. The aggregate records per-metric seed and file provenance. If computing a
derived statistic overflows or produces a non-finite value, the collector warns
and suppresses that metric (and suppresses the aggregate if no valid metrics
remain). These warnings also stop the `--fail-on-warnings` gate.

Additionally, maintain `{project_dir}/experiment/results/{round_dir}/INDEX.md` — a table mapping each result file to its round, script, key metric, and date:

```markdown
| File | Round | Script | Key Metric | Date |
|------|-------|--------|------------|------|
| final_2layer_d512.json | 10 | run_final_round.py | Cls 0.749 | 2026-04-03 |
| gradient_inversion.json | 12 | run_gradient_inversion.py | Cosim 0.626 | 2026-04-05 |
```

Update INDEX.md every time a new result file is created.

## Checkpoint and Marker Configuration Contract (MANDATORY)

Before launching each experiment, fully resolve defaults, inherited settings, dataset/split versions, and code revision into `resolved_config`. Compute `config_fingerprint` as SHA-256 over canonical JSON (UTF-8, keys sorted, stable separators) of the experiment configuration with only the per-run `seed` removed, and store it in the exact wire format `sha256:<64 lowercase hex characters>`. Store the seed separately. This makes the fingerprint seed-independent for one experiment configuration while keeping seed identity explicit. The collector independently recomputes this digest and rejects mismatches. For an aggregate artifact only, exclude both `seed` and `contributing_seeds` when recomputing the digest: `contributing_seeds` is aggregate provenance, not experiment configuration.

Every checkpoint under `{project_dir}/experiment/checkpoints/{run_dir}/` and every `COMPLETED` or `FAILED` marker under `{project_dir}/experiment/results/{run_dir}/` must be structured data containing `resolved_config`, `config_fingerprint`, seed, timestamp, and exact immutable log path. Each `run_dir` represents exactly one experiment ID and seed; never share a run marker or checkpoint across seeds.

`{project_dir}/experiment/results/{round_dir}/ALL_COMPLETE` is the only round-level completion marker. It records every expected experiment-ID/seed pair, fingerprint, and validated run marker, and is written only after all expected seed-scoped `COMPLETED` markers pass validation.

Resume only when the stored `config_fingerprint` is an exact match for the newly resolved `config_fingerprint` and the checkpoint's recorded seed matches the requested seed. A `COMPLETED` marker may be used to skip a run only under the same checks. On any mismatch, refuse to resume or skip, preserve the old artifact, and report **config drift**; require a new experiment ID/path or explicit user resolution. Never silently overwrite a mismatched checkpoint or marker.

## Sub-tasks (via Task Subagents)

### Interface Contract (write BEFORE spawning any subagent)

The setup subagents work independently, so they must share a single interface definition or their outputs will not compose. Before spawning Tasks 1-7, the MAIN agent writes `{project_dir}/experiment/configs/interface.md` specifying:

- **Experiment IDs** — the exact IDs from the Phase 4 experiment matrix (E01, E02, A01, ...).
- **CLI argument contract** — the exact command-line interface for `train.py`, `evaluate.py`, and each baseline runner (argument names, types, defaults).
- **Checkpoint path and format** — `{project_dir}/experiment/checkpoints/{run_dir}/...`, including experiment ID, seed, `resolved_config`, `config_fingerprint`, training state, timestamp, and immutable log path.
- **Result-file paths and `_meta` fields** — the result JSON locations per experiment and the required `_meta` schema (see "Experiment Result File Convention" above).
- **Evidence Contract interface** — exact contract paths, IDs, fingerprints, outcome IDs, analysis protocol IDs, and semantic names used across scripts and outputs.
- **Resume contract** — exact fingerprint and seed checks from "Checkpoint and Marker Configuration Contract" above.

**Every task prompt below MUST include the contents (or path) of `interface.md`.** Subagents implement against the contract; they do not invent their own conventions.

### Spawn Ordering

Tasks 1-5 and 7 may run in parallel. **Task 6 (run_all.sh) is spawned only AFTER Tasks 3-5 complete**, because it must call the actual CLIs of the scripts those tasks produced — pass the finished scripts' real invocations (not the contract alone) into the Task 6 prompt.

### Task 1: Environment Setup
```
Create a reproducible Python environment:

1. Create a micromamba/conda environment named `research-{project_dir}` (use the `project_dir` value from `.research_state.json` as-is, e.g., `research-keyed_nonlinear_transcription`):
   - If micromamba is available, use it (faster).
   - If only conda is available, use conda.
   - **Each project MUST have its own independent env.** Never install packages into another project's env.
   - If neither, use python venv + pip.

2. Install all dependencies from the experiment plan.

3. Create an `environment.yml` or `requirements.txt` for reproducibility.

4. Verify the installation:
   - `python -c "import torch; print(torch.cuda.is_available())"`
   - Import all key packages.

5. Write the result to the immutable round-scoped log `{project_dir}/experiment/logs/{round_dir}/env_setup_{timestamp}.log`.

IMPORTANT: Pin all package versions for reproducibility.
```

### Task 2: Dataset Download
```
Download all required datasets:

1. For each dataset:
   - Check if it already exists at the expected path.
   - If not, download it.
   - Verify integrity (checksum if available, or file count).
   - Note the exact version/split used.

2. For datasets that require registration (e.g., Cityscapes):
   - Check if credentials or data are already present.
   - If not, inform the user that manual download is needed and provide instructions.
   - Write a placeholder script that the user can run after obtaining credentials.

3. Organize data under {project_dir}/experiment/data/:
   {project_dir}/experiment/data/
   ├── {dataset_1}/
   │   ├── train/
   │   ├── val/
   │   └── test/
   └── {dataset_2}/
       └── ...

4. Create a data manifest file: {project_dir}/experiment/data/manifest.json
   Recording: dataset name, version, path, number of samples per split, download date.

5. Verify train/val/test split integrity — NO overlap between splits.
```

### Task 3: Training Script
```
Write the main training script at {project_dir}/experiment/scripts/train.py:

REQUIREMENTS:
1. Accept all hyperparameters via command-line arguments (argparse) or a config YAML.
2. Deterministic training:
   - Set random seeds for Python, NumPy, PyTorch, CUDA.
   - torch.backends.cudnn.deterministic = True
   - torch.backends.cudnn.benchmark = False
3. Checkpointing:
   - Save checkpoint every N epochs (configurable).
   - Save under `{project_dir}/experiment/checkpoints/{run_dir}/`.
   - Each checkpoint includes: model state, optimizer state, scheduler state, epoch, best metric, random states, `resolved_config`, `config_fingerprint`, seed, timestamp, and immutable log path.
   - On startup, resume only after the exact fingerprint and seed checks in "Checkpoint and Marker Configuration Contract" pass. Refuse mismatched artifacts as config drift.
   - Save "best" checkpoint based on validation metric.
4. Logging:
   - TensorBoard logging: loss curves, learning rate, validation metrics per epoch.
   - CSV logging as backup: {project_dir}/experiment/results/{run_dir}/metrics.csv
   - Console logging with timestamps.
   - Immutable execution log: {project_dir}/experiment/logs/{run_dir}/attempt_{attempt}_{timestamp}.log
5. Validation:
   - Run validation every N epochs.
   - Compute all target metrics on the validation set.
   - Early stopping if configured.
6. Completion signal:
   - On completion, write structured data to: {project_dir}/experiment/results/{run_dir}/COMPLETED
   - Include: final metrics, total training time, timestamp, `resolved_config`, `config_fingerprint`, seed, and immutable log path.
   - On failure, write structured data to: {project_dir}/experiment/results/{run_dir}/FAILED with error traceback and the same configuration/provenance fields.
7. Mixed precision:
   - Support torch.amp if GPU supports it, for speed.
8. Data loading:
   - Use num_workers > 0 for DataLoader.
   - Pin memory if CUDA is available.
```

### Task 4: Evaluation Script
```
Write the evaluation script at {project_dir}/experiment/scripts/evaluate.py:

REQUIREMENTS:
1. Load a trained model checkpoint.
2. Run inference on the test set.
3. Compute all target metrics.
4. Save results to {project_dir}/experiment/results/{run_dir}/eval_results.json
   - Every result JSON MUST include a `_meta` field — see "Experiment Result File Convention" at the top of this prompt for the exact schema.
5. Generate per-sample results if needed for qualitative analysis.
6. Statistical analysis:
   - If multiple seeds, compute mean ± std across seeds.
   - Paired t-test or Wilcoxon signed-rank test between methods.
   - Save statistical test results.
```

### Task 5: Baseline Setup
```
Set up baseline methods for comparison:

1. For each baseline in the experiment plan:
   - If an official GitHub repo exists, clone it.
   - Adapt it to use the same datasets and evaluation protocol.
   - OR if simpler, implement it within the same codebase for fair comparison.
2. Ensure baselines use the SAME:
   - Data preprocessing
   - Data splits
   - Evaluation metrics
   - Hardware (no unfair advantages)
3. Create a run script for each baseline.
```

### Task 6: Run Orchestrator

(Spawn only after Tasks 3-5 complete — see "Spawn Ordering" above.)

```
Write a master run script at {project_dir}/experiment/scripts/run_all.sh:

You are given the ACTUAL CLI invocations of train.py, evaluate.py, and the
baseline runners (written by earlier tasks). Call those exact CLIs — do not
invent argument names.

REQUIREMENTS:
1. Run ALL experiments sequentially (or in parallel if multiple GPUs).
2. For each experiment × seed run, construct its `run_dir`:
   a. Check if `{project_dir}/experiment/results/{run_dir}/COMPLETED` exists and its experiment ID, fingerprint, and seed match exactly → skip.
   b. Check if `{project_dir}/experiment/checkpoints/{run_dir}/` contains a checkpoint with the same exact identity → resume.
   c. If not started → start fresh.
   d. If either artifact exists but does not match → report config drift and refuse to reuse it.
3. After each experiment completes, log the result.
4. Only after every expected experiment × seed `COMPLETED` marker validates, write structured data to: {project_dir}/experiment/results/{round_dir}/ALL_COMPLETE. Include every experiment-ID/seed pair, its `resolved_config`, `config_fingerprint`, completion timestamp, and exact immutable log path.
5. Handle failures gracefully:
   - If an experiment fails, log the error and continue with the next one.
   - Write a summary of which experiments succeeded/failed.

Structure:
  run_all.sh
  ├── E01_seed0, E01_seed1, E01_seed2
  ├── E02_seed0, E02_seed1, E02_seed2
  ├── ...
  └── Final summary
```

### Task 7: Monitoring Setup
```
Set up experiment monitoring:

1. TensorBoard:
   - Write a launch script: {project_dir}/experiment/scripts/start_tensorboard.sh
   - Command: tensorboard --logdir {project_dir}/experiment/results/{round_dir}/ --port 6006
   - Include instructions for SSH port forwarding if remote.

2. Status dashboard (Streamlit or simple script):
   - Write {project_dir}/experiment/scripts/status.py that shows:
     - Which experiment × seed runs in `{round_dir}` are completed/running/pending, based only on seed-scoped `{run_dir}` markers whose experiment IDs, seeds, and fingerprints match the expected configs.
     - Current epoch and metrics for running experiments.
     - Estimated time remaining.
   - Can be run as: python status.py

3. Create a README at {project_dir}/experiment/README.md explaining:
   - How to start experiments: bash scripts/run_all.sh
   - How to monitor: bash scripts/start_tensorboard.sh
   - How to check status: python scripts/status.py
   - How to resume after interruption: just run run_all.sh again
```

## After Subagents Complete

Once all subagents have finished:

1. **Apply the Code Verification Protocol** (defined at the top of this file) to every newly written script: train.py, evaluate.py, status.py, baseline runners, and any model/utility modules. Steps 1-2 of the protocol (independent logical review + code-quality review) are mandatory before any script runs. Step 1 uses a host-native adversarial reviewer unless the explicit external-code-review privacy gate passes.
2. **Dry run** the training script for 1 iteration to catch import/shape errors that static review cannot.
3. **Present** the complete setup to the user:

```
✅ Experiment Setup Complete
─────────────────────────────
Environment: research-{project_dir} (micromamba)
Datasets: [list with sizes]
Experiments: [N] experiments × [M] seeds = [total] runs
Scripts:
  - train.py ✅
  - evaluate.py ✅
  - run_all.sh ✅
  - start_tensorboard.sh ✅
  - status.py ✅

To start experiments:
  $ conda activate research-{project_dir}  # or micromamba
  $ cd {project_dir}/experiment
  $ RUN_TS=$(date -u +%Y%m%dT%H%M%SZ)
  $ mkdir -p logs/{round_dir}
  $ ROUND_DIR={round_dir} nohup bash scripts/run_all.sh > logs/{round_dir}/run_all_${RUN_TS}.log 2>&1 &
  $ echo $! > logs/{round_dir}/run_all.pid

To monitor:
  $ bash scripts/start_tensorboard.sh
  $ python scripts/status.py

Estimated total time: [X] hours on [GPU name]
```

4. Ask: **"Everything is set up. Shall I start the experiments now? Once started, you can close this session and come back later — I'll pick up where things left off."**

5. If confirmed, start the experiments:
   ```bash
   cd {project_dir}/experiment
   RUN_TS=$(date -u +%Y%m%dT%H%M%SZ)
   mkdir -p logs/{round_dir}
   ROUND_DIR={round_dir} nohup bash scripts/run_all.sh > logs/{round_dir}/run_all_${RUN_TS}.log 2>&1 &
   echo $! > logs/{round_dir}/run_all.pid
   ```

6. Inform the user:
   ```
   🚀 Experiments started (PID: XXXXX)

   You can safely close this session now.
   When you come back, start a new session in this directory and ask me to continue this project.

   Quick commands while I'm away:
     $ tail -f {project_dir}/experiment/logs/{round_dir}/run_all_{timestamp}.log  # watch this launch's immutable log
     $ python {project_dir}/experiment/scripts/status.py    # check status
     $ bash {project_dir}/experiment/scripts/start_tensorboard.sh  # visualize
     $ stop_pid() { PIDFILE=$1; if [ -r "$PIDFILE" ] && IFS= read -r PID < "$PIDFILE" && [[ "$PID" =~ ^[1-9][0-9]*$ ]]; then kill "$PID"; else echo "Invalid PID file: $PIDFILE"; fi; }
     $ stop_pid {project_dir}/experiment/logs/{round_dir}/run_all.pid  # stop orchestrator
     $ stop_pid {project_dir}/experiment/logs/{run_dir}/current_pid   # stop the identified experiment/seed run
   ```

## State Update

When experiments are launched:
- `current_phase`: `5`
- `sub_step`: `null` — **always reset when Phase 5 begins**, regardless of whether the round arrived via normal design, refinement, or a Phase 4 skip
- `current_round`: unchanged
- `current_round_short_name`: unchanged and nonempty
- `phase_status`: `"in_progress"`
- `project_status`: unchanged
- `experiment.status`: `"running"`
- `experiment.scripts_ready`: `true`
- Record `run_dir`, the seed-scoped PID path, exact immutable log path, experiment ID, seed, and `config_fingerprint` in `experiment.active_runs`
- **Update roadmap:** Add the current round to the Active section with objective and expected duration. If `{project_dir}/research_roadmap.md` does not exist yet (Round 1), create it using the skeleton in `prompts/06_result_analysis.md` "Roadmap File Format" before registering the round.
- Append to `phase_history`

## On Experiment Completion

Before transitioning to Phase 6:
1. Set `current_phase` to `6`
2. Set `phase_status` to `"not_started"`
3. Set `experiment.status` to `"completed"`
4. Update `experiment.active_runs` — set status to `"completed"`
5. **Create the round subfolder** if it doesn't exist: `{project_dir}/summaries/{round_dir}/`
6. **Write `phase5_experiment_log.md`** in the round subfolder. Contents: which experiments ran, which seeds, duration, any failures, environment details.
7. **Update `experiment/results/{round_dir}/INDEX.md`** and verify every new JSON has a `_meta` field — per "Experiment Result File Convention" above.

## Session Resumption Logic

When the user returns and this phase is active:

1. Check if the orchestrator or any seed-scoped experiment process is still running (see "Subagent Safety Protocol" above):
   - `experiment/logs/{round_dir}/run_all.pid` — orchestrator (bash `run_all.sh`)
   - `experiment/logs/{run_dir}/current_pid` — individual Python script for one experiment ID and seed
   ```bash
   for PIDFILE in {project_dir}/experiment/logs/{round_dir}/run_all.pid {project_dir}/experiment/logs/{round_dir}/*/seed*/current_pid; do
       [ -r "$PIDFILE" ] || continue
       if IFS= read -r PID < "$PIDFILE" \
          && [[ "$PID" =~ ^[1-9][0-9]*$ ]] \
          && kill -0 "$PID" 2>/dev/null; then
           echo "$PIDFILE: still running (PID $PID)"
       fi
   done
   ```

2. Check for completion:
   ```bash
   if [ -f {project_dir}/experiment/results/{round_dir}/ALL_COMPLETE ]; then
       echo "All experiments completed!"
   fi
   ```

   Parse the marker and accept it only if its expected experiment IDs, fingerprints, and seeds exactly match the current round plan. Otherwise report config drift and do not advance.

3. Check for partial completion:
   ```bash
   ls {project_dir}/experiment/results/{round_dir}/*/seed*/COMPLETED 2>/dev/null | wc -l
   ls {project_dir}/experiment/results/{round_dir}/*/seed*/FAILED 2>/dev/null | wc -l
   ```

   Count a marker only after its fingerprint and seed match the expected run. Preserve and report mismatched markers as config drift.

4. Report status and propose next action:
   - All complete → Proceed to Phase 6
   - Some failed → Propose retry or skip
   - Still running → Show progress and estimated time remaining
