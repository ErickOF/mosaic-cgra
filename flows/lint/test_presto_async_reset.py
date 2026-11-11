"""Checks for the PRESTO-compatible asynchronous-reset audit."""

from pathlib import Path
import tempfile
import unittest

import presto_async_reset


class PrestoAsyncResetTest(unittest.TestCase):
    def audit(self, source):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "design.sv"
            path.write_text(source)
            return presto_async_reset.find_nonportable_async_processes([path])

    def test_top_level_reset_if_passes(self):
        findings = self.audit(
            "module portable(input logic clk, rstb, d, output logic q); "
            "always_ff @(posedge clk or negedge rstb) begin "
            "if (!rstb) q <= 0; else q <= d; end endmodule\n"
        )
        self.assertEqual(findings, [])

    def test_single_statement_reset_if_passes(self):
        findings = self.audit(
            "module portable(input logic clk, rstb, d, output logic q); "
            "always @(posedge clk or negedge rstb) if (!rstb) q <= 0; "
            "else q <= d; endmodule\n"
        )
        self.assertEqual(findings, [])

    def test_top_level_case_is_reported(self):
        findings = self.audit(
            "module nonportable(input logic clk, rstb, d, output logic q); "
            "always_ff @(posedge clk or negedge rstb) begin "
            "case (rstb) 0: q <= 0; default: q <= d; endcase end endmodule\n"
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["first_statement"], "case")

    def test_direct_task_call_is_reported(self):
        findings = self.audit(
            "module nonportable(input logic clk, rstb); task update; endtask "
            "always_ff @(posedge clk or negedge rstb) update(); endmodule\n"
        )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["first_statement"], "update")

    def test_synchronous_process_is_outside_scope(self):
        findings = self.audit(
            "module synchronous(input logic clk, rstb, d, output logic q); "
            "always_ff @(posedge clk) case (rstb) 0: q <= 0; "
            "default: q <= d; endcase endmodule\n"
        )
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
