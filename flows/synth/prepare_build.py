#!/usr/bin/env python3
"""Prepare synthesis output directories with bounded NFS-safe retries."""

import argparse
import errno
from pathlib import Path
import shutil
import time


OUTPUT_DIRECTORIES = ("work", "reports", "db", "netlist")
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


def prepare_build(build_dir):
    build_dir = Path(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)
    for name in OUTPUT_DIRECTORIES:
        remove_output(build_dir / name)


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
