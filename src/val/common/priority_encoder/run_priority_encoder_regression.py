"""Run native PyUVM priority, four-state, and invalid-parameter checks."""

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
WIDTHS = (1, 2, 3, 4, 5, 8, 16, 32)
PROFILES = tuple((f"width{width}_{'lsb' if direction else 'msb'}", width, direction)
                 for width in WIDTHS for direction in (1, 0))
INVALID_PARAMETERS = (
    ("zero_width", {"WIDTH": "0"}, "priority_encoder_width_must_be_greater_than_zero"),
    ("undersized_index", {"WIDTH": "3", "INDEX_WIDTH": "1"}, "priority_encoder_index_width_must_match_width"),
    ("oversized_index", {"WIDTH": "4", "INDEX_WIDTH": "3"}, "priority_encoder_index_width_must_match_width"),
    ("minimum_zero_index", {"WIDTH": "1", "INDEX_WIDTH": "0"}, "priority_encoder_index_width_must_match_width"),
)


def check_ambiguous_requests(args, build: Path, rtl: Path) -> list[dict]:
    """Prove the live assertion rejects each unacknowledged ambiguous request.

An expected test failure earns PASS only with the exact PyUVM test, a failing
JUnit record, and its ambiguous-request diagnostic. Compilation errors cannot pass.
"""
    reports = []
    for state in "xz":
        case = build / "ambiguous_request_checks" / state
        prefix = "-Ppriority_encoder." if args.sim == "icarus" else "-pvalue+priority_encoder."
        overrides = " ".join(shlex.quote(f"{prefix}{key}={value}") for key, value in {
            "WIDTH": "4", "LSB_HIGH_PRIORITY": "1",
        }.items())
        (result, log_file, results_file, coverage_file) = run_simulation(
            args, ROOT, TEST_DIR, 'priority_encoder', 'test_priority_encoder', 'PriorityEncoderTest', case, rtl,
            environment={
                'PRIORITY_ENCODER_WIDTH': '4', 'PRIORITY_ENCODER_LSB_HIGH_PRIORITY': '1',
                'PRIORITY_ENCODER_AMBIGUITY_PROBE': state, 'PRIORITY_ENCODER_SEED': str(args.seed),
                'PRIORITY_ENCODER_RANDOM_CYCLES': str(args.random_cycles),
            },
            compile_args=f'{args.compile_args} {overrides}',
            parameters={
                'WIDTH': 4, 'LSB_HIGH_PRIORITY': 1,
            },
        )
        diagnostic = log_file.read_text(encoding="utf-8")
        detected = False
        try:
            cases = ET.parse(results_file).findall(".//testcase")
            detected = (
                len(cases) == 1 and cases[0].get("name") == "PriorityEncoderTest"
                and cases[0].get("classname") == "test_priority_encoder"
                and cases[0].find("failure") is not None and cases[0].find("skipped") is None
                and f"AssertionError: Ambiguous-request assertion failed: i_request=001{state}" in diagnostic
            )
        except (OSError, ET.ParseError):
            pass
        reports.append({
            "unknown_bit": state, "status": "PASS" if detected else "NOT_RUN" if license_unavailable(diagnostic) else "FAIL",
            "expected_test_failure": detected, "make_returncode": result.returncode, "log": str(log_file),
        })
        print(f"Ambiguous-request assertion {state}: {reports[-1]['status']}", flush=True)
    return reports


def check_invalid_parameters(args, build: Path, rtl: Path) -> list[dict]:
    return [parameter_guard(args, build, rtl, 'priority_encoder', name, parameters, expected)
            for name, parameters, expected in INVALID_PARAMETERS]


