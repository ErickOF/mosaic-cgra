#!/usr/bin/env python3
"""Prepare synthesis output directories with bounded NFS-safe retries."""

import argparse
import errno
from pathlib import Path
import shutil
import sys
import time
import uuid


OUTPUT_DIRECTORIES = ("work", "reports", "db", "netlist")
QUARANTINE_DIRECTORY = ".stale-synthesis"
RETRYABLE_ERRNOS = {errno.EBUSY, errno.ENOTEMPTY, errno.ESTALE}


def remove_output(path, attempts=6, initial_delay=0.1):
    path = Path(path)
    for attempt in range(attempts):
        try:
            if path.is_symlink() or path.is_file():
                path.unlink()
            else:
                shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except OSError as error:
            if error.errno not in RETRYABLE_ERRNOS or attempt + 1 == attempts:
                raise
            time.sleep(initial_delay * (2 ** attempt))


def quarantine_output(path, quarantine_root):
    path = Path(path)
    quarantine_root = Path(quarantine_root)
    quarantine_root.mkdir(parents=True, exist_ok=True)
    destination = quarantine_root / f"{path.name}-{uuid.uuid4().hex}"
    path.rename(destination)
    try:
        remove_output(destination, attempts=2)
    except OSError as error:
        if error.errno not in RETRYABLE_ERRNOS:
            raise
        print(
            f"Warning: retained busy synthesis output at {destination}: {error}",
            file=sys.stderr,
        )
    return destination


def prepare_build(build_dir):
    build_dir = Path(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    for name in OUTPUT_DIRECTORIES:
        output = build_dir / name
        try:
            remove_output(output)
        except OSError as error:
            if error.errno not in RETRYABLE_ERRNOS:
                raise
            quarantine_output(output, build_dir / QUARANTINE_DIRECTORY)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    args = parser.parse_args()
    try:
        prepare_build(args.build.resolve())
    except OSError as error:
        parser.exit(2, f"Synthesis build cleanup failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
