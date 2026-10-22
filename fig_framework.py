"""Fig. 1: the synchronisation loop of an imaging-driven digital twin."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib import font_manager
for fam in ("Times New Roman", "Liberation Serif", "DejaVu Serif"):
    if any(fam in f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = fam
        break
plt.rcParams.update({"font.size": 8.5, "savefig.dpi": 300})

fig, ax = plt.subplots(figsize=(6.8, 2.9))
ax.set_xlim(0, 100); ax.set_ylim(-2, 41); ax.axis("off")

def box(x, y, w, h, title, body, fc):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=1.5", fc=fc, ec="black", lw=0.8))
    ax.text(x + w / 2, y + h - 2.6, title, ha="center", va="top", fontweight="bold")
    ax.text(x + w / 2, y + h - 7.2, body, ha="center", va="top", fontsize=7.6, linespacing=1.35)

def arrow(p, q, text, dy=1.6, rad=0.0, ls="-"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=10, lw=1.0, color="black",
                                 connectionstyle=f"arc3,rad={rad}", linestyle=ls))
    ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2 + dy, text, ha="center", va="bottom", fontsize=7.4)

box(2, 13, 25, 26, "Physical twin", "Patient with glioblastoma\nGrowth, chemoradiation,\npatient-specific response\nand recurrence", "#f2f2f2")
box(38, 13, 26, 26, "Digital twin", "Reaction-diffusion model\non patient anatomy\nParticle filter over\n$(D_w,\\ \\rho,\\ L,\\ \\gamma)$", "#dbe8f5")
box(74, 13, 24, 26, "Scheduling policy", "Forecast P(progression)\nScan if $P \\geq p^{*}$\n(gap 28 to 120 days)\nor fixed calendar", "#fbe3d6")
arrow((28.5, 26), (37, 26), "MRI scan", dy=1.4)
ax.text(32.75, 24.2, "FLAIR and\nT1Gd masks", ha="center", va="top", fontsize=7.0, color="0.3")
arrow((65.5, 26), (73, 26), "Forecast", dy=1.4)
ax.text(69.25, 24.2, "with\nuncertainty", ha="center", va="top", fontsize=7.0, color="0.3")
ax.add_patch(FancyArrowPatch((86, 12.2), (14.5, 12.2), arrowstyle="-|>", mutation_scale=10, lw=1.0, color="black",
                             connectionstyle="arc3,rad=-0.22"))
ax.text(50, 0.6, "Scan request: the twin decides when the next image is acquired (twin-to-patient link)",
        ha="center", fontsize=7.6, style="italic")
fig.tight_layout(); fig.savefig("figs/framework.png"); fig.savefig("figs/framework.pdf")
