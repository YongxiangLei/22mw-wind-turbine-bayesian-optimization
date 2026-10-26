# Redirect every user-level path to drive D so nothing is created on C:
# micromamba root (override with $env:BO_MAMBA_ROOT); all user-level paths are redirected to <script dir>\_sys
$mroot = if ($env:BO_MAMBA_ROOT) { $env:BO_MAMBA_ROOT } else { "D:\software\micromamba" }
$base = "$PSScriptRoot\_sys"
foreach ($sub in 'tmp','home','appdata','localappdata','pip-cache','mpl','xdg-cache','xdg-config') {
    New-Item -ItemType Directory -Force (Join-Path $base $sub) | Out-Null
}
$env:TEMP = "$base\tmp"; $env:TMP = "$base\tmp"
$env:HOME = "$base\home"; $env:USERPROFILE = "$base\home"
$env:APPDATA = "$base\appdata"; $env:LOCALAPPDATA = "$base\localappdata"
$env:PIP_CACHE_DIR = "$base\pip-cache"; $env:MPLCONFIGDIR = "$base\mpl"
$env:XDG_CACHE_HOME = "$base\xdg-cache"; $env:XDG_CONFIG_HOME = "$base\xdg-config"
$env:PYTHONNOUSERSITE = "1"
$env:MAMBA_ROOT_PREFIX = $mroot
$env:CONDA_PKGS_DIRS = "$mroot\pkgs"
$env:MAMBA_EXE = "$mroot\micromamba.exe"
$env:ROSCO_ENV = "$mroot\envs\rosco-env"
# env binaries first on PATH (python, openfast, libdiscon)
$env:PATH = "$env:ROSCO_ENV;$env:ROSCO_ENV\Library\bin;$env:ROSCO_ENV\Scripts;$env:ROSCO_ENV\Library\mingw-w64\bin;$env:PATH"
