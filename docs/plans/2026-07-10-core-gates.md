# Core Gate Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make Rev2Agent's persisted workflow, experiment provenance, citation gate, and credential setup fail safely under the reproduced audit cases.

**Architecture:** Keep the markdown-driven host architecture, but define explicit persisted and on-disk contracts and enforce them with stdlib Python tests. Prompt invariants cover host routing; runtime validators reject incomplete evidence rather than inferring it.

**Tech Stack:** Markdown protocols, Python 3.10+ standard library, `unittest`, GitHub Actions.

---

### Task 1: Persist and namespace round workflow state

**Files:**
- Create: `tests/test_prompt_invariants.py`
- Modify: `prompts/conventions.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `prompts/01_interview.md`
- Modify: `prompts/03_research_plan.md`
- Modify: `prompts/04_experiment_design.md`
- Modify: `prompts/05_experiment_execution.md`
- Modify: `prompts/06_result_analysis.md`
- Modify: `prompts/08_manuscript_review.md`

**Step 1: Write failing invariant tests**

Add `unittest` cases that assert:

```python
state_contract = read("prompts/conventions.md")
self.assertIn('"current_round_short_name": ""', state_contract)
self.assertIn('"review_reentry"', state_contract)

phase5 = read("prompts/05_experiment_execution.md")
self.assertIn("results/{round_dir}/{exp_id}/COMPLETED", phase5)
self.assertIn("results/{round_dir}/ALL_COMPLETE", phase5)
self.assertNotIn("experiment/ALL_COMPLETE", phase5)

for entrypoint in (read("AGENTS.md"), read("CLAUDE.md")):
    self.assertIn("project_status", entrypoint)
    self.assertIn("do not advance", entrypoint.lower())
```

Also assert that checkpoint instructions require a resolved configuration fingerprint, Phase 8 writes `sub_step: "review_reentry"`, and Phase 6 checks it explicitly.

**Step 2: Verify RED**

Run: `python3 -m unittest tests.test_prompt_invariants -v`

Expected: FAIL because the canonical state lacks the round name and re-entry enum and Phase 5 still uses global markers.

**Step 3: Implement the contract**

- Add top-level `"current_round_short_name": ""` to the state schema and document legacy inference from the unique `summaries/round{N}_*/` directory.
- Extend `sub_step` with `"review_reentry"` for Phase 6 only.
- Define `round_dir = round{current_round}_{current_round_short_name}` and require it before Phase 5 starts.
- Use `experiment/results/{round_dir}/{exp_id}/...`, `experiment/checkpoints/{round_dir}/{exp_id}/...`, and immutable `experiment/logs/{round_dir}/...` paths.
- Put `ALL_COMPLETE` inside the current round's result directory.
- Store the resolved config and `config_fingerprint` in checkpoints; resume only on exact match.
- Make both startup protocols stop on `project_status` of `completed` or `archived`.

**Step 4: Verify GREEN**

Run: `python3 -m unittest tests.test_prompt_invariants -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add AGENTS.md CLAUDE.md prompts tests/test_prompt_invariants.py
git commit -m "fix: persist round workflow identity"
```

### Task 2: Enforce result provenance and isolate seed aggregates

**Files:**
- Modify: `tests/test_collect_results.py`
- Modify: `scripts/collect_results.py`
- Modify: `prompts/05_experiment_execution.md`

**Step 1: Write failing regression tests**

`_meta.seed` is always required. A per-run record uses a nonnegative integer. An already-aggregated record uses `seed: "aggregate"` and provides a nonempty list of nonnegative integers in `resolved_config.contributing_seeds`; a missing or `null` seed is invalid.

Add tests for:

```python
def complete_meta(experiment_id, seed, fingerprint="cfg-v1"):
    return {
        "experiment_id": experiment_id,
        "config_fingerprint": fingerprint,
        "script": "scripts/eval.py",
        "log_file": "logs/eval.log",
        "timestamp": "2026-07-10T00:00:00Z",
        "resolved_config": {"model": experiment_id},
        "round": 1,
        "seed": seed,
    }
