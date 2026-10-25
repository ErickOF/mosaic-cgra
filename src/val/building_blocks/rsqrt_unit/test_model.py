"""Cross-check model primitives against Python's rational and integer arithmetic."""
from fractions import Fraction
from itertools import product
import unittest
from rsqrt_unit.images import image, seeds, verify_default_image
from rsqrt_unit.model import encode, protected_seed, rounded


class ModelTests(unittest.TestCase):
    def test_rounding(self):
        for value, shift, nearest in product(range(-1024, 1025), range(12), (0, 1)):
            actual, inexact, tie = rounded(value, shift, nearest)
            rational = Fraction(value, 1 << shift)
            self.assertEqual(actual, round(rational) if nearest else int(rational))
            self.assertEqual(inexact, rational.denominator != 1)
            self.assertEqual(tie, rational.denominator == 2)

    def test_seed_image(self):
        verify_default_image()
        from math import isqrt
        for width, fraction, address in ((18, 14, 3), (28, 22, 6), (52, 44, 8)):
            for index, value in enumerate(seeds(width, fraction, address)):
                parity, region = divmod(index, 1 << address)
                denominator = (1 << (address + 1)) + 2 * region + 1
                numerator = 1 << (2 * fraction + address + 1 - parity)
                floor = isqrt(numerator // denominator)
                middle = denominator * (2 * floor + 1) ** 2
                expected = floor + (4 * numerator > middle or
                    (4 * numerator == middle and floor % 2))
                self.assertEqual(value, expected)
            self.assertNotEqual(image(width, fraction, address)['image_id'], 0)

    def test_seed_protection(self):
        for width in (18, 28, 52):
            value = (1 << (width - 2)) + 37
            for protection in (1, 2):
                _, bits = encode(value, width, protection)
                for bit in range(bits):
                    data, corrected, bad = protected_seed(value, width, protection, 1 << bit)
                    self.assertEqual(bad, protection == 1)
                    self.assertEqual(corrected, protection == 2)
                    if corrected:
                        self.assertEqual(data, value)
                if protection == 2:
                    for first in range(bits):
                        for second in range(first + 1, bits):
                            _, corrected, bad = protected_seed(value, width, protection,
                                (1 << first) | (1 << second))
                            self.assertTrue(bad)
                            self.assertFalse(corrected)

    def test_reduced_newton(self):
        # Enumerate a reduced normalized interval, seeds and both roundings with
        # rational references for all three product boundaries.
        for n, y, nearest in product(range(16, 64), range(1, 17), (0, 1)):
            rounding = round if nearest else int
            square = rounded(y * y, 4, nearest)[0]
            product_value = rounded(n * square, 4, nearest)[0]
            correction = 48 - product_value
            update = rounded(y * correction, 5, nearest)[0]
            self.assertEqual(square, rounding(Fraction(y * y, 16)))
            self.assertEqual(product_value, rounding(Fraction(n * square, 16)))
            self.assertEqual(update, rounding(Fraction(y * correction, 32)))

    def test_floor_exponent(self):
        for exponent in range(-64, 65):
            half, parity = divmod(exponent, 2)
            self.assertEqual(2 * half + parity, exponent)
            self.assertEqual(half, exponent // 2)
            self.assertIn(parity, (0, 1))
