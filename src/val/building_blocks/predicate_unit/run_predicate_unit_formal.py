"""Prove predicate-bank sequential refinement using Yosys/slang and SAT induction.

Simulation separately checks X/Z and asynchronous reset between sampled clocks.
The reference and DUT have independent implementations of state and commands.
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

from run_predicate_unit_regression import (
    DEFAULTS,
    DEPENDENCIES,
    ROOT,
    TEST_DIR,
    verification_hashes,
)

PROFILES = tuple(
    (
        f"d{d}_n{n}_async{a}",
        DEFAULTS | {"PRED_DEPTH": d, "NUM_LANES": n, "ASYNC_RESET": a},
    )
    for d, n, a in product((1, 2, 3), (1, 2, 3, 4), range(2))
) + tuple((f"d4_n4_async{a}", DEFAULTS | {"ASYNC_RESET": a}) for a in range(2))


def prove(task):
    name, p, build, tool, timeout, sources = task
    case = build / name
    case.mkdir(exist_ok=True)
    script = (
        "read_slang --top predicate_unit -D MOSAIC_PREDICATE_UNIT_FORMAL "
        + " ".join(f"-G{k}={v}" for k, v in p.items())
        + " "
        + " ".join(str(path.relative_to(ROOT)) for path in sources)
        + "\nprep -top predicate_unit -flatten\nmemory_map\nasync2sync\ndffunmap\n"
        + "chformal -lower\nopt\ncheck -assert\n"
        + "sat -verify -tempinduct -seq 3 -maxsteps 8 -prove-asserts "
        "-set-init-def -set-def-inputs -set-at 1 i_rstb 0 "
        "-show-inputs -show-outputs\n"
    )
    (case / "prove.ys").write_text(script)
    log = case / "formal.log"
    row = {
        "name": name,
        "parameters": p,
        "status": "FAIL",
        "log": str(log),
        "scope": "sequential_induction",
    }
    try:
        with log.open("w") as output:
            result = subprocess.run(
                [tool, "-Q", "-T", "-s", str(case / "prove.ys")],
                cwd=ROOT,
                stdout=output,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=timeout,
            )
        diagnostic = log.read_text()
        if (
            result.returncode == 0
            and "Induction step proven: SUCCESS!" in diagnostic
            and "Import proof for assert:" in diagnostic
        ):
            row["status"] = "PASS"
        elif "No such command: read_slang" in diagnostic:
            row.update(status="NOT_RUN", error="Yosys slang frontend unavailable")
    except subprocess.TimeoutExpired:
        row.update(status="NOT_RUN", error=f"Proof exceeded {timeout} seconds")
    print(name, row["status"], flush=True)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yosys", default="yosys")
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument(
        "--case", action="append", choices=[name for name, _ in PROFILES]
    )
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 32:
        parser.error("--jobs must be between 1 and 32")
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    sources = (
        *DEPENDENCIES,
        ROOT / "src/rtl/building_blocks/predicate_unit.sv",
        TEST_DIR / "predicate_unit_reference.sv",
        TEST_DIR / "predicate_unit_formal.sv",
    )
    summary = {
        "status": "NOT_RUN",
        "profiles": [],
        "started_at_utc": datetime.now(UTC).isoformat(),
        "scope": "Two-state sequential refinement by SAT induction after reset",
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sources
        },
        "verification_sha256": verification_hashes(TEST_DIR),
        "clock_gate_memory_equivalence": "NOT_RUN",
        "physical_timing": "NOT_RUN",
        "physical_power": "NOT_RUN",
    }
    try:
        tool = shutil.which(args.yosys)
        if tool is None:
            raise FileNotFoundError("Yosys/slang executable unavailable")
        summary["tool_version"] = subprocess.check_output(
            [tool, "-V"], text=True
        ).strip()
        tasks = [
            (name, p, build, tool, args.timeout, sources)
            for name, p in PROFILES
            if not args.case or name in args.case
        ]
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            summary["profiles"] = list(pool.map(prove, tasks))
        if all(row["status"] == "PASS" for row in summary["profiles"]):
            summary["status"] = "PASS"
        elif any(row["status"] == "FAIL" for row in summary["profiles"]):
            summary["status"] = "FAIL"
    except (OSError, subprocess.SubprocessError) as error:
        summary["error"] = str(error)
    finally:
        summary["finished_at_utc"] = datetime.now(UTC).isoformat()
        (build / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(f"Predicate unit formal {summary['status']}: {build / 'summary.json'}")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
