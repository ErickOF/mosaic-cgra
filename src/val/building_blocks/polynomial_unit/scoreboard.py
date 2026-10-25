"""Independent bank, request and completion ledgers driven by real handshakes."""
from collections import deque
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from polynomial_unit.model import Error, bank, decode_word, evaluate, number, program
from polynomial_unit.ports import OUTPUTS

EVENTS = ('request_accept', 'result_complete', 'request_stall', 'result_stall',
          'horner_stage', 'clip_low', 'clip_high', 'internal_saturation', 'output_saturation',
          'program_write', 'program_read', 'program_commit', 'program_invalidate',
          'coefficient_corrected', 'coefficient_uncorrectable')
CONTROLS = ('i_flush', 'i_drain', 'i_error_clear', 'i_request_valid', 'i_result_ready',
            'i_program_valid', 'i_program_response_ready')


class PolynomialScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.tick = 0
        self.initialized = False
        self.reset()

    def reset(self):
        coefficients = [b['coefficients'] for b in self.banks] if hasattr(self, 'banks') else None
        if hasattr(self, 'pending'):
            self.coverage.discarded += len(self.pending)
            self.coverage.program_discarded += len(self.programs)
        self.banks = [bank(self.c) for _ in range(self.c.NUM_BANKS)]
        if coefficients:
            for b, values in zip(self.banks, coefficients):
                b['coefficients'] = values
        self.pending = deque()
        self.programs = deque()
        self.faults = getattr(self, 'faults', {})
        self.hard_fault = self.hard_latched = False
        self.error = 0
        self.events = dict.fromkeys(EVENTS, 0)
        self.flushed = False

    def inject(self, fault):
        kind, *values = fault
        if kind == 'coefficient':
            b, copy, index, mask = values
            key = b, copy, index
            self.faults[key] = self.faults.get(key, 0) ^ mask
            self.coverage.fault_bits.add((copy, index, mask))
        else:
            self.hard_fault = True
            self.coverage.hard_faults.add(kind)

    def compare(self, p):
        c = self.c
        if not self.initialized:
            return
        for name in OUTPUTS:
            assert number(p[name]) is not None, f'Unknown polynomial output: {name}'
        for prefix in ('o_result_', 'o_program_response_'):
            if number(p[prefix + 'valid']) == 0:
                for name in OUTPUTS:
                    if name.startswith(prefix) and name != prefix + 'valid':
                        assert number(p[name]) == 0, f'Invalid payload not isolated: {name}'
        enabled = number(p['i_rstb']) == 1
        assert number(p['o_error']) == int(enabled and bool(self.error))
        assert number(p['o_error_code']) == (int(self.error) if enabled else 0)
        fatal = self.hard_latched or any(b['fault'] for b in self.banks)
        assert number(p['o_fatal_error']) == int(enabled and fatal)
        assert number(p['o_flushed']) == int(enabled and self.flushed)
        for name in EVENTS:
            assert number(p['o_event_' + name]) == (self.events[name] if enabled else 0), (
                f'Polynomial event mismatch: {name}'
            )
        if not self.hard_fault:
            def packed(field, width):
                return sum(int(b[field]) << (i * width) for i, b in enumerate(self.banks))
            for name, field, width in (
                ('valid', 'valid', 1), ('version', 'version', c.BANK_VERSION_WIDTH),
                ('polynomial_id', 'polynomial_id', c.POLYNOMIAL_ID_WIDTH),
                ('quality_id', 'quality_id', c.QUALITY_ID_WIDTH)):
                assert number(p['o_bank_' + name]) == (packed(field, width) if enabled else 0), name
            complete = sum(int(not c.TRACK_COEFFICIENT_COVERAGE or
                               len(b['coverage']) == c.MAX_DEGREE + 1) << k
                           for k, b in enumerate(self.banks))
            assert number(p['o_bank_program_complete']) == (complete if enabled else 0)
        assert number(p['o_output_queue_occupancy']) <= c.OUTPUT_QUEUE_DEPTH
        assert number(p['o_program_queue_occupancy']) <= c.PROGRAM_RESPONSE_DEPTH
        if number(p['o_result_valid']):
            assert self.pending, 'Unexpected polynomial result'
            record = self.pending[0]
            assert self.tick - record['tick'] >= record['latency'], 'Polynomial completed early'
            for name, value in record['result'].items():
                assert number(p['o_result_' + name]) == value, (
                    f'Polynomial result {name}: expected {value}, got {p["o_result_" + name]}'
                )
        if number(p['o_program_response_valid']):
            assert self.programs, 'Unexpected polynomial program response'
            for name, value in self.programs[0].items():
                assert number(p['o_program_response_' + name]) == value, (
                    f'Program response {name}: expected {value}, got {p["o_program_response_" + name]}'
                )
        if enabled and all(number(p[name]) is not None for name in CONTROLS):
            if number(p['i_flush']) or number(p['i_drain']) or fatal or self.hard_fault:
                assert number(p['o_request_ready']) == 0
            if number(p['i_drain']) and not number(p['i_flush']) and not self.hard_fault:
                assert number(p['o_drain_done']) == int(not self.pending)

    def step(self, obs):
        c = self.c
        p = {name: number(value) for name, value in obs.ports.items()}
        self.tick += 1
        self.coverage.random_cycles += obs.item.random
        self.coverage.labels.add(obs.item.get_name().split(':', 1)[-1])
        if p['i_rstb'] == 0:
            self.reset()
            self.initialized = True
            return
        self.events = dict.fromkeys(EVENTS, 0)
        self.flushed = False
        retained = (Error.INTERNAL if self.hard_latched or self.hard_fault else
                    Error.COEFFICIENT if any(b['fault'] for b in self.banks) else Error.NONE)
        if p['i_rstb'] == 1 and p['i_flush'] == 1:
            self.flushed = bool(self.pending)
            self.coverage.discarded += len(self.pending)
            self.pending.clear()
            self.error = retained
            self.coverage.flushes += 1
            return
        running = p['i_rstb'] == 1 and all(p[name] is not None for name in CONTROLS)
        detected = Error.NONE
        if running and not self.hard_fault:
            request_take = p['i_request_valid'] == p['o_request_ready'] == 1
            program_take = p['i_program_valid'] == p['o_program_ready'] == 1
            self.events['request_accept'] = int(request_take)
            self.events['request_stall'] = int(p['i_request_valid'] == 1 and not p['o_request_ready'])
            self.events['result_stall'] = int(p['o_result_valid'] == 1 and not p['i_result_ready'])
            self.events['result_complete'] = number(obs.internals['finish'])
            self.events['horner_stage'] = int(bool(number(obs.internals['stage_commit'])))
            self.events['internal_saturation'] = int(bool(number(obs.internals['stage_saturated'])))
            clear = not self.pending and not self.programs and p['i_drain'] == 0 and (
                p['i_request_valid'] == p['i_program_valid'] == 0 and p['i_error_clear'] == 1)
            # Operations see pre-edge ownership even when the final result also retires.
            response = updated = None
            if program_take:
                command = {k.removeprefix('i_program_'): v for k, v in p.items()
                           if k.startswith('i_program_') and k not in
                           ('i_program_valid', 'i_program_response_ready')}
                response, updated, corrected, bad = program(
                    c, self.banks, self.pending, self.faults, command,
                    self.hard_latched or any(b['fault'] for b in self.banks))
                self.coverage.commands.add(command['command'])
                if command['command'] == 1 and not response['error']:
                    self.coverage.readback.add((command['bank'], command['coefficient_index']))
                self.coverage.program_errors.add(response['error_code'])
                for op, name in enumerate(('write', 'read', 'commit', 'invalidate')):
                    legal = not response['error'] or (op == 1 and response['error_code'] == 12)
                    self.events['program_' + name] = int(command['command'] == op and legal)
                self.events['coefficient_corrected'] |= int(corrected)
                self.events['coefficient_uncorrectable'] |= int(bad)
                if response['error']:
                    detected = Error(response['error_code'])
            record = None
            if request_take:
                request = {name.removeprefix('i_request_'): value for name, value in p.items()
                           if name.startswith('i_request_') and name != 'i_request_valid'}
                result, stats = evaluate(c, self.banks, self.faults, request)
                b = request['bank']
                tracked = b < c.NUM_BANKS and bool(self.banks[b]['valid'])
                degree = self.banks[b]['degree'] if tracked else 0
                latency = c.MAX_DEGREE + 1 if c.EVALUATION_ARCH else (
                    1 if result['predicated'] or result['error'] else degree + 1)
                record = dict(result=result, tracked=tracked, tick=self.tick, latency=latency)
                self.coverage.accepted += 1
                self.coverage.record_evaluation(request, result, stats, self.banks[b] if tracked else None)
                self.events['clip_low'] = result['clipped_low']
                self.events['clip_high'] = result['clipped_high']
                if result['error'] and detected == Error.NONE:
                    detected = Error(result['error_code'])
                expected_read = tracked and not result['predicated'] and result['error_code'] != 11
                assert bool(number(obs.internals['read_enable']) & 1) == expected_read
            faults = set()
            reads = number(obs.internals['read_enable'])
            for port in range(c.read_ports):
                if not reads >> port & 1:
                    continue
                b = number(obs.internals['read_bank'][port])
                index = number(obs.internals['read_index'][port])
                assert 0 <= b < c.NUM_BANKS and self.banks[b]['valid'], 'Read of invalid bank'
                assert index <= self.banks[b]['degree'], 'Read of unused coefficient'
                value = self.banks[b]['coefficients'][index]
                corrected, bad = (False, True) if value is None else decode_word(
                    value, c.COEFFICIENT_WIDTH, c.COEFFICIENT_PROTECTION,
                    self.faults.get((b, port, index), 0))[1:]
                assert number(obs.internals['read_bad'][-1-port]) == int(bad), str(obs.internals)
                assert number(obs.internals['read_corrected'][-1-port]) == int(corrected), obs.internals
                if bad:
                    faults.add(b)
                self.events['coefficient_corrected'] |= int(corrected)
                self.events['coefficient_uncorrectable'] |= int(bad)
                self.coverage.coefficient_reads.add((b, index))
            if p['o_result_valid'] and p['i_result_ready']:
                retired = self.pending.popleft()
                result = retired['result']
                self.coverage.latencies.add(self.tick - 1 - retired['tick'])
                if not self.coverage.arithmetic_done:
                    self.coverage.numeric_trace.append({
                        name: p['o_result_' + name] for name in result
                        if name not in ('context_id', 'tag')
                    })
                self.coverage.returned += 1
                self.coverage.output_saturations.add((result['output_saturated'],
                    int(bool(result['data'] & (1 << (c.OUTPUT_WIDTH - 1))))))
            if p['o_program_response_valid'] and p['i_program_response_ready']:
                self.programs.popleft()
                self.coverage.program_returned += 1
            if record:
                self.pending.append(record)
            if response:
                self.programs.append(response)
                if command['bank'] < c.NUM_BANKS:
                    self.banks[command['bank']] = updated
                self.coverage.program_accepted += 1
                if command['bank'] < c.NUM_BANKS and self.events['program_write']:
                    for port in range(c.read_ports):
                        self.faults.pop((command['bank'], port, command['coefficient_index']), None)
            for b in faults:
                self.banks[b]['fault'] = 1
            # Final output flags are independently checked on the ordered result.
            if self.events['result_complete']:
                # The finish head is the first accepted record not already queued.
                queued = p['o_output_queue_occupancy']
                finishing = list(self.pending)[queued - int(bool(p['o_result_valid'] and p['i_result_ready']))]
                self.events['output_saturation'] = finishing['result']['output_saturated']
            if self.events['coefficient_corrected'] and detected == Error.NONE:
                detected = Error.CORRECTED
            if self.events['coefficient_uncorrectable']:
                detected = Error.COEFFICIENT
            if clear:
                self.error = retained
        if any(p[name] is None for name in ('i_rstb', *CONTROLS)) or any(
            p['i_' + group + '_valid'] == 1 and any(value is None for name, value in p.items()
                if name.startswith('i_' + group + '_') and name not in
                ('i_' + group + '_valid', 'i_program_response_ready'))
            for group in ('request', 'program')):
            detected = Error.UNKNOWN
            self.coverage.unknowns += 1
        if self.hard_fault:
            detected = Error.INTERNAL
            if running:
                self.hard_latched = True
        if p['i_rstb'] != 0 and self.error == 0 and detected:
            self.error = int(detected)

    def write(self, obs):
        if obs.stage == 'post':
            self.coverage.labels.add(obs.item.get_name().split(':', 1)[-1])
            if obs.item.get_name().endswith(':arithmetic_done'):
                self.coverage.arithmetic_done = True
        if obs.stage == 'pre':
            if obs.item.fault:
                self.inject(obs.item.fault)
            if self.c.ASYNC_RESET and number(obs.ports['i_rstb']) == 0:
                self.reset()
                self.initialized = True
        self.compare(obs.ports)
        if obs.stage == 'edge':
            self.step(obs)
        self.coverage.samples[obs.stage] += 1

    def check_phase(self):
        assert not self.pending and not self.programs, 'Unfinished polynomial transactions'
        assert self.coverage.accepted == self.coverage.returned + self.coverage.discarded
        assert self.coverage.program_accepted == self.coverage.program_returned + self.coverage.program_discarded
