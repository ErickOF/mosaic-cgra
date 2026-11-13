"""Checks for the PRESTO-compatible declaration audit."""

from pathlib import Path
import tempfile
import unittest

import presto_declarations


class PrestoDeclarationTest(unittest.TestCase):
    def audit(self, source):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "design.sv"
            path.write_text(source)
            return presto_declarations.find_nonportable_declarations([path])

    def test_unique_genvar_and_net_names_pass(self):
        findings = self.audit(
            "module portable;\n"
            "    for (genvar lane = 0; lane < 2; lane++) begin : g_lane end\n"
            "    wire value;\n"
            "endmodule\n"
        )
        self.assertEqual(findings, [])

    def test_same_scope_genvar_and_net_collision_is_reported(self):
        findings = self.audit(
            "module nonportable;\n"
            "    for (genvar lane = 0; lane < 2; lane++) begin : g_lane end\n"
            "    wire lane;\n"
            "endmodule\n"
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["name"], "lane")
        self.assertIn("collides", findings[0]["issue"])

    def test_nested_genvar_can_match_module_net(self):
        findings = self.audit(
            "module portable;\n"
            "    if (1) begin : g_enabled\n"
            "        for (genvar lane = 0; lane < 2; lane++) begin : g_lane end\n"
            "    end\n"
            "    wire lane;\n"
            "endmodule\n"
        )
        self.assertEqual(findings, [])

    def test_declaration_before_initializer_use_passes(self):
        findings = self.audit(
            "module portable;\n"
            "    wire ready;\n"
            "    wire finish = ready;\n"
            "endmodule\n"
        )
        self.assertEqual(findings, [])

    def test_adjacent_forward_initializer_reference_is_reported(self):
        findings = self.audit(
            "module nonportable;\n"
            "    wire finish = ready;\n"
            "    wire ready;\n"
            "endmodule\n"
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["name"], "ready")
        self.assertIn("before", findings[0]["issue"])


if __name__ == "__main__":
    unittest.main()
