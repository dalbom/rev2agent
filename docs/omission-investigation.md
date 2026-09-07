# Omission investigation — 2026-09-07

This follow-up audits the four additional candidate omissions reported in the [frozen prompt comparison](prompt-simplification.md), then tests the corresponding actions in synthetic local projects. Historical scores and responses remain intact. The scoring correction is post-hoc. Four Codex sessions completed; Claude execution remains blocked by revoked login credentials. No runtime prompt change is justified by the observed evidence so far.

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

## Execution observations and limits

Scoring uses ordered tool events, worker identities, actor-specific writes, resulting artifacts, and main-agent reads. Final-answer keywords alone earn no execution credit. Launch PID evidence is evaluated at the verified-launch checkpoint; proper cleanup must not fail merely because a PID file is absent from the final snapshot.

The tested Codex v2 traces expose native-worker identity, fork metadata, tool calls/writes by actor, and main-agent artifact reads. **Assignment messages remain encrypted in both parent and child records.** Explicit input/output assignment wording, tool/resource limits, and the absence of author reasoning inside those messages are therefore **NOT_OBSERVABLE**; no decryption is attempted.

For cases 02–04, observed native workers and relevant artifacts can support **PARTIAL — assignment unobservable**, not a complete primary ownership PASS. Visible forbidden writes or direct contradictions can still be FAIL. Missing capability or no relevant work is NOT_EXERCISED. Encryption alone is an instrumentation limit and does not trigger a baseline comparison. Case 01's main-agent checkpoint is independently scoreable.

Claude's first live capability canary failed with HTTP 401 and revoked OAuth credentials, without a model answer. Login restoration is pending user action; this is a preserved setup failure, not a behavioral result. Actual Claude assignment visibility must be verified after authorization works.

The completed candidate runs requested `gpt-6-astra` at high effort through Codex CLI 0.153.4. Each case used one fresh session. Claude CLI 2.1.261 requested `claude-fable-5-1` at high effort for its capability canary; its authentication failure produced no model answer and no case was started. Requested model identifiers are not independent backend attestations.

| Host / case | Primary outcome | Directly observed evidence and limits |
|---|---|---|
| Codex 01 | **PASS for the roadmap/checkpoint endpoint** | After verifying launch, the main agent persisted run identity and created an Active roadmap entry with `round1_demo`, objective, and 120-second duration before reporting. It recorded the first attempt as interrupted, retained its logs, and checkpointed a retry. Cross-call process identity and persistence after the host session closes remain unconfirmed. |
| Codex 02 | **PARTIAL — assignment unobservable** | A native worker created with `fork_turns: none` read the implementation, contract, and input, then returned the correct methodological FAIL. The parent consumed that return and supplied separate unmeasured CPU/memory estimates. No review file was written; whether the native return had an explicit equivalent ownership contract is unobservable. All inputs and state remained unchanged. |
| Codex 03 | **PARTIAL — assignment unobservable** | A native worker in a separate context supplied the correct methodological FAIL using the available generic delegation mechanism. The parent consumed its review. No review file was written; explicit ownership of the returned result cannot be verified. Implementation and state remained unchanged. |
| Codex 04 | **PARTIAL — assignment unobservable** | The helper edited only `docs/quickstart.md` and `docs/troubleshooting.md`, then checked that both link destinations existed. The parent read the repaired files. The A/B decision and research state remained unchanged. Exact assignment bounds remain hidden. |
| Claude 01–04 | **NOT_EXERCISED — authentication blocked** | The live capability canary returned HTTP 401 with revoked OAuth credentials. No behavioral outcome is inferred. |

The review verdicts above are deliberately FAIL because the toy code averages absolute magnitudes instead of signed values; identifying that discrepancy is the expected successful review action. Returned native reviews are observed evidence, not proof that a filesystem artifact or explicit equivalent ownership contract was assigned. The documentation case does not test a live asynchronous input API or rendered pages.

No completed case revealed a confirmed prompt omission or an observable forbidden write. The frozen policy therefore triggered no baseline comparison or candidate repetition: encrypted assignments are an instrumentation limit, and launch persistence remains unestablished under the tested host process handling. The first attempt, recorded as interrupted, and its logs remain part of case 01; it is not replaced by the retry. Native-worker capability setup attempts and the Claude authentication failure are also retained separately from behavioral cases.

This follow-up changes the evaluation documents and dated changelog only. It adds no runtime instructions or agent calls. All 203 release tests and script compilation pass. PR #11 remains a draft: Claude execution and the hidden assignment obligations are unresolved, and these four Codex cases do not establish cross-host equivalence or full research-workflow reliability.

The retained local evidence includes `scoring-audit.md`, `observability.md`, the independently reviewed fixtures and actual review receipts, and `execution-freeze.json`. The historical inventory covers 154 files with SHA-256 `217ef85b2d95b7aab1394632e2830c12b6dfc747716431d338f030e79131900a`; the execution freeze is dated `2026-09-07T20:25:58.199303+00:00`. These identify local evidence, not a public raw-data archive. Known-case synthetic diagnostics cannot establish research quality, general behavioral equivalence, or reduced research-review requirements.
