"""Run the vector reduction width/feature matrix and strict integration assertions."""

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
from vector_reduction.config import DEFAULTS

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(
    ROOT / f"src/rtl/{name}.sv"
    for name in (
        "building_blocks/scalar_alu_pkg",
        "building_blocks/vector_lane_pkg",
        "building_blocks/vector_reduction_pkg",
        "common/dff",
        "common/operand_isolation",
        "common/write_gate",
        "building_blocks/vector_lane_pipeline",
        "building_blocks/vector_reduction_tree",
    )
)
GEOMETRIES = (
    (1, 1, 1),
    (1, 2, 2),
    (1, 4, 3),
    (1, 8, 4),
    (2, 1, 2),
    (2, 2, 3),
    (2, 3, 4),
    (3, 3, 5),
    (3, 3, 13),
    (4, 4, 6),
    (4, 4, 16),
    (8, 4, 10),
    (8, 4, 32),
    (16, 4, 18),
    (16, 4, 32),
    (8, 8, 11),
    (8, 8, 32),
    (32, 4, 34),
    (32, 4, 64),
    (5, 5, 8),
    (4, 7, 7),
)
PROFILES = (
    *(
        (
            f"latency{l}_async{a}",
            DEFAULTS
            | {
                "ELEMENT_WIDTH": 1,
                "NUM_ELEMENTS": 3,
                "ACC_WIDTH": 4,
                "LATENCY": l,
                "ASYNC_RESET": a,
            },
        )
        for l, a in product(range(9), range(2))
    ),
    *(
        (
            f"e{e}_n{n}_a{a}_async{reset}",
            DEFAULTS
            | {"ELEMENT_WIDTH": e, "NUM_ELEMENTS": n, "ACC_WIDTH": a, "ASYNC_RESET": reset},
        )
        for (e, n, a), reset in product(GEOMETRIES, range(2))
    ),
    *(
        (
            f"features{s}{m}{l}_async{a}",
            DEFAULTS
            | {
                "ELEMENT_WIDTH": 2,
                "NUM_ELEMENTS": 3,
                "ACC_WIDTH": 7,
                "LATENCY": 2,
                "ASYNC_RESET": a,
                "SUPPORT_SUM": s,
                "SUPPORT_MINMAX": m,
                "SUPPORT_LOGICAL": l,
            },
        )
        for s, m, l, a in product(range(2), repeat=4)
    ),
    *(
        (
            f"custom_latency_async{a}",
            DEFAULTS
            | {
                "ELEMENT_WIDTH": 1,
                "NUM_ELEMENTS": 3,
                "ACC_WIDTH": 3,
                "LATENCY": 10,
                "MAX_LATENCY": 10,
                "ASYNC_RESET": a,
            },
        )
        for a in range(2)
    ),
)
INVALID = (
    *(
        (f"{key.lower()}_{label}", {key: value})
        for key in ("ELEMENT_WIDTH", "NUM_ELEMENTS", "ACC_WIDTH", "MAX_LATENCY")
        for label, value in (("zero", 0), ("negative", -1), ("x", "32'bx"), ("z", "32'bz"))
    ),
    ("accumulator_too_narrow", {"ACC_WIDTH": 9}),
    (
        "packed_width_overflow",
        {"ELEMENT_WIDTH": 536870800, "NUM_ELEMENTS": 8, "ACC_WIDTH": 536870803},
    ),
    ("tree_width_overflow", {"NUM_ELEMENTS": 536870911}),
    ("wide_count_overflow", {"NUM_ELEMENTS": "64'd4294967296"}),
    ("wide_element_overflow", {"ELEMENT_WIDTH": "64'd4294967296"}),
    ("pipeline_overflow", {"LATENCY": 2147483646, "MAX_LATENCY": 2147483646}),
    *(
        (f"{key.lower()}_{label}", {key: value})
        for key in ("SUPPORT_SUM", "SUPPORT_MINMAX", "SUPPORT_LOGICAL", "ASYNC_RESET")
        for label, value in (("two", 2), ("negative", -1), ("x", "32'bx"), ("z", "32'bz"))
    ),
    *(
        (f"latency_{label}", {"LATENCY": value})
        for label, value in (("negative", -1), ("too_long", 9), ("x", "32'bx"), ("z", "32'bz"))
    ),
    *(
        (f"{key.lower()}_{label}", {key: value})
        for key, wrong in (("OPCODE_WIDTH", 4), ("RESULT_FORMAT_WIDTH", 3))
        for label, value in (("wrong", wrong), ("x", "32'bx"), ("z", "32'bz"))
    ),
)
PROBES = tuple(
    (f"element:{k}:{state}", f"element {k}") for k in range(5) for state in "xz"
) + tuple(
    (f"{name}:0:{state}", name)
    for name in ("i_valid", "i_rstb", "i_clock_enable")
    for state in "xz"
)
PROBES += tuple(
    (f"{kind}:0:{state}", "element 0") for kind in ("opaque_and", "opaque_or") for state in "xz"
)

