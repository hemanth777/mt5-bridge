$ErrorActionPreference = "Stop"

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
$Mt5Dir = if ($env:MT5_DIR) { $env:MT5_DIR } else { "C:\mt5\ExnessDemo" }
$Mt5Exe = if ($env:MT5_EXE) { $env:MT5_EXE } else { (Join-Path $Mt5Dir "terminal64.exe") }
$Mt5Args = "/portable"
$Mt5PidFile = Join-Path $Root "mt5.pid"
$ApiPidFile = Join-Path $Root "gateway.pid"
$StopScript = Join-Path $Root "stop_gateway.ps1"

# Stop only if gateway PID is running
$shouldStop = $false
if (Test-Path $ApiPidFile) {
  $pidText = (Get-Content $ApiPidFile | Select-Object -First 1).Trim()
  if ($pidText -match '^\d+$') {
    $p = Get-Process -Id ([int]$pidText) -ErrorAction SilentlyContinue
    if ($p) { $shouldStop = $true }
  }
}
if ($shouldStop -and (Test-Path $StopScript)) {
  & powershell.exe -ExecutionPolicy Bypass -File $StopScript
  Start-Sleep -Seconds 1
}

Set-Location $Root

# Activate venv
& "$Root\.venv\Scripts\Activate.ps1"

# Start dedicated MT5 instance and save PID
$mt5 = Start-Process -FilePath $Mt5Exe -ArgumentList $Mt5Args -PassThru -WindowStyle Minimized
$mt5.Id | Out-File -FilePath $Mt5PidFile -Encoding ascii -Force

# Start gateway and save PID
$api = Start-Process -FilePath "python.exe" `
  -ArgumentList "-m uvicorn api_gateway:app --host 0.0.0.0 --port 8080" `
  -PassThru -WindowStyle Hidden
$api.Id | Out-File -FilePath $ApiPidFile -Encoding ascii -Force
