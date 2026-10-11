"""Run independent disabled/enabled startup simulations of ClockGateTest."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sim", choices=("vcs", "icarus"), default="vcs")
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--rtl", type=Path, default=ROOT / "src/rtl/common/clock_gate.sv")
    parser.add_argument("--seed", type=int, default=20261010)
    parser.add_argument("--random-cycles", type=int, default=2000)
    parser.add_argument("--compile-args", default="")
    parser.add_argument("--sim-args", default="")
    parser.add_argument("--sim-bin-dir", type=Path)
    parser.add_argument("--make", default="make")
    args = parser.parse_args()
    if args.random_cycles < 1000:
        parser.error("--random-cycles must be at least 1000")
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    summary = {
        "status": "NOT_RUN", "framework": "PyUVM", "simulator": args.sim,
        "specification": "specs/common/mosaic-clock-gate/README.md",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "rtl": str(rtl), "profiles": [],
        "external_checks": dict.fromkeys((
            "hdl_sva", "formal",
            "commercial_static_checks", "technology_mapping", "logical_equivalence",
            "generated_clock_sta", "physical_power",
        ), "NOT_RUN"),
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = {
            name: hashlib.sha256((TEST_DIR / name).read_bytes()).hexdigest()
            for name in ("clock_gate_env.py", "test_clock_gate.py", "run_clock_gate_regression.py")
        }
        binaries = ("vcs",) if args.sim == "vcs" else ("iverilog", "vvp")
        missing = [binary for binary in binaries if shutil.which(
            binary, path=str(args.sim_bin_dir) if args.sim_bin_dir else None,
        ) is None]
        if missing:
            raise FileNotFoundError(f"Simulator executable(s) missing: {', '.join(missing)}")
        for enabled in (False, True):
            name = "startup_enabled" if enabled else "startup_disabled"
            case_build = build / name
            case_build.mkdir(parents=True, exist_ok=True)
            coverage_file, results_file = case_build / "coverage.json", case_build / "results.xml"
            log_file = case_build / "simulation.log"
            coverage_file.unlink(missing_ok=True)
            results_file.unlink(missing_ok=True)
            command = [
                args.make, "--no-print-directory", "-C", str(ROOT), "-f", "Makefile", "pyuvm",
                f"SIM={args.sim}", f"PYTHON_BIN={sys.executable}",
                "COCOTB_TOPLEVEL=clock_gate", "COCOTB_TEST_MODULES=test_clock_gate",
                f"PYUVM_TEST_DIR={TEST_DIR}", r"COCOTB_TEST_FILTER=^test_clock_gate\.ClockGateTest$",
                "COCOTB_TESTCASE=", f"VERILOG_SOURCES={rtl}", f"SIM_BUILD={case_build}",
                f"COCOTB_RESULTS_FILE={results_file}", f"COMPILE_ARGS={args.compile_args}",
                f"SIM_ARGS={args.sim_args}",
            ]
            if args.sim_bin_dir:
                variable = "VCS_BIN_DIR" if args.sim == "vcs" else "ICARUS_BIN_DIR"
                command.append(f"{variable}={args.sim_bin_dir.resolve()}")
            environment = os.environ.copy()
            environment.update(
                CLOCK_GATE_STARTUP_ENABLED=str(int(enabled)), CLOCK_GATE_SEED=str(args.seed + int(enabled)),
                CLOCK_GATE_RANDOM_CYCLES=str(args.random_cycles), CLOCK_GATE_COVERAGE_FILE=str(coverage_file),
            )
            print(f"Running {name}, seed={args.seed + int(enabled)}", flush=True)
            with log_file.open("w", encoding="utf-8") as log:
                result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
            report = {"status": "FAIL", "name": name, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                cases = ET.parse(results_file).findall(".//testcase")
                if len(cases) != 1 or cases[0].get("name") != "ClockGateTest" or cases[0].get("classname") != "test_clock_gate":
                    raise ValueError("The expected PyUVM test did not run exactly once")
                if any(cases[0].find(tag) is not None for tag in ("failure", "error", "skipped")):
                    raise ValueError("The PyUVM test failed or was skipped")
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if coverage["status"] != "PASS" or coverage["startup_enabled"] != enabled:
                    raise ValueError("Functional coverage or startup matching failed")
                if coverage["random_cycles"] != args.random_cycles or coverage["seed"] != args.seed + int(enabled):
                    raise ValueError("Random campaign settings did not match")
                report.update(coverage, name=name, coverage=str(coverage_file))
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                report["error"] = str(error)
                print("\n".join(log_file.read_text(encoding="utf-8").splitlines()[-25:]), flush=True)
            summary["profiles"].append(report)
            print(f"{name}: {report['status']}", flush=True)
        summary["status"] = "PASS" if len(summary["profiles"]) == 2 and all(
            profile["status"] == "PASS" for profile in summary["profiles"]
        ) else "FAIL"
    except OSError as error:
        summary["error"] = str(error)
        print(f"Clock gate regression could not run: {error}", file=sys.stderr)
    finally:
        summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        summary_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"Clock gate regression {summary['status']}: {summary_file}", flush=True)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
