"""Verify the shareable artifact manifest and relative Markdown links."""
import hashlib
import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
manifest = ROOT / "SHA256SUMS.txt"
count = 0
for line in manifest.read_text(encoding="utf-8").splitlines():
    digest, name = line.split("  ", 1)
    path = (ROOT / name).resolve()
    assert path.is_relative_to(ROOT.resolve()), name
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name
    count += 1
links = 0
for md in ROOT.rglob("*.md"):
    if any(part in ("models", "logs", "results", ".venv") for part in md.relative_to(ROOT).parts):
        continue
    for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", md.read_text(encoding="utf-8")):
        if "://" in target or target.startswith("#"):
            continue
        dest = unquote(target.split("#", 1)[0])
        assert (md.parent / dest).exists(), (md.name, target)
        links += 1
print(f"PASS: {count} file hashes and {links} relative Markdown links")
