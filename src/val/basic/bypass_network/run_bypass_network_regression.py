"""Run connectivity/timing profiles, elaboration guards, and live protocol probes."""

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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bypass_network.config import connectivity


ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = (ROOT / "src/rtl/common/dff.sv",)
CONFIGURATIONS = (
    ("minimum", 1, 1, 1, "all"),
    ("two_sources", 8, 2, 2, "minimal"),
    ("three_sources", 16, 3, 3, "balanced"),
    ("nominal_minimal", 32, 5, 4, "minimal"),
    ("nominal_balanced", 32, 5, 4, "balanced"),
    ("nominal_flexible", 32, 5, 4, "flexible"),
    ("nominal_all", 32, 5, 4, "all"),
    ("wide_balanced", 64, 8, 4, "balanced"),
    ("vector_flexible", 128, 8, 4, "flexible"),
    ("default", 32, 8, 4, "all"),
)
TIMINGS = (("combinational", 0, 0), ("sync", 1, 0), ("async", 1, 1))
PROFILES = tuple((f"{name}_{timing}", width, sources, destinations, graph, registered, asynchronous)
                 for name, width, sources, destinations, graph in CONFIGURATIONS for timing, registered, asynchronous in TIMINGS)
PROFILES += (("combinational_async_parameter", 32, 5, 4, "balanced", 0, 1),)
INVALID = (
    *((name, parameters, "bypass_network_invalid_parameters") for name, parameters in (
        ("zero_width", {"DATA_WIDTH": 0}), ("zero_sources", {"NUM_SOURCES": 0}),
        ("zero_destinations", {"NUM_DESTINATIONS": 0}),
        ("invalid_registered", {"REGISTER_OUTPUTS": 2}), ("invalid_async", {"ASYNC_RESET": 2}),
        ("negative_registered", {"REGISTER_OUTPUTS": -1}), ("negative_async", {"ASYNC_RESET": -1}),
        ("oversized_registered", {"REGISTER_OUTPUTS": "33'h100000000"}),
        ("oversized_async", {"ASYNC_RESET": "33'h100000000"}),
        *((f"{parameter.lower()}_{state}", {parameter: f"32'b{state}"}) for parameter, state in product(("REGISTER_OUTPUTS", "ASYNC_RESET"), "xz")),
    )),
    ("empty_graph", {"NUM_SOURCES": 3, "NUM_DESTINATIONS": 2, "CONNECTIVITY_MASK": "6'b000000"}, "bypass_network_destination_requires_an_edge"),
    ("empty_first_row", {"NUM_SOURCES": 3, "NUM_DESTINATIONS": 2, "CONNECTIVITY_MASK": "6'b111000"}, "bypass_network_destination_requires_an_edge"),
    ("empty_last_row", {"NUM_SOURCES": 3, "NUM_DESTINATIONS": 2, "CONNECTIVITY_MASK": "6'b000111"}, "bypass_network_destination_requires_an_edge"),
    *((f"unknown_mask_{state}", {"NUM_SOURCES": 3, "NUM_DESTINATIONS": 2, "CONNECTIVITY_MASK": f"6'b11{state}111"}, "bypass_network_connectivity_must_be_known") for state in "xz"),
)
PROBES = tuple((f"{timing}_{name}_{state}", bool(registered), f"{name}:{state}",
                f"Protocol assertion failed: {name}" + ("" if name in ("i_rstb", "i_flush") else ":0"))
               for timing, registered in (("combinational", 0), ("registered", 1))
               for name in (("unknown_select", "source_valid", "source_data", "destination_enable")
                            + (("capture_enable", "i_rstb", "i_flush") if registered else ()))
               for state in "xz")
PROBES += tuple((f"{timing}_{name}", bool(registered), f"{name}:1", f"Protocol assertion failed: {name}:0")
                for timing, registered in (("combinational", 0), ("registered", 1)) for name in ("disconnected", "out_of_range"))


def parameters_for(profile):
    _, width, sources, destinations, graph, registered, asynchronous = profile
    return dict(DATA_WIDTH=width, NUM_SOURCES=sources, NUM_DESTINATIONS=destinations,
                CONNECTIVITY_MASK=connectivity(sources, destinations, graph),
                REGISTER_OUTPUTS=registered, ASYNC_RESET=asynchronous)


def simulate(args, build, rtl, parameters, seed, *, graph="custom", probe=""):
    prefix = "-Pbypass_network." if args.sim == "icarus" else "-pvalue+bypass_network."
    literals = {name: str(value) for name, value in parameters.items()}
    mask_width = parameters["NUM_SOURCES"] * parameters["NUM_DESTINATIONS"]
    literals["CONNECTIVITY_MASK"] = f"{mask_width}'h{parameters['CONNECTIVITY_MASK']:x}"
    overrides = " ".join(shlex.quote(f"{prefix}{name}={literal}") for name, literal in literals.items())
    return run_simulation(
        args, ROOT, TEST_DIR, "bypass_network", "test_bypass_network", "BypassNetworkTest", build,
        " ".join(str(source) for source in (*DEPENDENCIES, rtl)), parameters=parameters,
        compile_args=f"{args.compile_args} {overrides}",
        environment={**{f"BYPASS_NETWORK_{name}": str(value) for name, value in parameters.items()},
                     "BYPASS_NETWORK_SEED": str(seed), "BYPASS_NETWORK_RANDOM_CYCLES": str(args.random_cycles),
                     "BYPASS_NETWORK_GRAPH": graph, "BYPASS_NETWORK_CHECK_INTERNALS": "1", "BYPASS_NETWORK_ASSERTION_PROBE": probe},
    )


