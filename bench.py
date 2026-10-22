"""Runtime of the twin's two operations: propagating one simulated day, and assimilating one scan.
Writes figs/bench.json and prints a small table."""
import json, os, platform, time
import numpy as np
import dtsync as d


def bench(P, reps=20):
    rng = np.random.default_rng(0)
    g = d.Grid(64, 2.0)
    pat = d.Patient(rng, g)
    pat.seed = 0
    tw = d.Twin(g, P, rng)
    tw.initialise(pat.observe(0))
    for day in range(d.T_PRE):
        tw.step_day(day)
    prop = []
    for _ in range(reps):
        t = time.perf_counter(); tw.step_day(d.T_RT1 + 10); prop.append(time.perf_counter() - t)
    obs = pat.observe(d.T_PRE)
    assim = []
    for _ in range(reps):
        c, th = tw.c.copy(), tw.theta.copy()
        t = time.perf_counter(); tw.assimilate(obs); assim.append(time.perf_counter() - t)
        tw.c, tw.theta = c, th
    days = d.SIM_END - d.T_PRE
    return dict(P=P, propagate_day_ms=(1e3 * np.mean(prop), 1e3 * np.std(prop)),
                assimilate_ms=(1e3 * np.mean(assim), 1e3 * np.std(assim)),
                full_followup_s=np.mean(prop) * days)


if __name__ == "__main__":
    os.makedirs("figs", exist_ok=True)
    out = dict(cpu=platform.processor() or platform.machine(), python=platform.python_version(),
               numpy=np.__version__, runs=[bench(P) for P in (128, 256, 512)])
    print(f"CPU: {out['cpu']}")
    for r in out["runs"]:
        print(f"P={r['P']:4d}  one day: {r['propagate_day_ms'][0]:.1f} +/- {r['propagate_day_ms'][1]:.1f} ms   "
              f"one scan: {r['assimilate_ms'][0]:.1f} +/- {r['assimilate_ms'][1]:.1f} ms   "
              f"{d.SIM_END - d.T_PRE}-day follow-up: {r['full_followup_s']:.1f} s")
    with open("figs/bench.json", "w") as fh:
        json.dump(out, fh, indent=1, default=float)
