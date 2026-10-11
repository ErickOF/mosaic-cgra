"""Summarize test power in watts and interval energy in joules.

Called by make power-report after PrimeTime PX/PrimePower writes its verbose
power and activity reports. Duration comes from the SAIF header, including
reset and idle time inside the captured interval. Energy uses average power
over that complete interval; this script does not produce a peak-power trace.
Python 3.12 or newer is required; all dependencies are in the standard library.
"""

import argparse
import json
import math
import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, TypedDict, overload

type PowerComponent = Literal[
    "internal", "switching", "dynamic", "leakage", "total"
]
type ComponentValues = dict[PowerComponent, float]


class ActivityCoverage(TypedDict):
    """Describe how many nets received activity from the SAIF file."""
    file_annotated_nets: int
    file_annotated_percent: float


class PowerSummary(TypedDict):
    """Describe the JSON result, with all measurements in SI units."""
    design: str
    analysis: Literal["post_route", "mapped_netlist_estimate"]
    duration_s: float
    average_power_w: ComponentValues
    energy_j: ComponentValues
    saif_annotation: ActivityCoverage
    inputs: dict[str, str]
    test_selection: dict[str, str]


# Tool reports can use decimal or scientific notation. Normalize each quantity
# from its declared unit; dynamic power and leakage need not share a unit.
NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
POWER_UNITS: dict[str, float] = {
    "W": 1.0,
    "mW": 1e-3,
    "uW": 1e-6,
    "µW": 1e-6,
    "μW": 1e-6,
    "nW": 1e-9,
    "pW": 1e-12,
    "fW": 1e-15,
}
TIME_UNITS: dict[str, float] = {
    "s": 1.0,
    "ms": 1e-3,
    "us": 1e-6,
    "ns": 1e-9,
    "ps": 1e-12,
    "fs": 1e-15,
}


def finite_nonnegative(value: str, label: str) -> float:
    """Parse value as a finite, nonnegative float.

    Raise ValueError for an invalid quantity, using label in diagnostics.
    """
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError(f"{label} must be finite and nonnegative")
    return result


def saif_duration(path: Path) -> float:
    """Return capture duration in seconds from DURATION times TIMESCALE.

    Read only the bounded header before INSTANCE data. Simulator wall time
    and the chosen test clock period are not substitutes for this duration.
    Raise ValueError for invalid header data or OSError if path cannot be read.
    """
    # Headers precede INSTANCE data. Avoid loading the full gate SAIF.
    with path.open(encoding="utf-8") as stream:
        header = ""
        while len(header) < 1024 * 1024:
            chunk = stream.read(4096)
            if not chunk:
                break
            header += chunk
            instance = re.search(r"\(\s*INSTANCE\b", header)
            if instance:
                header = header[:instance.start()]
                break
    scale = re.search(rf"\(\s*TIMESCALE\s+({NUMBER})\s*(\w+)\s*\)", header)
    duration = re.search(rf"\(\s*DURATION\s+({NUMBER})\s*\)", header)
    if not scale or not duration:
        raise ValueError("SAIF header must contain TIMESCALE and DURATION")
    if scale[2] not in TIME_UNITS:
        raise ValueError(f"Unsupported SAIF time unit: {scale[2]}")
    # For example, TIMESCALE 10 ps with DURATION 2000 describes 20 ns.
    seconds = (
        finite_nonnegative(scale[1], "TIMESCALE")
        * TIME_UNITS[scale[2]]
        * finite_nonnegative(duration[1], "DURATION")
    )
    if not math.isfinite(seconds) or seconds <= 0:
        raise ValueError("SAIF capture duration must be finite and positive")
    return seconds


