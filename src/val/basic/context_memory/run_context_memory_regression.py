"""Run context lifecycle profiles, native elaboration guards, and live assertions."""

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
DEPENDENCIES = (ROOT / "src/rtl/common/decoder.sv", ROOT / "src/rtl/common/dff.sv")
CONFIGURATIONS = (
    ("minimum", 1, 1, 1, 1), ("spatial", 64, 1, 16, 2), ("baseline", 256, 4, 32, 2),
    ("non_power_three", 24, 3, 8, 3), ("fine_grain", 40, 5, 1, 4),
    ("whole_word", 64, 8, 64, 1), ("exploration", 32, 32, 8, 4),
)
NAMES = ("CONTEXT_WIDTH", "CONTEXT_DEPTH", "WRITE_SLICE_WIDTH", "NUM_READ_PORTS", "HAS_RAW_READBACK", "ASYNC_RESET")
PROFILES = tuple((f"{name}_raw{raw}_{'async' if asynchronous else 'sync'}", width, depth, slice_width, ports, raw, asynchronous)
                 for name, width, depth, slice_width, ports in CONFIGURATIONS for raw, asynchronous in product((0, 1), repeat=2))
PROFILES += tuple((f"depth{depth}_exploration", 32, depth, 8, 2, 1, 0)
                  for depth in range(1, 33) if depth not in {profile[2] for profile in CONFIGURATIONS})
INVALID = (
    *((f"{name.lower()}_{value}", {name: value}) for name in NAMES[:4] for value in (0, -1)),
    ("nondivisible", {"CONTEXT_WIDTH": 10, "WRITE_SLICE_WIDTH": 3}),
    ("slice_exceeds_word", {"CONTEXT_WIDTH": 8, "WRITE_SLICE_WIDTH": 16}),
    *((f"{name.lower()}_{label}", {name: value}) for name in NAMES[4:] for label, value in (
        ("two", 2), ("negative", -1), ("oversized", "33'h100000000"), ("x", "32'bx"), ("z", "32'bz"))),
    *((f"{name.lower()}_{state}", {name: f"32'b{state}"}) for name in NAMES[:4] for state in "xz"),
)
PROBES = tuple((f"{name}_{state}", 1, f"{name}:{state}", name + (":0" if name in ("read_enable", "read_raw", "read_address") else ""))
               for name in ("i_rstb", "write_enable", "commit_enable", "invalidate_enable", "read_enable", "read_raw",
                            "write_mask", "write_data", "write_address", "commit_address", "invalidate_address", "read_address") for state in "xz")
PROBES += tuple((f"{name}_range", 1, f"{name}:range", name + (":0" if name == "read_address" else "")) for name in ("write_address", "commit_address", "invalidate_address", "read_address"))
PROBES += tuple((f"raw_forbidden_{state}", 0, f"raw_forbidden:{state}", "raw_forbidden:0") for state in "1xz")
PROBES += (("commit_invalidate_collision", 1, "commit_invalidate_collision:1", "commit_invalidate_collision"),
           ("commit_unknown_word", 1, "commit_data_unknown:1", "commit_data_unknown"))


def simulate(args, build, rtl, parameters, seed, *, probe=""):
    prefix = "-Pcontext_memory." if args.sim == "icarus" else "-pvalue+context_memory."
    flags = " ".join(shlex.quote(f"{prefix}{name}={value}") for name, value in parameters.items())
    return run_simulation(args, ROOT, TEST_DIR, "context_memory", "test_context_memory", "ContextMemoryTest", build,
        " ".join(str(source) for source in (*DEPENDENCIES, rtl)),
        parameters=parameters, compile_args=f"{args.compile_args} {flags}",
        environment={**{f"CONTEXT_MEMORY_{name}": str(value) for name, value in parameters.items()},
            "CONTEXT_MEMORY_SEED": str(seed), "CONTEXT_MEMORY_RANDOM_CYCLES": str(args.random_cycles),
            "CONTEXT_MEMORY_CHECK_INTERNALS": "1", "CONTEXT_MEMORY_ASSERTION_PROBE": probe})


