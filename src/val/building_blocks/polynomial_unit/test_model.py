"""Check the oracle against Python rational arithmetic and exhaustive bit faults."""
from fractions import Fraction
import unittest
from polynomial_unit.images import check_image
from polynomial_unit.model import decode_word, encode, rounded


class ModelTests(unittest.TestCase):
    def test_rounding_against_fraction(self):
        for value in range(-1024, 1025):
            for shift in range(10):
                rational = Fraction(value, 1 << shift)
                self.assertEqual(rounded(value, shift, False)[0], int(rational))
                self.assertEqual(rounded(value, shift, True)[0], round(rational))

    def test_protection_bits(self):
        for width in (8, 12, 18, 24, 32):
            for value in (0, 1, (1 << (width - 1)) - 1):
                for protection in (1, 2):
                    _, bits = encode(value, width, protection)
                    for bit in range(bits):
                        data, corrected, bad = decode_word(value, width, protection, 1 << bit)
                        self.assertEqual((corrected, bad), (protection == 2, protection == 1))
                        if corrected:
                            self.assertEqual(data, value)
                    if protection == 2:
                        for first in range(bits):
                            for second in range(first):
                                self.assertTrue(decode_word(value, width, protection,
                                    (1 << first) | (1 << second))[2])

    def test_versioned_image(self):
        check_image()
