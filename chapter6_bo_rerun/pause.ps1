# Pause the BO rerun.
#   -Mode Suspend (default): freeze python + openfast in memory; resume.ps1 continues exactly where they were.
#                            Lost if the PC reboots -> resume.ps1 then restarts unfinished runs from t = 0.
#   -Mode Stop             : terminate everything; resume.ps1 restarts unfinished runs from t = 0.
# Completed evaluations (runs\*\metrics.json with status OK) are always kept.
param([ValidateSet('Suspend', 'Stop')][string]$Mode = 'Suspend')
. "$PSScriptRoot\env_d.ps1"
. "$PSScriptRoot\proc_suspend.ps1"
$root = "$PSScriptRoot"
$lp = 0; if (Test-Path "$root\launcher.pid") { $lp = [int](Get-Content "$root\launcher.pid") }
$wp = 0; if (Test-Path "$root\auto_post.pid") { $wp = [int](Get-Content "$root\auto_post.pid") }
$procs = @(Get-RunProcesses)
$snap = foreach ($p in $procs) {
    $gp = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
    [pscustomobject]@{ pid = $p.ProcessId; name = $p.Name; cpu_s = if ($gp) { [int]$gp.CPU } else { $null }; cmd = $p.CommandLine }
}
# the watcher is a plain powershell process; stop it in both modes (resume.ps1 restarts it)
if ($wp) { Stop-Process -Id $wp -Force -ErrorAction SilentlyContinue }

if ($Mode -eq 'Suspend') {
    # python first so it cannot react while the solvers are being frozen
    foreach ($n in 'python.exe', 'openfast.exe') {
        $procs | Where-Object Name -eq $n | ForEach-Object { [void][ProcCtl]::Suspend([int]$_.ProcessId) }
    }
    Start-Sleep -Seconds 2
    $ok = Test-RunSuspended
} else {
    foreach ($n in 'python.exe', 'openfast.exe', 'micromamba.exe') {
        $procs | Where-Object Name -eq $n | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    }
    if ($lp) { Stop-Process -Id $lp -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
    $ok = (@(Get-RunProcesses).Count -eq 0)
}

$runs = Get-ChildItem "$root\runs" -Directory | Where-Object { $_.Name -match '^(baseline|eval_\d+)$' } | ForEach-Object {
    $par = if (Test-Path "$($_.FullName)\parameters.json") { Get-Content "$($_.FullName)\parameters.json" -Raw | ConvertFrom-Json } else { $null }
    $done = $false
    if (Test-Path "$($_.FullName)\metrics.json") {
        try { $done = ((Get-Content "$($_.FullName)\metrics.json" -Raw | ConvertFrom-Json).status -eq 'OK') } catch { $done = $false }
    }
    [pscustomobject]@{ tag = $_.Name; completed = $done; omega_pc = if ($par) { $par.omega_pc } else { $null } }
}
$state = [pscustomobject]@{
    paused_at = (Get-Date -Format s)
    mode = $Mode
    pause_verified = $ok
    approx_progress_of_running = if ($snap) { "{0:P0}" -f ((($snap | Where-Object name -eq 'openfast.exe' | Measure-Object cpu_s -Average).Average) / 6700) } else { $null }
    processes = $snap
    runs = $runs
    completed = @($runs | Where-Object completed).Count
    resume_command = "powershell -NoProfile -ExecutionPolicy Bypass -File $root\resume.ps1"
    note = "Suspend mode keeps the frozen processes in RAM; after a reboot resume.ps1 restarts unfinished runs from t = 0."
}
$state | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 "$root\pause_state.json"
Add-Content -Encoding utf8 "$root\rerun.log" ("$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  PAUSED ($Mode, verified=$ok) by pause.ps1: " +
    "$($state.completed) evaluation(s) complete; running ones at ~$($state.approx_progress_of_running)")
$state | Select-Object paused_at, mode, pause_verified, approx_progress_of_running, completed | Format-List
$runs | Format-Table -AutoSize
