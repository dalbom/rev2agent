from __future__ import annotations

import platform
import shutil
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .codex_adapter import SdkStatus


def build_settings_status(
    repo_root: Path,
    *,
    sdk_status: SdkStatus,
    which: Callable[[str], str | None] = shutil.which,
    python_version: str | None = None,
) -> dict[str, Any]:
    root = repo_root.resolve()
    tectonic_path = which("tectonic")
    pnpm_path = which("pnpm")
    return {
        "codex_sdk": asdict(sdk_status),
        "repository": {
            "root": root,
            "config_exists": (root / ".rev2agent_config.json").exists(),
        },
        "tools": {
            "latex": {
                "name": "tectonic",
                "available": tectonic_path is not None,
                "path": tectonic_path,
            },
            "python": {
                "available": True,
                "version": python_version or platform.python_version(),
            },
            "package_manager": {
                "name": "pnpm",
                "available": pnpm_path is not None,
                "path": pnpm_path,
            },
        },
    }
