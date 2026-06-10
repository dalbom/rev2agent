# Phase 5: Experiment Execution

## Objective
Set up the environment, download data, write all experiment scripts, and launch training. This phase is designed to be **fully autonomous** — the user should be able to walk away and come back when experiments are done.

## Mode
**Task (subagents)** for parallel setup work, then **direct execution** for launching experiments.

## Code Verification Protocol (MANDATORY)

**Every experiment script MUST pass this 3-step verification before execution.** No exceptions. This protocol was established after a Round 5 incident where train features were matched against val images, producing silently invalid results that wasted hours of GPU time and led to incorrect conclusions.

### Scope

Verification applies to ALL scripts that produce or compute values used in the manuscript — not just scripts under `experiment/scripts/`. This explicitly includes:
- **Figure/visualization generation scripts** (e.g., under `manuscript/figures/`) that train models, compute metrics, or generate numerical results at runtime rather than reading them from result files.
- **Standalone evaluation scripts** that compute metrics independently of the main experiment pipeline.

Scripts that ONLY read pre-computed results from JSON/CSV and render them (pure plotting) are exempt from Step 1 but still require Step 2.

### Step 1: Logical Flow Verification (External Model)

Before running any experiment script, query an external model (configured in `.rev2agent_config.json`) to verify that the code correctly implements the intended experimental protocol. This catches methodology bugs that code review cannot — bugs where the code runs perfectly but tests the wrong thing. If no external model is configured, use a separate host-native reviewer with an explicit "adversarial reviewer" role.

**Show which model is performing the review:**
```
Code Verification — [script_name.py]
Reviewer: gpt-5.4 via OpenRouter  (or "host-native adversarial reviewer" if no external model)
```

