import os, sys, numpy as np
R = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, R)
from bo_rerun import read_outb, FST
d = {t: read_outb(os.path.join(R, "runs", t, FST.replace(".fst", ".outb"))) for t in ("baseline", "eval_018")}
for a, b in ((160, 170), (185, 195), (100, 300)):
    for t in d:
        tt = d[t]["Time"]; w = (tt >= a) & (tt <= b); p = d[t]["GenPwr"][w]
        print(f"{a}-{b} s {t:9s} max {p.max():8.1f}  min {p.min():8.1f}  max|dev| {np.abs(p - 22000).max():6.1f} kW")
