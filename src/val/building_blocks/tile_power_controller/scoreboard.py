"""Check all public outputs, internal timers and physical safety invariants."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_component
from tile_power_controller.model import PowerModel, number
from tile_power_controller.transaction import OUTPUTS, STATES as P


class PowerScoreboard(uvm_component):
    def build_phase(self):
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.model = PowerModel(ConfigDB().get(self, '', 'config'))
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.initialized = False
        self.samples = 0

    def write(self, o):
        m, p = self.model, o.ports
        if o.stage == 'pre':
            m.settle(p)
        if not self.initialized:
            if o.stage == 'edge':
                m.step(p)
                self.initialized = True
            return
        expected, q = m.evaluate(p)
        for n in OUTPUTS:
            assert p[n] == expected[n], (
                f'{o.item.get_name()} {o.stage} {n}: got {p[n]}, expected {expected[n]}'
            )
        for n, value in o.storage.items():
            assert number(value) == m.timers[n], (
                f'{o.item.get_name()} {o.stage} {n} timer: got {value}, expected {m.timers[n]}'
            )
        assert not int(p['o_tile_clock_enable'], 2) or int(p['o_power_good_sync'], 2)
        assert int(p['o_tile_clock_enable'], 2) or int(p['o_clock_group_enable'], 2) == 0
        if int(p['o_tile_accept_enable'], 2):
            assert m.state in (P['ACTIVE'], P['STALLED'])
            assert not int(p['o_isolation_enable'], 2) and not int(p['o_write_disable'], 2)
            assert int(p['o_policy_valid'], 2) and not int(p['o_tile_reset_request'], 2)
        if not int(p['o_power_switch_enable'], 2):
            assert int(p['o_isolation_enable'], 2) and not int(p['o_tile_clock_enable'], 2)
        if int(p['o_retention_save'], 2) or int(p['o_retention_restore'], 2):
            assert int(p['o_tile_clock_enable'], 2) and int(p['o_write_disable'], 2)
        self.samples += 1
        if o.stage == 'edge':
            self.coverage.sample(o, q, m)
            m.step(p)
        self.coverage.model = m

    def check_phase(self):
        assert self.samples > 1000
        assert self.model.state == P['ACTIVE'] and not self.model.command_pending
        assert self.model.error == self.model.fatal == 0
