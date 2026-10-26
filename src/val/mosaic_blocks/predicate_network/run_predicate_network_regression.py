"""Python-only parameter campaign for the production predicate network and PyUVM suite."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mosaic_uvm.regression import (
    campaign_status,
    finish_summary,
    license_unavailable,
    parameter_guard,
    passed_test,
    require_simulator,
    run_simulation,
    verification_hashes,
)
from predicate_network.defaults import DEFAULTS
from predicate_network.dependencies import DEPENDENCIES as NAMES
from predicate_network.topology import physical, dimensions
from predicate_network.test_model import ModelTests

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f"src/rtl/{name}.sv" for name in NAMES)


def profile(label, **overrides):
    p = DEFAULTS | overrides
    g = physical(p)
    p.update(
        NODE_PRESENT_MASK=g["nodes"],
        LINK_PRESENT_MASK=g["mask"],
        NODE_CONNECTIVITY_MASKS=g["connectivity"],
    )
    return label, p


SMALL = dict(NETWORK_ROWS=2, NETWORK_COLS=2, MAX_TREE_DESTINATIONS=4, SCHEDULE_PERIOD_MAX=16)
PROFILES = (
    profile("default"),
    profile(
        "single_node",
        NETWORK_ROWS=1,
        NETWORK_COLS=1,
        MAX_TREE_DESTINATIONS=1,
        SCHEDULE_PERIOD_MAX=8,
    ),
    profile("four_local_ports", **SMALL, LOCAL_TX_PORTS=4, LOCAL_RX_PORTS=4),
    profile("small", **SMALL),
    profile("bounded_tree", **(SMALL | dict(MAX_TREE_DESTINATIONS=3))),
    profile("large", NETWORK_ROWS=8, NETWORK_COLS=8, MAX_TREE_DESTINATIONS=64),
    profile(
        "scalar_minimal", **SMALL, PREDICATE_WIDTH=1, CONNECTIVITY_PROFILE=0, SUPPORT_MULTICAST=0
    ),
    profile("lanes2", **SMALL, PREDICATE_WIDTH=2),
    profile("lanes4", **SMALL, PREDICATE_WIDTH=4),
    profile("lanes16", **SMALL, PREDICATE_WIDTH=16),
    profile("broadcast", **SMALL, CONNECTIVITY_PROFILE=2, MAX_MULTICAST_FANOUT=5),
    profile("dual_channels", **SMALL, CHANNELS_PER_DIRECTION=2, LOCAL_TX_PORTS=2, LOCAL_RX_PORTS=2),
    profile("boundary", **SMALL, EXPOSE_BOUNDARY_PORTS=1),
    profile(
        "boundary_dual",
        **SMALL,
        EXPOSE_BOUNDARY_PORTS=1,
        CHANNELS_PER_DIRECTION=2,
        LOCAL_TX_PORTS=2,
        LOCAL_RX_PORTS=2,
    ),
    profile("sparse", NODE_PRESENT_MASK=0xFFDF),
    profile("directed", **SMALL, LINK_PRESENT_MASK=0xFE),
    profile("no_multicast", **SMALL, SUPPORT_MULTICAST=0),
    profile("no_schedule", **SMALL, SUPPORT_SCHEDULE_CHECK=0),
    profile("no_parity", **SMALL, ENABLE_LINK_PARITY=0),
    profile("control_parity", **SMALL, CONTROL_PROTECTION=1, ASYNC_RESET=1),
    profile("control_ecc", **SMALL, CONTROL_PROTECTION=2),
    profile(
        "opaque_metadata",
        **SMALL,
        PREDICATE_METADATA_WIDTH=96,
        PRODUCER_ID_WIDTH=16,
        ASSOCIATION_TAG_WIDTH=16,
        ROUTE_PROOF_ID_WIDTH=64,
    ),
    profile(
        "features_off",
        **SMALL,
        SUPPORT_SCHEDULE_CHECK=0,
        SUPPORT_LINK_EXCLUSION=0,
        SUPPORT_MULTICAST=0,
        ENABLE_LINK_PARITY=0,
        CHECK_CONTEXT=0,
        ASYNC_RESET=1,
    ),
)
POSITIVE = (
    "NETWORK_ROWS",
    "NETWORK_COLS",
    "CHANNELS_PER_DIRECTION",
    "LOCAL_TX_PORTS",
    "LOCAL_RX_PORTS",
    "PREDICATE_WIDTH",
    "PREDICATE_METADATA_WIDTH",
    "CONTEXT_ID_WIDTH",
    "CONTEXT_VERSION_WIDTH",
    "KERNEL_ID_WIDTH",
    "ASSOCIATION_TAG_WIDTH",
    "PRODUCER_ID_WIDTH",
    "PREDICATE_EPOCH_WIDTH",
    "PREDICATE_CLASS_WIDTH",
    "PREDICATE_ERROR_WIDTH",
    "ROUTE_PROOF_ID_WIDTH",
    "MAX_MULTICAST_FANOUT",
    "MAX_TREE_DESTINATIONS",
    "SCHEDULE_PERIOD_MAX",
)
INVALID = (
    *(
        (f"{k.lower()}_{label}", {k: v})
        for k in POSITIVE
        for label, v in (("zero", 0), ("negative", -1), ("unknown", "32'bx"))
    ),
    *(
        (f"{k.lower()}_invalid", {k: 3})
        for k in (
            "EXPOSE_BOUNDARY_PORTS",
            "SUPPORT_MULTICAST",
            "SUPPORT_SCHEDULE_CHECK",
            "CHECK_CONTEXT",
            "ENABLE_LINK_PARITY",
            "SUPPORT_LINK_EXCLUSION",
            "ASYNC_RESET",
            "CONNECTIVITY_PROFILE",
            "CONTROL_PROTECTION",
        )
    ),
    ("rows_limit", dict(NETWORK_ROWS=9)),
    ("columns_limit", dict(NETWORK_COLS=9)),
    ("channels_limit", dict(CHANNELS_PER_DIRECTION=3)),
    ("ports_limit", dict(LOCAL_RX_PORTS=5)),
    ("predicate_limit", dict(PREDICATE_WIDTH=17)),
    ("metadata_limit", dict(PREDICATE_METADATA_WIDTH=520)),
    ("metadata_contract", dict(PREDICATE_METADATA_WIDTH=56)),
    ("metadata_alignment", dict(PREDICATE_METADATA_WIDTH=65)),
    ("proof_width", dict(ROUTE_PROOF_ID_WIDTH=16)),
    ("class_width", dict(PREDICATE_CLASS_WIDTH=1)),
    ("producer_address", dict(PRODUCER_ID_WIDTH=1)),
    ("fanout_limit", dict(MAX_MULTICAST_FANOUT=6)),
    ("tree_limit", dict(MAX_TREE_DESTINATIONS=17)),
    ("period_limit", dict(SCHEDULE_PERIOD_MAX=257)),
    ("minimal_vector", dict(CONNECTIVITY_PROFILE=0, SUPPORT_MULTICAST=0)),
    ("minimal_multicast", dict(CONNECTIVITY_PROFILE=0, PREDICATE_WIDTH=1)),
    ("node_mask_width", dict(NODE_PRESENT_MASK="1'b1")),
    ("link_mask_width", dict(LINK_PRESENT_MASK="1'b1")),
    ("connectivity_mask_width", dict(NODE_CONNECTIVITY_MASKS="1'b1")),
    ("absent_node_link", dict(NODE_PRESENT_MASK="16'hfffe", LINK_PRESENT_MASK="48'hffffffffffff")),
)


def hashes(rtl):
    return dict(
        rtl_sha256=hashlib.sha256(rtl.read_bytes()).hexdigest(),
        dependency_sha256={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in DEPENDENCIES
        },
        verification_sha256=verification_hashes(TEST_DIR),
        reused_python_sha256=verification_hashes(TEST_DIR.parent / "static_mesh"),
    )


def run_profile(task):
    args, build, rtl, index, name, p = task
    print("Running", name, flush=True)
    a = dimensions(p)
    values = p.copy()
    for k, width in (
        ("NODE_PRESENT_MASK", a["N"]),
        ("LINK_PRESENT_MASK", a["LB"]),
        ("NODE_CONNECTIVITY_MASKS", a["N"] * a["O"] * a["I"]),
    ):
        values[k] = f"{width}'d{p[k]}"
    prefix = "-Ppredicate_network." if args.sim == "icarus" else "-pvalue+predicate_network."
    flags = " ".join(shlex.quote(f"{prefix}{k}={v}") for k, v in values.items())
    result, log, results, coverage = run_simulation(
        args,
        ROOT,
        TEST_DIR,
        "predicate_network",
        "test_predicate_network",
        "PredicateNetworkTest",
        build / name,
        " ".join(map(str, (*DEPENDENCIES, rtl))),
        parameters=p,
        compile_args=f"{args.compile_args} {flags}",
        environment={
            **{f"PREDICATE_NETWORK_{k}": str(v) for k, v in p.items()},
            "PREDICATE_NETWORK_SEED": str(args.seed + index),
            "PREDICATE_NETWORK_RANDOM_CYCLES": str(args.random_cycles),
        },
    )
    row = dict(name=name, parameters=p, status="FAIL", log=str(log))
    try:
        if result.returncode:
            raise ValueError(f"make exited {result.returncode}")
        passed_test(results, "PredicateNetworkTest", "test_predicate_network")
        data = json.loads(coverage.read_text())
        contract = json.loads(coverage.with_name("contract.json").read_text())
        if (
            data["status"] != "PASS"
            or data["parameters"] != p
            or not data["goals"]
            or not all(data["goals"].values())
            or data["seed"] != args.seed + index
            or data["random_cycles"] != args.random_cycles
            or not contract["routes"]
            or data["hdl_assertions"] != "NOT_RUN"
        ):
            raise ValueError("Coverage or contract mismatch")
        row.update(data, name=name, coverage=str(coverage), log=str(log))
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        row["error"] = str(error)
        if license_unavailable(log.read_text()):
            row["status"] = "NOT_RUN"
        print("\n".join(log.read_text().splitlines()[-25:]), flush=True)
    print(name, row["status"], flush=True)
    return row


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sim", choices=("vcs", "icarus"), default="vcs")
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument(
        "--rtl", type=Path, default=ROOT / "src/rtl/mosaic_blocks/predicate_network.sv"
    )
    parser.add_argument("--seed", type=int, default=20261025)
    parser.add_argument("--random-cycles", type=int, default=1000)
    parser.add_argument("--compile-args", default="")
    parser.add_argument("--sim-args", default="")
    parser.add_argument("--sim-bin-dir", type=Path)
    parser.add_argument("--make", default="make")
    parser.add_argument("--case", action="append", choices=[n for n, _ in PROFILES])
    args = parser.parse_args()
    if args.random_cycles < 1:
        parser.error("--random-cycles must be positive")
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary = dict(
        status="NOT_RUN",
        framework="PyUVM",
        simulator=args.sim,
        profiles=[],
        parameter_checks=[],
        validation_mode="Python-only",
        hdl_assertions="NOT_RUN",
        synthesis="Design Compiler (deferred)",
        started_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    try:
        before = hashes(rtl)
        summary.update(before)
        with (build / "python_model_tests.log").open("w") as log:
            result = unittest.TextTestRunner(stream=log).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(ModelTests)
            )
        summary["python_model_checks"] = dict(
            status="PASS" if result.wasSuccessful() else "FAIL", tests=result.testsRun
        )
        if not result.wasSuccessful():
            raise ValueError("Python oracle checks failed")
        require_simulator(args)
        jobs = int(os.getenv("PREDICATE_NETWORK_JOBS", "4" if args.sim == "icarus" else "1"))
        if not 1 <= jobs <= 32:
            raise ValueError("PREDICATE_NETWORK_JOBS must be between 1 and 32")
        tasks = [
            (args, build, rtl, i, n, p)
            for i, (n, p) in enumerate(PROFILES)
            if not args.case or n in args.case
        ]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary["profiles"] = list(pool.map(run_profile, tasks))
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary["parameter_checks"] = list(
                pool.map(
                    lambda case: parameter_guard(
                        args,
                        build,
                        rtl,
                        "predicate_network",
                        case[0],
                        case[1],
                        "predicate_network_parameters_must_be_valid",
                        dependencies=DEPENDENCIES,
                    ),
                    INVALID,
                )
            )
        summary["sources_stable"] = before == hashes(rtl)
        complete = len(summary["profiles"]) == (len(set(args.case)) if args.case else len(PROFILES))
        summary["status"] = campaign_status(
            (*summary["profiles"], *summary["parameter_checks"], summary["python_model_checks"]),
            complete and summary["sources_stable"],
        )
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
    finally:
        finish_summary(build / "summary.json", summary, "Predicate network")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
