"""Run the DFF specification matrix through the existing PyUVM Make flow."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

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
    """Test the existing time-zero fatal guard without calling it elaboration."""
    case = build / "invalid_parameters" / "zero_width"
    case.mkdir(parents=True, exist_ok=True)
    wrapper = case / "invalid_width.sv"
    wrapper.write_text(
        '`timescale 1ns/1ps\nmodule dff_invalid_width;\n'
        'dff #(.WIDTH(0)) dut (.i_clk(1\'b0), .i_rstb(1\'b1), '
        '.i_enable(1\'b0), .i_d(2\'b00), .o_q());\n'
        'initial begin #1; $fatal(1, "Invalid width was accepted"); end\nendmodule\n',
        encoding="utf-8",
    )
    search_path = str(args.sim_bin_dir) if args.sim_bin_dir else None
    compiler = shutil.which("vcs" if args.sim == "vcs" else "iverilog", path=search_path)
    executable = case / ("simv" if args.sim == "vcs" else "sim.vvp")
    command = ([compiler, "-g2012", "-s", "dff_invalid_width", "-o", str(executable)]
               if args.sim == "icarus" else
               [compiler, "-full64", "-sverilog", "-top", "dff_invalid_width", "-o", str(executable)])
    log_file = case / "guard.log"
    with log_file.open("w", encoding="utf-8") as log:
        compiled = subprocess.run([*command, *shlex.split(args.compile_args), str(rtl), str(wrapper)],
                                  cwd=case, stdout=log, stderr=subprocess.STDOUT)
        runtime_code = None
        if compiled.returncode == 0:
            runtime = ([shutil.which("vvp", path=search_path), str(executable)]
                       if args.sim == "icarus" else [str(executable)])
            result = subprocess.run(runtime, cwd=case, stdout=log, stderr=subprocess.STDOUT)
            runtime_code = result.returncode
    diagnostic = log_file.read_text(encoding="utf-8")
    rejected = runtime_code is not None and runtime_code != 0 and "WIDTH must be greater than zero" in diagnostic
    return {"name": "zero_width", "parameters": {"WIDTH": 0},
            "status": "PASS" if rejected else "FAIL", "stage": "simulation_startup",
            "compiler_returncode": compiled.returncode, "runtime_returncode": runtime_code,
            "log": str(log_file), "strict_elaboration_validation": "BLOCKED"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sim", choices=("vcs", "icarus"), default="vcs")
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--rtl", type=Path, default=ROOT / "src/rtl/common/dff.sv")
    parser.add_argument("--seed", type=int, default=20261010)
    parser.add_argument("--random-cycles", type=int, default=2000)
    parser.add_argument("--compile-args", default="")
    parser.add_argument("--sim-args", default="")
    parser.add_argument("--sim-bin-dir", type=Path)
    parser.add_argument("--make", default="make")
    parser.add_argument("--case", action="append", choices=[profile[0] for profile in PROFILES])
    args = parser.parse_args()
    if args.random_cycles < 1000:
        parser.error("--random-cycles must be at least 1000")
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
        summary["verification_sha256"] = {
            name: hashlib.sha256((TEST_DIR / name).read_bytes()).hexdigest()
            for name in ("dff_env.py", "test_dff.py", "run_dff_regression.py")
        }
        binaries = ("vcs",) if args.sim == "vcs" else ("iverilog", "vvp")
        missing = [binary for binary in binaries if shutil.which(
            binary, path=str(args.sim_bin_dir) if args.sim_bin_dir else None,
        ) is None]
        if missing:
            raise FileNotFoundError(f"Simulator executable(s) missing: {', '.join(missing)}")
        summary["status"] = "FAIL"
        for index, (name, width, async_reset, has_enable, reset_value) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            assert width >= 1 and 0 <= reset_value < 1 << width, "Do not silently resize reset patterns"
            parameters = {"WIDTH": width, "RESET_VALUE": reset_value,
                          "ASYNC_RESET": async_reset, "HAS_ENABLE": has_enable}
            case = build / name
            case.mkdir(parents=True, exist_ok=True)
            coverage_file, results_file = case / "coverage.json", case / "results.xml"
            log_file = case / "simulation.log"
            coverage_file.unlink(missing_ok=True)
            results_file.unlink(missing_ok=True)
            parameter_file = case / "parameters.json"
            # Force rebuilding when parameters change, even in a reused directory.
            parameter_file.write_text(json.dumps(parameters) + "\n", encoding="utf-8")
            prefix = "-Pdff." if args.sim == "icarus" else "-pvalue+dff."
            # The Make recipe is a shell command. Quote the complete flag so
            # the apostrophe in a sized SV literal reaches the compiler intact.
            overrides = " ".join(shlex.quote(f"{prefix}{key}={parameter_literal(key, value, width)}")
                                 for key, value in parameters.items())
            command = [
                args.make, "--no-print-directory", "-C", str(ROOT), "-f", "Makefile", "pyuvm",
                f"SIM={args.sim}", f"PYTHON_BIN={sys.executable}", "COCOTB_TOPLEVEL=dff",
                "COCOTB_TEST_MODULES=test_dff", f"PYUVM_TEST_DIR={TEST_DIR}",
                r"COCOTB_TEST_FILTER=^test_dff\.DffTest$", "COCOTB_TESTCASE=",
                f"VERILOG_SOURCES={rtl}", f"SIM_BUILD={case}", f"COCOTB_RESULTS_FILE={results_file}",
                f"CUSTOM_COMPILE_DEPS={parameter_file}", f"COMPILE_ARGS={args.compile_args} {overrides}",
                f"SIM_ARGS={args.sim_args}",
            ]
            if args.sim_bin_dir:
                variable = "VCS_BIN_DIR" if args.sim == "vcs" else "ICARUS_BIN_DIR"
                command.append(f"{variable}={args.sim_bin_dir.resolve()}")
            environment = os.environ.copy()
            environment.update(
                DFF_WIDTH=str(width), DFF_RESET_VALUE=str(reset_value),
                DFF_ASYNC_RESET=str(async_reset), DFF_HAS_ENABLE=str(has_enable),
                DFF_SEED=str(args.seed + index), DFF_RANDOM_CYCLES=str(args.random_cycles),
                DFF_COVERAGE_FILE=str(coverage_file),
            )
            print(f"Running {name}: {parameters}, seed={args.seed + index}", flush=True)
            with log_file.open("w", encoding="utf-8") as log:
                result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
            report = {"status": "FAIL", "name": name, "parameters": parameters, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                cases = ET.parse(results_file).findall(".//testcase")
                if len(cases) != 1 or cases[0].get("name") != "DffTest" or cases[0].get("classname") != "test_dff":
                    raise ValueError("The expected PyUVM test did not run exactly once")
                if any(cases[0].find(tag) is not None for tag in ("failure", "error", "skipped")):
                    raise ValueError("The PyUVM test failed or was skipped")
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
        summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        summary_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"DFF regression {summary['status']}: {summary_file}", flush=True)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
