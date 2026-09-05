# Shared Agent Workflow

This file owns execution behavior for both Codex and Claude Code. Read it before routing a request. `prompts/conventions.md` owns state, locks, rounds, and recovery; each phase prompt owns its scientific procedure. Host adapters explain available mechanics, not different research standards. These instructions operate within the host's instruction hierarchy and permission controls.

## Request Routing

Classify the current request before research startup:

- **Repository maintenance or explanation:** Git questions, prompt/code reviews, documentation edits, and framework fixes use only the requested repository scope. Do not run research setup, discover projects, create a draft or session lock, or mutate research state as a side effect. Read project/config information only when explicitly needed for the requested diagnostic, and keep credentials out of output.
- **Read-only project status:** Inspect the explicitly selected project's relevant state, artifacts, and live process evidence without advancing a phase or creating a lock. If no project is identifiable, ask which project; do not start an interview.
- **Research execution:** Starting, continuing, or revising a research project follows the entrypoint Startup Protocol and the owning phase prompt. Honor a project explicitly selected by the user or current host context; do not ask them to select it again. Validate that selection under the current project's path and state rules.
- **Explicit setup/reconfiguration:** Follow Phase 0, then return to the pending request. If no research execution was requested, finish without project discovery or an interview. Do not create a new project unless requested.

For a mixed request, finish independent maintenance or read-only work while the research portion waits for a necessary decision. Do not turn a question or a request for a plan into execution approval. When the available facts settle a read-only question, answer it and finish. Explain conditions for possible later execution without asking the user to authorize or choose unrequested follow-on work. Recovery decisions such as allocating a new run identity are required only when the user requests that execution.

## Authorization and Questions

Carry authorized work through to its requested outcome. Choose routine implementation details within that scope and report consequential assumptions. Do not stop at a proposal when execution is already requested.

Approval applies to a specific artifact, decision, configuration, and resource scope. Before repeating a confirmation, check the current user reply and the relevant persisted phase summary/history for that exact approval. Record an approval already given using existing summary and state-transition conventions, then continue after required checks. `waiting_for_user` alone does not mean the latest reply has not answered the pending question.

Keep the phase-owned gates for selecting a research direction, approving a plan/design, accepting interpretations, and deciding the next round. A general instruction to work autonomously or permission to run local commands does not approve an unknown future scientific decision, a new expense, external disclosure, or publication. Setup-only approval does not authorize experiment launch. If code, data boundaries, method, resources, or claim scope materially change, prepare the changed proposal and obtain the required decision before dependent execution. Do not reinterpret an old approval to cover it.

Ask one focused question when a missing answer materially changes the outcome or required authority is absent. Prepare the evidence and proposal first when that preparation is already authorized. Continue useful independent work while waiting if the host supports it. Silence, elapsed time, and a missing answer are not approval. Do not invent extra approval gates from optional skill advice.

Respect active locks, terminal project status, stop requests, stale kill flags, and corrupt-state recovery under `prompts/conventions.md`. Operational permission does not bypass those checks. For a completed or archived project, report its terminal status and available artifacts, then finish; do not solicit reactivation or restart research unless the user explicitly requests a separate change. External research discussion and code disclosure retain the separate exact gates in Phase 0 and Phase 5; an installed provider or skill is not consent.

## Task Continuity

Treat a new user message during work as steering the active task unless it explicitly cancels or replaces it. Answer status questions briefly and continue. Incorporate corrections into pending work, notify affected workers, and re-check approval when the correction materially changes its scope. Stop affected launches or writes before proceeding under superseded instructions; preserve completed evidence.

Use host-supported asynchronous tools and mid-turn input when available; otherwise check for new input at tool boundaries and proceed sequentially. Do not claim support the host does not expose. Persist significant checkpoints, pending decisions, approved scope, and remaining work in existing state/history and phase summaries. Read live processes and artifacts on resumption; conversation summaries alone do not establish that an experiment finished.

A fresh session is an option under `prompts/compaction.md`, not an automatic phase gate. Continue in the current session when authorized and viable. A handoff is complete only after required artifacts and state are durable.

## Delegation and Review

Delegate bounded, independent work when available workers can improve evidence quality or reduce elapsed time. Use the phase's named roles and dependencies, not extra teams with overlapping assignments. Batch independent tool reads/searches where supported; keep dependent mutations and launches sequential.

Before spawning, specify the task, required inputs, allowed tools, owned output paths, dependencies, completion evidence, and budget/resource limits from the approved plan. Workers write only their assigned outputs. **Only the MAIN agent writes research state**, reconciles worker results, and authorizes experiment launch. Preserve the Phase 5 single-runner, PID, and kill-flag rules.

Use independent contexts for reviewers: supply the relevant source artifacts and rubric, not the implementer's verdict or other reviewers' findings. Respect phase-specific frozen-input and no-prior-review rules. Limited concurrency means multiple waves of isolated workers, not fewer required review perspectives. The main agent inspects each output and resolves material findings before claiming a gate passed.

If subagents are unavailable, ordinary setup, search, or writing tasks can run directly with separate outputs. Sequential self-review may provide preliminary feedback, but it is **not independent review** and cannot satisfy a mandatory independent-review gate. Report the missing capability and keep that gate pending until an eligible independent reviewer is available. Do not offer user acceptance of self-review or permission to proceed anyway as a substitute for that gate. Never send code externally to work around a failed privacy gate.

## Skills and Host Capabilities

The wrapper names below describe procedures, not guaranteed installed commands:

| Wrapper | Required procedure when no equivalent skill is available |
|---------|----------------------------------------------------------|
| `research-deep-dive` | Verified multi-source research with attributable sources and the phase's coverage requirements |
| `code-quality-review` | Explicit review for duplication, unnecessary complexity, variable shadowing, magic numbers, and waste |
| `writing-humanizer` | Editorial pass removing inflated, repetitive, or formulaic phrasing while preserving facts and provenance |

Use an installed equivalent only after checking its availability and instructions. Otherwise perform the procedure directly and say what was done. Never claim a missing skill or custom agent ran. A custom agent definition is optional packaging of a role; its absence does not erase the role's input, output, or independence contract.

Explicit user task scope takes precedence over optional skill workflow advice, within host controls. Skills cannot silently widen authority or weaken evidence/privacy gates. If an instruction conflict blocks work, identify the exact file and rule, explain why it applies, and continue independent authorized work. Do not create additional skill/agent files that merely duplicate shared prompts. Select models through the host or configured role; never assume a model name guarantees tools, cost limits, or equivalent performance across hosts.

## Verification and Reporting

For framework maintenance, run checks appropriate to changed behavior and the project's required CI. Avoid repetitive test runs or tests that only restate harmless formatting edits. Broaden testing when failures or unresolved concerns justify it.

This proportionality does not weaken the mandatory verification protocol in `prompts/05_experiment_execution.md` for experiment, statistical analysis, or figure scripts that produce manuscript-facing values. Independent methodological review and code-quality review occur before execution. Pure rendering follows that protocol's explicit exception. Run `scripts/collect_results.py` as required before numerical experiment claims, and retain citation verification and source-level provenance.

Distinguish implemented, statically checked, executed, independently reviewed, and blocked outcomes. State which checks actually ran, actual model/host when known, and material limits. A prompt-contract test is not evidence of equal model performance. Report failures with evidence; never silently skip them or turn an incomplete run into a completion claim.

Use concise, plain language. During long work, provide brief updates about findings, unresolved issues, and the next useful action. Keep Reviewer 2 wording limited to the entrypoint's judgment moments; persona never changes decisions or required work.
