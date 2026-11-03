"""Small diagnostic: one model, one I/O slot, an explicit or default stream."""
import argparse
import json

import acl
import numpy as np

from async_experiment import ROOT, TensorSlot, check

parser = argparse.ArgumentParser()
parser.add_argument("--default-stream", action="store_true")
parser.add_argument("--sync-first", action="store_true")
args = parser.parse_args()
context = model_id = slot = None
stream = 0
check(acl.init(), "init")
try:
    check(acl.rt.set_device(0), "set_device")
    context, ret = acl.rt.create_context(0)
    check(ret, "create_context")
    model_id, ret = acl.mdl.load_from_file(str(ROOT / "models/digits_b32.om"))
    check(ret, "load_from_file")
    if not args.default_stream:
        stream, ret = acl.rt.create_stream()
        check(ret, "create_stream")
    slot = TensorSlot(8192, 1280)
    with np.load(ROOT / "models/test_data.npz") as data:
        slot.write(data["x"][:32])
    sync_ret = None
    if args.sync_first:
        sync_ret = acl.mdl.execute(model_id, slot.inputs, slot.outputs)
    ret = acl.mdl.execute_async(model_id, slot.inputs, slot.outputs, stream)
    result = {"default_stream": args.default_stream, "sync_first": args.sync_first,
              "sync_ret": sync_ret, "execute_async_ret": ret,
              "recent_error": acl.get_recent_err_msg()}
    if ret == 0:
        result["synchronize_ret"] = acl.rt.synchronize_stream(stream)
        result["finite_output"] = bool(np.isfinite(slot.read()).all())
    print("PROBE_RESULT=" + json.dumps(result), flush=True)
finally:
    if stream != 0:
        check(acl.rt.synchronize_stream(stream), "cleanup sync")
    if slot is not None:
        slot.close()
    if stream != 0:
        check(acl.rt.destroy_stream(stream), "destroy_stream")
    if model_id is not None:
        check(acl.mdl.unload(model_id), "unload")
    if context is not None:
        check(acl.rt.destroy_context(context), "destroy_context")
    check(acl.rt.reset_device(0), "reset_device")
    check(acl.finalize(), "finalize")
