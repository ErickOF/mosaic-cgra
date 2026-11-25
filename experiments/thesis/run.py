"""Plan, execute and collect the thesis experiment campaign (Python/PyUVM only)."""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from cases import ROOT, architecture, campaign, digest, scenarios, workload
from bundle import generate
from results import collect
from schedule import grouping_candidates
from flavor.generate import digest as file_digest, verify_bundle
from flavor.model import dumps

sys.path.insert(0, str(ROOT / "src/val/lib"))
from mosaic_uvm.regression import passed_test, require_simulator, run_simulation


def save(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def provenance():
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    paths = [*Path(__file__).parent.rglob("*.py"), Path(__file__).with_name("campaign.toml"),
             ROOT / "Makefile", *list((ROOT / "src/val/mosaic_blocks").glob("*/model.py")),
             *list((ROOT / "src/val/mosaic_blocks").glob("*/layout.py")),
             ROOT / "src/val/mosaic_blocks/flavor/driver.py"]
    return dict(git_revision=revision, verification_sha256={str(p.relative_to(ROOT)): file_digest(p)
                for p in sorted(paths)}, dirty=bool(subprocess.check_output(
                    ["git", "status", "--porcelain"], cwd=ROOT, text=True)))


def plan(output):
    config = campaign()
    variants = ("H", "M", *(f"M{n}_{place}" for n in config["candidate_vct_counts"]
                            for place in config["candidate_placements"]))
    records = []
    from flavor.model import resolve
    for name in variants:
        document = architecture(name)
        resolved, geometry = resolve(document)
        path = output / "descriptors" / f"{name}.toml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(dumps(document))
        records.append(dict(variant=name, descriptor=str(path.relative_to(output)),
            architecture_sha256=digest(resolved), geometry={k: v for k, v in geometry.items()
                                                           if k != "native"},
            tiles=resolved["cluster"]["tiles"],
            grouping_candidates=grouping_candidates(resolved["cluster"])))
    cases = [workload(family, count, role=role)
        for family, settings in config["workloads"].items()
        for role, key in (("characterization", "characterization_sizes"),
                          ("reserved", "reserved_sizes")) for count in settings[key]]
    record = dict(schema=config["schema"], provenance=provenance(), variants=records,
        cases=cases, experiments=config["experiments"],
        tools={name: shutil.which(name) for name in ("iverilog", "vvp", "vcs", "dc_shell", "pt_shell")},
        thesis_sources="MastersDegreeThesis was not found locally; scope follows "
                       "doc/tesis-pruebas-y-resultados.md; external comparison awaits its artifact")
    save(output / "plan.json", record)
    print(f"Planned {len(records)} compositions, {len(cases)} frozen inputs and E0–E10: {output}")
    return record


def summary(experiment, variant, job, record, bundle, origin):
    case = job["case"]
    manifest = json.loads((bundle / "manifest.json").read_text())
    tiles = manifest["descriptor"]["tiles"]
    return dict(experiment=experiment, case_id=case["case_id"], workload=case["workload"],
        case_role=case["case_role"], variant=variant, policy=job["policy"],
        build_id=record["build_id"], git_revision=origin["git_revision"], seed=case["seed"],
        input_sha256=case["input_sha256"], numeric_contract={k: case[k] for k in (
            "element_width", "accumulator_width", "signed", "overflow")},
        operating_point=None, provenance=origin, scenario_id=digest(job),
        controls={k: v for k, v in job.items() if k != "case"},
        contrast=", ".join(f"{k}={v}" for k, v in job.items() if k not in ("case", "policy")),
        composition={kind.lower(): sum(t["class"] == kind for t in tiles)
                     for kind in ("BCT", "VCT", "MST")},
        geometry=manifest["geometry"],
        domain_model="RTL with delayed supply peers" if experiment == "D0" else "not exercised",
        status=dict(generation="PASS", rtl="NOT_RUN", domains="NOT_RUN",
                    power_intent="NOT_RUN", energy="BLOCKED"),
        metrics=dict(kernel_cycles=None, kernel_time_s=None, verified_outputs=None,
            energy_kernel_j=None, energy_per_output_j=None, energy_config_j=None,
            annotation_pct=None), windows={}, artifacts=dict(bundle=str(bundle)),
        reason="No phase-matched gate-level activity/power report; technology and operating "
               "point must be configured on the licensed server.")


def run(args, output):
    planned = plan(output)
    definitions = {item["id"]: item for item in planned["experiments"]}
    experiments = args.experiment or ["E0", "D0"]
    origin = provenance()
    failures = 0
    for experiment in experiments:
        definition = definitions[experiment]
        variants = args.variant or (["H", "M"] if experiment == "E0" else ["M"])
        for variant in variants:
            if definition["executor"] == "pending":
                path = output / "runs" / experiment / f"{variant}_pending"
                save(path / "summary.json", dict(experiment=experiment, variant=variant,
                    case_id="pending", status=dict(generation="NOT_RUN", rtl="BLOCKED",
                    domains="NOT_RUN", power_intent="NOT_RUN", energy="BLOCKED"), metrics={},
                    reason="; ".join(definition.get("requires", []))))
                continue
            bundle, record = generate(architecture(variant), output / "bundles",
                                      power=experiment == "D0")
            manifest = json.loads((bundle / "manifest.json").read_text())
            lanes = next((t["parameters"]["NUM_LANES"] for t in manifest["tile_parameter_table"]
                          if t["module"] == "vct"), 4)
            jobs = scenarios(experiment, lanes=lanes)
            if args.case:
                jobs = [j for j in jobs if j["case"]["case_id"] in args.case]
            if not jobs:
                raise ValueError(f"No matching runnable cases for {experiment}/{variant}")
            parent = output / "simulation" / experiment / variant
            parent.mkdir(parents=True, exist_ok=True)
            # Never overwrite raw evidence referenced by an earlier comparison.
            suite = Path(tempfile.mkdtemp(prefix="attempt-", dir=parent))
            jobfile = suite / "jobs.json"
            save(jobfile, jobs)
            reports = []
            for index, job in enumerate(jobs):
                row = summary(experiment, variant, job, record, bundle, origin)
                path = output / "runs" / experiment / (
                    f"{variant}_{job['case']['case_id']}_{digest(job)[:12]}")
                save(path / "summary.json", row)
                reports.append((path, row))
                for name in ("functional.json", "trace.json"):
                    (suite / f"case_{index:02d}" / name).unlink(missing_ok=True)
            args.sim_bin_dir = None
            args.make = "make"
            args.compile_args = ""
            args.sim_args = ""
            started = time.monotonic()
            try:
                require_simulator(args)
                simulator = "iverilog" if args.sim == "icarus" else "vcs"
                version = subprocess.run([simulator, "-V" if args.sim == "icarus" else "-ID"],
                    text=True, capture_output=True, timeout=30)
                save(suite / "tool.json", dict(executable=shutil.which(simulator),
                    version=version.stdout + version.stderr))
                sources = " ".join(str(bundle / p) for p in (bundle / "sources.f").read_text().splitlines())
                print(f"Running {experiment}/{variant}: {len(jobs)} PyUVM cases", flush=True)
                result, log, xml, coverage = run_simulation(args, ROOT,
                    Path(__file__).parent / "validation", "cluster", "test_thesis", "ThesisTest",
                    suite, sources, environment=dict(THESIS_SEED=str(campaign()["seed"]),
                        THESIS_BUNDLE=str(bundle), THESIS_OUTPUT=str(suite), THESIS_JOBS=str(jobfile)))
                passed = result.returncode == 0
                if passed:
                    passed_test(xml, "ThesisTest", "test_thesis")
                    assert json.loads(coverage.read_text())["status"] == "PASS"
                verify_bundle(bundle)
                if provenance() != origin:
                    raise ValueError("Experiment verification sources changed during execution")
                for index, (path, row) in enumerate(reports):
                    raw = suite / f"case_{index:02d}" / "functional.json"
                    if raw.exists():
                        data = json.loads(raw.read_text())
                        row["status"]["rtl"] = data["status"]
                        row["status"]["domains"] = data["status"] if experiment == "D0" else "NOT_RUN"
                        row["metrics"].update(data["metrics"])
                        row["windows"] = data["windows"]
                        row["artifacts"].update(functional=str(raw),
                            trace=str(raw.with_name("trace.json")))
                        if data["status"] != "PASS":
                            row["reason"] = f"Functional failure during {data['phase']}; see simulation log"
                    else:
                        row["status"]["rtl"] = "NOT_RUN"
                        row["reason"] = "Earlier case failed; inspect suite log"
                    row["artifacts"].update(log=str(log), xml=str(xml))
                    row["artifact_sha256"] = {name: file_digest(file)
                        for name, file in row["artifacts"].items() if Path(file).is_file()}
                    row.update(simulator=args.sim, wall_time_s=time.monotonic() - started,
                        reproduce=f"make thesis-run SIM={args.sim} THESIS_ARGS='--experiment "
                                  f"{experiment} --variant {variant}'")
                    save(path / "summary.json", row)
                if not passed:
                    failures += 1
                    print(f"FAIL {experiment}/{variant}: {log}", flush=True)
            except (FileNotFoundError, subprocess.TimeoutExpired) as error:
                for path, row in reports:
                    row["status"]["rtl"] = "BLOCKED"
                    row["reason"] = str(error)
                    save(path / "summary.json", row)
                failures += 1
            except Exception as error:
                for path, row in reports:
                    row["status"]["rtl"] = "FAIL"
                    row["reason"] = str(error)
                    save(path / "summary.json", row)
                failures += 1
                print(f"FAIL {experiment}/{variant}: {error}", flush=True)
    collect(output)
    return int(bool(failures))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "run", "report"))
    parser.add_argument("--output", type=Path, default=ROOT / "build/thesis")
    parser.add_argument("--sim", choices=("icarus", "vcs"), default="icarus")
    parser.add_argument("--experiment", action="append",
                        choices=[e["id"] for e in campaign()["experiments"]])
    parser.add_argument("--variant", action="append", choices=("H", "M", *(
        f"M{n}_{p}" for n in (2, 4, 6) for p in ("near", "far"))))
    parser.add_argument("--case", action="append")
    args = parser.parse_args()
    if campaign()["clock_period_ns"] != 10:
        parser.error("The portable native driver uses a 10 ns reference period")
    output = args.output.resolve()
    if args.command == "plan":
        plan(output)
    elif args.command == "run":
        return run(args, output)
    else:
        collect(output)
        print(output / "thesis-summary.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
