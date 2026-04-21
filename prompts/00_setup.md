# Phase 0: Setup

## Objective
Configure Rev2Agent for the user's environment. This phase runs **once** on first launch and is skipped on subsequent sessions.

## Mode
Direct conversation with the user.

## When This Phase Runs
- On first launch, when `.rev2agent_config.json` does not exist at the repository root.
- If the user explicitly requests reconfiguration (e.g., "reconfigure", "update setup").

## Design Principle

**Make setup as effortless as possible.** The user should never have to look up API base URLs, environment variable naming conventions, or model IDs. If they paste a key, we figure out the rest. If they type a sentence, we parse it.

## Steps

### 0.1 Welcome

```
Welcome to Rev2Agent
════════════════════

Reviewer 2 is now your agent.

Rev2Agent is an autonomous research assistant that takes a vague 
research idea and iterates through literature search, experiment 
design, execution, analysis, and manuscript writing.

Let me set up a few things first. This only takes a minute.
```

### 0.2 External API Keys

Present one simple question:

```
External LLM Access (optional)
──────────────────────────────
Rev2Agent works fine on its own, but it can also consult other AI 
models (GPT, Gemini, etc.) for independent second opinions.

If you have any API keys, just paste them below — I'll figure out 
which provider they belong to. You can paste multiple keys at once.

If you don't have any, just type "skip".
```

**Key auto-detection:** When the user pastes a key (or multiple keys in any format), identify the provider by prefix:

| Key Prefix | Provider | API Base |
|---|---|---|
| `sk-or-` | OpenRouter | `https://openrouter.ai/api/v1/chat/completions` |
| `sk-` (not `sk-or-`) | OpenAI | `https://api.openai.com/v1/chat/completions` |
| `AIzaSy` | Google AI Studio | `https://generativelanguage.googleapis.com/v1beta` |
| `xai-` | xAI (Grok) | `https://api.x.ai/v1/chat/completions` |
| `sk-ant-` | Anthropic | Host-dependent |
| Unknown | Ask the user which provider | — |

The flagship model for each provider is selected automatically in Step 0.3 (not hardcoded here).

**Host-provider note:** If the pasted key belongs to the same provider as the current host agent, ask whether the user wants to keep it for explicit external API calls or skip it as redundant. Do not assume a provider is always redundant across hosts.

**Handling natural language input:** The user might type any of these:
- `sk-or-v1-abc123` (just the key)
- `OpenRouter: sk-or-v1-abc123` (labeled)
- `Google API Key - AIzaSyABC123` (natural language)
- `here are my keys: sk-or-v1-abc123 and AIzaSyABC123` (multiple at once)
- `I have OpenRouter and Gemini` (no keys yet — ask them to paste)

Parse whatever format they use. Extract keys, auto-detect providers, confirm with user.

**After detecting each key:**
1. Test connectivity with a minimal API call.
2. If test succeeds: `✅ [Provider] connected — [model] available`
3. If test fails: `❌ [Provider] key didn't work. Check the key and try again, or skip.`
4. Store the key in `.rev2agent_config.json` (the config file is gitignored).

**If the user says "skip":** Note that all discussions will use host-native review agents only. This is perfectly fine — move on.

### 0.3 Model Selection (automatic — do NOT ask the user)

For each configured provider, select the **flagship-tier** model automatically. Do not ask the user which model to use.

#### What is "flagship tier"?

Each major provider has a model lineup. Flagship tier is the **primary high-capability model** — not the cheapest, not the most expensive. Concretely:

| Tier | Characteristics | Examples (as of 2026, will change) |
|---|---|---|
| Flagship | Provider's main high-capability model. Balanced cost/performance. | Claude Opus, GPT-5.4, Gemini Pro, Grok-3 |
| Budget | Smaller/faster/cheaper variants | Claude Haiku, GPT-4.1-mini, Gemini Flash |
| Premium | Reasoning-heavy or extended-thinking variants, significantly more expensive | o3-pro, Claude Opus with extended thinking at max budget |

**Select flagship tier. Exclude budget and premium.**

#### How to identify the flagship model

Apply this filter pipeline to all available models, regardless of provider:

```
Step 1: List all models
  - If the provider supports a model listing API (e.g., OpenRouter GET /api/v1/models),
    fetch the full list with pricing.
  - If not (e.g., Google AI Studio), check the provider's documentation or test
    known model names.

Step 2: Exclude by name pattern
  Remove any model whose ID contains these substrings (case-insensitive):
    mini, nano, flash, lite, fast, free, oss, audio, image, embed

Step 3: Exclude by pricing
  Remove models outside the flagship price band:
    - Input cost < $1/M tokens → budget tier, exclude
    - Input cost > $10/M tokens → premium tier, exclude
  If pricing is unavailable, keep the model and verify in Step 5.

Step 4: Pick the latest version per provider family
  Group remaining models by provider family (openai, google, anthropic, x-ai, etc.).
  Within each family, pick the model with the highest version number.
  Ignore date-stamped variants (e.g., -2024-08-06) and preview suffixes —
  treat "preview" as equivalent to the base model if no stable version exists.

Step 5: Sanity check
  The final selection should have at most one model per provider family.
  Each should cost roughly $1-10/M input tokens.
  If something looks off (e.g., a model slipped through that's clearly budget),
  drop it and pick the next best.
```

