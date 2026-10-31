"""Small, hand-calculated checks keep the independent oracle honest."""
import unittest
from mst.defaults import DEFAULTS
from mst.model import pack, unpack, positions, convert, stream_beats


class ModelTests(unittest.TestCase):
    def test_affine_rectangle(self):
        self.assertEqual(positions(dict(base=40, inner_stride=-3, outer_stride=20), 2,
            dict(inner_count=3, outer_count=2), 0), [40, 37, 34, 60, 57, 54])
        self.assertEqual(positions(dict(base=4), 0,
            dict(inner_count=3, outer_count=1), 2), [4, 8, 12])

    def test_conversion(self):
        self.assertEqual(convert(0xff800123, 1, 0, 1, signed_mode=1, saturate=1), (0x807f, True))
        self.assertEqual(convert(0xfe80, 0, 1, 1, signed_mode=1), (0xfffeff80, False))
        self.assertEqual(convert(0x01020304, 0, 0, 2, reverse=1), (0x04030201, False))

    def test_packed_layout(self):
        self.assertEqual(pack(DEFAULTS, 'mode', dict(transfer=5, address_mode=2)), 21)
        value = dict(command=7, generation=2, owner=5)
        self.assertEqual(unpack(DEFAULTS, 'identity', pack(DEFAULTS, 'identity', value))['owner'], 5)
        self.assertEqual(pack(DEFAULTS, 'identity', value), (5 << 32) | (2 << 16) | 7)

    def test_partial_position_packets(self):
        p = DEFAULTS | dict(SHELL_DATA_WIDTH=32)
        d = dict(identity=dict(context_id=1, version=2), source=dict(channel=0),
            destination=dict(channel=0), control=dict(inner_count=1, outer_count=1),
            format=dict(source_log2=3, destination_log2=3, lane_log2=0, eos=1))
        beats = stream_beats(p, d, [0x0807060504030201])
        self.assertEqual([v for v, _ in beats], [0x04030201, 0x08070605])
        self.assertEqual(unpack(p, 'stream', beats[0][1])['last'], 0)
        self.assertEqual(unpack(p, 'stream', beats[1][1])['eos'], 1)
