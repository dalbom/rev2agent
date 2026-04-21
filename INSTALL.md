# Installation

<details>
<summary>한국어</summary>

## 설치 방법

### 사전 준비

지원되는 코딩 에이전트 호스트 하나가 필요합니다:

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- Codex

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

1. **외부 LLM API 키 설정** (선택) -- 멀티 모델 토론과 코드 교차 검증에 사용. OpenRouter, OpenAI, Google AI Studio, xAI, Anthropic, OpenAI-compatible 엔드포인트를 지원합니다. 없어도 동작합니다.
2. **LaTeX 컴파일러 확인** (선택) -- 논문 PDF 생성용. 없으면 나중에 설치해도 됩니다.
3. **Python 환경** -- 실험 실행 시 프로젝트별로 자동 생성됩니다.

설정이 끝나면 연구 주제를 이야기하면 됩니다.

</details>

## Prerequisites

Install one supported coding agent host:

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code)
- Codex

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

1. **External LLM API keys** (optional) -- used for multi-model discussions and code cross-verification. Supports OpenRouter, OpenAI, Google AI Studio, xAI, Anthropic, and OpenAI-compatible endpoints. Works without them.
2. **LaTeX compiler check** (optional) -- for manuscript PDF generation. Can be installed later.
3. **Python environment** -- created automatically per project when experiments begin.

Once setup is complete, start talking about your research.
