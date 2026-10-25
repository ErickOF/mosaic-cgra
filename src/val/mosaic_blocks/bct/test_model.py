"""Unit checks for the independent arithmetic and context oracles."""
import unittest
from bct.defaults import DEFAULTS
from bct.model import arithmetic, pack, unpack, layout, signed


class ModelTests(unittest.TestCase):
    def test_context_roundtrip(self):
        for width in (8, 16, 32, 64):
            p = DEFAULTS | dict(DATA_WIDTH=width)
            c = {name: (1 << bits) - 1 for name, (_, bits) in layout(p).items()}
            self.assertEqual(unpack(p, pack(p, c)), c)

    def test_small_mixed_products(self):
        p = DEFAULTS | dict(DATA_WIDTH=8, MULTIPLY_OPERAND_WIDTH=4)
        for a in range(16):
            for b in range(16):
                for sa, sb in ((0, 0), (0, 1), (1, 0), (1, 1)):
                    actual, _ = arithmetic(p, dict(fu=1, signed_a=sa, signed_b=sb), a, b)
                    self.assertEqual(actual, ((signed(a, 4) if sa else a) *
                        (signed(b, 4) if sb else b)) % 256)

    def test_alu_saturation_boundaries(self):
        p = DEFAULTS | dict(DATA_WIDTH=8)
        for a, b, expected in ((127, 1, 127), (128, 255, 128), (255, 1, 0)):
            result, _ = arithmetic(p, dict(opcode=0, signed_a=1, saturate=1), a, b)
            self.assertEqual(result, expected)
