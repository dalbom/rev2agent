# Compaction at Phase Boundaries

Because all phase outputs are persisted to files (`.research_state.json`, `summaries/`, `research_roadmap.md`, experiment results), the conversation history becomes largely disposable at phase boundaries. Recommending `/compact` at these points reduces context pressure for long projects and prevents auto-compaction from firing at an awkward mid-task moment.

## When to Recommend

**Recommend `/compact` before proceeding when ALL of these are true:**
1. The current phase's summary file(s) have been written.
2. `.research_state.json` is updated.
3. `research_roadmap.md` is updated (Phase 5/6 only).
4. The next phase's prompt file has NOT yet been read.
5. This phase accumulated substantial tool results (experiment logs, subagent outputs, literature search results, etc.).

## High-Value Transitions

Almost always recommend at these boundaries:

- **Phase 5 → 6** — experiment execution logs and subagent outputs are typically the largest.
- **Phase 6 → 4 (next round)** — close out the previous round's context.
- **Phase 6 → 7** — analysis details live in `phase6_results.md`.
- **Phase 7 → 8** — section writer outputs captured in `main.tex`.

## Skip for Lightweight Transitions

Skip at 1→2, 3→4, 4→5, 8→7: the conversation is short and the compact cost is not justified.

## How to Recommend

`/compact` is a Claude Code built-in slash command that only the user can trigger — the agent cannot run it directly. At a qualifying transition, fold the recommendation into the existing confirmation prompt:

> Phase N complete. Summary, state, and roadmap are written.
> This phase accumulated large tool results — **recommend running `/compact` before proceeding to Phase N+1.**
> Either run `/compact` and then say "continue", or say "continue" to proceed without compacting.

After compact, the agent re-orients from the state files and then proceeds to read the next phase's prompt.

## Never Recommend Compact

- Mid-phase (in-flight tool calls, partial state)
- When a debugging thread is active (user is investigating an anomaly)
- When the Phase Transition Checklist has failed
- When the user has explicitly said they want to preserve context
