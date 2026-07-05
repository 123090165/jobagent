[CmdletBinding()]
param(
    [switch]$Stop,
    [switch]$OpenBrowser,
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [string]$EnvFile = ".env.deepseek.local"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$WebRoot = Join-Path $ProjectRoot "web"
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$StateDir = Join-Path ([System.IO.Path]::GetTempPath()) "jobagent-dev"
$BackendPidFile = Join-Path $StateDir "backend-$BackendPort.pid"
$FrontendPidFile = Join-Path $StateDir "frontend-$FrontendPort.pid"

New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

function Test-PortOpen {
    param([int]$Port)

    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $asyncResult = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        if (-not $asyncResult.AsyncWaitHandle.WaitOne(300)) {
            return $false
        }
        $client.EndConnect($asyncResult)
        return $true
    }
    catch {
        return $false
    }
    finally {
        $client.Close()
    }
}

function Wait-Port {
    param(
        [string]$Name,
        [int]$Port,
        [int]$TimeoutSeconds = 25
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortOpen -Port $Port) {
            Write-Host "$Name is listening on port $Port."
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    Write-Warning "$Name did not respond on port $Port within $TimeoutSeconds seconds."
    return $false
}

function Stop-ProcessTree {
    param([int]$ProcessId)

    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" -ErrorAction SilentlyContinue
    foreach ($child in $children) {
        Stop-ProcessTree -ProcessId $child.ProcessId
    }

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($null -ne $process) {
        Stop-Process -Id $ProcessId -Force
    }
}

function Stop-PortListener {
    param(
        [string]$Name,
        [int]$Port
    )

    $connections = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    if ($connections.Count -eq 0) {
        return
    }

    $processIds = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($processId in $processIds) {
        if (-not $processId) {
            continue
        }
        Write-Host "$Name listener on port $Port stopped (PID $processId)."
        Stop-ProcessTree -ProcessId ([int]$processId)
    }
}

function Stop-FromPidFile {
    param(
        [string]$Name,
        [string]$PidFile,
        [int]$Port
    )

    if (-not (Test-Path -LiteralPath $PidFile)) {
        Write-Host "$Name PID file not found; checking port $Port."
        Stop-PortListener -Name $Name -Port $Port
        return
    }

    $processId = (Get-Content -LiteralPath $PidFile -Raw).Trim()
    if (-not $processId) {
        Remove-Item -LiteralPath $PidFile -Force
        Write-Host "$Name PID file was empty; removed it."
        Stop-PortListener -Name $Name -Port $Port
        return
    }

    $process = Get-Process -Id ([int]$processId) -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        Remove-Item -LiteralPath $PidFile -Force
        Write-Host "$Name process $processId is not running; removed stale PID file."
        Stop-PortListener -Name $Name -Port $Port
        return
    }

    Stop-ProcessTree -ProcessId $process.Id
    Remove-Item -LiteralPath $PidFile -Force
    Write-Host "$Name stopped (PID $processId)."
}

function Resolve-EnvFilePath {
    param([string]$Value)

    if (-not $Value) {
        return $null
    }
    if ([System.IO.Path]::IsPathRooted($Value)) {
        return $Value
    }
    return Join-Path $ProjectRoot $Value
}

function Get-PowerShellExe {
    $current = (Get-Process -Id $PID).Path
    if ($current) {
        return $current
    }
    return "powershell.exe"
}

function Start-DevWindow {
    param(
        [string]$Name,
        [string[]]$ArgumentList,
        [string]$PidFile
    )

    $process = Start-Process `
        -FilePath (Get-PowerShellExe) `
        -ArgumentList $ArgumentList `
        -PassThru
    Set-Content -LiteralPath $PidFile -Value $process.Id
    Write-Host "$Name window started (PID $($process.Id))."
}

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python venv not found: $PythonExe. Create it and install requirements first."
}

$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if ($null -eq $npmCommand) {
    $npmCommand = Get-Command npm -ErrorAction SilentlyContinue
}
if ($null -eq $npmCommand) {
    throw "npm was not found in PATH."
}

if ($Stop) {
    Stop-FromPidFile -Name "Backend" -PidFile $BackendPidFile -Port $BackendPort
    Stop-FromPidFile -Name "Frontend" -PidFile $FrontendPidFile -Port $FrontendPort
    exit 0
}

if ($BackendOnly) {
    $envPath = Resolve-EnvFilePath -Value $EnvFile
    if ($envPath -and (Test-Path -LiteralPath $envPath)) {
        $env:JOBAGENT_ENV_FILE = $envPath
        Write-Host "Using env file: $envPath"
    }
    elseif ($envPath) {
        Write-Warning "Env file not found: $envPath. Backend will use app defaults."
    }

    Set-Location -LiteralPath $ProjectRoot
    & $PythonExe -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort
    exit $LASTEXITCODE
}

if ($FrontendOnly) {
    if (-not (Test-Path -LiteralPath (Join-Path $WebRoot "package.json"))) {
        throw "Frontend package.json not found: $WebRoot"
    }
    Set-Location -LiteralPath $WebRoot
    & $npmCommand.Source run dev -- --host 127.0.0.1 --port $FrontendPort
    exit $LASTEXITCODE
}

if (-not (Test-Path -LiteralPath (Join-Path $WebRoot "node_modules"))) {
    Write-Warning "web\node_modules not found. Run 'cd web; npm install' before using this script."
}

$scriptPath = $PSCommandPath
$baseArgs = @(
    "-NoExit",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $scriptPath
)

if (Test-PortOpen -Port $BackendPort) {
    Write-Host "Backend already appears to be listening on port $BackendPort."
}
else {
    Start-DevWindow `
        -Name "Backend" `
        -PidFile $BackendPidFile `
        -ArgumentList ($baseArgs + @(
            "-BackendOnly",
            "-BackendPort",
            "$BackendPort",
            "-EnvFile",
            $EnvFile
        ))
}

if (Test-PortOpen -Port $FrontendPort) {
    Write-Host "Frontend already appears to be listening on port $FrontendPort."
}
else {
    Start-DevWindow `
        -Name "Frontend" `
        -PidFile $FrontendPidFile `
        -ArgumentList ($baseArgs + @(
            "-FrontendOnly",
            "-FrontendPort",
            "$FrontendPort"
        ))
}

$backendReady = Wait-Port -Name "Backend" -Port $BackendPort
$frontendReady = Wait-Port -Name "Frontend" -Port $FrontendPort

$backendUrl = "http://127.0.0.1:$BackendPort"
$frontendUrl = "http://localhost:$FrontendPort"
Write-Host ""
Write-Host "Backend:  $backendUrl"
Write-Host "Frontend: $frontendUrl"
Write-Host "Stop:     .\scripts\start-dev.ps1 -Stop"

if ($OpenBrowser -and $frontendReady) {
    Start-Process $frontendUrl
}

if (-not ($backendReady -and $frontendReady)) {
    exit 1
}
