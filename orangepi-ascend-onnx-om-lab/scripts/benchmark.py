"""Validate all held-out samples; time resident execution and tensor round trips.

No dataset loading, training, model loading, or image preprocessing in latency samples.
"""
import argparse
import csv
import json
import platform
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import acl
import numpy as np
from threadpoolctl import threadpool_info, threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
ACL_DEVICE, ACL_HOST = 0, 1
HOST_TO_DEVICE, DEVICE_TO_HOST, DEVICE_TO_DEVICE = 1, 2, 3


def check(ret, operation):
    if ret != 0:
        raise RuntimeError(f"{operation}: ACL error {ret}")


def cpu_logits(x, weights):
    return np.maximum(x @ weights["w1"] + weights["b1"], 0) @ weights["w2"] + weights["b2"]


class AclModel:
    """One fixed-shape, one-input, one-output FP32 model, owning its buffers."""

    def __init__(self, path, batch, run_mode):
        self.model_id = self.desc = self.inputs = self.outputs = self.host_out = None
        self.buffers = []
        self.run_mode, self.batch = run_mode, batch
        try:
            start = time.perf_counter()
            self.model_id, ret = acl.mdl.load_from_file(str(path))
            check(ret, "mdl.load_from_file")
            self.load_ms = (time.perf_counter() - start) * 1000
            self.desc = acl.mdl.create_desc()
            check(acl.mdl.get_desc(self.desc, self.model_id), "mdl.get_desc")
            if acl.mdl.get_num_inputs(self.desc) != 1 or acl.mdl.get_num_outputs(self.desc) != 1:
                raise ValueError("Expected exactly one input and output")
            self.input_dims, ret = acl.mdl.get_input_dims(self.desc, 0)
            check(ret, "mdl.get_input_dims")
            self.output_dims, ret = acl.mdl.get_output_dims(self.desc, 0)
            check(ret, "mdl.get_output_dims")
            self.input_size = acl.mdl.get_input_size_by_index(self.desc, 0)
            self.output_size = acl.mdl.get_output_size_by_index(self.desc, 0)
            if self.input_size != batch * 64 * 4 or self.output_size != batch * 10 * 4:
                raise ValueError(f"Unexpected OM buffer sizes: {self.input_size}, {self.output_size}")
            # aclDataType: ACL_FLOAT = 0.
            if acl.mdl.get_input_data_type(self.desc, 0) != 0 or acl.mdl.get_output_data_type(self.desc, 0) != 0:
                raise ValueError("Expected FP32 model I/O")
            self.inputs = acl.mdl.create_dataset()
            self.outputs = acl.mdl.create_dataset()
            self.input_ptr = self.allocate(self.inputs, self.input_size)
            self.output_ptr = self.allocate(self.outputs, self.output_size)
            if run_mode == ACL_HOST:
                self.host_out, ret = acl.rt.malloc_host(self.output_size)
                check(ret, "rt.malloc_host")
        except BaseException:
            self.close()
            raise

    def allocate(self, dataset, size):
        ptr, ret = acl.rt.malloc(size, 2)  # ACL_MEM_MALLOC_NORMAL_ONLY
        check(ret, "rt.malloc")
        entry = [ptr, None]
        self.buffers.append(entry)
        data = acl.create_data_buffer(ptr, size)
        entry[1] = data
        _, ret = acl.mdl.add_dataset_buffer(dataset, data)
        check(ret, "mdl.add_dataset_buffer")
        return ptr

    def copy_input(self, x):
        if x.shape != (self.batch, 64) or x.dtype != np.float32:
            raise ValueError(f"Expected {(self.batch, 64)} FP32 input")
        # Keep bytes alive until the synchronous copy finishes.
        input_bytes = x.tobytes(order="C")
        ptr = acl.util.bytes_to_ptr(input_bytes)
        kind = DEVICE_TO_DEVICE if self.run_mode == ACL_DEVICE else HOST_TO_DEVICE
        check(acl.rt.memcpy(self.input_ptr, self.input_size, ptr, len(input_bytes), kind), "rt.memcpy(input)")

    def execute(self):
        # acl.mdl.execute is synchronous: timing ends after completion.
        check(acl.mdl.execute(self.model_id, self.inputs, self.outputs), "mdl.execute")

    def read_output(self):
        if self.run_mode == ACL_HOST:
            check(acl.rt.memcpy(self.host_out, self.output_size, self.output_ptr,
                                self.output_size, DEVICE_TO_HOST), "rt.memcpy(output)")
            ptr = self.host_out
        else:
            # On the integrated board in ACL_DEVICE mode this buffer is CPU accessible.
            ptr = self.output_ptr
        output_bytes = acl.util.ptr_to_bytes(ptr, self.output_size)
        return np.frombuffer(output_bytes, dtype=np.float32).reshape(self.batch, 10).copy()

    def infer(self, x):
        self.copy_input(x)
        self.execute()
        return self.read_output()

    def close(self):
        errors = []
        for ptr, buffer in reversed(self.buffers):
            if buffer is not None:
                errors.append(("destroy_data_buffer", acl.destroy_data_buffer(buffer)))
            errors.append(("free", acl.rt.free(ptr)))
        self.buffers.clear()
        for name in ("inputs", "outputs"):
            dataset = getattr(self, name)
            if dataset is not None:
                errors.append(("destroy_dataset", acl.mdl.destroy_dataset(dataset)))
                setattr(self, name, None)
        if self.host_out is not None:
            errors.append(("free_host", acl.rt.free_host(self.host_out)))
            self.host_out = None
        if self.desc is not None:
            errors.append(("destroy_desc", acl.mdl.destroy_desc(self.desc)))
            self.desc = None
        if self.model_id is not None:
            errors.append(("unload", acl.mdl.unload(self.model_id)))
            self.model_id = None
        failed = [(name, ret) for name, ret in errors if ret != 0]
        if failed:
            raise RuntimeError(f"ACL cleanup errors: {failed}")


