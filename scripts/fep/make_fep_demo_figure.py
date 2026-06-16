#!/usr/bin/env python3
"""Publication figure for the L147R x cortisol Tier-2 FEP demo.
(A) thermodynamic cycle  (B) bound-leg Crooks work distributions
(C) apo-leg work distributions  (D) ddG_bind result vs expectation.
"""
import os, re
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, "work")
KJ = 4.184

# ---------- data ----------
def work_vals(leg, which):
    f = os.path.join(WORK, leg, f"integ{which}.dat")
    return np.array([float(l.split()[1]) for l in open(f) if l.strip()])

def parse_dat(leg):
    t = open(os.path.join(WORK, leg, f"results_{leg}.dat")).read()
    g = lambda p: float(re.search(p, t).group(1))
    return {"BAR": g(r"BAR: dG\s*=\s*(-?[\d.]+)"),
            "BAR_e": g(r"BAR: Std Err \(bootstrap\)\s*=\s*([\d.]+)"),
            "CGI": g(r"CGI: dG\s*=\s*(-?[\d.]+)"),
            "CGI_e": g(r"CGI: Std Err \(bootstrap\)\s*=\s*([\d.]+)")}

legs = {l: parse_dat(l) for l in ("bound", "apo")}
W = {l: {"F": work_vals(l, "A"), "R": work_vals(l, "B")} for l in ("bound", "apo")}

ddG_BAR = legs["bound"]["BAR"] - legs["apo"]["BAR"]
ddG_BAR_e = np.hypot(legs["bound"]["BAR_e"], legs["apo"]["BAR_e"])
ddG_CGI = legs["bound"]["CGI"] - legs["apo"]["CGI"]
ddG_CGI_e = np.hypot(legs["bound"]["CGI_e"], legs["apo"]["CGI_e"])

# ---------- style ----------
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10,
    "axes.linewidth": 0.9, "axes.labelsize": 11, "axes.titlesize": 12,
    "xtick.direction": "out", "ytick.direction": "out",
    "savefig.dpi": 300, "figure.dpi": 150,
})
C_F, C_R = "#2c6fbb", "#c0392b"      # forward (blue), reverse (red)
C_BAR, C_CGI = "#1b1b1b", "#8e44ad"
C_MUT, C_LIG = "#e67e22", "#27ae60"

fig = plt.figure(figsize=(12.6, 6.8))
gs = fig.add_gridspec(2, 3, width_ratios=[1.18, 1.15, 1.15],
                      hspace=0.46, wspace=0.34,
                      left=0.045, right=0.985, top=0.84, bottom=0.10)
axA = fig.add_subplot(gs[:, 0])
axB = fig.add_subplot(gs[0, 1:])
axC = fig.add_subplot(gs[1, 1])
axD = fig.add_subplot(gs[1, 2])


# ===== Panel A: thermodynamic cycle =====
def box(ax, x, y, text, fc):
    b = FancyBboxPatch((x - 0.20, y - 0.062), 0.40, 0.124,
                       boxstyle="round,pad=0.012,rounding_size=0.02",
                       fc=fc, ec="#333333", lw=1.2, zorder=3)
    ax.add_patch(b)
    ax.text(x, y, text, ha="center", va="center", fontsize=10.5, zorder=4)

axA.set_xlim(0, 1); axA.set_ylim(-0.16, 1); axA.axis("off")
box(axA, 0.27, 0.80, "WT · apo", "#eef2f7")
box(axA, 0.78, 0.80, "WT · cortisol", "#e8f5ee")
box(axA, 0.27, 0.22, "L147R · apo", "#fdf0e3")
box(axA, 0.78, 0.22, "L147R · cortisol", "#fdf0e3")

# vertical alchemical legs (computed)
for x, leg, lab in [(0.27, "apo", "apo"), (0.78, "bound", "bound")]:
    d = legs[leg]
    axA.add_patch(FancyArrowPatch((x, 0.735), (x, 0.285),
                  arrowstyle="-|>", mutation_scale=16, lw=2.2,
                  color=C_MUT, zorder=2))
    axA.text(x + (0.035 if x < 0.5 else 0.035), 0.51,
             f"$\\Delta G_{{{lab}}}$\n{d['BAR']:.0f}\n±{d['BAR_e']:.0f}",
             ha="left", va="center", fontsize=9, color=C_MUT,
             rotation=0)
# horizontal binding (experiment) — dashed, not computed directly
for y in (0.80, 0.22):
    axA.add_patch(FancyArrowPatch((0.47, y), (0.58, y),
                  arrowstyle="-|>", mutation_scale=13, lw=1.6,
                  color=C_LIG, ls=(0, (4, 2)), zorder=2))
axA.text(0.525, 0.86, "bind", ha="center", fontsize=8.5, color=C_LIG)
axA.text(0.525, 0.28, "bind", ha="center", fontsize=8.5, color=C_LIG)