**Prompt template:**
```
Review this experiment script for LOGICAL/METHODOLOGY correctness (not code quality).

INTENDED EXPERIMENT:
[Describe what the experiment is supposed to test]

CRITICAL DATA FLOW TO VERIFY:
1. Which data split (train/val/test) is used for what purpose?
2. Do feature-image pairs correspond to the SAME samples?
3. Is the decoder trained on different samples than the query set?
4. Are the evaluation metrics computed on the correct set?
5. Is there any train/test leakage?

CODE:
[Paste the full script]

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

## Subagent Safety Protocol

A background Agent once zombified and repeatedly spawned rogue processes. Local `kill` could not stop the Agent itself, only its child processes. To prevent this:

1. **Kill flag**: When spawning long-running Agents, include this instruction in the Agent's prompt:
   ```
   Before EVERY tool call, check if the file {project_dir}/experiment/.kill_agent exists.
   If it exists, STOP immediately. Do not execute any more commands. Just return "Agent terminated by kill flag."
   ```
   The user can stop any agent instantly with `touch {project_dir}/experiment/.kill_agent`.

   **Kill flag hygiene:** Before launching ANY experiment agent, check whether `{project_dir}/experiment/.kill_agent` already exists. If it does, confirm with the user and delete it first — a stale flag means every new agent immediately self-terminates. See `prompts/conventions.md` "Stale kill flag".

2. **PID recording**: Two PID files are tracked under `{project_dir}/experiment/logs/`:
   - `logs/run_all.pid` — written by the orchestrator launch command (`echo $! > logs/run_all.pid` in the nohup wrapper). Kills the whole `run_all.sh` loop.
   - `logs/current_pid` — written by each individual Python script at startup so the currently-training process can be killed without taking down the orchestrator:
     ```python
     with open(LOGS_DIR / "current_pid", "w") as f:
         f.write(str(os.getpid()))
     ```
   The user can kill either with `kill $(cat logs/run_all.pid)` or `kill $(cat logs/current_pid)`.

3. **Single-agent rule**: Only one experiment-running Agent at a time. Before spawning a new Agent, verify no existing experiment processes are alive via the PID files:
   ```bash
   kill -0 $(cat {project_dir}/experiment/logs/run_all.pid) 2>/dev/null && echo "orchestrator still running"
   kill -0 $(cat {project_dir}/experiment/logs/current_pid) 2>/dev/null && echo "training script still running"
   ```
   If either check reports a live process, do NOT spawn a new experiment agent.

## Experiment Result File Convention

Every experiment script must include a `_meta` field in its output JSON:

```json
{
  "_meta": {
    "script": "scripts/run_gradient_inversion.py",
    "log_file": "logs/gradient_inversion.log",
    "timestamp": "2026-04-05T14:30:00",
    "config": {"d": 512, "n_layers": 2, "seeds": [42, 123, 456]},
    "round": 12
  },
  ... actual results ...
}
```

This enables tracing from any result file back to its generating script, log, and configuration without manual grep.

Additionally, maintain `{project_dir}/experiment/results/INDEX.md` — a table mapping each result file to its round, script, key metric, and date:

```markdown
| File | Round | Script | Key Metric | Date |
|------|-------|--------|------------|------|
| final_2layer_d512.json | 10 | run_final_round.py | Cls 0.749 | 2026-04-03 |
| gradient_inversion.json | 12 | run_gradient_inversion.py | Cosim 0.626 | 2026-04-05 |
```

Update INDEX.md every time a new result file is created.

## Sub-tasks (via Task Subagents)

### Interface Contract (write BEFORE spawning any subagent)

The setup subagents work independently, so they must share a single interface definition or their outputs will not compose. Before spawning Tasks 1-7, the MAIN agent writes `{project_dir}/experiment/configs/interface.md` specifying:

- **Experiment IDs** — the exact IDs from the Phase 4 experiment matrix (E01, E02, A01, ...).
- **CLI argument contract** — the exact command-line interface for `train.py`, `evaluate.py`, and each baseline runner (argument names, types, defaults).
- **Checkpoint path and format** — where checkpoints are saved and what each contains.
- **Result-file paths and `_meta` fields** — the result JSON locations per experiment and the required `_meta` schema (see "Experiment Result File Convention" above).

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

5. Write the result to {project_dir}/experiment/configs/env_setup.log

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
   - Each checkpoint includes: model state, optimizer state, scheduler state, epoch, best metric, random states.
   - On startup, check for existing checkpoints and RESUME automatically.
   - Save "best" checkpoint based on validation metric.
4. Logging:
   - TensorBoard logging: loss curves, learning rate, validation metrics per epoch.
   - CSV logging as backup: {project_dir}/experiment/results/{exp_id}/metrics.csv
   - Console logging with timestamps.
5. Validation:
   - Run validation every N epochs.
   - Compute all target metrics on the validation set.
   - Early stopping if configured.
6. Completion signal:
   - On completion, write a file: {project_dir}/experiment/results/{exp_id}/COMPLETED
   - Include: final metrics, total training time, timestamp.
   - On failure, write: {project_dir}/experiment/results/{exp_id}/FAILED with error traceback.
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
4. Save results to {project_dir}/experiment/results/{exp_id}/eval_results.json
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
2. For each experiment:
   a. Check if already completed (COMPLETED file exists) → skip.
   b. Check if partially done (checkpoint exists) → resume.
   c. If not started → start fresh.
3. After each experiment completes, log the result.
4. After ALL experiments complete, write: {project_dir}/experiment/ALL_COMPLETE
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
   - Command: tensorboard --logdir {project_dir}/experiment/results/ --port 6006
   - Include instructions for SSH port forwarding if remote.

2. Status dashboard (Streamlit or simple script):
   - Write {project_dir}/experiment/scripts/status.py that shows:
     - Which experiments are completed/running/pending.
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

1. **Apply the Code Verification Protocol** (defined at the top of this file) to every newly written script: train.py, evaluate.py, status.py, baseline runners, and any model/utility modules. Steps 1-2 of the protocol (external-model logical review + Simplify) are mandatory before any script runs.
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
  $ mkdir -p logs
  $ nohup bash scripts/run_all.sh > logs/run.log 2>&1 &
  $ echo $! > logs/run_all.pid

To monitor:
  $ bash scripts/start_tensorboard.sh
  $ python scripts/status.py

Estimated total time: [X] hours on [GPU name]
```

