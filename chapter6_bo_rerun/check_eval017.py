"""Compare eval_017 (failed at 80.7 s) with other runs over 0-80 s."""
import os, sys
import numpy as np
ROOT = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, ROOT)
from bo_rerun import read_outb, FST
for tag in ("baseline", "eval_008", "eval_015", "eval_017", "eval_018"):
    d = read_outb(os.path.join(ROOT, "runs", tag, FST.replace(".fst", ".outb")))
    t = d["Time"]; s = t <= 80.7
    gs = d["GenSpeed"][s]; i = int(np.argmax(gs))
    late = (t >= 50) & (t <= 80.7)
    print(f"{tag:9s} max GenSpeed 0-80.7 s = {gs.max():6.2f} rpm at t = {t[s][i]:5.1f} s | "
          f"max over 50-80.7 s = {d['GenSpeed'][late].max():5.2f} rpm | pitch max 50-80.7 s = {d['BldPitch1'][late].max():5.1f} deg | "
          f"t_end = {t[-1]:.1f}")
d = read_outb(os.path.join(ROOT, "runs", "eval_017", FST.replace(".fst", ".outb")))
t = d["Time"]; s = t >= 70
print("eval_017 last 10 s, every 1 s: GenSpeed", np.round(d["GenSpeed"][s][::100], 2).tolist())
print("eval_017 last 10 s, every 1 s: Pitch   ", np.round(d["BldPitch1"][s][::100], 2).tolist())
