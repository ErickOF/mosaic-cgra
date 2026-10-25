"""Lint the native AGU source and its dependencies for every PyUVM profile.

This target invokes Verilator only. Technology synthesis is deferred to the
Design Compiler flow; no Yosys, netlist generation or formal proof is invoked.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from run_agu_regression import (
    DEPENDENCIES,
    PROFILES,
    ROOT,
    TEST_DIR,
    verification_hashes,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verilator", default="verilator")
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument(
        "--case", action="append", choices=[name for name, _ in PROFILES]
    )
    args = parser.parse_args()
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    sources = (*DEPENDENCIES, ROOT / "src/rtl/building_blocks/agu.sv")
    summary = {
        "status": "NOT_RUN",
        "started_at_utc": datetime.now(UTC).isoformat(),
        "scope": "RTL lint only",
        "profiles": [],
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sources
        },
        "verification_sha256": verification_hashes(TEST_DIR),
        "synthesis": {
            "status": "NOT_RUN",
            "tool": "Design Compiler",
            "reason": "Deferred",
        },
        "formal": "NOT_RUN",
        "commercial_lint": "NOT_RUN",
    }
    try:
        tool = shutil.which(args.verilator)
        if tool is None:
            raise FileNotFoundError(
                f"Verilator executable unavailable: {args.verilator}"
            )
        summary["tool_version"] = subprocess.check_output(
            [tool, "--version"], text=True
        ).strip()
        selected = [
            (name, p) for name, p in PROFILES if not args.case or name in args.case
        ]
        for name, parameters in selected:
            case = build / name
            case.mkdir(exist_ok=True)
            log = case / "lint.log"
            command = [
                tool,
                "--lint-only",
                "-Wall",
                "--top-module",
                "agu",
                *(f"-G{key}={value}" for key, value in parameters.items()),
                *map(str, sources),
            ]
            with log.open("w") as output:
                result = subprocess.run(
                    command,
                    cwd=ROOT,
                    check=False,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                )
            diagnostic = log.read_text()
            status = (
                "PASS"
                if result.returncode == 0 and "%Warning" not in diagnostic
                else "FAIL"
            )
            summary["profiles"].append(
                {
                    "name": name,
                    "parameters": parameters,
                    "status": status,
                    "command": command,
                    "log": str(log),
                    "waivers": [],
                }
            )
            print(name, status, flush=True)
        summary["status"] = (
            "PASS"
            if len(summary["profiles"]) == len(selected)
            and all(row["status"] == "PASS" for row in summary["profiles"])
            else "FAIL"
        )
    except (FileNotFoundError, subprocess.SubprocessError) as error:
        summary["error"] = str(error)
    except OSError as error:
        summary.update(status="FAIL", error=str(error))
    finally:
        summary["finished_at_utc"] = datetime.now(UTC).isoformat()
        output = build / "summary.json"
        output.write_text(json.dumps(summary, indent=2) + "\n")
        print(f"AGU lint {summary['status']}: {output}")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
