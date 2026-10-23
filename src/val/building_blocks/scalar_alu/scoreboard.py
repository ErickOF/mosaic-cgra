"""Check every result/status bit against independently computed integer results."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from scalar_alu.model import predict
from scalar_alu.transaction import INPUTS, OUTPUTS


class AluScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.checked = 0

    def write(self, obs):
        c, p = self.c, obs.ports
        for name in INPUTS:
            assert p[name] == obs.item.ports[name], f'Coerced stimulus: {name}'
        expected, event = predict(c, p)
        actual = {name: p[name] for name in OUTPUTS}
        assert actual == expected, (
            f'{obs.item.get_name()}/{obs.stage}: inputs={p}, actual={actual}, expected={expected}'
        )
        if c.check_internals:
            legal = event['kind'] == 'legal'
            op = event.get('opcode')
            need_a = legal and op != 17 and (op != 15 or p['i_predicate'] == '1')
            need_b = legal and op not in (5, 16) and (op != 15 or p['i_predicate'] == '0')
            a = p['i_operand_a'] if need_a else '0' * c.width
            b = p['i_operand_b'] if need_b else '0' * c.width
            assert obs.internals['isolated_a'] == a
            assert obs.internals['isolated_b'] == b
            assert obs.internals['math_a'] == (a if legal and op in (0, 1) else '0' * c.width)
            assert obs.internals['math_b'] == (b if legal and op in (0, 1) else '0' * c.width)
        self.checked += 1
        self.coverage.record(obs, event)

    def check_phase(self):
        assert self.checked > 0, 'No actual ALU observations'
