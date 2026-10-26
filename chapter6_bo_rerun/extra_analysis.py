"""
Supplementary analysis of the Chapter 6 rerun (no new simulations):
  * J in four 50-s blocks (consistency of the baseline-vs-best difference over the 200-s window)
  * damage-equivalent loads (rainflow, 1-Hz equivalent) of tower-base and blade-root moments
  * rotor-speed / pitch statistics for baseline and BO best
  * state of the failed evaluation (eval_017) before the solver abort
Writes ch6_outputs/extra_analysis.json and ch6_outputs/table6_3.tex
"""
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from bo_rerun import read_outb, FST, P_REF, T_WIN  # noqa: E402

RUNS = os.path.join(ROOT, "runs")
OUT = os.path.join(ROOT, "ch6_outputs")
OUTB = FST.replace(".fst", ".outb")


def turning_points(x):
    dx = np.diff(x)
    keep = np.concatenate(([True], dx[1:] * dx[:-1] < 0, [True]))
    x = x[keep]
    # remove flat repeats
    return x[np.concatenate(([True], np.diff(x) != 0))]


def rainflow(x):
    """ASTM E1049 three-point rainflow; returns (ranges, counts)."""
    tp = turning_points(np.asarray(x, float))
    stack, ranges, counts = [], [], []
    for p in tp:
        stack.append(p)
        while len(stack) >= 3:
            r1 = abs(stack[-2] - stack[-3])
            r2 = abs(stack[-1] - stack[-2])
            if r2 < r1:
                break
            if len(stack) == 3:
                ranges.append(r1); counts.append(0.5)
                stack.pop(0)
            else:
                ranges.append(r1); counts.append(1.0)
                last = stack.pop(); stack.pop(); stack.pop(); stack.append(last)
    for i in range(len(stack) - 1):
        ranges.append(abs(stack[i + 1] - stack[i])); counts.append(0.5)
    return np.array(ranges), np.array(counts)


def del_1hz(x, t, m):
    r, n = rainflow(x)
    neq = (t[-1] - t[0]) * 1.0
    return float((np.sum(n * r ** m) / neq) ** (1.0 / m))


def stats(tag):
    d = read_outb(os.path.join(RUNS, tag, OUTB))
    t = d["Time"]; w = (t >= T_WIN[0]) & (t <= T_WIN[1])
    tt = t[w]
    p = d["GenPwr"][w]; gs = d["GenSpeed"][w]; pit = d["BldPitch1"][w]
    with open(os.path.join(RUNS, tag, "metrics.json")) as f:
        m = json.load(f)
    rated = 0.739436 * 60 / (2 * np.pi)
    blocks = []
    for a in np.arange(T_WIN[0], T_WIN[1], 50.0):
        s = (tt >= a) & (tt < a + 50.0)
        blocks.append(float(np.mean((p[s] - P_REF) ** 2)))
    pr = np.diff(pit) / np.diff(tt)
    res = {
        "tag": tag, "omega_pc": m["omega_pc"],
        "J": m["J_power_mse_kW2"], "power_rmse_kW": m["power_rmse_kW"], "J_blocks_50s": blocks,
        "genspd_rmse_rpm": float(np.sqrt(np.mean((gs - rated) ** 2))),
        "genspd_max_rpm": float(gs.max()), "genspd_overspeed_pct": float(100 * (gs.max() / rated - 1)),
        "pitch_std_deg": float(np.std(pit)), "pitch_travel_deg": float(np.sum(np.abs(np.diff(pit)))),
        "pitch_rate_rms_degps": float(np.sqrt(np.mean(pr ** 2))), "pitch_rate_max_degps": float(np.max(np.abs(pr))),
    }
    for ch, mm in (("TwrBsMyt", 4), ("TwrBsMxt", 4), ("RootMyc1", 10), ("RootMyb1", 10)):
        if ch in d:
            res[f"DEL_{ch}_m{mm}"] = del_1hz(d[ch][w], tt, mm)
            res[f"std_{ch}"] = float(np.std(d[ch][w]))
    return res


