"""Check command ownership, context snapshots and independent transfer ledgers."""
from collections import deque
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from tile_shell.model import ShellModel, number, capability_id
from tile_shell.transaction import OUTPUTS

class TileShellScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = ShellModel(self.c)
        self.capability = capability_id(self.c.parameters)
        self.held = {}
        self.monitoring = False
        self.transfer_counts = [0] * 6
        self.debug_expected = deque()
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write

    def responses(self, p, domain):
        m = self.model
        if domain == 'cfg':
            if p['o_cfg_response_valid']:
                tag = p['o_cfg_response_tag']
                assert tag in m.cfg_responses and m.cfg_responses[tag] is not None, 'Unowned configuration response'
                expected = m.cfg_responses[tag]
                for field, value in expected.items():
                    assert p['o_cfg_response_' + field] == value, (field, p['o_cfg_response_' + field], value)
                assert p['o_cfg_response_error'] == bool(expected['error_code'])
                if p['i_cfg_response_ready']:
                    del m.cfg_responses[tag]
                    self.coverage.counts['cfg_response'] += 1
        elif p['o_runtime_response_valid']:
            assert m.runtime_responses, 'Unowned runtime response'
            expected = m.runtime_responses[0]
            for field, value in expected.items():
                assert p['o_runtime_response_' + field] == value, (field, p['o_runtime_response_' + field], value)
            assert p['o_runtime_response_error'] == bool(expected['error_code'])
            if p['i_runtime_response_ready']:
                m.runtime_responses.popleft()
                if not expected['error_code']:
                    m.state = expected['state']
                self.coverage.counts['runtime_response'] += 1

    def stability(self, p, domain):
        channels = [('cfg_response', 'i_cfg_response_ready')] if domain == 'cfg' else [
            ('runtime_response', 'i_runtime_response_ready'), ('power_response', 'i_power_response_ready'),
            ('debug_response', 'i_debug_response_ready'), ('trace', 'i_trace_ready')]
        for prefix, ready in channels:
            fields = {n: p[n] for n in OUTPUTS if n.startswith('o_' + prefix + '_')}
            key = domain, prefix
            if key in self.held:
                assert fields == self.held[key], f'{prefix} changed under backpressure'
                self.coverage.counts['held_response'] += 1
            if p['o_' + prefix + '_valid'] and p[ready] == 0:
                self.held[key] = fields
            else:
                self.held.pop(key, None)

    def write(self, obs):
        p = {n: number(v) for n, v in obs.ports.items()}
        m, c, v = self.model, self.c, self.coverage
        if p['i_rstb'] == 0 or c.CONFIG_ASYNC and p['i_cfg_rstb'] == 0:
            m.reset()
            self.monitoring = False
            self.transfer_counts = [0] * 6
            self.debug_expected.clear()
            self.held.clear()
            v.counts['reset'] += 1
            return
        if obs.domain == 'post':
            if p['o_body_context_active']:
                ctx = p['o_body_context_id']
                assert ctx < c.CONTEXT_DEPTH and m.validated[ctx], 'Unvalidated body context'
                assert p['o_body_context_version'] == m.versions[ctx]
                assert p['o_body_context_image'] == int.from_bytes(m.image(ctx), 'little')
                assert p['o_body_context_word_valid'] == (1 << c.CONFIG_WORD_COUNT) - 1
                v.counts['atomic_context'] += 1
            if p['o_status_fatal_error']:
                assert p['o_body_start'] == 0 and p['o_body_data_in_valid'] == 0
                assert p['o_data_in_ready'] == 0
                v.counts['containment'] += 1
            if p['o_status_execution_state'] == 9:
                assert p['o_body_data_in_valid'] == p['o_body_predicate_in_valid'] == 0
                assert p['o_body_data_out_ready'] == p['o_body_predicate_out_ready'] == 0
                v.counts['suspended'] += 1
            assert p['o_monitor_clock_enable'] == self.monitoring
            assert p['o_status_tile_id'] == c.TILE_ID
            assert p['o_status_tile_class'] == c.TILE_CLASS
            assert p['o_status_arch_version'] == 1
            assert p['o_status_capability_id'] == self.capability
            if not c.SUPPORT_TRACE:
                assert p['o_trace_valid'] == p['o_trace_data'] == 0
            v.states.add(p['o_status_execution_state'])
            v.power_states.add(p['o_status_power_state'])
            v.accounting = dict(accepted=m.accepted, delivered=m.delivered, discarded=m.discarded,
                outstanding=sum(len(q) for qs in m.queues.values() for q in qs))
            return
        if obs.domain == 'cfg' or obs.domain == 'core' and not c.CONFIG_ASYNC:
            if p['i_cfg_request_valid'] == 1 and p['o_cfg_request_ready']:
                command, error = m.config(p)
                v.cfg_commands.add(command)
                if command == 0 and not error:
                    v.context_words.add((p['i_cfg_request_context_id'], p['i_cfg_request_word_index']))
                v.errors.add(error)
                v.counts['cfg_request'] += 1
            self.responses(p, 'cfg')
            self.stability(p, 'cfg')
        if obs.domain != 'core':
            return
        v.counts['core_edges'] += 1
        v.counts['random_cycles'] += obs.item.get_name().startswith('random_')
        m.validate(p)
        if p['o_body_validate_valid'] and p['i_body_validate_ready']:
            assert p['o_body_clock_enable'] and not p['o_body_flush']
        if p['i_runtime_request_valid'] == 1 and p['o_runtime_request_ready']:
            command, error = m.runtime(p)
            if not error and command == 0:
                self.monitoring = True
            if not error and command == 6:
                self.monitoring = False
            v.runtime_commands.add(command)
            v.errors.add(error)
            v.counts['runtime_request'] += 1
        self.responses(p, 'core')
        self.stability(p, 'core')
        terminate = (p['i_runtime_request_valid'] == 1 and p['o_runtime_request_ready'] and
                     p['i_runtime_request_command'] == 5 and not m.runtime_responses[-1]['error_code'])
        discard = terminate or p['o_status_fatal_error'] or (
            p['o_body_flush'] and p['o_status_execution_state'] == 12)
        if discard:
            m.cancel_validation(12 if terminate else 17)
        if p['o_debug_response_valid']:
            assert self.debug_expected, 'Unowned debug response'
            expected = self.debug_expected[0]
            if expected is not None:
                assert p['o_debug_response_error'] == 0
                assert p['o_debug_response_read_data'] == expected, 'Transfer counter mismatch'
                v.counts['counter_checks'] += 1
            if p['i_debug_response_ready'] == 1:
                self.debug_expected.popleft()
        if p['i_debug_request_valid'] == 1 and p['o_debug_request_ready']:
            address = p['i_debug_request_address']
            expected = self.transfer_counts[address - 0x40] if not p['i_debug_request_write'] and 0x40 <= address < 0x46 else None
            self.debug_expected.append(expected)
            if p['i_debug_request_write'] and address == 0x21 and p['i_debug_request_owner_id'] == m.owner:
                self.monitoring = bool(p['i_debug_request_write_data'] & 1)
        if p['o_monitor_clock_enable']:
            for index, (valid, ready) in enumerate((
                ('i_data_in_valid', 'o_data_in_ready'),
                ('o_data_out_valid', 'i_data_out_ready'),
                ('i_predicate_in_valid', 'o_predicate_in_ready'),
                ('o_predicate_out_valid', 'i_predicate_out_ready'),
                ('i_event_in_valid', 'o_event_in_ready'),
                ('o_event_out_valid', 'i_event_out_ready'))):
                if p[valid] is not None and p[ready] is not None:
                    self.transfer_counts[index] = min((1 << c.CONFIG_DATA_WIDTH) - 1,
                        self.transfer_counts[index] + (p[valid] & p[ready]).bit_count())
        transfers = m.transfers(p, bool(discard))
        for group, port, kind in transfers:
            v.transfers.add((group, port, kind))
        if (p['i_runtime_request_valid'] == 1 and p['o_runtime_request_ready'] and
            p['i_runtime_request_command'] == 6 and not error):
            self.transfer_counts = [0] * 6
        if p['o_trace_valid'] and p['i_trace_ready']:
            v.counts['trace'] += 1
        if p['o_power_response_valid'] and p['i_power_response_ready']:
            v.counts['power_response'] += 1
        if p['o_debug_response_valid'] and p['i_debug_response_ready']:
            v.counts['debug_response'] += 1

    def check_phase(self):
        m = self.model
        assert not m.cfg_responses and not m.runtime_responses and not m.validations
        assert not self.debug_expected
        assert all(not q for qs in m.queues.values() for q in qs)
        assert m.accepted == m.delivered + m.discarded
