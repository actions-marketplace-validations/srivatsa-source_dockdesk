#!/usr/bin/env pwsh
# ───────────────────────────────────────────────────────────
# DockDesk - Pip Install Integration Test (Windows)
# ───────────────────────────────────────────────────────────
# Tests: fresh venv → pip install → dockdesk --help → audit small repo → verify outputs
#
# Usage:
#   .\tests\test_pip_install.ps1
#   .\tests\test_pip_install.ps1 -TestRepo https://github.com/psf/httpbin
# ───────────────────────────────────────────────────────────

param(
    [string]$TestRepo = "https://github.com/pallets/click",
    [switch]$KeepVenv
)

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $PSScriptRoot  # project root

# Use a path without 8.3 short names (TEMP can resolve to SRINAT~1 which breaks venv)
$TestRoot = Join-Path $HOME ".dockdesk_test"
if (-not (Test-Path $TestRoot)) { New-Item -ItemType Directory -Path $TestRoot -Force | Out-Null }
$VenvDir = Join-Path $TestRoot "pip_test_venv"
$CloneDir = Join-Path $TestRoot "pip_test_repo"

# Locate a working Python — prefer the current venv's python, then system
$SysPython = $null
$CurrentVenvPython = Join-Path (Join-Path $ScriptDir ".venv") (Join-Path "Scripts" "python.exe")
if (Test-Path $CurrentVenvPython) {
    $SysPython = $CurrentVenvPython
} else {
    # Try common locations
    foreach ($candidate in @("python3", "python", "py -3")) {
        try {
            $null = & $candidate --version 2>&1
            if ($LASTEXITCODE -eq 0) { $SysPython = $candidate; break }
        } catch {}
    }
}
if (-not $SysPython) {
    Write-Error "Cannot find a Python interpreter. Ensure python is on PATH or .venv exists."
    exit 1
}

# Venv binaries
$VenvPython = Join-Path (Join-Path $VenvDir "Scripts") "python.exe"
$VenvDockDesk = Join-Path (Join-Path $VenvDir "Scripts") "dockdesk.exe"

$Failed = 0

function Test-Step {
    param([string]$Name, [scriptblock]$Action)
    Write-Host ""
    Write-Host "  [$Name] ..." -ForegroundColor Cyan -NoNewline
    try {
        & $Action
        Write-Host " OK" -ForegroundColor Green
    } catch {
        Write-Host " FAIL: $_" -ForegroundColor Red
        $script:Failed++
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DockDesk - Pip Install Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Python: $SysPython" -ForegroundColor DarkGray
Write-Host "  Venv:   $VenvDir" -ForegroundColor DarkGray

# ── Step 1: Create fresh venv ──
Test-Step "Create venv" {
    if (Test-Path $VenvDir) { Remove-Item -Recurse -Force $VenvDir }
    & $SysPython -m venv $VenvDir 2>$null
    if (-not (Test-Path $VenvPython)) { throw "venv python not found at $VenvPython" }
    # Ensure pip is available (some venvs don't create pip.exe script)
    & $VenvPython -m ensurepip --upgrade 2>$null | Out-Null
}

# ── Step 2: Pip install ──
Test-Step "Pip install dockdesk" {
    & $VenvPython -m pip install "$ScriptDir" 2>$null | Out-Null
    if (-not (Test-Path $VenvDockDesk)) { throw "dockdesk entry point not created at $VenvDockDesk" }
}

# ── Step 3: Verify CLI entry point ──
Test-Step "dockdesk --help" {
    $output = & $VenvDockDesk --help 2>$null | Out-String
    if ($output -notmatch "audit") { throw "help output missing 'audit' command" }
}

# ── Step 4: Verify version ──
Test-Step "dockdesk --version" {
    $output = & $VenvDockDesk --version 2>$null | Out-String
    if ($output -notmatch "dockdesk") { throw "version output missing 'dockdesk'" }
}

# ── Step 5: Verify list-models ──
Test-Step "dockdesk list-models" {
    $null = & $VenvDockDesk list-models 2>$null | Out-String
}

# ── Step 6: Clone test repo ──
Test-Step "Clone test repo" {
    if (Test-Path $CloneDir) { Remove-Item -Recurse -Force $CloneDir }
    git clone --depth 1 $TestRepo $CloneDir 2>$null | Out-Null
    if (-not (Test-Path $CloneDir)) { throw "git clone failed - directory not created" }
}

# ── Step 7: Run audit on test repo ──
Test-Step "dockdesk audit (10 files, fast)" {
    & $VenvDockDesk audit --workspace $CloneDir --skip-rag --max-files 10 --fast 2>$null | Out-Null
    # Check outputs instead of exit code
    $ReportPath = Join-Path $CloneDir "audit_report.md"
    if (-not (Test-Path $ReportPath)) { throw "audit did not produce audit_report.md" }
}

# ── Step 8: Verify audit_report.md exists ──
Test-Step "Verify audit_report.md" {
    $ReportPath = Join-Path $CloneDir "audit_report.md"
    if (-not (Test-Path $ReportPath)) { throw "audit_report.md not found" }
    $content = Get-Content $ReportPath -Raw
    if ($content.Length -lt 100) { throw "audit_report.md too small ($($content.Length) chars)" }
}

# ── Step 9: Verify dashboard_data.json exists ──
Test-Step "Verify dashboard_data.json" {
    $DashPath = Join-Path $CloneDir "dashboard_data.json"
    if (-not (Test-Path $DashPath)) { throw "dashboard_data.json not found" }
    $data = Get-Content $DashPath -Raw | ConvertFrom-Json
    if (-not $data.latest_run_files) { throw "dashboard_data.json missing latest_run_files" }
    $fileCount = ($data.latest_run_files | Measure-Object).Count
    if ($fileCount -eq 0) { throw "latest_run_files is empty" }
    Write-Host " ($fileCount files)" -ForegroundColor DarkGray -NoNewline
}

# ── Step 10: Verify python -m dockdesk works ──
Test-Step "python -m dockdesk --help" {
    $output = & $VenvPython -m dockdesk --help 2>$null | Out-String
    if ($output -notmatch "audit") { throw "module entry point missing 'audit'" }
}

# ── Cleanup ──
if (-not $KeepVenv) {
    Write-Host ""
    Write-Host "  Cleaning up..." -ForegroundColor DarkGray
    Remove-Item -Recurse -Force $VenvDir -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force $CloneDir -ErrorAction SilentlyContinue
}

# ── Summary ──
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
if ($Failed -eq 0) {
    Write-Host "  ALL TESTS PASSED" -ForegroundColor Green
    exit 0
} else {
    Write-Host "  $Failed TEST(S) FAILED" -ForegroundColor Red
    exit 1
}
