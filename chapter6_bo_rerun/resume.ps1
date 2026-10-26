# Resume the BO rerun after pause.ps1, a reboot or a crash.
#  * frozen (suspended) processes present -> thaw them; the simulations continue where they were.
#  * nothing running                     -> relaunch; finished runs (metrics.json OK) are skipped,
#                                           stored GP suggestions are reused, unfinished runs restart at t = 0.
$root = "$PSScriptRoot"
. "$root\env_d.ps1"
. "$root\proc_suspend.ps1"
$procs = @(Get-RunProcesses)

function Start-Watcher {
    $w = Start-Process -FilePath powershell.exe -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "$root\auto_post.ps1" `
         -WorkingDirectory $root -WindowStyle Hidden -PassThru
    $w.Id | Out-File -Encoding ascii "$root\auto_post.pid"
}

if ($procs.Count -gt 0) {
    if (-not (Test-RunSuspended)) { "Run is already active ($($procs.Count) env processes) - nothing to do."; exit 1 }
    foreach ($n in 'openfast.exe', 'python.exe') {
        $procs | Where-Object Name -eq $n | ForEach-Object { [void][ProcCtl]::Resume([int]$_.ProcessId) }
    }
    Start-Sleep -Seconds 2
    $thawed = -not (Test-RunSuspended)
    Add-Content -Encoding utf8 "$root\rerun.log" "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  RESUMED (thawed suspended processes, ok=$thawed) by resume.ps1"
    Start-Watcher
    "Resumed frozen run (ok=$thawed). Progress: $root\rerun.log"
    exit 0
}

if (Test-Path "$root\rerun_console.txt") {
    Move-Item "$root\rerun_console.txt" ("$root\logs\rerun_console_" + (Get-Date -Format 'yyyyMMdd_HHmmss') + ".txt") -Force
}
Add-Content -Encoding utf8 "$root\rerun.log" "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  RESUMED (relaunch; unfinished runs restart at t = 0) by resume.ps1"
$p = Start-Process -FilePath powershell.exe -ArgumentList "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "$root\launch.ps1" `
     -WorkingDirectory $root -WindowStyle Hidden -PassThru
$p.Id | Out-File -Encoding ascii "$root\launcher.pid"
Start-Sleep -Seconds 10   # let micromamba/python start before the watcher checks for live processes
Start-Watcher
"Relaunched. launcher pid $($p.Id). Progress: $root\rerun.log and $root\results.csv"
