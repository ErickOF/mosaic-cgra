"""Check closed-form sequences, handshake histories, storage enables and isolation."""

from pyuvm import ConfigDB, uvm_scoreboard, uvm_analysis_export
from agu.model import AguModel, known
from agu.transaction import Activity, INPUTS, OUTPUTS, STORAGE


class AguScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self,'','config')
        self.active = ConfigDB().get(self,'','active')
        self.coverage = ConfigDB().get(self,'','coverage')
        self.model = AguModel(self.c)
        self.analysis_export = uvm_analysis_export('analysis_export',self)
        self.analysis_export.write = self.write

    def write(self,obs):
        if isinstance(obs,Activity):
            # Adder operands are combinational and may change with live ready.
            assert obs.name in ('add_left','add_right'), f'Between-edge stability assertion failed: {obs.name}'
            return
        p,item,stage = obs.ports,obs.item,obs.stage
        for name in INPUTS:
            assert p[name]==item.ports[name], f'Stimulus was coerced: {name}'
        assert known(p['i_rstb']) and known(p['i_config_valid']) and known(p['i_error_clear']), 'Unknown control protocol'
        if stage=='pre' and self.c.asynchronous and p['i_rstb']=='0':
            self.model.reset()
        if stage=='edge':
            assert item.edge and item.pre is not None
            assert all(p[name]==item.pre.ports[name] for name in OUTPUTS), 'Pre-NBA transfer sampling failed'
        if stage=='post' and item.edge:
            event = self.model.step(item.pre.ports)
            self.coverage.record(event,item.pre.ports,item)
            if self.c.check_internals:
                changed = {name for name in STORAGE if obs.internals[name]!=item.pre.internals[name]}
                allowed = set()
                if event['kind']=='reset': allowed = {'inner_index','outer_index'}
                elif event['kind']=='start': allowed = set(STORAGE)
                elif event['kind']=='accept':
                    allowed = {'address','inner_index'}
                    if self.model.location()[1]==0: allowed |= {'row_base','outer_index'}
                assert changed <= allowed, f'Storage enable assertion failed: {changed-allowed}'
        if self.model.initialized:
            for name,expected in self.model.outputs(p).items():
                assert p[name]==expected, f'AGU assertion failed: {name}: {p[name]} != {expected} ({item.get_name()}, {stage})'
            if self.c.check_internals and stage!='edge':
                final = p['o_last']=='1'
                calculate = p['o_valid']==p['i_ready']==p['i_rstb']=='1' and not final
                if not calculate:
                    for name in ('add_left','add_right'):
                        assert set(obs.internals[name]) <= {'0'}, f'Adder isolation assertion failed: {name}'
        self.coverage.observations[stage] += 1

    def check_phase(self):
        assert self.model.initialized