#### Role assignment

- **Verification** (experiment code review): Pick one external flagship model from a provider other than the current host provider when possible. Independent review from a different provider is more valuable than same-provider review. If multiple such flagships exist, pick any one.
- **Discussion** ("major revision" panel): Include ALL selected flagship models across providers for maximum diversity, plus host-native review agents. One model per provider, no duplicates.
- **Host-native review agents** are always included in discussion (default 3). They are not selected through this pipeline — they come from the current host agent environment.

#### Examples

Assuming the filter pipeline selects: `openai/gpt-5.4`, `google/gemini-3.1-pro-preview`, `x-ai/grok-4`:

```
verification: openai/gpt-5.4 (external)
discussion:   3x host-native review agents + openai/gpt-5.4 + google/gemini-3.1-pro-preview + x-ai/grok-4
```

One external model only:
```
verification: openai/gpt-5.4
discussion:   3x host-native review agents + openai/gpt-5.4
```

No external models:
```
verification: host-native reviewer (with adversarial prompt)
discussion:   3x host-native review agents only
```

#### Show result, don't ask

Display the selected models and role assignments in the environment summary. If the user disagrees, they can override. Do not proactively ask.

### 0.4 LaTeX Check (silent)

Run automatically without asking:

```bash
which tectonic 2>/dev/null || ([ -f ./tectonic ] && echo "found") || echo "not found"
```

Only mention the result in the summary. Don't ask a question about it.

### 0.5 Environment Summary

```
Rev2Agent — Ready
═══════════════════

External models:
  ✅ OpenRouter — gpt-5.4 (flagship)
  ✅ Google AI Studio — gemini-3.1-pro-preview (flagship)

Roles:
  Verification: gpt-5.4 (external)
  Discussion:   3 host-native review agents + gpt-5.4 + gemini-3.1-pro-preview

LaTeX: ✅ tectonic found  /  ⚠️ Not installed yet (needed for Phase 7)
       Install later: curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh

Configuration saved. Type "reconfigure" anytime to change these settings.
```

If no external models:
```
Rev2Agent — Ready
═══════════════════

External models: None configured (host-only mode)
  Tip: You can add API keys anytime by typing "reconfigure"

"Major Revision" panel: 3 host-native review agents

LaTeX: ✅ tectonic found  /  ⚠️ Not installed yet

Configuration saved.
```

### 0.6 Quick Guide

```
How Rev2Agent works
────────────────────
Phase 1  Topic Interview      — Tell me your research idea
Phase 2  Literature Search    — I find papers and identify gaps
Phase 3  Research Plan        — We define the research question  
Phase 4  Experiment Design    — I plan the experiments
Phase 5  Experiment Execution — I write and run the code
Phase 6  Result Analysis      — I analyze what happened
Phase 7  Manuscript Writing   — I draft the paper
Phase 8  Review Panel         — AI reviewers critique the draft

Commands:
  "major revision"   — Convene multi-model discussion panel
  "reconfigure"      — Re-run this setup

At key moments, Reviewer 2 will weigh in with judgments.
Don't take it personally — Reviewer 2 never does.

Let's begin. What research area are you interested in?
```

Then proceed to Phase 1 (Topic Interview).

## Config File Schema

Save to `.rev2agent_config.json` at the repository root. **This file must be added to `.gitignore`** as it contains API keys.

```json
{
  "version": 1,
  "setup_completed_at": "2026-04-09T12:00:00Z",
  "providers": [
    {
      "name": "openrouter",
      "api_base": "https://openrouter.ai/api/v1/chat/completions",
      "api_key": "sk-or-v1-...",
      "flagship_model": "openai/gpt-5.4"
    },
    {
      "name": "google",
      "api_base": "https://generativelanguage.googleapis.com/v1beta",
      "api_key": "AIzaSy...",
      "flagship_model": "gemini-3.1-pro-preview"
    }
  ],
  "roles": {
    "verification": {"provider": "openrouter", "model": "openai/gpt-5.4"},
    "discussion": ["openai/gpt-5.4", "gemini-3.1-pro-preview"]
  },
  "major_revisions_panel": {
    "claude_agents": 3,
    "external_models": ["openai/gpt-5.4", "gemini-3.1-pro-preview"]
  },
  "latex": {
    "tectonic_path": "tectonic"
  }
}
```

The `providers` array can be empty (host-only mode). Keys are stored directly in this file since it is gitignored — no need for environment variables.

## State Update

Phase 0 does NOT create a `.research_state.json` (that happens in Phase 1). It only creates `.rev2agent_config.json` and ensures `.gitignore` includes it.

After setup, proceed directly to the Startup Protocol.
