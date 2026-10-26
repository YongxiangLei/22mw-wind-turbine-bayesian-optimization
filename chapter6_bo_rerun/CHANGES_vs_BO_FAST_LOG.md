# bo_rerun.py vs. the original Chapter 6 code (BO_FAST_LOG.py)

Original: `IEA-22-280-RWT-Monopile/BO_FAST_LOG.py`
(run 2025-09-15 → 2025-09-17, log `optimization_logs_20250915_111744/`).
Rerun:    `chapter6_bo_rerun/bo_rerun.py`.

## Unchanged
- Design variable: ω_pc at the three ROSCO breakpoints U_pc = 12 / 18 / 24 m/s; ζ_pc fixed
  ([0.847, 1.756, 0.744]); other ROSCO settings from `IEA-22-280-RWT-Monopile.yaml`.
- Bounds: ω_pc1 ∈ [0.1, 0.2], ω_pc2 ∈ [0.1, 0.2], ω_pc3 ∈ [0.1, 0.5] rad/s.
- Pipeline per candidate: `load_rosco_yaml` → `Turbine.load_from_fast` → `Controller.tune_controller`
  (Kp = (2ζω + A)/B, Ki = ω²/B) → `write_DISCON` → OpenFAST → power MSE vs 22 000 kW.
- Turbine model, 300 s simulation (TMax), DT = 0.0002 s, wind field `TurbSim.bts`.
- 5 random initial points with seed 42: identical to iterations 1–5 of the original run.

## Changed (and why)
| Item | BO_FAST_LOG.py | bo_rerun.py | Reason |
|---|---|---|---|
| Objective window | last 500 samples = last 0.1 s (DT_Out = 0.0002 s) | 100–300 s | a 0.1 s window measures the power at a single instant |
| Baseline | not run | ROSCO default ω_pc, same J | reference value for the improvement |
| BO budget | 5 random + 5 GP (sequential) | 5 random + 15 GP, 3 rounds × 5 in parallel (Kriging Believer) | non-converged; run time |
| Acquisition | bayes_opt default (version not recorded) | bayes_opt 3.3.0 default UCB, κ = 2.576 | documented |
| Run directories | shared; outb / DISCON overwritten | one directory per evaluation | traceability of Figs 6.3–6.5 |
| Output step | DT_Out default (0.0002 s), 213 MB/run | 0.01 s, ~4 MB/run | size only; no effect on dynamics |
| Wind probe | z = 310 m (WindVziList) | z = 170 m (hub height) | Fig 6.2 shows hub-height wind; output only |
| ROSCO LoggingLevel | 2 | 0 | debug files only; no effect on control |
| Software | OpenFAST 3.5.0, ROSCO 2.9.4 | OpenFAST 3.5.2, ROSCO 2.9.4 | 3.5.0 not available for win-64 on conda-forge |
| Paths | `openfast_x64.exe`, absolute paths to `libdiscon.dll` and `TurbSim.bts` | binaries of the micromamba environment, local copy of the same .bts | portability |
| Extra metrics | – | RMSE, gen-speed MSE, pitch std/travel, TwrBsMyt std, last-0.1 s MSE | discussion / comparison |
| Numerical failure | – | evaluation 17 diverged in BeamDyn at t = 80.704 s with `InterpOrder` = 2 (also with `NRMax` = 30); re-run with `InterpOrder` = 1 (`finalize_eval017.py`, `rerun_eval017.ps1`); baseline and eval_018 repeated with `InterpOrder` = 1 change J by < 0.001 % (`sens_prepare.py`, `run_sens_case.ps1`, `case_metrics.py`) | complete the 20-evaluation budget |
