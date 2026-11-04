"""Create portable PNG figures from audited scalar measurements."""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--base", type=Path)
args = parser.parse_args()
BASE = args.base or (ROOT / "measurements" if (ROOT / "measurements").exists() else ROOT / "results")
OUT = ROOT / "assets"
OUT.mkdir(exist_ok=True)
s = json.loads((BASE / "summary.json").read_text(encoding="utf-8"))
policies = ("reuse_all", "recreate_dataset", "reallocate_io", "reload_model")
labels = ["Reuse all", "Rebuild datasets", "Reallocate I/O", "Reload model"]
colors = ["#2369a1", "#42a5a0", "#e7a141", "#cb5e64"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False})

fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout="constrained")
means = [s["policy_statistics"][p]["total_us"]["mean"] for p in policies]
for ax, count in zip(axes, (3, 4)):
    x = np.arange(count)
    ax.bar(x, means[:count], color=colors[:count], width=.63)
    ax.set_xticks(x, labels[:count], rotation=15, ha="right")
    ax.set_ylabel("Completed request time (microseconds)")
    ax.grid(axis="y", alpha=.2)
    ax.set_axisbelow(True)
    if count == 3:
        lo = [means[i] - min(s["policy_statistics"][policies[i]]["round_mean_us"]) for i in x]
        hi = [max(s["policy_statistics"][policies[i]]["round_mean_us"]) - means[i] for i in x]
        ax.errorbar(x, means[:count], yerr=[lo, hi], fmt="none", color="#333333", capsize=5)
        ax.set_ylim(0, max(means[:count]) * 1.3)
        ax.set_title("Model resident: mean and range of 5 round means")
    else:
        ax.set_yscale("log")
        ax.set_ylim(50, max(means) * 2)
        ax.set_title("All lifecycle policies (log scale)")
    for i, value in enumerate(means[:count]):
        ax.text(i, value * 1.06 + (4 if count == 3 else 0),
                f"{value:,.1f}", ha="center", va="bottom", fontweight="bold")
fig.suptitle("Ascend310B1 / CANN 8.0.0 / static batch 32\n"
             "6,000 measured requests per policy; input copy + synchronous execute + output read",
             fontsize=13)
fig.savefig(OUT / "resource-reuse-latency.png", dpi=180)
plt.close(fig)

with (BASE / "startup/processes.csv").open(newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
fig, ax = plt.subplots(figsize=(9, 4.8), layout="constrained")
x = np.arange(1, len(rows) + 1)
first = [float(r["first_request_us"]) for r in rows]
warm = [float(r["next_30_request_median_us"]) for r in rows]
ax.plot(x, first, "o-", color=colors[3], label="First completed request")
ax.plot(x, warm, "s-", color=colors[0], label="Median of the following 30 requests")
ax.set(xlabel="Independent Python process", ylabel="Microseconds per batch-32 request",
       xticks=x, ylim=(0, max(first) * 1.2),
       title="First request and subsequent requests in 12 fresh processes\n"
             "Device remains powered on; runtime and model setup excluded from request timing")
ax.grid(alpha=.2)
ax.legend(loc="upper right")
fig.savefig(OUT / "first-request.png", dpi=180)
plt.close(fig)
print("Wrote 2 figures")
