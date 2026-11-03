"""Measure completed request windows, with distinct I/O slots and model IDs.

Fixed model batch=32. A scheduling window is a group of model invocations.
Resident execution and tensor-roundtrip windows have different timing boundaries.
"""
import argparse
import csv
import hashlib
import json
import platform
import random
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import acl
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BATCH = 32
POLICIES = ("sync_serial", "async_wait_each", "async_wait_group", "async_two_streams")
WINDOWS = (1, 4, 16, 64)


def check(ret, operation):
    if ret != 0:
        raise RuntimeError(f"{operation}: ACL error {ret}; {acl.get_recent_err_msg()}")


class TensorSlot:
    """One request owns its input/output datasets and memory until completion."""

    def __init__(self, input_size, output_size):
        self.input_size, self.output_size = input_size, output_size
        self.buffers, self.datasets = [], []
        try:
            self.inputs, self.input_ptr = self.allocate(input_size)
            self.outputs, self.output_ptr = self.allocate(output_size)
        except BaseException:
            self.close()
            raise

    def allocate(self, size):
        dataset = acl.mdl.create_dataset()
        self.datasets.append(dataset)
        ptr, ret = acl.rt.malloc(size, 2)
        check(ret, "rt.malloc")
        entry = [ptr, None]
        self.buffers.append(entry)
        buffer = acl.create_data_buffer(ptr, size)
        entry[1] = buffer
        _, ret = acl.mdl.add_dataset_buffer(dataset, buffer)
        check(ret, "mdl.add_dataset_buffer")
        return dataset, ptr

    def write(self, x):
        if x.shape != (BATCH, 64) or x.dtype != np.float32:
            raise ValueError("Expected (32,64) FP32 input")
        payload = x.tobytes(order="C")
        ptr = acl.util.bytes_to_ptr(payload)
        # This experiment deliberately targets the observed ACL_DEVICE board mode.
        check(acl.rt.memcpy(self.input_ptr, self.input_size, ptr, len(payload), 3), "memcpy input")

    def read(self):
        data = acl.util.ptr_to_bytes(self.output_ptr, self.output_size)
        return np.frombuffer(data, dtype=np.float32).reshape(BATCH, 10).copy()

    def close(self):
        failures = []
        for ptr, buffer in reversed(self.buffers):
            if buffer is not None:
                failures.append(("destroy_data_buffer", acl.destroy_data_buffer(buffer)))
            failures.append(("rt.free", acl.rt.free(ptr)))
        self.buffers.clear()
        for dataset in reversed(self.datasets):
            failures.append(("destroy_dataset", acl.mdl.destroy_dataset(dataset)))
        self.datasets.clear()
        bad = [(name, ret) for name, ret in failures if ret != 0]
        if bad:
            raise RuntimeError(f"Slot cleanup failed: {bad}")


