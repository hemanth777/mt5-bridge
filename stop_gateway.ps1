$ErrorActionPreference = "SilentlyContinue"

$ScriptRoot = $PSScriptRoot
if (-not $ScriptRoot) { $ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path }
$EnvFile = Join-Path $ScriptRoot ".env"

if (Test-Path $EnvFile) {
  Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
    $name, $value = $_ -split '=', 2
    if ($name) {
      [Environment]::SetEnvironmentVariable($name.Trim(), ($value -as [string]).Trim(), "Process")
    }
  }
}

$Root = if ($env:BRIDGE_ROOT) { $env:BRIDGE_ROOT } else { $ScriptRoot }
$Mt5PidFile = Join-Path $Root "mt5.pid"
$ApiPidFile = Join-Path $Root "gateway.pid"

function Stop-FromPidFile($file) {
  if (Test-Path $file) {
    $pid = (Get-Content $file | Select-Object -First 1).Trim()
    if ($pid -match '^\d+$') {
      Stop-Process -Id ([int]$pid) -Force
    }
    Remove-Item $file -Force
  }
}

# Stop gateway first, then MT5 instance owned by this gateway
Stop-FromPidFile $ApiPidFile
Stop-FromPidFile $Mt5PidFile
