"""Run the required write gate widths and HDL destination integrations in PyUVM."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
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
WIDTHS = (1, 2, 4, 8, 16, 32, 64, 128)
PROFILES = tuple((f"width{width}_{kind}", width, kind == "integration")
                 for width in WIDTHS for kind in ("functional", "integration"))
PROBES = (
    ("write_x", False, "Known-control assertion failed: unknown_write_enable"),
    ("write_z", False, "Known-control assertion failed: unknown_write_enable"),
    ("suppress_x", False, "Known-control assertion failed: unknown_requested_suppression"),
    ("suppress_z", False, "Known-control assertion failed: unknown_requested_suppression"),
    ("unsafe_suppression", True, "Integration safety assertion failed: suppressed architecturally required write"),
)


def license_unavailable(diagnostic: str) -> bool:
    """Record license checkout failures as unavailable execution, never PASS."""
    return any(fragment in diagnostic.lower() for fragment in (
        "license checkout failed", "license check out failed", "no valid license",
        "cannot connect to license server", "unable to checkout a license",
    ))


def test_case(results: Path):
    cases = ET.parse(results).findall(".//testcase")
    if len(cases) != 1 or cases[0].get("name") != "WriteGateTest" or cases[0].get("classname") != "test_write_gate":
        raise ValueError("The expected PyUVM test did not run exactly once")
    return cases[0]


def simulate(args, case: Path, rtl: Path, width: int, integration: bool, seed: int, probe=""):
    """Invalidate stale reports and compile each profile with explicit parameters."""
    case.mkdir(parents=True, exist_ok=True)
    coverage, results = case / "coverage.json", case / "results.xml"
    coverage.unlink(missing_ok=True)
    results.unlink(missing_ok=True)
    parameter_file = case / "parameters.json"
    parameter_file.write_text(json.dumps(dict(WIDTH=width, integration=integration)) + "\n", encoding="utf-8")
    top = "write_gate_destinations" if integration else "write_gate"
    prefix = f"-P{top}." if args.sim == "icarus" else f"-pvalue+{top}."
    sources = str(rtl) + (f" {TEST_DIR / 'write_gate_destinations.sv'}" if integration else "")
    command = [
        args.make, "--no-print-directory", "-C", str(ROOT), "-f", "Makefile", "pyuvm",
        f"SIM={args.sim}", f"PYTHON_BIN={sys.executable}", f"COCOTB_TOPLEVEL={top}",
        "COCOTB_TEST_MODULES=test_write_gate", f"PYUVM_TEST_DIR={TEST_DIR}",
        r"COCOTB_TEST_FILTER=^test_write_gate\.WriteGateTest$", "COCOTB_TESTCASE=",
        f"VERILOG_SOURCES={sources}", f"SIM_BUILD={case}", f"COCOTB_RESULTS_FILE={results}",
        f"CUSTOM_COMPILE_DEPS={parameter_file}", f"COMPILE_ARGS={args.compile_args} {shlex.quote(prefix + 'WIDTH=' + str(width))}",
        f"SIM_ARGS={args.sim_args}",
    ]
    if args.sim_bin_dir:
        variable = "VCS_BIN_DIR" if args.sim == "vcs" else "ICARUS_BIN_DIR"
        command.append(f"{variable}={args.sim_bin_dir}")
    environment = os.environ.copy()
    environment.update(
        WRITE_GATE_WIDTH=str(width), WRITE_GATE_INTEGRATION=str(int(integration)),
        WRITE_GATE_SEED=str(seed), WRITE_GATE_RANDOM_CYCLES=str(args.random_cycles),
        WRITE_GATE_COVERAGE_FILE=str(coverage),
        WRITE_GATE_CONTROL_PROBE=probe if not integration else "",
        WRITE_GATE_INTEGRATION_PROBE=probe if integration else "",
    )
    log_file = case / "simulation.log"
    with log_file.open("w", encoding="utf-8") as log:
        result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
    return result.returncode, log_file, results, coverage


def invalid_width(args, build: Path, rtl: Path) -> dict:
    """Require the RTL's named elaboration guard, not an unrelated compile error."""
    compiler = shutil.which("vcs" if args.sim == "vcs" else "iverilog",
                            path=str(args.sim_bin_dir) if args.sim_bin_dir else None)
    case = build / "invalid_parameters" / "zero_width"
    case.mkdir(parents=True, exist_ok=True)
    wrapper = case / "invalid_width.sv"
    wrapper.write_text("module write_gate_invalid_width;\nwrite_gate #(.WIDTH(0)) dut ();\nendmodule\n", encoding="utf-8")
    command = ([compiler, "-g2012", "-s", "write_gate_invalid_width", "-tnull"] if args.sim == "icarus" else
               [compiler, "-full64", "-sverilog", "-top", "write_gate_invalid_width", "-o", str(case / "simv")])
    log_file = case / "elaboration.log"
    with log_file.open("w", encoding="utf-8") as log:
        result = subprocess.run([*command, *shlex.split(args.compile_args), str(rtl), str(wrapper)],
                                cwd=case, stdout=log, stderr=subprocess.STDOUT)
    diagnostic = log_file.read_text(encoding="utf-8")
    guard = "write_gate_width_must_be_greater_than_zero"
    rejected = result.returncode != 0 and guard in diagnostic
    return dict(name="zero_width", parameters={"WIDTH": 0}, expected_guard=guard,
                status="PASS" if rejected else "NOT_RUN" if license_unavailable(diagnostic) else "FAIL",
                stage="elaboration" if rejected else None, compiler_returncode=result.returncode, log=str(log_file))


