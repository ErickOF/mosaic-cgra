"""Compare every public output against an independent transaction model."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_component
from tile_network_interface.model import InterfaceModel, num
from tile_network_interface.transaction import OUTPUTS


class InterfaceScoreboard(uvm_component):
    def build_phase(self):
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.model = InterfaceModel(ConfigDB().get(self, '', 'config'))
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.initialized = False
        self.samples = 0

    def write(self, observation):
        m, p, stage = self.model, observation.ports, observation.stage
        if stage == 'pre':
            m.step(p, False)
        if not self.initialized:
            if stage == 'edge' and num(p['i_rstb']) == 0:
                m.step(p, True)
                self.initialized = True
            elif stage == 'pre' and num(p['i_rstb']) == 0 and m.c.ASYNC_RESET:
                self.initialized = True
            return
        expected, q = m.evaluate(p)
        for name in OUTPUTS:
            assert p[name] == expected[name], (
                f'{observation.item.get_name()} {stage} '
                f'{name}: got {p[name]}, expected {expected[name]}'
            )
        self.samples += 1
        if stage == 'edge':
            self.coverage.sample(observation, q, m)
            m.step(p, True)
        if stage == 'held':
            self.coverage.model = m

    def check_phase(self):
        m = self.model
        assert self.samples > 1000
        assert not any(m.tx) and not any(m.rx) and not any(m.vc_queues)
        assert not any(m.partial) and not any(m.completed) and m.owner is None
        assert m.accepted_tx == m.sent_tx + m.discarded_tx
        assert m.accepted_rx == m.delivered_rx + m.discarded_rx
        assert m.accepted_tx * m.c.fragments == m.tx_flits + m.canceled_tx_flits
        assert m.rx_flits == m.popped_rx_flits + m.canceled_rx_flits
