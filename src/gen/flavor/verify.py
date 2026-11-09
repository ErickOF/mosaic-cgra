"""Run existing Python models and PyUVM against an immutable generated flavor."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flavor.generate import verify_bundle
from flavor.model import ROOT

TESTS = ROOT / "src/val/mosaic_blocks/cluster"
sys.path[:0] = [str(TESTS.parent), str(ROOT / "src/val/lib")]
from mosaic_uvm.regression import (passed_test, require_simulator, run_simulation,
                                   verification_hashes)
from cluster.test_model import ModelTests


def native_profiles(args, root, output, manifest, sources, seed):
    """Reuse each released tile's PyUVM campaign for its actual FU parameters.

    Identical hardware profiles share one functional run; the assembled-fabric
    test still checks every tile's identity, configuration and runtime interface.
    """
    profiles = {}
    for tile in manifest["tile_parameter_table"]:
        p = tile["parameters"]
        key = tile["module"], json.dumps({k: v for k, v in p.items() if k != "TILE_ID"},
                                       sort_keys=True)
        if key not in profiles:
            profiles[key] = dict(module=tile["module"], parameters=p, tiles=[])
        profiles[key]["tiles"].append(tile["id"])

    def run(item):
        index, profile = item
        module = profile["module"]
        test_dir = ROOT / "src/val/mosaic_blocks" / module
        before = verification_hashes(test_dir)
        prefix = module.upper()
        cycles = 20 if module == "mst" else 1000
        environment = {f"{prefix}_{key}": str(value)
                       for key, value in profile["parameters"].items()}
        environment.update({f"{prefix}_SEED": str(seed + index),
                            f"{prefix}_RANDOM_CYCLES": str(cycles)})
        test = module.capitalize() + "Test"
        prefix_flag = f"-P{module}." if args.sim == "icarus" else f"-pvalue+{module}."
        compile_flags = " ".join(f"{prefix_flag}{key}={value}"
                                 for key, value in profile["parameters"].items())
        result, log, xml, coverage = run_simulation(args, root, test_dir, module,
            "test_" + module, test, output / f"tile_profile_{index}_{module}", sources,
            parameters=profile["parameters"], environment=environment, compile_args=compile_flags)
        if result.returncode:
            raise ValueError(f"{module.upper()} FU profile failed: {log}")
        passed_test(xml, test, "test_" + module)
        data = json.loads(coverage.read_text())
        if (data["status"] != "PASS" or not data["goals"] or not all(data["goals"].values()) or
                data["seed"] != seed + index or data["random_transactions"] != cycles or
                any(data["parameters"].get(key) != value
                    for key, value in profile["parameters"].items())):
            raise ValueError(f"{module.upper()} FU coverage/provenance mismatch: {coverage}")
        if verification_hashes(test_dir) != before:
            raise ValueError(f"{module.upper()} verification sources changed during the run")
        return dict(module=module, tiles=profile["tiles"], status="PASS", coverage=str(coverage),
                    goals=data["goals"], verification_sha256=before, log=str(log))

    with ThreadPoolExecutor(max_workers=2 if args.sim == "icarus" else 1) as pool:
        return list(pool.map(run, enumerate(profiles.values(), 1)))


def verify(bundle, output, *, sim="icarus", seed=20261029, random_cycles=1000):
    bundle, output = Path(bundle).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    result_file = output / "summary.json"
    record = verify_bundle(bundle)
    manifest = json.loads((bundle / "manifest.json").read_text())
    descriptor = manifest["descriptor"]
    native = manifest["schema"] == "mosaic-native-fabric-v1"
    tests = ROOT / "src/val/mosaic_blocks/flavor" if native else TESTS
    smoke = not native and descriptor["rows"] != 2
    summary = dict(status="FAIL", build_id=record["build_id"], simulator=sim,
        scope="native tile interfaces and grid transport" if native else
              "control smoke" if smoke else "full integration", framework="PyUVM",
        synthesis="Design Compiler (deferred)", lint="NOT_RUN")
    before = verification_hashes(tests)
    try:
        with (output / "python_models.log").open("w") as log:
            models = unittest.TextTestRunner(stream=log).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(ModelTests))
        summary["python_models"] = dict(tests=models.testsRun, passed=models.wasSuccessful())
        if not models.wasSuccessful():
            raise ValueError("Independent Python model tests failed")
        directory = os.getenv("VCS_BIN_DIR" if sim == "vcs" else "ICARUS_BIN_DIR")
        args = argparse.Namespace(sim=sim, sim_bin_dir=Path(directory) if directory else None,
            make="make", compile_args="", sim_args="")
        require_simulator(args)
        files = [(bundle / name).resolve() for name in (bundle / "sources.f").read_text().splitlines()]
        if any(not path.is_relative_to(bundle) for path in files):
            raise ValueError("Source list escapes the generated bundle")
        test = "FabricTest" if native else "ClusterSmokeTest" if smoke else "ClusterTest"
        module = "test_flavor" if native else "test_cluster"
        print(f"Running {sim}: {summary['scope']} for {record['name']}", flush=True)
        environment = (dict(FLAVOR_ARTIFACTS=str(bundle), FLAVOR_SEED=str(seed),
                            FLAVOR_RANDOM_CYCLES=str(random_cycles)) if native else
            dict(CLUSTER_ARTIFACTS=str(bundle), CLUSTER_SEED=str(seed),
                 CLUSTER_RANDOM_CYCLES=str(random_cycles), CLUSTER_MODE="smoke" if smoke else "full"))
        result, log, xml, coverage = run_simulation(args, ROOT, tests, "cluster", module,
            test, output / "simulation", " ".join(map(str, files)), parameters=descriptor,
            environment=environment)
        summary["log"] = str(log)
        if result.returncode:
            raise ValueError(f"Simulation failed; see {log}")
        passed_test(xml, test, module)
        data = json.loads(coverage.read_text())
        if (data["status"] != "PASS" or not data["goals"] or not all(data["goals"].values()) or
                data["manifest_sha256"] != manifest["manifest_sha256"] or
                data["parameters"] != descriptor or data["seed"] != seed or
                data["random_cycles"] != random_cycles):
            raise ValueError("Coverage or test provenance mismatch")
        if native:
            summary["tile_profiles"] = native_profiles(args, ROOT, output, manifest,
                                                        " ".join(map(str, files)), seed)
        verify_bundle(bundle)
        if verification_hashes(tests) != before:
            raise ValueError("Verification sources changed during the run")
        summary.update(status="PASS", coverage=str(coverage), cycles=data["cycles"],
            goals=data["goals"], verification_sha256=before, sources_stable=True)
    except (OSError, ValueError, KeyError) as error:
        summary["error"] = str(error)
    result_file.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sim", choices=("icarus", "vcs"), default="icarus")
    parser.add_argument("--seed", type=int, default=20261029)
    parser.add_argument("--random-cycles", type=int, default=1000)
    args = parser.parse_args()
    if not 0 <= args.seed < 2 ** 31 or not 1000 <= args.random_cycles <= 100000:
        parser.error("seed must fit 31 bits and random-cycles must be 1000–100000")
    result = verify(args.bundle, args.output, sim=args.sim, seed=args.seed,
                    random_cycles=args.random_cycles)
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
