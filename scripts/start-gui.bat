@echo off
setlocal

set SCRIPT_DIR=%~dp0
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start-gui.ps1"

if errorlevel 1 (
  echo.
  echo Rev2Agent GUI failed to start.
  pause
)
