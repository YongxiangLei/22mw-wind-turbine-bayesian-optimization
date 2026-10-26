import os, sys, numpy as np
R = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, R)
from bo_rerun import read_outb, FST
out = {}
for tag in ("baseline", "eval_018"):
    d = read_outb(os.path.join(R, "runs", tag, FST.replace(".fst", ".outb")))
    t = d["Time"]; w = (t >= 100) & (t <= 300)
    out[tag] = d
    print(tag, "RotThrust std = %.1f kN, mean = %.1f kN" % (d["RotThrust"][w].std(), d["RotThrust"][w].mean()),
          "| RotTorq std = %.1f" % d["RotTorq"][w].std())
t = out["baseline"]["Time"]; w = (t >= 100) & (t <= 300)
dp = out["eval_018"]["BldPitch1"][w] - out["baseline"]["BldPitch1"][w]
print("pitch difference range: %.2f .. %.2f deg" % (dp.min(), dp.max()))
