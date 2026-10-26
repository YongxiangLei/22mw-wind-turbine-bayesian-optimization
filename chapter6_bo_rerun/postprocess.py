"""
Post-processing of the Chapter 6 BO rerun: Table 6.2, convergence plot and Figs 6.2-6.5.

  python postprocess.py [--runs DIR] [--out DIR]

Inputs : runs/<tag>/metrics.json, gain_schedule.json, *.outb  (baseline, eval_001 ... eval_020)
Outputs: ch6_outputs/  table6_2.tex, results_table.csv, summary.json,
         fig6_2_wind.pdf, fig6_3_pitch.pdf, fig6_4_gains.pdf, fig6_5_power.pdf, fig6_x_convergence.pdf (+ .png)
"""
import argparse
import csv
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bo_rerun import read_outb, FST, P_REF, T_WIN  # noqa: E402

ROOT = os.path.dirname(os.path.abspath(__file__))
plt.rcParams.update({"font.family": "serif", "font.size": 11, "axes.labelsize": 11, "legend.fontsize": 9,
                     "xtick.labelsize": 10, "ytick.labelsize": 10, "axes.grid": True, "grid.alpha": 0.3,
                     "savefig.bbox": "tight"})
C_BASE, C_BEST = "#4C72B0", "#C44E52"


def load_runs(runs_dir):
    out, failed = [], []
    for tag in sorted(os.listdir(runs_dir)):
        m = os.path.join(runs_dir, tag, "metrics.json")
        # only the real evaluations (baseline, eval_001 ... eval_020); archived attempts and
        # screening / sensitivity runs live in differently named directories
        if (tag == "baseline" or (tag.startswith("eval_") and tag[5:].isdigit())) and os.path.exists(m):
            with open(m) as f:
                r = json.load(f)
            r["dir"] = os.path.join(runs_dir, tag)
            (out if r.get("status") == "OK" else failed).append(r)
    base = next((r for r in out if r["tag"] == "baseline"), None)
    evals = sorted((r for r in out if r["tag"] != "baseline"), key=lambda r: r["tag"])
    return base, evals, failed


def evno(r):
    return int(r["tag"].split("_")[1])


def kind_of(r):
    n = int(r["tag"].split("_")[1])
    return "random" if n <= 5 else f"BO-{(n - 6) // 5 + 1}"


def sig(x, n=3):
    return float(f"{x:.{n}g}")


def save(fig, out, name):
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(out, f"{name}.{ext}"), dpi=300)
    plt.close(fig)


