"""Compare every public output to independent atomic pre-edge state."""
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from event_barrier.model import EventBarrierModel, number
from event_barrier.transaction import INPUTS, OUTPUTS


class EventBarrierScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = EventBarrierModel(self.c)
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.initialized = False

    def write(self, obs):
        item, stage, p = obs.item, obs.stage, obs.ports
        for name in INPUTS:
            expected = item.ports[name]
            if isinstance(expected, int):
                assert number(p[name]) == expected, f'Driven value changed: {name}'
            else:
                assert p[name].lower() == expected.lower(), f'Four-state stimulus changed: {name}'
        if stage == 'pre':
            if item.fault:
                self.model.fault = True
            if self.c.ASYNC_RESET and number(p['i_rstb']) == 0:
                self.model.reset()
                self.initialized = True
        if stage == 'edge':
            assert item.pre is not None
            assert all(p[name] == item.pre.ports[name] for name in OUTPUTS), 'Pre-NBA sampling'
        if stage == 'post':
            before = list(self.model.counts)
            events = self.model.step(item.pre.ports, item.edge)
            self.initialized |= number(p['i_rstb']) == 0 and item.edge
            self.coverage.record(events, obs, self.model, before)
        if self.initialized:
            expected, _ = self.model.evaluate(p)
            for name, value in expected.items():
                assert number(p[name]) == value, (f'{name}: {p[name]} != {value} '
                                                  f'({item.get_name()}, {stage})')
        self.coverage.observations[stage] += 1

    def check_phase(self):
        assert self.initialized
        assert not any(self.model.counts)
        assert not any(self.model.waits)
        assert not self.model.results and not self.model.releases
        assert not self.model.fatal
