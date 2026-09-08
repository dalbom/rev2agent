# New Session at Phase Boundaries

Follow `prompts/agent_workflow.md` for continuity. Before a handoff, persist
phase outputs, approval scope, decisions, unresolved questions, and next steps
in state, summaries, the roadmap, and experiment artifacts.

## When to Recommend

**Recommend a new session only when ALL of these are true:**
1. The current phase's summary file(s) have been written.
2. `.research_state.json` is updated.
3. `research_roadmap.md` is updated (Phase 5/6 only).
4. No active debugging, in-flight work, or incomplete handoff depends on the
   current conversation.
5. There is observed context pressure or repeated loss of relevant instructions
   or evidence. A long transcript or phase number alone is insufficient.

## How to Recommend

Include an optional recommendation in a status update or scientific
confirmation; it adds no approval gate or stop to authorized work:

> Phase N complete. Summary, state, and roadmap are written.
> [Observed context issue] makes a fresh session useful before Phase N+1.
> To switch, start a fresh session in this repository and say "continue [project_name]". Otherwise I will continue the authorized work here.

The new session follows the Startup Protocol in `prompts/conventions.md` and
resumes the named project's persisted state.

## Never Recommend New Session

Do not recommend mid-phase, during active debugging, after a failed Phase
Transition Checklist, or when the user explicitly wants to preserve context.
