#!/usr/bin/env python3
"""Reject nonportable or unresolved SystemVerilog identifier references."""

import argparse
from pathlib import Path
import sys

try:
    import pyslang
    from pyslang.ast import Compilation
    from pyslang.syntax import SyntaxTree
except ImportError as error:  # pragma: no cover - exercised without the project environment.
    raise SystemExit(
        "pyslang is required. Run make setup or install requirements.txt."
    ) from error


ROOT = Path(__file__).resolve().parents[2]

REFERENCE_DIAGNOSTICS = {
    pyslang.Diags.UsedBeforeDeclared: "used before declaration",
    pyslang.Diags.UndeclaredIdentifier: "is not declared",
    pyslang.Diags.UndeclaredButFoundPackage: "is not declared",
    pyslang.Diags.ImplicitNet: "creates an implicit net",
    pyslang.Diags.ImplicitNetPortNoDefault: "creates an implicit port net",
    pyslang.Diags.UnknownClassMember: "references an unknown class member",
    pyslang.Diags.UnknownClassOrPackage: "references an unknown class or package",
    pyslang.Diags.UnknownInterface: "references an unknown interface",
    pyslang.Diags.UnknownMember: "references an unknown member",
    pyslang.Diags.UnknownPackageMember: "references an unknown package member",
}

DESIGN_UNIT_DIAGNOSTICS = {
    pyslang.Diags.UnknownModule: "references an unknown module",
    pyslang.Diags.UnknownPackage: "references an unknown package",
}


def ordered_sources(rtl_root):
    sources = list(Path(rtl_root).rglob("*.sv"))
    return sorted(sources, key=lambda path: (not path.stem.endswith("_pkg"), str(path)))


def manifest_sources(manifest, project_root=ROOT):
    sources = []
    for line in Path(manifest).read_text().splitlines():
        entry = line.strip()
        if entry and not entry.startswith("#"):
            sources.append(Path(project_root) / entry)
    missing = [path for path in sources if not path.is_file()]
    if missing:
        raise ValueError(f"Missing source listed by {manifest}: {missing[0]}")
    return sources


def find_invalid_references(sources, check_design_units=False):
    tree = SyntaxTree.fromFiles([str(path) for path in sources])
    engine = pyslang.DiagnosticEngine(tree.sourceManager)
    parse_errors = [
        diagnostic for diagnostic in tree.diagnostics
        if engine.getSeverity(diagnostic.code, diagnostic.location) in
        (pyslang.DiagnosticSeverity.Error, pyslang.DiagnosticSeverity.Fatal)
    ]
    if parse_errors:
        details = ", ".join(str(diagnostic.code) for diagnostic in parse_errors)
        raise ValueError(f"SystemVerilog parsing failed: {details}")

    compilation = Compilation()
    compilation.addSyntaxTree(tree)
    source_manager = compilation.sourceManager
    findings = []
    for diagnostic in compilation.getAllDiagnostics():
        issue = REFERENCE_DIAGNOSTICS.get(diagnostic.code)
        if issue is None and check_design_units:
            issue = DESIGN_UNIT_DIAGNOSTICS.get(diagnostic.code)
        if issue is None:
            continue
        location = diagnostic.location
        findings.append({
            "path": Path(source_manager.getFullPath(location.buffer)),
            "line": source_manager.getLineNumber(location),
            "column": source_manager.getColumnNumber(location),
            "name": str(diagnostic.args[0]),
            "issue": issue,
        })
    return sorted(findings, key=lambda item: (
        str(item["path"]), item["line"], item["column"], item["name"], item["issue"]))


def find_forward_references(sources):
    return [finding for finding in find_invalid_references(sources)
            if finding["issue"] == "used before declaration"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rtl-root", type=Path, default=ROOT / "src/rtl")
    parser.add_argument("--manifest", action="append", type=Path,
                        help="Additional source manifest. Defaults to generated design manifests")
    args = parser.parse_args()
    rtl_root = args.rtl_root.resolve()
    sources = ordered_sources(rtl_root)
    if not sources:
        parser.error(f"No SystemVerilog sources found under {rtl_root}")

    manifests = args.manifest
    if manifests is None:
        manifests = sorted((ROOT / "src/gen").glob("*/generated/sources.f"))
    source_groups = [(str(rtl_root), sources, False)]
    try:
        source_groups += [
            (str(path), manifest_sources(path), True) for path in manifests]
        unique_sources = set(sources)
        unique_findings = {}
        for label, group, check_design_units in source_groups:
            for source in group:
                unique_sources.add(source.resolve())
            for finding in find_invalid_references(group, check_design_units):
                key = (finding["path"].resolve(), finding["line"],
                       finding["column"], finding["name"], finding["issue"])
                unique_findings[key] = finding
        findings = sorted(unique_findings.values(), key=lambda item: (
            str(item["path"]), item["line"], item["column"], item["name"], item["issue"]))
    except (OSError, ValueError) as error:
        parser.error(str(error))
    for finding in findings:
        try:
            path = finding["path"].relative_to(ROOT)
        except ValueError:
            path = finding["path"]
        print(f"{path}:{finding['line']}:{finding['column']}: "
              f"'{finding['name']}' {finding['issue']}")
    if findings:
        print(f"RTL symbol-reference check failed: {len(findings)} finding(s).")
        return 1
    print(f"RTL symbol-reference check passed: {len(unique_sources)} SystemVerilog files "
          f"across {len(source_groups)} source sets.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
