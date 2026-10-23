"""Check public responses, atomic bank changes, isolation and actual DFF pins."""

from multiplier.transaction import Activity
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard

from predicate_unit.model import PredicateModel, number
from predicate_unit.transaction import INPUTS, OUTPUTS


class PredicateScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.model = PredicateModel(self.c)
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write

    def storage(self, obs):
        before, after = obs.item.pre.internals, obs.internals
        for name, resettable in self.active["banks"].items():
            reset = before[name + ":i_rstb"] == "0"
            if reset and (obs.item.edge or self.c.asynchronous and resettable):
                expected = "0" * len(after[name])
            elif obs.item.edge and before[name + ":i_enable"] == "1":
                expected = before[name + ":i_d"]
            else:
                expected = before[name]
            assert after[name] == expected, f"DFF capture/hold/reset: {name}"
            self.coverage.storage_checks += 1

    def state(self, obs):
        for entry in range(self.c.depth):
            for lane in range(self.c.lanes):
                assert number(obs.internals[f"control:valid:{entry}:{lane}"]) == int(
                    self.model.valid[entry][lane]
                ), "Predicate validity diverged"
                expected = self.model.data[entry][lane]
                if expected is not None:
                    assert (
                        number(obs.internals[f"storage:data:{entry}:{lane}"])
                        == expected
                    ), "Predicate data changed without a legal write"
        self.coverage.state_checks += 1

    def isolation(self, obs):
        p, c = obs.ports, self.c
        controls = all(
            number(p[name]) is not None
            for name in ("i_opcode", "i_lane_mask", "i_write_enable")
        )
        active = p["i_rstb"] == p["i_clock_enable"] == p["i_valid"] == "1" and controls
        op = number(p["i_opcode"])
        mask = number(p["i_lane_mask"])
        for port, pin in enumerate(("i_source_a_addr", "i_source_b_addr")):
            needed = op is not None and (3 if port == 0 else 5) <= op <= 7
            address = number(p[pin])
            read = bool(
                active and needed and mask and address is not None and address < c.depth
            )
            assert number(obs.internals[f"decode:{port}"]) == (
                1 << address if read else 0
            )
            if not read:
                assert number(obs.internals[f"read:{port}"]) == 0, (
                    "Unused read data toggled"
                )
                assert number(obs.internals[f"read_valid:{port}"]) == 0
            else:
                for k in range(c.lanes):
                    if not mask & (1 << k):
                        assert obs.internals[f"read:{port}"][-1 - k] == "0", (
                            "Masked read"
                        )
        dest = number(p["i_destination_addr"])
        decode = (
            1 << dest
            if active
            and op <= 8
            and p["i_write_enable"] == "1"
            and mask
            and dest is not None
            and dest < c.depth
            else 0
        )
        assert number(obs.internals["destination"]) == decode, (
            "Destination decode gating"
        )
        self.coverage.isolation_checks += 1

    def write(self, obs):
        if self.c.probe:
            return  # Negative tests must be rejected by the native checker itself.
        if isinstance(obs, Activity):
            assert not self.model.initialized, f"Between-edge state change: {obs.name}"
            return
        p, item, stage = obs.ports, obs.item, obs.stage
        for name in INPUTS:
            assert p[name] == item.ports[name], f"Stimulus coerced: {name}"
        if stage == "pre" and self.c.asynchronous and p["i_rstb"] == "0":
            item.reset_population = sum(sum(row) for row in self.model.valid)
            self.model.reset()
        if stage == "edge":
            assert all(p[name] == item.pre.ports[name] for name in OUTPUTS), (
                "Pre-NBA response"
            )
        if stage == "post":
            event = self.model.step(item.pre.ports, item.edge)
            if hasattr(item, "reset_population"):
                event = {
                    "kind": "reset",
                    "population": item.reset_population,
                    "updates": [],
                }
            self.coverage.record(event, item, p)
            if self.c.check_internals:
                self.storage(obs)
        if self.model.initialized:
            for name, value in self.model.visible.items():
                assert number(p[name]) == value, (
                    f"{name}: {p[name]} != {value} ({item.get_name()}, {stage})"
                )
            if self.c.check_internals and stage != "edge":
                self.state(obs)
                self.isolation(obs)
        self.coverage.observations[stage] += 1

    def check_phase(self):
        assert self.model.initialized and not self.model.visible["o_valid"]
        self.coverage.accepted = self.model.accepted
