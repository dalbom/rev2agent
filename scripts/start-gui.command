#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/web/backend"
FRONTEND_DIR="$REPO_ROOT/web/frontend"
BACKEND_VENV="$BACKEND_DIR/.venv"
BACKEND_PYTHON="$BACKEND_VENV/bin/python"
BACKEND_STAMP="$BACKEND_VENV/.rev2agent-gui-ready"
FRONTEND_STAMP="$FRONTEND_DIR/node_modules/.rev2agent-gui-ready"
APP_URL="http://127.0.0.1:5173"

step() {
  printf "\n==> %s\n" "$1"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf "\n%s was not found. %s\n" "$1" "$2" >&2
    read -r -p "Press Enter to close."
    exit 1
  fi
}

port_open() {
  nc -z 127.0.0.1 "$1" >/dev/null 2>&1
}

shell_quote() {
  printf "%q" "$1"
}

ensure_backend() {
  step "Checking backend environment"
  require_command python3 "Install Python 3.10 or newer, then run this file again."

  if [ ! -x "$BACKEND_PYTHON" ]; then
    step "Creating backend Python environment"
    python3 -m venv "$BACKEND_VENV"
  fi

  local needs_install=0
  if [ ! -f "$BACKEND_STAMP" ]; then
    needs_install=1
  elif [ "$BACKEND_DIR/pyproject.toml" -nt "$BACKEND_STAMP" ]; then
    needs_install=1
  fi

  if [ "$needs_install" -eq 1 ]; then
    step "Installing backend packages"
    (
      cd "$BACKEND_DIR"
      "$BACKEND_PYTHON" -m pip install --upgrade pip
      "$BACKEND_PYTHON" -m pip install -e ".[dev]"
      touch "$BACKEND_STAMP"
    )
  fi
}

ensure_frontend() {
  step "Checking frontend environment"
  require_command pnpm "Install Node.js, then run 'corepack enable' or install pnpm."

  local needs_install=0
  if [ ! -d "$FRONTEND_DIR/node_modules" ] || [ ! -f "$FRONTEND_STAMP" ]; then
    needs_install=1
  elif [ "$FRONTEND_DIR/pnpm-lock.yaml" -nt "$FRONTEND_STAMP" ]; then
    needs_install=1
  fi

  if [ "$needs_install" -eq 1 ]; then
    step "Installing frontend packages"
    (
      cd "$FRONTEND_DIR"
      pnpm install
      touch "$FRONTEND_STAMP"
    )
  fi
}

start_backend() {
  if port_open 8000; then
    printf "Backend already running on http://127.0.0.1:8000\n"
    return
  fi

  step "Starting backend server"
  osascript <<EOF
tell application "Terminal"
  do script "cd $(shell_quote "$BACKEND_DIR"); $(shell_quote "$BACKEND_PYTHON") -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
end tell
EOF
}

start_frontend() {
  if port_open 5173; then
    printf "Frontend already running on %s\n" "$APP_URL"
    return
  fi

  step "Starting frontend server"
  osascript <<EOF
tell application "Terminal"
  do script "cd $(shell_quote "$FRONTEND_DIR"); pnpm dev --host 127.0.0.1 --port 5173"
end tell
EOF
}

printf "Rev2Agent GUI launcher\n"
printf "Repository: %s\n" "$REPO_ROOT"

ensure_backend
ensure_frontend
start_backend
start_frontend

step "Opening browser"
sleep 4
open "http://127.0.0.1:5173"
printf "\nRev2Agent GUI is starting at %s\n" "$APP_URL"
