"""Cross-check model primitives against Python's rational and integer arithmetic."""
from fractions import Fraction
from itertools import product
import unittest
from reciprocal_unit.images import image, seeds, verify_default_image
from reciprocal_unit.model import encode, protected_seed, rounded


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
        for width, fraction, address in ((16, 12, 3), (24, 20, 6), (48, 40, 8)):
            for index, value in enumerate(seeds(width, fraction, address)):
                midpoint = Fraction(1, 2) + Fraction(2 * index + 1, 1 << (address + 2))
                self.assertEqual(value, round((1 << fraction) / midpoint))
            self.assertNotEqual(image(width, fraction, address)['image_id'], 0)

    def test_seed_protection(self):
        for width in (16, 24, 48):
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
        # Every legal normalized state of a reduced F=6 format; compare the two
        # explicit rounding points with rational arithmetic, including ties.
        for n, y, nearest in product(range(32, 64), range(256), (0, 1)):
            t = rounded(n * y, 6, nearest)[0]
            u = 128 - t
            next_y = rounded(y * u, 6, nearest)[0]
            rounding = round if nearest else int
            self.assertEqual(t, rounding(Fraction(n * y, 64)))
            self.assertEqual(next_y, rounding(Fraction(y * u, 64)))
