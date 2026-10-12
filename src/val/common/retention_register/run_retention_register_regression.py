"""Run portable PyUVM retention, protocol, and invalid-parameter checks."""

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
WIDTHS = (1, 8, 16, 32, 64, 128)
PROFILES = tuple(
    (f"width{width}_{'async' if asynchronous else 'sync'}_{'enable' if enabled else 'noenable'}_{reset_class}",
     width, reset_class, value, asynchronous, enabled)
    for width in WIDTHS
    for reset_class, value in (("zero", 0), ("one", (1 << width)-1),
                              *(((("mixed", int(("10100101" * width)[:width], 2)),)) if width > 1 else ()))
    for asynchronous in (0,1) for enabled in (0,1)
)
INVALID_PARAMETERS = (
    ("zero_width", {"WIDTH": "0"}, "retention_register_width_must_be_greater_than_zero"),
    *((f"unknown_reset_value_{state}", {"WIDTH": "4", "RESET_VALUE": f"4'b10{state}1"},
       "retention_register_reset_value_must_be_known") for state in "xz"),
    ("invalid_async_reset", {"ASYNC_RESET": "2"}, "retention_register_async_reset_must_be_boolean"),
    ("invalid_has_enable", {"HAS_ENABLE": "2"}, "retention_register_has_enable_must_be_boolean"),
    *((f"unknown_async_reset_{state}", {"ASYNC_RESET": f"1'b{state}"},
       "retention_register_async_reset_must_be_boolean") for state in "xz"),
    *((f"unknown_has_enable_{state}", {"HAS_ENABLE": f"1'b{state}"},
       "retention_register_has_enable_must_be_boolean") for state in "xz"),
)
PROTOCOL_PROBES = (
    *((f"unknown_{field}_{state}", f"unknown_{field}") for field in ("reset", "enable", "save", "restore") for state in "xz"),
    ("save_restore_conflict", "save_restore_conflict"),
    ("enable_save", "enable_during_retention"), ("enable_restore", "enable_during_retention"),
    ("restore_without_save", "restore_without_save"), ("repeat_save", "repeat_save"),
    ("repeat_restore", "repeat_restore,restore_without_save"),
)


def check_protocol_probes(args, build: Path, rtl: Path) -> list[dict]:
    """Require exact failing PyUVM probes and their live protocol diagnostics."""
    reports = []
    for name, expected in PROTOCOL_PROBES:
        case = build / "protocol_checks" / name
        parameters = {"WIDTH": 8, "RESET_VALUE": 0, "ASYNC_RESET": 1, "HAS_ENABLE": 1}
        prefix = "-Pretention_register." if args.sim == "icarus" else "-pvalue+retention_register."
        overrides = " ".join(shlex.quote(f"{prefix}{key}={value}") for key, value in parameters.items())
        (result, log_file, results_file, coverage_file) = run_simulation(
            args, ROOT, TEST_DIR, 'retention_register', 'test_retention_register', 'RetentionRegisterTest', case, rtl,
            environment={
                'RETENTION_REGISTER_WIDTH': '8', 'RETENTION_REGISTER_RESET_VALUE': '0',
                'RETENTION_REGISTER_ASYNC_RESET': '1', 'RETENTION_REGISTER_HAS_ENABLE': '1',
                'RETENTION_REGISTER_CHECK_IMAGE': '1', 'RETENTION_REGISTER_PROTOCOL_PROBE': name,
                'RETENTION_REGISTER_SEED': str(args.seed),
                'RETENTION_REGISTER_RANDOM_CYCLES': str(args.random_cycles),
            },
            compile_args=f'{args.compile_args} {overrides}',
            parameters=parameters,
        )
        diagnostic = log_file.read_text(encoding="utf-8")
        detected = False
        try:
            cases = ET.parse(results_file).findall(".//testcase")
            detected = (len(cases) == 1 and cases[0].get("name") == "RetentionRegisterTest"
                        and cases[0].get("classname") == "test_retention_register"
                        and cases[0].find("failure") is not None and cases[0].find("skipped") is None
                        and f"AssertionError: Protocol assertion failed: {expected}" in diagnostic)
        except (OSError, ET.ParseError):
            pass
        reports.append({"name": name, "expected_diagnostic": expected,
                        "status": "PASS" if detected else "NOT_RUN" if license_unavailable(diagnostic) else "FAIL",
                        "expected_test_failure": detected, "make_returncode": result.returncode, "log": str(log_file)})
        print(f"Protocol assertion {name}: {reports[-1]['status']}", flush=True)
    return reports


