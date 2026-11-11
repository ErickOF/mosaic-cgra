#!/usr/bin/env python3
"""Reject explicit X comparisons on elaboration-time RTL parameters."""

import argparse
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
EXPLICIT_X_PARAMETER_CHECK = re.compile(
    r"\^\s*(?P<name>[A-Z][A-Z0-9_]*)\s*(?P<operator>===|!==)\s*1'bx"
)
EXPLICIT_X_PARAMETER_CONCAT_CHECK = re.compile(
    r"\^\s*\{(?P<body>[^}\n]+)\}\s*(?P<operator>===|!==)\s*1'bx"
)
IDENTIFIER = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


def is_parameter_concatenation(body):
    names = IDENTIFIER.findall(body)
    return bool(names) and all(name[0].isupper() for name in names)


def find_explicit_x_parameter_checks(sources):
    findings = []
    for path in sorted(Path(source) for source in sources):
        text = path.read_text()
        matches = list(EXPLICIT_X_PARAMETER_CHECK.finditer(text))
        matches.extend(
            match for match in EXPLICIT_X_PARAMETER_CONCAT_CHECK.finditer(text)
            if is_parameter_concatenation(match.group("body"))
        )
        for match in sorted(matches, key=lambda item: item.start()):
            offset = match.start()
            line = text.count("\n", 0, offset) + 1
            line_start = text.rfind("\n", 0, offset) + 1
            name = match.groupdict().get("name")
            if name is None:
                name = "{" + match.group("body").strip() + "}"
            findings.append({
                "path": path,
                "line": line,
                "column": offset - line_start + 1,
                "name": name,
                "operator": match.group("operator"),
            })
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rtl-root", type=Path, default=ROOT / "src/rtl")
    args = parser.parse_args()
    rtl_root = args.rtl_root.resolve()
    sources = sorted(rtl_root.rglob("*.sv"))
    if not sources:
        parser.error(f"No SystemVerilog sources found under {rtl_root}")

    try:
        findings = find_explicit_x_parameter_checks(sources)
    except OSError as error:
        parser.error(str(error))

    for finding in findings:
        try:
            path = finding["path"].relative_to(ROOT)
        except ValueError:
            path = finding["path"]
        print(
            f"{path}:{finding['line']}:{finding['column']}: explicit X comparison "
            f"on parameter '{finding['name']}' is not PRESTO portable"
        )
    if findings:
        print(f"PRESTO parameter-guard check failed: {len(findings)} finding(s).")
        return 1
    print(
        f"PRESTO parameter-guard check passed: {len(sources)} SystemVerilog files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