class Experiment:
    def __init__(self, model_path, inputs):
        self.models, self.streams, self.slots = [], [], []
        self.inputs = inputs
        self.model_load_ms = []
        try:
            # This CANN build rejects mixed sync/async execution on one model ID.
            # ID 0 is sync-only; IDs 1 and 2 belong exclusively to async streams.
            for _ in range(3):
                start = time.perf_counter_ns()
                model_id, ret = acl.mdl.load_from_file(str(model_path))
                check(ret, "mdl.load_from_file")
                self.models.append(model_id)
                self.model_load_ms.append((time.perf_counter_ns() - start) / 1e6)
            for _ in range(2):
                stream, ret = acl.rt.create_stream()
                check(ret, "rt.create_stream")
                self.streams.append(stream)
            if len(set(self.models)) != 3:
                raise AssertionError("Concurrent streams require independent model IDs")
            desc = acl.mdl.create_desc()
            try:
                check(acl.mdl.get_desc(desc, self.models[0]), "mdl.get_desc")
                assert acl.mdl.get_num_inputs(desc) == acl.mdl.get_num_outputs(desc) == 1
                assert acl.mdl.get_input_data_type(desc, 0) == acl.mdl.get_output_data_type(desc, 0) == 0
                self.input_size = acl.mdl.get_input_size_by_index(desc, 0)
                self.output_size = acl.mdl.get_output_size_by_index(desc, 0)
                assert self.input_size == BATCH * 64 * 4
                assert self.output_size == BATCH * 10 * 4
            finally:
                check(acl.mdl.destroy_desc(desc), "mdl.destroy_desc")
            for _ in range(max(WINDOWS)):
                self.slots.append(TensorSlot(self.input_size, self.output_size))
            self.write_inputs(max(WINDOWS))
        except BaseException:
            self.close()
            raise

    def write_inputs(self, window):
        for i in range(window):
            self.slots[i].write(self.inputs[i])

    def dispatch_and_wait(self, policy, window):
        start = time.perf_counter_ns()
        if policy == "sync_serial":
            for i in range(window):
                slot = self.slots[i]
                check(acl.mdl.execute(self.models[0], slot.inputs, slot.outputs), "mdl.execute")
        elif policy == "async_wait_each":
            for i in range(window):
                slot = self.slots[i]
                check(acl.mdl.execute_async(self.models[1], slot.inputs, slot.outputs, self.streams[0]), "execute_async")
                check(acl.rt.synchronize_stream(self.streams[0]), "synchronize_stream(each)")
        elif policy in ("async_wait_group", "async_two_streams"):
            count = 2 if policy == "async_two_streams" else 1
            for i in range(window):
                lane = i % count
                slot = self.slots[i]
                check(acl.mdl.execute_async(self.models[1 + lane], slot.inputs, slot.outputs, self.streams[lane]), "execute_async")
        else:
            raise ValueError(policy)
        issued = time.perf_counter_ns()
        if policy in ("async_wait_group", "async_two_streams"):
            count = min(window, 2) if policy == "async_two_streams" else 1
            for lane in range(count):
                check(acl.rt.synchronize_stream(self.streams[lane]), "synchronize_stream(group)")
        completed = time.perf_counter_ns()
        return (issued - start) / 1000, (completed - issued) / 1000

    def run_window(self, policy, window, boundary):
        start = time.perf_counter_ns()
        if boundary == "tensor_roundtrip":
            self.write_inputs(window)
        issue_us, drain_us = self.dispatch_and_wait(policy, window)
        if boundary == "tensor_roundtrip":
            outputs = [self.slots[i].read() for i in range(window)]
        completed = time.perf_counter_ns()
        return (completed - start) / 1000, issue_us, drain_us

    def read_outputs(self, window):
        return np.concatenate([self.slots[i].read() for i in range(window)])

    def close(self):
        # All queued work is drained before datasets or models can be released.
        for stream in self.streams:
            check(acl.rt.synchronize_stream(stream), "cleanup synchronize_stream")
        for slot in reversed(self.slots):
            slot.close()
        self.slots.clear()
        for stream in reversed(self.streams):
            check(acl.rt.destroy_stream(stream), "destroy_stream")
        self.streams.clear()
        for model_id in reversed(self.models):
            check(acl.mdl.unload(model_id), "mdl.unload")
        self.models.clear()


def validate(experiment, x, y, reference):
    validation = {}
    original_inputs = experiment.inputs
    full_inputs = []
    for offset in range(0, len(x), BATCH):
        tensor = np.zeros((BATCH, 64), dtype=np.float32)
        valid = min(BATCH, len(x) - offset)
        tensor[:valid] = x[offset:offset + valid]
        full_inputs.append(tensor)
    sync_output = None
    for policy in POLICIES:
        experiment.inputs = full_inputs
        experiment.write_inputs(len(full_inputs))
        experiment.dispatch_and_wait(policy, len(full_inputs))
        output = experiment.read_outputs(len(full_inputs))[:len(x)]
        assert output.shape == (360, 10) and np.isfinite(output).all()
        if sync_output is None:
            sync_output = output.copy()
        result = {
            "test_samples": len(y), "correct": int(np.sum(output.argmax(axis=1) == y)),
            "accuracy": float(np.mean(output.argmax(axis=1) == y)),
            "prediction_agreement_with_cpu": float(np.mean(output.argmax(axis=1) == reference.argmax(axis=1))),
            "max_abs_error_vs_sync": float(np.max(np.abs(output - sync_output))),
            "bitwise_equal_to_sync": bool(np.array_equal(output, sync_output)),
        }
        assert result["correct"] == 352 and result["prediction_agreement_with_cpu"] == 1.0
        np.testing.assert_allclose(output, sync_output, rtol=0, atol=1e-6)
        validation[policy] = result
        np.savez_compressed(ROOT / f"results/validation_{policy}.npz", logits=output, labels=y)
    experiment.inputs = original_inputs
    experiment.write_inputs(max(WINDOWS))
    return validation


