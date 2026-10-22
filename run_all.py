"""Night 1 pipeline. From the repo folder run:   .venv\\Scripts\\python.exe run_all.py
Resumable: if the laptop restarts, run the same command again and finished patients are skipped.
Progress: logs/run_all.log (one line per job) and logs/<job>.log (full output)."""
import os, subprocess, sys, time

PY = sys.executable
JOBS = [
    ("smoke",           ["run_batch_mp.py", "--n", "2", "--P", "32", "--out", "results/smoke", "--workers", "2"]),
    ("main",            ["run_batch_mp.py", "--n", "200", "--P", "256", "--out", "results/main", "--noise", "0.05"]),
    ("noise10",         ["run_batch_mp.py", "--n", "100", "--P", "256", "--out", "results/noise10", "--noise", "0.10"]),
    ("p512",            ["run_batch_mp.py", "--n", "40", "--P", "512", "--out", "results/p512", "--noise", "0.05"]),
    ("bench",           ["bench.py"]),
    ("analyze_main",    ["analyze.py", "results/main", "figs/main"]),
    ("analyze_noise10", ["analyze.py", "results/noise10", "figs/noise10"]),
    ("analyze_p512",    ["analyze.py", "results/p512", "figs/p512"]),
]

if __name__ == "__main__":
    os.makedirs("logs", exist_ok=True)
    only = set(sys.argv[1:])            # optional: python run_all.py main analyze_main
    with open("logs/run_all.log", "a", encoding="utf-8") as master:
        for name, args in JOBS:
            if only and name not in only:
                continue
            t0 = time.time()
            master.write(f"{time.strftime('%H:%M:%S')} START {name}\n"); master.flush()
            with open(f"logs/{name}.log", "a", encoding="utf-8") as fh:
                code = subprocess.call([PY] + args, stdout=fh, stderr=subprocess.STDOUT)
            status = "OK" if code == 0 else f"FAILED (exit {code}), see logs/{name}.log"
            master.write(f"{time.strftime('%H:%M:%S')} {status} {name} in {(time.time() - t0) / 60:.1f} min\n")
            master.flush()
            print(f"{name}: {status}", flush=True)
            if name == "smoke" and code != 0:
                print("Smoke test failed, stopping so nothing runs on a broken setup.")
                break
