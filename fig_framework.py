"""Fig. 1: the synchronisation loop of an imaging-driven digital twin. Writes figs/paper/fig1_framework.{png,pdf}."""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib import font_manager
for fam in ("Times New Roman", "Liberation Serif", "DejaVu Serif"):
    if any(fam in f.name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = fam
        break
plt.rcParams.update({"font.size": 7, "mathtext.fontset": "stix", "savefig.dpi": 300})

fig, ax = plt.subplots(figsize=(4.72, 1.47))          # 12 cm wide, LNCS text width is 12.2 cm
ax.set_xlim(0, 101); ax.set_ylim(5.8, 40); ax.axis("off")

def box(x, y, w, h, title, body, fc):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=1.5", fc=fc, ec="black", lw=0.7))
    ax.text(x + w / 2, y + h - 2.4, title, ha="center", va="top", fontweight="bold", fontsize=7.5)
    ax.text(x + w / 2, y + h - 8.4, body, ha="center", va="top", fontsize=6.5, linespacing=1.3)

def arrow(p, q, text, dy=1.4):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=8, lw=0.9, color="black"))
    ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2 + dy, text, ha="center", va="bottom", fontsize=6.5)

box(1, 15, 26, 24, "Physical twin", "Patient with glioblastoma\nGrowth, chemoradiation,\npatient-specific response\nand recurrence", "#f2f2f2")
box(38, 15, 26, 24, "Digital twin", "Reaction-diffusion model\non patient anatomy\nParticle filter over\n$(D_w,\\ \\rho,\\ L,\\ \\gamma)$", "#dbe8f5")
box(75, 15, 25, 24, "Scheduling policy", "Forecast P(progression)\nScan if $P \\geq p^{*}$\n(gap 28 to 120 days)\nor fixed calendar", "#fbe3d6")
arrow((28.6, 26), (36.4, 26), "MRI scan")
ax.text(32.5, 24.3, "FLAIR and\nT1Gd masks", ha="center", va="top", fontsize=6.0, color="0.3")
arrow((65.6, 26), (73.4, 26), "Forecast")
ax.text(69.5, 24.3, "with\nuncertainty", ha="center", va="top", fontsize=6.0, color="0.3")
ax.add_patch(FancyArrowPatch((87.5, 14.0), (14.0, 14.0), arrowstyle="-|>", mutation_scale=8, lw=0.9, color="black",
                             connectionstyle="arc3,rad=-0.16"))
fig.tight_layout(pad=0.1)
os.makedirs("figs/paper", exist_ok=True)
fig.savefig("figs/paper/fig1_framework.png"); fig.savefig("figs/paper/fig1_framework.pdf")
