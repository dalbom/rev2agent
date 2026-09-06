# Prompt simplification — 2026-09-07

This follow-up replaces overlapping instructions from PR #10 with shared ownership. It preserves scientific procedures and required reviewer counts. Source reduction is measured separately from host behavior; a smaller prompt is not proof of equivalent research quality or fewer runtime agent calls.

## Scope and instruction size

Baseline: released `main` at `1b5aaf7`. Candidate runtime snapshot: `d2cb9af`. Counts are whitespace-separated words, not tokenizer estimates. Both revisions include the same required sources in each comparison. Tests and documentation are excluded from runtime counts.

| Loaded sources | Baseline | Candidate | Reduction |
|----------------|---------:|----------:|----------:|
| Codex entrypoint + shared workflow | 4,053 | 1,024 | 74.7% |
| Claude entrypoint + shared workflow | 4,068 | 1,038 | 74.5% |
| Codex research startup, also including conventions | 5,300 | 2,661 | 49.8% |
| Claude research startup, also including conventions | 5,315 | 2,675 | 49.7% |
| All unique runtime Markdown files | 31,431 | 25,541 | 18.7% |

The last row includes both entrypoints and every Markdown file under `prompts/`, including phase files read later. Counting conventions in the research-startup rows prevents relocation from appearing as a saving. The unique-document total is an inventory measure, not a single request's loaded context.

The adapters load the shared workflow first; research execution then loads conventions and its owning phase prompt. Mandatory scientific protocols, privacy and state schemas remain with their existing owners. All 48 fenced scientific templates/examples across the seven edited phase/compaction files are byte-identical to the baseline. Four literature roles, five manuscript reviewers, and existing review gates remain required; this change does not claim reduced reviewer counts.

## Validation

- 203 release tests passed, including budget checks that fail on the previous release. Existing invariant tests now follow the actual shared owner through each adapter.
- Independent source review found no material loss of startup, state, approval, privacy, persona, or scientific review requirements.
- All eight declared host-probe batches completed, with zero tool calls. Frozen inputs and expectations were not changed after responses arrived.

The host trial compares both revisions using the original 20 regression cases and eight independently prepared cases withheld from the implementer until the candidate was frozen. It declares two invocations per host and revision before execution, with identical source selection and output contracts. Expectations stay outside model inputs. Only public prompt snapshots and synthetic case inputs are supplied; tools and personal context discovery are disabled using the established CLI procedure.

| Host | Version | Exact fields, repeat 1 / 2 | Regression cases | Held-out cases |
|------|---------|--------------------------:|-----------------:|---------------:|
| Codex | Released | 27/28 / 28/28 | 40/40 | 15/16 |
| Codex | Simplified | 28/28 / 27/28 | 40/40 | 15/16 |
| Claude | Released | 28/28 / 28/28 | 40/40 | 16/16 |
| Claude | Simplified | 28/28 / 28/28 | 40/40 | 16/16 |

Both Codex mismatches concern the same ambiguous fixture, `holdout_06`: it supplies "completed independent ... verification," while the output contract requires an explicit PASS before claiming review passed. Each mismatching response correctly continues monitoring the existing approved runner and refuses to infer that verdict. The original expected value remains unchanged, and these strict mismatches are retained in the table.

Independent review of all 224 written answers found lower complete procedural coverage in the candidate: 92/112 versus 96/112. A response is complete only when it states or clearly entails every required action and states no prohibited action; omissions and unresolved wording are counted separately from field matches.

| Host | Version | Complete procedural coverage | Detail omissions | Ambiguous wording |
|------|---------|----------------------------:|-----------------:|------------------:|
| Codex | Released | 52/56 | 4 | 0 |
| Codex | Simplified | 51/56 | 5 | 0 |
| Claude | Released | 44/56 | 6 | 6 |
| Claude | Simplified | 41/56 | 9 | 6 |

The four additional candidate omissions concern roadmap registration and output artifacts/paths for bounded review, custom-review fallback, and asynchronous documentation work. Combining complete procedural coverage with exact fields gives 95/112 released versus 91/112 simplified. The review found no explicit unauthorized launch, external-code disclosure, state takeover, round replay/reset, or self-review presented as independent PASS. Repeated ambiguities concern preliminary quality checks, config normalization, and fresh PID/kill-flag checks. These are gaps in constrained answers; they establish neither an operational regression nor behavioral equivalence. The candidate remains a draft, with this tradeoff recorded for release review.

| Host | Reported response input tokens, released repeats | Simplified repeats | Mean reduction |
|------|---------------------------------------:|-------------------:|---------------:|
| Codex | 36,403 / 36,403 | 32,096 / 32,096 | 11.8% |
| Claude | 45,851 / 45,810 | 38,899 / 38,858 | 15.2% |

These counts include host context and synthetic cases. Codex's reported input count already includes cached input; Claude's answering-model total sums uncached, cache-read, and cache-creation input. Claude separately reported 4,267 auxiliary Haiku input tokens per invocation: including those gives 50,118 / 50,077 → 43,166 / 43,125, a 13.9% reduction across reported models. Compare revisions within each host: the two CLIs have different context and injection mechanics. The selected source union contained 14,136 → 11,223 words for Codex and 14,151 → 11,237 for Claude; it includes only the phases needed by these cases, unlike the full inventory above.

CLI versions were Codex 0.153.4 and Claude Code 2.1.261. Requests selected `gpt-6-astra` and `claude-fable-5-1`, both at `high` effort. Claude reported `claude-fable-5-1` for the answering model; Codex did not report the actual model identity. Claude also reported auxiliary Haiku usage with no established role in the answers. Codex emitted two preserved startup diagnostics about experimental skill-discovery disabling and disabled code-mode hosting. All batches exited successfully; no alternate model, retry, or failed-run replacement was used. The two repeats ran in balanced order: released, simplified, simplified, released, with one process per host in each wave.

Case-freeze SHA-256: `5ba9194b65e122c0bb68264fa633e27dec5f411bcc6bec12e9700999906ff5d6`. Prompt-freeze SHA-256: `b3024102e3b785163b5f9e9d3e8a4f38b126b2eba14a99e82b1596c4f5d4ef88`. These identify the retained local evidence manifests. The [eight additional cases](../tests/fixtures/workflow/simplification-heldout.json) are now public regression fixtures; their held-out status applies only to this frozen comparison.

## Evidence limits

Decision probes describe intended actions. They do not execute delegation, filesystem transitions, live steering, or experiments. The supplied phase files cover setup, planning, design, and execution; literature, analysis, writing, and manuscript-review changes received source-contract review rather than live host evaluation. Judge expected fields and prose separately; do not infer actual call-count or research-quality improvements from static contracts or disabled-tool runs. Cases share batch context, so invocation repetitions are the independent units. Two batches per condition do not establish statistical equivalence. Historical PR #10 results remain in [the earlier record](cross-host-validation-results.md); the [general procedure](cross-host-validation.md) describes interpretation and operational follow-up.
