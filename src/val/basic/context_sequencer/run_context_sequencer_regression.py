"""Run sequencer profiles, strict parameter guards, live assertions, and memory integration."""

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
DEPENDENCIES = tuple(ROOT / name for name in (
    "src/rtl/basic/context_sequencer_pkg.sv", "src/rtl/common/dff.sv", "src/rtl/common/counter.sv"))
MEMORY_DEPENDENCIES = tuple(ROOT / name for name in ("src/rtl/common/decoder.sv", "src/rtl/basic/context_memory.sv"))
NAMES = ("CONTEXT_DEPTH", "LOOP_COUNT_WIDTH", "HAS_LOOP", "HAS_SUSPEND", "HAS_EXTERNAL_SWITCH", "ASYNC_RESET")
PROFILES = tuple((f"features_l{loop}s{suspend}w{switch}_{'async' if asynchronous else 'sync'}", 4, 4, loop, suspend, switch, asynchronous)
                 for loop, suspend, switch, asynchronous in product((0, 1), repeat=4))
PROFILES += tuple((f"{name}_{'async' if asynchronous else 'sync'}", depth, count_width, loop, suspend, switch, asynchronous)
                  for name, depth, count_width, loop, suspend, switch in (
                      ("minimum", 1, 1, 0, 0, 0), ("spatial", 1, 2, 1, 1, 1),
                      ("non_power_three", 3, 3, 1, 1, 1), ("single_visit", 5, 1, 1, 1, 1),
                      ("default", 4, 16, 1, 1, 1), ("exploration", 32, 8, 1, 1, 1))
                  for asynchronous in (0, 1))
PROFILES += tuple((f"depth{depth}_exploration", depth, 4, 1, 1, 1, 0) for depth in range(1, 33)
                  if depth not in {1, 3, 4, 5, 32})
INTEGRATIONS = (("memory_spatial", 1, 2, 1, 1, 1, 0), ("memory_non_power_async", 3, 3, 1, 1, 1, 1),
                ("memory_baseline", 4, 4, 1, 1, 1, 0))
INVALID = (
    *((f"{name.lower()}_{value}", {name: value}) for name in NAMES[:2] for value in (0, -1)),
    *((f"{name.lower()}_{state}", {name: f"32'b{state}"}) for name in NAMES[:2] for state in "xz"),
    *((f"{name.lower()}_{label}", {name: value}) for name in NAMES[2:] for label, value in (
        ("two", 2), ("negative", -1), ("oversized", "33'h100000000"), ("x", "32'bx"), ("z", "32'bz"))),
)
PROBES = tuple((f"{name}_{state}", f"{name}:{state}", name, {})
               for name in ("i_rstb", "i_start_enable", "i_stop_request", "i_suspend_request", "i_resume_request",
                            "i_switch_request", "i_error_clear", "i_step_accepted") for state in "xz")
PROBES += tuple((f"{name}_{state}", f"{name}:{state}", expected, {})
                for name, expected in (("active_valid", "i_active_context_valid"), ("candidate_valid", "i_candidate_context_valid"),
                                       ("i_safe_point", "i_safe_point"), ("start_address", "i_start_context"),
                                       ("switch_address", "i_switch_context"), ("transition_target", "transition_target"),
                                       ("loop_count", "loop_count"), ("transition_mode", "transition_mode")) for state in "xz")
