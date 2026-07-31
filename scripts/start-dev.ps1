[CmdletBinding()]
param(
    [switch]$Stop,
    [switch]$Check,
    [switch]$OpenBrowser,
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [switch]$RagOnly,
    [switch]$WorkerOnly,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173,
    [int]$RagPort = 8002,
    [int]$WorkerLimit = 10,
    [string]$EnvFile = ".env.deepseek.local",
    [string]$RagRoot = "D:\projects\rag-ai\MODULAR-RAG-MCP-SERVER"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$WebRoot = Join-Path $ProjectRoot "web"
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$StateDir = Join-Path ([System.IO.Path]::GetTempPath()) "jobagent-dev"
$BackendPidFile = Join-Path $StateDir "backend-$BackendPort.pid"
$FrontendPidFile = Join-Path $StateDir "frontend-$FrontendPort.pid"
$RagPidFile = Join-Path $StateDir "rag-$RagPort.pid"
$WorkerPidFile = Join-Path $StateDir "rag-worker.pid"

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

function Stop-FromPidFile {
    param(
        [string]$Name,
        [string]$PidFile,
        [int]$Port = 0
    )

    if (-not (Test-Path -LiteralPath $PidFile)) {
        Write-Host "$Name PID file not found; nothing managed by this script to stop."
        if ($Port -and (Test-PortOpen -Port $Port)) {
            Write-Warning "$Name port $Port is occupied by an external process; it was left running."
        }
        return
    }

    $processId = (Get-Content -LiteralPath $PidFile -Raw).Trim()
    if (-not $processId) {
        Remove-Item -LiteralPath $PidFile -Force
        Write-Host "$Name PID file was empty; removed it."
        return
    }

    $process = Get-Process -Id ([int]$processId) -ErrorAction SilentlyContinue
    if ($null -eq $process) {
        Remove-Item -LiteralPath $PidFile -Force
        Write-Host "$Name process $processId is not running; removed stale PID file."
        if ($Port -and (Test-PortOpen -Port $Port)) {
            Write-Warning "$Name port $Port is occupied by an external process; it was left running."
        }
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

function Resolve-ConfiguredPath {
    param(
        [string]$Value,
        [string]$BasePath
    )

    if ([System.IO.Path]::IsPathRooted($Value)) {
        return $Value
    }
    return Join-Path $BasePath $Value
}

function Read-DotEnv {
    param([string]$Path)

    $values = @{}
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $values
    }
    foreach ($rawLine in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $line = $rawLine.Trim()
        if (-not $line -or $line.StartsWith("#")) {
            continue
        }
        $separator = $line.IndexOf("=")
        if ($separator -lt 1) {
            continue
        }
        $name = $line.Substring(0, $separator).Trim()
        if ($name -notmatch "^[A-Za-z_][A-Za-z0-9_]*$") {
            continue
        }
        $value = $line.Substring($separator + 1).Trim()
        if (
            $value.Length -ge 2 -and
            (($value.StartsWith('"') -and $value.EndsWith('"')) -or
             ($value.StartsWith("'") -and $value.EndsWith("'")))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        $values[$name] = $value
    }
    return $values
}

function Import-DotEnv {
    param([string]$Path)

    $values = Read-DotEnv -Path $Path
    foreach ($entry in $values.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, "Process")
    }
}

function Set-DefaultEnvironmentValue {
    param(
        [string]$Name,
        [string]$Value
    )

    $current = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ([string]::IsNullOrWhiteSpace($current)) {
        [Environment]::SetEnvironmentVariable($Name, $Value, "Process")
    }
}

function Get-PowerShellExe {
    $current = (Get-Process -Id $PID).Path
    if ($current) {
        return $current
    }
    return "powershell.exe"
}

function Normalize-ProcessPathEnvironment {
    $variables = [Environment]::GetEnvironmentVariables("Process")
    $pathKeys = @(
        $variables.Keys |
            Where-Object {
                ([string]$_).Equals(
                    "Path",
                    [StringComparison]::OrdinalIgnoreCase
                )
            }
    )
    if ($pathKeys.Count -le 1) {
        return
    }

    $pathValue = [string]$variables["Path"]
    foreach ($key in $pathKeys) {
        [Environment]::SetEnvironmentVariable(
            [string]$key,
            $null,
            "Process"
        )
    }
    # Windows 变量名不区分大小写；先去重可避免 PowerShell 5.1 启动子进程时报重复键。
    [Environment]::SetEnvironmentVariable("Path", $pathValue, "Process")
}

function Start-DevWindow {
    param(
        [string]$Name,
        [string[]]$ArgumentList,
        [string]$PidFile,
        [string]$LogName
    )

    $stdoutLog = Join-Path $StateDir "$LogName.out.log"
    $stderrLog = Join-Path $StateDir "$LogName.err.log"
    Normalize-ProcessPathEnvironment
    $process = Start-Process `
        -FilePath (Get-PowerShellExe) `
        -ArgumentList $ArgumentList `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog `
        -PassThru
    Set-Content -LiteralPath $PidFile -Value $process.Id
    Write-Host "$Name started (PID $($process.Id)). Logs: $stdoutLog, $stderrLog"
}

function Get-NpmCommand {
    $command = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        $command = Get-Command npm -ErrorAction SilentlyContinue
    }
    if ($null -eq $command) {
        # 隐藏子进程可能无法继承可解析的 PATH，回退到 Windows 常见 Node 安装目录。
        $candidates = @(
            "C:\Program Files\nodejs\npm.cmd",
            "C:\Program Files (x86)\nodejs\npm.cmd"
        )
        $npmPath = $candidates |
            Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
            Select-Object -First 1
        if ($npmPath) {
            $command = Get-Item -LiteralPath $npmPath
        }
    }
    if ($null -eq $command) {
        throw "npm was not found in PATH."
    }
    return $command
}

if ($Stop) {
    Stop-FromPidFile -Name "Backend" -PidFile $BackendPidFile -Port $BackendPort
    Stop-FromPidFile -Name "Frontend" -PidFile $FrontendPidFile -Port $FrontendPort
    Stop-FromPidFile -Name "RAG worker" -PidFile $WorkerPidFile
    Stop-FromPidFile -Name "RAG server" -PidFile $RagPidFile -Port $RagPort
    exit 0
}

$envPath = Resolve-EnvFilePath -Value $EnvFile
$ragRootPath = Resolve-ConfiguredPath -Value $RagRoot -BasePath $ProjectRoot
$ragPythonExe = Join-Path $ragRootPath ".venv\Scripts\python.exe"
$ragEnvPath = Join-Path $ragRootPath ".env"

if ($BackendOnly) {
    if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
        throw "Python venv not found: $PythonExe"
    }
    if (-not (Test-Path -LiteralPath $envPath -PathType Leaf)) {
        throw "JobAgent environment file not found: $envPath"
    }
    Import-DotEnv -Path $envPath
    Set-DefaultEnvironmentValue -Name "JOBAGENT_RAG_MCP_URL" -Value "http://127.0.0.1:$RagPort/mcp"
    Set-DefaultEnvironmentValue -Name "JOBAGENT_RAG_MANAGEMENT_URL" -Value "http://127.0.0.1:$RagPort"
    $env:JOBAGENT_RAG_SYNC_ENABLED = "true"
    $env:JOBAGENT_ENV_FILE = $envPath
    Set-Location -LiteralPath $ProjectRoot
    & $PythonExe -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort --reload
    exit $LASTEXITCODE
}

