#!/usr/bin/env pwsh
# ───────────────────────────────────────────────────────────
# DockDesk - Test on any repo (Windows PowerShell)
# ───────────────────────────────────────────────────────────
# Usage:
#   .\test_on_repo.ps1 https://github.com/fastapi/fastapi
#   .\test_on_repo.ps1 C:\path\to\local\repo
#   .\test_on_repo.ps1 https://github.com/pallets/flask --max-files 30
#   .\test_on_repo.ps1 --test-suite                    # Run full test suite
#   .\test_on_repo.ps1 --test-suite --turbo            # Run suite in turbo mode
# ───────────────────────────────────────────────────────────

param(
    [Parameter(Position=0)]
    [string]$RepoPath,

    [int]$MaxFiles = 50,

    [string]$Model = "qwen2.5-coder:3b",

    [string]$ReasoningModel = "deepseek-r1:1.5b",

    [int]$Workers = 0,

    [int]$BatchSize = 0,

    [switch]$Fast,

    [switch]$Turbo,

    [switch]$Full,

    [switch]$KeepClone,

    [switch]$TestSuite
)

$ErrorActionPreference = "Stop"
$TempDir = $null
$SuiteResults = @()

# ── Helpers ──

function Run-SingleRepo {
    param(
        [string]$RepoUrl,
        [string]$RepoName,
        [int]$MaxF,
        [switch]$IsFast,
        [switch]$IsTurbo
    )

    $LocalTempDir = $null
    $TargetDir = $null

    # Clone or resolve local path
    if ($RepoUrl -match "^https?://") {
        $CloneName = ($RepoUrl -split "/")[-1] -replace "\.git$", ""
        $LocalTempDir = Join-Path $env:TEMP "dockdesk_test_$CloneName"

        if (Test-Path $LocalTempDir) {
            Write-Host "  [*] Using existing clone: $LocalTempDir" -ForegroundColor Yellow
        } else {
            Write-Host "  [*] Cloning $RepoUrl ..." -ForegroundColor Yellow
            git clone --depth 1 $RepoUrl $LocalTempDir 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) {
                Write-Host "  [!] Failed to clone $RepoUrl" -ForegroundColor Red
                return @{ name=$RepoName; status="CLONE_FAILED"; smoke_time=0; full_time=0; files=0; high=0; medium=0; low=0; pass_rate=0; cached=0 }
            }
        }
        $TargetDir = $LocalTempDir
    } else {
        if (-not (Test-Path $RepoUrl)) {
            Write-Host "  [!] Path does not exist: $RepoUrl" -ForegroundColor Red
            return @{ name=$RepoName; status="NOT_FOUND"; smoke_time=0; full_time=0; files=0; high=0; medium=0; low=0; pass_rate=0; cached=0 }
        }
        $TargetDir = (Resolve-Path $RepoUrl).Path
    }

    # Build args
    $BaseArgs = @(
        "audit",
        "--workspace", $TargetDir,
        "--model", $Model,
        "--reasoning-model", $ReasoningModel,
        "--skip-rag",
        "--max-files", $MaxF
    )

    if ($Workers -gt 0) { $BaseArgs += @("--workers", $Workers) }
    if ($BatchSize -gt 0) { $BaseArgs += @("--batch-size", $BatchSize) }
    if ($IsTurbo) { $BaseArgs += "--turbo" }
    elseif ($IsFast) { $BaseArgs += "--fast" }

    # Phase 1: Smoke test
    Write-Host "  Phase 1: Smoke (10 files, --fast) ..." -ForegroundColor DarkGray
    $SmokeStart = Get-Date
    $smokeArgs = @("audit", "--workspace", $TargetDir, "--model", $Model, "--reasoning-model", $ReasoningModel, "--skip-rag", "--max-files", 10, "--fast")
    if ($Workers -gt 0) { $smokeArgs += @("--workers", $Workers) }
    dockdesk @smokeArgs 2>&1 | Out-Null
    $SmokeDuration = ((Get-Date) - $SmokeStart).TotalSeconds

    # Phase 2: Full run
    Write-Host "  Phase 2: Full ($MaxF files) ..." -ForegroundColor DarkGray
    $FullStart = Get-Date
    & dockdesk @BaseArgs 2>&1 | Out-Null
    $FullDuration = ((Get-Date) - $FullStart).TotalSeconds

    # Parse results
    $ResultInfo = @{ name=$RepoName; status="OK"; smoke_time=$SmokeDuration; full_time=$FullDuration; files=0; high=0; medium=0; low=0; pass_rate=0; cached=0 }

    $DashPath = Join-Path $TargetDir "dashboard_data.json"
    if (Test-Path $DashPath) {
        try {
            $Data = Get-Content $DashPath -Raw | ConvertFrom-Json
            $RunFiles = $Data.latest_run_files
            if ($RunFiles) {
                $Total = ($RunFiles | Measure-Object).Count
                $ResultInfo.files = $Total
                $ResultInfo.high = ($RunFiles | Where-Object { $_.risk -eq "HIGH" } | Measure-Object).Count
                $ResultInfo.medium = ($RunFiles | Where-Object { $_.risk -eq "MEDIUM" } | Measure-Object).Count
                $ResultInfo.low = ($RunFiles | Where-Object { $_.risk -eq "LOW" } | Measure-Object).Count
                $PassCount = ($RunFiles | Where-Object { $_.status -eq "PASS" } | Measure-Object).Count
                $ResultInfo.pass_rate = if ($Total -gt 0) { [math]::Round($PassCount / $Total, 2) } else { 0 }
                $CachedCount = ($RunFiles | Where-Object { $_.duration_ms -eq 0 } | Measure-Object).Count
                $ResultInfo.cached = $CachedCount
            }
        } catch {
            $ResultInfo.status = "PARSE_ERROR"
        }
    } else {
        $ResultInfo.status = "NO_OUTPUT"
    }

    # Cleanup temp clone
    if ($LocalTempDir -and -not $KeepClone) {
        Remove-Item -Recurse -Force $LocalTempDir -ErrorAction SilentlyContinue
    }

    return $ResultInfo
}