PROBES += tuple((f"async_reset_{state}", f"i_rstb:{state}", "i_rstb", {"ASYNC_RESET": 1}) for state in "xz")
PROBES += tuple((name, probe, expected, overrides) for name, probe, expected, overrides in (
    *((f"unsupported_mode_{mode}", f"transition_mode:{mode}", "transition_mode", {}) for mode in (5, 6, 7)),
    ("zero_loop_count", "loop_count:0", "loop_count", {}),
    ("active_invalid", "active_invalid:1", "active_invalid", {}),
    ("resume_invalid", "resume_invalid:1", "resume_invalid", {}),
    ("quiescing_step", "quiescing_step:1", "step_without_execution", {}),
    ("command_conflict", "command_conflict:1", "command_conflict", {}),
    ("nested_loop", "nested_loop:1", "nested_loop", {}),
    ("live_switch", "live_switch:1", "command_state:i_switch_request", {}),
    ("start_address_range", "start_address:3", "i_start_context", {}),
    ("switch_address_range", "switch_address:3", "i_switch_context", {}),
    ("jump_address_range", "transition_target:3", "transition_target", {}),
    ("active_start", "active_start:1", "command_state:i_start_enable", {}),
    *((f"idle_{field}", f"{field}:1", "command_state:" + field, {}) for field in (
        "i_stop_request", "i_suspend_request", "i_resume_request", "i_switch_request", "i_error_clear")),
    ("disabled_suspend", "disabled_suspend:1", "command_state:i_suspend_request", {"HAS_SUSPEND": 0}),
    ("disabled_switch", "disabled_switch:1", "command_state:i_switch_request", {"HAS_EXTERNAL_SWITCH": 0}),
    ("disabled_loop", "loop_count:2", "transition_mode", {"HAS_LOOP": 0}),
))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def simulate(args, build, rtl, parameters, seed, *, probe="", integration=False):
    top = "context_sequencer_memory_tb" if integration else "context_sequencer"
    module = "test_context_sequencer_memory" if integration else "test_context_sequencer"
    test = "ContextSequencerMemoryTest" if integration else "ContextSequencerTest"
    prefix = f"-P{top}." if args.sim == "icarus" else f"-pvalue+{top}."
    flags = " ".join(shlex.quote(f"{prefix}{name}={value}") for name, value in parameters.items())
    sources = (*DEPENDENCIES, *MEMORY_DEPENDENCIES, rtl, TEST_DIR / "context_sequencer_memory_tb.sv") if integration else (*DEPENDENCIES, rtl)
    return run_simulation(args, ROOT, TEST_DIR, top, module, test, build, " ".join(map(str, sources)),
        parameters=parameters, compile_args=f"{args.compile_args} {flags}",
        environment={**{f"CONTEXT_SEQUENCER_{name}": str(value) for name, value in parameters.items()},
            "CONTEXT_SEQUENCER_SEED": str(seed), "CONTEXT_SEQUENCER_RANDOM_CYCLES": str(args.random_cycles),
            "CONTEXT_SEQUENCER_CHECK_INTERNALS": "1", "CONTEXT_SEQUENCER_ASSERTION_PROBE": probe})


def assertion_probes(args, build, rtl):
    reports = []
    for name, probe, expected, overrides in PROBES:
        parameters = dict(zip(NAMES, (3, 3, 1, 1, 1, 0))) | overrides
        result, log_file, results, _ = simulate(args, build / "assertion_probes" / name, rtl, parameters, args.seed, probe=probe)
        diagnostic = log_file.read_text(encoding="utf-8")
        detected = False
        try:
            cases = ET.parse(results).findall(".//testcase")
            detected = (len(cases) == 1 and cases[0].get("name") == "ContextSequencerTest" and cases[0].get("classname") == "test_context_sequencer"
                        and cases[0].find("failure") is not None and cases[0].find("skipped") is None and result.returncode != 0
                        and f"AssertionError: Protocol assertion failed: {expected}" in diagnostic)
        except (OSError, ET.ParseError):
            pass
        reports.append(dict(name=name, status="PASS" if detected else "NOT_RUN" if license_unavailable(diagnostic) else "FAIL",
                            expected_test_failure=detected, expected_assertion=expected, log=str(log_file)))
        print(f"Assertion {name}: {reports[-1]['status']}", flush=True)
    return reports


