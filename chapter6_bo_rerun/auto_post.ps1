# Detached watcher (all on D:): when the BO rerun writes final_results.json, run postprocess.py once.
. "$PSScriptRoot\env_d.ps1"
$root = "$PSScriptRoot"
$log = "$root\logs\auto_post.log"
Add-Content -Encoding utf8 $log "$(Get-Date -Format s)  watcher started (pid $PID)"
while (-not (Test-Path "$root\final_results.json")) {
    $alive = @(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like "$env:MAMBA_ROOT_PREFIX*" }).Count
    if ($alive -eq 0) {
        Add-Content -Encoding utf8 $log "$(Get-Date -Format s)  run stopped without final_results.json (paused or failed); watcher exits"
        exit 1
    }
    Start-Sleep -Seconds 300
}
Set-Location $root
& $env:MAMBA_EXE run -p $env:ROSCO_ENV python postprocess.py *> "$root\logs\postprocess_console.txt"
Add-Content -Encoding utf8 $log "$(Get-Date -Format s)  postprocess finished, exit=$LASTEXITCODE; outputs in $root\ch6_outputs"
