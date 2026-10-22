"""Compare every public output at setup, actual edge, settled and held samples."""
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from loop_controller.model import LoopModel, number


class LoopControllerScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.config = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = LoopModel(self.config)
        self.samples = 0

    def write(self, obs):
        p = obs.ports
        if obs.stage == 'pre':
            if obs.item.fault:
                self.model.fault = (15 if obs.item.fault == 'invariant' and
                                    not self.config.PROTECT_STATE else 14)
            if self.config.ASYNC_RESET and number(p['i_rstb']) == 0:
                self.coverage.reset_states.add(self.model.state)
                self.model.reset()
        expected = self.model.outputs(p)
        for name, value in expected.items():
            actual = number(p[name])
            assert actual == value, (f'{obs.item.get_name()} {obs.stage}: {name}: '
                                     f'expected {value}, got {p[name]}, state={self.model.state}')
        self.samples += 1
        if obs.stage == 'edge':
            self.coverage.record(obs, self.model, expected)
            self.model.step(p)

    def check_phase(self):
        assert self.samples > 1000
        assert self.model.state == 'idle' and not self.model.fatal