def summarize(values, window):
    totals = [value[0] for value in values]
    mean = float(np.mean(totals))
    return {"samples": len(totals), "median_window_us": float(np.median(totals)),
            "p95_window_us": float(np.percentile(totals, 95)), "mean_window_us": mean,
            "median_issue_phase_us": float(np.median([value[1] for value in values])),
            "median_final_wait_us": float(np.median([value[2] for value in values])),
            "mean_amortized_us_per_request": mean / window,
            "requests_per_second_from_mean": window * 1e6 / mean,
            "samples_per_second_from_mean": BATCH * window * 1e6 / mean}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--repeats", type=int, default=200)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--out-stem", default="formal")
    args = parser.parse_args()
    assert min(args.warmup, args.repeats, args.rounds) > 0
    (ROOT / "results").mkdir(exist_ok=True)
    with np.load(ROOT / "models/test_data.npz") as data:
        x, y, reference = data["x"], data["y"], data["reference_logits"]
    inputs = [np.ascontiguousarray(x[(i * BATCH + np.arange(BATCH)) % len(x)]) for i in range(max(WINDOWS))]
    model_path = ROOT / "models/digits_b32.om"
    metadata = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "configuration": vars(args),
                "python": platform.python_version(), "numpy": np.__version__,
                "soc_name": acl.get_soc_name(), "model_batch": BATCH, "windows": WINDOWS,
                "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
                "test_data_sha256": hashlib.sha256((ROOT / "models/test_data.npz").read_bytes()).hexdigest()}
    context = experiment = None
    collected = defaultdict(list)
    rows = []
    check(acl.init(), "init")
    try:
        check(acl.rt.set_device(0), "set_device")
        context, ret = acl.rt.create_context(0)
        check(ret, "create_context")
        run_mode, ret = acl.rt.get_run_mode()
        check(ret, "get_run_mode")
        metadata["run_mode"] = run_mode
        if run_mode != 0:
            raise RuntimeError("This board experiment requires ACL_DEVICE mode")
        experiment = Experiment(model_path, inputs)
        metadata["model_ids"] = experiment.models.copy()
        metadata["model_roles"] = dict(zip(("sync_only", "async_stream_0", "async_stream_1"), experiment.models))
        metadata["model_load_ms"] = experiment.model_load_ms
        metadata["slot_pool_bytes"] = len(experiment.slots) * (experiment.input_size + experiment.output_size)
        metadata["validation"] = validate(experiment, x, y, reference)
        print("Validation passed for all four policies on 360 independent test samples.", flush=True)
        conditions = [(boundary, window, policy) for boundary in ("resident", "tensor_roundtrip")
                      for window in WINDOWS for policy in POLICIES]
        for round_index in range(args.rounds):
            order = conditions.copy()
            random.Random(20261103 + round_index).shuffle(order)
            for boundary, window, policy in order:
                for _ in range(args.warmup):
                    experiment.run_window(policy, window, boundary)
                key = (boundary, window, policy)
                for iteration in range(args.repeats):
                    value = experiment.run_window(policy, window, boundary)
                    collected[key].append(value)
                    rows.append({"boundary": boundary, "window": window, "policy": policy,
                                 "round": round_index + 1, "iteration": iteration + 1,
                                 "window_us": value[0], "issue_phase_us": value[1], "final_wait_us": value[2]})
                # Changing inputs across slots makes stale/shared output buffers detectable.
                output = experiment.read_outputs(window)
                expected_cpu = np.concatenate([reference[(i * BATCH + np.arange(BATCH)) % len(x)] for i in range(window)])
                assert np.isfinite(output).all()
                assert np.array_equal(output.argmax(axis=1), expected_cpu.argmax(axis=1))
            print(f"Round {round_index + 1}/{args.rounds} complete: {len(rows)} windows measured.", flush=True)
        metadata["timings"] = [dict(boundary=boundary, window=window, policy=policy,
                                    **summarize(values, window))
                                for (boundary, window, policy), values in sorted(collected.items())]
    finally:
        if experiment is not None:
            experiment.close()
        if context is not None:
            check(acl.rt.destroy_context(context), "destroy_context")
        check(acl.rt.reset_device(0), "reset_device")
        check(acl.finalize(), "finalize")
    metadata["cleanup"] = "all ACL cleanup calls succeeded"
    (ROOT / f"results/{args.out_stem}.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    with (ROOT / f"results/{args.out_stem}_windows.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"windows": len(rows), "conditions": len(collected), "cleanup": metadata["cleanup"]}), flush=True)


if __name__ == "__main__":
    main()
