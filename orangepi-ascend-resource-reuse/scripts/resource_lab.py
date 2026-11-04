"""Synchronous pyACL lifecycle benchmark. Timers include completed work and cleanup.

One request is one static batch of 32 digits. Input bytes are prepared outside timing;
each output is copied into a NumPy array before buffers can be released.
"""
import argparse
import csv
import hashlib
import json
import platform
import random
import subprocess
import sys
import time
from pathlib import Path

import acl
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
POLICIES = ("reuse_all", "recreate_dataset", "reallocate_io", "reload_model")
STAGES = ("model_prepare_us", "memory_prepare_us", "dataset_prepare_us",
          "input_copy_us", "execute_us", "output_read_us", "dataset_release_us",
          "memory_release_us", "model_release_us")


def check(ret, op):
    if ret != 0:
        raise RuntimeError(f"{op}: ACL error {ret}")


class Model:
    def __init__(self):
        self.mid = self.desc = None
        try:
            self.mid, ret = acl.mdl.load_from_file(str(ROOT / "models/digits_b32.om"))
            check(ret, "load_from_file")
            self.desc = acl.mdl.create_desc()
            if not self.desc:
                raise RuntimeError("create_desc returned NULL")
            check(acl.mdl.get_desc(self.desc, self.mid), "get_desc")
            assert acl.mdl.get_num_inputs(self.desc) == 1
            assert acl.mdl.get_num_outputs(self.desc) == 1
            assert acl.mdl.get_input_size_by_index(self.desc, 0) == 8192
            assert acl.mdl.get_output_size_by_index(self.desc, 0) == 1280
            assert acl.mdl.get_input_data_type(self.desc, 0) == 0
            assert acl.mdl.get_output_data_type(self.desc, 0) == 0
            in_dims, ret = acl.mdl.get_input_dims(self.desc, 0)
            check(ret, "get_input_dims")
            out_dims, ret = acl.mdl.get_output_dims(self.desc, 0)
            check(ret, "get_output_dims")
            assert in_dims["dims"] == [32, 64]
            assert out_dims["dims"] == [32, 10]
        except BaseException:
            self.close()
            raise

    def close(self):
        errors = []
        if self.desc is not None:
            errors.append(("destroy_desc", acl.mdl.destroy_desc(self.desc)))
            self.desc = None
        if self.mid is not None:
            errors.append(("unload", acl.mdl.unload(self.mid)))
            self.mid = None
        for op, ret in errors:
            check(ret, op)


class Memory:
    def __init__(self):
        self.input = self.output = None
        try:
            self.input, ret = acl.rt.malloc(8192, 2)  # ACL_MEM_MALLOC_NORMAL_ONLY
            check(ret, "malloc(input)")
            self.output, ret = acl.rt.malloc(1280, 2)
            check(ret, "malloc(output)")
        except BaseException:
            self.close()
            raise

    def close(self):
        errors = []
        for attr in ("input", "output"):
            ptr = getattr(self, attr)
            if ptr is not None:
                errors.append((f"free({attr})", acl.rt.free(ptr)))
                setattr(self, attr, None)
        for op, ret in errors:
            check(ret, op)


class Datasets:
    """Own dataset and data-buffer descriptors, but never their backing memory."""
    def __init__(self, memory):
        self.input = self.output = None
        self.buffers = []
        try:
            for attr, size in (("input", 8192), ("output", 1280)):
                ds = acl.mdl.create_dataset()
                if not ds:
                    raise RuntimeError("create_dataset returned NULL")
                setattr(self, attr, ds)
                buf = acl.create_data_buffer(getattr(memory, attr), size)
                if not buf:
                    raise RuntimeError("create_data_buffer returned NULL")
                self.buffers.append(buf)
                _, ret = acl.mdl.add_dataset_buffer(ds, buf)
                check(ret, "add_dataset_buffer")
        except BaseException:
            self.close()
            raise

    def close(self):
        errors = []
        for buf in self.buffers:
            errors.append(("destroy_data_buffer", acl.destroy_data_buffer(buf)))
        self.buffers.clear()
        for attr in ("input", "output"):
            ds = getattr(self, attr)
            if ds is not None:
                errors.append(("destroy_dataset", acl.mdl.destroy_dataset(ds)))
                setattr(self, attr, None)
        for op, ret in errors:
            check(ret, op)


