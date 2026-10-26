"""Pure Python checks with hand-derived topology, CRC, and latency examples."""

import unittest
from static_mesh.defaults import DEFAULTS
from static_mesh.topology import boundary, crc32c, dimensions, image, physical
from static_mesh.model import MeshModel


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.p = DEFAULTS | dict(MESH_ROWS=2, MESH_COLS=2)

    def test_crc_vector(self):
        self.assertEqual(crc32c(b"123456789"), 0xE3069283)

    def test_directed_edges(self):
        g = physical(self.p)
        self.assertEqual(len(g["edges"]), 24)
        self.assertEqual(g["edges"][0]["source_node"], 0)
        self.assertEqual(g["edges"][0]["destination_node"], 1)
        self.assertEqual(g["edges"][1]["source_node"], 1)
        self.assertEqual(
            boundary(self.p),
            [
                (0, 0, 0),
                (1, 0, 0),
                (2, 1, 0),
                (3, 1, 0),
                (0, 3, 0),
                (2, 3, 0),
                (1, 2, 0),
                (3, 2, 0),
            ],
        )

    def test_hole_removes_incident_links(self):
        g = physical(self.p | dict(NODE_PRESENT_MASK=0b1101))
        for edge in g["edges"]:
            if 1 in (edge.get("source_node"), edge.get("destination_node")):
                self.assertFalse(g["mask"] >> edge["index"] & 1)

    def test_rank_and_arrival(self):
        raw, proof, c = image(self.p, {(0, 4): 0, (1, 0): 5})
        self.assertEqual(c["ranks"], {(0, 0): 0, (1, 5): 1})
        self.assertEqual(c["arrivals"], {(0, 0): 0, (1, 5): 1})
        self.assertNotEqual(proof, 0)
        self.assertEqual(raw & 255, 1)

    def test_cycle_rejection(self):
        # Flexible two-node U-turn route is physically legal but dependent cyclically.
        with self.assertRaisesRegex(AssertionError, "Cyclic"):
            image(self.p | dict(CONNECTIVITY_PROFILE=2), {(0, 4): 4, (1, 5): 5})

    def test_orphan_rejection(self):
        with self.assertRaisesRegex(AssertionError, "Orphan"):
            image(self.p, {(1, 0): 5})

    def test_two_node_latency(self):
        m = MeshModel(self.p, {(0, 4): 0, (1, 0): 5})
        ports = dict(
            i_reset_n=1,
            i_flush=0,
            o_faulted_link_mask=0,
            i_tile_rx_ready=255,
            i_boundary_tx_ready=255,
            i_tile_tx_valid=1,
            i_tile_tx_data=17,
            i_tile_tx_metadata=123,
            i_boundary_rx_valid=0,
            i_boundary_rx_data=0,
            i_boundary_rx_metadata=0,
        )
        self.assertEqual(m.step(ports)["tile"], {})
        ports["i_tile_tx_valid"] = 0
        self.assertEqual(m.step(ports)["tile"], {})
        self.assertEqual(m.step(ports)["tile"], {2: (17, 123)})
        self.assertEqual(m.occupancy(), 0)

    def test_multicast_tree(self):
        m = MeshModel(self.p, {(0, 0): 0, (0, 4): 0, (1, 0): 5})
        self.assertEqual(m.endpoints((0, 0)), [("tile", 0), ("tile", 2)])
