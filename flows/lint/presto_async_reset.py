#!/usr/bin/env python3
"""Reject asynchronous sequential processes without a top-level reset if."""

import argparse
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]
ASYNC_PROCESS = re.compile(
    r"\balways(?:_ff)?\s*@\("
    r"(?P<events>[^)]*(?:posedge|negedge)[^)]*\bor\b[^)]*(?:posedge|negedge)[^)]*)"
    r"\)\s*(?:begin(?:\s*:\s*[A-Za-z_]\w*)?)?",
    re.DOTALL,
)
TRIVIA = re.compile(r"(?:\s+|//[^\n]*(?:\n|$)|/\*.*?\*/)*", re.DOTALL)
IDENTIFIER = re.compile(r"[A-Za-z_]\w*")


def find_nonportable_async_processes(sources):
    findings = []
    for path in sorted(Path(source) for source in sources):
        text = path.read_text()
        for match in ASYNC_PROCESS.finditer(text):
            statement = TRIVIA.match(text, match.end()).end()
            token = IDENTIFIER.match(text, statement)
            first_statement = token.group() if token else "<unknown>"
            if first_statement == "if":
                continue
            offset = match.start()
            line = text.count("\n", 0, offset) + 1
            line_start = text.rfind("\n", 0, offset) + 1
            findings.append({
                "path": path,
                "line": line,
                "column": offset - line_start + 1,
                "first_statement": first_statement,
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
        findings = find_nonportable_async_processes(sources)
    except OSError as error:
        parser.error(str(error))

    for finding in findings:
        try:
            path = finding["path"].relative_to(ROOT)
        except ValueError:
            path = finding["path"]
        print(
            f"{path}:{finding['line']}:{finding['column']}: asynchronous process "
            f"starts with '{finding['first_statement']}', not a PRESTO-compatible reset if"
        )
    if findings:
        print(f"PRESTO asynchronous-reset check failed: {len(findings)} finding(s).")
        return 1
    print(f"PRESTO asynchronous-reset check passed: {len(sources)} SystemVerilog files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
