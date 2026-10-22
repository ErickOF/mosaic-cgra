"""Check complete public behavior, source contracts and unreset payload writes."""
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.logic import bits
from local_switch.model import LocalSwitchModel, lane
from local_switch.transaction import CONFIG, INPUTS, OUTPUTS


class LocalSwitchScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = LocalSwitchModel(self.c)
        self.initialized = False
        self.held_inputs = {}
        self.held_config = None
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write

    def check_producers(self, p):
        if p['i_rstb'] == '0' or p['i_flush'] == '1':
            self.held_inputs.clear()
            self.held_config = None
            return
        for i, previous in self.held_inputs.items():
            assert p['i_input_valid'][-i - 1] == '1', 'Producer withdrew stalled input'
            assert previous == (lane(p['i_input_data'], i, self.c.DATA_WIDTH),
                lane(p['i_input_metadata'], i, self.c.METADATA_WIDTH)), 'Producer changed stalled payload'
        if self.held_config:
            assert p['i_config_valid'] == '1' and self.held_config == tuple(p[n] for n in CONFIG), 'Producer changed stalled configuration'

    def storage(self, obs, plan):
        c = self.c
        valid, masks = self.model.raw_state()
        for i in range(c.NUM_INPUTS):
            if self.initialized:
                assert obs.storage[f'v{i}'] == valid[i], 'Stored buffer ownership differs'
                assert obs.storage[f'p{i}'] == masks[i], 'Stored pending copies differ'
            raw = obs.storage[f'd{i}']
            if obs.item.edge and plan['accept'][i] and plan['run']:
                expected = lane(obs.item.pre.ports['i_input_data'], i, c.DATA_WIDTH)
                expected += lane(obs.item.pre.ports['i_input_metadata'], i, c.METADATA_WIDTH)
                assert raw == expected, 'Input payload capture mismatch'
            else:
                assert raw == obs.item.pre.storage[f'd{i}'], 'Unqualified payload write'
            self.coverage.storage_checks += 1

    def write(self, obs):
        c, model = self.c, self.model
        p, item, stage = obs.ports, obs.item, obs.stage
        for name in INPUTS:
            assert p[name] == bits(item.ports[name], c.widths[name]), f'Stimulus was coerced: {name}'
        if stage == 'pre':
            if item.fault:
                assert not model.fault, 'Fault injections must be separated by flush or reset'
                model.fault = item.fault
            if p['i_rstb'] == '0':
                self.coverage.reset_occupancies.add(sum(bool(model.pending(i)) for i in range(c.NUM_INPUTS)))
            if c.ASYNC_RESET and p['i_rstb'] == '0':
                model.reset()
                self.initialized = True
            self.check_producers(p)
        if stage == 'edge':
            assert all(p[n] == item.pre.ports[n] for n in OUTPUTS), 'Not a pre-NBA observation'
        if stage == 'post':
            events, plan = model.step(item.pre.ports, item.edge)
            if item.edge and p['i_rstb'] == '0':
                self.initialized = True
            if item.edge:
                pre = item.pre.ports
                if pre['i_rstb'] == '0' or pre['i_flush'] == '1':
                    self.held_inputs.clear()
                    self.held_config = None
                else:
                    self.held_inputs = {i: (lane(pre['i_input_data'], i, c.DATA_WIDTH),
                        lane(pre['i_input_metadata'], i, c.METADATA_WIDTH)) for i in range(c.NUM_INPUTS)
                        if pre['i_input_valid'][-i - 1] == '1' and pre['o_input_ready'][-i - 1] == '0'}
                    self.held_config = tuple(pre[n] for n in CONFIG) if (
                        pre['i_config_valid'] == '1' and pre['o_config_ready'] == '0') else None
            if c.check_internals:
                self.storage(obs, plan)
            self.coverage.record(events, obs, model, plan)
        if self.initialized:
            expected, _ = model.evaluate(p)
            for name, value in expected.items():
                assert p[name] == value, f'{name}: {p[name]} != {value} ({item.get_name()}, {stage})'
        self.coverage.observations[stage] += 1

    def check_phase(self):
        self.model.conservation()
        assert not any(self.model.queues) and not self.held_inputs and self.held_config is None
