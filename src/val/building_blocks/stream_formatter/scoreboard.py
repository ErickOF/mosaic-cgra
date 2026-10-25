"""Compare every interface field, retained storage and qualified fault events."""
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from stream_formatter.model import StreamFormatterModel, number
from stream_formatter.transaction import INPUTS, OUTPUTS, PAYLOAD, RESULT


class StreamFormatterScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = StreamFormatterModel(self.c)
        self.initialized = False
        self.previous = None
        self.previous_pre = None
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write

    def storage(self, obs):
        old = obs.item.pre.storage if obs.stage == 'post' else {}
        new = obs.storage
        if obs.stage == 'post':
            for bank in ('configuration', 'slice_valid') if self.c.REGISTER_OUTPUTS else ('configuration',):
                expected = old[bank + ':o_q']
                if old[bank + ':i_rstb'] == '0' and (obs.item.edge or self.c.ASYNC_RESET):
                    expected = '0' * len(expected)
                elif obs.item.edge and old[bank + ':i_enable'] == '1':
                    expected = old[bank + ':i_d']
                assert new[bank + ':o_q'] == expected, f'DFF capture/hold: {bank}'
                self.coverage.storage_checks += 1
            if self.c.REGISTER_OUTPUTS:
                expected = old['slice_input'] if obs.item.edge and old['slice_enable'] == '1' else old['slice_data']
                assert new['slice_data'] == expected, 'Elastic payload capture/hold'
                self.coverage.storage_checks += 1
        _, plan = self.model.evaluate(obs.ports)
        bits = sum(1 << (n - 1) for n in plan['faults'])
        assert number(new['detected']) == bits, 'All-class fault bitmap'
        assert number(new['format_error_events']) == (bits if plan['input'] else 0)
        row = (self.model.accepted % self.model.descriptor['i_row_beats']
               if self.model.active and self.model.accepted < self.model.descriptor['i_frame_beats']
               else 0)
        assert number(new['row_index']) == row, 'Wrapping row counter'
        for pin, expected in (
            ('i_write_enable', int(plan['config'])), ('i_suppress', int(bool(plan['error']))),
            ('o_write_enable', int(plan['start'])), ('o_write_suppressed', int(bool(plan['error'])))):
            assert number(new['gate:' + pin]) == expected, 'Configuration write gate'
        if not (plan['normal'] and plan['active'] and plan['p']['i_valid'] == 1 and
                self.model.descriptor['i_mode'] == 1 and
                self.model.accepted < self.model.descriptor['i_frame_beats']):
            assert number(new['claims']) == number(new['expected_claims']) == 0, 'Comparator isolation'
        self.coverage.isolation_checks += 1

    def write(self, obs):
        item, ports, stage = obs.item, obs.ports, obs.stage
        for name in INPUTS:
            value = item.ports[name]
            assert number(ports[name]) == value if isinstance(value, int) else ports[name] == value.lower()
        if stage == 'pre' and self.c.ASYNC_RESET and number(ports['i_rstb']) == 0:
            self.coverage.reset_observed(self.model)
            self.model.reset()
            self.initialized = True
        if stage == 'edge':
            assert all(ports[n] == item.pre.ports[n] for n in OUTPUTS), 'Expected pre-NBA snapshot'
        if stage == 'post':
            if item.edge and number(item.pre.ports['i_rstb']) == 0:
                self.coverage.reset_observed(self.model)
            plan = self.model.step(item.pre.ports, item.edge)
            self.initialized |= item.edge and number(ports['i_rstb']) == 0
            self.coverage.record(obs, self.model, plan)
        if self.initialized:
            expected, plan = self.model.evaluate(ports)
            for name, value in expected.items():
                if value is None:
                    raise AssertionError(f'STREAM_FORMATTER_PROTOCOL: unknown selected byte ({name})')
                assert number(ports[name]) == value, f'{name}: {ports[name]} != {value}: {item.get_name()} {stage}'
            if self.c.check_internals and stage != 'edge':
                self.storage(obs)
            if stage == 'pre':
                source = self.previous_pre
                if (source and source['i_valid'] == '1' and source['o_ready'] == '0' and
                        source['i_rstb'] == ports['i_rstb'] == '1' and
                        source['i_flush'] == ports['i_flush'] == '0'):
                    assert ports['i_valid'] == '1'
                    assert all(source['i_' + n] == ports['i_' + n] for n in PAYLOAD), 'Source changed while stalled'
                old = self.previous
                if (old and old['o_valid'] == '1' and old['i_ready'] != '1' and
                        old['i_rstb'] == ports['i_rstb'] == '1' and
                        old['i_flush'] == ports['i_flush'] == '0'):
                    assert all(old[n] == ports[n] for n in RESULT), 'Stalled output changed'
            if stage == 'post' and item.edge:
                self.previous = dict(ports)
                self.previous_pre = dict(item.pre.ports)
        self.coverage.observations[stage] += 1

    def check_phase(self):
        m = self.model
        assert self.initialized and not m.active and m.pending is None
        assert m.total_in == m.total_out + m.discarded
