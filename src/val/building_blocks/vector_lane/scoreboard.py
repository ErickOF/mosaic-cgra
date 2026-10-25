"""Check public responses, transaction conservation, FU isolation and DFF behavior."""

from multiplier.transaction import Activity as ClockActivity
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard

from vector_lane.model import LaneModel, known, predict
from vector_lane.transaction import INPUTS, OUTPUTS


class LaneScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.model = LaneModel(self.c)
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write

    def isolation(self, obs):
        c, p, values = self.c, obs.ports, obs.internals
        enabled = not c.latency or p["i_rstb"] == p["i_clock_enable"] == "1"
        event = predict(c, p)[1] if enabled else {"kind": "inactive"}
        selected = event.get("family") if event["kind"] == "legal" else None
        for family in ("alu", "mul", "mac"):
            active = family == selected
            assert values[family + "_request"] == str(int(active)), "FU request decode"
            if family != "alu" and not getattr(c, family):
                continue
            for operand in ("a", "b"):
                expected = p["i_operand_" + operand] if active else "0" * c.element
                assert values[family + "_" + operand] == expected, "Inactive FU operand toggled"
        expected = p["i_accumulator"] if selected == "mac" else "0" * c.accumulator
        if c.mac:
            assert values["mac_accumulator"] == expected, "MAC accumulator isolation"
        self.coverage.isolation_checks += 1

    def storage(self, obs):
        before, after = obs.item.pre.internals, obs.internals
        for name, resettable in self.active["banks"].items():
            rst = before[name + ":i_rstb"]
            if rst == "0" and (obs.item.edge or self.c.asynchronous and resettable):
                expected = "0" * len(after[name])
            elif obs.item.edge and before[name + ":i_enable"] == "1":
                expected = before[name + ":i_d"]
            else:
                expected = before[name]
            assert after[name] == expected, f"DFF capture/hold/reset: {name}"
            self.coverage.storage_checks += 1
            if before[name + ":i_enable"] == "0":
                self.coverage.frozen_banks.add(name)
            self.coverage.banks.add(name)

    def write(self, obs):
        if self.c.probe:
            return  # Negative runs must be rejected by the native checker itself.
        if isinstance(obs, ClockActivity):
            assert not self.model.initialized, f"Between-edge DFF change: {obs.name}"
            return
        c, p, item, stage = self.c, obs.ports, obs.item, obs.stage
        for name in INPUTS:
            assert p[name] == item.ports[name], f"Stimulus coerced: {name}"
        if c.latency:
            assert known(p["i_rstb"]), "VECTOR_LANE_PROTOCOL: i_rstb"
            if p["i_rstb"] == "1":
                assert known(p["i_clock_enable"]), "VECTOR_LANE_PROTOCOL: i_clock_enable"
                if p["i_clock_enable"] == "1":
                    assert known(p["i_valid"]), "VECTOR_LANE_PROTOCOL: i_valid"
        if stage == "pre" and c.latency and c.asynchronous and p["i_rstb"] == "0":
            item.reset_occupancy = self.model.occupancy
            self.model.reset()
        if stage == "edge" and c.latency:
            assert all(p[name] == item.pre.ports[name] for name in OUTPUTS), "Pre-NBA sampling"
        if stage == "post":
            event = self.model.step(item.pre.ports, item.edge)
            if hasattr(item, "reset_occupancy"):
                event = {"kind": "reset", "occupancy": item.reset_occupancy}
            self.coverage.record(event, item)
            self.coverage.accounting = {
                "accepted": self.model.accepted,
                "emitted": self.model.emitted,
                "reset_discarded": self.model.discarded,
            }
            if c.check_internals and c.latency:
                self.storage(obs)
        if self.model.initialized:
            expected = self.model.output(p)
            for name in OUTPUTS:
                assert p[name] == expected[name], (
                    f"Vector lane {name}: {p[name]} != {expected[name]}"
                    f" ({item.get_name()}, {stage})"
                )
            if c.check_internals and stage != "edge":
                self.isolation(obs)
        self.coverage.observations[stage] += 1

    def check_phase(self):
        assert self.model.initialized and not self.model.pending
        assert self.model.visible["o_valid"] == "0"
        assert self.model.accepted == self.model.emitted + self.model.discarded
        self.coverage.accounting = {
            "accepted": self.model.accepted,
            "emitted": self.model.emitted,
            "reset_discarded": self.model.discarded,
        }
