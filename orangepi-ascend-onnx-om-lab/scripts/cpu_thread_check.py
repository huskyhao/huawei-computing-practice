"""Fresh-process follow-up for the observed batch-128 BLAS threading anomaly."""
import json
import resource
import time
from pathlib import Path

import numpy as np
from threadpoolctl import threadpool_info, threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
with np.load(ROOT / "models/weights.npz") as archive:
    weights = {key: archive[key] for key in archive.files}
with np.load(ROOT / "models/test_data.npz") as archive:
    x = np.ascontiguousarray(archive["x"][:128])


def infer():
    return np.maximum(x @ weights["w1"] + weights["b1"], 0) @ weights["w2"] + weights["b2"]


results = []
for threads in (1, 4, 1, 4):
    with threadpool_limits(limits=threads):
        for _ in range(20):
            infer()
        before = resource.getrusage(resource.RUSAGE_SELF)
        values = []
        for _ in range(100):
            start = time.perf_counter_ns()
            infer()
            values.append((time.perf_counter_ns() - start) / 1000)
        after = resource.getrusage(resource.RUSAGE_SELF)
        result = {"threads": threads, "batch": 128, "warmup": 20, "repeats": 100,
                  "median_us": float(np.median(values)), "p95_us": float(np.percentile(values, 95)),
                  "mean_us": float(np.mean(values)), "samples_us": values,
                  "cpu_seconds": after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime,
                  "threadpools": threadpool_info()}
        results.append(result)
        print(json.dumps({key: value for key, value in result.items() if key != "samples_us"}), flush=True)
(ROOT / "results/cpu-thread-check.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