def assertion_probes(args, build, rtl):
    reports = []
    for name, raw, probe, expected in PROBES:
        parameters = dict(zip(NAMES, (16, 3, 4, 2, raw, 0)))
        result, log_file, results, _ = simulate(args, build / "assertion_probes" / name, rtl, parameters, args.seed, probe=probe)
        diagnostic = log_file.read_text(encoding="utf-8")
        detected = False
        try:
            cases = ET.parse(results).findall(".//testcase")
            detected = (len(cases) == 1 and cases[0].get("name") == "ContextMemoryTest" and cases[0].get("classname") == "test_context_memory"
                and cases[0].find("failure") is not None and cases[0].find("skipped") is None and result.returncode != 0
                and f"AssertionError: Protocol assertion failed: {expected}" in diagnostic)
        except (OSError, ET.ParseError):
            pass
        reports.append(dict(name=name, status="PASS" if detected else "NOT_RUN" if license_unavailable(diagnostic) else "FAIL",
                            expected_assertion=expected, expected_test_failure=detected, log=str(log_file)))
        print(f"Assertion {name}: {reports[-1]['status']}", flush=True)
    return reports


def main():
    args = parse_args("context_memory", __doc__, profiles=[profile[0] for profile in PROFILES], seed=20261012, rtl_category="basic")
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    summary = dict(status="NOT_RUN", framework="PyUVM", simulator=args.sim, rtl=str(rtl),
        scope="selected_profiles" if args.case else "representative_dimensions_and_all_exploration_depths",
        specification="specs/basic/mosaic-context-memory/README.md", started_at_utc=datetime.now(timezone.utc).isoformat(),
        profiles=[], parameter_checks=[], assertion_probes=[],
        external_checks=dict.fromkeys(("hdl_sva", "formal", "commercial_lint", "cdc", "rdc", "dft", "vc_lp", "technology_synthesis",
        "macro_equivalence", "physical_timing", "physical_power", "semantic_configuration_validation", "execution_safe_point",
        "reset_synchronizer_integration", "contracts_manifest"), "NOT_RUN"))
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["dependency_sha256"] = {str(source.relative_to(ROOT)): hashlib.sha256(source.read_bytes()).hexdigest() for source in DEPENDENCIES}
        summary["verification_sha256"] = verification_hashes(TEST_DIR)
        require_simulator(args)
        summary["status"] = "FAIL"
        for index, (name, *values) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            parameters = dict(zip(NAMES, values))
            print(f"Running {name}, seed={args.seed + index}", flush=True)
            result, log_file, results, coverage_file = simulate(args, build / name, rtl, parameters, args.seed + index)
            report = dict(name=name, status="FAIL", parameters=parameters, log=str(log_file))
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                passed_test(results, "ContextMemoryTest", "test_context_memory")
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if (coverage["status"] != "PASS" or coverage["parameters"] != parameters or coverage["structural_assertions"] != "PASS"
                        or not coverage["goals"] or not all(coverage["goals"].values())):
                    raise ValueError("Coverage or elaborated settings did not match")
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
        summary["parameter_checks"] = [parameter_guard(args, build, rtl, "context_memory", name, parameters,
            "context_memory_parameters_must_be_valid", dependencies=DEPENDENCIES) for name, parameters in INVALID]
        summary["assertion_probes"] = assertion_probes(args, build, rtl)
        complete = len(summary["profiles"]) == (len(set(args.case)) if args.case else len(PROFILES)) and len(summary["parameter_checks"]) == len(INVALID) and len(summary["assertion_probes"]) == len(PROBES)
        summary["status"] = campaign_status((*summary["profiles"], *summary["parameter_checks"], *summary["assertion_probes"]), complete)
        if not args.case:
            passed = [report for report in summary["profiles"] if report["status"] == "PASS"]
            summary["matrix_goals"] = dict(all_profiles={report["name"] for report in passed} == {profile[0] for profile in PROFILES},
                every_exploration_depth={report["parameters"]["CONTEXT_DEPTH"] for report in passed} == set(range(1, 33)),
                raw_reset_cross={(report["parameters"]["HAS_RAW_READBACK"], report["parameters"]["ASYNC_RESET"]) for report in passed} == set(product((0, 1), repeat=2)))
            if summary["status"] == "PASS" and not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"Context memory regression could not run: {error}", file=sys.stderr)
    finally:
        finish_summary(summary_file, summary, "Context memory")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
