"""Run PyUVM reset sequencing, stage assertions, and elaboration guards."""

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
PROFILES = tuple((f"stages{stages}", stages) for stages in (2, 3, 4))
INVALID_PARAMETERS = (
    ("zero_stages", {"STAGES": "0"}, "reset_synchronizer_stages_must_be_at_least_two"),
    ("one_stage", {"STAGES": "1"}, "reset_synchronizer_stages_must_be_at_least_two"),
)


def check_unknown_resets(args, build: Path, rtl: Path) -> list[dict]:
    """Prove the live assertion rejects each unacknowledged unknown reset.

An expected test failure earns PASS only with the exact PyUVM test, a failing
JUnit record, and its unknown-reset diagnostic. Compilation errors cannot pass.
"""
    reports = []
    for state in "xz":
        case = build / "unknown_reset_checks" / state
        prefix = "-Preset_synchronizer." if args.sim == "icarus" else "-pvalue+reset_synchronizer."
        overrides = " ".join(shlex.quote(f"{prefix}{key}={value}") for key, value in {
            "STAGES": "2",
        }.items())
        (result, log_file, results_file, coverage_file) = run_simulation(
            args, ROOT, TEST_DIR, 'reset_synchronizer', 'test_reset_synchronizer', 'ResetSynchronizerTest', case, rtl,
            environment={
                'RESET_SYNCHRONIZER_STAGES': '2', 'RESET_SYNCHRONIZER_CHECK_STAGES': '1',
                'RESET_SYNCHRONIZER_UNKNOWN_PROBE': state, 'RESET_SYNCHRONIZER_SEED': str(args.seed),
                'RESET_SYNCHRONIZER_RANDOM_CYCLES': str(args.random_cycles),
            },
            compile_args=f'{args.compile_args} {overrides}',
            parameters={
                'STAGES': 2,
            },
        )
        diagnostic = log_file.read_text(encoding="utf-8")
        detected = False
        try:
            cases = ET.parse(results_file).findall(".//testcase")
            detected = (
                len(cases) == 1 and cases[0].get("name") == "ResetSynchronizerTest"
                and cases[0].get("classname") == "test_reset_synchronizer"
                and cases[0].find("failure") is not None and cases[0].find("skipped") is None
                and f"AssertionError: Unknown-reset assertion failed: i_async_rstb={state}" in diagnostic
            )
        except (OSError, ET.ParseError):
            pass
        reports.append({
            "unknown_bit": state, "status": "PASS" if detected else "NOT_RUN" if license_unavailable(diagnostic) else "FAIL",
            "expected_test_failure": detected, "make_returncode": result.returncode, "log": str(log_file),
        })
        print(f"Unknown-reset assertion {state}: {reports[-1]['status']}", flush=True)
    return reports


def check_invalid_parameters(args, build: Path, rtl: Path) -> list[dict]:
    return [parameter_guard(args, build, rtl, 'reset_synchronizer', name, parameters, expected)
            for name, parameters, expected in INVALID_PARAMETERS]


def main() -> int:
    args = parse_args('reset_synchronizer', __doc__, profiles=[profile[0] for profile in PROFILES], seed=20261011)
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    summary = {
        "status": "NOT_RUN", "framework": "PyUVM", "simulator": args.sim,
        "scope": "selected_profiles" if args.case else "synchronization_depth_matrix",
        "specification": "specs/common/mosaic-reset-synchronizer/README.md",
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "rtl": str(rtl),
        "profiles": [], "parameter_checks": [], "unknown_reset_checks": [],
        "external_checks": dict.fromkeys((
            "hdl_sva", "formal", "commercial_lint", "cdc", "rdc", "dft", "vc_lp",
            "synthesis", "logical_equivalence", "physical_timing", "physical_power",
            "metastability_mtbf", "recovery_removal", "physical_minimum_reset_pulse",
            "synchronizer_placement", "clock_gating_integration", "reset_reconvergence_integration",
        ), "NOT_RUN"),
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = verification_hashes(TEST_DIR)
        require_simulator(args)
        summary["status"] = "FAIL"
        for index, (name, stages) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            parameters = {"STAGES": stages}
            case = build / name
            # Each depth is a separate elaborated synchronization chain.
            prefix = "-Preset_synchronizer." if args.sim == "icarus" else "-pvalue+reset_synchronizer."
            compiler_parameters = {"STAGES": str(stages)}
            overrides = " ".join(shlex.quote(f"{prefix}{key}={value}") for key, value in compiler_parameters.items())
            print(f'Running {name}: {parameters}, seed={args.seed + index}', flush=True)
            (result, log_file, results_file, coverage_file) = run_simulation(
                args, ROOT, TEST_DIR, 'reset_synchronizer', 'test_reset_synchronizer', 'ResetSynchronizerTest', case, rtl,
                environment={
                    'RESET_SYNCHRONIZER_STAGES': str(stages), 'RESET_SYNCHRONIZER_CHECK_STAGES': '1',
                    'RESET_SYNCHRONIZER_UNKNOWN_PROBE': '', 'RESET_SYNCHRONIZER_SEED': str(args.seed + index),
                    'RESET_SYNCHRONIZER_RANDOM_CYCLES': str(args.random_cycles),
                },
                compile_args=f'{args.compile_args} {overrides}',
                parameters=parameters,
            )
            report = {"status": "FAIL", "name": name, "parameters": parameters, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                passed_test(results_file, 'ResetSynchronizerTest', 'test_reset_synchronizer')
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if coverage["status"] != "PASS" or coverage["parameters"] != parameters or coverage["portable_stage_assertions"] != "PASS" or not all(coverage["goals"].values()):
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
        summary["unknown_reset_checks"] = check_unknown_resets(args, build, rtl)
        reports = (*summary["profiles"], *summary["parameter_checks"], *summary["unknown_reset_checks"])
        complete = len(summary["profiles"]) == (len(set(args.case)) if args.case else len(PROFILES)) and len(summary["parameter_checks"]) == len(INVALID_PARAMETERS) and len(summary["unknown_reset_checks"]) == 2
        summary["status"] = campaign_status(reports, complete)
        if not args.case:
            passed = [profile for profile in summary["profiles"] if profile["status"] == "PASS"]
            phases = {(profile["parameters"]["STAGES"], kind, phase) for profile in passed
                      for kind, phase in profile["bins"]["reset_transition_phases"]}
            expected_phases = ("low", "high", "before_rise", "after_rise", "before_fall", "after_fall", "on_rise", "on_fall")
            summary["matrix_goals"] = {
                "every_specified_depth": {profile["parameters"]["STAGES"] for profile in passed} == {stages for _, stages in PROFILES},
                "reset_phase_depth_cross": {(stages, kind, phase) for _, stages in PROFILES for kind in ("assert", "deassert") for phase in expected_phases} <= phases,
            }
            if summary["status"] == "PASS" and not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"

    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"Reset synchronizer regression could not run: {error}", file=sys.stderr)
    finally:
        finish_summary(summary_file, summary, 'Reset synchronizer')
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
