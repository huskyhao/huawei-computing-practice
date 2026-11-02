"""Train an offline digits classifier and export the SAME weights to ONNX."""
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import onnx
import sklearn
from onnx import TensorProto, helper, numpy_helper
from onnx.reference import ReferenceEvaluator
from sklearn.datasets import load_digits
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier
from threadpoolctl import threadpool_info, threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
BATCHES = (1, 32, 128)


def logits(x, weights):
    return np.maximum(x @ weights["w1"] + weights["b1"], 0) @ weights["w2"] + weights["b2"]


def main():
    (ROOT / "models").mkdir(exist_ok=True)
    (ROOT / "results").mkdir(exist_ok=True)
    digits = load_digits()
    x = np.ascontiguousarray(digits.data / 16.0, dtype=np.float32)
    y = digits.target.astype(np.int64)
    indices = np.arange(len(y))
    train_idx, test_idx = train_test_split(indices, test_size=0.2, random_state=42, stratify=y)
    classifier = MLPClassifier(hidden_layer_sizes=(128,), activation="relu", solver="lbfgs",
                               alpha=1e-4, max_iter=300, tol=1e-6, random_state=42)
    with threadpool_limits(limits=1):
        start = time.perf_counter()
        classifier.fit(x[train_idx], y[train_idx])
        training_seconds = time.perf_counter() - start
        sklearn_pred = classifier.predict(x[test_idx])
    weights = {"w1": classifier.coefs_[0].astype(np.float32),
               "b1": classifier.intercepts_[0].astype(np.float32),
               "w2": classifier.coefs_[1].astype(np.float32),
               "b2": classifier.intercepts_[1].astype(np.float32)}
    with threadpool_limits(limits=1):
        reference = logits(x[test_idx], weights)
    np.savez(ROOT / "models/weights.npz", **weights)
    np.savez(ROOT / "models/test_data.npz", x=x[test_idx], y=y[test_idx],
             test_indices=test_idx, reference_logits=reference, sklearn_predictions=sklearn_pred)
    checks, hashes = {}, {}
    for batch in BATCHES:
        graph = helper.make_graph([
            helper.make_node("MatMul", ["input", "w1"], ["mm1"]),
            helper.make_node("Add", ["mm1", "b1"], ["hidden"]),
            helper.make_node("Relu", ["hidden"], ["relu"]),
            helper.make_node("MatMul", ["relu", "w2"], ["mm2"]),
            helper.make_node("Add", ["mm2", "b2"], ["logits"]),
        ], "digits_mlp_64_128_10", [helper.make_tensor_value_info("input", TensorProto.FLOAT, [batch, 64])],
           [helper.make_tensor_value_info("logits", TensorProto.FLOAT, [batch, 10])],
           [numpy_helper.from_array(value, name) for name, value in weights.items()])
        model = helper.make_model(graph, producer_name="digits-ascend-practice",
                                  opset_imports=[helper.make_opsetid("", 13)], ir_version=8)
        onnx.checker.check_model(model)
        path = ROOT / f"models/digits_b{batch}.onnx"
        onnx.save(model, path)
        sample = x[test_idx[:batch]]
        with threadpool_limits(limits=1):
            onnx_result = ReferenceEvaluator(model).run(None, {"input": sample})[0]
            expected = logits(sample, weights)
        np.testing.assert_allclose(onnx_result, expected, rtol=1e-5, atol=1e-5)
        checks[str(batch)] = float(np.max(np.abs(onnx_result - expected)))
        hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(), "numpy": np.__version__, "sklearn": sklearn.__version__,
        "onnx": onnx.__version__, "dataset": "sklearn.datasets.load_digits (8x8, values divided by 16)",
        "total_samples": len(y), "train_samples": len(train_idx), "test_samples": len(test_idx),
        "split_random_state": 42, "stratified": True, "architecture": [64, 128, 10],
        "training_parameters": classifier.get_params(), "training_seconds": training_seconds,
        "training_iterations": int(classifier.n_iter_), "loss": float(classifier.loss_),
        "sklearn_accuracy": float(accuracy_score(y[test_idx], sklearn_pred)),
        "numpy_fp32_accuracy": float(accuracy_score(y[test_idx], reference.argmax(axis=1))),
        "numpy_sklearn_prediction_agreement": float(np.mean(reference.argmax(axis=1) == sklearn_pred)),
        "onnx_reference_max_abs_error": checks, "onnx_sha256": hashes,
        "threadpools": threadpool_info(), "batches": BATCHES,
    }
    (ROOT / "results/training.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2), flush=True)


if __name__ == "__main__":
    main()