class Request:
    def __init__(self, policy):
        self.policy = policy
        self.model = self.memory = self.datasets = None
        try:
            if policy != "reload_model":
                self.model = Model()
            if policy in ("reuse_all", "recreate_dataset"):
                self.memory = Memory()
            if policy == "reuse_all":
                self.datasets = Datasets(self.memory)
        except BaseException:
            self.close()
            raise

    def close(self):
        for attr in ("datasets", "memory", "model"):
            obj = getattr(self, attr)
            if obj is not None:
                obj.close()
                setattr(self, attr, None)

    def run(self, payload):
        stages = dict.fromkeys(STAGES, 0.0)
        model, memory, datasets = self.model, self.memory, self.datasets

        def timed(name, function):
            start = time.perf_counter_ns()
            value = function()
            stages[name] = (time.perf_counter_ns() - start) / 1000.0
            return value

        start = time.perf_counter_ns()
        try:
            if model is None:
                model = timed("model_prepare_us", Model)
            if memory is None:
                memory = timed("memory_prepare_us", Memory)
            if datasets is None:
                datasets = timed("dataset_prepare_us", lambda: Datasets(memory))
            # This script deliberately supports only the tested integrated DEVICE mode.
            timed("input_copy_us", lambda: check(
                acl.rt.memcpy(memory.input, 8192, acl.util.bytes_to_ptr(payload),
                              len(payload), 3), "memcpy(DEVICE_TO_DEVICE)"))
            timed("execute_us", lambda: check(
                acl.mdl.execute(model.mid, datasets.input, datasets.output), "execute"))
            out = timed("output_read_us", lambda: np.frombuffer(
                acl.util.ptr_to_bytes(memory.output, 1280), dtype=np.float32
            ).reshape(32, 10).copy())
        finally:
            # Synchronous execute has completed before release, even in reload policy.
            if datasets is not None and self.datasets is None:
                timed("dataset_release_us", datasets.close)
            if memory is not None and self.memory is None:
                timed("memory_release_us", memory.close)
            if model is not None and self.model is None:
                timed("model_release_us", model.close)
        stages["total_us"] = (time.perf_counter_ns() - start) / 1000.0
        stages["python_gap_us"] = stages["total_us"] - sum(stages[k] for k in STAGES)
        return out, stages


def load_data():
    with np.load(ROOT / "models/test_data.npz") as data:
        x, y = data["x"], data["y"]
        cpu_reference = data["reference_logits"]
    payloads, valid = [], []
    for offset in range(0, len(x), 32):
        block = np.zeros((32, 64), dtype=np.float32)
        n = min(32, len(x) - offset)
        block[:n] = x[offset:offset + n]
        payloads.append(block.tobytes())
        valid.append(n)
    return payloads, valid, y, cpu_reference


def init_runtime():
    check(acl.init(), "init")
    check(acl.rt.set_device(0), "set_device")
    context, ret = acl.rt.create_context(0)
    check(ret, "create_context")
    mode, ret = acl.rt.get_run_mode()
    check(ret, "get_run_mode")
    if mode != 0:
        raise RuntimeError(f"This benchmark requires ACL_DEVICE=0, got {mode}")
    return context


def close_runtime(context):
    check(acl.rt.destroy_context(context), "destroy_context")
    check(acl.rt.reset_device(0), "reset_device")
    check(acl.finalize(), "finalize")


def benchmark(args):
    payloads, valid, y, cpu_ref = load_data()
    results_dir = ROOT / "results" / args.label
    results_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "configuration": {"rounds": args.rounds, "repeats": args.repeats,
                          "warmup": args.warmup, "seed": 20261104},
        "python": platform.python_version(), "numpy": np.__version__,
        "soc": acl.get_soc_name(), "run_mode": 0, "batch": 32,
        "input_bytes": 8192, "output_bytes": 1280,
        "sha256": {name: hashlib.sha256((ROOT / "models" / name).read_bytes()).hexdigest()
                   for name in ("digits_b32.om", "test_data.npz")},
        "validation": {}, "round_order": [], "rows": 0,
        "timer_pair_median_us": None,
    }
    clock_samples = []
    for _ in range(10000):
        t = time.perf_counter_ns()
        clock_samples.append((time.perf_counter_ns() - t) / 1000)
    metadata["timer_pair_median_us"] = float(np.median(clock_samples))
    context = init_runtime()
    reference = []
    try:
        with (results_dir / "requests.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=[
                "round", "policy", "sample", "input_index", *STAGES, "python_gap_us", "total_us"])
            writer.writeheader()
            # Full held-out validation is untimed; padded tail rows are excluded.
            for policy in POLICIES:
                request = Request(policy)
                outputs = []
                try:
                    for i, payload in enumerate(payloads):
                        out, _ = request.run(payload)
                        assert np.isfinite(out).all()
                        if policy == "reuse_all":
                            reference.append(out.copy())
                        assert np.array_equal(out, reference[i])
                        outputs.append(out[:valid[i]])
                finally:
                    request.close()
                logits = np.concatenate(outputs)
                meta = {
                    "samples": len(y), "correct": int((logits.argmax(1) == y).sum()),
                    "cpu_prediction_agreement": float((logits.argmax(1) == cpu_ref.argmax(1)).mean()),
                    "max_abs_vs_reuse": float(max(np.max(np.abs(
                        o - r[:valid[i]])) for i, (o, r) in enumerate(zip(outputs, reference)))),
                }
                assert meta["correct"] >= int(.95 * len(y))
                assert meta["cpu_prediction_agreement"] == 1
                metadata["validation"][policy] = meta
            for rnd in range(args.rounds):
                order = list(POLICIES)
                random.Random(20261104 + rnd).shuffle(order)
                metadata["round_order"].append(order)
                for policy in order:
                    request = Request(policy)
                    totals = []
                    try:
                        for j in range(args.warmup):
                            out, _ = request.run(payloads[j % len(payloads)])
                            assert np.array_equal(out, reference[j % len(payloads)])
                        for j in range(args.repeats):
                            idx = j % len(payloads)
                            out, times = request.run(payloads[idx])
                            # Validation and CSV I/O happen after the total timer.
                            assert np.isfinite(out).all()
                            assert np.array_equal(out, reference[idx])
                            assert all(np.isfinite(v) and v >= 0 for v in times.values())
                            writer.writerow({"round": rnd, "policy": policy, "sample": j,
                                             "input_index": idx, **times})
                            metadata["rows"] += 1
                            totals.append(times["total_us"])
                    finally:
                        request.close()
                    handle.flush()
                    print(json.dumps({"round": rnd, "policy": policy,
                                      "mean_us": float(np.mean(totals)),
                                      "median_us": float(np.median(totals))}), flush=True)
    finally:
        close_runtime(context)
    metadata["timed_outputs_verified"] = metadata["rows"]
    np.savez_compressed(results_dir / "validation.npz",
                        logits=np.concatenate([r[:v] for r, v in zip(reference, valid)]),
                        labels=y, cpu_reference=cpu_ref)
    (results_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"COMPLETE {metadata['rows']} timed requests", flush=True)


