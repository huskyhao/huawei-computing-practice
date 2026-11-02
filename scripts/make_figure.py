#!/usr/bin/env python3
"""Plot medians and the full observed range of all unfiltered batches."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "measurements/summary.json").read_text())
layouts = ["shared", "packed8", "stride64", "stride128", "stride256"]
labels = ["One shared counter", "8 B / packed", "64 B stride", "128 B stride", "256 B stride"]
colors = ["#9B6678", "#D58C34", "#68A3B9", "#168675", "#384E77"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "text.color": "#183044", "axes.labelcolor": "#526579",
                     "axes.edgecolor": "#CBD5E1", "xtick.color": "#526579", "ytick.color": "#526579"})
fig, axes = plt.subplots(1, 2, figsize=(13, 6.5), sharey=True)
fig.subplots_adjust(left=0.08, right=0.98, top=0.77, bottom=0.27, wspace=0.15)
for ax, mode, title in zip(axes, ["lse", "llsc"],
                           ["LSE  /  LDADD", "LL/SC  /  LDXR + STXR"]):
    for layout, label, color in zip(layouts, labels, colors):
        group = [next(r for r in data["results"] if r["atomic_mode"] == mode
                      and r["layout"] == layout and r["threads"] == t) for t in (1, 2, 4, 8)]
        med = [r["median_mops"] for r in group]
        low = [m-r["min_mops"] for m,r in zip(med,group)]
        high = [r["max_mops"]-m for m,r in zip(med,group)]
        ax.errorbar([1,2,4,8],med,yerr=[low,high],label=label,color=color,
                    marker="o",markersize=5,linewidth=2,capsize=3,alpha=0.9)
    ax.set_xscale("log", base=2); ax.set_xticks([1,2,4,8], ["1","2","4","8"])
    ax.set_yscale("log")
    ax.set_ylim(15, 1800)
    ax.grid(axis="both",color="#E4EAF0",which="major",alpha=0.9)
    ax.set_axisbelow(True)
    ax.set_title(title,loc="left",fontsize=14,weight="bold",pad=15)
    ax.set_xlabel("Pinned worker threads",labelpad=10)
axes[0].set_ylabel("Total atomic increments / second (millions, log scale)",labelpad=10)
fig.text(0.08,0.94,"False sharing: layout meets atomic instructions",fontsize=21,weight="bold")
fig.text(0.08,0.875,"TaiShan-v110  |  GCC 14.3.0  |  2,000,000 increments per worker  |  one shared L3 domain",
         fontsize=10,color="#63758A")
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles,labels,loc="lower center",bbox_to_anchor=(0.52,0.145),ncol=5,frameon=False,fontsize=9)
fig.text(0.08,0.055,"Points: median of 9 runs. Whiskers: full min-max range; no filtering.  |  360 measured batches\n"
         "Same 4 KiB-aligned arena for all layouts; thread creation/join and validation excluded.  |  2026-11-02",
         fontsize=9,color="#63758A",linespacing=1.7)
(ROOT / "assets").mkdir(exist_ok=True)
fig.savefig(ROOT / "assets/scaling.png",dpi=180,facecolor="white")
plt.close(fig)
print(ROOT / "assets/scaling.png")
