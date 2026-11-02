"""Render publication assets from measured JSON and saved prediction arrays.

Run on a machine with NumPy and Matplotlib; this is not a benchmark dependency.
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets"
OUT.mkdir(exist_ok=True)
data = json.loads((ROOT / "results/benchmark.json").read_text(encoding="utf-8"))
batches = [int(key) for key in data["batches"]]
series = [("cpu_numpy_t1", "CPU NumPy / 1 thread", "#64748b"),
          ("npu_execute", "NPU synchronous execute", "#0284c7"),
          ("npu_tensor_roundtrip", "NPU tensor round trip", "#0f766e")]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": "white", "axes.facecolor": "white"})
fig, axes = plt.subplots(1, 2, figsize=(13.8, 5.5), constrained_layout=True)
xpos = np.arange(len(batches))
for offset, (key, label, color) in enumerate(series):
    values = [data["batches"][str(batch)]["timing"][key]["median_us"] for batch in batches]
    bars = axes[0].bar(xpos + (offset - 1) * 0.25, values, width=0.24, color=color, label=label)
    for bar, value in zip(bars, values):
        axes[0].annotate(f"{value:.1f}", (bar.get_x() + bar.get_width() / 2, value),
                         xytext=(0, 4), textcoords="offset points", ha="center", fontsize=8)
axes[0].set(xticks=xpos, xticklabels=batches, xlabel="Static batch size",
            ylabel="Median latency per call (microseconds)", title="Latency (lower is better)")
axes[0].set_ylim(bottom=0, top=axes[0].get_ylim()[1] * 1.15)
axes[0].grid(axis="y", alpha=0.15)
for key, label, color in [series[0], series[2]]:
    values = [data["batches"][str(batch)]["timing"][key]["serial_samples_per_second_from_mean"]
              for batch in batches]
    axes[1].plot(xpos, values, marker="o", linewidth=2, label=label, color=color)
    for index, value in enumerate(values):
        if index > 0:
            offset = -14 if key.startswith("cpu") else 7
            axes[1].annotate(f"{value:,.0f}", (index, value), xytext=(0, offset),
                             textcoords="offset points", ha="center", fontsize=8, color=color)
axes[1].set(xticks=xpos, xticklabels=batches, xlabel="Static batch size",
            ylabel="Samples / second (batch / mean measured latency)",
            title="Serial tensor throughput (higher is better)")
axes[1].set_ylim(bottom=0)
axes[1].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
axes[1].grid(axis="y", alpha=0.15)
fig.suptitle("Orange Pi AIpro / Ascend310B1 / CANN 8.0.0\n"
             "Same 64-128-10 MLP weights; 50 warmups + 500 samples x 3 rounds", fontsize=13)
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(handles, labels, loc="outside lower center", ncol=3, frameon=False)
fig.savefig(OUT / "latency-throughput.png", dpi=170, bbox_inches="tight")
plt.close(fig)

with np.load(ROOT / "models/test_data.npz") as archive:
    inputs, labels = archive["x"], archive["y"]
with np.load(ROOT / "results/predictions_b32.npz") as archive:
    predictions = archive["predictions"]
fig, axes = plt.subplots(4, 5, figsize=(10, 8), constrained_layout=True)
for index, ax in enumerate(axes.flat):
    ax.imshow(inputs[index].reshape(8, 8), cmap="gray_r", vmin=0, vmax=1, interpolation="nearest")
    correct = labels[index] == predictions[index]
    ax.set_title(f"#{index}: true {labels[index]} / NPU {predictions[index]}",
                 fontsize=10, color="#0f766e" if correct else "#b91c1c")
    ax.axis("off")
fig.suptitle("First 20 held-out digits / NPU batch=32\n"
             "8 x 8 grayscale input; no sample selection by prediction", fontsize=13)
fig.savefig(OUT / "digits-predictions.png", dpi=170, bbox_inches="tight")
plt.close(fig)
print("Rendered:", *(str(path) for path in OUT.glob("*.png")), sep="\n")
