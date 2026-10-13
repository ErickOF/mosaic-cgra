"""Simulator execution and evidence validation shared by module campaigns."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import xml.etree.ElementTree as ET


def parse_args(module, description, profiles=None, seed=20261011, *, rtl_category="common"):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--sim", choices=("vcs", "icarus"), default="vcs")
    parser.add_argument("--build-dir", type=Path, required=True)
    root = Path(__file__).resolve().parents[4]
    parser.add_argument("--rtl", type=Path, default=root / f"src/rtl/{rtl_category}/{module}.sv")
    parser.add_argument("--seed", type=int, default=seed)
    parser.add_argument("--random-cycles", type=int, default=2000)
    parser.add_argument("--compile-args", default="")
    parser.add_argument("--sim-args", default="")
    parser.add_argument("--sim-bin-dir", type=Path)
    parser.add_argument("--make", default="make")
    if profiles is not None:
        parser.add_argument("--case", action="append", choices=profiles)
    args = parser.parse_args()
    if args.random_cycles < 1000:
        parser.error("--random-cycles must be at least 1000")
    if args.sim_bin_dir:
        args.sim_bin_dir = args.sim_bin_dir.resolve()
    return args


def license_unavailable(diagnostic: str) -> bool:
    return any(fragment in diagnostic.lower() for fragment in (
        "license checkout failed", "license check out failed", "no valid license",
        "cannot connect to license server", "unable to checkout a license",
    ))


def require_simulator(args):
    binaries = ("vcs",) if args.sim == "vcs" else ("iverilog", "vvp")
    missing = [binary for binary in binaries if shutil.which(
        binary, path=str(args.sim_bin_dir) if args.sim_bin_dir else None) is None]
    if missing:
        raise FileNotFoundError(f"Simulator executable(s) missing: {', '.join(missing)}")


def verification_hashes(test_dir):
    """Include every component and shared helper in the campaign's provenance."""
    library = Path(__file__).resolve().parent
    files = {str(path.relative_to(test_dir)): path for path in sorted(test_dir.rglob("*.py"))}
    files.update({f"shared/{path.name}": path for path in sorted(library.glob("*.py"))})
    files.update({path.name: path for path in sorted(test_dir.glob("*.sv"))})
    files["Makefile"] = library.parents[3] / "Makefile"
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in files.items()}


def run_simulation(args, root, test_dir, top, module, test_class, build, sources,
                   *, environment, parameters=None, compile_args=None):
    """Force fresh parameters/results and execute precisely one decorated test."""
    build = Path(build)
    build.mkdir(parents=True, exist_ok=True)
    results, coverage = build / "results.xml", build / "coverage.json"
    results.unlink(missing_ok=True)
    coverage.unlink(missing_ok=True)
    parameter_file = build / "parameters.json"
    if parameters is None:
        parameters = json.loads(parameter_file.read_text()) if parameter_file.exists() else {}
    parameter_file.write_text(json.dumps(parameters) + "\n", encoding="utf-8")
    command = [
        args.make, "--no-print-directory", "-C", str(root), "-f", "Makefile", "pyuvm",
        f"SIM={args.sim}", f"PYTHON_BIN={sys.executable}", f"COCOTB_TOPLEVEL={top}",
        f"COCOTB_TEST_MODULES={module}", f"PYUVM_TEST_DIR={test_dir}",
        f"COCOTB_TEST_FILTER=^{module}\\.{test_class}$", "COCOTB_TESTCASE=",
        f"VERILOG_SOURCES={sources}", f"SIM_BUILD={build}", f"COCOTB_RESULTS_FILE={results}",
        f"CUSTOM_COMPILE_DEPS={parameter_file}",
        f"COMPILE_ARGS={args.compile_args if compile_args is None else compile_args}", f"SIM_ARGS={args.sim_args}",
    ]
    if args.sim_bin_dir:
        variable = "VCS_BIN_DIR" if args.sim == "vcs" else "ICARUS_BIN_DIR"
        command.append(f"{variable}={args.sim_bin_dir}")
    process_environment = os.environ.copy()
    coverage_keys = [key.removesuffix("_SEED") + "_COVERAGE_FILE" for key in environment if key.endswith("_SEED")]
    assert len(coverage_keys) == 1, "A simulation must identify one suite seed namespace"
    environment = {**environment, coverage_keys[0]: str(coverage)}
    process_environment.update(environment)
    log_file = build / "simulation.log"
    with log_file.open("w", encoding="utf-8") as log:
        result = subprocess.run(command, env=process_environment, stdout=log, stderr=subprocess.STDOUT)
    return result, log_file, results, coverage


