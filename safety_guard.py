"""Laptop backstop for long runs: watches a running pipeline and steps in only when something is abnormal.

Usage:  python safety_guard.py <PID of run_all.py>      (start it after run_all.py; it exits when the run ends)

Windows and the CPU firmware already protect the hardware (the CPU throttles itself at its temperature limit), and
the guard never overrides that. It is a second line for abnormal situations, with limits above normal full-load
values so it never slows a normal run:
- CPU: the pipeline is meant to run with DTSYNC_WORKERS=6 (6 of 12 logical cores); the guard reports the number of
  pipeline processes, CPU load and the actual clock from the Windows performance counter (a clock falling below the
  3.3 GHz base under load is a sign of thermal throttling; the CPU temperature itself needs administrator rights).
- RAM at 90% or more: warning. At 95% or more: stop the run (finished patients are saved; rerun to resume).
- On battery: suspend all pipeline processes until the charger is back; stop after 240 minutes on battery.
Every 10 minutes it writes a status line with real numbers to logs/safety.log, and peaks at the end.
"""
import os, subprocess, sys, time
import psutil

CHECK_EVERY_SECONDS = 30
REPORT_EVERY_SECONDS = 600
RAM_WARN_PERCENT = 90
RAM_STOP_PERCENT = 95
BATTERY_MAX_WAIT_MINUTES = 240
LOG = os.path.join("logs", "safety.log")


def log(msg):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def effective_clock_mhz():
    """Actual average clock from the Windows performance counter (% of base clock); falls back to psutil."""
    try:
        out = subprocess.run(["typeperf", r"\Processor Information(_Total)\% Processor Performance", "-sc", "1"],
                             capture_output=True, text=True, timeout=20).stdout
        perf = float(out.strip().splitlines()[1].split(",")[1].strip('"'))
        return perf / 100 * psutil.cpu_freq().max
    except Exception:
        f = psutil.cpu_freq()
        return f.current if f else float("nan")


def tree(root):
    try:
        return [root] + root.children(recursive=True)
    except psutil.NoSuchProcess:
        return []


def on_battery():
    b = psutil.sensors_battery()
    return b is not None and not b.power_plugged


def stop(root, reason):
    log(f"STOP: {reason}. Terminating the run; finished patients are saved, rerun run_all.py to resume.")
    procs = tree(root)
    for p in reversed(procs):            # workers first, run_all.py last
        try:
            p.kill()
        except psutil.NoSuchProcess:
            pass


def main(pid):
    os.makedirs("logs", exist_ok=True)
    root = psutil.Process(pid)
    log(f"guard started for PID {pid} ({' '.join(root.cmdline()[-2:])}); limits: RAM warn {RAM_WARN_PERCENT}%, "
        f"stop {RAM_STOP_PERCENT}%, pause on battery (max {BATTERY_MAX_WAIT_MINUTES} min)")
    peak_ram = peak_cpu = 0.0
    min_clock, paused, last_report = None, 0.0, 0.0
    psutil.cpu_percent()
    while root.is_running() and root.status() != psutil.STATUS_ZOMBIE:
        time.sleep(CHECK_EVERY_SECONDS)
        if not root.is_running():
            break
        ram = psutil.virtual_memory().percent
        cpu = psutil.cpu_percent()
        peak_ram, peak_cpu = max(peak_ram, ram), max(peak_cpu, cpu)
        if ram >= RAM_STOP_PERCENT:
            stop(root, f"system RAM at {ram:.0f}% (limit {RAM_STOP_PERCENT}%)")
            break
        if ram >= RAM_WARN_PERCENT:
            log(f"warning: system RAM at {ram:.0f}%")
        if on_battery():
            procs = tree(root)
            log(f"on battery: suspending {len(procs)} pipeline processes until the charger is back")
            for p in procs:
                try:
                    p.suspend()
                except psutil.NoSuchProcess:
                    pass
            t0 = time.monotonic()
            while on_battery() and time.monotonic() - t0 < 60 * BATTERY_MAX_WAIT_MINUTES:
                time.sleep(15)
            paused += time.monotonic() - t0
            if on_battery():
                for p in procs:
                    try:
                        p.resume()
                    except psutil.NoSuchProcess:
                        pass
                stop(root, f"still on battery after {BATTERY_MAX_WAIT_MINUTES} min")
                break
            for p in procs:
                try:
                    p.resume()
                except psutil.NoSuchProcess:
                    pass
            log(f"charger connected after {time.monotonic() - t0:.0f} s, resumed")
        if time.monotonic() - last_report >= REPORT_EVERY_SECONDS:
            last_report = time.monotonic()
            clock = effective_clock_mhz()
            if cpu > 80:
                min_clock = clock if min_clock is None else min(min_clock, clock)
            procs = [p for p in tree(root) if p.is_running()]
            rss = sum(p.memory_info().rss for p in procs if p.is_running()) / 2 ** 30
            log(f"status: RAM {ram:.0f}% (pipeline {rss:.2f} GB in {len(procs)} processes), CPU {cpu:.0f}%, "
                f"clock {clock:.0f} MHz")
    log(f"guard finished: peak RAM {peak_ram:.0f}%, peak CPU {peak_cpu:.0f}%, lowest clock under load "
        f"{min_clock if min_clock is not None else float('nan'):.0f} MHz, paused on battery {paused:.0f} s")


if __name__ == "__main__":
    main(int(sys.argv[1]))
