"""Cross-check recovered evidence before publishing numbers in the article."""
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
training = json.loads((ROOT / "results/training.json").read_text(encoding="utf-8"))
benchmark = json.loads((ROOT / "results/benchmark.json").read_text(encoding="utf-8"))
with np.load(ROOT / "models/test_data.npz") as archive:
    labels = archive["y"]
    reference = archive["reference_logits"]
    indices = archive["test_indices"]
assert len(labels) == len(set(indices.tolist())) == 360
assert training["train_samples"] + training["test_samples"] == 1797
hashes = {}
for line in (ROOT / "results/model-sha256.txt").read_text().splitlines():
    expected, filename = line.split(maxsplit=1)
    actual = hashlib.sha256((ROOT / filename).read_bytes()).hexdigest()
    assert actual == expected, filename
    hashes[filename] = actual
for name, expected in training["onnx_sha256"].items():
    assert hashes[f"models/{name}"] == expected
samples = defaultdict(list)
with (ROOT / "results/latency_samples.csv").open(newline="", encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        samples[(row["batch"], row["scenario"])].append(float(row["latency_us"]))
assert sum(map(len, samples.values())) == 18000
assert len(samples) == 12
for batch, result in benchmark["batches"].items():
    with np.load(ROOT / f"results/predictions_b{batch}.npz") as archive:
        output, pred = archive["logits"], archive["predictions"]
        np.testing.assert_array_equal(archive["labels"], labels)
    assert output.shape == (360, 10) and np.isfinite(output).all()
    np.testing.assert_array_equal(pred, output.argmax(axis=1))
    np.testing.assert_array_equal(pred, reference.argmax(axis=1))
    assert int(np.sum(pred == labels)) == result["validation"]["correct"] == 352
    for scenario, stats in result["timing"].items():
        values = samples[(batch, scenario)]
        assert len(values) == stats["samples"] == 1500
        for key, measured in [("median_us", np.median(values)), ("mean_us", np.mean(values)),
                               ("p95_us", np.percentile(values, 95))]:
            assert np.isclose(measured, stats[key], rtol=1e-12, atol=1e-9), (batch, scenario, key)
        throughput = int(batch) * 1e6 / np.mean(values)
        assert np.isclose(throughput, stats["serial_samples_per_second_from_mean"])
    for key, threads in [("cpu_numpy_t1", 1), ("cpu_numpy_t4", 4)]:
        assert all(pool["num_threads"] == threads
                   for pool in result["cpu_threadpool_configurations"][key])
report = {"models_sha256_verified": len(hashes), "test_samples": 360,
          "correct_per_npu_batch": 352, "prediction_agreement": 1.0,
          "latency_samples_verified": 18000, "timing_groups_verified": 12,
          "status": "passed"}
(ROOT / "results/artifact-verification.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
