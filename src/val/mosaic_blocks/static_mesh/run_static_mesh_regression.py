"""Python-only parameter campaign for the production static mesh and PyUVM suite."""

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
from static_mesh.defaults import DEFAULTS
from static_mesh.dependencies import DEPENDENCIES as NAMES
from static_mesh.topology import physical, dimensions
from static_mesh.test_model import ModelTests

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


PROFILES = (
    profile("default"),
    profile("small", MESH_ROWS=2, MESH_COLS=2),
    profile("large", MESH_ROWS=8, MESH_COLS=8, CONFIG_DATA_WIDTH=256),
    profile(
        "minimal16",
        MESH_ROWS=2,
        MESH_COLS=3,
        LINK_DATA_WIDTH=16,
        CONNECTIVITY_PROFILE=0,
        LOCAL_TX_PORTS=1,
        LOCAL_RX_PORTS=1,
        CONTEXT_DEPTH=1,
    ),
    profile(
        "wide128",
        MESH_ROWS=2,
        MESH_COLS=2,
        LINK_DATA_WIDTH=128,
        LINK_METADATA_WIDTH=96,
        LOCAL_TX_PORTS=4,
        LOCAL_RX_PORTS=4,
        CONTEXT_DEPTH=8,
        BOUNDARY_BUFFER_DEPTH=8,
    ),
    profile(
        "dual_channels",
        MESH_ROWS=2,
        MESH_COLS=2,
        CHANNELS_PER_DIRECTION=2,
        LOCAL_TX_PORTS=4,
        LOCAL_RX_PORTS=4,
        LINK_DATA_WIDTH=64,
        LINK_METADATA_WIDTH=96,
        CONNECTIVITY_PROFILE=2,
        BOUNDARY_BUFFER_DEPTH=2,
    ),
    profile("sparse", NODE_PRESENT_MASK=0xFFDF, BOUNDARY_BUFFER_DEPTH=4),
    profile("directed", MESH_ROWS=2, MESH_COLS=2, LINK_PRESENT_MASK=0xFFFFFE),
    profile(
        "no_boundary",
        MESH_ROWS=2,
        MESH_COLS=2,
        EXPOSE_BOUNDARY_PORTS=0,
        SUPPORT_MULTICAST=0,
        SUPPORT_LINK_EXCLUSION=0,
    ),
    profile(
        "single_node",
        MESH_ROWS=1,
        MESH_COLS=1,
        EXPOSE_BOUNDARY_PORTS=0,
        CONFIG_DATA_WIDTH=32,
        LINK_EPOCH_WIDTH=1,
    ),
    profile(
        "scheduled_wire",
        MESH_ROWS=2,
        MESH_COLS=2,
        FLOW_PROFILE=1,
        BOUNDARY_BUFFER_DEPTH=0,
        SCHEDULE_PERIOD_MAX=8,
    ),
    profile(
        "scheduled_queue",
        MESH_ROWS=2,
        MESH_COLS=2,
        FLOW_PROFILE=1,
        BOUNDARY_BUFFER_DEPTH=2,
        SCHEDULE_PERIOD_MAX=16,
    ),
    profile("parity", MESH_ROWS=2, MESH_COLS=2, ENABLE_LINK_PARITY=1),
    profile("control_parity", MESH_ROWS=2, MESH_COLS=2, CONTROL_PROTECTION=1, ASYNC_RESET=1),
    profile("control_ecc", MESH_ROWS=2, MESH_COLS=2, CONTROL_PROTECTION=2, ENABLE_LINK_PARITY=1),
    profile(
        "features_off",
        MESH_ROWS=2,
        MESH_COLS=2,
        CHECK_CONTEXT=0,
        SUPPORT_MULTICAST=0,
        SUPPORT_LINK_EXCLUSION=0,
        ASYNC_RESET=1,
    ),
)
POSITIVE = (
    "MESH_ROWS",
    "MESH_COLS",
    "CHANNELS_PER_DIRECTION",
    "LOCAL_TX_PORTS",
    "LOCAL_RX_PORTS",
    "LINK_DATA_WIDTH",
    "LINK_METADATA_WIDTH",
    "CONTEXT_DEPTH",
    "CONFIG_DATA_WIDTH",
    "CONTEXT_ID_WIDTH",
    "CONTEXT_VERSION_WIDTH",
    "KERNEL_ID_WIDTH",
    "LINK_EPOCH_WIDTH",
    "MAX_MULTICAST_FANOUT",
    "MAX_READY_COMBINATIONAL_NODES",
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
            "CHECK_CONTEXT",
            "ENABLE_LINK_PARITY",
            "SUPPORT_LINK_EXCLUSION",
            "ASYNC_RESET",
            "CONNECTIVITY_PROFILE",
            "CONTROL_PROTECTION",
            "FLOW_PROFILE",
        )
    ),
    ("rows_limit", dict(MESH_ROWS=9)),
    ("columns_limit", dict(MESH_COLS=9)),
    ("channel_limit", dict(CHANNELS_PER_DIRECTION=5)),
    ("data_alignment", dict(LINK_DATA_WIDTH=17)),
    ("metadata_contract", dict(LINK_METADATA_WIDTH=32)),
    ("metadata_alignment", dict(LINK_METADATA_WIDTH=65)),
    ("config_alignment", dict(CONFIG_DATA_WIDTH=9)),
    ("context_address", dict(CONTEXT_ID_WIDTH=1)),
    ("proof_width", dict(ROUTE_PROOF_ID_WIDTH=16)),
    ("checksum_width", dict(CONTEXT_CHECKSUM_WIDTH=16)),
    ("boundary_negative", dict(BOUNDARY_BUFFER_DEPTH=-1)),
    ("boundary_limit", dict(BOUNDARY_BUFFER_DEPTH=9)),
    ("elastic_unbuffered_boundary", dict(BOUNDARY_BUFFER_DEPTH=0)),
    ("uncharacterized_bypass", dict(MAX_COMBINATIONAL_HOPS=1)),
    ("fanout_limit", dict(MAX_MULTICAST_FANOUT=7)),
    ("period_limit", dict(SCHEDULE_PERIOD_MAX=257)),
    ("node_mask_width", dict(NODE_PRESENT_MASK="1'b1")),
    ("link_mask_width", dict(LINK_PRESENT_MASK="1'b1")),
    ("connectivity_mask_width", dict(NODE_CONNECTIVITY_MASKS="1'b1")),
)


