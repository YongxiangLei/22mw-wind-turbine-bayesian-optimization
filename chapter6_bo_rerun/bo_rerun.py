"""
Re-run of the Chapter 6 Bayesian optimisation of the ROSCO pitch-controller
natural frequencies (omega_pc) for the IEA 22 MW monopile turbine.

Changes with respect to the original script ../IEA-22-280-RWT-Monopile/BO_FAST_LOG.py
(see CHANGES_vs_BO_FAST_LOG.md):
  * objective J = MSE of generator power over the window 100-300 s
    (the original used the last 500 output samples = last 0.1 s, because
    DT_Out = DT = 0.0002 s);
  * a baseline run with the ROSCO default omega_pc is evaluated with the same J;
  * the 5 random initial points (and the baseline) run in parallel, then the
    GP-guided evaluations run in parallel batches (Kriging Believer, --batch);
  * every run has its own directory, so DISCON / outputs are not overwritten;
  * DT_Out = 0.01 s, wind probe at hub height (170 m), ROSCO LoggingLevel 0.
Model directory: $BO_MODEL_DIR (default ../IEA-22-280-RWT-Monopile);
micromamba environment: $ROSCO_ENV (set by env_d.ps1).

Usage:
  python bo_rerun.py setup                         # build runs/template and runs/IEA-22-280-RWT
  python bo_rerun.py test                          # 5 s smoke test of the whole pipeline
  python bo_rerun.py run [--n-iter N] [--batch q]  # baseline + 5 random + N GP-guided (default 15, q = 5)
"""
import argparse
import csv
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.abspath(__file__))
# OpenFAST/ROSCO model of the IEA 22 MW monopile turbine (default: the model folder of this repository)
SRC = os.environ.get("BO_MODEL_DIR", os.path.normpath(os.path.join(ROOT, os.pardir, "IEA-22-280-RWT-Monopile")))
RUNS = os.path.join(ROOT, "runs")
TEMPLATE = os.path.join(RUNS, "template")
SHARED = os.path.join(RUNS, "IEA-22-280-RWT")
ENV = os.environ.get("ROSCO_ENV", r"D:\software\micromamba\envs\rosco-env")
OPENFAST = os.path.join(ENV, "Library", "bin", "openfast.exe")
LIBDISCON = os.path.join(ENV, "Library", "lib", "libdiscon.dll")

FST = "IEA-22-280-RWT-Monopile.fst"
YAML = "IEA-22-280-RWT-Monopile.yaml"
DISCON = "IEA-22-280-RWT_DISCON.IN"
PERF = "../IEA-22-280-RWT/IEA-22-280-RWT_Cp_Ct_Cq.txt"
TOP_FILES = [FST, YAML, "IEA-22-280-RWT_AeroDyn15.dat", "IEA-22-280-RWT_ElastoDyn.dat",
             "IEA-22-280-RWT_ElastoDyn_tower.dat", "IEA-22-280-RWT_HydroDyn.dat",
             "IEA-22-280-RWT_ServoDyn.dat", "IEA-22-280-RWT_SubDyn.dat"]

P_REF = 22000.0                    # kW
T_WIN = (100.0, 300.0)             # objective window [s]
PBOUNDS = {"omega_pc1": (0.1, 0.2), "omega_pc2": (0.1, 0.2), "omega_pc3": (0.1, 0.5)}
KEYS = list(PBOUNDS)
INIT_POINTS = 5
SEED = 42


# ----------------------------------------------------------------------------- file helpers
def set_param(path, key, value):
    """Replace the value (first token) of the FAST input line whose label is `key`."""
    with open(path, "r") as f:
        lines = f.readlines()
    n = 0
    for i, line in enumerate(lines):
        tok = line.split()
        if len(tok) >= 2 and tok[1] == key:
            m = re.match(r'^(\s*)("[^"]*"|\S+)(.*)$', line.rstrip("\n"))
            lines[i] = f"{m.group(1)}{value}{m.group(3)}\n"
            n += 1
    if n != 1:
        raise RuntimeError(f"{key}: found {n} lines in {path}")
    with open(path, "w") as f:
        f.writelines(lines)


