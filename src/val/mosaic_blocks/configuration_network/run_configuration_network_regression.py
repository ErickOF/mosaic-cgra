"""Python-only parameter campaign for the production configuration network and PyUVM suite."""

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
from configuration_network.defaults import DEFAULTS
from configuration_network.dependencies import DEPENDENCIES as NAMES
from configuration_network.layout import (
    tables,
    dimensions,
    published_parameters,
    topology,
    endpoint,
)
from configuration_network.test_model import ModelTests
from configuration_network.adapter_contract import DEFAULTS as ADAPTER_DEFAULTS

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f"src/rtl/{name}.sv" for name in NAMES)


def profile(label, **overrides):
    p = DEFAULTS | overrides
    p.update(tables(p))
    return label, p


SMALL = dict(
    NUM_ENDPOINTS=4,
    NUM_TILE_ENDPOINTS=4,
    NUM_INFRA_ENDPOINTS=0,
    TRANSACTION_TIMEOUT_CYCLES=256,
    COMMIT_TIMEOUT_CYCLES=128,
)
PROFILES = (
    profile("default"),
    profile("small", **SMALL, CONTROL_PROTECTION=0),
    profile(
        "large",
        NUM_ENDPOINTS=68,
        NUM_TILE_ENDPOINTS=64,
        NUM_INFRA_ENDPOINTS=4,
        CONTROL_PROTECTION=0,
    ),
    profile(
        "single",
        NUM_ENDPOINTS=1,
        NUM_TILE_ENDPOINTS=1,
        NUM_INFRA_ENDPOINTS=0,
        TREE_BRANCH_FACTOR=2,
        MAX_OUTSTANDING_TRANSACTIONS=1,
        TRANSACTION_ID_WIDTH=1,
        CONTROL_PROTECTION=0,
        TRANSACTION_TIMEOUT_CYCLES=256,
        COMMIT_TIMEOUT_CYCLES=64,
    ),
    profile(
        "daisy",
        NUM_ENDPOINTS=6,
        NUM_TILE_ENDPOINTS=4,
        NUM_INFRA_ENDPOINTS=2,
        TOPOLOGY_PROFILE=0,
        TREE_BRANCH_FACTOR=2,
        CONTROL_PROTECTION=0,
        TRANSACTION_TIMEOUT_CYCLES=512,
        COMMIT_TIMEOUT_CYCLES=128,
    ),
    profile("row_column", **SMALL, TOPOLOGY_PROFILE=2),
    profile("binary", **SMALL, TREE_BRANCH_FACTOR=2),
    profile("ternary", **SMALL, TREE_BRANCH_FACTOR=3),
    profile("two_masters", **SMALL, NUM_MASTERS=2),
    profile("four_masters", **SMALL, NUM_MASTERS=4),
    profile(
        "flit8",
        **(SMALL | dict(TRANSACTION_TIMEOUT_CYCLES=1024)),
        CONFIG_FLIT_WIDTH=8,
        CONFIG_DATA_WIDTH=8,
        BYTE_STROBE_WIDTH=1,
        CONTROL_PROTECTION=0,
    ),
    profile(
        "flit32",
        **SMALL,
        CONFIG_FLIT_WIDTH=32,
        CONFIG_DATA_WIDTH=32,
        BYTE_STROBE_WIDTH=4,
    ),
    profile(
        "wide",
        **SMALL,
        CONFIG_FLIT_WIDTH=256,
        CONFIG_DATA_WIDTH=256,
        BYTE_STROBE_WIDTH=32,
    ),
    profile(
        "queues1",
        **SMALL,
        COMMAND_QUEUE_DEPTH=1,
        RESPONSE_QUEUE_DEPTH=1,
        BRANCH_BUFFER_DEPTH=1,
        ENDPOINT_QUEUE_DEPTH=1,
        MAX_OUTSTANDING_TRANSACTIONS=1,
    ),
    profile(
        "queues_deep",
        **SMALL,
        BRANCH_BUFFER_DEPTH=4,
        ENDPOINT_QUEUE_DEPTH=4,
        MAX_OUTSTANDING_TRANSACTIONS=8,
    ),
    profile("sparse", **SMALL, ENDPOINT_PRESENT_MASK=0b1101),
    profile(
        "permuted_ids", **SMALL, ENDPOINT_ID_TABLE=7 | (2 << 8) | (9 << 16) | (1 << 24)
    ),
    profile("control_ecc", **SMALL, CONTROL_PROTECTION=2, ASYNC_RESET=1),
    profile(
        "features_off",
        **SMALL,
        CONTROL_PROTECTION=0,
        ENABLE_PACKET_CRC=0,
        SUPPORT_READBACK=0,
        SUPPORT_MULTICAST=0,
        ASYNC_RESET=1,
    ),
)
POSITIVE = (
    "NUM_MASTERS",
    "NUM_ENDPOINTS",
    "TREE_BRANCH_FACTOR",
    "CONFIG_DATA_WIDTH",
    "CONFIG_FLIT_WIDTH",
    "ENDPOINT_ID_WIDTH",
    "ENDPOINT_TYPE_WIDTH",
    "COMMAND_WIDTH",
    "CONTEXT_ID_WIDTH",
    "CONTEXT_VERSION_WIDTH",
    "OWNER_ID_WIDTH",
    "KERNEL_ID_WIDTH",
    "PACKAGE_ID_WIDTH",
    "CONFIG_EPOCH_WIDTH",
    "TRANSACTION_ID_WIDTH",
    "TAG_WIDTH",
    "WORD_INDEX_WIDTH",
    "BYTE_STROBE_WIDTH",
    "COMMAND_QUEUE_DEPTH",
    "RESPONSE_QUEUE_DEPTH",
    "BRANCH_BUFFER_DEPTH",
    "ENDPOINT_QUEUE_DEPTH",
    "MAX_OUTSTANDING_TRANSACTIONS",
    "TRANSACTION_TIMEOUT_CYCLES",
    "COMMIT_TIMEOUT_CYCLES",
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
            "SUPPORT_MULTICAST",
            "SUPPORT_READBACK",
            "ENABLE_PACKET_CRC",
            "CONTROL_PROTECTION",
            "ASYNC_RESET",
        )
    ),
    ("unsupported_noc", dict(TOPOLOGY_PROFILE=3)),
    ("unproved_replay", dict(SUPPORT_PACKET_RETRY=1)),
    ("unsupported_cdc", dict(SUPPORT_ASYNC_ENDPOINTS=1)),
    ("ordering", dict(RESPONSE_ORDERING=1)),
    ("endpoint_sum", dict(NUM_TILE_ENDPOINTS=15)),
    ("endpoint_limit", dict(NUM_ENDPOINTS=129)),
    ("masters_limit", dict(NUM_MASTERS=5)),
    ("branch_limit", dict(TREE_BRANCH_FACTOR=5)),
    ("data_alignment", dict(CONFIG_DATA_WIDTH=65)),
    ("flit_alignment", dict(CONFIG_FLIT_WIDTH=63)),
    ("strobe_width", dict(BYTE_STROBE_WIDTH=7)),
    ("packet_crc", dict(PACKET_CRC_WIDTH=16)),
    ("image_crc", dict(IMAGE_CRC_WIDTH=16)),
    ("status_width", dict(STATUS_WIDTH=3)),
    ("error_width", dict(ERROR_CODE_WIDTH=7)),
    ("endpoint_id_capacity", dict(ENDPOINT_ID_WIDTH=1)),
    ("transaction_id_capacity", dict(TRANSACTION_ID_WIDTH=1)),
    ("duplicate_ids", dict(ENDPOINT_ID_TABLE="160'b0")),
    ("present_width", dict(ENDPOINT_PRESENT_MASK="1'b1")),
    ("unsafe_clock_domain", dict(ENDPOINT_CLOCK_DOMAIN_TABLE="20'b1")),
    ("unsafe_commit_domain", dict(COMMIT_DOMAIN_TABLE="20'b1")),
    ("empty_contexts", dict(ENDPOINT_CONTEXT_DEPTH_TABLE="640'b0")),
    ("empty_words", dict(ENDPOINT_WORD_COUNT_TABLE="640'b0")),
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
    from configuration_network.defaults import TABLE_WIDTHS

    for k, width in TABLE_WIDTHS.items():
        values[k] = f"{eval(width, {}, a)}'h{p[k]:x}"
    prefix = (
        "-Pconfiguration_network."
        if args.sim == "icarus"
        else "-pvalue+configuration_network."
    )
    flags = " ".join(shlex.quote(f"{prefix}{k}={v}") for k, v in values.items())
    result, log, results, coverage = run_simulation(
        args,
        ROOT,
        TEST_DIR,
        "configuration_network",
        "test_configuration_network",
        "ConfigurationNetworkTest",
        build / name,
        " ".join(map(str, (*DEPENDENCIES, rtl))),
        parameters=published_parameters(p),
        compile_args=f"{args.compile_args} {flags}",
        environment={
            **{
                f"CONFIGURATION_NETWORK_{k}": hex(v) if k in TABLE_WIDTHS else str(v)
                for k, v in p.items()
            },
            "CONFIGURATION_NETWORK_SEED": str(args.seed + index),
            "CONFIGURATION_NETWORK_RANDOM_CYCLES": str(args.random_cycles),
        },
    )
    row = dict(
        name=name, parameters=published_parameters(p), status="FAIL", log=str(log)
    )
    try:
        if result.returncode:
            raise ValueError(f"make exited {result.returncode}")
        passed_test(results, "ConfigurationNetworkTest", "test_configuration_network")
        data = json.loads(coverage.read_text())
        contract = json.loads(coverage.with_name("contract.json").read_text())
        if (
            data["status"] != "PASS"
            or data["parameters"] != published_parameters(p)
            or not data["goals"]
            or not all(data["goals"].values())
            or data["seed"] != args.seed + index
            or data["random_cycles"] != args.random_cycles
            or contract["topology"] != topology(p)
            or contract["parameters"] != published_parameters(p)
            or contract["endpoints"] != [endpoint(p, e) for e in range(a["NE"])]
            or contract["packet"]["command_packet_bits"] != a["CP"]
            or contract["packet"]["response_packet_bits"] != a["RP"]
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


def run_adapter(task):
    args, build, index, protection = task
    name = f"tile_adapter_{protection}"
    p = ADAPTER_DEFAULTS | dict(
        CONTROL_PROTECTION=protection, ASYNC_RESET=int(protection == 2)
    )
    top = "configuration_network_tile_adapter"
    prefix = f"-P{top}." if args.sim == "icarus" else f"-pvalue+{top}."
    flags = " ".join(f"{prefix}{k}={v}" for k, v in p.items())
    result, log, results, coverage = run_simulation(
        args,
        ROOT,
        TEST_DIR,
        top,
        "test_configuration_network_adapter",
        "ConfigurationAdapterTest",
        build / name,
        " ".join(map(str, DEPENDENCIES)),
        parameters=published_parameters(p),
        compile_args=f"{args.compile_args} {flags}",
        environment={
            **{f"CONFIGURATION_ADAPTER_{k}": str(v) for k, v in p.items()},
            "CONFIGURATION_ADAPTER_SEED": str(args.seed + index),
        },
    )
    row = dict(name=name, status="FAIL", log=str(log))
    try:
        if result.returncode:
            raise ValueError(f"make exited {result.returncode}")
        passed_test(
            results, "ConfigurationAdapterTest", "test_configuration_network_adapter"
        )
        data = json.loads(coverage.read_text())
        if (
            data["status"] != "PASS"
            or data["parameters"] != published_parameters(p)
            or not all(data["goals"].values())
        ):
            raise ValueError("Adapter coverage mismatch")
        row.update(data, name=name, coverage=str(coverage))
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        row["error"] = str(error)
        print("\n".join(log.read_text().splitlines()[-25:]), flush=True)
    print(name, row["status"], flush=True)
    return row


ADAPTER_INVALID = (
    ("data_alignment", dict(CONFIG_DATA_WIDTH=65)),
    ("contexts_zero", dict(CONTEXT_DEPTH=0)),
    ("contexts_unknown", dict(CONTEXT_DEPTH="32'bx")),
    ("words_zero", dict(CONFIG_WORD_COUNT=0)),
    ("protection_invalid", dict(CONTROL_PROTECTION=3)),
    ("reset_invalid", dict(ASYNC_RESET=2)),
    ("context_capacity", dict(CONTEXT_ID_WIDTH=1)),
    ("word_capacity", dict(WORD_INDEX_WIDTH=1)),
    ("tile_id", dict(TILE_ID=65536)),
)


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sim", choices=("vcs", "icarus"), default="vcs")
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument(
        "--rtl",
        type=Path,
        default=ROOT / "src/rtl/mosaic_blocks/configuration_network.sv",
    )
    parser.add_argument("--seed", type=int, default=20261026)
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
        jobs = int(
            os.getenv(
                "CONFIGURATION_NETWORK_JOBS", "4" if args.sim == "icarus" else "1"
            )
        )
        if not 1 <= jobs <= 32:
            raise ValueError("CONFIGURATION_NETWORK_JOBS must be between 1 and 32")
        tasks = [
            (args, build, rtl, i, n, p)
            for i, (n, p) in enumerate(PROFILES)
            if not args.case or n in args.case
        ]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary["profiles"] = list(pool.map(run_profile, tasks))
            summary["adapters"] = list(
                pool.map(
                    run_adapter, [(args, build, len(tasks) + i, i) for i in range(3)]
                )
            )
            summary["adapter_parameter_checks"] = list(
                pool.map(
                    lambda case: parameter_guard(
                        args,
                        build / "adapter_guards",
                        ROOT
                        / "src/rtl/mosaic_blocks/configuration_network_tile_adapter.sv",
                        "configuration_network_tile_adapter",
                        case[0],
                        case[1],
                        "configuration_network_tile_adapter_parameters_must_be_valid",
                        dependencies=DEPENDENCIES[:-1],
                    ),
                    ADAPTER_INVALID,
                )
            )
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary["parameter_checks"] = list(
                pool.map(
                    lambda case: parameter_guard(
                        args,
                        build,
                        rtl,
                        "configuration_network",
                        case[0],
                        case[1],
                        "configuration_network_parameters_must_be_valid",
                        dependencies=DEPENDENCIES,
                    ),
                    INVALID,
                )
            )
        summary["sources_stable"] = before == hashes(rtl)
        complete = len(summary["profiles"]) == (
            len(set(args.case)) if args.case else len(PROFILES)
        )
        summary["status"] = campaign_status(
            (
                *summary["profiles"],
                *summary["parameter_checks"],
                *summary["adapters"],
                *summary["adapter_parameter_checks"],
                summary["python_model_checks"],
            ),
            complete and summary["sources_stable"],
        )
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
    finally:
        finish_summary(build / "summary.json", summary, "Configuration network")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
