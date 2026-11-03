"""Time a subprocess without requiring the optional /usr/bin/time package."""
import resource
import subprocess
import sys
import time
from pathlib import Path

record = Path(sys.argv[1])
start = time.perf_counter()
returncode = subprocess.call(sys.argv[2:])
elapsed = time.perf_counter() - start
max_rss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
record.write_text(f"elapsed_seconds={elapsed:.6f}\nmax_rss_kb={max_rss}\nreturncode={returncode}\n", encoding="utf-8")
raise SystemExit(returncode)
