"""
Finish the re-run of evaluation 17 (numpy/matplotlib only - scipy/sklearn are blocked by
Windows Smart App Control on this machine, and are not needed here).
  python finalize_eval017.py <openfast_returncode> <wall_seconds>
 * writes runs/eval_017/metrics.json (same fields as the other evaluations)
 * compares the re-run with the failed run over 0-80.7 s (NRMax only acts on non-converged steps,
   so the two should be identical there)
 * regenerates ch6_outputs (postprocess.py, extra_analysis.py) and appends to rerun.log
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys

import numpy as np

R = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, R)
from bo_rerun import read_outb, metrics, FST  # noqa: E402  (no scipy/sklearn import)

RUN = os.path.join(R, "runs", "eval_017")
OLD = os.path.join(R, "runs", "eval_017_failed_NRMax10")
OUTB = FST.replace(".fst", ".outb")


def read_text(path):
    """OpenFAST stdout redirected by PowerShell is UTF-16; Python subprocess output is UTF-8/ANSI."""
    raw = open(path, "rb").read()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff") or raw[1:200:2].count(0) > 50:
        return raw.decode("utf-16", errors="ignore")
    return raw.decode("utf-8", errors="ignore")


def log(msg):
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    with open(os.path.join(R, "rerun.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def main():
    rc = int(sys.argv[1]) if len(sys.argv) > 1 else -1
    wall = float(sys.argv[2]) if len(sys.argv) > 2 else float("nan")
    yml = open(os.path.join(RUN, "IEA-22-280-RWT-Monopile.yaml")).read()
    rated_rpm = float(re.search(r"rated_rotor_speed:\s*([0-9.eE+-]+)", yml).group(1)) * 60 / (2 * np.pi)
    with open(os.path.join(RUN, "parameters.json")) as f:
        om = json.load(f)["omega_pc"]
    stdout = read_text(os.path.join(RUN, "openfast_stdout.txt"))
    ok = os.path.exists(os.path.join(RUN, OUTB)) and "terminated normally" in stdout
    res = {"tag": "eval_017", "omega_pc": om, "returncode": rc, "wall_s": wall,
           "finished": dt.datetime.now().isoformat(),
           "note": "re-run with InterpOrder=1 (instead of 2) and BeamDyn NRMax=30, load_retries=50. "
                   "Attempts with InterpOrder=2 failed at t=80.704 s (BeamDyn GA2 did not converge) with "
                   "NRMax=10 and NRMax=30 (identical up to 80.69 s); archived in runs/eval_017_failed_NRMax10 "
                   "and runs/eval_017_failed_NRMax30. Numerical sensitivity: runs/sens_i1_baseline, sens_i1_eval_018.",
           "numerics": {"InterpOrder": 1, "NRMax": 30, "load_retries": 50}}
    if ok:
        res.update(metrics(os.path.join(RUN, OUTB), rated_rpm))
        res["status"] = "OK"
    else:
        res["status"] = "FAILED"
        res["error"] = [l.strip() for l in stdout.splitlines() if "converge" in l or "error at simulation time" in l][-3:]
    with open(os.path.join(RUN, "metrics.json"), "w") as f:
        json.dump(res, f, indent=1)

    # identity check against the failed run on the common interval
    cmp_ = {}
    if os.path.exists(os.path.join(RUN, OUTB)) and os.path.exists(os.path.join(OLD, OUTB)):
        a, b = read_outb(os.path.join(OLD, OUTB)), read_outb(os.path.join(RUN, OUTB))
        n = min(len(a["Time"]), len(b["Time"])) - 1          # drop the last (aborted) sample
        worst = []
        for ch in a:
            if ch == "Time" or ch not in b:
                continue
            x, y = a[ch][:n], b[ch][:n]
            rng = max(np.ptp(x), 1e-12)
            worst.append((float(np.max(np.abs(x - y)) / rng), ch))
        worst.sort(reverse=True)
        cmp_ = {"t_common_end_s": float(a["Time"][n - 1]), "n_channels": len(worst),
                "max_rel_diff": worst[0][0], "worst_channel": worst[0][1],
                "identical_channels": int(sum(1 for w, _ in worst if w == 0.0))}
        with open(os.path.join(RUN, "compare_InterpOrder1_vs_InterpOrder2_0-80s.json"), "w") as f:
            json.dump(cmp_, f, indent=1)

    if ok:
        log(f"eval_017 (re-run, InterpOrder=1): OK  J={res['J_power_mse_kW2']:.1f} kW^2  wall={wall / 3600:.2f} h  "
            f"| vs InterpOrder=2 run over 0-{cmp_.get('t_common_end_s', float('nan')):.2f} s: max rel diff "
            f"{cmp_.get('max_rel_diff', float('nan')):.2e} (channel {cmp_.get('worst_channel')})")
        for script in ("postprocess.py", "extra_analysis.py"):
            p = subprocess.run([sys.executable, os.path.join(R, script)], cwd=R, capture_output=True, text=True)
            with open(os.path.join(R, "logs", f"{script[:-3]}_after_eval017.txt"), "w", encoding="utf-8") as f:
                f.write(p.stdout + "\n" + p.stderr)
            log(f"{script} after eval_017 re-run: exit={p.returncode}")
    else:
        log(f"eval_017 (re-run, InterpOrder=1): FAILED: {res.get('error')}")


if __name__ == "__main__":
    main()
