"""Checks for the PRESTO-compatible parameter-guard audit."""

from pathlib import Path
import tempfile
import unittest

import presto_parameter_guards


class PrestoParameterGuardTest(unittest.TestCase):
    def audit(self, source):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "design.sv"
            path.write_text(source)
            return presto_parameter_guards.find_explicit_x_parameter_checks([path])

    def test_known_value_predicate_passes(self):
        findings = self.audit(
            "module portable #(parameter WIDTH = 8, "
            "localparam bit VALID = (((^WIDTH == 1'b0) || "
            "(^WIDTH == 1'b1)) === 1'b1)) (); endmodule\n"
        )
        self.assertEqual(findings, [])

    def test_runtime_signal_check_is_not_a_parameter_guard(self):
        findings = self.audit(
            "module runtime(input logic [3:0] i_data); "
            "wire known = ^i_data !== 1'bx; endmodule\n"
        )
        self.assertEqual(findings, [])

    def test_explicit_known_parameter_check_is_reported(self):
        findings = self.audit(
            "module nonportable #(parameter WIDTH = 8, "
            "localparam bit VALID = (^WIDTH !== 1'bx)) (); endmodule\n"
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["name"], "WIDTH")
        self.assertEqual(findings[0]["operator"], "!==")

    def test_spaced_unknown_parameter_check_is_reported(self):
        findings = self.audit(
            "module nonportable #(parameter MASK = 0); "
            "if ( ^ MASK === 1'bx) bad child(); endmodule\n"
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["name"], "MASK")
        self.assertEqual(findings[0]["operator"], "===")

    def test_parameter_concatenation_check_is_reported(self):
        findings = self.audit(
            "module nonportable #(parameter MAP = 0, parameter MASK = 0); "
            "localparam bit VALID = (^{MAP, MASK} !== 1'bx); endmodule\n"
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["name"], "{MAP, MASK}")
        self.assertEqual(findings[0]["operator"], "!==")

    def test_runtime_concatenation_with_width_constants_passes(self):
        findings = self.audit(
            "module runtime #(parameter WIDTH = 4) "
            "(input logic [WIDTH-1:0] i_data); "
            "wire known = ^{i_data[WIDTH-1:0]} !== 1'bx; endmodule\n"
        )
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
