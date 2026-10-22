"""Check every public output, atomic elastic history and arithmetic-bank holds."""
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from exp_unit.model import ExpUnitModel, image, number, predict
from exp_unit.transaction import INPUTS, OUTPUTS


class ExpUnitScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = ExpUnitModel(self.c)
        self.initialized = False
        self.previous_values = {}
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write

    def storage(self, obs, incoming, plan):
        c = self.c
        for s, raw in obs.storage.items():
            token = incoming[s - 1] if s else predict(c, plan['p']) if plan['accept'] else None
            capture = obs.item.edge and plan['run'] and not plan['flush'] and plan['ready'][s] and token and token[1]['active']
            if not capture or number(obs.item.pre.ports['i_rstb']) != 1:
                assert raw == obs.item.pre.storage[s], f'Inactive arithmetic storage changed: stage {s}'
            else:
                r, f = token
                rw, ew, iw = c.RANGE_WIDTH, c.RANGE_WIDTH - c.RANGE_FRACTION_WIDTH, c.INTERNAL_WIDTH
                if s < 2:
                    width, value = rw, f['z'] % (1 << rw)
                elif s == 2:
                    rem = c.RANGE_FRACTION_WIDTH - c.TABLE_ADDRESS_WIDTH
                    table = image(c.TABLE_ADDRESS_WIDTH, c.INTERNAL_FRACTION_WIDTH)
                    width = ew + rem + 2 * iw
                    value = (((f['k'] % (1 << ew)) << rem) | f['remainder']) << (2 * iw)
                    value |= table[f['address']] << iw
                    value |= table[f['address'] + 1] if f['interpolation'] else 0
                elif s == 3:
                    width, value = ew + iw, ((f['k'] % (1 << ew)) << iw) | f['mantissa']
                else:
                    width = ew + c.OUTPUT_WIDTH + 3
                    value = ((f['k'] % (1 << ew)) << (c.OUTPUT_WIDTH + 3)) | r['o_result_data'] << 3
                    value |= r['o_result_overflow'] << 2 | r['o_result_underflow'] << 1 | r['o_result_saturated']
                if c.TABLE_PROTECTION:
                    value |= (value.bit_count() % 2) << width
                assert number(raw) == value, f'Arithmetic capture mismatch: stage {s}'
            self.coverage.storage_checks += 1

    def write(self, obs):
        item, p, stage = obs.item, obs.ports, obs.stage
        for name in INPUTS:
            expected = item.ports[name]
            assert number(p[name]) == expected if isinstance(expected, int) else p[name].lower() == expected.lower(), f'Stimulus changed: {name}'
        if stage == 'pre':
            if item.release:
                self.model.fault = None
            if item.fault:
                self.model.fault = item.fault
            if self.c.ASYNC_RESET and number(p['i_rstb']) == 0:
                self.model.reset()
                self.initialized = True
        if stage == 'edge':
            assert all(p[n] == item.pre.ports[n] for n in OUTPUTS), 'Pre-NBA sampling'
        if stage == 'post':
            old = list(self.model.pipeline)
            _, plan = self.model.evaluate(item.pre.ports)
            if item.edge and plan['pop']:
                _, fact = self.model.queue[0]
                if fact['active']:
                    key = (fact['base'], fact['interpolation'], fact['mode'], fact['signed'])
                    value = number(item.pre.ports['o_result_data'])
                    previous = self.previous_values.get(key)
                    if previous and fact['x'] >= previous[0]:
                        assert value >= previous[1], 'Output is not nondecreasing'
                    self.previous_values[key] = fact['x'], value
            events = self.model.step(item.pre.ports, item.edge)
            if item.edge and number(p['i_rstb']) == 0:
                self.initialized = True
            if self.c.check_internals:
                self.storage(obs, old, plan)
            self.coverage.record(events, obs, self.model, plan)
        if self.initialized:
            expected, _ = self.model.evaluate(p)
            for name, value in expected.items():
                assert number(p[name]) == value, f'{name}: {p[name]} != {value} ({item.get_name()}, {stage})'
        self.coverage.observations[stage] += 1

    def check_phase(self):
        assert self.initialized and self.model.occupancy == 0
        assert self.model.accepted == self.model.delivered + self.model.discarded