if ($FrontendOnly) {
    if (-not (Test-Path -LiteralPath (Join-Path $WebRoot "package.json"))) {
        throw "Frontend package.json not found: $WebRoot"
    }
    $npmCommand = Get-NpmCommand
    Set-Location -LiteralPath $WebRoot
    & $npmCommand.Source run dev -- --host 127.0.0.1 --port $FrontendPort
    exit $LASTEXITCODE
}

if ($RagOnly) {
    if (-not (Test-Path -LiteralPath $ragPythonExe -PathType Leaf)) {
        throw "RAG Python venv not found: $ragPythonExe"
    }
    if (-not (Test-Path -LiteralPath $ragEnvPath -PathType Leaf)) {
        throw "RAG environment file not found: $ragEnvPath"
    }
    Import-DotEnv -Path $ragEnvPath
    if ([string]::IsNullOrWhiteSpace($env:RAG_SERVICE_TOKEN)) {
        throw "RAG_SERVICE_TOKEN is missing from $ragEnvPath"
    }
    Set-Location -LiteralPath $ragRootPath
    & $ragPythonExe -u -m mcp_server.server `
        --transport streamable-http `
        --host 127.0.0.1 `
        --port $RagPort `
        --http-path /mcp `
        --settings config/settings.yaml
    exit $LASTEXITCODE
}

if ($WorkerOnly) {
    if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
        throw "Python venv not found: $PythonExe"
    }
    if (-not (Test-Path -LiteralPath $envPath -PathType Leaf)) {
        throw "JobAgent environment file not found: $envPath"
    }
    Import-DotEnv -Path $envPath
    Set-DefaultEnvironmentValue -Name "JOBAGENT_RAG_MANAGEMENT_URL" -Value "http://127.0.0.1:$RagPort"
    $env:JOBAGENT_RAG_SYNC_ENABLED = "true"
    $env:JOBAGENT_ENV_FILE = $envPath
    Set-Location -LiteralPath $ProjectRoot
    & $PythonExe -u -m scripts.run_rag_sync --watch --limit $WorkerLimit
    exit $LASTEXITCODE
}

if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "JobAgent Python venv not found: $PythonExe"
}
if (-not (Test-Path -LiteralPath $ragPythonExe -PathType Leaf)) {
    throw "RAG Python venv not found: $ragPythonExe"
}
if (-not (Test-Path -LiteralPath $envPath -PathType Leaf)) {
    throw "JobAgent environment file not found: $envPath"
}
if (-not (Test-Path -LiteralPath $ragEnvPath -PathType Leaf)) {
    throw "RAG environment file not found: $ragEnvPath"
}

$jobEnv = Read-DotEnv -Path $envPath
$ragEnv = Read-DotEnv -Path $ragEnvPath
$jobToken = [string]$jobEnv["JOBAGENT_RAG_SERVICE_TOKEN"]
$ragToken = [string]$ragEnv["RAG_SERVICE_TOKEN"]
if ([string]::IsNullOrWhiteSpace($jobToken)) {
    throw "JOBAGENT_RAG_SERVICE_TOKEN is missing from $envPath"
}
if ([string]::IsNullOrWhiteSpace($ragToken)) {
    throw "RAG_SERVICE_TOKEN is missing from $ragEnvPath"
}
if ($jobToken -cne $ragToken) {
    throw "JobAgent and RAG service tokens do not match. Update the two env files before starting."
}

$npmCommand = Get-NpmCommand

if (-not (Test-Path -LiteralPath (Join-Path $WebRoot "node_modules"))) {
    throw "web\node_modules not found. Run 'cd web; npm install' before using this script."
}

if ($Check) {
    Write-Host "Startup configuration is valid."
    Write-Host "JobAgent root: $ProjectRoot"
    Write-Host "RAG root:      $ragRootPath"
    Write-Host "Backend port:  $BackendPort"
    Write-Host "Frontend port: $FrontendPort"
    Write-Host "RAG port:      $RagPort"
    Write-Host "Shared token:  configured and matching (value hidden)"
    exit 0
}

$scriptPath = $PSCommandPath
$baseArgs = @(
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    $scriptPath
)

if (Test-PortOpen -Port $RagPort) {
    Write-Host "RAG server already appears to be listening on port $RagPort."
}
else {
    Start-DevWindow `
        -Name "RAG server" `
        -PidFile $RagPidFile `
        -LogName "rag-$RagPort" `
        -ArgumentList ($baseArgs + @(
            "-RagOnly",
            "-RagPort",
            "$RagPort",
            "-RagRoot",
            $ragRootPath
        ))
}

$ragReady = Wait-Port -Name "RAG server" -Port $RagPort
if ($ragReady) {
    $env:JOBAGENT_ENV_FILE = $envPath
    $env:JOBAGENT_RAG_MCP_URL = "http://127.0.0.1:$RagPort/mcp"
    $inspectionLog = Join-Path $StateDir "rag-inspection.log"
    & $PythonExe -m scripts.inspect_rag_mcp *> $inspectionLog
    if ($LASTEXITCODE -eq 0) {
        Write-Host "RAG MCP protocol inspection passed."
    }
    else {
        Write-Warning "RAG MCP protocol inspection failed. Check $inspectionLog"
        $ragReady = $false
    }
}

if (Test-PortOpen -Port $BackendPort) {
    Write-Host "Backend already appears to be listening on port $BackendPort."
}
else {
    Start-DevWindow `
        -Name "Backend" `
        -PidFile $BackendPidFile `
        -LogName "backend-$BackendPort" `
        -ArgumentList ($baseArgs + @(
            "-BackendOnly",
            "-BackendPort",
            "$BackendPort",
            "-RagPort",
            "$RagPort",
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
        -LogName "frontend-$FrontendPort" `
        -ArgumentList ($baseArgs + @(
            "-FrontendOnly",
            "-FrontendPort",
            "$FrontendPort"
        ))
}

