from __future__ import annotations

from pathlib import Path

from app.codex_adapter import SdkStatus
from app.settings import build_settings_status


def test_build_settings_status_reports_config_and_tooling(tmp_path: Path) -> None:
    (tmp_path / ".rev2agent_config.json").write_text("{}", encoding="utf-8")

    def fake_which(name: str) -> str | None:
        return {
            "tectonic": "C:/tools/tectonic.exe",
            "pnpm": "C:/tools/pnpm.cmd",
        }.get(name)

    status = build_settings_status(
        tmp_path,
        sdk_status=SdkStatus(available=True, version="0.1.0b2", message="openai_codex is installed."),
        which=fake_which,
        python_version="3.11.14",
    )

    assert status["repository"]["config_exists"] is True
    assert status["environment"]["platform"]
    assert status["codex_sdk"]["available"] is True
    assert status["tools"]["latex"]["available"] is True
    assert status["tools"]["latex"]["path"] == "C:/tools/tectonic.exe"
    assert status["tools"]["python"]["version"] == "3.11.14"
    assert status["tools"]["package_manager"]["name"] == "pnpm"
    assert status["tools"]["package_manager"]["available"] is True


def test_build_settings_status_reports_missing_optional_tools(tmp_path: Path) -> None:
    status = build_settings_status(
        tmp_path,
        sdk_status=SdkStatus(available=False, version=None, message="missing"),
        which=lambda _name: None,
        python_version="3.11.14",
    )

    assert status["repository"]["config_exists"] is False
    assert status["environment"]["platform"]
    assert status["codex_sdk"]["available"] is False
    assert status["tools"]["latex"]["available"] is False
    assert status["tools"]["package_manager"]["available"] is False


def test_build_settings_status_finds_tectonic_in_repo_parent(tmp_path: Path) -> None:
    repo_root = tmp_path / "rev2agent-repo"
    repo_root.mkdir()
    local_tectonic = tmp_path / "tectonic.exe"
    local_tectonic.write_text("", encoding="utf-8")

    status = build_settings_status(
        repo_root,
        sdk_status=SdkStatus(available=True, version="0.1.0b2", message="openai_codex is installed."),
        which=lambda _name: None,
        python_version="3.11.14",
    )

    assert status["tools"]["latex"]["available"] is True
    assert status["tools"]["latex"]["path"] == str(local_tectonic)
