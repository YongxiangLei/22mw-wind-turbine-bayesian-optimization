import json, os
import numpy as np
R = os.path.dirname(os.path.abspath(__file__))
ex = json.load(open(os.path.join(R, "ch6_outputs", "extra_analysis.json")))
for k in ("baseline", "best"):
    b = ex[k]; m = json.load(open(os.path.join(R, "runs", b["tag"], "metrics.json")))
    g = json.load(open(os.path.join(R, "runs", b["tag"], "gain_schedule.json")))
    v = np.array(g["v"]); i = int(np.argmin(abs(v - 17.9)))
    print(k, b["tag"], "P_mean=%.1f kW" % m["power_mean_kW"], "P_std=%.1f" % m["power_std_kW"],
          "pitch_rate_rms=%.3f max=%.3f deg/s" % (b["pitch_rate_rms_degps"], b["pitch_rate_max_degps"]),
          "genspd_rmse=%.3f max=%.3f" % (b["genspd_rmse_rpm"], b["genspd_max_rpm"]),
          "DEL FA=%.0f SS=%.0f" % (b["DEL_TwrBsMyt_m4"], b["DEL_TwrBsMxt_m4"]),
          "| v=%.2f: omega=%.3f Kp=%.3f Ki=%.4f" % (v[i], g["omega_pc"][i], g["Kp"][i], g["Ki"][i]),
          "| Kp range [%.3f, %.3f], Ki range [%.4f, %.4f], v range [%.2f, %.2f]" % (min(g["Kp"]), max(g["Kp"]), min(g["Ki"]), max(g["Ki"]), v[0], v[-1]))
print("blocks base", np.round(np.array(ex["baseline"]["J_blocks_50s"]) / 1e3, 2), "best", np.round(np.array(ex["best"]["J_blocks_50s"]) / 1e3, 2))
rows = []
for t in sorted(os.listdir(os.path.join(R, "runs"))):
    p = os.path.join(R, "runs", t, "metrics.json")
    if t.startswith("eval_") and os.path.exists(p):
        m = json.load(open(p))
        if m["status"] == "OK": rows.append((m["omega_pc"][1], m["J_power_mse_kW2"], t))
rows.sort()
print("omega2 vs J:", [(round(a, 3), round(b / 1e3, 2)) for a, b, _ in rows])
print("corr(omega2, J) =", np.corrcoef([r[0] for r in rows], [r[1] for r in rows])[0, 1])
for j in (0, 2):
    vals = []
    for t in sorted(os.listdir(os.path.join(R, "runs"))):
        p = os.path.join(R, "runs", t, "metrics.json")
        if t.startswith("eval_") and os.path.exists(p):
            m = json.load(open(p))
            if m["status"] == "OK": vals.append((m["omega_pc"][j], m["J_power_mse_kW2"]))
    print("corr(omega%d, J) =" % (j + 1), np.corrcoef(*zip(*vals))[0, 1])
