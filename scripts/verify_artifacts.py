#!/usr/bin/env python3
"""Verify measured sources, both atomic modes, all samples and public files."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for line in (ROOT / "measurements/source-sha256.txt").read_text().splitlines():
    digest, name = line.split(maxsplit=1)
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
for line in (ROOT / "validation/script-sha256.txt").read_text().splitlines():
    digest, name = line.split(maxsplit=1)
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest,name
subprocess.run([sys.executable, str(ROOT / "scripts/analyze.py")],check=True,stdout=subprocess.DEVNULL)
for mode in ("lse", "llsc"):
    for prefix in ("bench", "ubsan"):
        log = (ROOT / f"measurements/{prefix}-{mode}.stderr.txt").read_text()
        assert "SELFTEST PASS cases=60" in log
        assert "runtime error" not in log
lse = (ROOT / "measurements/counter-lse.s").read_text()
llsc = (ROOT / "measurements/counter-llsc.s").read_text()
assert re.search(r"\bldadd\b", lse) and not re.search(r"\bstxr\b", lse)
assert re.search(r"\bldxr\b", llsc) and re.search(r"\bstxr\b", llsc)
assert not re.search(r"\bldadd\b", llsc)
blog = (ROOT / "blog.md").read_text(encoding="utf-8")
for mode in ("lse", "llsc"):
    assert (ROOT / f"measurements/table-{mode}.md").read_text(encoding="utf-8").strip() in blog
assert (ROOT / "validation/table-8threads.md").read_text(encoding="utf-8").strip() in blog
for doc in ("README.md", "blog.md", "sources.md", "PUBLICATION.md"):
    text = (ROOT / doc).read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)]+)\)",text):
        if "://" not in target and not target.startswith("#"):
            assert (ROOT / target.split("#")[0]).exists(),target
assert (ROOT / "assets/scaling.png").read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
for p in ROOT.rglob("*"):
    if not p.is_file() or ".git" in p.parts or p.suffix == ".png": continue
    text = p.read_text(encoding="utf-8")
    # Match identity-bearing patterns without embedding any private identifiers.
    assert not re.search(r"(?i)/(?:home|Users)/|[A-Z]:[\\/]Users[\\/]|/(?:nix)/store/|BEGIN [A-Z ]*PRIVATE KEY",text),p
    assert not re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b",text),p
summary=json.loads((ROOT / "measurements/summary.json").read_text())
print(f"PASS: source hashes, {summary['samples']} main + 120 validation batches, two instruction modes, checksums, public paths and blog tables")