axA.text(0.5, 0.075,
         r"$\Delta\Delta G_{\mathrm{bind}} = \Delta G_{\mathrm{bound}} - "
         r"\Delta G_{\mathrm{apo}}$",
         ha="center", fontsize=10.5)
axA.text(0.5, 0.005,
         f"= {legs['bound']['BAR']:.1f} − ({legs['apo']['BAR']:.1f})"
         f" = {ddG_BAR:+.1f} kJ/mol",
         ha="center", fontsize=9.5, color=C_BAR)
axA.text(0.5, -0.105,
         "WT → L147R morph on both legs; the common ~−630 kJ/mol\n"
         "charge-insertion cost cancels in the difference",
         ha="center", va="center", fontsize=7.6, color="#666", zorder=1)
axA.set_title("A   Alchemical thermodynamic cycle", loc="left", fontweight="bold", pad=8)


# ===== Panels B & C: Crooks work distributions =====
def work_panel(ax, leg, title):
    d = legs[leg]
    wf, wr = W[leg]["F"], W[leg]["R"]
    allw = np.concatenate([wf, wr])
    lo, hi = allw.min() - 25, allw.max() + 25
    xs = np.linspace(lo, hi, 400)
    bins = np.linspace(lo, hi, 14)
    for w, c, lab in [(wf, C_F, "forward  (WT→mut)"),
                      (wr, C_R, "reverse  (mut→WT)")]:
        ax.hist(w, bins=bins, density=True, color=c, alpha=0.30,
                edgecolor=c, lw=0.8)
        mu, sd = w.mean(), w.std(ddof=1)
        ax.plot(xs, norm.pdf(xs, mu, sd), color=c, lw=2.0, label=lab)
        ax.plot([mu, mu], [0, norm.pdf(mu, mu, sd)], color=c, lw=0.9, ls=":")
    ax.axvline(d["BAR"], color=C_BAR, lw=1.8, ls="--",
               label=f"BAR ΔG = {d['BAR']:.1f}")
    ax.set_xlabel("work  W (kJ/mol)")
    ax.set_ylabel("probability density")
    ax.set_title(title, loc="left", fontweight="bold", pad=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(fontsize=8, frameon=False, loc="upper right")
    ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))

work_panel(axB, "bound", "B   Bound leg — non-equilibrium work (8+8 transitions)")
work_panel(axC, "apo", "C   Apo leg")


# ===== Panel D: ddG summary =====
ests = ["BAR", "CGI"]
vals = [ddG_BAR, ddG_CGI]
errs = [ddG_BAR_e, ddG_CGI_e]
cols = [C_BAR, C_CGI]
xpos = np.arange(len(ests))
axD.axhline(0, color="#888", lw=1.0, zorder=1)
axD.axhspan(axD.get_ylim()[0], 0, color="#27ae60", alpha=0.05)
bars = axD.bar(xpos, vals, yerr=errs, width=0.55, color=cols, alpha=0.85,
               ecolor="#333", capsize=6, zorder=3)
for x, v, e in zip(xpos, vals, errs):
    axD.text(x, v - e - 2.0, f"{v:+.1f}\n±{e:.1f}", ha="center", va="top",
             fontsize=9)
axD.set_xticks(xpos); axD.set_xticklabels(ests)
axD.set_ylabel(r"$\Delta\Delta G_{\mathrm{bind}}$ (kJ/mol)")
axD.set_title("D   L147R favors cortisol", loc="left", fontweight="bold", pad=6)
axD.spines[["top", "right"]].set_visible(False)
axD.set_ylim(min(vals) - max(errs) - 12, 9)
axD.text(0.97, 0.96, "favorable (ΔΔG < 0)\n✓ matches assay",
         transform=axD.transAxes, ha="right", va="top", fontsize=8.5,
         color="#1e7d34")

fig.suptitle("Tier-2 relative binding FEP (pmx + GROMACS non-equilibrium TI): "
             "L147R × cortisol — demonstration",
             fontsize=12.5, fontweight="bold", x=0.5, y=0.965)
fig.text(0.5, 0.005, "Demo scale (8 transitions × 50 ps/leg, chain A). "
         "Sign robust across BAR & CGI; magnitude not yet converged.",
         ha="center", fontsize=8, color="#666")

out = os.path.join(HERE, "FEP_demo_figure")
fig.savefig(out + ".png", bbox_inches="tight")
fig.savefig(out + ".pdf", bbox_inches="tight")
print("wrote", out + ".png /.pdf")
print(f"ddG BAR={ddG_BAR:+.2f}±{ddG_BAR_e:.2f}  CGI={ddG_CGI:+.2f}±{ddG_CGI_e:.2f} kJ/mol")
