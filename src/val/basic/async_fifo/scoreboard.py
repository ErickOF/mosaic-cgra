"""Assert ordering, conservative visibility, pointer legality, and reset epochs."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard

from async_fifo.model import QueueModel
from async_fifo.transaction import Activity, CHAINS


class AsyncFifoScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        self.model = QueueModel()
        self.previous = None
        self.source_pending = None
        self.storage = {}

    def known_controls(self, sample):
        for name in CHAINS:
            if name in sample.chains:
                final = sample.chains[name][-1]
                assert set(final) <= {"0", "1"}, f"Known-control assertion failed: {name}[final]={final}"
        for name in ("i_w_rstb", "i_r_rstb", "i_w_valid", "i_r_ready", "o_w_init_done", "o_r_init_done"):
            sample.integer(name)

    def write(self, observation):
        if isinstance(observation, Activity):
            assert observation.allowed, f"Unclocked-state assertion failed: {observation.signal} changed to {observation.value}"
            self.coverage.transitions[observation.signal] += 1
            return
        before, after, item = observation.before, observation.after, observation.item
        config, model = self.config, self.model
        self.known_controls(before)
        self.known_controls(after)
        for name, value in item.inputs.items():
            expected = str(value) if name != "i_w_data" else value
            assert after.ports[name] == expected, f"Stimulus was coerced: {name}={after.ports[name]}, expected={expected}"
        resets = tuple(after.integer(f"i_{domain}_rstb") for domain in "wr")
        # The driver samples these values before applying either clock change:
        # assertion must take effect even when no local rising edge occurs.
        for domain, released in zip("wr", resets):
            if not released:
                boundary = "full" if domain == "w" else "empty"
                assert before.integer(f"o_{domain}_{boundary}") == 1
                assert before.integer(f"o_{domain}_level") == before.integer(f"o_{domain}_init_done") == 0
                assert before.integer("o_w_ready" if domain == "w" else "o_r_valid") == 0
                if domain == "r":
                    assert set(before.ports["o_r_data"]) == {"0"}, "Reset waited for a read clock edge"
        was_occupancy = len(model.records)
        stalled_output = self.previous is not None and self.previous.integer("o_r_valid") and not self.previous.integer("i_r_ready")
        new_reset = model.reset_event(resets)
        rises = {domain: before.ports[f"i_{domain}_clk"] == "0" and after.ports[f"i_{domain}_clk"] == "1" for domain in "wr"}
        push = rises["w"] and before.integer("i_w_valid") and before.integer("o_w_ready")
        pop = rises["r"] and before.integer("o_r_valid") and before.integer("i_r_ready")
        if new_reset or item.cancellation:
            self.source_pending = None
        if self.source_pending is not None:
            assert before.integer("i_w_valid") and before.ports["i_w_data"] == self.source_pending, "Source stalled-data assertion failed"
        if rises["w"]:
            self.source_pending = before.ports["i_w_data"] if before.integer("i_w_valid") and not push else None
        if push:
            assert before.integer("o_w_init_done") and not before.integer("o_w_full"), "Unsafe push while full/uninitialized"
            self.storage[model.w.count % config.depth] = before.ports["i_w_data"]
        if pop:
            assert before.integer("o_r_init_done") and not before.integer("o_r_empty"), "Unsafe pop while empty/uninitialized"
        if model.epoch and before.integer("o_r_valid"):
            assert model.records and before.ports["o_r_data"] == model.records[0], "Visible-head assertion failed before read edge"
        peer = {"w": (model.r.count, model.r.up), "r": (model.w.count, model.w.up)}
        old_counts = model.w.count, model.r.count
        model.transfer(push, pop, before.ports["i_w_data"], before.ports["o_r_data"])
        assert len(model.records) <= config.depth, "FIFO overflow: accepted more than DEPTH live records"
        for domain, released, transfer in zip("wr", resets, (push, pop)):
            if released and rises[domain]:
                getattr(model, domain).advance(peer[domain], config.stages, transfer, config.depth, write=domain == "w")
        self.check_outputs(before, after, rises, pop)
        if config.check_internals:
            self.check_internals(after, item)
        self.coverage.sample(observation, model, push, pop, rises, old_counts, new_reset, was_occupancy, stalled_output)
        self.previous = after

    def check_outputs(self, before, after, rises, pop):
        model, config = self.model, self.config
        for domain in "wr":
            history = getattr(model, domain)
            initialized = bool(after.integer(f"i_{domain}_rstb") and history.up and history.visible(config.stages)[1])
            assert after.integer(f"o_{domain}_init_done") == initialized, f"Initialization-latency assertion failed in {domain} domain"
            flag = "full" if domain == "w" else "empty"
            assert after.integer(f"o_{domain}_{flag}") == history.boundary, f"Conservative-{flag} assertion failed"
            assert after.integer(f"o_{domain}_level") == history.level, f"Local-level visibility assertion failed in {domain} domain"
            assert after.integer("o_w_ready" if domain == "w" else "o_r_valid") == (initialized and not history.boundary)
            if initialized and model.epoch:
                assert 0 <= history.level <= config.depth, "Initialized occupancy estimate outside [0, DEPTH]"
                occupancy = len(model.records)
                assert history.level >= occupancy if domain == "w" else history.level <= occupancy, "Occupancy conservatism assertion failed"
        assert after.integer("o_w_almost_full") == (after.integer("o_w_init_done") and model.w.level >= config.almost_full)
        assert after.integer("o_r_almost_empty") == (not after.integer("o_r_init_done") or model.r.level <= config.almost_empty)
        if model.epoch and after.integer("o_r_valid"):
            assert model.records and after.ports["o_r_data"] == model.records[0], "Visible-head assertion failed after read edge"
        if not after.integer("i_r_rstb"):
            assert set(after.ports["o_r_data"]) == {"0"}, "Read output did not clear asynchronously"
        elif not (rises["r"] and after.integer("o_r_valid") and (before.integer("o_r_empty") or pop)):
            assert after.ports["o_r_data"] == before.ports["o_r_data"], "Read-register update without a qualified head capture"
        if before.integer("o_r_valid") and not before.integer("i_r_ready") and after.integer("i_r_rstb") and model.epoch:
            assert after.integer("o_r_valid") and after.ports["o_r_data"] == before.ports["o_r_data"], "Read stalled-data assertion failed"

    def check_internals(self, after, item):
        config, model = self.config, self.model
        mask = 2 * config.depth - 1
        for domain in "wr":
            history = getattr(model, domain)
            binary = history.count & mask
            assert int(after.internals[f"{domain}_bin"], 2) == binary, "Pointer advanced without its local handshake"
            gray = binary ^ (binary >> 1)
            assert int(after.internals[f"{domain}_gray"], 2) == gray, "Binary-to-Gray conversion assertion failed"
            assert int(after.internals[f"{domain}_up"], 2) == history.up
            if self.previous and after.integer(f"i_{domain}_rstb"):
                prior = int(self.previous.internals[f"{domain}_gray"], 2)
                assert (prior ^ gray).bit_count() <= 1, "Source Gray transition changed multiple bits"
            for kind in ("gray", "up"):
                name = f"{'r' if domain == 'w' else 'w'}_{kind}_sync"
                for index, value in enumerate(after.chains[name]):
                    if item.fault and item.fault[:2] == (name, index):
                        assert index == 0 and set(value) <= {"x", "z"}, "Positive injection must stay in the first stage"
                        continue
                    count, up = history.visible(index + 1)
                    binary_peer = count & mask
                    expected = binary_peer ^ (binary_peer >> 1) if kind == "gray" else int(up)
                    assert int(value, 2) == expected, f"Synchronizer stage/latency assertion failed: {name}[{index}]"
        for address, expected in self.storage.items():
            assert after.internals[f"memory[{address}]"] == expected, f"Unqualified storage write/reset at address {address}"

    def check_phase(self):
        model = self.model
        assert not model.records, "Accepted records remain undrained at end of test"
        assert model.pushed == model.popped + model.canceled, "Record conservation/cancellation assertion failed"
