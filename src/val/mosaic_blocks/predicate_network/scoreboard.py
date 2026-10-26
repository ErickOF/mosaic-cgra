"""Reuse the independently checked cycle and end-to-end multicast ledger."""

from types import SimpleNamespace
from static_mesh.scoreboard import MeshScoreboard
from static_mesh.topology import dimensions
from predicate_network.topology import mesh_parameters
from predicate_network.topology import dimensions as predicate_dimensions
from predicate_network.transaction import OUTPUTS


class PredicateScoreboard(MeshScoreboard):
    def build_phase(self):
        super().build_phase()
        self.predicate = self.c
        self.geometry = predicate_dimensions(self.c.parameters)
        p = mesh_parameters(self.c.parameters)
        self.c = SimpleNamespace(parameters=p, aliases=dimensions(p))

    def write(self, obs):
        p, a = obs.ports, self.geometry
        if p["i_reset_n"]:
            for name in OUTPUTS:
                assert p[name] is not None, ("Unknown public output", name, obs.item.get_name())
        super().write(obs)
        if obs.phase != "pre" or not p["i_reset_n"] or p["i_flush"]:
            return
        for prefix, count, ready in (
            ("o_pred_rx", a["N"] * a["RX"], "i_pred_rx_ready"),
            ("o_boundary_pred", a["B"], "i_boundary_pred_ready"),
        ):
            for j in range(count):
                value = p[prefix + "_value"] >> (j * a["PV"]) & ((1 << a["PV"]) - 1)
                mask = p[prefix + "_lane_valid"] >> (j * a["PV"]) & ((1 << a["PV"]) - 1)
                meta = p[prefix + "_metadata"] >> (j * a["M"]) & ((1 << a["M"]) - 1)
                if not p[prefix + "_valid"] >> j & 1:
                    assert not (value or mask or meta), ("Inactive payload", prefix, j)
                    continue
                assert value & ~mask == 0, ("Invalid predicate lane became true", prefix, j)
                if p[ready] is None or not p[ready] >> j & 1:
                    continue
                kind = meta >> (a["CI"] + a["V"] + a["K"] + a["EP"] + a["PR"] + a["T"])
                kind &= (1 << a["CL"]) - 1
                self.coverage.hit(f"class_{kind}")
                self.coverage.hit(
                    "false_valid" if mask and not value else "invalid" if not mask else "true"
                )
                for lane in range(a["PV"]):
                    self.coverage.hit(
                        f"lane_{lane}_value_{value >> lane & 1}_valid_{mask >> lane & 1}"
                    )
                if prefix == "o_boundary_pred" and self.predicate.parameters["ENABLE_LINK_PARITY"]:
                    assert (
                        p["o_boundary_pred_parity"] >> j & 1
                        == (value.bit_count() + mask.bit_count() + meta.bit_count()) % 2
                    )