def setup():
    os.makedirs(TEMPLATE, exist_ok=True)
    for fn in TOP_FILES:
        shutil.copy2(os.path.join(SRC, fn), os.path.join(TEMPLATE, fn))
    # shared turbine folder (blades, BeamDyn, airfoils, Cp table, inflow) + wind file
    src_shared = os.path.join(SRC, "IEA-22-280-RWT")
    os.makedirs(SHARED, exist_ok=True)
    for fn in os.listdir(src_shared):
        p = os.path.join(src_shared, fn)
        if os.path.isfile(p):
            shutil.copy2(p, os.path.join(SHARED, fn))
    if not os.path.isdir(os.path.join(SHARED, "Airfoils")):
        shutil.copytree(os.path.join(src_shared, "Airfoils"), os.path.join(SHARED, "Airfoils"))
    wind_dst = os.path.join(SHARED, "Wind")
    os.makedirs(wind_dst, exist_ok=True)
    for fn in ("TurbSim.bts", "TurbSim.inp", "TurbSim.sum"):
        shutil.copy2(os.path.join(src_shared, "Wind", "ExampleFiles", fn), os.path.join(wind_dst, fn))

    bts = os.path.join(wind_dst, "TurbSim.bts").replace("\\", "/")
    inflow = os.path.join(SHARED, "IEA-22-280-RWT_InflowFile.dat")
    set_param(inflow, "FileName_BTS", f'"{bts}"')
    set_param(inflow, "WindVziList", "170.0")          # wind probe at hub height
    set_param(os.path.join(TEMPLATE, "IEA-22-280-RWT_ServoDyn.dat"), "DLL_FileName",
              '"' + LIBDISCON.replace("\\", "/") + '"')
    fst = os.path.join(TEMPLATE, FST)
    set_param(fst, "Echo", "False")
    set_param(fst, "DT_Out", "0.01")
    set_param(fst, "OutFileFmt", "2")
    print("setup done:", TEMPLATE, SHARED)


# ----------------------------------------------------------------------------- outb reader
def read_outb(path):
    with open(path, "rb") as f:
        fid = np.frombuffer(f.read(2), "<i2")[0]
        clen = 10
        if fid == 4:
            clen = int(np.frombuffer(f.read(2), "<i2")[0])
        nc, nt = np.frombuffer(f.read(8), "<i4")
        if fid == 1:
            tscl, toff = np.frombuffer(f.read(16), "<f8")
        else:
            t1, dtt = np.frombuffer(f.read(16), "<f8")
        scl = np.frombuffer(f.read(4 * nc), "<f4")
        off = np.frombuffer(f.read(4 * nc), "<f4")
        ld = int(np.frombuffer(f.read(4), "<i4")[0])
        f.read(ld)
        names = [f.read(clen).decode("ascii").strip() for _ in range(nc + 1)]
        f.read(clen * (nc + 1))
        if fid == 1:
            traw = np.frombuffer(f.read(4 * nt), "<i4")
            time_ = (traw - toff) / tscl
        else:
            time_ = t1 + dtt * np.arange(nt)
        raw = np.frombuffer(f.read(2 * nc * nt), "<i2").reshape(nt, nc)
    data = (raw.astype(np.float64) - off) / scl
    out = {"Time": time_}
    for i, n in enumerate(names[1:]):
        out[n] = data[:, i]
    return out


