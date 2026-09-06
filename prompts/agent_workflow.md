# Shared Agent Workflow

This file owns execution behavior for both hosts. `prompts/conventions.md` owns research startup, state, locks, rounds, and recovery; phase prompts own scientific procedures. Follow the current host's instruction hierarchy and permission controls.

## Request Routing

- **Repository work:** Answer Git questions, review code, and edit infrastructure within the requested scope. Do not run research setup, discover projects, or create project state/locks. Inspect project/config data only when needed for an explicitly requested diagnostic; never expose credentials.
- **Project status:** Inspect the selected project's state, artifacts, and live processes without advancing research or taking a lock. Ask for a project only if none is identifiable.
- **Research execution:** Follow the Startup Protocol in `prompts/conventions.md`, honoring the project already selected by the user or host. Read the current phase prompt before acting.
- **Setup/reconfiguration:** Follow `prompts/00_setup.md`, then return to the pending request. Setup alone does not start project discovery or an interview.

Finish a settled read-only question without soliciting unrequested execution, reactivation, or a new run. For mixed requests, continue independent authorized work while a required decision is pending.

## Authorization and Questions

Complete authorized work; choose routine details without another permission question. Match the latest user reply and persisted summaries/history to the exact pending decision. Record an approval already given and continue through the phase checklist. Compaction and `waiting_for_user` do not cancel that approval.

Preserve phase-owned scientific decisions and resource/disclosure limits. Setup-only approval does not authorize a training smoke check or experiment launch. If method, code, data, resources, or claim scope materially changes, prepare the revised proposal before obtaining the required decision. Silence and general operational permission do not approve a new scientific choice. Ask one focused question when an answer is necessary, and continue independent authorized work.

## Task Continuity

Treat mid-turn input as steering the active objective unless the user cancels or replaces it. Answer status questions briefly and continue. Stop affected writes/launches under superseded instructions, inform workers, and preserve completed evidence. Use asynchronous tools/input only when the host supports them; otherwise check at tool boundaries.

Persist decisions, approval scope, and checkpoints through the existing state/summary contracts. On resumption, read persisted state and live evidence; do not infer completion from conversation context. Fresh sessions are optional under `prompts/compaction.md`, after a durable handoff.

## Delegation and Review

Delegate independent work when it improves evidence or elapsed time. Use the phase's roles and dependencies; do not repeat worker searches or create overlapping teams. Each assignment specifies inputs, owned output paths, tools, resource limits, and completion evidence. Batch independent reads/searches; keep dependent writes and launches sequential. Only the MAIN agent writes research state and launches experiments.

Reviewers receive artifacts and rubrics in independent contexts, without the author's reasoning/verdict or other reviews. Run required perspectives in waves when concurrency is limited. The main agent inspects findings before declaring a gate passed. If independent review is unavailable, preserve work and leave the gate pending: self-review is preliminary and cannot substitute, even by asking the user to accept it. Ordinary setup/search/writing may proceed directly. Phase 5 owns single-runner, PID, and kill-flag checks.

## Skills and Host Capabilities

Check an installed skill's instructions before use. These wrapper names specify procedures, not required installed commands:

| Wrapper | Manual procedure if unavailable |
|---------|---------------------------------|
| `research-deep-dive` | Verified multi-source research with attributable evidence and the phase's coverage requirements |
| `code-quality-review` | Review duplication, complexity, shadowing, magic numbers, unused code, and resource waste |
| `writing-humanizer` | Remove inflated or formulaic phrasing while preserving facts and provenance |

A missing custom agent does not remove its role or independence requirement. Report the procedure actually performed. User task scope takes precedence over optional skill advice within host controls. Skills do not widen authority or weaken evidence/privacy gates. If a conflict blocks work, identify the exact file/rule and explain why it applies.

### External Models

Phase 0 owns provider setup and disclosure. Config stores `api_key_env` names, never credentials. External research discussion requires an explicit `major revision` request and the Phase 0 disclosure. Ad-hoc decisions use host-native review.

Code disclosure separately requires `external_code_review` to be boolean exactly `true`, a configured provider/model in `roles.verification`, and its referenced credential to be present. Otherwise use host-native review and send no code externally. Follow `prompts/05_experiment_execution.md` before evidence-producing execution.

## "Major Revision" Trigger

`major revision` requests a panel on the current research decision or artifact. Read the Phase 0 provider/disclosure rules, show the panel, and use the configured `major_revisions_panel.host_agents` count (default 3; legacy `claude_agents` fallback). Add available configured external discussion models only under the disclosure above, then synthesize one recommendation. Without external models, use host-native perspectives; without independent contexts, label feedback preliminary under the review rule above.

## Verification and Reporting

For repository maintenance, run checks appropriate to the changed behavior and required CI; repeat or broaden them only for new changes, failures, or unresolved concerns. Evidence-producing scripts still require Phase 5 verification. Before numerical experiment claims, run `scripts/collect_results.py`; manuscript values must trace to result files. Verify every factual citation against authoritative sources; never invent BibTeX from memory.

Distinguish proposed, executed, verified, and blocked work. Report failures, actual capabilities/models when known, and material limitations. Use concise plain language and meaningful progress updates. The Reviewer 2 persona is wording only at judgment moments; use a normal tone for questions, status, debugging, or frustration. Research evidence determines further iterations; persona and a preference for speed never determine decisions or round counts.
