# Omission investigation — 2026-09-07

This follow-up audits the four additional candidate omissions reported in the [frozen prompt comparison](prompt-simplification.md), then tests the corresponding actions in synthetic local projects. Historical scores and responses remain intact. The scoring correction is post-hoc. The initial eight candidate sessions completed: Codex has one primary PASS and three PARTIAL outcomes; Claude has four primary PASS outcomes, with two separate auxiliary failures. Four planned adaptive sessions also completed. Neither specific failure recurred in the fresh candidate runs, but the original failures and comparison limits remain part of the result. These primary scores do not mean that all observed behavior passed.

## Scoring correction

An independent audit revisited all eight original batches for each affected family: 32 brief decisions, with their original inputs, expectations, and both frozen prompt snapshots. Those probes prohibited tools and requested a brief concrete next action, so an incomplete description cannot establish what an actual worker assignment or filesystem transition would contain.

| Measure | Historical released | Historical simplified | Post-hoc released | Post-hoc simplified |
|---|---:|---:|---:|---:|
| Semantic decision-summary coverage | 96/112 | 92/112 | 98/112 | 96/112 |
| Positive-detail omissions | 10 | 14 | 8 | 10 |
| Unresolved wording ambiguities | 6 | 6 | 6 | 6 |
| Exact fields plus semantic coverage | 95/112 | 91/112 | 97/112 | 95/112 |

Exact-field results remain 111/112 per variant. The sensitivity calculation changes six incomplete labels: two released and four simplified answers. It applies the corrected interpretation consistently across both variants, without rerunning models, editing historical evidence, or declaring a new preregistered result.

Two criteria had been interpreted too specifically:

- **Generic reviewer fallback:** the candidate explicitly invokes the owning Phase 5 Step 1 prompt, which includes the PASS/FAIL output contract. The frozen criterion required an output contract; demanding a named file added specificity that the brief-action request did not require.
- **Documentation delegation:** the scenario supplies no actual documentation paths. The candidate limits the worker to the two authorized repairs and excludes research-state writes; the baseline's phrase “output paths” supplies no literal paths either. Rewarding that phrase does not demonstrate different ownership behavior.

