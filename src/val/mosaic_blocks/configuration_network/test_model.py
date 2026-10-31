"""Hand-derived ABI, topology, CRC, permission and endpoint-semantic checks."""

import unittest
from configuration_network.defaults import DEFAULTS
from configuration_network.layout import (
    dimensions,
    tables,
    packet,
    endpoint,
    topology,
    preflight,
    crc32c,
)
from configuration_network.model import NativeEndpoint


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.p = DEFAULTS | dict(
            NUM_ENDPOINTS=4, NUM_TILE_ENDPOINTS=4, NUM_INFRA_ENDPOINTS=0
        )
        self.p.update(tables(self.p))
        self.a = dimensions(self.p)

    def request(self, **kwargs):
        return (
            dict(
                command=1,
                destination_mask=1,
                owner_id=0,
                kernel_id=3,
                package_id=7,
                epoch=0,
                context_id=0,
                expected_version=0,
                word_index=0,
                write_data=0,
                write_strobe=255,
                expected_crc=0,
                tag=1,
                protocol=1,
                flags=0,
                transaction_id=0,
                sequence_id=0,
            )
            | kwargs
        )

    def test_crc(self):
        self.assertEqual(crc32c(b"123456789"), 0xE3069283)

    def test_packet_layout(self):
        value = packet(self.p, dict(command=1, transaction=2, tag=3, protocol=1))
        self.assertEqual(value & ((1 << 29) - 1), 1 | (2 << 5) | (3 << 13))
        self.assertEqual(
            value >> (self.a["CP"] - 32),
            crc32c(
                (value & ((1 << (self.a["CP"] - 32)) - 1)).to_bytes(
                    (self.a["CP"] - 32) // 8, "little"
                )
            ),
        )

    def test_padding_is_protected(self):
        v = packet(self.p, dict(protocol=1))
        body = v & ((1 << (self.a["CP"] - 32)) - 1)
        self.assertNotEqual(
            v >> (self.a["CP"] - 32),
            crc32c(
                (body ^ (1 << self.a["CB"])).to_bytes(
                    (self.a["CP"] - 32) // 8, "little"
                )
            ),
        )

    def test_tree(self):
        t = topology(self.p)
        self.assertEqual(t["parents"], [-1, 0, 0, 0, 0])
        self.assertEqual(t["routes"], [15, 1, 2, 4, 8])
        self.assertEqual(t["depths"], [1] * 4)

    def test_default_four_levels(self):
        t = topology(DEFAULTS)
        self.assertEqual(t["diameter"], 3)
        self.assertEqual(t["routes"][0], (1 << 20) - 1)

    def test_daisy(self):
        t = topology(self.p | dict(TOPOLOGY_PROFILE=0))
        self.assertEqual(t["parents"], [-1, 0, 1, 0, 1, 2, 2])
        self.assertEqual(t["depths"], [1, 2, 3, 3])

    def test_sparse(self):
        p = self.p | dict(ENDPOINT_PRESENT_MASK=0b1101)
        self.assertEqual(topology(p)["routes"][0], 13)
        self.assertFalse(endpoint(p, 1)["present"])

    def test_modes(self):
        self.assertEqual(
            preflight(self.p, self.request(command=2, destination_mask=3), 0, 15), 3
        )
        self.assertEqual(preflight(self.p, self.request(destination_mask=0), 0, 15), 3)
        self.assertEqual(preflight(self.p, self.request(command=8), 0, 15), 2)

    def test_permissions(self):
        self.assertEqual(preflight(self.p, self.request(owner_id=7), 0, 15), 5)
        self.assertEqual(preflight(self.p, self.request(), 0, 14), 19)

    def test_schema(self):
        p = self.p | dict(ENDPOINT_SCHEMA_TABLE=4 | (5 << 32) | (4 << 64) | (4 << 96))
        self.assertEqual(preflight(p, self.request(destination_mask=3), 0, 15), 6)

    def test_masked_writes_and_versions(self):
        n = NativeEndpoint(self.p, 0)
        r = self.request(write_data=0xAABBCCDD, write_strobe=5)
        self.assertEqual(n.execute(r)["context_version"], 1)
        self.assertEqual(n.context(0)["words"][0], 0x00BB00DD)
        self.assertFalse(n.context(0)["validated"])

    def test_incomplete_image(self):
        n = NativeEndpoint(self.p, 0)
        n.execute(self.request(write_data=0x55))
        r = n.execute(
            self.request(command=3, expected_version=1, expected_crc=n.crc(0))
        )
        self.assertNotEqual(r["status"], 0)

    def test_cancel_retains_data(self):
        n = NativeEndpoint(self.p, 0)
        n.execute(self.request(write_data=0x55))
        n.cancel()
        self.assertEqual(n.context(0)["words"][0], 0x55)
        self.assertFalse(n.context(0)["written"])
        self.assertFalse(n.context(0)["validated"])
