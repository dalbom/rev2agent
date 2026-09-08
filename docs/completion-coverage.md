# Completion coverage — 2026-09-08

The shared workflow now asks both hosts to account for each requested outcome, its supporting evidence, relevant verification, and pending work. At phase handoffs it asks them to confirm required summaries and checkpoints and distinguish preliminary checks from passed gates. This adds **31 whitespace-separated words** once in `prompts/agent_workflow.md`; the two host adapters already load that file.

The earlier [omission investigation](omission-investigation.md) concentrated on additional omissions in the simplified candidate. Shared omissions also warrant attention. Existing requirements demonstrate that the rules were retained; they do not demonstrate consistently complete answers or execution. Conversely, a missing detail in a brief proposed action does not prove that a real operation would omit it.

The intervention follows the emphasis on completing authorized work and proportionate verification in [OpenAI's model guidance](https://developers.openai.com/api/docs/guides/latest-model), retrieved on 2026-09-08. Its effectiveness must be measured separately. It adds no required critic, worker, extra approval, or broad test suite.

## Comparison design

This is a new comparison against the current simplified draft, `19d8f26`, with only the added paragraph differing. It is not a replacement for the earlier released-versus-simplified comparison. Historical responses, scores, and source snapshots remain unchanged.

The decision comparison uses the exact previous 28 scenario inputs and request header, with two repeats per host and variant: eight planned batches and 224 decisions. All cases have been exposed before; the original 20/8 split is only a historical grouping. The requested models remain `gpt-6-astra` and `claude-fable-5-1`, at high effort, using Codex CLI 0.153.4 and Claude Code 2.1.261. Each host's variant order is baseline, candidate, candidate, baseline.

An evaluator amendment was frozen before calls. It separates decisive fields, action correctness, and whole-answer coverage. It accepts supplied evidence attribution and specific owning-protocol references, permits fresh process guards, and distinguishes preliminary quality checks from formal review PASS. It does not require invented output filenames or repeat supplied completed prerequisites. A literal documentation edit still needs proportionate verification. Privacy-migration order is scored where startup context is explicit.

For the previously ambiguous `holdout_06`, the primary expected review-PASS field is now false: the unchanged header requires an explicitly supplied PASS, while the scenario says only that verification was completed. The returned boolean and a sensitivity using the old true expectation are retained separately. This changes no historical score. New results therefore must not be compared numerically with the old 98/112 and 96/112 totals as if the rubric and baseline were unchanged.

Two new operational cases test actual work, separately from proposed-action coverage:

- An approved Phase 3 handoff with a missing earlier summary recoverable from supplied synthetic notes. Inspect summary repair before the atomic transition, persisted round/history, and the report that detailed design remains unstarted.
- Two broken documentation links with only one available destination. Inspect the feasible repair and actual check, preservation of the unresolved limitation, and accurate reporting of both outcomes.

Both cases are planned for each host and variant, eight sessions total, with a 900-second session limit and the existing $8 Claude budget ceiling. They use isolated synthetic workspaces, local tools and optional native workers. No current research projects or private research data are supplied. The operation harness does not add its own completion-reporting reminder. Actual artifacts and ordered tool events are graded separately from final-answer wording.

## Validation status

The repository's 203 Python tests, script compilation, and whitespace checks passed after the paragraph was added. Both hosts passed offline CLI/version and namespace checks. These checks establish neither improved model behavior nor research-quality equivalence.

The four Codex batches completed. A reviewer read all 112 answers against the frozen criteria without the variant mapping, saved all annotations, then the batches were unblinded.

| Codex measure | Current simplified draft | With completion rule |
|---|---:|---:|
| Complete answers, repeat 1 | 25/28 | 27/28 |
| Complete answers, repeat 2 | 25/28 | 26/28 |
| Complete answers, combined | **50/56** | **53/56** |
| Answers matching every expected field | 56/56 | 55/56 |
| Mean prose words per answer | 37.1 | 38.1 |

All 112 outputs had valid schemas and used no tools. Review found coverage omissions rather than explicit action contradictions. Both candidate repeats included the launch-roadmap checkpoint omitted by both baseline repeats; one candidate repeat also included main-agent inspection of the generic reviewer's findings. Both variants still left required-summary handoff coverage unstated in both repeats. One candidate repeat also omitted the main-agent inspection detail. The original 20-case subset scored 34/40 versus 37/40 for completeness; the eight previously held-out cases scored 16/16 in both variants.

The single candidate field mismatch is the declared `holdout_06` ambiguity: it returned true for supplied completed verification while correctly continuing to monitor the existing run. With only that expectation restored to the old true label, the same responses score 54/56 baseline and 55/56 candidate on fields. Neither calculation replaces the semantic result or historical scores. Codex emitted the previously observed disabled-code-mode and experimental-feature startup diagnostics; all four invocations completed successfully. Actual backend model identity was not emitted.

Claude's first baseline invocation failed with HTTP 401 reporting a revoked OAuth access token; it produced no valid decision batch. That attempt is retained. The cause of revocation was not established. After a fresh login, an authentication canary returned `AUTH_OK`, and the comparison resumed with the same frozen inputs. The within-host order is preserved; cross-host lockstep was relaxed for the authentication interruption. Initial delegated reviews also encountered a Codex usage limit, but source/fixture review and Codex answer grading subsequently completed.

Before the Claude replay, an additive authentication amendment removed the interactive credential-file mount. The previous read-only mount could not persist refreshed credentials and isolated the CLI's surrounding lock state. This is a harness limitation, not proof that it caused the revocation. The amended launcher passes only the current access token in memory through the documented `CLAUDE_CODE_OAUTH_TOKEN` environment variable, requires at least two hours of remaining validity, and runs Claude sessions serially. Refresh credentials and personal configuration/history remain outside the namespace. Both Claude variants use this adapter; prompt bytes, models, effort, CLI arguments, and grading remain frozen. The canary confirmed working inference authentication and unchanged credential-file bytes; it does not establish reliable future interactive refresh. See the [official environment-variable reference](https://code.claude.com/docs/en/env-vars).

All four Claude decision batches then completed. The independent reviewer graded all 112 answers without the variant mapping, using the same criteria and interpretations as the Codex review, and saved annotations before unblinding.

| Claude measure | Current simplified draft | With completion rule |
|---|---:|---:|
| Complete answers, repeat 1 | 26/28 | 27/28 |
| Complete answers, repeat 2 | 25/28 | 26/28 |
| Complete answers, combined | **51/56** | **53/56** |
| Answers matching every expected field | 54/56 | 54/56 |
| Mean prose words per answer | 51.8 | 64.1 |

All 112 Claude outputs had valid schemas and used no tools. The answering model was reported as `claude-fable-5-1`; the CLI also reported auxiliary Haiku usage whose role in the answers was not established. Review found coverage omissions and no explicit action contradictions. Both variants omitted a scoped check for the literal documentation-edit scenario in both repeats. The generic-reviewer main-inspection detail was omitted once in each variant. One baseline repeat also omitted post-launch process verification and main inspection of the documentation worker's return. These are proposed-answer omissions, not observed execution failures. The original 20-case subset scored 38/40 versus 39/40 for completeness; the eight previously held-out cases scored 13/16 versus 14/16.

Every Claude field mismatch is the declared `holdout_06` ambiguity. With only that expectation restored to the historical true label, both variants score 56/56 on fields. The primary results remain 54/56. The modest coverage increase came with longer answers; these two repeats do not establish a reliable effect size or general superiority.

All four Codex operational sessions completed. A separate reviewer inspected the ordered tool events, initial/final inventories, protected files, and final reports against the frozen expectations. The reviewer knew fixture design and variant identity; this execution review was not blinded.

| Codex operation | Baseline execution / final coverage | Candidate execution / final coverage |
|---|---|---|
| Missing-summary handoff | PASS / PASS | PASS / PASS |
| Documentation with unavailable guide | PASS / PASS | PASS / PASS |

Both handoff runs restored the missing summary before the visible atomic state transition, preserved all prior history, advanced round 4 to 5 exactly once, and stopped before design. Both documentation runs repaired the available setup link, verified it, and accurately reported the missing recovery guide. The candidate added a missing-guide notice and catalog link; the baseline left the unresolved link and asked for its destination. Both were allowed by the frozen criteria. Neither fabricated the missing guide or created research state. Recovered interpreter/check-command diagnostics remain in the traces; later successful checks supply the verification evidence.

All four Claude operational sessions also completed. The same separate execution reviewer inspected their ordered tool results, artifacts, protected inputs, and final reports against the frozen criteria, with variant identity visible.

| Claude operation | Baseline execution / final coverage | Candidate execution / final coverage |
|---|---|---|
| Missing-summary handoff | PASS / PASS | PASS / PASS |
| Documentation with unavailable guide | PASS / PASS | PASS / PASS |

Both Claude handoff runs reconstructed the missing summary before the observed atomic state write, preserved all six prior history entries and added one completion event, advanced round 4 to 5 once, and left detailed design unstarted. Both documentation runs repaired and checked the setup link while accurately reporting recovery instructions as unavailable. The candidate changed the recovery link to the catalog-declared path and explicitly reported that its target was still missing; the baseline retained the original unresolved link. Neither fabricated recovery content. All four sessions reported successful completion by `claude-fable-5-1` and used no native workers. Protected fixture and runtime-source bytes were preserved.

The execution review retained two minor wording issues: the candidate handoff compressed a specific SOTA-baseline exclusion, and the baseline documentation answer inferred historical nonexistence from current absence. Neither affected the frozen primary outcome grades.

Across both hosts, all eight operational sessions passed execution and final-answer coverage. These executions show that both versions met the requirements in these two cases. They do not demonstrate an execution improvement or resolve every remaining prose omission.

The runtime instruction total is now **25,572 words**, compared with **31,431** in the released baseline used by the original simplification report: an **18.6% reduction**. These are source word counts, not token measurements or measured execution savings.

New raw evidence is retained locally under `.git/task-backups/2026-09-08-completeness/`, including the failed Claude attempt, both freezes, both hosts' replies/traces, blinded annotations, operation reviews, and the authentication amendment. Decision-freeze SHA-256: `6ef0ff4a581ee71055a4cb14a21d199cfd8e199420ce51cba9ebdb617a37b39b`. Operation-freeze SHA-256: `db41f21bebd170123dbd8e67921ccbad006d97ce96b0dbdb9ba3c43cc734dea2`. Authentication-adapter SHA-256: `35dc55b2996ad8a0979d174b2c7620c2779867b44eefcc713842466b59cdb1ae`.

## Evidence limits

Repeated decisions in shared batch context do not provide an end-to-end research-quality evaluation. The two operational fixtures cover completion and handoff behavior, not literature quality, experiment validity, manuscript quality, or long-running research reliability. A retained instruction or a passed structural test is insufficient evidence of those capabilities.
