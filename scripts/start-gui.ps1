$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $RepoRoot "web\backend"
$FrontendDir = Join-Path $RepoRoot "web\frontend"
$BackendVenv = Join-Path $BackendDir ".venv"
$BackendPython = Join-Path $BackendVenv "Scripts\python.exe"
$BackendStamp = Join-Path $BackendVenv ".rev2agent-gui-ready"
$FrontendStamp = Join-Path $FrontendDir "node_modules\.rev2agent-gui-ready"
$AppUrl = "http://127.0.0.1:5173"

function Write-Step($Message) {
  Write-Host ""
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Require-Command($Name, $Hint) {
  $Command = Get-Command $Name -ErrorAction SilentlyContinue
  if (-not $Command) {
    throw "$Name was not found. $Hint"
  }
  return $Command.Source
}

function Test-LocalPort($Port) {
  $Client = New-Object Net.Sockets.TcpClient
  try {
    $Async = $Client.BeginConnect("127.0.0.1", $Port, $null, $null)
    if (-not $Async.AsyncWaitHandle.WaitOne(300, $false)) {
      return $false
    }
    $Client.EndConnect($Async)
    return $true
  } catch {
    return $false
  } finally {
    $Client.Close()
  }
}

function Quote-PowerShell($Value) {
  return "'" + ($Value -replace "'", "''") + "'"
}

function Ensure-Backend {
  Write-Step "Checking backend environment"
  $Python = Require-Command "python" "Install Python 3.10 or newer, then run this script again."

  if (-not (Test-Path $BackendPython)) {
    Write-Step "Creating backend Python environment"
    & $Python -m venv $BackendVenv
  }

  $PyProject = Join-Path $BackendDir "pyproject.toml"
  $NeedsInstall = -not (Test-Path $BackendStamp)
  if (-not $NeedsInstall -and (Test-Path $PyProject)) {
    $NeedsInstall = (Get-Item $PyProject).LastWriteTimeUtc -gt (Get-Item $BackendStamp).LastWriteTimeUtc
  }

  if ($NeedsInstall) {
    Write-Step "Installing backend packages"
    Push-Location $BackendDir
    try {
      & $BackendPython -m pip install --upgrade pip
      & $BackendPython -m pip install -e ".[dev]"
      New-Item -ItemType File -Path $BackendStamp -Force | Out-Null
    } finally {
      Pop-Location
    }
  }
}

function Ensure-Frontend {
  Write-Step "Checking frontend environment"
  $Pnpm = Require-Command "pnpm" "Install Node.js, then run 'corepack enable' or install pnpm."

  $NodeModules = Join-Path $FrontendDir "node_modules"
  $Lockfile = Join-Path $FrontendDir "pnpm-lock.yaml"
  $NeedsInstall = -not (Test-Path $NodeModules) -or -not (Test-Path $FrontendStamp)
  if (-not $NeedsInstall -and (Test-Path $Lockfile)) {
    $NeedsInstall = (Get-Item $Lockfile).LastWriteTimeUtc -gt (Get-Item $FrontendStamp).LastWriteTimeUtc
  }

  if ($NeedsInstall) {
    Write-Step "Installing frontend packages"
    Push-Location $FrontendDir
    try {
      & $Pnpm install
      New-Item -ItemType File -Path $FrontendStamp -Force | Out-Null
    } finally {
      Pop-Location
    }
  }
}

function Start-Backend {
  if (Test-LocalPort 8000) {
    Write-Host "Backend already running on http://127.0.0.1:8000"
    return
  }

  Write-Step "Starting backend server"
  $BackendCommand = "Set-Location -LiteralPath $(Quote-PowerShell $BackendDir); & $(Quote-PowerShell $BackendPython) -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
  Start-Process powershell.exe -ArgumentList @("-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $BackendCommand)
}

function Start-Frontend {
  if (Test-LocalPort 5173) {
    Write-Host "Frontend already running on $AppUrl"
    return
  }

  Write-Step "Starting frontend server"
  $FrontendCommand = "Set-Location -LiteralPath $(Quote-PowerShell $FrontendDir); pnpm dev --host 127.0.0.1 --port 5173"
  Start-Process powershell.exe -ArgumentList @("-NoExit", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", $FrontendCommand)
}

try {
  Write-Host "Rev2Agent GUI launcher"
  Write-Host "Repository: $RepoRoot"

  Ensure-Backend
  Ensure-Frontend
  Start-Backend
  Start-Frontend

  Write-Step "Opening browser"
  Start-Sleep -Seconds 4
  Start-Process $AppUrl
  Write-Host ""
  Write-Host "Rev2Agent GUI is starting at $AppUrl"
} catch {
  Write-Host ""
  Write-Host $_.Exception.Message -ForegroundColor Red
  Write-Host ""
  Read-Host "Press Enter to close"
  exit 1
}
