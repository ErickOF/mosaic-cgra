#!/usr/bin/env python3
"""Reject declaration patterns that Synopsys PRESTO resolves nonportably."""

import argparse
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
GENVAR = re.compile(r"^(?P<indent>[ \t]*)for\s*\(\s*genvar\s+(?P<name>[A-Za-z_]\w*)")
NET = re.compile(
    r"^(?P<indent>[ \t]*)(?:wire|logic|reg)\b"
    r"(?:\s+(?:signed|unsigned))?(?:\s*\[[^;]+?\])?\s+(?P<name>[A-Za-z_]\w*)"
)
DECLARATION = re.compile(
    r"(?m)^(?P<indent>[ \t]*)(?:wire|logic|reg)\b\s+"
    r"(?:(?:signed|unsigned)\s+)?(?:\[[^\]]+\]\s+)?"
    r"(?P<name>[A-Za-z_]\w*)(?:\s*\[[^\]]+\])?\s*"
    r"(?:=\s*(?P<initializer>.*?))?;",
    re.DOTALL,
)


def find_nonportable_declarations(sources):
    findings = []
    for path in sorted(Path(source) for source in sources):
        text = path.read_text()
        lines = text.splitlines()
        genvars = {}
        nets = {}
        for line_number, line in enumerate(lines, 1):
            match = GENVAR.match(line)
            if match:
                genvars.setdefault((match.group("indent"), match.group("name")), []).append(
                    line_number
                )
            match = NET.match(line)
            if match:
                nets.setdefault((match.group("indent"), match.group("name")), []).append(
                    line_number
                )
        for key in sorted(set(genvars) & set(nets)):
            indent, name = key
            findings.append({
                "path": path,
                "line": nets[key][0],
                "column": len(indent) + 1,
                "name": name,
                "issue": f"collides with same-scope genvar declared on line {genvars[key][0]}",
            })

        declarations = list(DECLARATION.finditer(text))
        for declaration, following in zip(declarations, declarations[1:]):
            initializer = declaration.group("initializer")
            if not initializer or declaration.group("indent") != following.group("indent"):
                continue
            if following.start() - declaration.end() > 256:
                continue
            name = following.group("name")
            if not re.search(rf"\b{re.escape(name)}\b", initializer):
                continue
            offset = declaration.start()
            findings.append({
                "path": path,
                "line": text.count("\n", 0, offset) + 1,
                "column": len(declaration.group("indent")) + 1,
                "name": name,
                "issue": "is referenced before the following declaration",
            })
    return sorted(findings, key=lambda finding: (
        str(finding["path"]), finding["line"], finding["column"], finding["name"]
    ))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rtl-root", type=Path, default=ROOT / "src/rtl")
    args = parser.parse_args()
    rtl_root = args.rtl_root.resolve()
    sources = sorted(rtl_root.rglob("*.sv"))
    if not sources:
        parser.error(f"No SystemVerilog sources found under {rtl_root}")

    try:
        findings = find_nonportable_declarations(sources)
    except OSError as error:
        parser.error(str(error))
    for finding in findings:
        try:
            path = finding["path"].relative_to(ROOT)
        except ValueError:
            path = finding["path"]
        print(
            f"{path}:{finding['line']}:{finding['column']}: "
            f"'{finding['name']}' {finding['issue']}"
        )
    if findings:
        print(f"PRESTO declaration check failed: {len(findings)} finding(s).")
        return 1
    print(f"PRESTO declaration check passed: {len(sources)} SystemVerilog files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