def check_invalid_parameters(args, build: Path, rtl: Path) -> list[dict]:
    return [parameter_guard(args, build, rtl, 'retention_register', name, parameters, expected)
            for name, parameters, expected in INVALID_PARAMETERS]


def main() -> int:
    args = parse_args('retention_register', __doc__, profiles=[profile[0] for profile in PROFILES], seed=20261011)
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    summary = {
        "status": "NOT_RUN", "framework": "PyUVM", "simulator": args.sim,
        "scope": "selected_profiles" if args.case else "width_reset_enable_matrix",
        "specification": "specs/common/mosaic-retention-register/README.md",
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "rtl": str(rtl),
        "profiles": [], "parameter_checks": [], "protocol_checks": [],
        "external_checks": dict.fromkeys((
            "hdl_sva", "formal", "commercial_lint", "cdc", "rdc", "dft", "vc_lp",
            "synthesis", "logical_equivalence", "physical_timing", "physical_power",
            "power_aware_simulation", "retention_supply_loss", "legal_power_state_cross",
            "approved_retention_cell_mapping", "power_sequence_integration", "physical_supply_connectivity",
        ), "NOT_RUN"),
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = verification_hashes(TEST_DIR)
        require_simulator(args)
        summary["status"] = "FAIL"
        for index, (name, width, reset_class, reset_value, asynchronous, enabled) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            parameters = {"WIDTH": width, "RESET_VALUE": reset_value, "ASYNC_RESET": asynchronous, "HAS_ENABLE": enabled}
            case = build / name
            # Sized reset literals preserve the complete value through WIDTH=128.
            # Quote apostrophes for the Make recipe shell.
            prefix = "-Pretention_register." if args.sim == "icarus" else "-pvalue+retention_register."
            compiler_parameters = {"WIDTH": str(width), "RESET_VALUE": f"{width}'h{reset_value:x}",
                                   "ASYNC_RESET": str(asynchronous), "HAS_ENABLE": str(enabled)}
            overrides = " ".join(shlex.quote(f"{prefix}{key}={value}") for key, value in compiler_parameters.items())
            print(f'Running {name}: {parameters}, seed={args.seed + index}', flush=True)
            (result, log_file, results_file, coverage_file) = run_simulation(
                args, ROOT, TEST_DIR, 'retention_register', 'test_retention_register', 'RetentionRegisterTest', case, rtl,
                environment={
                    'RETENTION_REGISTER_WIDTH': str(width), 'RETENTION_REGISTER_RESET_VALUE': str(reset_value),
                    'RETENTION_REGISTER_ASYNC_RESET': str(asynchronous),
                    'RETENTION_REGISTER_HAS_ENABLE': str(enabled), 'RETENTION_REGISTER_CHECK_IMAGE': '1',
                    'RETENTION_REGISTER_PROTOCOL_PROBE': '', 'RETENTION_REGISTER_SEED': str(args.seed + index),
                    'RETENTION_REGISTER_RANDOM_CYCLES': str(args.random_cycles),
                },
                compile_args=f'{args.compile_args} {overrides}',
                parameters=parameters,
            )
            report = {"status": "FAIL", "name": name, "parameters": parameters, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                passed_test(results_file, 'RetentionRegisterTest', 'test_retention_register')
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if coverage["status"] != "PASS" or coverage["parameters"] != parameters or coverage["reset_class"] != reset_class or coverage["portable_image_assertions"] != "PASS" or not all(coverage["goals"].values()):
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
        summary["protocol_checks"] = check_protocol_probes(args, build, rtl)
        reports = (*summary["profiles"], *summary["parameter_checks"], *summary["protocol_checks"])
        complete = len(summary["profiles"]) == (len(set(args.case)) if args.case else len(PROFILES)) and len(summary["parameter_checks"]) == len(INVALID_PARAMETERS) and len(summary["protocol_checks"]) == len(PROTOCOL_PROBES)
        summary["status"] = campaign_status(reports, complete)
        if not args.case:
            crossed = {(profile["parameters"]["WIDTH"], profile["reset_class"], profile["parameters"]["ASYNC_RESET"], profile["parameters"]["HAS_ENABLE"])
                       for profile in summary["profiles"] if profile["status"] == "PASS"}
            summary["matrix_goals"] = {"width_reset_class_reset_style_enable_cross": crossed == {(width, reset_class, asynchronous, enabled) for _, width, reset_class, _, asynchronous, enabled in PROFILES}}
            if summary["status"] == "PASS" and not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"

    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"Retention register regression could not run: {error}", file=sys.stderr)
    finally:
        finish_summary(summary_file, summary, 'Retention register')
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
