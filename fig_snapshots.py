"""Truth versus twin forecast maps for one virtual patient. Usage: python fig_snapshots.py [seed] [policy]"""
import sys, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import dtsync as d

for fam in ("Times New Roman", "Liberation Serif", "DejaVu Serif"):
    if any(fam in f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = fam
        break
plt.rcParams.update({"font.size": 8, "savefig.dpi": 300})

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 2003
policy = sys.argv[2] if len(sys.argv) > 2 else "trig_0.1"
rng = np.random.default_rng(seed)
g = d.Grid(64, 2.0)
pat = d.Patient(rng, g)
pat.seed = seed
tw = d.Twin(g, 256, rng)
tw.initialise(pat.observe(0))
for day in range(d.T_PRE):
    tw.step_day(day)
obs = pat.observe(d.T_PRE)
pat.obs_area_pre = obs[1].sum() * g.dx ** 2
pat.obs_flair_pre = obs[0].sum() * g.dx ** 2
tw.assimilate(obs)
tp = pat.t_prog or 300
days = sorted(set([d.T_FU1, max(d.T_FU1 + 30, tp - 60), tp, min(tp + 45, d.SIM_END)]))
res = d.run_policy(tw, pat, policy, rng, set(), snap_days=set(days))
os.makedirs("figs", exist_ok=True)
fig, axs = plt.subplots(2, 4, figsize=(6.8, 3.6))
anat = np.ma.masked_where(g.m == 0, g.m)
ys, xs = np.nonzero(g.brain)
crop = (slice(ys.min(), ys.max() + 1), slice(xs.min(), xs.max() + 1))
for j, t in enumerate(days):
    ft, tt = pat.true_masks(t)
    for i in range(2):
        ax = axs[i, j]
        ax.imshow(anat[crop], cmap="Greys", vmin=0, vmax=2.5, interpolation="nearest")
        if i == 0:
            ax.imshow(np.ma.masked_where(~ft, ft)[crop], cmap="Blues", vmin=0, vmax=1.6, alpha=0.8)
            ax.imshow(np.ma.masked_where(~tt, tt)[crop], cmap="Reds", vmin=0, vmax=1.2, alpha=0.9)
            ax.set_title(f"Day {t}" + (" (true progression)" if t == tp and pat.t_prog else ""), fontsize=8)
        else:
            pf = res["snaps"][t][0]
            ax.imshow(np.ma.masked_where(pf < 0.02, pf)[crop], cmap="viridis", vmin=0, vmax=1, alpha=0.9)
            ax.contour(ft[crop].astype(float), levels=[0.5], colors="white", linewidths=0.8)
            pt1 = res["snaps"][t][1]
            if pt1.max() >= 0.5:
                ax.contour(pt1[crop], levels=[0.5], colors="red", linewidths=0.9, linestyles="--")
        ax.set_xticks([]); ax.set_yticks([])
axs[0, 0].set_ylabel("Ground truth\n(FLAIR blue, T1Gd red)")
axs[1, 0].set_ylabel("Twin forecast: P(FLAIR),\nP(T1Gd)=0.5 dashed red")
fig.tight_layout()
fig.savefig(f"figs/snapshots_{seed}.png")
print("scan days:", res["scan_days"], "detected:", res["detected"], "t_prog:", pat.t_prog, "days shown:", days)