def metrics(outb, rated_genspd_rpm):
    d = read_outb(outb)
    t = d["Time"]
    w = (t >= T_WIN[0]) & (t <= T_WIN[1])
    p = d["GenPwr"][w]
    gs = d["GenSpeed"][w]
    pit = d["BldPitch1"][w]
    m = {
        "J_power_mse_kW2": float(np.mean((p - P_REF) ** 2)),
        "power_rmse_kW": float(np.sqrt(np.mean((p - P_REF) ** 2))),
        "power_mean_kW": float(np.mean(p)),
        "power_std_kW": float(np.std(p)),
        "power_min_kW": float(p.min()), "power_max_kW": float(p.max()),
        "genspd_mse_rpm2": float(np.mean((gs - rated_genspd_rpm) ** 2)),
        "genspd_max_rpm": float(gs.max()),
        "pitch_mean_deg": float(np.mean(pit)), "pitch_std_deg": float(np.std(pit)),
        "pitch_travel_deg": float(np.sum(np.abs(np.diff(pit)))),
        "twrbsmyt_std_kNm": float(np.std(d["TwrBsMyt"][w])) if "TwrBsMyt" in d else None,
        "wind_mean_ms": float(np.mean(d["Wind1VelX"][w])),
        "wind_std_ms": float(np.std(d["Wind1VelX"][w])),
        "t_end_s": float(t[-1]),
        # objective as computed by the original BO_FAST_LOG.py (last 0.1 s), for comparison only
        "J_old_last0p1s_kW2": float(np.mean((d["GenPwr"][t >= t[-1] - 0.1 + 1e-9] - P_REF) ** 2)),
    }
    return m


# ----------------------------------------------------------------------------- one evaluation
class Tuner:
    def __init__(self):
        from rosco.toolbox import turbine as RT
        from rosco.toolbox.inputs.validation import load_rosco_yaml
        cwd = os.getcwd()
        os.chdir(TEMPLATE)
        try:
            self.inps = load_rosco_yaml(YAML)
            tp = self.inps["turbine_params"]
            pp = self.inps["path_params"]
            self.turbine = RT.Turbine(tp)
            self.turbine.load_from_fast(pp["FAST_InputFile"], pp["FAST_directory"],
                                        rot_source="txt", txt_filename=pp["rotor_performance_filename"])
        finally:
            os.chdir(cwd)
        self.rated_genspd_rpm = tp["rated_rotor_speed"] * 60 / (2 * np.pi)  # direct drive
        self.default_omega = list(self.inps["controller_params"]["omega_pc"])

    def write(self, run_dir, omegas):
        import copy
        from rosco.toolbox import controller as RC
        from rosco.toolbox.utilities import write_DISCON
        cp = copy.deepcopy(self.inps["controller_params"])
        cp["omega_pc"] = [float(x) for x in omegas]
        cp["LoggingLevel"] = 0
        c = RC.Controller(cp)
        c.tune_controller(self.turbine)
        cwd = os.getcwd()
        os.chdir(run_dir)
        try:
            write_DISCON(self.turbine, c, param_file=DISCON, txt_filename=PERF)
        finally:
            os.chdir(cwd)
        v = c.v[len(c.v_below_rated) + 1:]
        sched = {"v": list(map(float, v)), "omega_pc": list(map(float, c.omega_pc_U)),
                 "zeta_pc": list(map(float, c.zeta_pc_U)),
                 "Kp": list(map(float, c.pc_gain_schedule.Kp)), "Ki": list(map(float, c.pc_gain_schedule.Ki))}
        with open(os.path.join(run_dir, "gain_schedule.json"), "w") as f:
            json.dump(sched, f, indent=1)
        fig, ax = plt.subplots(2, 2, figsize=(9, 6), sharex=True, constrained_layout=True)
        for a, k, lab in zip(ax.flat, ["omega_pc", "zeta_pc", "Kp", "Ki"],
                             [r"$\omega_{pc}$ [rad/s]", r"$\zeta_{pc}$ [-]", r"$K_p$ [s]", r"$K_i$ [-]"]):
            a.plot(v, sched[k]); a.set_ylabel(lab); a.grid(alpha=0.3)
        for a in ax[1]:
            a.set_xlabel("Wind speed [m/s]")
        fig.suptitle(os.path.basename(run_dir) + "  omega_pc = " + ", ".join(f"{x:.4f}" for x in omegas))
        fig.savefig(os.path.join(run_dir, "gain_schedule.png"), dpi=150)
        plt.close(fig)