```

- E01 and E02 with two seeds each produce two aggregates.
- Duplicate `(round, experiment_id, config_fingerprint, method, group, seed)` records produce a warning and no aggregate for that identity.
- Empty JSON, non-object JSON, `NaN`, invalid round values, incomplete `_meta`, and no-metric objects all produce warnings and no entries.
- Missing or `null` seeds are rejected; aggregate inputs are accepted only with `seed: "aggregate"` and valid `resolved_config.contributing_seeds`.
- Mixed valid and invalid rounds never crash Markdown formatting.

**Step 2: Verify RED**

Run: `python3 -m unittest tests.test_collect_results -v`

Expected: FAIL on cross-experiment aggregation and silent malformed inputs.

**Step 3: Implement strict collection**

- Scan every `*.json` candidate except the collector's own outputs and report non-files/empty files.
- Parse JSON with a `parse_constant` callback that rejects non-RFC values.
- Validate the required `_meta` fields and types; skip invalid files after recording warnings.
- Require `_meta.seed` on every file: a nonnegative integer for per-run input, or `"aggregate"` with nonempty integer `resolved_config.contributing_seeds` for aggregate input.
- Require at least one finite metric.
- Carry `experiment_id` and `config_fingerprint` into entries and aggregate keys.
- Detect duplicate seeded identities and suppress their aggregate while preserving provenance warnings.

**Step 4: Verify GREEN**

Run: `python3 -m unittest tests.test_collect_results -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add scripts/collect_results.py tests/test_collect_results.py prompts/05_experiment_execution.md
git commit -m "fix: enforce experiment result provenance"
```

### Task 3: Make citation verification prove metadata identity

**Files:**
- Modify: `tests/test_verify_citations.py`
- Modify: `scripts/verify_citations_bibtex.py`
- Modify: `prompts/07_manuscript_writing.md`
- Modify: `CLAUDE.md`

**Step 1: Write failing regression tests**

Add tests proving:

```python
result = base_result(
    doi_verified=True,
    issues=["Missing author field"],
)
self.assertEqual(verifier.compute_entry_status(result), verifier.SUSPICIOUS)
```

- `url_verified=True` alone returns `UNVERIFIED`, never a verified status.
- A strict full run with a reachable unrelated URL and missing author fails.
- A DOI response with the correct title/year but wrong author or venue is `SUSPICIOUS`.
- A `.tex` scan read error makes the verifier fail.
- DOI author names normalize in `Given Family` order and Unicode normalization is symmetric.

**Step 2: Verify RED**

Run: `python3 -m unittest tests.test_verify_citations -v`

Expected: FAIL because evidence flags currently override structural errors and DOI-clean entries skip author/venue comparison.

**Step 3: Implement strict identity checks**

- Evaluate structural errors before verification flags.
- Keep URL presence/reachability informational and remove it from passing-status counts.
- Stop automatically requesting arbitrary BibTeX URLs; Crossref/S2/DOI remain the automated identity sources.
- Compare DOI authors and venue using normalized metadata; fix DOI author ordering.
- Persist scan errors and make summary failure independent of strict mode.
- Update reports and prompt claims to describe the actual verification sources.

**Step 4: Verify GREEN**

Run: `python3 -m unittest tests.test_verify_citations -v`

Expected: PASS without `ResourceWarning`s.

**Step 5: Commit**

```bash
git add scripts/verify_citations_bibtex.py tests/test_verify_citations.py prompts/07_manuscript_writing.md CLAUDE.md
git commit -m "fix: require citation metadata agreement"
```

### Task 4: Remove chat-secret collection and gate external code egress

**Files:**
- Modify: `tests/test_prompt_invariants.py`
- Modify: `prompts/00_setup.md`
- Modify: `prompts/05_experiment_execution.md`
- Modify: `AGENTS.md`
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `README_ko.md`
- Modify: `INSTALL.md`

**Step 1: Write failing invariant tests**

Assert that setup says `Do not paste API keys`, uses `api_key_env`, never stores an `api_key` value, and defines `external_code_review` with a default of `false`. Assert Phase 5 uses an external reviewer only when that opt-in is true.

**Step 2: Verify RED**

Run: `python3 -m unittest tests.test_prompt_invariants -v`

Expected: FAIL because Phase 0 currently solicits and stores plaintext secrets.

**Step 3: Implement environment-reference setup**

- Replace key-paste detection with standard provider environment variables and a host-only `skip` path.
- Store only `api_key_env` names in `.rev2agent_config.json`; set file permissions to `0600` where supported even though it is non-secret configuration.
- Add a separate external-code-review opt-in, default false.
- Never print secret values or include them in command arguments.
- Update English/Korean setup documentation and both host entrypoints.

**Step 4: Verify GREEN**

Run: `python3 -m unittest tests.test_prompt_invariants -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add prompts AGENTS.md CLAUDE.md README.md README_ko.md INSTALL.md tests/test_prompt_invariants.py
git commit -m "fix: keep provider credentials out of chat"
```

### Task 5: Full verification and final review

**Files:**
- Modify only if review finds a demonstrated defect.

**Step 1: Run the complete gate**

```bash
python3 -W error::ResourceWarning -m compileall -q scripts tests
python3 -W error::ResourceWarning -m unittest discover tests -v
git diff --check
```

Expected: all tests pass with no warnings and no whitespace errors.

**Step 2: Review prompt consistency**

Search for obsolete global markers, plaintext-key fields, and old `sub_step` enums:

```bash
rg -n 'experiment/ALL_COMPLETE|"api_key"|sub_step.*null.*refinement' AGENTS.md CLAUDE.md prompts README.md README_ko.md INSTALL.md
```

Expected: no obsolete contract remains outside explicit migration/history notes.

**Step 3: Request final code review**

Compare the branch against `main`, resolve all critical or important findings, then rerun Step 1.
