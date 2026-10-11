"""Run the counter specification matrix through the existing PyUVM Make flow."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET


# src/val/<category>/counter is four directory levels below the project root.
# Resolve from the script so direct invocations work from any directory.
ROOT = Path(__file__).resolve().parents[4]
PROFILES = (
    ("minimum_saturating", 1, 1, 0, 0),
    ("minimum_wrapping", 1, 0, 0, 0),
    ("fifo_pointer", 4, 0, 0, 0),
    ("small_event", 8, 1, 0, 0),
    ("performance", 32, 1, 0, 0),
    ("extended", 64, 1, 0, 0),
    ("async_reset", 32, 1, 1, 0),
    ("nonzero_reset", 16, 1, 0, 0x35A7),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sim", choices=("vcs", "icarus"), default="vcs")
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--rtl", type=Path, default=ROOT / "src/rtl/common/counter.sv")
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
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    rtl = args.rtl.resolve()
    summary = {
        "status": "NOT_RUN",
        "framework": "PyUVM",
        "simulator": args.sim,
        "scope": "selected_profiles" if args.case else "recommended_matrix",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "specification": "specs/common/mosaic-counter/README.md",
        "rtl": str(rtl),
        "rtl_sha256": None,
        "profiles": [],
        "external_checks": {
            "formal": "NOT_RUN", "hdl_sva": "NOT_RUN",
            "commercial_static_checks": "NOT_RUN", "physical_power": "NOT_RUN",
        },
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = {
            name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
            for name in ("counter_env.py", "test_counter_spec.py", "run_counter_regression.py")
        }
        # Missing tools are NOT_RUN, rather than successful verification or
        # an RTL failure. Respect the same executable directory as cocotb.
        binaries = ("vcs",) if args.sim == "vcs" else ("iverilog", "vvp")
        missing = [
            binary for binary in binaries
            if shutil.which(binary, path=str(args.sim_bin_dir) if args.sim_bin_dir else None) is None
        ]
        if missing:
            raise FileNotFoundError(f"Simulator executable(s) missing: {', '.join(missing)}")
        for index, (name, width, saturate, async_reset, reset_value) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            case_build = build / name
            case_build.mkdir(parents=True, exist_ok=True)
            coverage_file = case_build / "coverage.json"
            results_file = case_build / "results.xml"
            log_file = case_build / "simulation.log"
            coverage_file.unlink(missing_ok=True)
            results_file.unlink(missing_ok=True)
            parameters = {
                "WIDTH": width, "SATURATE": saturate,
                "ASYNC_RESET": async_reset, "RESET_VALUE": reset_value,
            }
            # Rewriting this dependency forces recompilation when parameter
            # overrides change, even if the same build directory is reused.
            parameter_file = case_build / "parameters.json"
            parameter_file.write_text(json.dumps(parameters) + "\n", encoding="utf-8")
            overrides = " ".join(
                f"-Pcounter.{key}={value}" if args.sim == "icarus"
                else f"-pvalue+counter.{key}={value}"
                for key, value in parameters.items()
            )
            command = [
                args.make, "--no-print-directory", "-C", str(ROOT), "-f", "Makefile", "pyuvm",
                f"SIM={args.sim}", f"PYTHON_BIN={sys.executable}",
                "COCOTB_TOPLEVEL=counter", "COCOTB_TEST_MODULES=test_counter_spec",
                f"PYUVM_TEST_DIR={Path(__file__).resolve().parent}",
                r"COCOTB_TEST_FILTER=^test_counter_spec\.CounterSpecTest$", "COCOTB_TESTCASE=",
                f"VERILOG_SOURCES={rtl}", f"SIM_BUILD={case_build}",
                f"COCOTB_RESULTS_FILE={results_file}",
                f"CUSTOM_COMPILE_DEPS={parameter_file}",
                f"COMPILE_ARGS={args.compile_args} {overrides}", f"SIM_ARGS={args.sim_args}",
            ]
            if args.sim_bin_dir:
                binary_variable = "VCS_BIN_DIR" if args.sim == "vcs" else "ICARUS_BIN_DIR"
                command.append(f"{binary_variable}={args.sim_bin_dir.resolve()}")
            environment = os.environ.copy()
            environment.update(
                COUNTER_WIDTH=str(width), COUNTER_RESET_VALUE=str(reset_value),
                COUNTER_SATURATE=str(saturate), COUNTER_ASYNC_RESET=str(async_reset),
                COUNTER_SEED=str(args.seed + index), COUNTER_RANDOM_CYCLES=str(args.random_cycles),
                COUNTER_COVERAGE_FILE=str(coverage_file),
            )
            print(f"Running {name}: {parameters}, seed={args.seed + index}", flush=True)
            with log_file.open("w", encoding="utf-8") as log:
                result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
            report = {"status": "FAIL", "name": name, "parameters": parameters, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                cases = ET.parse(results_file).findall(".//testcase")
                if len(cases) != 1 or cases[0].get("name") != "CounterSpecTest":
                    raise ValueError("The expected PyUVM test did not run exactly once")
                if cases[0].find("failure") is not None or cases[0].find("error") is not None:
                    raise ValueError("The PyUVM test failed")
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if coverage["status"] != "PASS" or coverage["parameters"] != parameters:
                    raise ValueError("Functional coverage or parameter matching failed")
                report.update(coverage, name=name, log=str(log_file), coverage=str(coverage_file))
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                report["error"] = str(error)
                print("\n".join(log_file.read_text(encoding="utf-8").splitlines()[-25:]), flush=True)
            summary["profiles"].append(report)
            print(f'{name}: {report["status"]}', flush=True)
        summary["status"] = (
            "PASS" if summary["profiles"] and all(
                report["status"] == "PASS" for report in summary["profiles"]
            ) else "FAIL"
        )
        if summary["status"] == "PASS" and not args.case:
            # The remaining specification crosses span elaborations rather
            # than cycles within one statically configured counter instance.
            boundaries = {
                (report["parameters"]["SATURATE"], boundary)
                for report in summary["profiles"]
                for boundary in ("overflow", "underflow")
                if report["events"][boundary] > 0
            }
            reset_commands = {
                (report["parameters"]["ASYNC_RESET"], command)
                for report in summary["profiles"]
                for command in report["bins"]["commands"]
            }
            width_boundaries = {
                (report["parameters"]["WIDTH"], boundary)
                for report in summary["profiles"]
                for boundary in ("overflow", "underflow")
                if report["events"][boundary] > 0
            }
            summary["matrix_goals"] = {
                "recommended_profiles": len(summary["profiles"]) == len(PROFILES),
                "boundary_saturation_cross": set(product((0, 1), ("overflow", "underflow"))) <= boundaries,
                "reset_mode_active_command_cross": set(product((0, 1), ("clear", "load", "increment", "decrement"))) <= reset_commands,
                "width_boundary_cross": set(product({profile[1] for profile in PROFILES}, ("overflow", "underflow"))) <= width_boundaries,
            }
            if not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"
    except OSError as error:
        summary["error"] = str(error)
        print(f"Counter regression could not run: {error}", file=sys.stderr)
    finally:
        summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        summary_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"Counter regression {summary['status']}: {summary_file}", flush=True)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