def prepare_run(tuner, tag, omegas, tmax=None):
    d = os.path.join(RUNS, tag)
    os.makedirs(d, exist_ok=True)
    for fn in TOP_FILES:
        shutil.copy2(os.path.join(TEMPLATE, fn), os.path.join(d, fn))
    if tmax is not None:
        set_param(os.path.join(d, FST), "TMax", f"{tmax}")
    tuner.write(d, omegas)
    with open(os.path.join(d, "parameters.json"), "w") as f:
        json.dump({"tag": tag, "omega_pc": list(map(float, omegas)), "prepared": dt.datetime.now().isoformat()}, f, indent=1)
    return d


def run_openfast(d):
    t0 = time.time()
    with open(os.path.join(d, "openfast_stdout.txt"), "w") as fo, open(os.path.join(d, "openfast_stderr.txt"), "w") as fe:
        rc = subprocess.run([OPENFAST, FST], cwd=d, stdout=fo, stderr=fe).returncode
    return rc, time.time() - t0


def evaluate(tuner, tag, omegas, tmax=None):
    """Prepare (main thread) is done by caller; this runs OpenFAST and computes metrics."""
    d = os.path.join(RUNS, tag)
    mfile = os.path.join(d, "metrics.json")
    if os.path.exists(mfile):                      # resume: reuse only successful runs
        try:
            with open(mfile) as f:
                old = json.load(f)
            if old.get("status") == "OK":
                return old
        except (json.JSONDecodeError, OSError):
            pass
        os.remove(mfile)
    rc, wall = run_openfast(d)
    outb = os.path.join(d, FST.replace(".fst", ".outb"))
    res = {"tag": tag, "omega_pc": list(map(float, omegas)), "returncode": rc, "wall_s": wall,
           "finished": dt.datetime.now().isoformat()}
    if rc == 0 and os.path.exists(outb):
        res.update(metrics(outb, tuner.rated_genspd_rpm))
        res["status"] = "OK"
    else:
        res["status"] = "FAILED"
    with open(mfile, "w") as f:
        json.dump(res, f, indent=1)
    return res