# ───────────────────────────────────────────────────────────
# MAIN
# ───────────────────────────────────────────────────────────

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  DockDesk - Repo Test Runner" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if ($TestSuite) {
    # ── Test Suite Mode: read test_repos.yml ──
    $ManifestPath = Join-Path $PSScriptRoot "tests" "test_repos.yml"
    if (-not (Test-Path $ManifestPath)) {
        Write-Error "Test manifest not found: $ManifestPath"
        exit 1
    }

    # Simple YAML parser for our flat structure
    $Content = Get-Content $ManifestPath -Raw
    $Repos = @()
    $Current = $null

    foreach ($line in ($Content -split "`n")) {
        $trimmed = $line.Trim()
        if ($trimmed -match "^- name:\s*(.+)$") {
            if ($Current) { $Repos += $Current }
            $Current = @{ name=$Matches[1].Trim(); url=""; max_files=50; category="" }
        }
        elseif ($Current -and $trimmed -match "^url:\s*(.+)$") { $Current.url = $Matches[1].Trim() }
        elseif ($Current -and $trimmed -match "^max_files:\s*(\d+)") { $Current.max_files = [int]$Matches[1] }
        elseif ($Current -and $trimmed -match "^category:\s*(.+)$") { $Current.category = $Matches[1].Trim() }
    }
    if ($Current) { $Repos += $Current }

    Write-Host "  Found $($Repos.Count) repos in test manifest" -ForegroundColor White
    Write-Host "  Mode: $(if ($Turbo) { 'TURBO' } elseif ($Fast) { 'FAST' } else { 'STANDARD' })" -ForegroundColor White
    Write-Host ""

    $SuiteStart = Get-Date
    $FailCount = 0

    foreach ($repo in $Repos) {
        Write-Host "────────────────────────────────────────" -ForegroundColor DarkGray
        Write-Host "  Testing: $($repo.name) ($($repo.category))" -ForegroundColor Green
        Write-Host "  URL:     $($repo.url)" -ForegroundColor DarkGray
        Write-Host ""

        $result = Run-SingleRepo -RepoUrl $repo.url -RepoName $repo.name -MaxF $repo.max_files -IsFast:$Fast -IsTurbo:$Turbo
        $SuiteResults += [PSCustomObject]$result

        $statusColor = if ($result.status -eq "OK") { "Green" } else { "Red" }
        Write-Host "  -> $($result.status) | $('{0:N1}' -f $result.smoke_time)s smoke | $('{0:N1}' -f $result.full_time)s full | $($result.files) files | H=$($result.high) M=$($result.medium) L=$($result.low) | Pass=$($result.pass_rate) | Cached=$($result.cached)" -ForegroundColor $statusColor
        Write-Host ""

        if ($result.status -ne "OK" -or $result.files -eq 0) {
            $FailCount++
        }
    }

    $SuiteDuration = ((Get-Date) - $SuiteStart).TotalSeconds

    # Summary table
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  TEST SUITE SUMMARY" -ForegroundColor Cyan
    Write-Host "═══════════════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
    Write-Host ("  {0,-15} {1,-10} {2,8} {3,8} {4,6} {5,6} {6,6} {7,6} {8,6}" -f "Repo","Status","Smoke(s)","Full(s)","Files","HIGH","MED","LOW","Cache")
    Write-Host ("  {0,-15} {1,-10} {2,8} {3,8} {4,6} {5,6} {6,6} {7,6} {8,6}" -f "----","------","--------","-------","-----","----","---","---","-----")

    foreach ($r in $SuiteResults) {
        $sc = if ($r.status -eq "OK") { "White" } else { "Red" }
        Write-Host ("  {0,-15} {1,-10} {2,8:N1} {3,8:N1} {4,6} {5,6} {6,6} {7,6} {8,6}" -f $r.name,$r.status,$r.smoke_time,$r.full_time,$r.files,$r.high,$r.medium,$r.low,$r.cached) -ForegroundColor $sc
    }

    Write-Host ""
    Write-Host "  Total suite time: $('{0:N1}' -f $SuiteDuration)s" -ForegroundColor White
    Write-Host "  Passed: $($Repos.Count - $FailCount)/$($Repos.Count)" -ForegroundColor $(if ($FailCount -eq 0) { "Green" } else { "Yellow" })
    Write-Host ""

    if ($FailCount -gt 0) {
        Write-Host "  SUITE FAILED: $FailCount repo(s) produced errors or 0 results" -ForegroundColor Red
        exit 1
    }
    exit 0
}