def main():
    with open(os.path.join(OUT, "summary.json")) as f:
        summ = json.load(f)
    base = stats("baseline")
    best = stats(summ["best"]["tag"])
    rel = {k: 100 * (best[k] - base[k]) / base[k] for k in base
           if isinstance(base[k], float) and base[k] != 0}
    rel_blocks = [100 * (b2 - b1) / b1 for b1, b2 in zip(base["J_blocks_50s"], best["J_blocks_50s"])]

    # failed evaluation
    fail = {}
    p17 = os.path.join(RUNS, "eval_017", OUTB)
    if os.path.exists(p17) and os.path.getsize(p17) > 1000:
        try:
            d = read_outb(p17)
            t = d["Time"]
            fail = {"t_end": float(t[-1]), "genspd_max_rpm": float(d["GenSpeed"].max()),
                    "pitch_range_deg": [float(d["BldPitch1"].min()), float(d["BldPitch1"].max())]}
        except Exception as e:  # truncated file
            fail = {"error": str(e)}
    with open(os.path.join(RUNS, "eval_017", "metrics.json")) as f:
        fail["omega_pc"] = json.load(f)["omega_pc"]
    log = open(os.path.join(RUNS, "eval_017", "openfast_stdout.txt"), errors="ignore").read()
    fail["message"] = [l.strip() for l in log.splitlines() if "converge" in l or "error at simulation time" in l]

    # wind
    d = read_outb(os.path.join(RUNS, "baseline", OUTB))
    t = d["Time"]; w = (t >= T_WIN[0]) & (t <= T_WIN[1]); u = d["Wind1VelX"][w]
    wind = {"mean": float(u.mean()), "std": float(u.std()), "TI": float(u.std() / u.mean()),
            "min": float(u.min()), "max": float(u.max())}

    out = {"baseline": base, "best": best, "rel_change_pct": rel, "J_block_change_pct": rel_blocks,
           "failed_eval_017": fail, "wind_hub_100_300s": wind}
    with open(os.path.join(OUT, "extra_analysis.json"), "w") as f:
        json.dump(out, f, indent=1)

    def row(label, key, fmt, scale=1.0):
        a, b = base[key] * scale, best[key] * scale
        return f"{label} & {a:{fmt}} & {b:{fmt}} & {100 * (b - a) / a:+.0f}\\% \\\\"

    lines = [r"\begin{table}[h]", r"\centering\small",
             r"\caption{Baseline (ROSCO default $\omega_{pc}$) and BO-best controller (evaluation "
             + summ["best"]["tag"].split("_")[1].lstrip("0") +
             r") over 100--300~s of the same turbulent wind field. DEL: 1-Hz damage-equivalent load from rainflow counting "
             r"with W\"ohler exponent $m=4$ (steel tower). Pitch statistics refer to blade~1.}",
             r"\label{tab:baseline_vs_best}", r"\begin{tabular}{lccc}", r"\hline",
             r"Metric & Baseline & BO best & Change \\", r"\hline",
             row(r"Power MSE $J$ ($10^3$~kW$^2$)", "J", ".2f", 1e-3),
             row("Power RMSE (kW)", "power_rmse_kW", ".1f"),
             row("Generator-speed RMSE (rpm)", "genspd_rmse_rpm", ".3f"),
             row("Max.\\ generator speed (rpm)", "genspd_max_rpm", ".2f"),
             row("Pitch std (deg)", "pitch_std_deg", ".2f"),
             row("Pitch travel (deg)", "pitch_travel_deg", ".1f"),
             row("RMS pitch rate (deg/s)", "pitch_rate_rms_degps", ".3f")]
    for ch, lab in (("TwrBsMyt", "Tower-base fore-aft"), ("TwrBsMxt", "Tower-base side-side"),
                    ("RootMyc1", "Blade-1 root flapwise"), ("RootMyb1", "Blade-1 root out-of-plane")):
        for k in base:
            if k.startswith(f"DEL_{ch}_"):
                mm = k.split("_m")[-1]
                lines.append(row(f"{lab} DEL, $m={mm}$ (MN\\,m)", k, ".1f", 1e-3))
    lines += [r"\hline", r"\end{tabular}", r"\end{table}"]
    with open(os.path.join(OUT, "table6_3.tex"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(json.dumps({"rel_change_pct": rel, "J_block_change_pct": rel_blocks, "blocks_base": base["J_blocks_50s"],
                      "blocks_best": best["J_blocks_50s"], "fail": fail, "wind": wind}, indent=1))


if __name__ == "__main__":
    main()