# ----------------------------------------------------------------------------- logging
def log(msg):
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    print(line, flush=True)
    with open(os.path.join(ROOT, "rerun.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


def write_table(results):
    cols = ["tag", "kind", "omega_pc1", "omega_pc2", "omega_pc3", "J_power_mse_kW2", "power_rmse_kW",
            "power_std_kW", "genspd_mse_rpm2", "pitch_std_deg", "pitch_travel_deg", "twrbsmyt_std_kNm",
            "J_old_last0p1s_kW2", "best_so_far_kW2", "wall_s", "status"]
    with open(os.path.join(ROOT, "results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        best = np.inf
        for r in results:
            row = dict(r)
            row["omega_pc1"], row["omega_pc2"], row["omega_pc3"] = r["omega_pc"]
            if r["kind"] != "baseline" and r.get("status") == "OK":
                best = min(best, r["J_power_mse_kW2"])
            row["best_so_far_kW2"] = best if np.isfinite(best) else ""
            w.writerow(row)


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["setup", "test", "run"])
    ap.add_argument("--n-iter", type=int, default=15)
    ap.add_argument("--batch", type=int, default=5, help="parallel GP-guided evaluations per round")
    args = ap.parse_args()

    if args.mode == "setup":
        setup()
        return

    import bayes_opt
    from bayes_opt import BayesianOptimization
    tuner = Tuner()

    if args.mode == "test":
        d = prepare_run(tuner, "test_5s", tuner.default_omega, tmax=5.0)
        if os.path.exists(os.path.join(d, "metrics.json")):
            os.remove(os.path.join(d, "metrics.json"))
        r = evaluate(tuner, "test_5s", tuner.default_omega)
        print(json.dumps({k: r.get(k) for k in ("status", "returncode", "wall_s", "t_end_s")}, indent=1))
        return

    log(f"start: rosco toolbox + bayes_opt {bayes_opt.__version__}, J window {T_WIN}, "
        f"init={INIT_POINTS}, n_iter={args.n_iter}, batch={args.batch}, seed={SEED}, bounds={PBOUNDS}")
    rng = np.random.RandomState(SEED)
    lo = np.array([PBOUNDS[k][0] for k in KEYS]); hi = np.array([PBOUNDS[k][1] for k in KEYS])
    init = [lo + (hi - lo) * rng.uniform(size=3) for _ in range(INIT_POINTS)]

    # phase 1: baseline + random initial points in parallel
    jobs = [("baseline", "baseline", tuner.default_omega)] + \
           [(f"eval_{i + 1:03d}", "random", list(x)) for i, x in enumerate(init)]
    for tag, kind, om in jobs:
        if not os.path.exists(os.path.join(RUNS, tag, "metrics.json")):
            prepare_run(tuner, tag, om)
    log("phase 1: " + "; ".join(f"{t}={np.round(o, 4).tolist()}" for t, _, o in jobs))
    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        futs = [ex.submit(evaluate, tuner, t, o) for t, _, o in jobs]
        res1 = [f.result() for f in futs]
    results = []
    for (tag, kind, om), r in zip(jobs, res1):
        r["kind"] = kind
        results.append(r)
        log(f"{tag}: {r['status']}  J={r.get('J_power_mse_kW2', float('nan')):.1f} kW^2  wall={r['wall_s'] / 3600:.2f} h")
    write_table(results)

    # phase 2: GP-guided evaluations in parallel batches of size q (Kriging Believer), resumable.
    # Within a round, each suggestion is registered with the GP posterior mean as a provisional
    # target before the next suggestion; after the round, a fresh GP is fitted on real results only.
    real = [(r["omega_pc"], -r["J_power_mse_kW2"]) for r in results
            if r["kind"] != "baseline" and r["status"] == "OK"]
    q = max(1, args.batch)
    n_done = 0
    rnd = 0
    while n_done < args.n_iter:
        nq = min(q, args.n_iter - n_done)
        tags = [f"eval_{INIT_POINTS + n_done + j + 1:03d}" for j in range(nq)]
        bopt = BayesianOptimization(f=None, pbounds=PBOUNDS, random_state=SEED + 1 + rnd,
                                    verbose=0, allow_duplicate_points=True)
        for om, tgt in real:
            bopt.register(params=dict(zip(KEYS, om)), target=tgt)
        batch = []
        for tag in tags:
            pfile = os.path.join(RUNS, tag, "parameters.json")
            if os.path.exists(pfile):                       # resume: reuse stored suggestion
                with open(pfile) as f:
                    om = json.load(f)["omega_pc"]
            else:
                s = bopt.suggest()
                om = [float(s[key]) for key in KEYS]
                prepare_run(tuner, tag, om)
            mu = float(bopt._gp.predict(np.array(om).reshape(1, -1))[0]) if len(real) else 0.0
            bopt.register(params=dict(zip(KEYS, om)), target=mu)   # provisional (believer)
            batch.append((tag, om))
        log(f"round {rnd + 1}: " + "; ".join(f"{t}={np.round(o, 4).tolist()}" for t, o in batch))
        with ThreadPoolExecutor(max_workers=len(batch)) as ex:
            res = [f.result() for f in [ex.submit(evaluate, tuner, t, o) for t, o in batch]]
        for (tag, om), r in zip(batch, res):
            r["kind"] = "bo"
            r["round"] = rnd + 1
            results.append(r)
            if r["status"] == "OK":
                real.append((om, -r["J_power_mse_kW2"]))
            log(f"{tag}: {r['status']}  J={r.get('J_power_mse_kW2', float('nan')):.1f} kW^2  wall={r['wall_s'] / 3600:.2f} h")
        write_table(results)
        n_done += nq
        rnd += 1

    best = min((r for r in results if r["kind"] != "baseline" and r["status"] == "OK"),
               key=lambda r: r["J_power_mse_kW2"])
    base = results[0]
    log(f"done. baseline J={base.get('J_power_mse_kW2')}, best {best['tag']} J={best['J_power_mse_kW2']:.1f} "
        f"omega_pc={np.round(best['omega_pc'], 4).tolist()}")
    with open(os.path.join(ROOT, "final_results.json"), "w") as f:
        json.dump({"baseline": base, "best": best, "n_evals": len(results) - 1}, f, indent=1)


if __name__ == "__main__":
    main()