def startup_child():
    """Fresh Python process, but a running device and OS file caches."""
    payloads, _, labels, cpu_ref = load_data()  # Dataset loading excluded here.
    stages = {}
    context = request = None

    def stage(name, function):
        t = time.perf_counter_ns()
        value = function()
        stages[name] = (time.perf_counter_ns() - t) / 1000
        return value

    start = time.perf_counter_ns()
    try:
        context = stage("runtime_init_us", init_runtime)
        request = stage("resource_prepare_us", lambda: Request("reuse_all"))
        out, first = request.run(payloads[0])
        assert np.isfinite(out).all()
        assert np.array_equal(out.argmax(1), cpu_ref[:32].argmax(1))
        reference = out.copy()
        stages["first_request_us"] = first["total_us"]
        stages["first_execute_us"] = first["execute_us"]
        warm = []
        for _ in range(30):
            out, t = request.run(payloads[0])
            assert np.isfinite(out).all()
            assert np.array_equal(out, reference)
            warm.append(t["total_us"])
        stages["next_30_request_mean_us"] = float(np.mean(warm))
        stages["next_30_request_median_us"] = float(np.median(warm))
        stages["first_batch_correct"] = int((reference.argmax(1) == labels[:32]).sum())
    finally:
        if request is not None:
            stage("resource_release_us", request.close)
        if context is not None:
            stage("runtime_release_us", lambda: close_runtime(context))
    stages["internal_session_us"] = (time.perf_counter_ns() - start) / 1000
    print("STARTUP_JSON " + json.dumps(stages), flush=True)


def startup_parent(args):
    target = ROOT / "results" / "startup"
    target.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in range(args.processes):
        start = time.perf_counter_ns()
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--startup-child"],
                                text=True, capture_output=True, timeout=120)
        elapsed_us = (time.perf_counter_ns() - start) / 1000
        (target / f"process-{i:02d}.log").write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"Startup child {i} failed, inspect its local log")
        messages = [line for line in result.stdout.splitlines() if line.startswith("STARTUP_JSON ")]
        assert len(messages) == 1
        row = json.loads(messages[0][len("STARTUP_JSON "):])
        row.update(process=i, process_wall_us=elapsed_us)
        rows.append(row)
        print(json.dumps({"startup_process": i, **row}), flush=True)
    with (target / "processes.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--repeats", type=int, default=300)
    p.add_argument("--warmup", type=int, default=20)
    p.add_argument("--label", default="formal")
    p.add_argument("--startup-child", action="store_true")
    p.add_argument("--startup", action="store_true")
    p.add_argument("--processes", type=int, default=12)
    a = p.parse_args()
    if min(a.rounds, a.repeats, a.warmup, a.processes) < 1:
        p.error("Counts must be positive")
    if Path(a.label).name != a.label:
        p.error("label must be a single directory name")
    if a.startup_child:
        startup_child()
    elif a.startup:
        startup_parent(a)
    else:
        benchmark(a)