def power_values(report: str) -> ComponentValues:
    """Return internal, switching, dynamic, leakage, and total power in watts.

    Accept explicit units on a summary line or inherit the corresponding
    report-header unit. Missing units and duplicate fields are rejected so
    report formatting changes cannot silently alter the resulting energy.
    Raise ValueError for invalid, missing, or inconsistent measurements.
    """

    def declared_unit(kind: str) -> float | None:
        """Convert a header unit declaration to watts per reported unit."""
        match = re.search(
            rf"{kind}\s+Power\s+Units?\s*[:=]\s*({NUMBER})\s*(\S+)",
            report,
        )
        if not match:
            return None
        if match[2] not in POWER_UNITS:
            raise ValueError(
                f"Unsupported {kind.lower()} power unit: {match[2]}"
            )
        factor = (
            finite_nonnegative(match[1], f"{kind} power unit")
            * POWER_UNITS[match[2]]
        )
        if factor <= 0:
            raise ValueError(f"{kind} power unit must be positive")
        return factor

    dynamic_unit = declared_unit("Dynamic")
    leakage_unit = declared_unit("Leakage")

    # A required field always returns a float or raises; an optional total
    # can return None. Overloads let type checkers preserve that distinction.
    @overload
    def value(
        label: str, inherited_unit: float | None, *,
        required: Literal[True] = True,
    ) -> float: ...

    @overload
    def value(
        label: str, inherited_unit: float | None, *, required: Literal[False],
    ) -> float | None: ...

    def value(
        label: str, inherited_unit: float | None, *, required: bool = True,
    ) -> float | None:
        """Read one summary field, ignoring its trailing percentage."""
        matches = list(
            re.finditer(
                rf"^[ \t]*{re.escape(label)}[ \t]*=[ \t]*({NUMBER})"
                rf"[ \t]*([A-Za-zµμ]+)?[ \t]*(?:\([^\n)]*\))?[ \t]*$",
                report,
                re.MULTILINE,
            )
        )
        if not matches:
            if required:
                raise ValueError(f"Missing {label} in power report")
            return None
        if len(matches) != 1:
            raise ValueError(f"Ambiguous {label} in power report")
        match = matches[0]
        unit = match[2]
        # A line's explicit unit takes precedence over the shared header unit.
        factor = POWER_UNITS.get(unit) if unit else inherited_unit
        if factor is None:
            raise ValueError(
                f"Missing or unsupported units for {label}: {unit}"
            )
        return finite_nonnegative(match[1], label) * factor

    # Add SI values only after normalizing their potentially different units.
    internal = value("Cell Internal Power", dynamic_unit)
    switching = value("Net Switching Power", dynamic_unit)
    leakage = value("Cell Leakage Power", leakage_unit)
    dynamic = internal + switching
    total = dynamic + leakage
    # Reports round values independently. Allow 0.5% rounding differences,
    # but reject a total that materially disagrees with its component powers.
    for label, computed in (
        ("Total Dynamic Power", dynamic), ("Total Power", total)
    ):
        reported = value(label, dynamic_unit, required=False)
        if reported is not None and not math.isclose(
            reported, computed, rel_tol=0.005, abs_tol=1e-18
        ):
            raise ValueError(f"{label} does not match its component powers")
    values: ComponentValues = {
        "internal": internal,
        "switching": switching,
        "dynamic": dynamic,
        "leakage": leakage,
        "total": total,
    }
    if not all(math.isfinite(number) for number in values.values()):
        raise ValueError("Power values must be finite")
    return values


