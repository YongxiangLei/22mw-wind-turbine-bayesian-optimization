"""Metrics of a sensitivity run and comparison with the original (InterpOrder = 2) run.
  python case_metrics.py <run_dir_name> <reference_run_name> <returncode> <wall_seconds>"""
import datetime as dt
import json
import os
import re
import sys

import numpy as np

R = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, R)
from bo_rerun import metrics, FST  # noqa: E402
from finalize_eval017 import read_text, log  # noqa: E402

name, ref, rc, wall = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4])
d = os.path.join(R, "runs", name)
yml = open(os.path.join(d, "IEA-22-280-RWT-Monopile.yaml")).read()
rated = float(re.search(r"rated_rotor_speed:\s*([0-9.eE+-]+)", yml).group(1)) * 60 / (2 * np.pi)
txt = read_text(os.path.join(d, "openfast_stdout.txt"))
outb = os.path.join(d, FST.replace(".fst", ".outb"))
res = {"tag": name, "reference_run": ref, "returncode": rc, "wall_s": wall, "finished": dt.datetime.now().isoformat(),
       "numerics": {"InterpOrder": 1}}
if os.path.exists(outb) and "terminated normally" in txt:
    res.update(metrics(outb, rated)); res["status"] = "OK"
    with open(os.path.join(R, "runs", ref, "metrics.json")) as f:
        J2 = json.load(f)["J_power_mse_kW2"]
    res["J_InterpOrder2_kW2"] = J2
    res["J_rel_change_pct"] = 100 * (res["J_power_mse_kW2"] - J2) / J2
    log(f"{name}: OK  J={res['J_power_mse_kW2']:.1f} kW^2 (InterpOrder=2 run {ref}: {J2:.1f}, "
        f"change {res['J_rel_change_pct']:+.2f} %)  wall={wall / 3600:.2f} h")
else:
    res["status"] = "FAILED"
    log(f"{name}: FAILED " + "; ".join(l.strip() for l in txt.splitlines() if "error at simulation time" in l))
with open(os.path.join(d, "metrics.json"), "w") as f:
    json.dump(res, f, indent=1)
