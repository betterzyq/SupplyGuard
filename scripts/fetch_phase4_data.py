#!/usr/bin/env python3
"""Fetch only two pinned CC BY DataCo files; verify official hashes and sizes."""

import argparse
import hashlib
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/catalog/dataco-v5.json"
DIRECTORY = ROOT / "data/external/dataco-v5"


def checksum(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    manifest = json.loads(CATALOG.read_text())
    DIRECTORY.mkdir(parents=True, exist_ok=True)
    with httpx.Client(
        follow_redirects=True, timeout=httpx.Timeout(60, connect=20)
    ) as client:
        for item in manifest["files"]:
            target = DIRECTORY / item["filename"]
            if not target.exists():
                if args.check_only:
                    raise FileNotFoundError(
                        target.name + " missing; run make phase4-data"
                    )
                partial = target.with_suffix(".csv.part")
                print("Downloading official DataCo v5:", target.name, flush=True)
                seen = 0
                last = 0
                with client.stream("GET", item["url"]) as response:
                    response.raise_for_status()
                    with partial.open("wb") as output:
                        for chunk in response.iter_bytes(1024 * 1024):
                            seen += len(chunk)
                            if seen > item["bytes"]:
                                raise ValueError("Download exceeds pinned size")
                            output.write(chunk)
                            if seen - last >= 20 * 1024 * 1024:
                                print("Downloaded", seen, "bytes", flush=True)
                                last = seen
                if seen != item["bytes"] or checksum(partial) != item["sha256"]:
                    raise ValueError("Official size/SHA256 mismatch")
                partial.replace(target)
            if (
                target.stat().st_size != item["bytes"]
                or checksum(target) != item["sha256"]
            ):
                raise ValueError("Existing dataset differs from pinned official data")
            print("PASS official bytes and SHA256:", target.name, flush=True)
    (DIRECTORY / "source-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
