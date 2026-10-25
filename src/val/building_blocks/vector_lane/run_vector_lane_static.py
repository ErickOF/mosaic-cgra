"""Lint and synthesize every vector lane profile, checking feature removal and clocks."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from run_vector_lane_regression import (
    DEPENDENCIES,
    PROFILES,
    ROOT,
    TEST_DIR,
    verification_hashes,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yosys", default="yosys")
    parser.add_argument("--verilator", default="verilator")
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--case", action="append", choices=[name for name, _ in PROFILES])
    args = parser.parse_args()
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    sources = (*DEPENDENCIES, ROOT / "src/rtl/building_blocks/vector_lane.sv")
    summary = {
        "status": "NOT_RUN",
        "profiles": [],
        "started_at_utc": datetime.now(UTC).isoformat(),
        "source_sha256": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources
        },
        "verification_sha256": verification_hashes(TEST_DIR),
        "technology_mapping": "NOT_RUN",
        "commercial_lint": "NOT_RUN",
        "cdc": "NOT_RUN",
        "rdc": "NOT_RUN",
        "physical_timing": "NOT_RUN",
        "physical_power": "NOT_RUN",
    }
    try:
        yosys, verilator = shutil.which(args.yosys), shutil.which(args.verilator)
        if yosys is None or verilator is None:
            raise FileNotFoundError("Static checks require Verilator and Yosys with slang")
        summary["yosys_version"] = subprocess.check_output([yosys, "-V"], text=True).strip()
        summary["verilator_version"] = subprocess.check_output(
            [verilator, "--version"], text=True
        ).strip()
        for name, p in PROFILES:
            if args.case and name not in args.case:
                continue
            case = build / name
            case.mkdir(exist_ok=True)
            row = {"name": name, "parameters": p, "status": "FAIL"}
            log = case / "lint.log"
            with log.open("w") as output:
                lint = subprocess.run(
                    [
                        verilator,
                        "--lint-only",
                        "--top-module",
                        "vector_lane",
                        "-Wall",
                        *(f"-G{k}={v}" for k, v in p.items()),
                        *map(str, sources),
                    ],
                    check=False,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                )
            row.update(lint="PASS" if lint.returncode == 0 else "FAIL", lint_log=str(log))
            script = (
                "read_slang --top vector_lane "
                + " ".join(f"-G{k}={v}" for k, v in p.items())
                + " "
                + " ".join(str(path.relative_to(ROOT)) for path in sources)
                + "\nprep -top vector_lane -flatten\nopt\ncheck -assert\nscc -expect 0\nstat\n"
                + "write_json netlist.json\n"
            )
            # read_slang gets repository-relative inputs; standard Yosys output
            # commands accept quoted absolute destinations, including external builds.
            script = script.replace(
                "write_json netlist.json", "write_json " + json.dumps(str(case / "netlist.json"))
            )
            (case / "synth.ys").write_text(script)
            log = case / "synth.log"
            with log.open("w") as output:
                synth = subprocess.run(
                    [yosys, "-Q", "-T", "-s", str(case / "synth.ys")],
                    cwd=ROOT,
                    check=False,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                )
            row.update(
                generic_synthesis="PASS" if synth.returncode == 0 else "FAIL", synth_log=str(log)
            )
            if synth.returncode == 0:
                netlist = json.loads((case / "netlist.json").read_text())["modules"]["vector_lane"]
                types = {cell["type"].lower() for cell in netlist["cells"].values()}
                forbidden = {
                    kind
                    for kind in types
                    if any(token in kind for token in ("latch", "$div", "$mod", "blackbox"))
                }
                sequential = [
                    cell for cell in netlist["cells"].values() if "dff" in cell["type"].lower()
                ]
                clk = netlist["ports"]["i_clk"]["bits"]
                single_clock = all(cell["connections"]["CLK"] == clk for cell in sequential)
                names = netlist["netnames"]
                removed = all(
                    not any(f"g_{unit}.u_unit." in n for n in names)
                    for unit in ("mul", "mac")
                    if not p["SUPPORT_" + unit.upper()]
                )
                row.update(
                    forbidden_cells=sorted(forbidden),
                    cell_count=len(netlist["cells"]),
                    sequential_cells=len(sequential),
                    single_functional_clock=single_clock,
                    disabled_units_removed=removed,
                    zero_latency_without_state=bool(sequential) == bool(p["LANE_LATENCY"]),
                )
                if (
                    lint.returncode == 0
                    and not forbidden
                    and single_clock
                    and removed
                    and row["zero_latency_without_state"]
                ):
                    row["status"] = "PASS"
            summary["profiles"].append(row)
            print(name, row["status"], flush=True)
        count = len(set(args.case)) if args.case else len(PROFILES)
        if len(summary["profiles"]) == count and all(
            p["status"] == "PASS" for p in summary["profiles"]
        ):
            summary["status"] = "PASS"
        else:
            summary["status"] = "FAIL"
    except (FileNotFoundError, subprocess.SubprocessError) as error:
        summary["error"] = str(error)
    except (OSError, ValueError, KeyError, AssertionError) as error:
        summary["status"] = "FAIL"
        summary["error"] = str(error)
    finally:
        summary["finished_at_utc"] = datetime.now(UTC).isoformat()
        (build / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(f"Vector lane static {summary['status']}: {build / 'summary.json'}")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
