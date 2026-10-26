import os, sys, numpy as np
R = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, R)
from extra_analysis import rainflow, del_1hz
from bo_rerun import read_outb, FST
# 1) analytic check: 10 sine cycles of amplitude 1 -> 10 cycles of range 2 -> DEL(neq = 10) = 2
t = np.linspace(0, 10, 100001); x = np.sin(2 * np.pi * t)
r, n = rainflow(x); print("sine: total cycles %.1f, max range %.3f, DEL %.4f (expect 10, 2, 2)" % (n.sum(), r.max(), del_1hz(x, t, 4)))
# 2) mixed signal: big slow cycle + small fast ripple; check vs. brute-force reasoning
x2 = 5 * np.sin(2 * np.pi * 0.1 * t) + 0.5 * np.sin(2 * np.pi * 3 * t)
r2, n2 = rainflow(x2); print("mixed: cycles %.1f, ranges>5: %.1f (expect 1 large cycle, ~30 small)" % (n2.sum(), n2[r2 > 5].sum()))
# 3) the two runs: cycle statistics of the side-side and fore-aft tower moments
for ch in ("TwrBsMxt", "TwrBsMyt"):
    for tag in ("baseline", "eval_018"):
        d = read_outb(os.path.join(R, "runs", tag, FST.replace(".fst", ".outb")))
        tt = d["Time"]; w = (tt >= 100) & (tt <= 300); y = d[ch][w]
        r, n = rainflow(y)
        q = np.percentile(np.repeat(r, (2 * n).astype(int)), [50, 90, 99])
        top = np.sort(r)[-5:] / 1e3
        print(ch, tag, "cycles %.0f, std %.0f kNm, range p50/p90/p99 = %s MNm, 5 largest = %s MNm, DEL m4 = %.1f MNm" %
              (n.sum(), y.std(), np.round(q / 1e3, 2), np.round(top, 1), del_1hz(y, tt[w], 4) / 1e3))
