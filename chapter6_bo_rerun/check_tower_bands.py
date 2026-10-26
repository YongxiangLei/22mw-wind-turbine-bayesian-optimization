import os, sys, numpy as np
R = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, R)
from bo_rerun import read_outb, FST
bands = [(0, 0.08), (0.08, 0.15), (0.15, 0.30), (0.30, 0.40), (0.40, 5.0)]
res = {}
for tag in ("baseline", "eval_018"):
    d = read_outb(os.path.join(R, "runs", tag, FST.replace(".fst", ".outb")))
    t = d["Time"]; w = (t >= 100) & (t <= 300); dt = t[1] - t[0]
    for ch in ("TwrBsMyt", "TwrBsMxt", "RotThrust", "BldPitch1"):
        x = d[ch][w] - d[ch][w].mean()
        X = np.fft.rfft(x * np.hanning(len(x))); f = np.fft.rfftfreq(len(x), dt)
        P = np.abs(X) ** 2
        res[(tag, ch)] = [P[(f >= a) & (f < b)].sum() for a, b in bands]
        if ch == "TwrBsMyt" and tag == "baseline":
            fi = (f > 0.15) & (f < 0.4); print("tower FA spectral peak in 0.15-0.4 Hz at %.3f Hz" % f[fi][np.argmax(P[fi])])
for ch in ("TwrBsMyt", "TwrBsMxt", "RotThrust", "BldPitch1"):
    b, x = np.array(res[("baseline", ch)]), np.array(res[("eval_018", ch)])
    print(ch.ljust(10), " ".join("[%.2f-%.2f Hz] share %.0f%%->%.0f%% ratio %.2f" % (a, c, 100 * bb / b.sum(), 100 * xx / x.sum(), xx / bb)
                                  for (a, c), bb, xx in zip(bands, b, x)))
