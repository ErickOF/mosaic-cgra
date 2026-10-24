"""Independent standard CRC vectors and bytearray/ownership model checks."""
from pathlib import Path
import random
import unittest
from tile_shell.config import TileShellConfig
from tile_shell.defaults import DEFAULTS
from tile_shell.model import ShellModel, crc32c

class ModelTests(unittest.TestCase):
    def model(self):
        return ShellModel(TileShellConfig(DEFAULTS, 0, 1000, Path('unused')))

    def request(self, **overrides):
        return {('i_cfg_request_' + k): v for k, v in (dict(command=0, tile_id=0, owner_id=5,
            context_id=0, word_index=0, write_data=0, write_strobe=0, expected_crc=0, tag=1) | overrides).items()}

    def test_crc32c(self):
        self.assertEqual(crc32c(b''), 0)
        self.assertEqual(crc32c(b'123456789'), 0xe3069283)
        reference = crc32c(bytes(range(256)))
        for bit in range(256 * 8):
            changed = bytearray(range(256))
            changed[bit // 8] ^= 1 << (bit % 8)
            self.assertNotEqual(crc32c(changed), reference)

    def test_byte_write_masks(self):
        m, r = self.model(), random.Random(20261025)
        expected = bytearray(64)
        for tag in range(1, 100):
            word, strobe, data = r.randrange(8), r.randrange(256), r.getrandbits(64)
            m.config(self.request(word_index=word, write_strobe=strobe, write_data=data, tag=tag))
            for byte in range(8):
                if strobe >> byte & 1:
                    expected[word * 8 + byte] = data >> (byte * 8) & 255
            self.assertEqual(m.image(0), expected)
            self.assertEqual(m.versions[0], tag)

    def test_unauthorized_mutation(self):
        m = self.model()
        m.owner, m.kernel = 5, 3
        before = m.image(0)
        _, error = m.config(self.request(owner_id=4, write_data=0xffff, write_strobe=255))
        self.assertEqual(error, 3)
        self.assertEqual(m.image(0), before)
        self.assertEqual(m.versions[0], 0)
        self.assertEqual(m.written[0], 0)
