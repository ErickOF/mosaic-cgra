"""Run the DFF specification matrix through the existing PyUVM Make flow."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import shlex
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from mosaic_uvm.regression import (
    finish_summary, parameter_guard, parse_args, passed_test, require_simulator, run_simulation, verification_hashes,
)

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
# The first seven profiles are recommended by the specification. Additional
# profiles cross both reset modes with both enable branches and reset patterns.
PROFILES = (
    ("single_bit_sync", 1, 0, 1, 0),
    ("single_bit_async", 1, 1, 1, 0),
    ("byte_register", 8, 0, 1, 0),
    ("scalar_register", 32, 0, 1, 0),
    ("vector_register", 128, 0, 1, 0),
    ("always_enabled", 32, 0, 0, 0),
    ("nonzero_reset", 32, 1, 1, 0x5A5AA5A5),
    ("async_always_enabled", 32, 1, 0, 0xA55A5AA5),
    ("sync_nonzero_reset", 8, 0, 1, 0xA5),
    ("minimum_nonzero_reset", 1, 1, 0, 1),
    ("extended_always_enabled", 128, 0, 0, 0),
)


def parameter_literal(name: str, value: int, width: int) -> str:
    """Give reset patterns and static booleans exactly their declared widths."""
    if name == "RESET_VALUE":
        return f"{width}'h{value:x}"
    if name in ("ASYNC_RESET", "HAS_ENABLE"):
        return f"1'b{value}"
    return str(value)


def check_invalid_width(args, build: Path, rtl: Path) -> dict:
    report = parameter_guard(args, build, rtl, "dff", "zero_width", {"WIDTH": 0},
                           "WIDTH must be greater than zero",
                           wrapper_source=(
        '`timescale 1ns/1ps\nmodule dff_invalid_width;\n'
        'dff #(.WIDTH(0)) dut (.i_clk(1\'b0), .i_rstb(1\'b1), '
        '.i_enable(1\'b0), .i_d(2\'b00), .o_q());\n'
        'initial begin #1; $fatal(1, "Invalid width was accepted"); end\nendmodule\n'
    ), allow_startup=True)
    report["strict_elaboration_validation"] = "BLOCKED"
    if report["status"] == "PASS" and report["stage"] != "simulation_startup":
        report["status"] = "FAIL"
    return report


def main() -> int:
    args = parse_args('dff', __doc__, profiles=[profile[0] for profile in PROFILES], seed=20261010)
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    summary = {
        "status": "NOT_RUN", "framework": "PyUVM", "simulator": args.sim,
        "scope": "selected_profiles" if args.case else "recommended_matrix_with_branch_crosses",
        "specification": "specs/common/mosaic-dff/README.md",
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "rtl": str(rtl),
        "profiles": [], "parameter_checks": [],
        "specification_gaps": {
            "strict_elaboration_parameter_validation": "BLOCKED",
            "reason": "WIDTH=0 uses a time-zero fatal; typed RESET_VALUE permits implicit resizing",
        },
        "external_checks": dict.fromkeys((
            "formal", "hdl_sva", "commercial_lint", "cdc", "rdc", "dft", "low_power",
            "synthesis", "physical_timing", "physical_power",
        ), "NOT_RUN"),
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = verification_hashes(TEST_DIR)
        require_simulator(args)
        summary["status"] = "FAIL"
        for index, (name, width, async_reset, has_enable, reset_value) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            assert width >= 1 and 0 <= reset_value < 1 << width, "Do not silently resize reset patterns"
            parameters = {"WIDTH": width, "RESET_VALUE": reset_value,
                          "ASYNC_RESET": async_reset, "HAS_ENABLE": has_enable}
            case = build / name
            # Force rebuilding when parameters change, even in a reused directory.
            prefix = "-Pdff." if args.sim == "icarus" else "-pvalue+dff."
            # The Make recipe is a shell command. Quote the complete flag so
            # the apostrophe in a sized SV literal reaches the compiler intact.
            overrides = " ".join(shlex.quote(f"{prefix}{key}={parameter_literal(key, value, width)}")
                                 for key, value in parameters.items())
            print(f'Running {name}: {parameters}, seed={args.seed + index}', flush=True)
            (result, log_file, results_file, coverage_file) = run_simulation(
                args, ROOT, TEST_DIR, 'dff', 'test_dff', 'DffTest', case, rtl,
                environment={
                    'DFF_WIDTH': str(width), 'DFF_RESET_VALUE': str(reset_value),
                    'DFF_ASYNC_RESET': str(async_reset), 'DFF_HAS_ENABLE': str(has_enable),
                    'DFF_SEED': str(args.seed + index), 'DFF_RANDOM_CYCLES': str(args.random_cycles),
                },
                compile_args=f'{args.compile_args} {overrides}',
                parameters=parameters,
            )
            report = {"status": "FAIL", "name": name, "parameters": parameters, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                passed_test(results_file, 'DffTest', 'test_dff')
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if coverage["status"] != "PASS" or coverage["parameters"] != parameters:
                    raise ValueError("Coverage or elaboration parameters did not match")
                if coverage["seed"] != args.seed + index or coverage["random_cycles"] != args.random_cycles:
                    raise ValueError("Random campaign settings did not match")
                report.update(coverage, name=name, coverage=str(coverage_file))
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                report["error"] = str(error)
                print("\n".join(log_file.read_text(encoding="utf-8").splitlines()[-25:]), flush=True)
            summary["profiles"].append(report)
            print(f"{name}: {report['status']}", flush=True)
        summary["parameter_checks"] = [check_invalid_width(args, build, rtl)]
        expected_profiles = len(set(args.case)) if args.case else len(PROFILES)
        summary["status"] = "PASS" if len(summary["profiles"]) == expected_profiles and all(
            report["status"] == "PASS" for report in (*summary["profiles"], *summary["parameter_checks"])
        ) else "FAIL"
        if not args.case:
            branches = {(report["parameters"]["ASYNC_RESET"], report["parameters"]["HAS_ENABLE"])
                        for report in summary["profiles"] if report["status"] == "PASS"}
            summary["matrix_goals"] = {"all_recommended_profiles": len(summary["profiles"]) == len(PROFILES),
                                       "all_reset_enable_branches": set(product((0, 1), repeat=2)) <= branches}
            if not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"DFF regression could not run: {error}", file=sys.stderr)
    finally:
        finish_summary(summary_file, summary, 'DFF')
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
