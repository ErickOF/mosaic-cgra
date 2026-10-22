"""Check all public outputs and exact request/response ownership accounting."""
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from lut_unit.model import LutModel, number


class LutUnitScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.config = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = LutModel(self.config)
        self.samples = 0

    def write(self, obs):
        m, p = self.model, obs.ports
        if obs.stage == 'pre':
            if self.config.ASYNC_RESET and number(p['i_rstb']) == 0:
                m.reset()
            if obs.item.fault:
                m.fault(obs.item.fault)
        expected = m.outputs(p)
        for name, value in expected.items():
            actual = number(p[name])
            assert actual == value, (f'{obs.item.get_name()} {obs.stage}: {name}: '
                f'expected {value}, got {p[name]}, tick={m.tick}, '
                f'pipe={len(m.pipe)}, results={len(m.results)}, programs={len(m.programs)}')
        self.samples += 1
        if obs.stage == 'pre' and self.config.check_internals:
            a = m.plan(p)
            for bank, raw in obs.storage.items():
                reads = 0
                if a['lookup'] and a['lookup'][3] and a['lookup'][0]['bank'] == bank:
                    reads = 1 | (a['lookup'][0]['interpolated'] << 1)
                if a['program'] and a['program'][0]['command'] == 1 and a['program'][0]['bank'] == bank:
                    reads |= 1
                assert number(raw) == reads, f'Unexpected bank {bank} read activity'
        if obs.stage == 'edge':
            plan = m.plan(p)
            self.coverage.record(obs, m, plan)
            m.step(p)
            self.coverage.accounting = dict(m.accounting)
            assert m.accounting['lookups'] == m.accounting['results'] + m.accounting['discarded'] + len(m.pipe) + len(m.results)
            assert m.accounting['programs'] == m.accounting['responses'] + m.accounting['program_discarded'] + len(m.programs)

    def check_phase(self):
        assert self.samples > 1000
        assert not self.model.pipe and not self.model.results and not self.model.programs
        assert not self.model.fatal
