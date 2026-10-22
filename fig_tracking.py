"""Paper version of the tracking figure from analyze.py (same content: median FLAIR Dice before progression over
time for the static, 60-day and triggered p* = 0.1 twins), 8.5 cm wide, Times, markers so it reads in greyscale.
Usage: python fig_tracking.py results/main   -> figs/paper/figS_tracking.{png,pdf}"""
import os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import analyze
import dtsync as d

plt.rcParams.update({"font.size": 8, "mathtext.fontset": "stix"})
rs = analyze.load(sys.argv[1] if len(sys.argv) > 1 else "results/main")
days = sorted(rs[0]["results"]["static"]["evals"].keys())
styles = {"static": dict(ls="--", color="0.45", marker="", label="Static model (no sync)"),
          "fixed_60": dict(ls="-", color="black", marker="s", mfc="white", ms=3, label="Fixed 60-day sync"),
          "trig_0.1": dict(ls="-", color="tab:blue", marker="o", ms=3, label="Triggered sync ($p^{*} = 0.1$)")}
fig, ax = plt.subplots(figsize=(3.35, 2.45))
for pol, st in styles.items():
    med = []
    for t in days:
        vals = [r["results"][pol]["evals"][t]["dice"] for r in rs if (r["t_prog"] or 10 ** 9) > t]
        med.append(np.median(vals) if len(vals) >= 5 else np.nan)
    ax.plot(days, med, lw=1.1, markevery=2, **st)
ax.axvspan(d.T_RT0, d.T_RT1, color="0.88", lw=0)
ax.text((d.T_RT0 + d.T_RT1) / 2, 0.005, "CRT", transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontsize=7)
ax.set_xlabel("Days since diagnosis"); ax.set_ylabel("FLAIR Dice before progression (median)")
ax.legend(frameon=False, fontsize=7, loc="lower left"); ax.grid(alpha=0.25, lw=0.5)
fig.tight_layout(pad=0.2)
os.makedirs("figs/paper", exist_ok=True)
fig.savefig("figs/paper/figS_tracking.png", dpi=300); fig.savefig("figs/paper/figS_tracking.pdf")
print("written figs/paper/figS_tracking.png and .pdf")
