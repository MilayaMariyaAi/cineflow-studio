"""Prove this distribution tree still matches its DIST_MANIFEST.json.

Ships inside every cineflow-studio sync (stdlib only). Exit 0 = tree intact;
exit 1 = a file was added, removed or hand-edited after the sync.
Usage: python scripts/verify_dist.py [--root PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

SKIP = {"DIST_MANIFEST.json"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    root = args.root.resolve()
    manifest_path = root / "DIST_MANIFEST.json"
    if not manifest_path.is_file():
        print("VERIFY FAIL: DIST_MANIFEST.json missing", file=sys.stderr)
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems: list[str] = []
    for rel, expected in sorted(manifest["files"].items()):
        path = root / rel
        if not path.is_file():
            problems.append(f"missing: {rel}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            problems.append(f"modified: {rel}")
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root).as_posix()
            if rel not in SKIP and rel not in manifest["files"]:
                problems.append(f"unexpected: {rel}")
    sha_file = root / "DIST_SOURCE_SHA"
    if not sha_file.is_file() or sha_file.read_text(encoding="utf-8").strip() != manifest.get("source_sha", ""):
        problems.append("DIST_SOURCE_SHA does not match the manifest source_sha")
    if problems:
        for line in problems:
            print(f"VERIFY FAIL: {line}", file=sys.stderr)
        return 1
    print(f"VERIFY OK: {len(manifest['files'])} files match DIST_MANIFEST.json (source {manifest['source_sha']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