def hashes(rtl):
    return dict(
        rtl_sha256=hashlib.sha256(rtl.read_bytes()).hexdigest(),
        dependency_sha256={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in DEPENDENCIES
        },
        verification_sha256=verification_hashes(TEST_DIR),
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
    prefix = "-Pstatic_mesh." if args.sim == "icarus" else "-pvalue+static_mesh."
    flags = " ".join(shlex.quote(f"{prefix}{k}={v}") for k, v in values.items())
    result, log, results, coverage = run_simulation(
        args,
        ROOT,
        TEST_DIR,
        "static_mesh",
        "test_static_mesh",
        "StaticMeshTest",
        build / name,
        " ".join(map(str, (*DEPENDENCIES, rtl))),
        parameters=p,
        compile_args=f"{args.compile_args} {flags}",
        environment={
            **{f"STATIC_MESH_{k}": str(v) for k, v in p.items()},
            "STATIC_MESH_SEED": str(args.seed + index),
            "STATIC_MESH_RANDOM_CYCLES": str(args.random_cycles),
        },
    )
    row = dict(name=name, parameters=p, status="FAIL", log=str(log))
    try:
        if result.returncode:
            raise ValueError(f"make exited {result.returncode}")
        passed_test(results, "StaticMeshTest", "test_static_mesh")
        data = json.loads(coverage.read_text())
        contract = json.loads(coverage.with_name("contract.json").read_text())
        if (
            data["status"] != "PASS"
            or data["parameters"] != p
            or not data["goals"]
            or not all(data["goals"].values())
            or data["seed"] != args.seed + index
            or data["random_cycles"] != args.random_cycles
            or not contract["route_images"]
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
    parser.add_argument("--rtl", type=Path, default=ROOT / "src/rtl/mosaic_blocks/static_mesh.sv")
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
        jobs = int(os.getenv("STATIC_MESH_JOBS", "4" if args.sim == "icarus" else "1"))
        if not 1 <= jobs <= 32:
            raise ValueError("STATIC_MESH_JOBS must be between 1 and 32")
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
                        "static_mesh",
                        case[0],
                        case[1],
                        "static_mesh_parameters_must_be_valid",
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
        finish_summary(build / "summary.json", summary, "Static mesh")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