def measure(function, warmup, repeats):
    for _ in range(warmup):
        function()
    samples = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        function()
        samples.append((time.perf_counter_ns() - start) / 1000.0)
    return samples


def validate(model, x, y, reference, sklearn_predictions):
    outputs = []
    for offset in range(0, len(x), model.batch):
        valid = min(model.batch, len(x) - offset)
        padded = np.zeros((model.batch, 64), dtype=np.float32)
        padded[:valid] = x[offset:offset + valid]
        outputs.append(model.infer(padded)[:valid])
    output = np.concatenate(outputs)
    if output.shape != reference.shape or not np.isfinite(output).all():
        raise AssertionError("Invalid NPU output shape or non-finite result")
    pred = output.argmax(axis=1)
    reference_pred = reference.argmax(axis=1)
    diff = output.astype(np.float64) - reference.astype(np.float64)
    result = {
        "test_samples": len(y), "correct": int(np.sum(pred == y)),
        "accuracy": float(np.mean(pred == y)),
        "numpy_prediction_agreement": float(np.mean(pred == reference_pred)),
        "sklearn_prediction_agreement": float(np.mean(pred == sklearn_predictions)),
        "max_abs_logit_error": float(np.max(np.abs(diff))),
        "mean_abs_logit_error": float(np.mean(np.abs(diff))),
        "relative_l2_logit_error": float(np.linalg.norm(diff) / np.linalg.norm(reference)),
        "prediction_disagreement_indices": np.flatnonzero(pred != reference_pred).tolist(),
    }
    # These are explicit experiment acceptance criteria, not a dataset accuracy guarantee.
    if result["accuracy"] < 0.95 or result["numpy_prediction_agreement"] < 0.99:
        raise AssertionError(f"Validation acceptance criteria failed: {result}")
    np.savez_compressed(ROOT / f"results/predictions_b{model.batch}.npz", logits=output,
                        predictions=pred, labels=y, reference_logits=reference)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmup", type=int, default=50)
    parser.add_argument("--repeats", type=int, default=500)
    parser.add_argument("--rounds", type=int, default=3)
    args = parser.parse_args()
    if min(args.warmup, args.repeats, args.rounds) < 1:
        parser.error("All timing counts must be positive")
    (ROOT / "results").mkdir(exist_ok=True)
    with np.load(ROOT / "models/weights.npz") as archive:
        weights = {key: archive[key] for key in archive.files}
    with np.load(ROOT / "models/test_data.npz") as archive:
        x, y = archive["x"], archive["y"]
        reference, sklearn_predictions = archive["reference_logits"], archive["sklearn_predictions"]
    metadata = {"created_at_utc": datetime.now(timezone.utc).isoformat(),
                "python": platform.python_version(), "numpy": np.__version__,
                "soc_name": acl.get_soc_name(), "configuration": vars(args),
                "threadpools": threadpool_info(), "batches": {}}
    rows = []
    context = None
    check(acl.init(), "init")
    try:
        check(acl.rt.set_device(0), "rt.set_device")
        context, ret = acl.rt.create_context(0)
        check(ret, "rt.create_context")
        run_mode, ret = acl.rt.get_run_mode()
        check(ret, "rt.get_run_mode")
        metadata["run_mode"] = run_mode
        if run_mode not in (ACL_DEVICE, ACL_HOST):
            raise ValueError(f"Unknown run mode: {run_mode}")
        for batch in (1, 32, 128):
            model = AclModel(ROOT / f"models/digits_b{batch}.om", batch, run_mode)
            try:
                result = {"load_ms": model.load_ms, "input_dims": model.input_dims,
                          "output_dims": model.output_dims, "input_bytes": model.input_size,
                          "output_bytes": model.output_size,
                          "validation": validate(model, x, y, reference, sklearn_predictions),
                          "timing": {}, "cpu_threadpool_configurations": {}}
                sample = np.ascontiguousarray(x[:batch])
                model.copy_input(sample)
                collected = {name: [] for name in ("cpu_numpy_t1", "cpu_numpy_t4", "npu_execute", "npu_tensor_roundtrip")}
                for round_index in range(args.rounds):
                    order = list(collected)
                    random.Random(42 + round_index).shuffle(order)
                    for scenario in order:
                        if scenario.startswith("cpu"):
                            threads = 1 if scenario.endswith("t1") else 4
                            with threadpool_limits(limits=threads):
                                result["cpu_threadpool_configurations"][scenario] = threadpool_info()
                                samples = measure(lambda: cpu_logits(sample, weights), args.warmup, args.repeats)
                        else:
                            function = model.execute if scenario == "npu_execute" else lambda: model.infer(sample)
                            samples = measure(function, args.warmup, args.repeats)
                        collected[scenario].extend(samples)
                        rows.extend({"batch": batch, "scenario": scenario, "round": round_index + 1,
                                     "iteration": index + 1, "latency_us": value}
                                    for index, value in enumerate(samples))
                for scenario, samples in collected.items():
                    median = float(np.median(samples))
                    mean = float(np.mean(samples))
                    result["timing"][scenario] = {
                        "samples": len(samples), "median_us": median,
                        "p95_us": float(np.percentile(samples, 95)), "mean_us": mean,
                        "serial_samples_per_second_from_mean": batch * 1e6 / mean,
                    }
                metadata["batches"][str(batch)] = result
                print(json.dumps({"batch": batch, **result}, indent=2), flush=True)
            finally:
                model.close()
    finally:
        if context is not None:
            check(acl.rt.destroy_context(context), "rt.destroy_context")
        check(acl.rt.reset_device(0), "rt.reset_device")
        check(acl.finalize(), "finalize")
    with (ROOT / "results/latency_samples.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["batch", "scenario", "round", "iteration", "latency_us"])
        writer.writeheader()
        writer.writerows(rows)
    (ROOT / "results/benchmark.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved {len(rows)} timing samples; ACL resources released", flush=True)


if __name__ == "__main__":
    main()
