"""Run the virtual cohort. Usage: python run_batch.py --n 40 --P 128 --out results/pilot --noise 0.05"""
import argparse, os, pickle, time
import numpy as np
import dtsync as d

POLICIES = ("static", "fixed_30", "fixed_45", "fixed_60", "fixed_90", "fixed_120", "reactive",
            "trig_0.02", "trig_0.05", "trig_0.1", "trig_0.2", "trig_0.4", "trig_0.6")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--P", type=int, default=128)
    ap.add_argument("--seed0", type=int, default=2000)
    ap.add_argument("--noise", type=float, default=0.05)
    ap.add_argument("--out", default="results/pilot")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    for i in range(a.n):
        f = os.path.join(a.out, f"patient_{a.seed0 + i}.pkl")
        if os.path.exists(f):
            continue
        r = d.run_patient(a.seed0 + i, P=a.P, policies=POLICIES, noise=a.noise)
        for pol in r["results"].values():          # keep files small
            pol["daily"] = pol["daily"].astype(np.float32)
        r["true_area"] = r["true_area"].astype(np.float32)
        with open(f, "wb") as fh:
            pickle.dump(r, fh)
        print(f"[{i + 1}/{a.n}] seed {a.seed0 + i} t_prog={r['t_prog']} elapsed {time.time() - t0:.0f}s", flush=True)