# ── Single repo mode ──
if (-not $RepoPath) {
    Write-Error "Provide a repo path/URL, or use --TestSuite. Usage: .\test_on_repo.ps1 <repo> [--Fast] [--Turbo]"
    exit 1
}

# Determine target directory
if ($RepoPath -match "^https?://") {
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
    if (-not (Test-Path $RepoPath)) {
        Write-Error "Path does not exist: $RepoPath"
        exit 1
    }
    $TargetDir = (Resolve-Path $RepoPath).Path
}

# Count files
$FileCount = (Get-ChildItem -Path $TargetDir -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.DirectoryName -notmatch "node_modules|\.git|__pycache__|venv|dist|build" } |
    Measure-Object).Count

Write-Host ""
Write-Host "  Target:      $TargetDir" -ForegroundColor White
Write-Host "  Total files:  $FileCount" -ForegroundColor White
Write-Host "  Max files:    $MaxFiles" -ForegroundColor White
Write-Host "  Model:        $Model" -ForegroundColor White
Write-Host "  Reasoning:    $ReasoningModel" -ForegroundColor White
if ($Workers -gt 0) { Write-Host "  Workers:      $Workers" -ForegroundColor White }
if ($BatchSize -gt 0) { Write-Host "  Batch size:   $BatchSize" -ForegroundColor White }
if ($Turbo) { Write-Host "  Mode:         TURBO" -ForegroundColor Yellow }
elseif ($Fast) { Write-Host "  Mode:         FAST" -ForegroundColor Yellow }
Write-Host ""

# Build command
$Args = @(
    "audit",
    "--workspace", $TargetDir,
    "--model", $Model,
    "--reasoning-model", $ReasoningModel,
    "--skip-rag",
    "--max-files", $MaxFiles
)

if ($Workers -gt 0) { $Args += @("--workers", $Workers) }
if ($BatchSize -gt 0) { $Args += @("--batch-size", $BatchSize) }
if ($Turbo) { $Args += "--turbo" }
elseif ($Fast) { $Args += "--fast" }

if ($Full) {
    $Args = $Args | Where-Object { $_ -ne "--max-files" -and $_ -ne "$MaxFiles" }
}

# Smoke test
Write-Host "────────────────────────────────────────" -ForegroundColor DarkGray
Write-Host "  Phase 1: Smoke Test (10 files, --fast)" -ForegroundColor Green
Write-Host "────────────────────────────────────────" -ForegroundColor DarkGray

$SmokeStart = Get-Date
$smokeArgs = @("audit", "--workspace", $TargetDir, "--model", $Model, "--reasoning-model", $ReasoningModel, "--skip-rag", "--max-files", 10, "--fast")
if ($Workers -gt 0) { $smokeArgs += @("--workers", $Workers) }
dockdesk @smokeArgs
$SmokeEnd = Get-Date
$SmokeDuration = ($SmokeEnd - $SmokeStart).TotalSeconds

Write-Host ""
Write-Host "  Smoke test completed in $([math]::Round($SmokeDuration, 1))s" -ForegroundColor Green
Write-Host ""

# Full run
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
        $CachedCount = ($RunFiles | Where-Object { $_.duration_ms -eq 0 } | Measure-Object).Count
        Write-Host "  Findings:     HIGH=$HighRisk  MEDIUM=$MedRisk  LOW=$LowRisk  Cached=$CachedCount" -ForegroundColor White
    }
}

Write-Host ""

# Cleanup
if ($TempDir -and -not $KeepClone) {
    Write-Host "[*] Cleaning up temp clone..." -ForegroundColor DarkGray
    Remove-Item -Recurse -Force $TempDir -ErrorAction SilentlyContinue
}

Write-Host "Done." -ForegroundColor Green
