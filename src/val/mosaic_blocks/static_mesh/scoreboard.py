"""Independent cycle predictions plus end-to-end exact-once branch ledgers."""

from collections import defaultdict, deque
from pyuvm import ConfigDB, uvm_subscriber
from static_mesh.model import MeshModel


class MeshScoreboard(uvm_subscriber):
    def build_phase(self):
        self.c = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.model = None
        self.version = None
        self.ledger = defaultdict(deque)
        self.prediction = None

    def write(self, obs):
        p, a = obs.ports, self.c.aliases
        if obs.phase == "post":
            if self.prediction is not None:
                assert p["o_directed_link_active"] == self.prediction["links"], (
                    "Link events",
                    obs.item.get_name(),
                )
            return
        self.coverage.cycles += 1
        for n in (
            "o_tile_tx_ready",
            "o_tile_rx_valid",
            "o_boundary_rx_ready",
            "o_boundary_tx_valid",
            "o_idle",
            "o_quiescent",
            "o_cfg_ready",
            "o_error",
            "o_context_valid",
        ):
            assert p[n] is not None, ("Unknown public control", n, obs.item.get_name())
        if not p["i_reset_n"] or p["i_flush"]:
            self.ledger.clear()
            if self.model:
                self.model.step(p)
            self.prediction = None
            assert not (
                p["o_tile_tx_ready"]
                or p["o_tile_rx_valid"]
                or p["o_boundary_rx_ready"]
                or p["o_boundary_tx_valid"]
            ), "Reset/flush handshake"
            return
        routes = self.active.get("routes")
        if routes is None or self.active.get("fault_mode"):
            self.prediction = None
            return
        if self.version != self.active["generation"]:
            assert not any(self.ledger.values()), "Activation lost accepted traffic"
            self.model = MeshModel(self.c.parameters, routes)
            self.version = self.active["generation"]
        ingress = bool(
            p["i_enable"]
            and not p["i_drain"]
            and not p["i_cfg_valid"]
            and not p["i_link_fault_valid"]
            and not p["i_boundary_isolate"]
            and not p["o_error"]
            and not p["o_active_link_fault"]
        )
        before_occupancy = self.model.occupancy()
        self.prediction = self.model.step(p, ingress=ingress)
        for group, count, dw, mw, valid, ready, data, meta in (
            (
                "tile",
                a["N"] * a["RX"],
                a["D"],
                a["M"],
                "o_tile_rx_valid",
                "i_tile_rx_ready",
                "o_tile_rx_data",
                "o_tile_rx_metadata",
            ),
            (
                "boundary",
                a["B"],
                a["D"],
                a["M"],
                "o_boundary_tx_valid",
                "i_boundary_tx_ready",
                "o_boundary_tx_data",
                "o_boundary_tx_metadata",
            ),
        ):
            expected = self.prediction[group]
            assert p[valid] == sum(1 << j for j in expected), (
                "Valid",
                group,
                obs.item.get_name(),
                p[valid],
                expected,
                p["o_error_code"],
            )
            for j, packet in expected.items():
                actual = (
                    p[data] >> (j * dw) & ((1 << dw) - 1),
                    p[meta] >> (j * mw) & ((1 << mw) - 1),
                )
                assert actual == packet, ("Payload", group, j, actual, packet)
                if p[ready] >> j & 1:
                    assert self.ledger[group, j] and self.ledger[group, j].popleft() == packet, (
                        "Duplicate/reordered",
                        group,
                        j,
                        packet,
                    )
                    self.coverage.delivered += 1
        for group, count, valid, ready, data, meta in (
            (
                "tile",
                a["N"] * a["TX"],
                "i_tile_tx_valid",
                "o_tile_tx_ready",
                "i_tile_tx_data",
                "i_tile_tx_metadata",
            ),
            (
                "boundary",
                a["B"],
                "i_boundary_rx_valid",
                "o_boundary_rx_ready",
                "i_boundary_rx_data",
                "i_boundary_rx_metadata",
            ),
        ):
            for j in range(count):
                if p[valid] >> j & 1:
                    expected_ready = j in self.prediction["ready_" + group]
                    assert bool(p[ready] >> j & 1) == expected_ready, (
                        "Ready",
                        group,
                        j,
                        obs.item.get_name(),
                    )
                if p[valid] & p[ready] & (1 << j):
                    packet = (
                        p[data] >> (j * a["D"]) & ((1 << a["D"]) - 1),
                        p[meta] >> (j * a["M"]) & ((1 << a["M"]) - 1),
                    )
                    if group == "tile":
                        resource = j // a["TX"], j % a["TX"]
                    else:
                        edge = self.model.g["edges"][a["IL"] + 2 * j]
                        resource = edge["destination_node"], edge["destination_port"]
                    endpoints = self.model.endpoints(resource)
                    assert endpoints, "Accepted unrouted ingress"
                    for destination in endpoints:
                        self.ledger[destination].append(packet)
                    self.coverage.accepted += 1
                    self.coverage.expected_copies += len(endpoints)
        assert not p["o_error"], (
            "Unexpected runtime error",
            p["o_error_code"],
            obs.item.get_name(),
        )
        if p["o_quiescent"]:
            assert before_occupancy == 0, "False quiescence"

    def check_phase(self):
        assert not any(self.ledger.values()), "Undelivered accepted copies at end of test"
