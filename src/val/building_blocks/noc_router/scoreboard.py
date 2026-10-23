"""Verify port observations against independently routed accepted-flit ledgers."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from noc_router.model import RouterModel
from noc_router.transaction import INPUTS


class RouterScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = RouterModel(self.c)
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.initialized = False
        self.stalled = {}

    def write(self, obs):
        p, item = obs.ports, obs.item
        for name in INPUTS:
            assert p[name] == item.ports[name], f'Coerced stimulus: {name}'
        if obs.stage == 'pre':
            if self.c.ASYNC_RESET and p['i_rstb'] == '0':
                self.model.reset()
                self.initialized = True
            if item.fault and self.c.BUFFER_PROTECTION == 2 and item.fault[-1].bit_count() == 2:
                port, vc, _, _ = item.fault
                self.model.queues[port * self.c.NUM_VCS + vc][0]['fields']['error'] = (
                    1 << self.c.ERROR_WIDTH
                ) - 1
            if self.initialized and p['i_rstb'] == '1' and p['i_flush'] == '0':
                self.model.check_outputs(p)
        if obs.stage == 'post' and item.edge:
            event = self.model.step(item.pre, obs)
            self.initialized = True
            self.model.check_state(p)
            self.coverage.record(event, item, self.model)
            self.stalled.clear()
        self.coverage.observations[obs.stage] += 1

    def check_phase(self):
        assert self.model.pending == 0, 'Undelivered accepted flits at end of test'
        assert self.model.idle, 'Packet ownership did not drain'
        self.coverage.accounting = dict(
            accepted=self.model.accepted,
            forwarded=self.model.forwarded,
            quarantined=self.model.discarded,
            rejected_sink=self.model.sunk,
            reset_or_flush=self.model.canceled,
            pending=self.model.pending,
        )
