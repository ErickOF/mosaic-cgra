"""Run representative async FIFO profiles, guards, and live assertion probes."""

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
    campaign_status, finish_summary, license_unavailable, parameter_guard, parse_args,
    passed_test, require_simulator, run_simulation, verification_hashes,
)


ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = (ROOT / "src/rtl/common/counter.sv", ROOT / "src/rtl/common/dff.sv")
# The specification defines no maximum released width/depth or release manifest.
# These are finite verification profiles, not an invented release limit.
PROFILES = (
    ("minimum", 1, 2, 2, 1, 0),
    ("depth4", 8, 4, 2, 3, 1),
    ("nominal", 32, 8, 2, 7, 1),
    ("wide_deep", 128, 32, 2, 31, 1),
    ("stages3", 32, 8, 3, 7, 1),
    ("stages4", 32, 8, 4, 7, 1),
    ("late_full_zero_empty", 32, 8, 3, 8, 0),
    ("early_full_high_empty", 32, 8, 4, 1, 7),
    ("narrow_deep", 1, 32, 4, 16, 16),
    ("wide_minimum", 128, 2, 3, 2, 0),
)
PARAMETER_NAMES = ("DATA_WIDTH", "DEPTH", "SYNC_STAGES", "ALMOST_FULL_LEVEL", "ALMOST_EMPTY_LEVEL")
INVALID = (
    ("zero_width", {"DATA_WIDTH": 0}),
    ("zero_depth", {"DEPTH": 0}),
    ("one_depth", {"DEPTH": 1}),
    ("non_power_two3", {"DEPTH": 3}),
    ("non_power_two6", {"DEPTH": 6}),
    ("zero_stages", {"SYNC_STAGES": 0}),
    ("one_stage", {"SYNC_STAGES": 1}),
    ("zero_almost_full", {"ALMOST_FULL_LEVEL": 0}),
    ("large_almost_full", {"ALMOST_FULL_LEVEL": 9}),
    ("large_almost_empty", {"ALMOST_EMPTY_LEVEL": 8}),
    ("negative_almost_empty", {"ALMOST_EMPTY_LEVEL": -1}),
)
PROBES = tuple(product(("i_w_valid", "i_r_ready", "i_w_rstb", "i_r_rstb",
                       "r_gray_sync", "w_gray_sync", "r_up_sync", "w_up_sync"), "xz"))


def simulate(args, build, rtl, parameters, seed, *, probe=""):
    prefix = "-Pasync_fifo." if args.sim == "icarus" else "-pvalue+async_fifo."
    flags = " ".join(shlex.quote(f"{prefix}{name}={value}") for name, value in parameters.items())
    return run_simulation(
        args, ROOT, TEST_DIR, "async_fifo", "test_async_fifo", "AsyncFifoTest", build,
        " ".join(str(source) for source in (*DEPENDENCIES, rtl)), parameters=parameters,
        compile_args=f"{args.compile_args} {flags}",
        environment={**{f"ASYNC_FIFO_{name}": str(value) for name, value in parameters.items()},
                     "ASYNC_FIFO_SEED": str(seed), "ASYNC_FIFO_RANDOM_CYCLES": str(args.random_cycles),
                     "ASYNC_FIFO_CHECK_INTERNALS": "1", "ASYNC_FIFO_ASSERTION_PROBE": probe},
    )


def assertion_probes(args, build, rtl):
    reports = []
    parameters = dict(zip(PARAMETER_NAMES, PROFILES[2][1:]))
    for name, value in PROBES:
        label = f"{name}_{value}"
        result, log_file, results, _ = simulate(args, build / "assertion_probes" / label, rtl, parameters,
                                              args.seed, probe=f"{name}:{value}")
        diagnostic = log_file.read_text(encoding="utf-8")
        expected = f"Known-control assertion failed: {name}" + ("[final]" if name.endswith("_sync") else "=")
        detected = False
        try:
            cases = ET.parse(results).findall(".//testcase")
            detected = (len(cases) == 1 and cases[0].get("name") == "AsyncFifoTest"
                        and cases[0].get("classname") == "test_async_fifo"
                        and cases[0].find("failure") is not None and cases[0].find("skipped") is None
                        and result.returncode != 0 and f"AssertionError: {expected}" in diagnostic)
        except (OSError, ET.ParseError):
            pass
        report = dict(name=label, status="PASS" if detected else "NOT_RUN" if license_unavailable(diagnostic) else "FAIL",
                      expected_test_failure=detected, expected_assertion=expected, log=str(log_file))
        reports.append(report)
        print(f"Assertion {label}: {report['status']}", flush=True)
    return reports