def main() -> int:
    args = parse_args('priority_encoder', __doc__, profiles=[profile[0] for profile in PROFILES], seed=20261011)
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    summary = {
        "status": "NOT_RUN", "framework": "PyUVM", "simulator": args.sim,
        "scope": "selected_profiles" if args.case else "width_priority_matrix",
        "specification": "specs/common/mosaic-priority-encoder/README.md",
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "rtl": str(rtl),
        "profiles": [], "parameter_checks": [], "ambiguous_request_checks": [],
        "external_checks": dict.fromkeys((
            "hdl_sva", "formal", "commercial_lint", "cdc", "rdc", "dft", "vc_lp",
            "synthesis", "logical_equivalence", "physical_timing", "physical_power",
            "request_coherence_integration", "acknowledgement_retention_integration",
        ), "NOT_RUN"),
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = verification_hashes(TEST_DIR)
        require_simulator(args)
        summary["status"] = "FAIL"
        for index, (name, width, direction) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            parameters = {"WIDTH": width, "LSB_HIGH_PRIORITY": direction,
                          "INDEX_WIDTH": max(1, (width - 1).bit_length())}
            case = build / name
            # Leave INDEX_WIDTH derived and audit the actual binary index port.
            # Static priority direction is an elaboration-time parameter.
            prefix = "-Ppriority_encoder." if args.sim == "icarus" else "-pvalue+priority_encoder."
            compiler_parameters = {"WIDTH": str(width), "LSB_HIGH_PRIORITY": str(direction)}
            overrides = " ".join(shlex.quote(f"{prefix}{key}={value}") for key, value in compiler_parameters.items())
            print(f'Running {name}: {parameters}, seed={args.seed + index}', flush=True)
            (result, log_file, results_file, coverage_file) = run_simulation(
                args, ROOT, TEST_DIR, 'priority_encoder', 'test_priority_encoder', 'PriorityEncoderTest', case, rtl,
                environment={
                    'PRIORITY_ENCODER_WIDTH': str(width), 'PRIORITY_ENCODER_LSB_HIGH_PRIORITY': str(direction),
                    'PRIORITY_ENCODER_AMBIGUITY_PROBE': '', 'PRIORITY_ENCODER_SEED': str(args.seed + index),
                    'PRIORITY_ENCODER_RANDOM_CYCLES': str(args.random_cycles),
                },
                compile_args=f'{args.compile_args} {overrides}',
                parameters=parameters,
            )
            report = {"status": "FAIL", "name": name, "parameters": parameters, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                passed_test(results_file, 'PriorityEncoderTest', 'test_priority_encoder')
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if coverage["status"] != "PASS" or coverage["parameters"] != parameters or not all(coverage["goals"].values()):
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
        summary["ambiguous_request_checks"] = check_ambiguous_requests(args, build, rtl)
        reports = (*summary["profiles"], *summary["parameter_checks"], *summary["ambiguous_request_checks"])
        complete = len(summary["profiles"]) == (len(set(args.case)) if args.case else len(PROFILES)) and len(summary["parameter_checks"]) == len(INVALID_PARAMETERS) and len(summary["ambiguous_request_checks"]) == 2
        summary["status"] = campaign_status(reports, complete)
        if not args.case:
            crossed = {(profile["parameters"]["WIDTH"], profile["parameters"]["LSB_HIGH_PRIORITY"])
                       for profile in summary["profiles"] if profile["status"] == "PASS"}
            selected = {(profile["parameters"]["WIDTH"], profile["parameters"]["LSB_HIGH_PRIORITY"], index)
                        for profile in summary["profiles"] if profile["status"] == "PASS"
                        for index in profile["bins"]["selected_indices"]}
            summary["matrix_goals"] = {
                "width_priority_direction_cross": crossed == {(width, direction) for _, width, direction in PROFILES},
                "selected_index_priority_direction_cross": selected == {(width, direction, index) for _, width, direction in PROFILES for index in range(width)},
            }
            if summary["status"] == "PASS" and not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"

    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"Priority encoder regression could not run: {error}", file=sys.stderr)
    finally:
        finish_summary(summary_file, summary, 'Priority encoder')
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
