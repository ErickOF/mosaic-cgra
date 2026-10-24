"""Independent rational checks for the fixed-point scoreboard's primitives."""
from fractions import Fraction
from itertools import product
from pathlib import Path
import unittest

from exp_unit.config import DEFAULTS, ExpUnitConfig
from exp_unit.model import image, predict, rounded


class ModelTests(unittest.TestCase):
    def test_signed_rounding(self):
        for value, shift, nearest in product(range(-1024, 1025), range(12), (0, 1)):
            rational = Fraction(value, 1 << shift)
            actual, inexact = rounded(value, 1 << shift, nearest)
            self.assertEqual(actual, round(rational) if nearest else int(rational))
            self.assertEqual(inexact, rational.denominator != 1)

    def test_floor_partition(self):
        # Signed bit partition must match mathematical floor, including values
        # where truncation would choose the wrong table segment and exponent.
        for z in range(-4096, 4096):
            bits = z % (1 << 13)
            integer = bits >> 6
            if integer & 64:
                integer -= 128
            fraction = bits & 63
            self.assertEqual(integer, Fraction(z, 64).__floor__())
            self.assertEqual(integer * 64 + fraction, z)
            self.assertTrue(0 <= fraction < 64)

    def test_interpolation_rationals(self):
        for address in (2, 3):
            table = image(address, 8)
            self.assertEqual((table[0], table[-1]), (256, 512))
            for segment, remainder, nearest in product(range(1 << address), range(32), (0, 1)):
                lower, upper = table[segment:segment + 2]
                exact = Fraction((upper - lower) * remainder, 32)
                actual = lower + rounded(exact.numerator, exact.denominator, nearest)[0]
                expected = lower + (round(exact) if nearest else int(exact))
                self.assertEqual(actual, expected)
                self.assertTrue(lower <= actual <= upper)

    def test_exact_exp2_integer_scaling(self):
        c = ExpUnitConfig(DEFAULTS, 0, 1000, False, False, Path('unused'))
        for exponent, nearest, signed in product(range(-20, 17), (0, 1), (0, 1)):
            request = dict(i_request_operand=(exponent << c.INPUT_FRACTION_WIDTH) %
                           (1 << c.INPUT_WIDTH), i_request_base=1, i_request_interpolate=1,
                           i_request_round_mode=nearest, i_request_output_signed=signed,
                           i_request_predicate=1, i_request_context_id=0, i_request_tag=0)
            actual, _ = predict(c, request)
            exact = Fraction(2) ** (exponent + c.OUTPUT_FRACTION_WIDTH)
            maximum = (1 << (c.OUTPUT_WIDTH - signed)) - 1
            expected = min(maximum, round(exact) if nearest else int(exact))
            self.assertEqual(actual['o_result_data'], expected)
            self.assertEqual(actual['o_result_overflow'], exact > maximum)
            self.assertEqual(actual['o_result_underflow'], expected == 0)
            self.assertEqual(actual['o_result_saturated'], exact > maximum)