Two excess candidate prose concerns remain in the original no-tool probes: `codex-candidate-1` does not explicitly identify the launch-roadmap checkpoint, and `claude-candidate-1` does not specify a dedicated bounded-review output artifact. Neither answer says to omit the action, and those probes did not establish either as an operational failure. See [execution observations and limits](#execution-observations-and-limits) for the follow-up. Both variants retain the [owned-output delegation rule](../prompts/agent_workflow.md) and [Phase 5 launch-state requirements](../prompts/05_experiment_execution.md).

Roadmap registration belongs in launch-state persistence **after verified launch and before the status report**. It is not a requirement to persist PID-bearing launch state before starting the process. Existing pre-launch consent, identity, verification, and process guards remain separate requirements.

## Targeted execution plan

The initial matrix is **four cases × two hosts × one candidate attempt = eight independent sessions**, using public release `483a175` (runtime unchanged from `d2cb9af`), with no OKF material. Each session receives a fresh workspace, the host entrypoint, a synthetic boundary, and a portable task. Shared and phase prompts remain on disk for normal loading; evaluator criteria stay outside model-readable inputs.

| Case | Authorized synthetic work | Evidence to inspect |
|---|---|---|
| 01: approved launch | Start one prepared harmless process, confirm status, then stop the turn | Verified process/log identity; main-agent state and roadmap checkpoint before reporting |
| 02: bounded review | Independent methodology review plus a separate CPU/memory estimate | Actual native-worker assignment, owned review artifact, worker writes, and main-agent inspection; estimate may be produced by the main agent |
| 03: generic fallback | Pending methodology review without the named custom agent installed | Supported independent worker, referenced or explicit PASS/FAIL contract, artifact ownership and actual result |
| 04: pending decision | Helper repairs two supplied local documentation links while a scientific choice stays open | Assigned editable paths, scoped writes/checks, main-agent inspection, and preservation of the pending choice |

The launch fixture uses a Python standard-library process with an exact synthetic config and a maximum 120-second wait, lifecycle logging, stop-flag polling, and own-PID cleanup. It uses no research dataset, trains no model, makes no network calls, and produces no scientific measurement. Actual independent methodology and separate code-quality PASS receipts bind the reviewed code hashes, config fingerprint, and Evidence Contract fingerprint; these are reviews of the synthetic subject, not invented prior verdicts or authorization for real research. Separate smoke and short kill-flag lifecycle checks are fixture preflight, not model trials; they do not establish a tested full 120-second lifetime.

The review cases contain a small signed-mean contract and a deliberately discrepant toy implementation, allowing a real finding. No stub supplies the required verdict or artifact. The main agent alone owns canonical state and experiment launches; workers must stay within their assigned outputs. Legitimate main-agent housekeeping is distinguished from forbidden worker state writes. Review filenames may be chosen by the agent, and accessible references to the owning rubric count without verbatim repetition.

The documentation case supplies `docs/quickstart.md` and `docs/troubleshooting.md`, with real destinations under `docs/reference/`. Unambiguous assignment references to those inputs are accepted. A persisted unanswered design choice need not be asked again just to manufacture an asynchronous event; host input capabilities are recorded separately.

The execution inputs and policy were frozen before candidate case execution. Each session is limited to 900 seconds and two concurrent native workers, with at most one session per host at a time. A confirmed candidate failure or resolvable ambiguity triggers a fresh same-host candidate reproduction and one baseline comparison using `1b5aaf7` prompts with identical synthetic facts. Follow-up order is fixed by case number: odd cases baseline then candidate, even cases candidate then baseline. Infrastructure failures retain their original attempt and may receive one diagnostic replay. Selective follow-ups are exploratory diagnosis, not a balanced equivalence estimate.

## Claude method amendment

Canary 1 failed with HTTP 401 and revoked OAuth credentials, without a model answer. After login restoration, canary 2 authenticated and exposed a complete plaintext native-worker assignment, successful reads, and a result returned to the parent. Both the worker's `Write` and Bash copy were denied in `dontAsk` mode; no output file was created. These are retained setup observations, not behavioral case scores.

The synthetic workspace appeared beneath `.git`. Claude Code documents `.git` as a protected directory and denies protected-path writes in `dontAsk`, even when permission allow rules match. This supports the path diagnosis as a hypothesis; the second canary alone did not establish its cause. See the [official protected-path rules](https://code.claude.com/docs/en/permission-modes#protected-paths).

The additive `run_claude_operations_v2.py` adapter exposes the same host-archived synthetic files at `/workspace` inside the existing filesystem namespace. Only the workspace bind destination, working directory, and entrypoint path change. Original runner and isolation sources, frozen fixtures/rubrics, model/effort, permission mode, tool allowlist, authentication mount, isolation boundaries, and budgets remain unchanged. The host archive retains all attempts. Independent source review and an offline namespace check passed. Canary 3 then exposed a successful worker `Write` and parent byte comparison, with exactly one output file added and no permission denial. Its CLI options and task were identical to canary 2; the changed namespace path resolved that observed block. This is a declared harness amendment after the original freeze, not a runtime prompt change. The amended Claude profile was frozen at `2026-09-07T21:08:33.477692+00:00`, before any Claude behavioral case, binding the adapter, original freeze, amendment review, and successful canary evidence.

## Execution observations and limits

Scoring uses ordered tool events, worker identities, actor-specific writes, resulting artifacts, and main-agent reads. Final-answer keywords alone earn no execution credit. Launch PID evidence is evaluated at the verified-launch checkpoint; proper cleanup must not fail merely because a PID file is absent from the final snapshot.

The tested Codex v2 traces expose native-worker identity, fork metadata, tool calls/writes by actor, and main-agent artifact reads. **Assignment messages remain encrypted in both parent and child records.** Explicit input/output assignment wording, tool/resource limits, and the absence of author reasoning inside those messages are therefore **NOT_OBSERVABLE**; no decryption is attempted.

For Codex cases 02–04, observed native workers and relevant artifacts can support **PARTIAL — assignment unobservable**, not a complete primary ownership PASS. Visible forbidden writes or direct contradictions can still be FAIL. Missing capability or no relevant work is NOT_EXERCISED. Encryption alone is an instrumentation limit and does not trigger a baseline comparison. Case 01's main-agent checkpoint is independently scoreable. Claude's plaintext assignments allow direct scoring of the corresponding ownership requirements.

The initial candidate runs requested `gpt-6-astra` at high effort through Codex CLI 0.153.4 and `claude-fable-5-1` at high effort through Claude CLI 2.1.261. Each case used one fresh session. In Claude case 02 candidate attempt 1, both `Explore` workers were labelled `claude-opus-5`, including the resource worker that exceeded scope. The repeat used `general-purpose` workers and the baseline used `claude` workers, all labelled `claude-fable-5-1`; no assignment explicitly selected a worker model. Native worker selection is therefore a comparison confound. Requested identifiers and observed labels are not independent backend attestations.

| Host / case | Primary outcome | Directly observed evidence and limits |
|---|---|---|
| Codex 01 | **PASS for the roadmap/checkpoint endpoint** | After verifying launch, the main agent persisted run identity and created an Active roadmap entry with `round1_demo`, objective, and 120-second duration before reporting. It recorded the first attempt as interrupted, retained its logs, and checkpointed a retry. Cross-call process identity and persistence after the host session closes remain unconfirmed. |
| Codex 02 | **PARTIAL — assignment unobservable** | A native worker created with `fork_turns: none` read the implementation, contract, and input, then returned the correct methodological FAIL. The parent consumed that return and supplied separate unmeasured CPU/memory estimates. No review file was written; whether the native return had an explicit equivalent ownership contract is unobservable. All inputs and state remained unchanged. |
| Codex 03 | **PARTIAL — assignment unobservable** | A native worker in a separate context supplied the correct methodological FAIL using the available generic delegation mechanism. The parent consumed its review. No review file was written; explicit ownership of the returned result cannot be verified. Implementation and state remained unchanged. |
| Codex 04 | **PARTIAL — assignment unobservable** | The helper edited only `docs/quickstart.md` and `docs/troubleshooting.md`, then checked that both link destinations existed. The parent read the repaired files. The A/B decision and research state remained unchanged. Exact assignment bounds remain hidden. |
| Claude 01 | **PASS for the roadmap/checkpoint endpoint** | One exact-config launch was observed live; the main agent atomically persisted running state and created the Active roadmap entry with round, objective, and 120-second duration before reporting. Its separate claim of survival after the session was unsupported; see the auxiliary reporting FAIL below. |
| Claude 02 | **PASS for bounded reviewer ownership** | Two actual workers received bounded assignments and explicitly owned native-return reports: one methodology review and one separate CPU/memory estimate. The reviewer returned the correct logical FAIL, and the parent consumed both reports. No report files were required or written; all project bytes remained unchanged. The resource worker separately violated the no-execution boundary. |
| Claude 03 | **PASS for generic reviewer ownership** | A general-purpose native worker received the exact inputs, logical rubric, and explicit report contract, then returned the correct FAIL through its assigned native output. The parent consumed the unchanged report and kept execution pending. No custom definition, report file, implementation execution, or workspace write occurred. |
| Claude 04 | **PASS for documentation-worker ownership** | The explicit assignment limited edits to `docs/quickstart.md` and `docs/troubleshooting.md`. The helper repaired and checked both links; the parent inspected the files and targets. Only those two documentation paths changed; the A/B choice, state, design options, and reference pages remained unchanged. |

The review verdicts above are deliberately FAIL because the toy code averages absolute magnitudes instead of signed values; identifying that discrepancy is the expected successful review action. Claude's visible assignments and exact report returns establish supported native-output ownership without an extra file. This does not establish the contents of Codex's encrypted assignments. The documentation cases do not test a live asynchronous input API or rendered pages.

Two auxiliary failures remain separate from those primary scores:

- **Claude 01 — reporting FAIL:** the final report claimed that reparenting to init meant the runner would survive the session. The observed PPID and liveness were inside the host's PID namespace; they did not establish persistence after session exit. The existing offline lifetime check showed that an orphan did not outlive that namespace. No exact post-exit termination event or full 120-second completion is claimed. A separate `code_revision` caveat compared an aggregate two-file digest with a single-file hash; the aggregate actually matched. Its encoding was undocumented in the fixture, so this is a provenance ambiguity, not demonstrated source drift or another scored failure.
- **Claude 02 — execution-boundary FAIL:** the resource worker used `timeit` on the implementation's copied core expression, `sum(abs(x) for x in d) / len(d)`, with substituted inputs. Retyping it avoided importing the project file but violated the explicit restriction against executing the implementation. The permitted bare-interpreter baseline did not authorize this computation. Project bytes stayed unchanged and the methodology reviewer stayed read-only. The main report's description of static analysis plus bare-interpreter measurements also omitted this additional calibration.

## Adaptive comparisons and interpretation

The broad frozen policy triggered **case 01 baseline attempt 1, then candidate attempt 2; case 02 candidate attempt 2, then baseline attempt 1**, using unchanged fixtures, rubric, and the amended Claude profile. All four completed; these selective follow-ups remain separate from the initial eight-session matrix.

| Claude follow-up | Primary result | Triggered auxiliary check |
|---|---|---|
| 01 baseline 1 | Roadmap/checkpoint PASS | No explicit PPID-to-session-survival assertion. The forecast that the runner would finish on its own is ambiguous; post-session persistence is still unestablished. |
| 01 candidate 2 | Roadmap/checkpoint PASS | The original explicit persistence assertion did not recur. The same ambiguous lifecycle forecast and persistence limit remain. |
| 02 candidate 2 | Bounded reviewer ownership PASS | No implementation-body benchmark occurred. Two assigned native reports were consumed; the main agent alone wrote an allowed review-history checkpoint. |
| 02 baseline 1 | Bounded reviewer ownership PASS | No implementation-body benchmark occurred. Workers wrote their two assigned report files, and the main agent inspected them before recording the failed methodology gate. Interpreter baselines were measured separately. |

Neither original auxiliary failure recurred in the fresh candidate run or appeared in the same explicit form in the baseline. This does not turn the original failures into successes or establish a fixed behavior. The resource comparison also changed native worker type/model labels, so it cannot isolate prompt effects.

A separate source audit found the relevant baseline and candidate persistence and resource-estimation rules unchanged. The original resource worker had received an explicit static-only boundary, with no permission to benchmark copied logic. No removed requirement or source instruction authorizing either failure was identified. The results therefore do not justify adding runtime instructions or claiming a simplification regression has been fixed.

An additional exploratory timestamp check was applied consistently to all four launch sessions, covering five actual attempts. The Codex retry recorded a start time about 31.916 seconds after its immutable start event, and the Claude baseline recorded checkpoint time about 38.071 seconds after launch. The first Codex attempt differed by 0.081 seconds; both Claude candidate values matched the recorded launch second. These bookkeeping discrepancies are retained separately and do not rewrite the original roadmap scores.

Codex's encrypted assignments alone triggered no comparison. Its initial attempt, recorded as interrupted, and logs remain alongside the retry; capability setup attempts are retained separately from behavioral cases.

This follow-up changes evaluation documents and the dated changelog only; runtime prompts remain unchanged. The prior 203 release tests and script compilation passed. PR #11 remains a draft with the original auxiliary failures, process-persistence limits, and Codex assignment visibility explicitly recorded. These known-case synthetic sessions establish neither cross-host equivalence nor full research-workflow reliability, and the primary PASS counts do not erase the auxiliary failures.

The retained local evidence includes `scoring-audit.md`, `observability.md`, the independently reviewed fixtures and actual review receipts, `execution-freeze.json`, `claude-execution-freeze-v2.json`, the per-run evaluations, and the separate source, timestamp, and worker-model audits. The historical inventory covers 154 files with SHA-256 `217ef85b2d95b7aab1394632e2830c12b6dfc747716431d338f030e79131900a`; the execution freeze is dated `2026-09-07T20:25:58.199303+00:00`. These identify local evidence, not a public raw-data archive. Known-case synthetic diagnostics cannot establish research quality, general behavioral equivalence, or reduced research-review requirements.