def activity_coverage(report: str) -> ActivityCoverage:
    """Read file-annotated net coverage and reject a SAIF with no mapping.

    Nonzero coverage establishes that some activity was matched; it does not
    establish full coverage. Unmatched activity can be estimated by the tool.
    Raise ValueError if coverage is missing, invalid, or zero.
    """
    # In report_switching_activity the first data column is File(%).
    match = re.search(
        r"^\s*Nets\s+(\d+)\s*\(\s*([\d.]+)\s*%\s*\)",
        report,
        re.MULTILINE,
    )
    if not match:
        raise ValueError(
            "Cannot read SAIF annotation coverage from activity report"
        )
    if int(match[1]) == 0:
        raise ValueError(
            "SAIF annotated zero nets; "
            "check POWER_SAIF_STRIP_PATH and the netlist"
        )
    percent = finite_nonnegative(match[2], "SAIF coverage")
    if percent > 100:
        raise ValueError("SAIF coverage exceeds 100 percent")
    return {
        "file_annotated_nets": int(match[1]),
        "file_annotated_percent": percent,
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Write the JSON summary, print readable SI scales, and return zero.

    Parse argv when supplied, otherwise use the process command line. Remove
    an earlier output before validating measurements. Errors raise
    SystemExit(2).
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    path_options = {
        "report": "PrimeTime verbose average power report",
        "activity-report": "PrimeTime switching activity report",
        "saif": "SAIF file containing the capture duration",
        "output": "destination JSON summary (replaces any previous summary)",
    }
    for option, help_text in path_options.items():
        parser.add_argument(
            f"--{option}", type=Path, required=True, metavar="PATH",
            help=help_text,
        )
    metadata_options = {
        "design": "analyzed top module name",
        "netlist": "netlist used to produce the SAIF",
        "sdc": "constraints used for power analysis",
        "spef": "extracted parasitics used for post-route power analysis",
        "sdf": "delay annotation used in the gate simulation",
        "test-modules": "selected PyUVM test modules",
        "test-filter": "test filter used during the SAIF capture",
    }
    for option, help_text in metadata_options.items():
        # These describe the supplied Make configuration. When analyzing an
        # existing SAIF, supply its original inputs and test selection.
        parser.add_argument(f"--{option}", default="", help=help_text)
    args = parser.parse_args(argv)
    try:
        # A failed new analysis must not leave an earlier successful summary.
        args.output.unlink(missing_ok=True)
        duration = saif_duration(args.saif)
        # Explicit UTF-8 keeps Unicode unit symbols independent of the locale.
        powers = power_values(args.report.read_text(encoding="utf-8"))
        coverage = activity_coverage(
            args.activity_report.read_text(encoding="utf-8")
        )
        # E[J] = P_average[W] * duration[s], including the leakage component.
        energies: ComponentValues = {
            component: watts * duration for component, watts in powers.items()
        }
        if not all(math.isfinite(number) for number in energies.values()):
            raise ValueError("Energy values must be finite")
        summary: PowerSummary = {
            "design": args.design,
            # This label records whether the analysis was supplied with SPEF;
            # parasitic completeness is assessed in the tool's separate report.
            "analysis": (
                "post_route" if args.spef else "mapped_netlist_estimate"
            ),
            "duration_s": duration,
            "average_power_w": powers,
            "energy_j": energies,
            "saif_annotation": coverage,
            "inputs": {
                "netlist": args.netlist,
                "sdc": args.sdc,
                "spef": args.spef,
                "sdf": args.sdf,
                "saif": str(args.saif),
            },
            "test_selection": {
                "modules": args.test_modules,
                "filter": args.test_filter,
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(summary, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError) as error:
        # Propagate incomplete inputs or invalid measurements to make's status.
        parser.exit(2, f"Power/energy summary failed: {error}\n")
    # JSON retains watts/joules; console output uses convenient mW/pJ scales.
    print(f"Capture duration: {duration * 1e9:.6g} ns")
    print(
        f"Average power: {powers["total"] * 1e3:.6g} mW "
        f"(dynamic {powers["dynamic"] * 1e3:.6g}, "
        f"leakage {powers["leakage"] * 1e3:.6g})"
    )
    print(
        f"Energy: {energies["total"] * 1e12:.6g} pJ "
        f"(dynamic {energies["dynamic"] * 1e12:.6g}, "
        f"leakage {energies["leakage"] * 1e12:.6g})"
    )
    print(
        "SAIF file annotation: "
        f"{coverage["file_annotated_percent"]:.2f}% of nets"
    )
    print(f"Power/energy summary: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
