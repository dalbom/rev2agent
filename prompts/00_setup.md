# Phase 0: Setup

## Objective

Configure Rev2Agent without putting provider credentials in the conversation or
in repository files. This phase runs on first launch, during security migration,
or when the user asks to reconfigure.

## Mode

Direct conversation with the user.

## When This Phase Runs

- `.rev2agent_config.json` does not exist.
- The config is not schema version 2, contains a legacy `api_key` value field,
  or has an invalid security setting.
- The user requests reconfiguration.

Security migration happens before project discovery or phase routing. A config
file's existence alone is not proof that setup is safe or complete.

## Design Principle

Make provider setup straightforward while keeping secret values outside chat,
configuration, logs, and command history. The user selects providers; Rev2Agent
stores only the names of environment variables that the provider client should
resolve later.

## Steps

### 0.1 Welcome

```text
Welcome to Rev2Agent
====================

Reviewer 2 is now your agent.

Rev2Agent can run entirely with host-native reviewers. Optional external
providers add perspectives to "major revision" discussions.
```

### 0.2 External Provider Access (optional)

Present this notice before asking which providers to configure:

```text
External model access is optional.

Do not paste API keys here. Set credentials as environment variables outside
this chat, then tell me only which provider names you want to enable. Type
"skip" for host-only mode.

Configured external discussion models may receive research questions,
manuscript excerpts, or decision context during an explicitly requested
"major revision" panel. Configuring a provider does not permit uploading
experiment source code; that has a separate opt-in and is disabled by default.
```

Use these standard references:

| Provider | Environment reference | API base |
|---|---|---|
| OpenRouter | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` |
| OpenAI | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| Google AI Studio | `GEMINI_API_KEY` (accept `GOOGLE_API_KEY`) | `https://generativelanguage.googleapis.com/v1beta` |
| xAI | `XAI_API_KEY` | `https://api.x.ai/v1` |
| Anthropic | `ANTHROPIC_API_KEY` | `https://api.anthropic.com` |
| DeepSeek | `DEEPSEEK_API_KEY` | `https://api.deepseek.com` |

For a custom OpenAI-compatible provider, ask only for its provider name, API
base, and environment-variable name. The environment name must match
`[A-Za-z_][A-Za-z0-9_]*`. Never ask for or accept the value.

#### Credential handling rules

- Check environment-variable **presence only**. Do not return its length,
  prefix, suffix, hash, or value.
- Never print, echo, summarize, or interpolate secret values into output,
  errors, prompts, logs, URLs, filenames, or command arguments.
- Resolve a credential inside the provider-calling process and use an
  authentication header. Do not place it in a shell command or query string.
- Store only `api_key_env`, never a credential value.
- If a referenced variable is missing, mark that provider unavailable and ask
  the user to set it outside chat or continue without it. Do not ask them to
  prove the value in chat.

For a selected provider whose reference is present, test connectivity with its
model-listing endpoint. The calling process resolves the environment variable
internally; logs report only provider name, success/failure, and model count.
An authentication failure should say that the referenced variable was rejected,
without revealing any credential material.

If the user says `skip`, configure host-only mode and continue.

### 0.3 Model Selection

For each available provider, list models and choose one current flagship-tier
text model. Exclude obvious budget, embedding, audio, image, free, and unusually
expensive reasoning-only variants. Prefer a stable model; use a preview only
when no stable peer exists. Do not hardcode the examples in this prompt as a
permanent model list.

Role assignment is separate from credential availability:

- **Discussion:** configured external models may join an explicitly requested
  `major revision` panel after the disclosure in Step 0.2.
- **Code verification:** use a host-native adversarial reviewer by default.
  An external reviewer is eligible only under Step 0.4.

### 0.4 External Code Review (separate opt-in)

Set `external_code_review` to the JSON boolean `false` unless the user
explicitly asks to enable external review after being told that full unpublished
source code may leave the host and be processed under the provider's terms.

Only the JSON boolean exactly `true` is an opt-in. Missing values, strings such
as `"true"`, numbers, null, and all other invalid values mean `false`. Enabling
this setting does not override a missing provider environment reference.

The user can change this later with `reconfigure`. Never infer consent from the
presence of an environment variable or from enabling external discussions.

### 0.5 Discussion Panel Size

Ask one question, defaulting to 3:

