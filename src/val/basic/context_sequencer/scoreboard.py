"""Assert state history, qualification, loop visits, events, and real waveforms."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import bits
from context_sequencer.constants import INPUTS, OUTPUTS
from context_sequencer.model import SequencerModel
from context_sequencer.transaction import Activity


class SequencerScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.coverage = ConfigDB().get(self, "", "coverage")
        self.analysis_export = uvm_analysis_export("analysis_export", self)
        self.analysis_export.write = self.write
        self.model = SequencerModel(self.config)
        self.reported = set()

    def write(self, observation):
        if isinstance(observation, Activity):
            assert not observation.quiet, f"Quiet-waveform assertion failed: {observation.signal}"
            self.coverage.waveforms[observation.signal] += 1
            return
        config, ports, item = self.config, observation.ports, observation.item
        for name in INPUTS:
            if name != "i_clk" or observation.stage != "pre":
                assert ports[name] == item.ports[name], f"Stimulus was coerced: {name}"
        if observation.stage == "pre" and ports["i_clk"] == "0" and item.ports["i_clk"] == "1":
            fault = self.model.fault(ports)
            reason = fault[1] if fault else None
            assert reason == item.violation, f"Protocol assertion failed: {reason or 'missing expected violation'}"
            if reason:
                self.coverage.assertions[reason] += 1
                if reason not in self.reported:
                    self.logger.info("Expected protocol assertion: %s", reason)
                    self.reported.add(reason)
        before = dict(state=self.model.state, active=self.model.active, owner=self.model.owner,
                      remaining=self.model.remaining, total_visits=self.model.total_visits, error=self.model.error,
                      reads=self.model.reads(ports))
        reset = ports["i_rstb"] == "0" and (config.async_reset or self.model.clock == "0" and ports["i_clk"] == "1")
        rising = self.model.step(ports)
        expected = self.model.outputs(ports)
        for name in OUTPUTS:
            wanted = bits(int(expected[name]), config.widths[name])
            assert ports[name] == wanted, f"Sequencer assertion failed: {item.get_name()}/{observation.stage}: {name}={ports[name]}, expected={wanted}"
        if config.check_internals:
            expected_internals = dict(state=(int(self.model.state), 4), pending_context=(self.model.pending, config.address_width),
                                      pending_scheduled=(int(self.model.pending_scheduled), 1))
            for name, (value, width) in expected_internals.items():
                assert observation.internals[name] == bits(value, width), f"State-storage assertion failed: {name}"
        self.coverage.sample(observation, before, self.model, rising, reset)
