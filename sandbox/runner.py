"""Trusted wrapper inside a disposable, networkless container. Never run on host."""

import base64
import json
from pathlib import Path
import subprocess
import sys

job = json.loads(sys.stdin.buffer.read(18_000_000))
for name, value in job["files"].items():
    if not name or any(c not in "0123456789abcdef-" for c in name):
        raise ValueError("Invalid input ID")
    Path("/input", name).write_bytes(base64.b64decode(value, validate=True))
Path("/input/job.py").write_text(job["code"])
try:
    result = subprocess.run(
        [sys.executable, "-I", "/input/job.py"],
        cwd="/output",
        env={
            "PATH": "/usr/local/bin:/usr/bin",
            "MPLBACKEND": "Agg",
            "MPLCONFIGDIR": "/tmp/mpl",
            "HOME": "/tmp",
        },
        capture_output=True,
        timeout=40,
    )
    if result.returncode:
        print(
            json.dumps(
                {
                    "error": "Python failed: "
                    + result.stderr.decode(errors="replace")[-2000:]
                }
            )
        )
    else:
        files = []
        total = 0
        for path in Path("/output").iterdir():
            if path.is_symlink() or not path.is_file():
                continue
            size = path.stat().st_size
            total += size
            if size > 5_000_000 or total > 5_000_000 or len(files) >= 10:
                raise ValueError("Artifact limits exceeded")
            files.append(
                {
                    "name": path.name,
                    "content": base64.b64encode(path.read_bytes()).decode(),
                }
            )
        print(
            json.dumps(
                {
                    "stdout": result.stdout.decode(errors="replace")[:12000],
                    "files": files,
                }
            )
        )
except Exception as exc:
    print(
        json.dumps(
            {
                "error": type(exc).__name__
                + ": isolated execution failed or exceeded limits"
            }
        )
    )
