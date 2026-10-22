"""Summarise a results folder. Usage: python analyze.py results/pilot figs/pilot"""
import glob, os, pickle, sys, json
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

for fam in ("Times New Roman", "Liberation Serif", "DejaVu Serif"):
    if any(fam in f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = fam
        break
plt.rcParams.update({"font.size": 9, "axes.linewidth": 0.6, "savefig.dpi": 300})

import dtsync as d


def load(folder):
    rs = []
    for f in sorted(glob.glob(os.path.join(folder, "patient_*.pkl"))):
        with open(f, "rb") as fh:
            rs.append(pickle.load(fh))
    return rs


def boot_ci(x, fn=np.mean, B=2000, seed=0):
    x = np.asarray([v for v in x if np.isfinite(v)])
    if len(x) == 0:
        return np.nan, np.nan, np.nan
    rng = np.random.default_rng(seed)
    bs = [fn(rng.choice(x, len(x))) for _ in range(B)]
    return fn(x), np.percentile(bs, 2.5), np.percentile(bs, 97.5)


def per_patient(r, pol, key):
    ev = r["results"][pol]["evals"]
    tp = r["t_prog"] or 10 ** 9
    vals = [ev[t][key] for t in sorted(ev) if t < tp]
    return np.mean(vals) if vals else np.nan


def summarise(rs):
    pols = list(rs[0]["results"].keys())
    rows = {}
    for pol in pols:
        row = {}
        for key in ("dice", "rel_err", "covered", "width"):
            row[key] = boot_ci([per_patient(r, pol, key) for r in rs])
        if pol != "static":
            scans = [r["results"][pol]["n_scans"] for r in rs]
            row["scans"] = boot_ci(scans)
            delays, missed, false_alarm = [], 0, 0
            for r in rs:
                tp, det = r["t_prog"], r["results"][pol]["detected"]
                if tp is not None and tp <= d.EVAL_END:      # progression inside the evaluation window
                    if det is None:
                        missed += 1
                    elif det < tp - 30:                       # alarm well before true progression
                        false_alarm += 1
                    else:                                     # within 30 d measurement tolerance: on time
                        delays.append(max(det - tp, 0))
                elif det is not None and (tp is None or det < tp - 30):
                    false_alarm += 1
            ms = [r["results"][pol].get("assim_ms") for r in rs]
            row["assim_ms"] = float(np.mean([m for m in ms if m])) if any(ms) else np.nan
            row["delay"] = boot_ci(delays)
            row["delay_median"] = float(np.median(delays)) if delays else np.nan
            row["missed"], row["false_alarm"], row["n_detected"] = missed, false_alarm, len(delays)
        rows[pol] = row
    return rows


def print_table(rows, n):
    print(f"N = {n} virtual patients")
    print(f"{'policy':<10} {'FLAIR Dice':>18} {'rel. area err':>18} {'90% cover':>10} {'scans':>14} {'delay (d)':>18} {'med':>5} {'miss':>4} {'FA':>3}")
    for pol, r in rows.items():
        dsc = "%.3f [%.3f,%.3f]" % r["dice"]
        err = "%.3f [%.3f,%.3f]" % r["rel_err"]
        cov = "%.2f" % r["covered"][0]
        if pol == "static":
            print(f"{pol:<10} {dsc:>18} {err:>18} {cov:>10}")
            continue
        r.setdefault("assim_ms", float("nan"))
        sc = "%.1f [%.1f,%.1f]" % r["scans"]
        dl = "%.1f [%.1f,%.1f]" % r["delay"]
        print(f"{pol:<10} {dsc:>18} {err:>18} {cov:>10} {sc:>14} {dl:>18} {r['delay_median']:>5.0f} {r['missed']:>4} {r['false_alarm']:>3}  {r['assim_ms']:.0f}ms")


def fig_tradeoff(rows, out):
    fx = [p for p in rows if p.startswith("fixed")]
    tg = [p for p in rows if p.startswith("trig")]
    fig, ax = plt.subplots(figsize=(3.6, 2.8))
    styles = ((fx, "s", "-", "black", "white", "Fixed interval", (5, 4), "left", "{} d"),
              (tg, "o", "-", "tab:blue", "tab:blue", "Uncertainty-triggered", (-5, -11), "right", "{}"))
    for group, mk, ls, col, mfc, lab, off, ha, fmt in styles:
        xs = np.array([rows[p]["scans"][0] for p in group]); ys = np.array([rows[p]["delay"][0] for p in group])
        lo = np.array([rows[p]["delay"][1] for p in group]); hi = np.array([rows[p]["delay"][2] for p in group])
        o = np.argsort(xs)
        ax.errorbar(xs[o], ys[o], yerr=[ys[o] - lo[o], hi[o] - ys[o]], fmt="none", ecolor=col, alpha=0.3,
                    elinewidth=0.7, capsize=1.5)
        ax.plot(xs[o], ys[o], ls, color=col, lw=1.0, marker=mk, ms=4, mfc=mfc, mec=col, label=lab)
        for p, x, y in zip(group, xs, ys):
            ax.annotate(fmt.format(p.split("_")[1]), (x, y), textcoords="offset points", xytext=off,
                        fontsize=6.5, ha=ha, color=col)
    if "reactive" in rows:
        r = rows["reactive"]
        ax.errorbar([r["scans"][0]], [r["delay"][0]], yerr=[[r["delay"][0] - r["delay"][1]], [r["delay"][2] - r["delay"][0]]],
                    fmt="^", color="tab:red", ms=5.5, elinewidth=0.7, capsize=1.5, alpha=0.9, label="Reactive rule (no twin)")
    ax.set_ylim(bottom=0)
    xmin = min(rows[p]["scans"][0] for p in rows if p != "static")
    ax.set_xlim(left=xmin - 0.45)
    ax.set_xlabel("Follow-up scans per patient (mean)")
    ax.set_ylabel("Detection delay in days (mean, 95% CI)")
    ax.legend(frameon=False, fontsize=7, loc="upper right")
    ax.grid(alpha=0.25, lw=0.5)
    fig.tight_layout(); fig.savefig(out); fig.savefig(out.replace(".png", ".pdf")); plt.close(fig)


def fig_tracking(rs, out, pols=("static", "fixed_60", "trig_0.1")):
    days = sorted(rs[0]["results"]["static"]["evals"].keys())
    fig, ax = plt.subplots(figsize=(3.4, 2.6))
    styles = {"static": ("--", "Static model (no sync)"), "fixed_60": ("-", "Fixed 60-day sync"),
              "trig_0.1": ("-", "Triggered sync")}
    for pol in pols:
        med = []
        for t in days:
            vals = [r["results"][pol]["evals"][t]["dice"] for r in rs if (r["t_prog"] or 10 ** 9) > t]
            med.append(np.median(vals) if len(vals) >= 5 else np.nan)
        st, lab = styles.get(pol, ("-", pol))
        ax.plot(days, med, st, lw=1.2, label=lab, color="tab:blue" if pol.startswith("trig") else ("0.5" if pol == "static" else "black"))
    ax.axvspan(d.T_RT0, d.T_RT1, color="0.85", lw=0)
    ax.set_xlabel("Days since diagnosis"); ax.set_ylabel("FLAIR Dice before progression (median)")
    ax.legend(frameon=False, fontsize=8); ax.grid(alpha=0.25, lw=0.5)
    fig.tight_layout(); fig.savefig(out); plt.close(fig)


def fig_example(r, out, pols=("static", "fixed_60", "trig_0.1")):
    fig, axs = plt.subplots(1, 2, figsize=(6.8, 2.5), sharex=True)
    t = np.arange(d.HORIZON + 1)
    for ax, col, true, lab in ((axs[0], 3, r["true_flair"], "FLAIR area (mm$^2$)"),
                               (axs[1], 0, r["true_area"], "Enhancing (T1Gd) area (mm$^2$)")):
        ax.plot(t, true, color="black", lw=1.4, label="Ground truth")
        colors = {"static": "0.55", "fixed_60": "tab:orange", "trig_0.1": "tab:blue"}
        for pol in pols:
            dl = r["results"][pol]["daily"]
            m = slice(d.T_PRE + 1, d.HORIZON + 1)
            ax.plot(t[m], dl[m, col + 1], color=colors[pol], lw=1, label=pol.replace("_", " "))
            ax.fill_between(t[m], dl[m, col], dl[m, col + 2], color=colors[pol], alpha=0.15, lw=0)
            for sd in r["results"][pol]["scan_days"]:
                ax.plot([sd], [ax.get_ylim()[0]], marker="|", color=colors[pol], ms=6)
        if r["t_prog"]:
            ax.axvline(r["t_prog"], color="red", lw=0.8, ls=":")
        ax.axvspan(d.T_RT0, d.T_RT1, color="0.9", lw=0)
        ax.set_ylabel(lab); ax.set_xlabel("Days since diagnosis"); ax.grid(alpha=0.25, lw=0.5)
    axs[0].legend(frameon=False, fontsize=7)
    fig.tight_layout(); fig.savefig(out); plt.close(fig)


if __name__ == "__main__":
    folder = sys.argv[1]
    figdir = sys.argv[2] if len(sys.argv) > 2 else "figs"
    os.makedirs(figdir, exist_ok=True)
    rs = load(folder)
    tps = np.array([r["t_prog"] if r["t_prog"] is not None else np.inf for r in rs])
    inwin = tps[tps <= d.EVAL_END]
    print(f"Cohort: {len(rs)} patients, {len(inwin)} progress by day {d.EVAL_END} "
          f"(median {np.median(inwin):.0f} d, IQR {np.percentile(inwin, 25):.0f} to {np.percentile(inwin, 75):.0f})")
    rows = summarise(rs)
    print_table(rows, len(rs))
    fig_tradeoff(rows, os.path.join(figdir, "tradeoff.png"))
    fig_tracking(rs, os.path.join(figdir, "tracking.png"))
    prog = [r for r in rs if r["t_prog"]]
    ex = prog[len(prog) // 2] if prog else rs[0]
    fig_example(ex, os.path.join(figdir, "example_patient.png"))
    # compact per-patient table (small enough to upload for joint analysis)
    import csv
    with open(os.path.join(figdir, "patients.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["seed", "policy", "t_prog", "detected", "n_scans", "scan_days", "dice_pre", "rel_err_pre",
                    "cover_pre", "width_pre", "assim_ms", "Dw", "rho", "L", "gamma"])
        for r in rs:
            th = r["theta"]
            for pol, x in r["results"].items():
                w.writerow([r["seed"], pol, r["t_prog"], x["detected"], x["n_scans"],
                            " ".join(map(str, x["scan_days"])),
                            *(round(per_patient(r, pol, k), 4) for k in ("dice", "rel_err", "covered", "width")),
                            x.get("assim_ms"), round(float(np.exp(th[0])), 4), round(float(np.exp(th[1])), 5),
                            round(float(th[2]), 3), round(float(np.exp(th[3])), 3)])
    with open(os.path.join(figdir, "summary.json"), "w") as fh:
        json.dump({k: {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in v.items()} for k, v in rows.items()},
                  fh, indent=1, default=float)