def passed_test(results, test_class, module):
    cases = ET.parse(results).findall(".//testcase")
    if (len(cases) != 1 or cases[0].get("name") != test_class
            or cases[0].get("classname") != module):
        raise ValueError("The expected PyUVM test did not run exactly once")
    if any(cases[0].find(tag) is not None for tag in ("failure", "error", "skipped")):
        raise ValueError("The PyUVM test failed or was skipped")
    return cases[0]


def parameter_guard(args, build, rtl, module, name, parameters, expected_guard,
                    *, wrapper_source=None, allow_startup=False, dependencies=()):
    """Keep strict elaboration and explicitly permitted startup guards distinct."""
    case = build / "invalid_parameters" / name
    case.mkdir(parents=True, exist_ok=True)
    top = f"{module}_invalid_parameters"
    if wrapper_source is None:
        overrides = ", ".join(f".{key}({value})" for key, value in parameters.items())
        wrapper_source = f"module {top};\n{module} #({overrides}) dut ();\nendmodule\n"
    else:
        # Existing fixtures may provide ports or a fallback startup fatal.
        import re
        top = re.search(r"module\s+(\w+)", wrapper_source)[1]
    wrapper = case / "invalid_parameters.sv"
    wrapper.write_text(wrapper_source, encoding="utf-8")
    search = str(args.sim_bin_dir) if args.sim_bin_dir else None
    compiler = shutil.which("vcs" if args.sim == "vcs" else "iverilog", path=search)
    executable = case / ("simv" if args.sim == "vcs" else "sim.vvp")
    command = ([compiler, "-g2012", "-s", top, *( ["-o", str(executable)] if allow_startup else ["-tnull"] )]
               if args.sim == "icarus" else [compiler, "-full64", "-sverilog", "-top", top, "-o", str(executable)])
    log_file = case / ("guard.log" if allow_startup else "elaboration.log")
    runtime_code = None
    with log_file.open("w", encoding="utf-8") as log:
        compiled = subprocess.run([*command, *shlex.split(args.compile_args),
                                   *(str(source) for source in dependencies), str(rtl), str(wrapper)],
                                  cwd=case, stdout=log, stderr=subprocess.STDOUT)
        if allow_startup and compiled.returncode == 0:
            runtime = [shutil.which("vvp", path=search), str(executable)] if args.sim == "icarus" else [str(executable)]
            runtime_code = subprocess.run(runtime, cwd=case, stdout=log, stderr=subprocess.STDOUT).returncode
    diagnostic = log_file.read_text(encoding="utf-8")
    rejected = expected_guard in diagnostic and (compiled.returncode != 0 or runtime_code not in (None, 0))
    report = dict(name=name, parameters=parameters, expected_guard=expected_guard,
                  status="NOT_RUN" if license_unavailable(diagnostic) else "PASS" if rejected else "FAIL",
                  compiler_returncode=compiled.returncode, runtime_returncode=runtime_code,
                  stage="elaboration" if rejected and compiled.returncode else "simulation_startup" if rejected else None,
                  log=str(log_file))
    print(f"Invalid parameters {name}: {report['status']}", flush=True)
    return report


def campaign_status(reports, complete):
    if complete and all(report["status"] == "PASS" for report in reports):
        return "PASS"
    if complete and any(report["status"] == "NOT_RUN" for report in reports) and all(
            report["status"] in ("PASS", "NOT_RUN") for report in reports):
        return "NOT_RUN"
    return "FAIL"


def finish_summary(path, summary, label):
    summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"{label} regression {summary['status']}: {path}", flush=True)
