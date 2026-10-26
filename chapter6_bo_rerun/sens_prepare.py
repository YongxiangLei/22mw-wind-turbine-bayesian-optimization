"""Set InterpOrder = 1 for the eval_017 re-run and prepare the numerical-sensitivity runs
(baseline and eval_018 repeated with InterpOrder = 1, everything else identical)."""
import os
import shutil
import sys

R = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, R)
from bo_rerun import set_param, TOP_FILES, FST, DISCON  # noqa: E402

RUNS = os.path.join(R, "runs")
set_param(os.path.join(RUNS, "eval_017", FST), "InterpOrder", "1")
print("eval_017: InterpOrder=1")
for src in ("baseline", "eval_018"):
    d = os.path.join(RUNS, f"sens_i1_{src}")
    os.makedirs(d, exist_ok=True)
    for fn in TOP_FILES + [DISCON, "parameters.json", "gain_schedule.json"]:
        shutil.copy2(os.path.join(RUNS, src, fn), os.path.join(d, fn))
    set_param(os.path.join(d, FST), "InterpOrder", "1")
    print(f"sens_i1_{src}: prepared (InterpOrder=1)")
