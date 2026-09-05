# Cross-host workflow validation results — 2026-09-05

This is an implementation-validation record, not a research-quality or model-performance benchmark. The release is based on `origin/main` commit `88027a6`; it preserves the existing project layout and state schema.

## Repository validation

- Pre-update release baseline: 192 standard-library tests passed.
- Candidate release: 201 standard-library tests passed, including nine structural/host-parity tests. Script byte compilation and `git diff --check` passed.
- Independent review checked prompt authority, scientific approvals, external-code privacy, terminal status, fallback independence, and verification ordering.
- The existing collector test deliberately emits a fail-on-warnings diagnostic; the suite exits successfully.

## Authenticated Claude comparison

After the user renewed authentication, Claude Code `2.1.261` completed three independent batch invocations per revision using the same fixed 18 scenarios. The baseline was `88027a6`; the candidate was `d5e1140`. Each invocation requested `claude-fable-5-1` with `high` effort. Assistant response events identify `claude-fable-5-1` in all six invocations. Resolved effort is not separately reported.

| Revision | Fixture-specified field matches by repetition |
|----------|-----------------------------------------------|
| Baseline `88027a6` | 15/18, 15/18, 15/18 |
| Candidate `d5e1140` | 18/18, 18/18, 18/18 |

Every baseline repetition unnecessarily required another user decision for archived projects, completed projects, and a completed-run/config mismatch question. The candidate finished those scoped requests without requiring an unrequested follow-on decision.

**Field matches were not full semantic acceptance.** Independent review of all 108 decisions found that candidate repetitions 1–2 and baseline repetition 3 proposed `current_round 0→1` without a supplied round value. Candidate repetition 2 also left an ambiguous user waiver of mandatory independent review; baseline responses proposed related exceptions. No state writes or experiments actually ran.

The follow-up change makes Phase 3 read the persisted round, increment it exactly once, and resume the persisted phase if that approval's transition was already recorded. The shared workflow explicitly disallows offering self-review acceptance as a substitute for mandatory independent review. The original 18 cases remain unchanged; two additional development cases check a Round 7→8 replan and a previously completed transition that must remain at Round 8.

## Follow-up regression probes

The follow-up schedule was fixed before responses: three Claude batches and one Codex batch, each with the expanded 20-case fixture. Candidate inputs were working-tree snapshots on `d5e1140`, identified by per-file hashes. These are in-sample regression checks; the expanded fixture is not the original baseline comparison.

| Host | Fixture-specified field matches by repetition |
|------|-----------------------------------------------|
| Claude, responding model `claude-fable-5-1` | 20/20, 20/20, 20/20 |
| Codex, requested model `gpt-6-astra` | 20/20 in one batch; actual model unreported |

All follow-up responses use the persisted round for the original ambiguous case, advance the supplied Round 7 to 8, preserve Round 8 when the transition already exists, and retain eligible independent review as a prerequisite. These are proposed actions; they do not verify filesystem writes or launch ordering.

Full semantic acceptance remains incomplete. Answers omit the explicit maintenance disclosure that no further commands ran; some delegated-review descriptions omit owned output paths. Some Claude answers perform preliminary manual quality checks before independent logical PASS without claiming the formal gate is complete. One answer describes waiting for an unresolved scientific choice too broadly, without preserving unrelated authorized work. One setup-only answer asks for unrequested later launch approval without launching. The original launch-order fixture is also ambiguous because Phase 5 persists process identity after launch. These omissions and ambiguity are retained in the independent review rather than hidden by the field-match totals.

## Execution identity and limits

Claude's successful streams report empty tools, MCP servers, skills, and plugin lists, with zero tool-call events. Its usage records also include `claude-haiku-4-5-20251001`; the CLI does not identify that auxiliary model's role. The responding assistant model is Fable, but this is not a claim of Fable-only host execution. The six original comparison invocations report about $7.05 in aggregate CLI-estimated cost; this is not a billing statement.

Codex was requested as `gpt-6-astra` with `high` effort. Its JSONL does not report resolved model or effort, so both remain **unknown**. The follow-up completed with zero tool-call events and two preserved startup diagnostics: experimental skill-discovery suppression and intentionally disabled Code Mode. These are not inference failures.

Only allowlisted prompt Markdown and synthetic scenarios were supplied. Evaluator expectations, private research projects, credentials, manuscripts, and source scripts were excluded. Claude used safe mode, explicit prompt loading, disabled tools/settings/MCP/plugins, and no session persistence. Codex used a read-only sandbox with user configuration, host-skill discovery, memory, hooks, plugins, apps, shell, browser, delegation, and other side-effect capabilities disabled. Each CLI still supplies its own base instructions.

Earlier Claude attempts failed authentication before inference and remain archived as setup failures. Earlier Codex exploration included one incompatible output schema, followed by corrected 18-case batches. Prompt and fixture refinements during that exploration make the results development evidence. The successful authenticated Claude comparison includes the final explicit-project routing correction that those earlier Codex probes preceded.

## Remaining acceptance work

- Semantic review must assess prose as well as booleans; matching fields alone cannot close acceptance.
- Use held-out cases before making comparative behavioral claims. Cases within one batch share context; three batch invocations are not 54 independent case trials.
- Exercise real delegation, live user steering, filesystem transitions, process control, and sustained research output in disposable synthetic projects before claiming operational or research-quality parity.
- The local OKF integration has separate framework and GUI tests and is excluded from this pre-OKF release.

The PR remains a draft. These checks do not authorize merging, publishing, or migrating user projects.

## Evidence provenance

Raw inputs, output events, final responses, evaluator notes, fixture snapshots, CLI arguments, and per-file hashes are retained locally under the common Git directory in `task-backups/2026-09-05-cross-host-workflow/probes/`. These are local evidence, not repository deliverables. The public procedure and fixture live in [cross-host-validation.md](cross-host-validation.md) and [scenarios.json](../tests/fixtures/workflow/scenarios.json).

Follow-up candidate hashes (full manifests are retained with each run):

- `CLAUDE.md`: `7784b08af232b5414f7a90bc6f0dc45c4e81358a8a72e9291e18860337776984`
- `prompts/agent_workflow.md`: `76409de8df7785be2ea8c7e2fec0dea6d872ae3088c627544e868999570ae2bb`
- `prompts/03_research_plan.md`: `837401945121952ab55c496d1bf52015059d82c576b70c8dfa2b71440b99b8f1`
- 20-case fixture: `8466c7c3a3502397b320c9e073ad55d2e98240a72cd3078110e489f1c3bc8abc`
