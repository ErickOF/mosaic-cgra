"""Simulator-independent checks of mapping, region transactions, and byte merges."""
import unittest
from banked_scratchpad.defaults import DEFAULTS
from banked_scratchpad.model import Architecture, encode_descriptor, map_address


class ModelTests(unittest.TestCase):
    def test_mapping_bijection(self):
        for banks in (1, 2, 3, 4, 8, 16, 32):
            for mode in (0, 1) if banks & (banks - 1) == 0 else (0,):
                p = DEFAULTS | dict(NUM_BANKS=banks, BANK_DEPTH_WORDS=8, MAP_MODE=mode)
                seen = {map_address(p, addr) for addr in range(banks * 64)}
                self.assertEqual(seen, {(b, addr) for b in range(banks) for addr in range(64)})

    def test_byte_merge(self):
        m = Architecture(DEFAULTS)
        x = dict(addr=0, size=8, opcode=1, wdata=0x1122334455667788)
        m.access(x)
        m.access(x | dict(addr=3, size=1, wdata=0xAB))
        self.assertEqual(m.access(x | dict(opcode=0))[0], 0x11223344AB667788)

    def test_protection(self):
        for mode in (1, 2):
            m = Architecture(DEFAULTS | dict(PROTECTION_MODE=mode, PARITY_GRANULARITY=16))
            x = dict(addr=0, size=8, opcode=1, wdata=0x1234)
            m.access(x)
            m.faults[0, 0] = 1
            result = m.access(x | dict(opcode=0))
            self.assertEqual(result, (0, 7, 0, 1) if mode == 1 else (0x1234, 0, 1, 0))
            m.faults[0, 0] = 3
            before = m.memory.copy()
            m.access(x | dict(size=1))
            self.assertEqual(m.memory, before)

    def test_descriptor_width(self):
        m = Architecture(DEFAULTS)
        self.assertEqual(encode_descriptor(m.a, m.regions[0]), 0)
        full = {k: (1 << w) - 1 for k, w in __import__(
            'banked_scratchpad.config', fromlist=['descriptor_fields']).descriptor_fields(m.a)}
        self.assertEqual(encode_descriptor(m.a, full).bit_length(), m.a['DW'])
