# run.ps1 -- Start the Presence backend and frontend in separate terminal windows.
#
# Usage: Right-click -> "Run with PowerShell"  OR  from a terminal: .\run.ps1
#
# Requirements:
#   - uv    (https://docs.astral.sh/uv/getting-started/installation/)
#   - Bun   (https://bun.sh/)

# $PSScriptRoot is the folder where this script lives -- always correct regardless
# of which directory you run it from.
$root = $PSScriptRoot

# ---- Preflight checks -------------------------------------------------------
Write-Host ""
Write-Host "  Presence -- startup" -ForegroundColor Cyan
Write-Host "  ===================" -ForegroundColor Cyan
Write-Host ""

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "  ERROR: 'uv' is not installed." -ForegroundColor Red
    Write-Host "  Install it from: https://docs.astral.sh/uv/getting-started/installation/" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "  Press Enter to exit"
    exit 1
}

if (-not (Get-Command bun -ErrorAction SilentlyContinue)) {
    Write-Host "  ERROR: 'bun' is not installed." -ForegroundColor Red
    Write-Host "  Install it from: https://bun.sh/" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "  Press Enter to exit"
    exit 1
}

# ---- Install dependencies (idempotent -- safe to run every time) ------------
Write-Host "  [1/2] Syncing backend dependencies (uv sync)..." -ForegroundColor White
Push-Location "$root\backend"
uv sync
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: uv sync failed." -ForegroundColor Red
    Pop-Location; Read-Host "  Press Enter to exit"; exit 1
}
Pop-Location

Write-Host "  [2/2] Installing frontend dependencies (bun install)..." -ForegroundColor White
Push-Location "$root\frontend"
bun install
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: bun install failed." -ForegroundColor Red
    Pop-Location; Read-Host "  Press Enter to exit"; exit 1
}
Pop-Location

# ---- Database Setup ---------------------------------------------------------
$dbUrl = $null

# 1. Try Docker if running
$dockerAvailable = $false
if (Get-Command docker -ErrorAction SilentlyContinue) {
    & docker info > $null 2>&1
    if ($LASTEXITCODE -eq 0) {
        $dockerAvailable = $true
    }
}

if ($dockerAvailable) {
    Write-Host "  Starting PostgreSQL database via Docker (docker compose up db -d)..." -ForegroundColor White
    docker compose up db -d
    if ($LASTEXITCODE -eq 0) {
        $dbUrl = "postgresql://presence:presence@localhost:5432/presence"
        Write-Host "  Docker database started on port 5432." -ForegroundColor Green
    }
}

# 2. If Docker is not available or failed, try local PostgreSQL installation
if (-not $dbUrl) {
    $pgBin = $null
    if (Get-Command pg_ctl -ErrorAction SilentlyContinue) {
        $pgBin = Split-Path (Get-Command pg_ctl).Source
    } else {
        $pgDirs = Get-ChildItem "C:\Program Files\PostgreSQL" -ErrorAction SilentlyContinue | Sort-Object Name -Descending
        foreach ($d in $pgDirs) {
            if (Test-Path "$($d.FullName)\bin\pg_ctl.exe") {
                $pgBin = "$($d.FullName)\bin"
                break
            }
        }
    }

    if ($pgBin) {
        Write-Host "  Detected local PostgreSQL at $pgBin." -ForegroundColor White
        $pgData = "$root\.pgdata"
        if (-not (Test-Path $pgData)) {
            Write-Host "  Initializing local database cluster at $pgData..." -ForegroundColor White
            & "$pgBin\initdb.exe" -D $pgData -U presence -A trust
        }

        # Check if server is running for this data directory
        & "$pgBin\pg_ctl.exe" -D $pgData status > $null 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  Starting local PostgreSQL on port 5433..." -ForegroundColor White
            & "$pgBin\pg_ctl.exe" -D $pgData -o "-p 5433" -l "$pgData\server.log" start
            Start-Sleep -Seconds 1
        }

        # Ensure 'presence' database exists
        & "$pgBin\createdb.exe" -h 127.0.0.1 -p 5433 -U presence presence > $null 2>&1
        $dbUrl = "postgresql://presence@127.0.0.1:5433/presence"
        Write-Host "  Local PostgreSQL ready on port 5433." -ForegroundColor Green
    } else {
        Write-Host "  WARNING: Docker is not running and local PostgreSQL binaries were not found." -ForegroundColor Yellow
        Write-Host "  Ensure Docker Desktop or PostgreSQL is running, or set DATABASE_URL." -ForegroundColor Yellow
    }
}

# Persist DATABASE_URL to backend/.env and current environment
if ($dbUrl) {
    Set-Content -Path "$root\backend\.env" -Value "DATABASE_URL=$dbUrl"
    $env:DATABASE_URL = $dbUrl
}

# ---- Launch servers ---------------------------------------------------------
Write-Host ""
Write-Host "  Starting backend  ->  http://localhost:8000/docs" -ForegroundColor Green
Write-Host "  Starting frontend ->  http://localhost:5173" -ForegroundColor Green
Write-Host ""

$shellExe = if (Get-Command pwsh -ErrorAction SilentlyContinue) { "pwsh" } else { "powershell" }

$backendCmd = "Write-Host '  Backend running -- http://localhost:8000/docs' -ForegroundColor Green; Write-Host '  Database: $dbUrl' -ForegroundColor DarkGray; Write-Host '  NOTE: First face-recognition call downloads ~500 MB model. Be patient!' -ForegroundColor Yellow; Write-Host ''; uv run uvicorn main:app --reload --port 8000"

Start-Process $shellExe -ArgumentList `
    "-NoExit", `
    "-Command", `
    $backendCmd `
    -WorkingDirectory "$root\backend"

# Give the backend a couple of seconds to bind its port before the frontend starts.
Start-Sleep -Seconds 2

Start-Process $shellExe -ArgumentList `
    "-NoExit", `
    "-Command", `
    "Write-Host '  Frontend running -- http://localhost:5173' -ForegroundColor Green; Write-Host ''; bun run dev" `
    -WorkingDirectory "$root\frontend"

Write-Host "  Both windows are open. Close them to stop the servers." -ForegroundColor Cyan
Write-Host ""