def assertion_probes(args, build: Path, rtl: Path) -> list[dict]:
    reports = []
    for name, integration, expected in PROBES:
        code, log_file, results, _ = simulate(args, build / "assertion_probes" / name, rtl, 8, integration, args.seed, name)
        diagnostic = log_file.read_text(encoding="utf-8")
        detected = False
        try:
            case = test_case(results)
            detected = (code != 0 and case.find("failure") is not None and case.find("skipped") is None
                        and f"AssertionError: {expected}" in diagnostic)
        except (OSError, ValueError, ET.ParseError):
            pass
        reports.append(dict(name=name, status="PASS" if detected else "NOT_RUN" if license_unavailable(diagnostic) else "FAIL",
                            expected_test_failure=detected, make_returncode=code, log=str(log_file)))
        print(f"Assertion {name}: {reports[-1]['status']}", flush=True)
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sim", choices=("vcs", "icarus"), default="vcs")
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--rtl", type=Path, default=ROOT / "src/rtl/common/write_gate.sv")
    parser.add_argument("--seed", type=int, default=20261011)
    parser.add_argument("--random-cycles", type=int, default=2000)
    parser.add_argument("--compile-args", default="")
    parser.add_argument("--sim-args", default="")
    parser.add_argument("--sim-bin-dir", type=Path)
    parser.add_argument("--make", default="make")
    parser.add_argument("--case", action="append", choices=[profile[0] for profile in PROFILES])
    args = parser.parse_args()
    if args.random_cycles < 1000:
        parser.error("--random-cycles must be at least 1000")
    if args.sim_bin_dir:
        args.sim_bin_dir = args.sim_bin_dir.resolve()
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    summary = dict(
        status="NOT_RUN", framework="PyUVM", simulator=args.sim,
        scope="selected_profiles" if args.case else "width_destination_matrix",
        specification="specs/common/mosaic-write-gate/README.md", rtl=str(rtl),
        started_at_utc=datetime.now(timezone.utc).isoformat(), profiles=[], parameter_checks=[], assertion_probes=[],
        external_checks=dict.fromkeys((
            "hdl_sva", "formal", "formal_integration", "commercial_lint", "cdc", "rdc", "dft", "vc_lp",
            "technology_synthesis", "logical_equivalence", "physical_timing", "physical_power",
            "destination_energy_savings", "system_protocol_integration",
        ), "NOT_RUN"),
    )
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = {
            name: hashlib.sha256((TEST_DIR / name).read_bytes()).hexdigest()
            for name in ("write_gate_env.py", "test_write_gate.py", "run_write_gate_regression.py", "write_gate_destinations.sv")
        }
        binaries = ("vcs",) if args.sim == "vcs" else ("iverilog", "vvp")
        missing = [binary for binary in binaries if shutil.which(binary, path=str(args.sim_bin_dir) if args.sim_bin_dir else None) is None]
        if missing:
            raise FileNotFoundError(f"Simulator executable(s) missing: {', '.join(missing)}")
        summary["status"] = "FAIL"
        for index, (name, width, integration) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            print(f"Running {name}, seed={args.seed + index}", flush=True)
            code, log_file, results, coverage_file = simulate(args, build / name, rtl, width, integration, args.seed + index)
            report = dict(status="FAIL", name=name, parameters={"WIDTH": width}, integration=integration, log=str(log_file))
            try:
                if code:
                    raise ValueError(f"make exited with status {code}")
                case = test_case(results)
                if any(case.find(tag) is not None for tag in ("failure", "error", "skipped")):
                    raise ValueError("The PyUVM test failed or was skipped")
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if (coverage["status"] != "PASS" or coverage["parameters"] != {"WIDTH": width}
                        or coverage["integration"] != integration or not coverage["goals"] or not all(coverage["goals"].values())):
                    raise ValueError("Coverage or elaboration settings did not match")
                if coverage["seed"] != args.seed + index or coverage["random_transactions"] != args.random_cycles:
                    raise ValueError("Random campaign settings did not match")
                report.update(coverage, name=name, coverage=str(coverage_file))
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                report["error"] = str(error)
                diagnostic = log_file.read_text(encoding="utf-8")
                if license_unavailable(diagnostic):
                    report["status"] = "NOT_RUN"
                print("\n".join(diagnostic.splitlines()[-25:]), flush=True)
            summary["profiles"].append(report)
            print(f"{name}: {report['status']}", flush=True)
        summary["parameter_checks"] = [invalid_width(args, build, rtl)]
        summary["assertion_probes"] = assertion_probes(args, build, rtl)
        reports = (*summary["profiles"], *summary["parameter_checks"], *summary["assertion_probes"])
        complete = (len(summary["profiles"]) == (len(set(args.case)) if args.case else len(PROFILES))
                    and len(summary["parameter_checks"]) == 1 and len(summary["assertion_probes"]) == len(PROBES))
        summary["status"] = (
            "PASS" if complete and all(report["status"] == "PASS" for report in reports)
            else "NOT_RUN" if complete and any(report["status"] == "NOT_RUN" for report in reports)
            and all(report["status"] in ("PASS", "NOT_RUN") for report in reports) else "FAIL"
        )
        if not args.case:
            crossed = {(report["parameters"]["WIDTH"], report["integration"])
                       for report in summary["profiles"] if report["status"] == "PASS"}
            summary["matrix_goals"] = {"width_functional_destination_cross": crossed == set(product_matrix())}
            if summary["status"] == "PASS" and not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"Write gate regression could not run: {error}", file=sys.stderr)
    finally:
        summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        summary_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"Write gate regression {summary['status']}: {summary_file}", flush=True)
    return 0 if summary["status"] == "PASS" else 1


def product_matrix():
    return ((width, integration) for width in WIDTHS for integration in (False, True))


if __name__ == "__main__":
    sys.exit(main())