def main() -> int:
    args = parse_args("async_fifo", __doc__, profiles=[profile[0] for profile in PROFILES],
                      seed=20261012, rtl_category="basic")
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    summary = dict(status="NOT_RUN", framework="PyUVM", simulator=args.sim,
                   scope="selected_profiles" if args.case else "representative_parameter_matrix",
                   specification="specs/basic/mosaic-async-fifo/README.md", rtl=str(rtl),
                   started_at_utc=datetime.now(timezone.utc).isoformat(), profiles=[], parameter_checks=[], assertion_probes=[],
                   external_checks=dict.fromkeys(("hdl_sva", "formal_multiclock", "commercial_lint", "cdc", "rdc",
                   "gray_bus_skew", "mtbf", "technology_synthesis", "gate_sdf", "memory_macro_equivalence",
                   "physical_placement", "physical_power", "dft", "vc_lp", "released_profile_manifest"), "NOT_RUN"))
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["dependency_sha256"] = {str(source.relative_to(ROOT)): hashlib.sha256(source.read_bytes()).hexdigest() for source in DEPENDENCIES}
        summary["verification_sha256"] = verification_hashes(TEST_DIR)
        require_simulator(args)
        summary["status"] = "FAIL"
        for index, (name, *values) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            parameters = dict(zip(PARAMETER_NAMES, values))
            print(f"Running {name}, seed={args.seed + index}", flush=True)
            result, log_file, results, coverage_file = simulate(args, build / name, rtl, parameters, args.seed + index)
            report = dict(name=name, status="FAIL", parameters=parameters, log=str(log_file))
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                passed_test(results, "AsyncFifoTest", "test_async_fifo")
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if (coverage["status"] != "PASS" or coverage["parameters"] != parameters
                        or coverage["structural_assertions"] != "PASS" or not coverage["goals"] or not all(coverage["goals"].values())):
                    raise ValueError("Coverage or elaborated parameters did not match")
                if coverage["seed"] != args.seed + index or coverage["random_transactions"] != args.random_cycles:
                    raise ValueError("Random campaign settings did not match")
                report.update(coverage, name=name, log=str(log_file), coverage=str(coverage_file))
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                report["error"] = str(error)
                if license_unavailable(log_file.read_text(encoding="utf-8")):
                    report["status"] = "NOT_RUN"
                print("\n".join(log_file.read_text(encoding="utf-8").splitlines()[-20:]), flush=True)
            summary["profiles"].append(report)
            print(f"{name}: {report['status']}", flush=True)
        summary["parameter_checks"] = [parameter_guard(
            args, build, rtl, "async_fifo", name, parameters, "async_fifo_parameters_must_be_valid",
            dependencies=DEPENDENCIES,
        ) for name, parameters in INVALID]
        summary["assertion_probes"] = assertion_probes(args, build, rtl)
        reports = (*summary["profiles"], *summary["parameter_checks"], *summary["assertion_probes"])
        complete = (len(summary["profiles"]) == (len(set(args.case)) if args.case else len(PROFILES))
                    and len(summary["parameter_checks"]) == len(INVALID) and len(summary["assertion_probes"]) == len(PROBES))
        summary["status"] = campaign_status(reports, complete)
        if not args.case:
            summary["matrix_goals"] = dict(
                all_representative_profiles={report["name"] for report in summary["profiles"] if report["status"] == "PASS"} == {profile[0] for profile in PROFILES},
                widths={report["parameters"]["DATA_WIDTH"] for report in summary["profiles"]} == {1, 8, 32, 128},
                depths={report["parameters"]["DEPTH"] for report in summary["profiles"]} == {2, 4, 8, 32},
                synchronizer_depths={report["parameters"]["SYNC_STAGES"] for report in summary["profiles"]} == {2, 3, 4},
            )
            if summary["status"] == "PASS" and not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"Async FIFO regression could not run: {error}", file=sys.stderr)
    finally:
        finish_summary(summary_file, summary, "Async FIFO")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
