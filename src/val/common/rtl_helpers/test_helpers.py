"""Check shared RTL algorithms against independent geometry/CRC oracles using Icarus."""

from pathlib import Path
from random import Random
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]


def crc32c(crc, value):
    """Polynomial long division, separate from the RTL's reflected recurrence."""
    polynomial = 0x11EDC6F41
    reverse = lambda value, width: int(f"{value:0{width}b}"[::-1], 2)
    remainder = reverse(crc, 32) ^ (reverse(value, 8) << 24)
    remainder <<= 8
    for bit in range(39, 31, -1):
        if remainder & (1 << bit):
            remainder ^= polynomial << (bit - 32)
    return reverse(remainder, 32)


class SharedHelpersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which("iverilog")
        runtime = shutil.which("vvp")
        if not compiler or not runtime:
            raise unittest.SkipTest("Icarus Verilog is required for RTL helper checks")
        random = Random(20261029)
        cls.vectors = [(0xFFFFFFFF, byte) for byte in b"123456789"]
        cls.vectors += [(random.getrandbits(32), random.getrandbits(8)) for _ in range(1000)]
        queries = "\n".join(
            f'$display("C %08h", crc_pkg::crc32c_byte(32\'h{crc:08x}, 8\'h{byte:02x}));'
            for crc, byte in cls.vectors
        )
        # The legacy expressions deliberately remain independent witnesses for X/Z
        # propagation: polynomial identities alone only establish two-state equivalence.
        bench = r"""
module helpers_tb;
    function automatic logic [31:0] legacy_byte(input logic [31:0] crc,
        input logic [7:0] value);
        logic [31:0] result;
        result = crc ^ {24'b0, value};
        for (int b = 0; b < 8; b++)
            result = result[0] ? (result >> 1) ^ 32'h82f63b78 : result >> 1;
        return result;
    endfunction
    logic [31:0] crc;
    logic [7:0] value;
    initial begin
        for (int width = 1; width <= 4096; width++)
            $display("G %0d %0d %0d %0d %0d", width, ecc_pkg::hamming_bits(width),
                ecc_pkg::code_width(width, 0), ecc_pkg::code_width(width, 1),
                ecc_pkg::code_width(width, 2));
        $display("H %0d", ecc_pkg::hamming_bits(2147483647));
        for (int position = 1; position < 267; position++)
            $display("I %0d %0d", position, ecc_pkg::data_index(position));
        for (int bit_index = 0; bit_index < 32; bit_index++) begin
            crc = 32'h12345678;
            crc[bit_index] = 1'bx;
            $display("F %b %b", legacy_byte(crc, 8'ha5), crc_pkg::crc32c_byte(crc, 8'ha5));
            crc[bit_index] = 1'bz;
            $display("F %b %b", legacy_byte(crc, 8'h5a), crc_pkg::crc32c_byte(crc, 8'h5a));
        end
        for (int bit_index = 0; bit_index < 8; bit_index++) begin
            value = 8'ha5;
            value[bit_index] = 1'bx;
            $display("F %b %b", legacy_byte(32'hffffffff, value),
                crc_pkg::crc32c_byte(32'hffffffff, value));
            value[bit_index] = 1'bz;
            $display("F %b %b", legacy_byte(32'hffffffff, value),
                crc_pkg::crc32c_byte(32'hffffffff, value));
        end
        QUERIES
        $finish;
    end
endmodule
""".replace("QUERIES", queries)
        with tempfile.TemporaryDirectory(prefix="mosaic-rtl-helpers-") as directory:
            directory = Path(directory)
            source = directory / "helpers_tb.sv"
            executable = directory / "simulation"
            source.write_text(bench)
            sources = [ROOT / f"src/rtl/common/{name}_pkg.sv" for name in ("ecc", "crc")]
            sources.append(source)
            compile_result = subprocess.run(
                [compiler, "-g2012", "-s", "helpers_tb", "-o", str(executable),
                 *map(str, sources)], capture_output=True, text=True)
            if compile_result.returncode:
                raise RuntimeError(compile_result.stderr)
            result = subprocess.run([runtime, str(executable)], capture_output=True,
                                    text=True, check=True)
        cls.rows = [line.split() for line in result.stdout.splitlines()]

    def test_ecc_geometry(self):
        geometries = [list(map(int, row[1:])) for row in self.rows if row[0] == "G"]
        self.assertEqual(len(geometries), 4096)
        for width, hamming, plain, parity, secded in geometries:
            # Count representable single-error locations until all data + parity fit.
            expected = next(n for n in range(1, 33) if 2 ** n >= width + n + 1)
            self.assertEqual((hamming, plain, parity), (expected, width, width + 1))
            stripes = [min(256, width - start) for start in range(0, width, 256)]
            self.assertEqual(secded, sum(bits + next(n for n in range(1, 10)
                if 2 ** n >= bits + n + 1) + 1 for bits in stripes))
        self.assertIn(["H", "32"], self.rows)
        for _, position, index in (row for row in self.rows if row[0] == "I"):
            position = int(position)
            self.assertEqual(int(index), len([n for n in range(1, position)
                if n.bit_count() != 1]))

    def test_crc_polynomial(self):
        actual = [int(row[1], 16) for row in self.rows if row[0] == "C"]
        self.assertEqual(actual, [crc32c(crc, byte) for crc, byte in self.vectors])
        crc = 0xFFFFFFFF
        for byte in b"123456789":
            crc = crc32c(crc, byte)
        self.assertEqual(crc ^ 0xFFFFFFFF, 0xE3069283)

    def test_crc_unknown_values(self):
        rows = [row for row in self.rows if row[0] == "F"]
        self.assertEqual(len(rows), 80)
        for _, previous, current in rows:
            self.assertEqual(previous, current)



if __name__ == "__main__":
    unittest.main()
