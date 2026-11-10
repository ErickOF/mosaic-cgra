"""Checks for the PRESTO-compatible declaration-order audit."""

from pathlib import Path
import tempfile
import unittest

import forward_references


class ForwardReferenceTest(unittest.TestCase):
    def audit(self, source):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "design.sv"
            path.write_text(source)
            return forward_references.find_invalid_references([path])

    def test_declaration_before_use_passes(self):
        findings = self.audit(
            "module ordered; wire declared; wire observed = declared; endmodule\n")
        self.assertEqual(findings, [])

    def test_use_before_declaration_is_reported(self):
        findings = self.audit(
            "module forward; wire observed = declared_later; "
            "wire declared_later; endmodule\n")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["name"], "declared_later")
        self.assertEqual(findings[0]["issue"], "used before declaration")

    def test_undeclared_identifier_is_reported(self):
        findings = self.audit(
            "`default_nettype none\nmodule unresolved; "
            "wire observed = missing; endmodule\n")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["name"], "missing")
        self.assertEqual(findings[0]["issue"], "is not declared")

    def test_unknown_module_is_reported_for_complete_design(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "design.sv"
            path.write_text("module wrapper; missing child(); endmodule\n")
            findings = forward_references.find_invalid_references(
                [path], check_design_units=True)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["name"], "missing")
        self.assertEqual(findings[0]["issue"], "references an unknown module")

    def test_manifest_paths_are_project_relative(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "rtl/design.sv"
            source.parent.mkdir()
            source.write_text("module design; endmodule\n")
            manifest = root / "sources.f"
            manifest.write_text("# ordered sources\nrtl/design.sv\n")
            self.assertEqual(
                forward_references.manifest_sources(manifest, root), [source])


if __name__ == "__main__":
    unittest.main()
