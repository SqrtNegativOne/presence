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

# ---- Launch servers ---------------------------------------------------------
Write-Host ""
Write-Host "  Starting backend  ->  http://localhost:8000/docs" -ForegroundColor Green
Write-Host "  Starting frontend ->  http://localhost:5173" -ForegroundColor Green
Write-Host ""

# Start-Process opens a NEW PowerShell window for each server.
# -NoExit keeps the window open after the command finishes (or crashes).
# -WorkingDirectory sets the correct folder so Python/Bun can find their files.

Start-Process powershell -ArgumentList `
    "-NoExit", `
    "-Command", `
    "Write-Host '  Backend running -- http://localhost:8000/docs' -ForegroundColor Green; Write-Host '  NOTE: First face-recognition call downloads ~500 MB model. Be patient!' -ForegroundColor Yellow; Write-Host ''; uv run uvicorn main:app --reload --port 8000" `
    -WorkingDirectory "$root\backend"

# Give the backend a couple of seconds to bind its port before the frontend starts.
Start-Sleep -Seconds 2

Start-Process powershell -ArgumentList `
    "-NoExit", `
    "-Command", `
    "Write-Host '  Frontend running -- http://localhost:5173' -ForegroundColor Green; Write-Host ''; bun run dev" `
    -WorkingDirectory "$root\frontend"

Write-Host "  Both windows are open. Close them to stop the servers." -ForegroundColor Cyan
Write-Host ""
