from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


CONFIG_FILENAME = ".rev2agent_config.json"


def setup_config_path(repo_root: Path) -> Path:
    return repo_root.resolve() / CONFIG_FILENAME


def setup_is_complete(repo_root: Path) -> bool:
    return setup_config_path(repo_root).exists()


def complete_host_only_setup(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    config_path = setup_config_path(root)

    if config_path.exists():
        config = _read_existing_config(config_path)
    else:
        config = _host_only_config()
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")

    _ensure_gitignore_entry(root / ".gitignore", CONFIG_FILENAME)
    return config


def _host_only_config() -> dict[str, Any]:
    return {
        "version": 1,
        "setup_completed_at": _utc_now(),
        "providers": [],
        "roles": {
            "verification": {
                "provider": "host-native",
                "model": "host-native adversarial reviewer",
            },
            "discussion": ["host-native"],
        },
        "major_revisions_panel": {
            "claude_agents": 3,
            "external_models": [],
        },
        "latex": {
            "tectonic_path": None,
        },
    }


def _read_existing_config(config_path: Path) -> dict[str, Any]:
    try:
        parsed = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _ensure_gitignore_entry(gitignore_path: Path, entry: str) -> None:
    if gitignore_path.exists():
        lines = gitignore_path.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    if entry in {line.strip() for line in lines}:
        return

    if lines and lines[-1].strip():
        lines.append("")
    lines.append("# Rev2Agent local setup")
    lines.append(entry)
    gitignore_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
