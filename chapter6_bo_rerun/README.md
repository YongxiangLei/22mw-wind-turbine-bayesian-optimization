# Bayesian optimisation of the ROSCO pitch controller – IEA 22 MW monopile (Chapter 6)

Code for the batch Bayesian optimisation (BO) of the collective pitch controller of the
IEA 22 MW monopile reference turbine with OpenFAST and ROSCO. The decision variables are the
three scheduled natural frequencies of the ROSCO pitch loop, `omega_pc` at `U_pc` = 12, 18 and 24 m/s;
the PI gain schedules follow from them through the ROSCO pole-placement equations
(`Kp = (2 zeta omega + A)/B`, `Ki = omega^2/B`).

This folder contains code and environment definitions only. Simulation results
(`runs/`, `ch6_outputs/`, logs) are not part of the repository; see `.gitignore`.
The OpenFAST model is the one in `../IEA-22-280-RWT-Monopile/`. Differences from the original
script `../IEA-22-280-RWT-Monopile/BO_FAST_LOG.py` are listed in `CHANGES_vs_BO_FAST_LOG.md`.

## Method
- Objective: `J` = mean squared error of the generator power w.r.t. 22 MW over 100–300 s of a
  300 s simulation (one turbulent TurbSim field, `Wind/ExampleFiles/TurbSim.bts`, 18.2 m/s at 170 m).
- Search space: `omega_pc1, omega_pc2` in [0.10, 0.20] rad/s, `omega_pc3` in [0.10, 0.50] rad/s; damping ratios fixed.
- Baseline: ROSCO default `omega_pc` = [0.104, 0.113, 0.289] rad/s, evaluated with the same `J`.
- BO: `bayes_opt` 3.3.0, GP with Matérn-5/2 kernel, UCB (kappa = 2.576); 5 random initial points
  (seed 42) followed by 15 GP-guided points in 3 parallel batches of 5 (Kriging Believer).

## Requirements
Windows, a micromamba environment `rosco-env` (Python 3.10, ROSCO 2.9.4, OpenFAST 3.5.2, bayes_opt 3.3.0):

```powershell
micromamba create -p <micromamba-root>\envs\rosco-env --file rosco-env.explicit.txt   # exact builds
# or: micromamba create -p <micromamba-root>\envs\rosco-env -f rosco-env.yml
```

`env_d.ps1` sets the environment variables used by all scripts. Set `$env:BO_MAMBA_ROOT` to your
micromamba root (default `D:\software\micromamba`); it also redirects TEMP/HOME/APPDATA and package
caches to `_sys\` next to the scripts. `BO_MODEL_DIR` overrides the model directory.
Run Python through `micromamba run` (the environment must be activated for the DLLs to load).

## Usage
```powershell
. .\env_d.ps1
& $env:MAMBA_EXE run -p $env:ROSCO_ENV python bo_rerun.py setup    # copy model to runs\ (template + shared files)
& $env:MAMBA_EXE run -p $env:ROSCO_ENV python bo_rerun.py test     # 5 s smoke test
.\launch.ps1                                                 # full run: baseline + 20 evaluations (~8 h on 16 cores)
.\pause.ps1  [-Mode Suspend|Stop]                            # pause; .\resume.ps1 continues (finished runs are kept)
& $env:MAMBA_EXE run -p $env:ROSCO_ENV python postprocess.py       # Table 6.2, Figs 6.2–6.5, convergence -> ch6_outputs\
& $env:MAMBA_EXE run -p $env:ROSCO_ENV python extra_analysis.py    # baseline vs best: block J, DELs (Table 6.3)
& $env:MAMBA_EXE run -p $env:ROSCO_ENV python plot_fig6_5_single.py
```
`auto_post.ps1` runs `postprocess.py` automatically when the optimisation finishes.

## Files
| File | Purpose |
|---|---|
| `bo_rerun.py` | set-up, smoke test and batch BO loop (OpenFAST + ROSCO toolbox + bayes_opt) |
| `postprocess.py`, `plot_fig6_5_single.py` | results table and figures |
| `extra_analysis.py` | 50 s block analysis, rainflow DELs, baseline vs best table |
| `finalize_eval017.py`, `rerun_eval017.ps1` | re-run of evaluation 17 (BeamDyn divergence with `InterpOrder` = 2) |
| `screen_eval017.py`, `run_screen_case.ps1` | 90 s screening of numerical fixes (DT, NumCrctn, InterpOrder) |
| `sens_prepare.py`, `run_sens_case.ps1`, `case_metrics.py` | baseline and best repeated with `InterpOrder` = 1 |
| `check_*.py`, `numbers_for_text.py` | diagnostics used for the chapter text (failure analysis, thrust, tower bands, rainflow check) |
| `env_d.ps1`, `launch.ps1`, `pause.ps1`, `resume.ps1`, `proc_suspend.ps1`, `auto_post.ps1` | environment and run control |
| `rosco-env.yml`, `rosco-env.explicit.txt` | environment specification |

## Notes
- One OpenFAST run takes about 2 h of single-core CPU time; the batch scheme runs 5–6 at once.
- If Windows Smart App Control is enabled, it may block unsigned DLLs of scipy/scikit-learn
  (`bayes_opt`, ROSCO toolbox). OpenFAST and the numpy-only post-processing are not affected.
