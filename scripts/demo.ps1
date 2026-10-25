# One-command WATTSON demo for Windows.
#
#   powershell -ExecutionPolicy Bypass -File scripts/demo.ps1
#
# Starts a Temporal dev server (if one is not already listening), a worker, and
# the API against a fresh demo SQLite database, then runs the end-to-end demo.
# Everything is simulated: no cloud credentials and no paid resources.

[CmdletBinding()]
param(
    [int]$ApiPort = 0,
    [switch]$KeepRunning
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Token = if ($env:WATTSON_API_TOKEN) { $env:WATTSON_API_TOKEN } else { "wattson-demo-token" }
$TaskQueue = "wattson-demo"
$LogDir = Join-Path $Root ".data\logs"
$DataDir = Join-Path $Root ".data"
New-Item -ItemType Directory -Force -Path $LogDir, $DataDir | Out-Null
$env:WATTSON_API_TOKEN = $Token
$env:WATTSON_TEMPORAL_HOST = "localhost:7233"
$env:WATTSON_TEMPORAL_TASK_QUEUE = $TaskQueue
$env:WATTSON_PROVIDER = "simulator"
$env:WATTSON_AI_PROVIDER = "none"
$env:WATTSON_KILL_SWITCH = "false"

$DbPath = (Join-Path $DataDir "demo.db").Replace("\", "/")
$env:WATTSON_DATABASE_URL = "sqlite:///$DbPath"
Remove-Item -Force -ErrorAction SilentlyContinue "$DbPath", "$DbPath-shm", "$DbPath-wal"

function Test-Port([int]$Port) {
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(500)) { return $false }
        $client.EndConnect($async)
        return $true
    } catch {
        return $false
    } finally {
        $client.Dispose()
    }
}

function Wait-Port([int]$Port, [int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port $Port) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Stop-Tree([int]$ProcessId) {
    if ($ProcessId -and (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)) {
        & taskkill.exe /PID $ProcessId /T /F 2>$null | Out-Null
    }
}

$startedTemporal = $null
$startedWorker = $null
$startedApi = $null
$apiPort = $ApiPort

try {
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uv) { throw "uv is not installed or not on PATH." }
    $temporal = Get-Command temporal -ErrorAction SilentlyContinue

    if (-not (Test-Port 7233)) {
        if (-not $temporal) {
            throw "Temporal CLI is not installed. Install it or start a dev server on localhost:7233."
        }
        Write-Host "Starting Temporal dev server on 127.0.0.1:7233 (headless)..."
        $startedTemporal = Start-Process -FilePath $temporal.Source `
            -ArgumentList @("server", "start-dev", "--headless", "--port", "7233",
                            "--db-filename", (Join-Path $DataDir "temporal-demo.db")) `
            -WorkingDirectory $Root `
            -RedirectStandardOutput (Join-Path $LogDir "demo-temporal.out.log") `
            -RedirectStandardError (Join-Path $LogDir "demo-temporal.err.log") `
            -PassThru
        if (-not (Wait-Port 7233 45)) { throw "Temporal did not start. See .data/logs/demo-temporal.err.log." }
    } else {
        Write-Host "Using the Temporal server already listening on 127.0.0.1:7233."
    }

    if ($apiPort -eq 0) {
        foreach ($candidate in 8000, 8010, 8020) {
            if (-not (Test-Port $candidate)) { $apiPort = $candidate; break }
        }
        if ($apiPort -eq 0) { throw "Ports 8000, 8010 and 8020 are all in use." }
    }
    $env:WATTSON_API_URL = "http://127.0.0.1:$apiPort"

    Write-Host "Starting worker on task queue '$TaskQueue'..."
    $startedWorker = Start-Process -FilePath $uv.Source `
        -ArgumentList @("run", "python", "-m", "wattson.worker") `
        -WorkingDirectory $Root `
        -RedirectStandardOutput (Join-Path $LogDir "demo-worker.out.log") `
        -RedirectStandardError (Join-Path $LogDir "demo-worker.err.log") `
        -PassThru

    Write-Host "Starting API on http://127.0.0.1:$apiPort ..."
    $startedApi = Start-Process -FilePath $uv.Source `
        -ArgumentList @("run", "uvicorn", "wattson.api.app:app", "--host", "127.0.0.1", "--port", "$apiPort") `
        -WorkingDirectory $Root `
        -RedirectStandardOutput (Join-Path $LogDir "demo-api.out.log") `
        -RedirectStandardError (Join-Path $LogDir "demo-api.err.log") `
        -PassThru

    $ready = $false
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        try {
            $health = Invoke-RestMethod -Uri "$($env:WATTSON_API_URL)/api/health" -TimeoutSec 3
            if ($health.status) { $ready = $true; break }
        } catch {
            Start-Sleep -Milliseconds 750
        }
    }
    if (-not $ready) {
        throw "API did not become ready. See .data/logs/demo-api.err.log and demo-worker.err.log."
    }

    Write-Host ""
    & $uv.Source run wattson-demo --api-url $env:WATTSON_API_URL --token $Token
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "Demo exited with code $exitCode. Inspect .data/logs/ for details."
    }
}
finally {
    if (-not $KeepRunning) {
        if ($startedApi) { Stop-Tree $startedApi.Id }
        if ($startedWorker) { Stop-Tree $startedWorker.Id }
        if ($startedTemporal) { Stop-Tree $startedTemporal.Id }
    } else {
        Write-Host "KeepRunning set: API=$($startedApi.Id) worker=$($startedWorker.Id) temporal=$($startedTemporal.Id)"
    }
}
