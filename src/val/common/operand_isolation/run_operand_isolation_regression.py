"""Run the operand isolation width/clamp matrix with native PyUVM checks."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from mosaic_uvm.regression import (
    campaign_status, finish_summary, license_unavailable, parameter_guard, parse_args, passed_test, require_simulator, run_simulation, verification_hashes,
)

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
WIDTHS = (1, 8, 16, 32, 64, 128, 256)
PROFILES = tuple(
    (f"width{width}_{clamp_class}", width, clamp_class, value)
    for width in WIDTHS
    for clamp_class, value in (
        ("zero", 0), ("one", (1 << width) - 1),
        *(((("mixed", int(("10100101" * width)[:width], 2)),)) if width > 1 else ()),
    )
)
INVALID_PARAMETERS = (
    ("zero_width", {"WIDTH": "0"}, "operand_isolation_width_must_be_greater_than_zero"),
    *((f"unknown_clamp_{state}", {"WIDTH": "4", "CLAMP_VALUE": f"4'b10{state}1"},
       "operand_isolation_clamp_value_must_be_known") for state in "xz"),
)


def check_unknown_controls(args, build: Path, rtl: Path) -> list[dict]:
    """Prove the live assertion rejects each unacknowledged illegal control.

An expected test failure earns PASS only with the exact PyUVM test, a failing
JUnit record, and its known-control diagnostic. Compilation errors cannot pass.
"""
    reports = []
    for state in "xz":
        case = build / "unknown_control_checks" / state
        prefix = "-Poperand_isolation." if args.sim == "icarus" else "-pvalue+operand_isolation."
        overrides = " ".join(shlex.quote(f"{prefix}{key}={value}") for key, value in {
            "WIDTH": "8", "CLAMP_VALUE": "8'ha5",
        }.items())
        (result, log_file, results_file, coverage_file) = run_simulation(
            args, ROOT, TEST_DIR, 'operand_isolation', 'test_operand_isolation', 'OperandIsolationTest', case, rtl,
            environment={
                'OPERAND_ISOLATION_WIDTH': '8', 'OPERAND_ISOLATION_CLAMP_VALUE': '165',
                'OPERAND_ISOLATION_CONTROL_PROBE': state, 'OPERAND_ISOLATION_SEED': str(args.seed),
                'OPERAND_ISOLATION_RANDOM_CYCLES': str(args.random_cycles),
            },
            compile_args=f'{args.compile_args} {overrides}',
            parameters={
                'WIDTH': 8, 'CLAMP_VALUE': 165,
            },
        )
        diagnostic = log_file.read_text(encoding="utf-8")
        detected = False
        try:
            cases = ET.parse(results_file).findall(".//testcase")
            detected = (
                len(cases) == 1 and cases[0].get("name") == "OperandIsolationTest"
                and cases[0].get("classname") == "test_operand_isolation"
                and cases[0].find("failure") is not None and cases[0].find("skipped") is None
                and f"AssertionError: Known-control assertion failed: i_isolate={state}" in diagnostic
            )
        except (OSError, ET.ParseError):
            pass
        reports.append({
            "control": state, "status": "PASS" if detected else "NOT_RUN" if license_unavailable(diagnostic) else "FAIL",
            "expected_test_failure": detected, "make_returncode": result.returncode, "log": str(log_file),
        })
        print(f"Unknown-control assertion {state}: {reports[-1]['status']}", flush=True)
    return reports


def check_invalid_parameters(args, build: Path, rtl: Path) -> list[dict]:
    return [parameter_guard(args, build, rtl, 'operand_isolation', name, parameters, expected)
            for name, parameters, expected in INVALID_PARAMETERS]


def main() -> int:
    args = parse_args('operand_isolation', __doc__, profiles=[profile[0] for profile in PROFILES], seed=20261011)
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    summary = {
        "status": "NOT_RUN", "framework": "PyUVM", "simulator": args.sim,
        "scope": "selected_profiles" if args.case else "width_clamp_matrix",
        "specification": "specs/common/mosaic-operand-isolation/README.md",
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "rtl": str(rtl),
        "profiles": [], "parameter_checks": [], "unknown_control_checks": [],
        "external_checks": dict.fromkeys((
            "hdl_sva", "formal", "commercial_lint", "cdc", "rdc", "dft", "vc_lp",
            "synthesis", "logical_equivalence", "physical_timing", "physical_power",
            "accepted_operation_integration", "downstream_power_savings",
        ), "NOT_RUN"),
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = verification_hashes(TEST_DIR)
        require_simulator(args)
        summary["status"] = "FAIL"
        for index, (name, width, clamp_class, clamp_value) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            parameters = {"WIDTH": width, "CLAMP_VALUE": clamp_value}
            case = build / name
            # Preserve sized-literal apostrophes through Make without narrowing
            # clamp values, including the 256-bit configuration.
            prefix = "-Poperand_isolation." if args.sim == "icarus" else "-pvalue+operand_isolation."
            compiler_parameters = {"WIDTH": str(width), "CLAMP_VALUE": f"{width}'h{clamp_value:x}"}
            overrides = " ".join(shlex.quote(f"{prefix}{key}={value}") for key, value in compiler_parameters.items())
            print(f'Running {name}: {parameters}, seed={args.seed + index}', flush=True)
            (result, log_file, results_file, coverage_file) = run_simulation(
                args, ROOT, TEST_DIR, 'operand_isolation', 'test_operand_isolation', 'OperandIsolationTest', case, rtl,
                environment={
                    'OPERAND_ISOLATION_WIDTH': str(width), 'OPERAND_ISOLATION_CLAMP_VALUE': str(clamp_value),
                    'OPERAND_ISOLATION_CONTROL_PROBE': '', 'OPERAND_ISOLATION_SEED': str(args.seed + index),
                    'OPERAND_ISOLATION_RANDOM_CYCLES': str(args.random_cycles),
                },
                compile_args=f'{args.compile_args} {overrides}',
                parameters=parameters,
            )
            report = {"status": "FAIL", "name": name, "parameters": parameters, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                passed_test(results_file, 'OperandIsolationTest', 'test_operand_isolation')
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if coverage["status"] != "PASS" or coverage["parameters"] != parameters or coverage["clamp_class"] != clamp_class or not all(coverage["goals"].values()):
                    raise ValueError("Coverage or elaboration parameters did not match")
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
        summary["parameter_checks"] = check_invalid_parameters(args, build, rtl)
        summary["unknown_control_checks"] = check_unknown_controls(args, build, rtl)
        reports = (*summary["profiles"], *summary["parameter_checks"], *summary["unknown_control_checks"])
        complete = len(summary["profiles"]) == (len(set(args.case)) if args.case else len(PROFILES)) and len(summary["parameter_checks"]) == len(INVALID_PARAMETERS) and len(summary["unknown_control_checks"]) == 2
        summary["status"] = campaign_status(reports, complete)
        if not args.case:
            crossed = {(report["parameters"]["WIDTH"], report["clamp_class"])
                       for report in summary["profiles"] if report["status"] == "PASS"}
            summary["matrix_goals"] = {"width_clamp_class_cross": crossed == {(width, clamp_class) for _, width, clamp_class, _ in PROFILES}}
            if summary["status"] == "PASS" and not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"Operand isolation regression could not run: {error}", file=sys.stderr)
    finally:
        finish_summary(summary_file, summary, 'Operand isolation')
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
