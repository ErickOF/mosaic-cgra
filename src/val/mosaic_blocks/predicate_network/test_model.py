"""Hand-derived predicate packing, route, schedule and independent-model checks."""

import unittest
from static_mesh.topology import crc32c
from predicate_network.defaults import DEFAULTS
from predicate_network.topology import dimensions, physical, graph, route_image, image, metadata


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.p = DEFAULTS | dict(NETWORK_ROWS=2, NETWORK_COLS=2, MAX_TREE_DESTINATIONS=4)

    def test_crc_vector(self):
        self.assertEqual(crc32c(b"123456789"), 0xE3069283)

    def test_metadata_layout(self):
        self.assertEqual(
            metadata(self.p, 0x12, 0x3456, 0x789A, 2, 0xBC, 0xDE, 3, 2), 0x8F7AF2789A345612
        )

    def test_opaque_metadata(self):
        p = self.p | dict(PREDICATE_METADATA_WIDTH=80)
        self.assertEqual(metadata(p, 1, 2, 3, 1, 4, 5, opaque=0xABCD) >> 64, 0xABCD)

    def test_false_and_invalid_differ(self):
        self.assertNotEqual(
            metadata(self.p, 1, 1, 3, 1, 0, 0, 0), metadata(self.p, 1, 1, 3, 1, 0, 0, 2)
        )
        self.assertNotEqual(0 | (1 << 8), 0 | (0 << 8))

    def test_route_image(self):
        # I=O=5: 20 enables precede 20 three-bit source selectors.
        self.assertEqual(route_image(self.p, {(1, 0): 4}), (1 << 5) | (4 << 35))

    def test_two_node_depth(self):
        c = graph(self.p, {(0, 3): 0, (1, 0): 4})
        self.assertEqual(c["depths"], {(0, 0): 0, (1, 4): 1})
        self.assertEqual(c["destinations"][0, 0], [("tile", 1)])

    def test_startup_slot_shift(self):
        c = image(self.p, {(0, 3): 0, (1, 0): 4}, scheduled=True, period=3)
        self.assertEqual(c["schedule_enable"], 1)
        self.assertEqual(c["slots"], 2)

    def test_orphan_rejected(self):
        with self.assertRaisesRegex(AssertionError, "orphan"):
            graph(self.p, {(1, 0): 4})

    def test_dangling_rejected(self):
        with self.assertRaisesRegex(AssertionError, "dangling"):
            graph(self.p, {(0, 3): 0})

    def test_tree_limit(self):
        r = {(0, 0): 0, (0, 3): 0, (1, 0): 4}
        self.assertEqual(len(graph(self.p, r)["destinations"][0, 0]), 2)
        with self.assertRaisesRegex(AssertionError, "tree"):
            graph(self.p | dict(MAX_TREE_DESTINATIONS=1), r)

    def test_multicast_off(self):
        with self.assertRaisesRegex(AssertionError, "multicast"):
            graph(self.p | dict(SUPPORT_MULTICAST=0), {(0, 0): 0, (0, 3): 0, (1, 0): 4})

    def test_disabled_link(self):
        p = self.p | dict(LINK_PRESENT_MASK=0xFE)
        self.assertFalse(physical(p)["mask"] & 1)
        with self.assertRaisesRegex(AssertionError, "physical"):
            graph(p, {(0, 3): 0, (1, 0): 4})

    def test_cardinal_cycle(self):
        with self.assertRaisesRegex(AssertionError, "cycle"):
            graph(self.p, {(0, 3): 2, (1, 2): 4, (3, 4): 1, (2, 1): 3})

    def test_boundary_ingress_depth(self):
        p = self.p | dict(EXPOSE_BOUNDARY_PORTS=1)
        c = graph(p, {(0, 0): 1})
        self.assertEqual(c["depths"], {(0, 1): 1})
        self.assertEqual(c["link_depth"], {8: 0})

    def test_single_node_sentinel(self):
        p = self.p | dict(NETWORK_ROWS=1, NETWORK_COLS=1, MAX_TREE_DESTINATIONS=1)
        a = dimensions(p)
        self.assertEqual((a["L"], a["LB"]), (0, 1))
        self.assertEqual(physical(p)["mask"], 0)