4. Ask: **"Everything is set up. Shall I start the experiments now? Once started, you can close this session and come back later — I'll pick up where things left off."**

5. If confirmed, start the experiments:
   ```bash
   cd {project_dir}/experiment
   mkdir -p logs
   nohup bash scripts/run_all.sh > logs/run.log 2>&1 &
   echo $! > logs/run_all.pid
   ```

6. Inform the user:
   ```
   🚀 Experiments started (PID: XXXXX)

   You can safely close this session now.
   When you come back, start a new session in this directory and ask me to continue this project.

   Quick commands while I'm away:
     $ tail -f {project_dir}/experiment/logs/run.log        # watch live output
     $ python {project_dir}/experiment/scripts/status.py    # check status
     $ bash {project_dir}/experiment/scripts/start_tensorboard.sh  # visualize
     $ kill $(cat {project_dir}/experiment/logs/run_all.pid)       # stop orchestrator
     $ kill $(cat {project_dir}/experiment/logs/current_pid)       # stop current script
   ```

## State Update

When experiments are launched:
- `current_phase`: `5`
- `sub_step`: `null` — **always reset when Phase 5 begins**, regardless of whether the round arrived via normal design, refinement, or a Phase 4 skip
- `current_round`: unchanged
- `phase_status`: `"in_progress"`
- `project_status`: unchanged
- `experiment.status`: `"running"`
- `experiment.scripts_ready`: `true`
- Record PID and experiment details in `experiment.active_runs`
- **Update roadmap:** Add the current round to the Active section with objective and expected duration. If `{project_dir}/research_roadmap.md` does not exist yet (Round 1), create it using the skeleton in `prompts/06_result_analysis.md` "Roadmap File Format" before registering the round.
- Append to `phase_history`

## On Experiment Completion

Before transitioning to Phase 6:
1. Set `current_phase` to `6`
2. Set `phase_status` to `"not_started"`
3. Set `experiment.status` to `"completed"`
4. Update `experiment.active_runs` — set status to `"completed"`
5. **Create the round subfolder** if it doesn't exist: `{project_dir}/summaries/round{current_round}_{short_name}/`
6. **Write `phase5_experiment_log.md`** in the round subfolder. Contents: which experiments ran, which seeds, duration, any failures, environment details.
7. **Update `results/INDEX.md`** and verify every new JSON has a `_meta` field — per "Experiment Result File Convention" above.

## Session Resumption Logic

When the user returns and this phase is active:

1. Check if the experiment process is still running. Two PID files may exist (see "Subagent Safety Protocol" above):
   - `logs/run_all.pid` — orchestrator (bash `run_all.sh`)
   - `logs/current_pid` — individual Python script currently training
   ```bash
   for PIDFILE in {project_dir}/experiment/logs/run_all.pid {project_dir}/experiment/logs/current_pid; do
       PID=$(cat "$PIDFILE" 2>/dev/null)
       if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
           echo "$PIDFILE: still running (PID $PID)"
       fi
   done
   ```

2. Check for completion:
   ```bash
   if [ -f {project_dir}/experiment/ALL_COMPLETE ]; then
       echo "All experiments completed!"
   fi
   ```

3. Check for partial completion:
   ```bash
   ls {project_dir}/experiment/results/*/COMPLETED 2>/dev/null | wc -l
   ls {project_dir}/experiment/results/*/FAILED 2>/dev/null | wc -l
   ```

4. Report status and propose next action:
   - All complete → Proceed to Phase 6
   - Some failed → Propose retry or skip
   - Still running → Show progress and estimated time remaining
