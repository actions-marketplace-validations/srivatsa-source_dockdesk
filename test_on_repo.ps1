#!/usr/bin/env pwsh
# ───────────────────────────────────────────────────────────
# DockDesk - Test on any repo (Windows PowerShell)
# ───────────────────────────────────────────────────────────
# Usage:
#   .\test_on_repo.ps1 https://github.com/fastapi/fastapi
#   .\test_on_repo.ps1 C:\path\to\local\repo
#   .\test_on_repo.ps1 https://github.com/pallets/flask --max-files 30
# ───────────────────────────────────────────────────────────

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$RepoPath,

    [int]$MaxFiles = 50,

    [string]$Model = "qwen2.5-coder:3b",

    [string]$ReasoningModel = "deepseek-r1:1.5b",

    [switch]$Fast,

    [switch]$Full,

    [switch]$KeepClone
)

$ErrorActionPreference = "Stop"
$TempDir = $null

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DockDesk - Repo Test Runner" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ── Determine target directory ──
if ($RepoPath -match "^https?://") {
    # It's a URL — clone it
    $RepoName = ($RepoPath -split "/")[-1] -replace "\.git$", ""
    $TempDir = Join-Path $env:TEMP "dockdesk_test_$RepoName"

    if (Test-Path $TempDir) {
        Write-Host "[*] Using existing clone: $TempDir" -ForegroundColor Yellow
    } else {
        Write-Host "[*] Cloning $RepoPath ..." -ForegroundColor Yellow
        git clone --depth 1 $RepoPath $TempDir
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to clone $RepoPath"
            exit 1
        }
    }
    $TargetDir = $TempDir
} else {
    # It's a local path
    if (-not (Test-Path $RepoPath)) {
        Write-Error "Path does not exist: $RepoPath"
        exit 1
    }
    $TargetDir = (Resolve-Path $RepoPath).Path
}

# ── Count files ──
$FileCount = (Get-ChildItem -Path $TargetDir -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.DirectoryName -notmatch "node_modules|\.git|__pycache__|venv|dist|build" } |
    Measure-Object).Count

Write-Host ""
Write-Host "  Target:      $TargetDir" -ForegroundColor White
Write-Host "  Total files:  $FileCount" -ForegroundColor White
Write-Host "  Max files:    $MaxFiles" -ForegroundColor White
Write-Host "  Model:        $Model" -ForegroundColor White
Write-Host "  Reasoning:    $ReasoningModel" -ForegroundColor White
Write-Host ""

# ── Build command ──
$Args = @(
    "audit",
    "--workspace", $TargetDir,
    "--model", $Model,
    "--reasoning-model", $ReasoningModel,
    "--skip-rag",
    "--max-files", $MaxFiles
)

if ($Fast) {
    $Args += "--fast"
}

if ($Full) {
    # Remove max-files cap for full run
    $Args = $Args | Where-Object { $_ -ne "--max-files" -and $_ -ne "$MaxFiles" }
}

# ── Smoke test (quick, 10 files) ──
Write-Host "────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  Phase 1: Smoke Test (10 files, --fast)" -ForegroundColor Green
Write-Host "────────────────────────────────────────" -ForegroundColor DarkGray

$SmokeStart = Get-Date
dockdesk audit --workspace $TargetDir --model $Model --reasoning-model $ReasoningModel --skip-rag --max-files 10 --fast
$SmokeEnd = Get-Date
$SmokeDuration = ($SmokeEnd - $SmokeStart).TotalSeconds

Write-Host ""
Write-Host "  Smoke test completed in $([math]::Round($SmokeDuration, 1))s" -ForegroundColor Green
Write-Host ""

# ── Full run ──
Write-Host "────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  Phase 2: Full Audit" -ForegroundColor Green
Write-Host "────────────────────────────────────────" -ForegroundColor DarkGray

$FullStart = Get-Date
& dockdesk @Args
$FullEnd = Get-Date
$FullDuration = ($FullEnd - $FullStart).TotalSeconds

Write-Host ""
Write-Host "────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  Results Summary" -ForegroundColor Cyan
Write-Host "────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  Repo:         $TargetDir"
Write-Host "  Total files:  $FileCount"
Write-Host "  Smoke test:   $([math]::Round($SmokeDuration, 1))s"
Write-Host "  Full audit:   $([math]::Round($FullDuration, 1))s"

$ReportPath = Join-Path $TargetDir "audit_report.md"
if (Test-Path $ReportPath) {
    Write-Host "  Report:       $ReportPath" -ForegroundColor Green
} else {
    Write-Host "  Report:       (not generated)" -ForegroundColor Yellow
}

$DashPath = Join-Path $TargetDir "dashboard_data.json"
if (Test-Path $DashPath) {
    $Data = Get-Content $DashPath | ConvertFrom-Json
    $RunFiles = $Data.latest_run_files
    if ($RunFiles) {
        $HighRisk = ($RunFiles | Where-Object { $_.risk -eq "HIGH" } | Measure-Object).Count
        $MedRisk  = ($RunFiles | Where-Object { $_.risk -eq "MEDIUM" } | Measure-Object).Count
        $LowRisk  = ($RunFiles | Where-Object { $_.risk -eq "LOW" } | Measure-Object).Count
        Write-Host "  Findings:     HIGH=$HighRisk  MEDIUM=$MedRisk  LOW=$LowRisk" -ForegroundColor White
    }
}

Write-Host ""

# ── Cleanup ──
if ($TempDir -and -not $KeepClone) {
    Write-Host "[*] Cleaning up temp clone..." -ForegroundColor DarkGray
    Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
}

Write-Host "Done." -ForegroundColor Green
