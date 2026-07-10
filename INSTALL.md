# Installation

<details>
<summary>한국어</summary>

## 설치 방법

### 사전 준비

지원되는 코딩 에이전트 호스트 하나가 필요합니다:

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- [Codex CLI](https://help.openai.com/en/articles/11096431-openai-codex-ci-getting-started)

추가로 필요한 것:

- **Python 3.10+** -- `scripts/` 도구는 표준 라이브러리만 사용하므로 별도의 `pip install`이 필요 없습니다. 실험용 Python 가상환경은 프로젝트별로 자동 생성됩니다.
- **git**

### 시작하기

**Claude Code**

Claude Code를 열고 아래 프롬프트를 붙여넣으세요:

> Clone https://github.com/dalbom/rev2agent and set it up as my working directory. Then follow the CLAUDE.md startup protocol.

**Codex**

rev2agent 저장소를 Codex에서 열고 `AGENTS.md` 시작 프로토콜을 따르세요.

끝입니다. Rev2Agent가 환경 설정(Phase 0)부터 안내합니다.

### 이미 clone 했다면

**Claude Code**

rev2agent 디렉토리에서 Claude Code를 실행하면 됩니다:

> Open the rev2agent directory and follow the CLAUDE.md startup protocol.

또는 터미널에서:

```bash
cd rev2agent
claude
```

**Codex**

rev2agent 디렉토리를 Codex에서 열고 `AGENTS.md` 시작 프로토콜을 따르세요.

### Phase 0에서 일어나는 일

첫 실행 시 Rev2Agent가 다음을 안내합니다:

1. **외부 LLM 연결** (선택) -- 멀티 모델 토론에 사용합니다. 자격 증명은 채팅이나 설정 파일이 아니라 환경 변수로 설정하며, Phase 0에는 프로바이더 이름만 전달합니다. OpenRouter, OpenAI, Google AI Studio, xAI, Anthropic, OpenAI-compatible 엔드포인트를 지원합니다. 없어도 동작합니다. 외부 코드 검토는 기본적으로 비활성화되며 별도의 명시적 동의가 필요합니다.
2. **LaTeX 컴파일러 확인** (선택) -- 논문 PDF 생성용. 없으면 나중에 설치해도 됩니다:

   ```bash
   curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh
   ```

3. **Python 환경** -- 실험 실행 시 프로젝트별로 자동 생성됩니다.

설정이 끝나면 연구 주제를 이야기하면 됩니다.

### 생성되는 파일

- `.rev2agent_config.json` -- 저장소 루트에 생성되는 로컬 설정입니다. 비밀 값 대신 환경 변수 이름만 저장하고 파일 권한을 가능한 경우 `0600`으로 설정합니다. git에서 무시되며 커밋하지 않습니다.
- 연구 프로젝트는 저장소 루트의 하위 폴더로 생성되며 기본적으로 git에서 무시됩니다. 연구 데이터가 public 저장소에 올라가지 않습니다.

</details>

## Prerequisites

Install one supported coding agent host:

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- [Codex CLI](https://help.openai.com/en/articles/11096431-openai-codex-ci-getting-started)

You also need:

- **Python 3.10+** -- the `scripts/` tooling is stdlib-only, so no `pip install` is required. Python virtual environments for experiments are created per-project automatically.
- **git**

## Getting Started

**Claude Code**

Open Claude Code and paste this prompt:

> Clone https://github.com/dalbom/rev2agent and set it up as my working directory. Then follow the CLAUDE.md startup protocol.

**Codex**

Open the repository in Codex and follow the `AGENTS.md` startup protocol.

That's it. Rev2Agent will guide you through environment setup (Phase 0) and then ask about your research topic.

## If You Already Cloned

**Claude Code**

Open the rev2agent directory in Claude Code:

> Open the rev2agent directory and follow the CLAUDE.md startup protocol.

Or from a terminal:

```bash
cd rev2agent
claude
```

**Codex**

Open the rev2agent directory in Codex and follow the `AGENTS.md` startup protocol.

## What Happens in Phase 0

On first run, Rev2Agent walks you through:

1. **External LLM access** (optional) -- used for multi-model discussions. Set each credential in an environment variable outside chat; Phase 0 receives only provider names. OpenRouter, OpenAI, Google AI Studio, xAI, Anthropic, and OpenAI-compatible endpoints are supported. External code review is disabled by default and requires a separate explicit opt-in.
2. **LaTeX compiler check** (optional) -- for manuscript PDF generation. Can be installed later:

   ```bash
   curl --proto '=https' --tlsv1.2 -fsSL https://drop-sh.fullyjustified.net | sh
   ```

3. **Python environment** -- created automatically per project when experiments begin.

Once setup is complete, start talking about your research.

## What Gets Created

- `.rev2agent_config.json` -- machine-local configuration created at the repository root. It stores environment variable names rather than secret values, uses mode `0600` where supported, and is git-ignored. Never commit it.
- Research projects are created as subfolders of the repository root and are git-ignored by default, so your research data stays out of the public repo.
