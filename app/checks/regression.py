"""Python/PyUVM checks of exported flavors, using their copied RTL sources."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/gen"))
from flavor.generate import generate
from flavor.model import starter
from flavor.verify import verify


def profiles():
    def grid(name, rows, cols, kinds):
        document = starter()
        document["name"] = name
        document["cluster"].update(rows=rows, cols=cols, scratchpad_bank_words=32,
            tiles=[dict(id=r * cols + c, row=r, col=c,
                        **{"class": kinds[(r * cols + c) % len(kinds)]})
                   for r in range(rows) for c in range(cols)])
        return document

    classes = ("BCT", "MST", "VCT", "SFT", "CPT")
    result = {
        "single": grid("single", 1, 1, ("BCT",)),
        "rectangle": grid("rectangle", 2, 3, classes),
        "long_column": grid("long_column", 9, 1, classes),
        "multiple_mst": grid("multiple_mst", 1, 3, ("MST", "MST", "BCT")),
        "all_functions": grid("all_functions", 1, 5, classes),
    }
    tiles = result["all_functions"]["cluster"]["tiles"]
    tiles[0]["parameters"] = {"FU_PROFILE": 2, "DATA_WIDTH": 64, "ACCUMULATOR_COUNT": 2}
    tiles[2]["parameters"] = {"FU_PROFILE": 2}
    tiles[3]["parameters"] = {"FU_PROFILE": 3, "EXP_PIPELINE_DEPTH": 7,
                             "RECIP_INTERNAL_WIDTH": 32, "RSQRT_INTERNAL_WIDTH": 32}
    tiles[4]["parameters"] = {"MAX_LOOP_DEPTH": 2, "INDEX_WIDTH": 16, "TRIP_COUNT_WIDTH": 16}
    result["rectangle"]["cluster"]["tiles"][5]["parameters"] = {"RF_DEPTH": 16}
    # These selections cannot be represented by the legacy cumulative profiles.
    from tile_units import UNIT_DEFAULTS
    independent = grid("independent", 1, 5, classes)
    complements = grid("complements", 1, 5, classes)
    disabled = grid("disabled", 1, 5, classes)
    for document in (independent, complements, disabled):
        for tile in document["cluster"]["tiles"]:
            tile["parameters"] = {name: 0 for name in UNIT_DEFAULTS[tile["class"]]}
            if tile["class"] == "VCT":
                tile["parameters"].update(SUPPORT_MUL=0, SUPPORT_MAC=0)
    for tile, enabled in zip(independent["cluster"]["tiles"],
            ("ENABLE_MAC", "ENABLE_LOAD", "ENABLE_DOT_PRODUCT", "ENABLE_RECIPROCAL",
             "ENABLE_LOOP_CONTROLLER"), strict=True):
        tile["parameters"][enabled] = 1
    for tile, enabled in zip(complements["cluster"]["tiles"],
            ("ENABLE_MULTIPLIER", "ENABLE_STORE", "SUPPORT_MAC", "ENABLE_EXPONENTIAL",
             "ENABLE_ACTIONS"), strict=True):
        tile["parameters"][enabled] = 1
    single_fus = grid("single_fus", 2, 5, ("SFT",))
    for tile, enabled in zip(single_fus["cluster"]["tiles"], UNIT_DEFAULTS["SFT"], strict=True):
        tile["parameters"] = {name: int(name == enabled) for name in UNIT_DEFAULTS["SFT"]}
    result.update(independent=independent, complements=complements, disabled=disabled,
                  single_fus=single_fus)
    local = grid("local_fus", 1, 6, ("BCT", "CPT", "CPT", "VCT", "VCT", "VCT"))
    for tile, enabled in zip(local["cluster"]["tiles"],
            ("ENABLE_ALU", "ENABLE_PREDICATE", "ENABLE_EVENT_BARRIER", "ENABLE_LANE_ALU",
             "SUPPORT_MUL", "ENABLE_REDUCTION"), strict=True):
        p = tile["parameters"] = {name: 0 for name in UNIT_DEFAULTS[tile["class"]]}
        if tile["class"] == "VCT":
            p.update(SUPPORT_MUL=0, SUPPORT_MAC=0)
        p[enabled] = 1
    result["local_fus"] = local
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sim", choices=("icarus", "vcs"), default="icarus")
    parser.add_argument("--output", type=Path, default=ROOT / "build/app-checks/regression")
    parser.add_argument("--case", action="append", choices=tuple(profiles()))
    parser.add_argument("--jobs", type=int, choices=range(1, 5), default=2)
    args = parser.parse_args()
    output = args.output.resolve()

    def run(item):
        name, document = item
        bundle, _ = generate(document, output / "bundles")
        return verify(bundle, output / name, sim=args.sim) | {"case": name}

    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(run, ((name, doc) for name, doc in profiles().items()
                                     if not args.case or name in args.case)))
    passed = bool(results) and all(result["status"] == "PASS" for result in results)
    summary = dict(status="PASS" if passed else "FAIL", profiles=results)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"Flavor regression {summary['status']}: {len(results)} profiles")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
