"""Parallel cohort runner.
Usage: python run_batch_mp.py --n 200 --P 256 --out results/main --noise 0.05 --workers 7
Each patient is independent and fully determined by its seed, so results are identical to the serial runner."""
import os
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
import argparse, multiprocessing, pickle, time
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import dtsync as d
from run_batch import POLICIES


def one(seed, P, noise, out):
    f = os.path.join(out, f"patient_{seed}.pkl")
    if os.path.exists(f):
        return seed, None, 0.0
    t = time.time()
    r = d.run_patient(seed, P=P, policies=POLICIES, noise=noise)
    for pol in r["results"].values():
        pol["daily"] = pol["daily"].astype(np.float32)
    r["true_area"] = r["true_area"].astype(np.float32)
    r["runtime_s"] = time.time() - t
    with open(f, "wb") as fh:
        pickle.dump(r, fh)
    return seed, r["t_prog"], r["runtime_s"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--P", type=int, default=256)
    ap.add_argument("--seed0", type=int, default=2000)
    ap.add_argument("--noise", type=float, default=0.05)
    ap.add_argument("--out", default="results/main")
    ap.add_argument("--workers", type=int,
                    default=int(os.environ.get("DTSYNC_WORKERS", max(1, min(8, (os.cpu_count() or 2) - 2)))))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    ctx = multiprocessing.get_context("spawn")          # same behaviour on Windows, macOS and Linux
    with ProcessPoolExecutor(max_workers=a.workers, mp_context=ctx) as ex:
        futs = [ex.submit(one, a.seed0 + i, a.P, a.noise, a.out) for i in range(a.n)]
        for k, fu in enumerate(as_completed(futs), 1):
            seed, tp, rt = fu.result()
            print(f"[{k}/{a.n}] seed {seed} t_prog={tp} patient {rt:.0f}s total {time.time() - t0:.0f}s", flush=True)
