param([string]$Name, [string]$Ref)
. "$PSScriptRoot\env_d.ps1"
$root = "$PSScriptRoot"
$d = "$root\runs\$Name"
Add-Content -Encoding utf8 "$root\rerun.log" "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $Name started (InterpOrder=1 sensitivity run of $Ref)"
Set-Location $d
$t0 = Get-Date
cmd /c "`"$env:MAMBA_EXE`" run -p `"$env:ROSCO_ENV`" openfast IEA-22-280-RWT-Monopile.fst > openfast_stdout.txt 2>&1"
$rc = $LASTEXITCODE
$wall = ((Get-Date) - $t0).TotalSeconds
Set-Location $root
cmd /c "`"$env:MAMBA_EXE`" run -p `"$env:ROSCO_ENV`" python -u case_metrics.py $Name $Ref $rc $wall > logs\case_metrics_$Name.txt 2>&1"