def window(d):
    t = d["Time"]
    return (t >= T_WIN[0]) & (t <= T_WIN[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", default=os.path.join(ROOT, "runs"))
    ap.add_argument("--out", default=os.path.join(ROOT, "ch6_outputs"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    base, evals, failed = load_runs(a.runs)
    if base is None or not evals:
        sys.exit("baseline or evaluations missing")
    best = min(evals, key=lambda r: r["J_power_mse_kW2"])
    failed_evals = [r for r in failed if r["tag"] != "baseline"]

    # ---------------------------------------------------------------- table
    rows = [base] + evals
    with open(os.path.join(a.out, "results_table.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tag", "kind", "omega1", "omega2", "omega3", "J_kW2", "RMSE_kW", "J_old_last0.1s_kW2",
                    "genspd_mse_rpm2", "pitch_std_deg", "pitch_travel_deg", "twrbsmyt_std_kNm", "wall_h"])
        for r in rows:
            w.writerow([r["tag"], "baseline" if r is base else kind_of(r), *[f"{x:.4f}" for x in r["omega_pc"]],
                        f"{r['J_power_mse_kW2']:.1f}", f"{r['power_rmse_kW']:.2f}", f"{r['J_old_last0p1s_kW2']:.1f}",
                        f"{r['genspd_mse_rpm2']:.5f}", f"{r['pitch_std_deg']:.3f}", f"{r['pitch_travel_deg']:.1f}",
                        f"{r['twrbsmyt_std_kNm']:.0f}" if r.get("twrbsmyt_std_kNm") is not None else "",
                        f"{r['wall_s'] / 3600:.2f}"])

    lines = [r"\begin{table}[h]", r"\centering\small",
             r"\caption{Bayesian optimisation of the pitch-controller natural frequencies "
             r"$\omega_{pc}^{(1)},\omega_{pc}^{(2)},\omega_{pc}^{(3)}$ (rad/s) at $U_{pc}=12,18,24$~m/s. "
             r"$J$: generator-power MSE with respect to 22~MW over 100--300~s; RMSE $=\sqrt{J}$; "
             r"$J_{\text{old}}$: the objective of the original run (last 0.1~s of the simulation), shown for comparison only. "
             r"Evaluations 1--5 are random; 6--20 are proposed by the GP in three batches of five. "
             r"Bold: lowest $J$. ``n.c.'': the OpenFAST structural solver (BeamDyn) did not converge, no result.}",
             r"\label{tab:optimized_parameters}",
             r"\begin{tabular}{llccccccc}", r"\hline",
             r"Eval. & Type & $\omega_{pc}^{(1)}$ & $\omega_{pc}^{(2)}$ & $\omega_{pc}^{(3)}$ & "
             r"$J$ ($10^3$~kW$^2$) & RMSE (kW) & $J_{\text{old}}$ ($10^3$~kW$^2$) & Time (h) \\", r"\hline"]
    table_rows = [base] + sorted(evals + failed_evals, key=evno)
    for r in table_rows:
        lab = "Baseline" if r is base else str(evno(r))
        typ = "ROSCO default" if r is base else kind_of(r)
        if r.get("status") == "OK":
            cells = [lab, typ, *[f"{x:.3f}" for x in r["omega_pc"]],
                     f"{sig(r['J_power_mse_kW2'] / 1e3):#.3g}", f"{r['power_rmse_kW']:.1f}",
                     f"{sig(r['J_old_last0p1s_kW2'] / 1e3):#.3g}", f"{r['wall_s'] / 3600:.1f}"]
        else:
            cells = [lab, typ, *[f"{x:.3f}" for x in r["omega_pc"]], "n.c.", "--", "--", f"{r['wall_s'] / 3600:.1f}"]
        if r is best:
            cells = [r"\textbf{" + c + "}" for c in cells]
        lines.append(" & ".join(cells) + r" \\")
        if r is base:
            lines.append(r"\hline")
    lines += [r"\hline", r"\end{tabular}", r"\end{table}"]
    with open(os.path.join(a.out, "table6_2.tex"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # ---------------------------------------------------------------- convergence
    J = np.array([r["J_power_mse_kW2"] for r in evals]) / 1e3
    k = np.array([evno(r) for r in evals])
    n_all = max([evno(r) for r in evals + failed_evals])
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    kinds = [kind_of(r) for r in evals]
    for kd, mk, lab in [("random", "o", "random initial"), ("BO", "s", "GP-guided")]:
        sel = [i for i, x in enumerate(kinds) if x.startswith(kd)]
        ax.plot(k[sel], J[sel], mk, ms=6, mfc="none", color="0.3", label=lab)
    bsf = np.minimum.accumulate(J)
    ax.step(np.append(k, n_all), np.append(bsf, bsf[-1]), where="post", color=C_BEST, lw=1.8, label="best so far")
    ax.axhline(base["J_power_mse_kW2"] / 1e3, color=C_BASE, ls="--", lw=1.4, label="baseline (ROSCO default)")
    if failed_evals:
        ytop = base["J_power_mse_kW2"] / 1e3
        ax.plot([evno(r) for r in failed_evals], [ytop] * len(failed_evals), "x", ms=8, mew=1.6, color="k",
                label="solver did not converge")
    for b in (5.5, 10.5, 15.5):
        if b < n_all:
            ax.axvline(b, color="0.7", lw=0.8, ls=":")
    ax.set_xlabel("Evaluation"); ax.set_ylabel(r"$J$ [$10^3$ kW$^2$]"); ax.set_xticks(np.arange(1, n_all + 1))
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncol=3, frameon=False, handlelength=1.6, columnspacing=1.0)
    save(fig, a.out, "fig6_x_convergence")

    # ---------------------------------------------------------------- time series
    db = read_outb(os.path.join(base["dir"], FST.replace(".fst", ".outb")))
    dx = read_outb(os.path.join(best["dir"], FST.replace(".fst", ".outb")))
    wb, wx = window(db), window(dx)
    tb, tx = db["Time"][wb], dx["Time"][wx]
    lb = r"baseline $\omega_{pc}$=[" + ", ".join(f"{x:.3f}" for x in base["omega_pc"]) + "]"
    lx = f"BO best (eval. {int(best['tag'].split('_')[1])}) " + r"$\omega_{pc}$=[" + ", ".join(f"{x:.3f}" for x in best["omega_pc"]) + "]"

    # Fig 6.2 wind at hub height
    fig, ax = plt.subplots(figsize=(6.4, 3.0))
    u = db["Wind1VelX"][wb]
    ax.plot(tb, u, color="g", lw=0.8)
    ax.axhline(u.mean(), color="k", ls="--", lw=0.8, label=f"mean {u.mean():.1f} m/s, TI {u.std() / u.mean():.3f}")
    ax.set_xlabel("Time [s]"); ax.set_ylabel("Hub-height wind speed [m/s]"); ax.set_xlim(*T_WIN); ax.legend(loc="upper center")
    save(fig, a.out, "fig6_2_wind")

    # Fig 6.3 pitch
    fig, axs = plt.subplots(2, 1, figsize=(6.4, 5.0), gridspec_kw={"height_ratios": [2, 1]}, sharex=True)
    axs[0].plot(tb, db["BldPitch1"][wb], color=C_BASE, lw=1.0, label=lb)
    axs[0].plot(tx, dx["BldPitch1"][wx], color=C_BEST, lw=1.0, label=lx)
    axs[0].set_ylabel("Blade pitch [deg]"); axs[0].legend(loc="upper left")
    n = min(len(tb), len(tx))
    axs[1].plot(tb[:n], dx["BldPitch1"][wx][:n] - db["BldPitch1"][wb][:n], color="0.3", lw=0.8)
    axs[1].set_ylabel(r"$\Delta$ pitch [deg]"); axs[1].set_xlabel("Time [s]"); axs[1].set_xlim(*T_WIN)
    save(fig, a.out, "fig6_3_pitch")

    # Fig 6.4 gain schedules
    gs = []
    for r in (base, best):
        with open(os.path.join(r["dir"], "gain_schedule.json")) as f:
            gs.append(json.load(f))
    fig, ax = plt.subplots(2, 2, figsize=(7.0, 5.0), sharex=True, constrained_layout=True)
    for axi, key, ylab in zip(ax.flat, ["omega_pc", "zeta_pc", "Kp", "Ki"],
                              [r"$\omega_{pc}$ [rad/s]", r"$\zeta_{pc}$ [-]", r"$K_p$ [s]", r"$K_i$ [-]"]):
        axi.plot(gs[0]["v"], gs[0][key], color=C_BASE, lw=1.4, ls="--", label="baseline")
        axi.plot(gs[1]["v"], gs[1][key], color=C_BEST, lw=1.4, label="BO best")
        axi.set_ylabel(ylab)
    for axi in ax[1]:
        axi.set_xlabel("Wind speed [m/s]")
    ax[0, 0].legend()
    save(fig, a.out, "fig6_4_gains")

    # Fig 6.5 power output (MW), y-axis scaled to the data around the 22 MW reference
    eb, ex = db["GenPwr"][wb] - P_REF, dx["GenPwr"][wx] - P_REF
    pb, px = db["GenPwr"][wb] / 1e3, dx["GenPwr"][wx] / 1e3
    pref = P_REF / 1e3
    half = (np.ceil(max(np.abs(eb).max(), np.abs(ex).max()) / 50.0) * 50.0 + 50.0) / 1e3   # MW, rounded up + margin
    fig, axs = plt.subplots(3, 1, figsize=(6.4, 7.6), constrained_layout=True)
    axs[0].plot(tb, pb, color=C_BASE, lw=0.6, label=f"baseline (RMSE {np.sqrt(np.mean(eb ** 2)):.1f} kW)")
    axs[0].plot(tx, px, color=C_BEST, lw=0.6, alpha=0.8, label=f"BO best (RMSE {np.sqrt(np.mean(ex ** 2)):.1f} kW)")
    axs[0].axhline(pref, color="k", ls="--", lw=1.0, label=f"reference {pref:.0f} MW")
    z0, z1 = 150.0, 170.0
    axs[0].axvspan(z0, z1, color="0.88", zorder=0)
    axs[0].set_ylim(pref - half, pref + half)
    axs[0].set_xlabel("Time [s]"); axs[0].set_ylabel("Generator power [MW]"); axs[0].set_xlim(*T_WIN)
    axs[0].legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3, frameon=False, columnspacing=1.0)
    zb, zx = (tb >= z0) & (tb <= z1), (tx >= z0) & (tx <= z1)
    axs[1].plot(tb[zb], pb[zb], color=C_BASE, lw=1.0)
    axs[1].plot(tx[zx], px[zx], color=C_BEST, lw=1.0)
    axs[1].axhline(pref, color="k", ls="--", lw=1.0)
    axs[1].set_ylim(pref - half, pref + half)
    axs[1].set_xlim(z0, z1); axs[1].set_xlabel("Time [s] (zoom of the shaded interval)"); axs[1].set_ylabel("Generator power [MW]")
    bins = np.linspace(min(eb.min(), ex.min()), max(eb.max(), ex.max()), 60)
    axs[2].hist(eb, bins=bins, density=True, histtype="step", color=C_BASE, lw=1.4, label="baseline")
    axs[2].hist(ex, bins=bins, density=True, histtype="step", color=C_BEST, lw=1.4, label="BO best")
    axs[2].set_xlabel(r"$P_{gen}-P_{ref}$ [kW]"); axs[2].set_ylabel("Density"); axs[2].legend()
    save(fig, a.out, "fig6_5_power")

    # ---------------------------------------------------------------- summary
    jb, jx = base["J_power_mse_kW2"], best["J_power_mse_kW2"]
    old = np.array([r["J_old_last0p1s_kW2"] for r in evals]); new = np.array([r["J_power_mse_kW2"] for r in evals])
    summ = {
        "n_evals": len(evals), "failed_evals": [r["tag"] for r in failed_evals], "baseline": {k_: base[k_] for k_ in ("omega_pc", "J_power_mse_kW2", "power_rmse_kW",
                                                                     "genspd_mse_rpm2", "pitch_std_deg", "pitch_travel_deg", "twrbsmyt_std_kNm")},
        "best": {k_: best[k_] for k_ in ("tag", "omega_pc", "J_power_mse_kW2", "power_rmse_kW",
                                          "genspd_mse_rpm2", "pitch_std_deg", "pitch_travel_deg", "twrbsmyt_std_kNm")},
        "J_reduction_vs_baseline_pct": 100 * (jb - jx) / jb,
        "rmse_reduction_vs_baseline_pct": 100 * (np.sqrt(jb) - np.sqrt(jx)) / np.sqrt(jb),
        "best_found_at_eval": int(best["tag"].split("_")[1]),
        "spearman_old_vs_new_J": float(np.corrcoef(np.argsort(np.argsort(old)), np.argsort(np.argsort(new)))[0, 1]),
        "evals_better_than_baseline": int(np.sum(new < jb)),
        "Kp_sign_change_best": bool(np.any(np.array(gs[1]["Kp"]) > 0)),
        "Kp_sign_change_baseline": bool(np.any(np.array(gs[0]["Kp"]) > 0)),
        "wind_hub_mean_ms": base["wind_mean_ms"], "wind_hub_TI": base["wind_std_ms"] / base["wind_mean_ms"],
        "total_cpu_h": float(sum(r["wall_s"] for r in [base] + evals) / 3600),
    }
    with open(os.path.join(a.out, "summary.json"), "w") as f:
        json.dump(summ, f, indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
