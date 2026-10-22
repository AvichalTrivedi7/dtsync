"""Mean follow-up scans per patient for progressors versus patients stable to day 420, per policy.
Usage: python split_scans.py figs/main/patients.csv"""
import csv, sys
import numpy as np

EVAL_END = 420


def boot(x, B=2000, seed=0):
    x = np.asarray(x, float)
    if len(x) == 0:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(seed)
    bs = [rng.choice(x, len(x)).mean() for _ in range(B)]
    return x.mean(), np.percentile(bs, 2.5), np.percentile(bs, 97.5)


if __name__ == "__main__":
    rows = list(csv.DictReader(open(sys.argv[1], newline="")))
    pols = list(dict.fromkeys(r["policy"] for r in rows))
    prog = lambda r: r["t_prog"] not in ("", "None") and int(r["t_prog"]) <= EVAL_END
    n_prog = len({r["seed"] for r in rows if prog(r)})
    n_stab = len({r["seed"] for r in rows}) - n_prog
    print(f"{n_prog} progressors (true progression by day {EVAL_END}), {n_stab} stable to day {EVAL_END}")
    print(f"{'policy':<10} {'progressors: scans [95% CI]':>30} {'stable: scans [95% CI]':>26}")
    for pol in pols:
        if pol == "static":
            continue
        a = boot([int(r["n_scans"]) for r in rows if r["policy"] == pol and prog(r)])
        b = boot([int(r["n_scans"]) for r in rows if r["policy"] == pol and not prog(r)])
        print(f"{pol:<10} {'%.1f [%.1f, %.1f]' % a:>30} {'%.1f [%.1f, %.1f]' % b:>26}")
