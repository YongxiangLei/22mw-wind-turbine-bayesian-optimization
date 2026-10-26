"""Single-panel Figure 6.5 (style of the original generator_power_with_reference.png) from the rerun."""
import json
import os
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, R)
from bo_rerun import read_outb, FST, P_REF  # noqa: E402

OUT = [os.path.join(R, "ch6_outputs")]
summ = json.load(open(os.path.join(R, "ch6_outputs", "summary.json")))
best_tag = summ["best"]["tag"]

def load(tag):
    d = read_outb(os.path.join(R, "runs", tag, FST.replace(".fst", ".outb")))
    t = d["Time"]; w = (t >= 100.0) & (t <= 300.0)
    return t[w], d["GenPwr"][w]

tb, pb = load("baseline")
tx, px = load(best_tag)
rmse_b = np.sqrt(np.mean((pb - P_REF) ** 2)); rmse_x = np.sqrt(np.mean((px - P_REF) ** 2))
dev = max(np.abs(pb - P_REF).max(), np.abs(px - P_REF).max())
half = np.ceil(dev / 100.0) * 100.0 + 100.0          # symmetric range, rounded up + margin
print(f"max deviation {dev:.0f} kW -> y-axis {P_REF - half:.0f} .. {P_REF + half:.0f} kW")

fig, ax = plt.subplots(figsize=(6.4, 4.8))
ax.plot(tb, pb, color="tab:blue", lw=0.9, label=f"Baseline, ROSCO default (RMSE {rmse_b:.1f} kW)")
ax.plot(tx, px, color="tab:orange", lw=0.9, alpha=0.85,
        label=f"BO-optimized, eval. {int(best_tag.split('_')[1])} (RMSE {rmse_x:.1f} kW)")
ax.plot(tb, np.full_like(tb, P_REF), "--", color="tab:green", lw=1.5, label=f"Reference ({P_REF / 1e3:.1f} MW)")
ax.set_xlabel("Time [s]"); ax.set_ylabel("Generator Power [kW]")
ax.set_xlim(100, 300); ax.set_ylim(P_REF - half, P_REF + half)
ax.grid(True)
ax.legend(loc="upper left", fontsize=9, framealpha=0.95)
fig.tight_layout()
for d in OUT:
    os.makedirs(d, exist_ok=True)
    fig.savefig(os.path.join(d, "generator_power_with_reference.png"), dpi=600)
    fig.savefig(os.path.join(d, "generator_power_with_reference.pdf"))
plt.close(fig)
print("saved:", [os.path.join(d, "generator_power_with_reference.png") for d in OUT])
