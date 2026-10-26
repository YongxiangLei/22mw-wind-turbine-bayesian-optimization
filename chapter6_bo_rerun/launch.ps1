. "$PSScriptRoot\env_d.ps1"
Set-Location $PSScriptRoot
& $env:MAMBA_EXE run -p $env:ROSCO_ENV python -u bo_rerun.py run --n-iter 15 --batch 5 *> "$PSScriptRoot\rerun_console.txt"
"exit=$LASTEXITCODE  $(Get-Date -Format s)" | Out-File -Append -Encoding utf8 "$PSScriptRoot\rerun_console.txt"