```text
How many host-native review agents should join the "major revision" panel?
[default: 3]
```

Store the result as `major_revisions_panel.host_agents`. Legacy
`claude_agents` may be read as a fallback, but new writes use `host_agents`.

### 0.6 LaTeX Check

Check for `tectonic` silently. Report whether it is available; do not block
setup because it is absent.

### 0.7 Environment Summary

Report provider names, selected model IDs, their `api_key_env` references,
discussion composition, external code review as enabled/disabled, host reviewer
count, and LaTeX status. Never include environment values.

Example:

```text
Rev2Agent - Ready

External discussions:
  OpenRouter - openai/gpt-5.4 (credential reference: OPENROUTER_API_KEY)

Code verification:
  Host-native adversarial reviewer (external code review disabled)

Configuration saved. Type "reconfigure" to change these settings.
```

Then proceed to Phase 1.

## Secure Config Write Protocol

Use this protocol for setup and migration:

1. Build a sanitized version-2 object in memory. It must contain environment
   names only and no secret values.
2. Create a same-directory temporary file with mode `0600` **before writing any
   content** where the platform supports POSIX permissions. Never write first
   and tighten permissions later.
3. Write, flush, and sync the temporary file, then atomically replace
   `.rev2agent_config.json`.
4. Apply mode `0600` to the final path where supported and verify the final
   permissions. Report a warning if the platform cannot enforce them.
5. Ensure `.rev2agent_config.json` remains in `.gitignore` because it is local
   machine configuration, even though version 2 contains no credential values.

## Legacy Configuration Migration

Run this migration before normal startup whenever a config is version 1,
contains a legacy `api_key` value field, or lacks the version-2 privacy fields.

1. Restrict the existing file to mode `0600` where supported before inspecting
   its structure.
2. Detect only whether a legacy value field exists. **Never display, print, use,
   transmit, test, or copy the legacy value.** Do not use it for connectivity.
3. Treat every affected external provider as unavailable immediately. Map its
   provider name to the standard `api_key_env` reference and check that
   environment variable's presence only.
4. If every retained provider has its referenced variable set, build a sanitized
   version-2 object: preserve nonsecret provider bases, model choices, discussion
   roles, panel size, and LaTeX settings; remove every legacy value field; add
   `api_key_env`; and set missing, non-boolean, or invalid
   `external_code_review` to `false`. Write it with the Secure Config Write
   Protocol.
5. If any reference is missing, pause external-provider migration and ask the
   user either to set it outside chat and resume, or to explicitly disable and
   scrub that provider. **Do not silently delete** what may be the user's only
   remaining copy. Until the choice is resolved, make no external calls and do
   not continue normal project routing.
6. Recommend that the user rotate every legacy credential because it may have
   been exposed in prior chat history or local plaintext storage.

Migration must never turn provider availability into permission for external
code review. The default remains `false`.

## Config File Schema

Save this nonsecret, machine-local object to `.rev2agent_config.json`:

```json
{
  "version": 2,
  "setup_completed_at": "2026-07-10T00:00:00Z",
  "external_code_review": false,
  "providers": [
    {
      "name": "openrouter",
      "api_base": "https://openrouter.ai/api/v1",
      "api_key_env": "OPENROUTER_API_KEY",
      "flagship_model": "openai/gpt-5.4"
    },
    {
      "name": "google",
      "api_base": "https://generativelanguage.googleapis.com/v1beta",
      "api_key_env": "GEMINI_API_KEY",
      "flagship_model": "gemini-pro"
    }
  ],
  "roles": {
    "verification": {
      "provider": "host-native",
      "model": "adversarial-reviewer"
    },
    "discussion": [
      "openai/gpt-5.4",
      "gemini-pro"
    ]
  },
  "major_revisions_panel": {
    "host_agents": 3,
    "external_models": [
      "openai/gpt-5.4",
      "gemini-pro"
    ]
  },
  "latex": {
    "tectonic_path": "tectonic"
  }
}
```

The `providers` array may be empty. `api_key_env` stores a variable name, not a
secret. External code review remains host-native unless the top-level opt-in is
exactly `true` and Phase 5 also confirms that the selected provider reference is
present.

## State Update

Phase 0 does not create `.research_state.json`. It writes or migrates only
`.rev2agent_config.json`, then returns to the Startup Protocol.
