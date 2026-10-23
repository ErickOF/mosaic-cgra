"""Check mathematical lane equivalence and bounded sequential alignment.

Requires Yosys with the slang frontend. Simulation checks four-state containment
and clockless reset. Sequential proofs cover 2 * LANE_LATENCY + 6 sampled edges; they are bounded, not induction.
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

from run_vector_lane_regression import (
    DEFAULTS,
    DEPENDENCIES,
    ROOT,
    TEST_DIR,
    verification_hashes,
)
from run_vector_lane_regression import PROFILES as SIMULATION_PROFILES

PROFILES = (
    *(
        (
            f"e{e}_features{m}{c}{s}{n}",
            DEFAULTS
            | {
                "ELEMENT_WIDTH": e,
                "ACC_WIDTH": 2 * e,
                "SUPPORT_MUL": m,
                "SUPPORT_MAC": c,
                "SUPPORT_SATURATION": s,
                "SUPPORT_MINMAX": n,
                "LANE_LATENCY": 0,
                "MUL_LATENCY": 0,
                "MAC_LATENCY": 0,
            },
        )
        for e in (1, 2, 3, 4)
        for m, c, s, n in product(range(2), repeat=4)
    ),
    *(
        (name, p)
        for name, p in SIMULATION_PROFILES
        if (name.startswith(("l", "custom_latency"))) and p["LANE_LATENCY"] > 0
    ),
)


def proof_success(text, parameters):
    depth = 2 * parameters["LANE_LATENCY"] + 6
    marker = (
        f"Reached maximum number of time steps -> proved base case for {depth} steps: SUCCESS!"
        if parameters["LANE_LATENCY"] > 4
        else "SAT proof finished - no model found: SUCCESS!"
    )
    return marker in text and "Import proof for assert:" in text


def run_profile(task):
    name, p, build, tool, timeout, sources = task
    case = build / name
    case.mkdir(exist_ok=True)
    depth = 2 * p["LANE_LATENCY"] + 6
    if not p["LANE_LATENCY"]:
        command = "sat -verify -prove-asserts -set-def-inputs -show-inputs -show-outputs\n"
    else:
        strategy = (
            f"-tempinduct-baseonly -maxsteps {depth}" if p["LANE_LATENCY"] > 4 else f"-seq {depth}"
        )
        command = (
            f"sat -verify {strategy} -prove-asserts "
            "-set-init-def -set-def-inputs -set-at 1 i_rstb 0 "
            "-set-at 1 i_clock_enable 0 -show-inputs -show-outputs\n"
        )
    script = (
        "read_slang --top vector_lane_formal "
        + " ".join(f"-G{key}={value}" for key, value in p.items())
        + " "
        + " ".join(str(path.relative_to(ROOT)) for path in sources)
        + "\nprep -top vector_lane_formal -flatten\nmemory_map\nasync2sync\ndffunmap\n"
        + "chformal -lower\nopt\ncheck -assert\n"
        + command
    )
    (case / "prove.ys").write_text(script)
    log = case / "formal.log"
    row = {
        "name": name,
        "parameters": p,
        "status": "FAIL",
        "log": str(log),
        "scope": "combinational" if not p["LANE_LATENCY"] else "bounded_sequential",
        "depth": 2 * p["LANE_LATENCY"] + 6 if p["LANE_LATENCY"] else 0,
    }
    try:
        with log.open("w") as output:
            result = subprocess.run(
                [tool, "-Q", "-T", "-s", str(case / "prove.ys")],
                check=False,
                stdout=output,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                cwd=ROOT,
            )
        text = log.read_text()
        if result.returncode == 0 and proof_success(text, p):
            row["status"] = "PASS"
        elif "No such command: read_slang" in text:
            row["status"] = "NOT_RUN"
            row["error"] = "Yosys slang frontend unavailable"
    except subprocess.TimeoutExpired:
        row["status"] = "NOT_RUN"
        row["error"] = f"Proof exceeded {timeout} seconds"
    print(name, row["status"], flush=True)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yosys", default="yosys")
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--case", action="append", choices=[name for name, _ in PROFILES])
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--resume", action="store_true", help="Reuse matching successful proofs")
    args = parser.parse_args()
    if not 1 <= args.jobs <= 32:
        parser.error("--jobs must be between 1 and 32")
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    sources = (
        *DEPENDENCIES,
        ROOT / "src/rtl/building_blocks/vector_lane.sv",
        TEST_DIR / "vector_lane_reference.sv",
        TEST_DIR / "vector_lane_formal.sv",
    )
    summary = {
        "status": "NOT_RUN",
        "profiles": [],
        "started_at_utc": datetime.now(UTC).isoformat(),
        "scope": "Two-state combinational equivalence and bounded enabled-edge sequential equivalence",
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sources
        },
        "verification_sha256": verification_hashes(TEST_DIR),
        "technology_mapping": "NOT_RUN",
        "physical_timing": "NOT_RUN",
        "physical_power": "NOT_RUN",
    }
    tool = shutil.which(args.yosys)
    try:
        if tool is None:
            raise FileNotFoundError(f"Yosys executable missing: {args.yosys}")
        summary["tool_version"] = subprocess.check_output([tool, "-V"], text=True).strip()
        selected = [(name, p) for name, p in PROFILES if not args.case or name in args.case]
        cached = {}
        if args.resume and (build / "summary.json").exists():
            previous = json.loads((build / "summary.json").read_text())
            if (
                previous.get("source_sha256") == summary["source_sha256"]
                and previous.get("tool_version") == summary["tool_version"]
            ):
                for row in previous["profiles"]:
                    log = Path(row["log"])
                    if (
                        row["status"] == "PASS"
                        and row["parameters"] == dict(selected).get(row["name"])
                        and log.exists()
                        and proof_success(log.read_text(), row["parameters"])
                    ):
                        cached[row["name"]] = row
        summary["resumed_profiles"] = len(cached)
        tasks = [
            (name, p, build, tool, args.timeout, sources)
            for name, p in selected
            if name not in cached
        ]
        summary["profiles"] = list(cached.values())
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            for row in pool.map(run_profile, tasks):
                summary["profiles"].append(row)
                (build / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        order = {name: i for i, (name, _) in enumerate(PROFILES)}
        summary["profiles"].sort(key=lambda row: order[row["name"]])
        expected = len(set(args.case)) if args.case else len(PROFILES)
        rows = summary["profiles"]
        if len(rows) == expected and all(row["status"] == "PASS" for row in rows):
            summary["status"] = "PASS"
        elif any(row["status"] == "FAIL" for row in rows):
            summary["status"] = "FAIL"
    except (OSError, subprocess.SubprocessError) as error:
        summary["error"] = str(error)
    finally:
        summary["finished_at_utc"] = datetime.now(UTC).isoformat()
        (build / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(f"Vector lane formal {summary['status']}: {build / 'summary.json'}", flush=True)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
