"""Check every public output, atomic elastic history and arithmetic-bank holds."""
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from exp_unit.model import ExpUnitModel, image, log2e, number, predict
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

    def arithmetic(self, obs, plan):
        """Check reusable arithmetic and isolation at the actual pre-edge boundary.

        Public results and register captures are checked separately. These checks
        also catch wrong sign extension or operand widths hidden by saturation.
        """
        c, p, a = self.c, plan['p'], {n: number(v) for n, v in obs.arithmetic.items()}
        legal = all(p[n] is not None for n in INPUTS if n.startswith('i_request_'))
        legal = legal and (c.SUPPORT_EXP2 if p['i_request_base'] else c.SUPPORT_EXP_E)
        legal = legal and (not p['i_request_interpolate'] or c.SUPPORT_INTERPOLATION)
        active = bool(plan['permit'] and p['i_request_valid'] == 1 and legal and
                      p['i_request_predicate'])
        enabled = active and p['i_request_base'] == 0
        x = p['i_request_operand'] or 0
        if x & (1 << (c.INPUT_WIDTH - 1)):
            x -= 1 << c.INPUT_WIDTH
        product_width = c.INPUT_WIDTH + c.LOG2E_FRACTION_WIDTH + 2
        expected = x * log2e(c.LOG2E_FRACTION_WIDTH) if enabled else 0
        assert a['product_e'] == expected % (1 << product_width), 'Full signed base-e product'
        if c.SUPPORT_EXP_E:
            width = max(c.INPUT_WIDTH, c.LOG2E_FRACTION_WIDTH + 2)
            assert a['base_e_enable'] == enabled
            assert a['base_e_a'] == (x % (1 << width) if enabled else 0)
            assert a['base_e_b'] == (log2e(c.LOG2E_FRACTION_WIDTH) if enabled else 0)
        if c.SUPPORT_INTERPOLATION:
            token = self.model.pipeline[2]
            fact = token[1] if token else {}
            enabled = bool(plan['permit'] and fact.get('active') and fact['interpolation'])
            table = image(c.TABLE_ADDRESS_WIDTH, c.INTERNAL_FRACTION_WIDTH)
            lower = table[fact['address']] if enabled else 0
            delta = table[fact['address'] + 1] - lower if enabled else 0
            remainder = fact['remainder'] if enabled else 0
            assert a['interpolation_enable'] == enabled
            assert a['interpolation_a'] == delta, 'Unsigned interpolation difference'
            assert a['interpolation_b'] == remainder, 'Unsigned interpolation remainder'
            assert a['interpolation_product'] == delta * remainder, 'Full interpolation product'
            if enabled:
                assert a['interpolation_sum'] == fact['mantissa'], 'Rounded interpolation sum'
                assert lower <= a['mantissa'] <= table[fact['address'] + 1]
        token = self.model.pipeline[1]
        if plan['permit'] and token and token[1]['active']:
            fact = token[1]
            coordinate = a['z2']
            if coordinate & (1 << (c.RANGE_WIDTH - 1)):
                coordinate -= 1 << c.RANGE_WIDTH
            assert coordinate == fact['z']
            k, fraction = divmod(coordinate, 1 << c.RANGE_FRACTION_WIDTH)
            assert k == fact['k'] and 0 <= fraction < 1 << c.RANGE_FRACTION_WIDTH
        self.coverage.arithmetic_checks += 1

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
            if self.initialized and self.c.check_internals and not self.model.fault:
                _, plan = self.model.evaluate(p)
                self.arithmetic(obs, plan)
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
