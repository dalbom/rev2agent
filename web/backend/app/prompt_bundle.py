from __future__ import annotations

import json
from pathlib import Path
from typing import Any


PHASE_PROMPTS: dict[int, str] = {
    0: "00_setup.md",
    1: "01_interview.md",
    2: "02_literature_search.md",
    3: "03_research_plan.md",
    4: "04_experiment_design.md",
    5: "05_experiment_execution.md",
    6: "06_result_analysis.md",
    7: "07_manuscript_writing.md",
    8: "08_manuscript_review.md",
}


def build_phase_prompt_bundle(
    *,
    repo_root: Path,
    project_path: Path,
    state: dict[str, Any],
    user_prompt: str,
) -> str:
    phase = _phase_number(state.get("current_phase"))
    if phase is None:
        raise ValueError("Research state does not contain a valid current_phase")

    sections = [
        "# Rev2Agent SDK Prompt Bundle",
        repository_instructions_section(repo_root),
        phase_prompt_section(repo_root, phase),
        research_state_section(state),
        project_context_section(repo_root, project_path),
        user_prompt_section(user_prompt),
    ]
    return "\n\n".join(section for section in sections if section.strip()).rstrip() + "\n"


def repository_instructions_section(repo_root: Path) -> str:
    agents_path = repo_root / "AGENTS.md"
    claude_path = repo_root / "CLAUDE.md"
    if agents_path.exists():
        return f"## Repository Instructions (AGENTS.md)\n\n{agents_path.read_text(encoding='utf-8')}"
    if claude_path.exists():
        return f"## Repository Instructions (CLAUDE.md)\n\n{claude_path.read_text(encoding='utf-8')}"
    return "## Repository Instructions\n\nNo AGENTS.md or CLAUDE.md found."


def phase_prompt_section(repo_root: Path, phase: int) -> str:
    prompt_path = phase_prompt_path(repo_root, phase)
    return f"## Phase Prompt ({prompt_path.relative_to(repo_root).as_posix()})\n\n{prompt_path.read_text(encoding='utf-8')}"


def research_state_section(state: dict[str, Any]) -> str:
    state_json = json.dumps(state, indent=2, ensure_ascii=False)
    return f"## Current Research State\n\n```json\n{state_json}\n```"


def project_context_section(repo_root: Path, project_path: Path) -> str:
    project_rel = project_path.resolve().relative_to(repo_root.resolve()).as_posix()
    return (
        "## Project Context\n\n"
        f"- Repository root: `{repo_root.resolve()}`\n"
        f"- Project directory: `{project_rel}`\n"
        "- Treat the user prompt below as the latest user feedback or instruction for this phase.\n"
        "- The session working directory is already the project directory; create and reference "
        "files relative to it (for example experiment/scripts/run.py, "
        "summaries/phase4_experiment_design.md).\n"
        "- Repository instructions and phase prompts write paths with a {project_dir}/ prefix; "
        "that prefix refers to the CURRENT directory here. Never create a "
        f"'{project_rel}' subdirectory inside the project "
        f"(no nested {project_rel}/{project_rel} paths)."
    )


def user_prompt_section(user_prompt: str) -> str:
    trimmed = user_prompt.strip()
    return f"## User Prompt\n\n{trimmed if trimmed else '(No additional user prompt was provided.)'}"


def phase_prompt_path(repo_root: Path, phase: int) -> Path:
    try:
        filename = PHASE_PROMPTS[phase]
    except KeyError as exc:
        raise ValueError(f"Unknown phase: {phase}") from exc
    return repo_root / "prompts" / filename


def _phase_number(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None