REUSED_VERIFICATION = tuple((ROOT / "src/val/building_blocks/vector_lane").glob("*.py")) + tuple(
    ROOT / "src/val/building_blocks" / path
    for path in (
        "scalar_alu/model.py",
        "scalar_alu/transaction.py",
        "multiplier/monitor.py",
        "multiplier/transaction.py",
    )
)


def verification_hashes(test_dir):
    return shared_verification_hashes(test_dir) | {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in REUSED_VERIFICATION
    }


def simulate(args, build, rtl, parameters, seed, probe=""):
    prefix = "-Pvector_reduction." if args.sim == "icarus" else "-pvalue+vector_reduction."
    flags = " ".join(shlex.quote(f"{prefix}{key}={value}") for key, value in parameters.items())
    return run_simulation(
        args,
        ROOT,
        TEST_DIR,
        "vector_reduction",
        "test_vector_reduction",
        "ReductionTest",
        build,
        " ".join(map(str, (*DEPENDENCIES, rtl))),
        parameters=parameters,
        compile_args=f"{args.compile_args} {flags}",
        environment={
            **{f"VECTOR_REDUCTION_{key}": str(value) for key, value in parameters.items()},
            "VECTOR_REDUCTION_SEED": str(seed),
            "VECTOR_REDUCTION_RANDOM_CYCLES": str(args.random_cycles),
            "VECTOR_REDUCTION_CHECK_INTERNALS": "1",
            "VECTOR_REDUCTION_HDL_ASSERTIONS": "1",
            "VECTOR_REDUCTION_ASSERTION_PROBE": probe,
        },
    )


def assertion_probes(args, build, rtl):
    rows = []
    for index, (probe, name) in enumerate(PROBES):
        result, log, results, _ = simulate(
            args,
            build / "assertion_probes" / f"{index:02d}",
            rtl,
            DEFAULTS
            | {
                "ELEMENT_WIDTH": 3,
                "NUM_ELEMENTS": 5,
                "ACC_WIDTH": 8,
                "LATENCY": 0 if probe.startswith("opaque_") else 1,
            },
            args.seed,
            probe,
        )
        rejected = (
            result.returncode != 0 and f"VECTOR_REDUCTION_PROTOCOL: {name}" in log.read_text()
        )
        if results.exists():
            try:
                cases = ET.parse(results).findall(".//testcase")
                rejected &= (
                    len(cases) == 1
                    and cases[0].find("failure") is not None
                    and cases[0].get("name") == "ReductionTest"
                    and cases[0].get("classname") == "test_vector_reduction"
                )
            except ET.ParseError:
                rejected = False
        status = (
            "NOT_RUN" if license_unavailable(log.read_text()) else "PASS" if rejected else "FAIL"
        )
        rows.append({"probe": probe, "expected_assertion": name, "status": status, "log": str(log)})
        print("Assertion", probe, status, flush=True)
    return rows


def run_profile(task):
    args, build, rtl, index, name, p = task
    print("Running", name, flush=True)
    result, log, results, coverage = simulate(args, build / name, rtl, p, args.seed + index)
    row = {"name": name, "parameters": p, "status": "FAIL", "log": str(log)}
    try:
        if result.returncode:
            raise ValueError(f"make exited {result.returncode}")
        passed_test(results, "ReductionTest", "test_vector_reduction")
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
        "vector_reduction",
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
        "specification": "specs/building-blocks/mosaic-vector-reduction/README.md",
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
        jobs = int(os.getenv("VECTOR_REDUCTION_JOBS", "4"))
        if not 1 <= jobs <= 32:
            raise ValueError("VECTOR_REDUCTION_JOBS must be between 1 and 32")
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary["profiles"] = list(pool.map(run_profile, tasks))
        summary["parameter_checks"] = [
            parameter_guard(
                args,
                build,
                rtl,
                "vector_reduction",
                name,
                p,
                "vector_reduction_parameters_must_be_valid",
                dependencies=DEPENDENCIES,
            )
            for name, p in INVALID
        ]
        summary["assertion_probes"] = assertion_probes(args, build, rtl)
        complete = (
            len(summary["profiles"]) == (len(set(args.case)) if args.case else len(PROFILES))
            and len(summary["parameter_checks"]) == len(INVALID)
            and len(summary["assertion_probes"]) == len(PROBES)
        )
        summary["status"] = campaign_status(
            (*summary["profiles"], *summary["parameter_checks"], *summary["assertion_probes"]),
            complete,
        )
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(error, file=sys.stderr)
    finally:
        finish_summary(output, summary, "Vector reduction")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
