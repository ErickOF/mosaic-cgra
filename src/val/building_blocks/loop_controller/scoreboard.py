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
        if obs.internals:
            self.check_selection(obs, expected)
        self.samples += 1
        if obs.stage == 'edge':
            self.coverage.record(obs, self.model, expected)
            self.model.step(p)

    def check_selection(self, obs, expected):
        """Check common-block selection against the independent current point.

        Token comparison still uses the Cartesian-product model. These extra
        observations check that inactive or higher levels receive no update,
        even when their unchanged storage would hide an unnecessary write.
        """
        m = self.model
        command = number(obs.ports['i_control_command'])
        valid = number(obs.ports['i_control_valid']) == 1
        decoded = 1 << command if valid and command in (0, 1, 2) else 0
        assert number(obs.internals['control_decoded']) == decoded, (
            'Loop control opcode did not decode or fail closed correctly'
        )
        writes = 0
        if expected['o_iteration_valid']:
            candidates = [
                level for level, ordinal in enumerate(reversed(m.point))
                if ordinal + 1 < m.config['trip_count'][level]
            ]
            selected = min(candidates) if candidates else None
            assert number(obs.internals['advance_valid']) == int(selected is not None)
            assert number(obs.internals['advance_onehot']) == (
                0 if selected is None else 1 << selected
            ), 'Loop carry selection must choose the innermost nonfinal level'
            if selected is not None:
                assert number(obs.internals['advance_level']) == selected
                if number(obs.ports['i_iteration_ready']) == 1:
                    writes = (1 << (selected + 1)) - 1
                    if obs.stage == 'edge':
                        self.coverage.advance_levels.add((m.config['depth'], selected))
        assert number(obs.internals['level_write']) == writes, (
            'Loop level update mask changed without an authorized advancement'
        )
        if obs.stage == 'edge':
            self.coverage.selection_checks += 1
            self.coverage.level_holds += writes == 0
            if valid:
                if command is None:
                    self.coverage.unknown_control_decodes += 1
                else:
                    self.coverage.control_opcodes.add(command)

    def check_phase(self):
        assert self.samples > 1000
        assert self.model.state == 'idle' and not self.model.fatal
