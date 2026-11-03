#!/usr/bin/env python3
"""Plot the measured batches; Matplotlib is needed only for this local step."""
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / "measurements/summary.json").read_text())
with (ROOT / "measurements/raw.csv").open(newline="") as f:
    rows = list(csv.DictReader(f))
names = ["scalar", "auto_o2", "auto_o3", "auto_tuned", "neon4"]
labels = ["Scalar / O3, no SIMD", "GCC O2 / generic", "GCC O3 / generic",
          "GCC O3 / tsv110", "NEON / 4 accumulators"]
colors = ["#94A3B8", "#94A3B8", "#339AAA", "#197D8C", "#D89A32"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.spines.left": False, "axes.edgecolor": "#CBD5E1",
                     "text.color": "#172A3A", "axes.labelcolor": "#475569",
                     "xtick.color": "#64748B", "ytick.color": "#334155"})
fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.8), sharey=True)
fig.subplots_adjust(left=0.205, right=0.98, bottom=0.23, top=0.77, wspace=0.12)
for ax, size, title, subtitle in zip(axes, [262144, 268435456],
        ["256 KiB working set", "256 MiB working set"],
        ["Fits within the 512 KiB private L2", "Exceeds the 48 MiB local L3 domain"]):
    ax.set_axisbelow(True)
    ax.grid(axis="x", color="#E8EDF3")
    ax.set_xlim(0, 31)
    ax.set_xticks([0, 5, 10, 15, 20, 25, 30])
    for i, (name, color) in enumerate(zip(names, colors)):
        item = next(x for x in data["results"] if x["bytes"] == size and x["variant"] == name)
        values = [float(r["logical_gib_s"]) for r in rows
                  if int(r["bytes"]) == size and r["variant"] == name]
        ax.barh(i, item["median_gib_s"], height=0.52, color=color, alpha=0.88)
        jitter = [(j - 5) * 0.024 for j in range(len(values))]
        ax.scatter(values, [i + j for j in jitter], s=11, color="#102A43", alpha=0.55, zorder=3)
        ax.text(item["max_gib_s"] + 0.45, i,
                f"{item['median_gib_s']:.2f}  ({item['speedup_vs_scalar']:.2f}x)",
                va="center", fontsize=9, color="#243B53")
    ax.set_title(title, loc="left", fontsize=14, weight="bold", pad=31)
    ax.text(0, 1.045, subtitle, transform=ax.transAxes, color="#64748B", fontsize=9)
    ax.set_xlabel("Logical input throughput (GiB/s)", labelpad=10)
    ax.tick_params(axis="y", length=0)
axes[0].set_yticks(range(len(labels)), labels)
axes[0].invert_yaxis()
fig.text(0.065, 0.945, "What does SIMD change on Kunpeng?", fontsize=22, weight="bold")
fig.text(0.065, 0.885, "TaiShan-v110  /  uint32 -> uint64 sum  /  one pinned CPU  /  GCC 14.3.0",
         fontsize=11, color="#52677B")
fig.text(0.065, 0.09,
         "Bars: median of 11 batch means. Dots: all 11 batches. Labels: GiB/s and speedup vs scalar.\n"
         "Same x-axis scale. Input generation, allocation and validation excluded from timing.  |  2026-11-02",
         fontsize=9, color="#64748B", linespacing=1.7)
output = ROOT / "assets"
output.mkdir(exist_ok=True)
fig.savefig(output / "throughput.png", dpi=180, facecolor="white")
plt.close(fig)
print(output / "throughput.png")
