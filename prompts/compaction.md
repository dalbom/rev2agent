# New Session at Phase Boundaries

Persist phase outputs in `.research_state.json`, summaries, the roadmap, and
experiment artifacts so a new session can reconstruct the work. Summaries must
also preserve approval scope, decisions, unresolved questions, and next steps;
files do not automatically capture everything from a conversation. Continue
authorized work in the current session by default under
`prompts/agent_workflow.md`.

## When to Recommend

**Recommend a new session only when ALL of these are true:**
1. The current phase's summary file(s) have been written.
2. `.research_state.json` is updated.
3. `research_roadmap.md` is updated (Phase 5/6 only).
4. No active debugging, in-flight work, or incomplete handoff depends on the
   current conversation.
5. There is observed context pressure or repeated loss of relevant instructions
   or evidence. A long transcript or phase number alone is insufficient.

## High-Value Transitions

These boundaries can be useful if the conditions above actually hold:

- **Phase 2 → 3** — a deep literature search accumulates substantial tool results (web searches, parallel agent outputs, credibility scoring); everything needed lives in `phase2_literature.md` and `literature/`.
- **Phase 5 → 6** — experiment execution logs and subagent outputs are typically the largest.
- **Phase 6 → 4 (next round)** — close out the previous round's context.
- **Phase 6 → 7** — analysis details live in `phase6_results.md`.
- **Phase 7 → 8** — section writer outputs captured in `main.tex`.

## Skip for Lightweight Transitions

Usually skip at 0→1, 1→2, 3→4, 4→5, 8→7. Assess the actual context rather than
assuming a transition is heavy or lightweight from its number.

## How to Recommend

At a qualifying transition, include an optional recommendation in the status
update or an already-required scientific confirmation. It is not a new approval
gate and does not stop work that is already authorized:

> Phase N complete. Summary, state, and roadmap are written.
> [Observed context issue] makes a fresh session useful before Phase N+1.
> To switch, start a fresh session in this repository and say "continue [project_name]". Otherwise I will continue the authorized work here.

The new session will follow the Startup Protocol, detect the project, read `.research_state.json`, and resume at the correct phase.

## Never Recommend New Session

- Mid-phase (in-flight tool calls, partial state)
- When a debugging thread is active (user is investigating an anomaly)
- When the Phase Transition Checklist has failed
- When the user has explicitly said they want to preserve context