if (-not $ragReady) {
    Write-Warning "RAG worker was not started because the RAG server is unavailable."
}
elseif (Test-Path -LiteralPath $WorkerPidFile) {
    $workerProcessId = (Get-Content -LiteralPath $WorkerPidFile -Raw).Trim()
    $parsedWorkerProcessId = 0
    $workerProcess = $null
    if ([int]::TryParse($workerProcessId, [ref]$parsedWorkerProcessId)) {
        $workerProcess = Get-Process `
            -Id $parsedWorkerProcessId `
            -ErrorAction SilentlyContinue
    }
    if ($null -ne $workerProcess) {
        Write-Host "RAG worker is already running (PID $workerProcessId)."
    }
    else {
        Remove-Item -LiteralPath $WorkerPidFile -Force
    }
}

if ($ragReady -and -not (Test-Path -LiteralPath $WorkerPidFile)) {
    Start-DevWindow `
        -Name "RAG worker" `
        -PidFile $WorkerPidFile `
        -LogName "rag-worker" `
        -ArgumentList ($baseArgs + @(
            "-WorkerOnly",
            "-WorkerLimit",
            "$WorkerLimit",
            "-RagPort",
            "$RagPort",
            "-EnvFile",
            $EnvFile
        ))
    Start-Sleep -Seconds 1
    $startedWorkerProcessId = (Get-Content -LiteralPath $WorkerPidFile -Raw).Trim()
    $startedWorkerProcess = Get-Process -Id ([int]$startedWorkerProcessId) -ErrorAction SilentlyContinue
    if ($null -eq $startedWorkerProcess) {
        Remove-Item -LiteralPath $WorkerPidFile -Force -ErrorAction SilentlyContinue
        throw "RAG worker exited during startup. Check $StateDir\rag-worker.err.log"
    }
}

$backendReady = Wait-Port -Name "Backend" -Port $BackendPort
$frontendReady = Wait-Port -Name "Frontend" -Port $FrontendPort

$backendUrl = "http://127.0.0.1:$BackendPort"
$frontendUrl = "http://localhost:$FrontendPort"
Write-Host ""
Write-Host "Backend:   $backendUrl"
Write-Host "Frontend:  $frontendUrl"
Write-Host "RAG MCP:   http://127.0.0.1:$RagPort/mcp"
Write-Host "RAG worker: running in watch mode"
Write-Host "Logs:      $StateDir"
Write-Host "Stop all:  .\scripts\start-dev.ps1 -Stop"

if ($OpenBrowser -and $frontendReady) {
    Start-Process $frontendUrl
}

if (-not ($backendReady -and $frontendReady -and $ragReady)) {
    exit 1
}
