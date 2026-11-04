#!/usr/bin/env python3
"""Render measured medians and full ranges; requires Matplotlib only locally."""
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/"measurements/summary.json").read_text())
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":10,"axes.spines.top":False,
                     "axes.spines.right":False,"axes.edgecolor":"#CAD4DE","text.color":"#183044",
                     "axes.labelcolor":"#50657A","xtick.color":"#50657A","ytick.color":"#50657A"})
fig,axes=plt.subplots(1,2,figsize=(13,6))
fig.subplots_adjust(left=0.08,right=0.98,top=0.74,bottom=0.24,wspace=0.25)
for ax,pattern,title,ylabel in zip(axes,["chase","scan"],
        ["Dependent random loads  /  lower is better","Sequential scan  /  higher is better"],
        ["Nanoseconds per dependent hop","Logical input throughput (GiB/s)"]):
    for cpu,local,color in [(4,0,"#197D91"),(52,2,"#CB8530")]:
        rows=sorted([r for r in data["results"] if r["cpu"]==cpu],key=lambda x:x["memory_node"])
        med=[r[pattern]["median"] for r in rows]
        low=[m-r[pattern]["min"] for m,r in zip(med,rows)]
        high=[r[pattern]["max"]-m for m,r in zip(med,rows)]
        ax.errorbar(range(4),med,yerr=[low,high],label=f"CPU {cpu} / node {local}",
                    color=color,marker="o",markersize=6,linewidth=2,capsize=4)
        ax.scatter([local],[med[local]],s=220,facecolors="none",edgecolors=color,linewidths=1.8,zorder=4)
    ax.set_ylim(bottom=0);ax.set_xticks(range(4),["Node 0","Node 1","Node 2","Node 3"])
    ax.set_xlim(-0.25,3.25);ax.set_xlabel("Bound memory node",labelpad=10)
    ax.set_ylabel(ylabel,labelpad=10);ax.grid(axis="y",color="#E6ECF2");ax.set_axisbelow(True)
    ax.set_title(title,loc="left",fontsize=12,weight="bold",pad=14)
fig.text(0.08,0.94,"NUMA placement: the same core, different memory",fontsize=20,weight="bold")
fig.text(0.08,0.875,"Kunpeng / TaiShan-v110  |  one pinned CPU  |  256 MiB mapping  |  GCC 14.3.0  |  2026-11-04",
         fontsize=10,color="#61758A")
handles,labels=axes[0].get_legend_handles_labels()
fig.legend(handles,labels,loc="upper center",bbox_to_anchor=(0.5,0.835),ncol=2,frameon=False)
fig.text(0.08,0.09,"Points: median of 9 batch means. Whiskers: full min-max range; no filtering. Rings: local memory.\n"
         "All base pages queried before and after timing. Mapping uses MADV_NOHUGEPAGE; allocation and validation excluded.",
         fontsize=9,color="#61758A",linespacing=1.7)
(ROOT/"assets").mkdir(exist_ok=True)
fig.savefig(ROOT/"assets/numa-latency-throughput.png",dpi=180,facecolor="white")
plt.close(fig)
print(ROOT/"assets/numa-latency-throughput.png")
