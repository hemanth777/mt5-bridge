$ErrorActionPreference = "SilentlyContinue"

$Root = "C:\mt5-bridge"
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
