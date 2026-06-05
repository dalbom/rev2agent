from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_windows_gui_launcher_wraps_powershell_script() -> None:
    batch_script = REPO_ROOT / "scripts" / "start-gui.bat"
    powershell_script = REPO_ROOT / "scripts" / "start-gui.ps1"

    assert batch_script.exists()
    assert powershell_script.exists()

    batch_text = batch_script.read_text(encoding="utf-8")
    powershell_text = powershell_script.read_text(encoding="utf-8")

    assert "start-gui.ps1" in batch_text
    assert "$PSScriptRoot" in powershell_text
    assert "web\\backend" in powershell_text
    assert "web\\frontend" in powershell_text
    assert "uvicorn app.main:app" in powershell_text
    assert "pnpm dev --host 127.0.0.1 --port 5173" in powershell_text
    assert "http://127.0.0.1:5173" in powershell_text


def test_macos_gui_launcher_bootstraps_and_opens_browser() -> None:
    mac_script = REPO_ROOT / "scripts" / "start-gui.command"

    assert mac_script.exists()

    script_text = mac_script.read_text(encoding="utf-8")

    assert "dirname \"$0\"" in script_text
    assert "web/backend" in script_text
    assert "web/frontend" in script_text
    assert "uvicorn app.main:app" in script_text
    assert "pnpm dev --host 127.0.0.1 --port 5173" in script_text
    assert "open \"http://127.0.0.1:5173\"" in script_text
