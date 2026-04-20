# Installation

<details>
<summary>한국어</summary>

## 설치 방법

### 사전 준비

[Claude Code](https://docs.anthropic.com/en/docs/claude-code)를 설치하세요. 터미널(CLI), 데스크톱 앱(Mac/Windows), 웹(claude.ai/code), IDE 확장(VS Code/JetBrains) 중 편한 것을 선택하면 됩니다.

### 시작하기

Claude Code를 열고 아래 프롬프트를 붙여넣으세요:

> Clone https://github.com/dalbom/rev2agent and set it up as my working directory. Then follow the CLAUDE.md startup protocol.

끝입니다. Rev2Agent가 환경 설정(Phase 0)부터 안내합니다.

### 이미 clone 했다면

rev2agent 디렉토리에서 Claude Code를 실행하면 됩니다:

> Open the rev2agent directory and follow the CLAUDE.md startup protocol.

또는 터미널에서:

```bash
cd rev2agent
claude
```

### Phase 0에서 일어나는 일

첫 실행 시 Rev2Agent가 다음을 안내합니다:

1. **외부 LLM API 키 설정** (선택) -- 멀티 모델 토론과 코드 교차 검증에 사용. 없어도 동작합니다.
2. **LaTeX 컴파일러 확인** (선택) -- 논문 PDF 생성용. 없으면 나중에 설치해도 됩니다.
3. **Python 환경** -- 실험 실행 시 프로젝트별로 자동 생성됩니다.

설정이 끝나면 연구 주제를 이야기하면 됩니다.

</details>

## Prerequisites

Install [Claude Code](https://docs.anthropic.com/en/docs/claude-code) using whichever interface you prefer: terminal (CLI), desktop app (Mac/Windows), web (claude.ai/code), or IDE extension (VS Code/JetBrains).

## Getting Started

Open Claude Code and paste this prompt:

> Clone https://github.com/dalbom/rev2agent and set it up as my working directory. Then follow the CLAUDE.md startup protocol.

That's it. Rev2Agent will guide you through environment setup (Phase 0) and then ask about your research topic.

## If You Already Cloned

Open the rev2agent directory in Claude Code:

> Open the rev2agent directory and follow the CLAUDE.md startup protocol.

Or from a terminal:

```bash
cd rev2agent
claude
```

## What Happens in Phase 0

On first run, Rev2Agent walks you through:

1. **External LLM API keys** (optional) -- used for multi-model discussions and code cross-verification. Works without them.
2. **LaTeX compiler check** (optional) -- for manuscript PDF generation. Can be installed later.
3. **Python environment** -- created automatically per project when experiments begin.

Once setup is complete, start talking about your research.