def assertion_probes(args, build, rtl):
    reports = []
    for name, registered, probe, expected in PROBES:
        parameters = dict(DATA_WIDTH=8, NUM_SOURCES=3, NUM_DESTINATIONS=2,
                          CONNECTIVITY_MASK=connectivity(3, 2, "minimal"), REGISTER_OUTPUTS=int(registered), ASYNC_RESET=0)
        result, log_file, results, _ = simulate(args, build / "assertion_probes" / name, rtl, parameters, args.seed, probe=probe)
        diagnostic = log_file.read_text(encoding="utf-8")
        detected = False
        try:
            cases = ET.parse(results).findall(".//testcase")
            detected = (len(cases) == 1 and cases[0].get("name") == "BypassNetworkTest"
                        and cases[0].get("classname") == "test_bypass_network" and cases[0].find("failure") is not None
                        and cases[0].find("skipped") is None and result.returncode != 0
                        and f"AssertionError: {expected}" in diagnostic)
        except (OSError, ET.ParseError):
            pass
        reports.append(dict(name=name, status="PASS" if detected else "NOT_RUN" if license_unavailable(diagnostic) else "FAIL",
                            expected_assertion=expected, expected_test_failure=detected, log=str(log_file)))
        print(f"Assertion {name}: {reports[-1]['status']}", flush=True)
    return reports


def main() -> int:
    args = parse_args("bypass_network", __doc__, profiles=[profile[0] for profile in PROFILES], seed=20261012, rtl_category="basic")
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    summary = dict(status="NOT_RUN", framework="PyUVM", simulator=args.sim,
                   scope="selected_profiles" if args.case else "representative_connectivity_timing_matrix",
                   specification="specs/basic/mosaic-bypass-network/README.md", rtl=str(rtl),
                   started_at_utc=datetime.now(timezone.utc).isoformat(), profiles=[], parameter_checks=[], assertion_probes=[],
                   external_checks=dict.fromkeys(("hdl_sva", "formal", "commercial_lint", "cdc", "rdc", "dft", "vc_lp",
                   "technology_synthesis", "physical_timing", "physical_power", "tile_context_protocol", "tile_feedback_cycle_analysis",
                   "released_tile_graph_integration", "contracts_manifest"), "NOT_RUN"))
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["dependency_sha256"] = {str(source.relative_to(ROOT)): hashlib.sha256(source.read_bytes()).hexdigest() for source in DEPENDENCIES}
        summary["verification_sha256"] = verification_hashes(TEST_DIR)
        require_simulator(args)
        summary["status"] = "FAIL"
        for index, profile in enumerate(PROFILES):
            name, _, _, _, graph, _, _ = profile
            if args.case and name not in args.case:
                continue
            parameters = parameters_for(profile)
            print(f"Running {name}, seed={args.seed + index}", flush=True)
            result, log_file, results, coverage_file = simulate(args, build / name, rtl, parameters, args.seed + index, graph=graph)
            report = dict(name=name, status="FAIL", parameters=parameters, graph=graph, log=str(log_file))
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                passed_test(results, "BypassNetworkTest", "test_bypass_network")
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if (coverage["status"] != "PASS" or coverage["parameters"] != parameters or coverage["graph"] != graph
                        or coverage["structural_assertions"] != "PASS" or not coverage["goals"] or not all(coverage["goals"].values())):
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
        summary["parameter_checks"] = []
        for name, parameters, expected in INVALID:
            overrides = ", ".join(f".{key}({value})" for key, value in parameters.items())
            # Keep the fixture name distinct from the unresolved guard module.
            wrapper = f"module bypass_network_guard_fixture;\nbypass_network #({overrides}) dut ();\nendmodule\n"
            summary["parameter_checks"].append(parameter_guard(
                args, build, rtl, "bypass_network", name, parameters, expected,
                dependencies=DEPENDENCIES, wrapper_source=wrapper))
        summary["assertion_probes"] = assertion_probes(args, build, rtl)
        reports = (*summary["profiles"], *summary["parameter_checks"], *summary["assertion_probes"])
        complete = (len(summary["profiles"]) == (len(set(args.case)) if args.case else len(PROFILES))
                    and len(summary["parameter_checks"]) == len(INVALID) and len(summary["assertion_probes"]) == len(PROBES))
        summary["status"] = campaign_status(reports, complete)
        if not args.case:
            crossed = {(report["graph"], report["parameters"]["REGISTER_OUTPUTS"]) for report in summary["profiles"] if report["status"] == "PASS"}
            summary["matrix_goals"] = dict(
                every_representative_profile={report["name"] for report in summary["profiles"] if report["status"] == "PASS"} == {profile[0] for profile in PROFILES},
                connectivity_timing_cross=crossed == set(product(("minimal", "balanced", "flexible", "all"), (0, 1))),
            )
            if summary["status"] == "PASS" and not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"Bypass network regression could not run: {error}", file=sys.stderr)
    finally:
        finish_summary(summary_file, summary, "Bypass network")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
