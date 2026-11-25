"""Scan Git-visible working-tree files with pinned Gitleaks; never print findings unredacted."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

IMAGE = "zricethezav/gitleaks:v8.24.3@sha256:e1b35e12a8c6fa8901f060459cfb6b2fc4c484d3afbe3b029733a3bbfab07055"


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    files = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=root,
    ).decode().split("\0")
    with tempfile.TemporaryDirectory(prefix="passanorte-scan-") as directory:
        staging = Path(directory)
        for name in set(files):
            if not name or not (root / name).is_file():
                continue
            if name.startswith("secrets/") or name.endswith(".private.pem"):
                raise RuntimeError("Secret material must not be tracked")
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(root / name, target)
        return subprocess.call([
            "docker", "run", "--rm", "-v", f"{staging}:/scan:ro", IMAGE,
            "dir", "/scan", "--redact", "--no-banner",
        ], cwd=root)


if __name__ == "__main__":
    raise SystemExit(main())
