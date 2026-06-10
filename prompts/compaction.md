# New Session at Phase Boundaries

Because all phase outputs are persisted to files (`.research_state.json`, `summaries/`, `research_roadmap.md`, experiment results), the conversation history is fully reconstructable from disk. Starting a new session at phase boundaries is preferred over carrying forward a large summarized context because:

1. **No information loss** — a new session reads state files directly instead of relying on condensed conversation history.
2. **Lower context load** — a new session only reads the files it needs.
3. **Clean context** — no accumulated noise from previous phases.

## When to Recommend

**Recommend starting a new session before proceeding when ALL of these are true:**
1. The current phase's summary file(s) have been written.
2. `.research_state.json` is updated.
3. `research_roadmap.md` is updated (Phase 5/6 only).
4. The next phase's prompt file has NOT yet been read.
5. This phase accumulated substantial tool results (experiment logs, subagent outputs, literature search results, etc.).

## High-Value Transitions

Almost always recommend at these boundaries:

- **Phase 2 → 3** — a deep literature search accumulates substantial tool results (web searches, parallel agent outputs, credibility scoring); everything needed lives in `phase2_literature.md` and `literature/`.
- **Phase 5 → 6** — experiment execution logs and subagent outputs are typically the largest.
- **Phase 6 → 4 (next round)** — close out the previous round's context.
- **Phase 6 → 7** — analysis details live in `phase6_results.md`.
- **Phase 7 → 8** — section writer outputs captured in `main.tex`.

## Skip for Lightweight Transitions

Skip at 0→1, 1→2, 3→4, 4→5, 8→7: the conversation is short and starting a new session is not justified.

## How to Recommend

At a qualifying transition, fold the recommendation into the existing confirmation prompt:

> Phase N complete. Summary, state, and roadmap are written.
> This phase accumulated large tool results — **recommend starting a new session** before Phase N+1.
> Start a fresh session in this repository and say "continue [project_name]", or say "continue" here to proceed in this session.

The new session will follow the Startup Protocol, detect the project, read `.research_state.json`, and resume at the correct phase.

## Never Recommend New Session

- Mid-phase (in-flight tool calls, partial state)
- When a debugging thread is active (user is investigating an anomaly)
- When the Phase Transition Checklist has failed
- When the user has explicitly said they want to preserve context
