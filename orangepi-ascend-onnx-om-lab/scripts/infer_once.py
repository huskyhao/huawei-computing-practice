"""Infer one held-out digit, padding to an already compiled static batch."""
import argparse
import json

import acl
import numpy as np

from benchmark import AclModel, ROOT, check

parser = argparse.ArgumentParser()
parser.add_argument("--batch", type=int, choices=(1, 32, 128), default=32)
parser.add_argument("--index", type=int, default=0)
args = parser.parse_args()
with np.load(ROOT / "models/test_data.npz") as archive:
    x, y = archive["x"], archive["y"]
if not 0 <= args.index < len(y):
    parser.error(f"index must be in [0, {len(y) - 1}]")
check(acl.init(), "init")
context, model = None, None
try:
    check(acl.rt.set_device(0), "rt.set_device")
    context, ret = acl.rt.create_context(0)
    check(ret, "rt.create_context")
    run_mode, ret = acl.rt.get_run_mode()
    check(ret, "rt.get_run_mode")
    model = AclModel(ROOT / f"models/digits_b{args.batch}.om", args.batch, run_mode)
    batch = np.zeros((args.batch, 64), dtype=np.float32)
    batch[0] = x[args.index]
    scores = model.infer(batch)[0]
    print(json.dumps({"test_index": args.index, "label": int(y[args.index]),
                      "npu_prediction": int(scores.argmax()), "run_mode": run_mode,
                      "logits": scores.tolist()}, indent=2))
finally:
    if model is not None:
        model.close()
    if context is not None:
        check(acl.rt.destroy_context(context), "rt.destroy_context")
    check(acl.rt.reset_device(0), "rt.reset_device")
    check(acl.finalize(), "finalize")
