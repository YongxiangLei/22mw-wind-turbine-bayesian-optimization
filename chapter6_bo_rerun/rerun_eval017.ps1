# Re-run evaluation 17 of the Chapter 6 BO (all on D:). OpenFAST + numpy only.
# Attempts with InterpOrder=2 failed at t=80.704 s (BeamDyn); this run uses InterpOrder=1.
. "$PSScriptRoot\env_d.ps1"
$root = "$PSScriptRoot"
$run  = "$root\runs\eval_017"
Add-Content -Encoding utf8 "$root\rerun.log" "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  eval_017 full re-run started (InterpOrder 2 -> 1, NRMax 30, load_retries 50; pid $PID)"
Set-Location $run
$t0 = Get-Date
cmd /c "`"$env:MAMBA_EXE`" run -p `"$env:ROSCO_ENV`" openfast IEA-22-280-RWT-Monopile.fst > openfast_stdout.txt 2>&1"
$rc = $LASTEXITCODE
$wall = ((Get-Date) - $t0).TotalSeconds
Set-Location $root
cmd /c "`"$env:MAMBA_EXE`" run -p `"$env:ROSCO_ENV`" python -u finalize_eval017.py $rc $wall > logs\finalize_eval017_console.txt 2>&1"