def main():
    args = parse_args("context_sequencer", __doc__, profiles=[profile[0] for profile in (*PROFILES, *INTEGRATIONS)],
                      seed=20261012, rtl_category="basic")
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    summary = dict(status="NOT_RUN", framework="PyUVM", simulator=args.sim, rtl=str(rtl), interface_version=1,
        encoding_scope="repository_local", scope="selected_profiles" if args.case else "all_exploration_depths_feature_cross_and_memory_integration",
        specification="specs/basic/mosaic-context-sequencer/README.md", started_at_utc=datetime.now(timezone.utc).isoformat(),
        profiles=[], parameter_checks=[], assertion_probes=[],
        external_checks=dict.fromkeys(("hdl_sva", "formal", "commercial_lint", "cdc", "rdc", "dft", "vc_lp", "technology_synthesis",
                                      "sequential_equivalence", "physical_timing", "physical_power", "tile_safe_point_integration",
                                      "architectural_context_validation", "canonical_contracts", "reset_release_integration"), "NOT_RUN"))
    try:
        summary["rtl_sha256"] = digest(rtl)
        summary["dependency_sha256"] = {str(source.relative_to(ROOT)): digest(source) for source in (*DEPENDENCIES, *MEMORY_DEPENDENCIES)}
        summary["reference_dependency_sha256"] = {str(source.relative_to(ROOT)): digest(source) for source in
            (ROOT / "src/val/basic/context_memory/model.py", ROOT / "src/val/basic/context_memory/transaction.py")}
        summary["verification_sha256"] = verification_hashes(TEST_DIR)
        require_simulator(args)
        summary["status"] = "FAIL"
        for index, (name, *values) in enumerate((*PROFILES, *INTEGRATIONS)):
            if args.case and name not in args.case:
                continue
            parameters = dict(zip(NAMES, values))
            integration = name.startswith("memory_")
            print(f"Running {name}, seed={args.seed + index}", flush=True)
            result, log_file, results, coverage_file = simulate(args, build / name, rtl, parameters, args.seed + index, integration=integration)
            report = dict(name=name, status="FAIL", parameters=parameters, log=str(log_file), fixture="context_memory" if integration else "sequencer_unit")
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                passed_test(results, "ContextSequencerMemoryTest" if integration else "ContextSequencerTest",
                            "test_context_sequencer_memory" if integration else "test_context_sequencer")
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if (coverage["status"] != "PASS" or coverage["parameters"] != parameters or coverage["structural_assertions"] != "PASS"
                        or coverage["interface_version"] != 1 or not coverage["goals"] or not all(coverage["goals"].values())):
                    raise ValueError("Coverage, parameters, or local interface version did not match")
                if coverage["seed"] != args.seed + index or not integration and coverage["random_transactions"] != args.random_cycles:
                    raise ValueError("Random campaign settings did not match")
                report.update(coverage, name=name, log=str(log_file), coverage=str(coverage_file))
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                report["error"] = str(error)
                if license_unavailable(log_file.read_text(encoding="utf-8")):
                    report["status"] = "NOT_RUN"
                print("\n".join(log_file.read_text(encoding="utf-8").splitlines()[-25:]), flush=True)
            summary["profiles"].append(report)
            print(f"{name}: {report['status']}", flush=True)
        summary["parameter_checks"] = [parameter_guard(args, build, rtl, "context_sequencer", name, parameters,
            "context_sequencer_parameters_must_be_valid", dependencies=DEPENDENCIES) for name, parameters in INVALID]
        summary["assertion_probes"] = assertion_probes(args, build, rtl)
        complete = (len(summary["profiles"]) == (len(set(args.case)) if args.case else len(PROFILES) + len(INTEGRATIONS))
                    and len(summary["parameter_checks"]) == len(INVALID) and len(summary["assertion_probes"]) == len(PROBES))
        summary["status"] = campaign_status((*summary["profiles"], *summary["parameter_checks"], *summary["assertion_probes"]), complete)
        if not args.case:
            passed = [report for report in summary["profiles"] if report["status"] == "PASS"]
            units = [report for report in passed if report["fixture"] == "sequencer_unit"]
            summary["matrix_goals"] = dict(all_profiles={report["name"] for report in passed} == {profile[0] for profile in (*PROFILES, *INTEGRATIONS)},
                every_exploration_depth={report["parameters"]["CONTEXT_DEPTH"] for report in units} == set(range(1, 33)),
                feature_reset_cross={(report["parameters"]["HAS_LOOP"], report["parameters"]["HAS_SUSPEND"], report["parameters"]["HAS_EXTERNAL_SWITCH"], report["parameters"]["ASYNC_RESET"]) for report in units} == set(product((0, 1), repeat=4)),
                memory_integration={report["name"] for report in passed if report["fixture"] == "context_memory"} == {profile[0] for profile in INTEGRATIONS})
            if summary["status"] == "PASS" and not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"Context sequencer regression could not run: {error}", file=sys.stderr)
    finally:
        finish_summary(summary_file, summary, "Context sequencer")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
