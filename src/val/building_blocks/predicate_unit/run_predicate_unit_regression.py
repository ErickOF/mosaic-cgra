"""Run the predicate bank depth/lane matrix and strict integration assertions."""

import hashlib
import json
import os
import shlex
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from mosaic_uvm.regression import (
    campaign_status,
    finish_summary,
    license_unavailable,
    parameter_guard,
    parse_args,
    passed_test,
    require_simulator,
    run_simulation,
)
from mosaic_uvm.regression import (
    verification_hashes as shared_verification_hashes,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from predicate_unit.config import DEFAULTS

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(
    ROOT / f"src/rtl/{name}.sv"
    for name in (
        "building_blocks/predicate_unit_pkg",
        "common/dff",
        "common/decoder",
        "common/operand_isolation",
        "common/write_gate",
    )
)
PROFILES = tuple(
    (
        f"d{d}_n{n}_async{a}",
        DEFAULTS | {"PRED_DEPTH": d, "NUM_LANES": n, "ASYNC_RESET": a},
    )
    for d, n, a in product((1, 2, 3, 4, 8), (1, 2, 4, 8), range(2))
)
INVALID = (
    *(
        (f"{key.lower()}_{label}", {key: value})
        for key in ("PRED_DEPTH", "NUM_LANES")
        for label, value in (
            ("zero", 0),
            ("negative", -1),
            ("x", "32'bx"),
            ("z", "32'bz"),
            ("wide", "64'd4294967296"),
        )
    ),
    *(
        (f"{key.lower()}_{label}", {key: value})
        for key in ("ASYNC_RESET", "OPCODE_WIDTH")
        for label, value in (
            ("wrong", 2),
            ("negative", -1),
            ("x", "32'bx"),
            ("z", "32'bz"),
        )
    ),
    ("state_overflow", {"PRED_DEPTH": 1073741823, "NUM_LANES": 2}),
)
PROBES = tuple(
    (f"{name}:{state}", name, reset)
    for reset in range(2)
    for name in (
        "i_rstb",
        "i_clock_enable",
        "i_valid",
        "load0",
        "load1",
        "load2",
        "load3",
    )
    for state in "xz"
)
REUSED_VERIFICATION = tuple(
    ROOT / "src/val/building_blocks" / name
    for name in (
        "vector_lane/transaction.py",
        "multiplier/transaction.py",
        "multiplier/monitor.py",
    )
)


def verification_hashes(test_dir):
    return shared_verification_hashes(test_dir) | {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in REUSED_VERIFICATION
    }


def simulate(args, build, rtl, parameters, seed, probe=""):
    prefix = "-Ppredicate_unit." if args.sim == "icarus" else "-pvalue+predicate_unit."
    flags = " ".join(
        shlex.quote(f"{prefix}{key}={value}") for key, value in parameters.items()
    )
    return run_simulation(
        args,
        ROOT,
        TEST_DIR,
        "predicate_unit",
        "test_predicate_unit",
        "PredicateTest",
        build,
        " ".join(map(str, (*DEPENDENCIES, rtl))),
        parameters=parameters,
        compile_args=f"{args.compile_args} {flags}",
        environment={
            **{
                f"PREDICATE_UNIT_{key}": str(value) for key, value in parameters.items()
            },
            "PREDICATE_UNIT_SEED": str(seed),
            "PREDICATE_UNIT_RANDOM_CYCLES": str(args.random_cycles),
            "PREDICATE_UNIT_CHECK_INTERNALS": "1",
            "PREDICATE_UNIT_HDL_ASSERTIONS": "1",
            "PREDICATE_UNIT_ASSERTION_PROBE": probe,
        },
    )


def assertion_probes(args, build, rtl):
    rows = []
    for index, (probe, name, reset) in enumerate(PROBES):
        result, log, results, _ = simulate(
            args,
            build / "assertion_probes" / f"{index:02d}",
            rtl,
            DEFAULTS | {"ASYNC_RESET": reset},
            args.seed,
            probe,
        )
        rejected = (
            result.returncode != 0
            and f"PREDICATE_UNIT_PROTOCOL: {name}" in log.read_text()
        )
        if results.exists():
            try:
                cases = ET.parse(results).findall(".//testcase")
                rejected &= (
                    len(cases) == 1
                    and cases[0].find("failure") is not None
                    and cases[0].get("name") == "PredicateTest"
                    and cases[0].get("classname") == "test_predicate_unit"
                )
            except ET.ParseError:
                rejected = False
        status = (
            "NOT_RUN"
            if license_unavailable(log.read_text())
            else "PASS"
            if rejected
            else "FAIL"
        )
        rows.append(
            {
                "probe": probe,
                "asynchronous_reset": reset,
                "expected_assertion": name,
                "status": status,
                "log": str(log),
            }
        )
        print("Assertion", probe, status, flush=True)
    return rows


def run_profile(task):
    args, build, rtl, index, name, p = task
    print("Running", name, flush=True)
    result, log, results, coverage = simulate(
        args, build / name, rtl, p, args.seed + index
    )
    row = {"name": name, "parameters": p, "status": "FAIL", "log": str(log)}
    try:
        if result.returncode:
            raise ValueError(f"make exited {result.returncode}")
        passed_test(results, "PredicateTest", "test_predicate_unit")
        data = json.loads(coverage.read_text())
        if (
            data["status"] != "PASS"
            or data["parameters"] != p
            or not data["goals"]
            or not all(data["goals"].values())
            or data["random_transactions"] != args.random_cycles
            or data["seed"] != args.seed + index
            or data["native_hdl_assertions"] != "PASS"
        ):
            raise ValueError("Coverage evidence mismatch")
        row.update(data, name=name, log=str(log), coverage=str(coverage))
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        row["error"] = str(error)
        if license_unavailable(log.read_text()):
            row["status"] = "NOT_RUN"
        print("\n".join(log.read_text().splitlines()[-22:]), flush=True)
    print(name, row["status"], flush=True)
    return row


def main():
    args = parse_args(
        "predicate_unit",
        __doc__,
        profiles=[name for name, _ in PROFILES],
        seed=20261022,
        rtl_category="building_blocks",
    )
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    output = build / "summary.json"
    output.unlink(missing_ok=True)
    summary = {
        "status": "NOT_RUN",
        "framework": "PyUVM",
        "simulator": args.sim,
        "profiles": [],
        "parameter_checks": [],
        "assertion_probes": [],
        "started_at_utc": datetime.now(UTC).isoformat(),
        "specification": "specs/building-blocks/mosaic-predicate-unit/README.md",
        "external_checks": dict.fromkeys(
            (
                "formal",
                "commercial_lint",
                "cdc",
                "rdc",
                "dft",
                "vc_lp",
                "technology_synthesis",
                "sequential_equivalence",
                "physical_timing",
                "physical_power",
                "mosaic_contracts",
            ),
            "NOT_RUN",
        ),
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["dependency_sha256"] = {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in DEPENDENCIES
        }
        summary["verification_sha256"] = verification_hashes(TEST_DIR)
        require_simulator(args)
        tasks = [
            (args, build, rtl, i, name, p)
            for i, (name, p) in enumerate(PROFILES)
            if not args.case or name in args.case
        ]
        jobs = int(os.getenv("PREDICATE_UNIT_JOBS", "4"))
        if not 1 <= jobs <= 32:
            raise ValueError("PREDICATE_UNIT_JOBS must be between 1 and 32")
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary["profiles"] = list(pool.map(run_profile, tasks))
        summary["parameter_checks"] = [
            parameter_guard(
                args,
                build,
                rtl,
                "predicate_unit",
                name,
                p,
                "predicate_unit_parameters_must_be_valid",
                dependencies=DEPENDENCIES,
            )
            for name, p in INVALID
        ]
        summary["assertion_probes"] = assertion_probes(args, build, rtl)
        complete = (
            len(summary["profiles"])
            == (len(set(args.case)) if args.case else len(PROFILES))
            and len(summary["parameter_checks"]) == len(INVALID)
            and len(summary["assertion_probes"]) == len(PROBES)
        )
        summary["status"] = campaign_status(
            (
                *summary["profiles"],
                *summary["parameter_checks"],
                *summary["assertion_probes"],
            ),
            complete,
        )
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(error, file=sys.stderr)
    finally:
        finish_summary(output, summary, "Predicate unit")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
