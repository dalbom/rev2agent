# Cross-host workflow validation results — 2026-09-05

This is an implementation-validation record, not a research-quality or model-performance benchmark. The release is based on `origin/main` commit `88027a6`; its changes preserve the existing project layout and state schema.

## Repository validation

- Pre-update release baseline: 192 standard-library tests passed.
- Candidate release: 201 standard-library tests passed, including nine new structural/host-parity tests. Script byte compilation and `git diff --check` passed.
- Independent review checked prompt authority, scientific approvals, external-code privacy, terminal status, fallback independence, and verification ordering. Reported issues were corrected before handoff.
- The existing collector test deliberately emits a fail-on-warnings diagnostic; the suite exits successfully.

## Synthetic host probes

| Cell | Requested model / effort | Outcome |
|------|--------------------------|---------|
| Codex baseline | `gpt-6-astra` / `high` | Two exploratory batches completed; raw responses retained for inspection. |
| Codex final candidate | `gpt-6-astra` / `high` | One batch covering 18 synthetic scenarios completed without tool-call events; every fixture-specified expected field matched. |
| Claude baseline and candidate | `claude-fable-5-1` / `high` | Both failed authentication before inference: saved OAuth session expired and refresh failed. No automatic model or authentication fallback was attempted. |

Codex JSONL did not report the resolved model or resolved effort. These remain **unknown**; the requested model/effort is not proof of execution identity. Claude returned empty model usage. No Fable performance result is available.

The first exploratory batch used different route labels and omitted one field definition, so it cannot receive an exact-schema score. Subsequent probes corrected the output contract. During development, probes exposed unsolicited reactivation and run-allocation questions; the prompts and fixture were refined, then the final candidate was rerun. The final 18 cases are therefore an in-sample regression check, not a held-out evaluation. The cases share a batch and are not independent repetitions. Matching fields does not establish every prose obligation or actual process/state ordering.

No private research projects, configuration credentials, manuscript, or source scripts were supplied. Only explicitly selected prompt Markdown and synthetic scenarios were included; evaluator expectations were withheld. Claude used safe mode and disabled tools. Codex used a read-only sandbox with user configuration, host-skill discovery, memory, hooks, plugins, external apps, shell, browser, delegation, and other side-effect capabilities disabled for the probe; event output contained no tool calls. The CLI host still supplies its own base instructions, so this is not a pure-model comparison.

The final integration review also found a stale no-project fallback in the routing pseudocode. Both entrypoints now validate an explicitly selected project before the empty-list fallback; a new structural regression test covers this correction. The live probes above preceded that final consistency correction.

## Remaining acceptance work

- Renew the local Claude login and rerun the same fixed scenarios on the requested Fable model, recording the actual model if reported.
- Use independent repetitions and held-out scenarios before making comparative behavioral claims.
- Validate actual delegation, mid-turn input, prelaunch state ordering, process control, and sustained research output in disposable synthetic projects before claiming operational or research-quality parity.
- The local OKF integration has separate framework and GUI tests; it is not included in this pre-OKF release branch.

Keep the PR as a draft while the required cross-host evidence remains pending. A prompt-only update does not authorize merging, publishing a release, or migrating user projects.

## Evidence provenance

Raw inputs, output events, final responses, fixture snapshots, CLI arguments, and per-file hashes are retained locally under the repository's common Git directory in `task-backups/2026-09-05-cross-host-workflow/probes/`. They are not repository deliverables. The reproducible public procedure and scenario fixture live in [cross-host-validation.md](cross-host-validation.md) and [scenarios.json](../tests/fixtures/workflow/scenarios.json).

Last executed candidate probe hashes (before the final routing-pseudocode consistency correction; the full set is in the local metadata):

- `AGENTS.md`: `4b5227d539d6fe40bffbd682d28c767ab6b090157e8966ed8973a8d3b04d8c02`
- `prompts/agent_workflow.md`: `00cf43cf5a4e9de2b5bb9edb8765c4d627502d10ce9bcd1a661c84cd531fe3f0`
- `prompts/05_experiment_execution.md`: `aa9343e7e9da5ff41a1a86c3813ac086edaf7ba5c8c44420a186175a68e0971a`
