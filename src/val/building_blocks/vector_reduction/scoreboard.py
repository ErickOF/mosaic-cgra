"""Check public responses, transaction conservation, FU isolation and DFF behavior."""

from multiplier.transaction import Activity as ClockActivity
from pyuvm import ConfigDB, uvm_analysis_export
from vector_lane.scoreboard import LaneScoreboard

from vector_reduction.model import ReductionModel, known, predict
from vector_reduction.transaction import INPUTS, OUTPUTS


class ReductionScoreboard(LaneScoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.model = ReductionModel(self.c)
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write

    def isolation(self, obs):
        c, p, values = self.c, obs.ports, obs.internals
        enabled = not c.latency or p["i_rstb"] == p["i_clock_enable"] == "1"
        event = predict(c, p)[1] if enabled else {"kind": "inactive"}
        selected = event.get("opcode") if event["kind"] == "legal" else None
        for op in c.enabled_opcodes:
            assert values[f"active:{op}"] == str(int(op == selected)), "Selected tree enable"
            for k in range(c.count):
                active = op == selected and p["i_element_mask"][-1 - k] == "1"
                word = p["i_data"][-(k + 1) * c.element : len(p["i_data"]) - k * c.element]
                identity = c.mask if op == 3 else 0
                expected = word if active else f"{identity:0{c.element}b}"
                assert values[f"leaf:{op}:{k}"] == expected, "Tree operand isolation"
        self.coverage.isolation_checks += 1

    def storage(self, obs):
        super().storage(obs)
        for k in range(self.c.latency):
            self.coverage.valid_states.add((k, obs.internals[f"control:{k}:valid"]))

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
            assert known(p["i_rstb"]), "VECTOR_REDUCTION_PROTOCOL: i_rstb"
            if p["i_rstb"] == "1":
                assert known(p["i_clock_enable"]), "VECTOR_REDUCTION_PROTOCOL: i_clock_enable"
                if p["i_clock_enable"] == "1":
                    assert known(p["i_valid"]), "VECTOR_REDUCTION_PROTOCOL: i_valid"
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
                    f"Vector reduction {name}: {p[name]} != {expected[name]}"
                    f" ({item.get_name()}, {stage})"
                )
            if c.check_internals and stage != "edge":
                self.isolation(obs)
        self.coverage.observations[stage] += 1
