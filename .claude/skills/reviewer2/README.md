# reviewer2

A Claude Code mod. In a session opened at a Rev2Agent checkout's root, after each main-loop answer it asks a small model for Reviewer 2's one-line aside and shows it in a speech bubble above the prompt, beside an avatar the model picks for the line. User-facing notes are in the repository README under "Reviewer 2 bubble".

## How it is loaded

The folder is a skills-directory plugin: Claude Code loads `.claude/skills/<name>/` of the session's primary working directory as `<name>@skills-dir` once the folder is trusted. So the mod runs only for sessions opened at the repository root, and nobody installs it. As a second guard, `hooks/register.ts` serves a session only when its project root has `prompts/agent_workflow.md` and `prompts/conventions.md`.

Mods need Claude Code 2.1.287 or later. Older builds skip the hooks module.

## Behaviour

- `turn.start` keeps the prompt and takes the bubble down. `turn.complete` starts the model call in the background and returns at once. Subagent turns, interruptions, refusals and errors get no aside.
- The model call is `$.model.complete` on the session's own client: the `model` option (sonnet by default), effort `low`, 300 output tokens, 30 s timeout. At most two run at once.
- The reply's first line names an avatar in brackets (`[skeptical]`); the rest is the aside. `SKIP` shows nothing. An unknown id falls back to the manifest's default.
- While the model drafts, the band shows the `thinking` avatar with `…` (terminal: a dim line). Nothing shows while the assistant is working.
- The bubble is saved per session in `$.store`, so a resume or a reload shows it again until the next prompt. The 20 most recent sessions are kept.
- The aside is drawn only. It never enters the conversation.

## Settings and commands

`userConfig` in `.claude-plugin/plugin.json` gives two `/config` rows:

| Option | Default | |
| --- | --- | --- |
| `enabled` | `true` | Draft an aside after each answer |
| `model` | `sonnet` | `sonnet` or `haiku` |

`/reviewer2` (or `/reviewer2 status`) shows the state and the last result. `/reviewer2 on|off` changes the `enabled` row through `$.config.set`, which reloads the module with the new value. `/reviewer2 again` drafts an aside for the last answer once more, even when off.

## Files

| File | What it holds |
| --- | --- |
| `hooks/register.ts` | Event wiring: turns, the bubble, `/reviewer2`, storage |
| `hooks/bubble.ts` | Pure logic: payload, reply parsing, avatar catalog, SVG, storage index |
| `prompts/system.txt` | Reviewer 2's system prompt (the mod appends the reply format and avatar list) |
| `avatars/` | 128 px round PNGs and `manifest.json`, exported by `assets/avatars/slice_avatars.py` |
| `tests/` | `claude plugin test` suites |

## Development

```bash
claude plugin validate .claude/skills/reviewer2
claude plugin test .claude/skills/reviewer2
```

An interactive session watches a skills-directory plugin and reloads the hooks module on save. To redraw or add avatars, generate 3x3 sheets into `assets/avatars/sheets/` with the prompts in `assets/avatars/PROMPTS.md` (the sheets are not in git), update `SHEETS` in `assets/avatars/slice_avatars.py`, and run it; it rewrites `avatars/` here.
