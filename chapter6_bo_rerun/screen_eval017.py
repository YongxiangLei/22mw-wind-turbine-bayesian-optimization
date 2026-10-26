"""Prepare short (TMax = 90 s) screening runs of evaluation 17 with candidate numerical fixes."""
import os
import shutil
import sys

R = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, R)
from bo_rerun import set_param, TOP_FILES, FST, DISCON  # noqa: E402

SRC = os.path.join(R, "runs", "eval_017")
CASES = {
    "A_dt1e-4": [("DT", "0.0001")],
    "B_numcrctn1": [("NumCrctn", "1")],
    "C_interp1": [("InterpOrder", "1")],
}
for name, changes in CASES.items():
    d = os.path.join(R, "runs", f"eval_017_screen_{name}")
    os.makedirs(d, exist_ok=True)
    for fn in TOP_FILES + [DISCON, "IEA-22-280-RWT_BeamDyn_eval017.dat"]:
        shutil.copy2(os.path.join(SRC, fn), os.path.join(d, fn))
    fst = os.path.join(d, FST)
    set_param(fst, "TMax", "90.0")
    for key, val in changes:
        set_param(fst, key, val)
    print(name, "->", d, changes)
