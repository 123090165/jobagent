# 对本地 JobAgent 与 Modular RAG 执行最小实时同步和检索验收。
[CmdletBinding()]
param(
    [string]$EnvFile = ".env.deepseek.local",
    [switch]$SkipMcpInspection
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

function Resolve-ProjectPath {
    param([string]$Value)

    if ([System.IO.Path]::IsPathRooted($Value)) {
        return $Value
    }
    return Join-Path $ProjectRoot $Value
}

function Import-DotEnv {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Environment file not found: $Path"
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

        $key = $line.Substring(0, $separator).Trim()
        if ($key -notmatch "^[A-Za-z_][A-Za-z0-9_]*$") {
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
        [Environment]::SetEnvironmentVariable($key, $value, "Process")
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

if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Python virtual environment not found: $PythonExe"
}

$envPath = Resolve-ProjectPath -Value $EnvFile
Import-DotEnv -Path $envPath

Set-DefaultEnvironmentValue `
    -Name "JOBAGENT_RAG_MCP_URL" `
    -Value "http://127.0.0.1:8002/mcp"
Set-DefaultEnvironmentValue `
    -Name "JOBAGENT_RAG_MANAGEMENT_URL" `
    -Value "http://127.0.0.1:8002"

$env:JOBAGENT_RAG_SYNC_ENABLED = "true"
$env:JOBAGENT_RAG_LIVE_TEST = "1"

if ([string]::IsNullOrWhiteSpace($env:JOBAGENT_RAG_SERVICE_TOKEN)) {
    throw "JOBAGENT_RAG_SERVICE_TOKEN is missing from $envPath"
}
if ($env:JOBAGENT_RAG_SERVICE_TOKEN.Length -lt 32) {
    throw "JOBAGENT_RAG_SERVICE_TOKEN must contain at least 32 characters"
}

Set-Location -LiteralPath $ProjectRoot
Write-Host "Loaded RAG configuration from: $envPath"
Write-Host "MCP endpoint:        $env:JOBAGENT_RAG_MCP_URL"
Write-Host "Management endpoint: $env:JOBAGENT_RAG_MANAGEMENT_URL"
Write-Host "Service token:       configured (value hidden)"

if (-not $SkipMcpInspection) {
    Write-Host ""
    Write-Host "Checking MCP protocol and required tools..."
    $inspectionOutput = & $PythonExe -m scripts.inspect_rag_mcp 2>&1
    $inspectionExitCode = $LASTEXITCODE
    if ($inspectionExitCode -ne 0) {
        $inspectionOutput | Write-Host
        throw "MCP inspection failed with exit code $inspectionExitCode"
    }
    Write-Host "MCP inspection passed."
}

Write-Host ""
Write-Host "Running isolated live RAG lifecycle test..."
& $PythonExe -m pytest `
    tests/test_rag_live_integration.py `
    -q `
    -p no:cacheprovider
$testExitCode = $LASTEXITCODE

if ($testExitCode -eq 0) {
    Write-Host "Live RAG verification passed."
}
else {
    Write-Error "Live RAG verification failed with exit code $testExitCode"
}
exit $testExitCode
