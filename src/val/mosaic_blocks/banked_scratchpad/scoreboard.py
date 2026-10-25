"""Independent region oracle, byte memory, ordered obligations, and signal holds."""
from collections import Counter, deque
from pyuvm import ConfigDB, uvm_subscriber
from banked_scratchpad.model import Architecture, lane, map_address, encode_descriptor


class ScratchpadScoreboard(uvm_subscriber):
    def build_phase(self):
        super().build_phase()
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.active = ConfigDB().get(self, '', 'active')
        self.model = Architecture(self.c.parameters)
        self.active['model'] = self.model
        self.queues = [deque() for _ in range(self.c.NUM_CLIENTS)]
        self.active['queues'] = self.queues
        self.command = None
        self.event = None
        self.holds = {}
        self.ticks = 0
        self.flushing = False
        self.statistics = Counter()
        self.peaks = [0] * (self.c.NUM_CLIENTS + self.c.NUM_BANKS + self.c.NUM_REGIONS)

    def check_statistics(self, p, b):
        a = self.c.a
        for index, expected in self.statistics.items():
            assert lane(b['statistics'], 32, index) == expected, ('counter', index, expected,
                lane(b['statistics'], 32, index))
        for index, expected in enumerate(self.peaks):
            assert lane(b['outstanding_peaks'], 32, index) == expected, ('peak', index, expected)
        for c in range(a['C']):
            self.peaks[c] = max(self.peaks[c], lane(p['o_client_outstanding'], a['CO'], c))
            if p['i_client_req_valid'] >> c & p['o_client_req_ready'] >> c & 1:
                op = lane(p['i_client_req_opcode'], 2, c)
                if op < 2:
                    self.statistics[c * 18 + op] += 1
                    self.statistics[c * 18 + 2 + op] += lane(p['i_client_req_size'] or 0, a['Z'], c)
        for bank in range(a['B']):
            self.peaks[a['C'] + bank] = max(self.peaks[a['C'] + bank],
                lane(p['o_bank_outstanding'], a['BO'], bank))
            if b['bank_req_valid'] >> bank & b['bank_req_ready'] >> bank & 1:
                op = lane(b['bank_req_write'], 1, bank)
                base = a['C'] * 18 + bank * 16
                self.statistics[base + op] += 1
                self.statistics[base + 2] += 1 << lane(b['bank_req_size'], a['LZ'], bank)
        for r in range(a['R']):
            index = a['C'] + a['B'] + r
            self.peaks[index] = max(self.peaks[index], lane(p['o_region_outstanding'], a['RO'], r))

    def write(self, obs):
        p, b, a = obs.ports, obs.banks, self.c.a
        self.ticks += 1
        cov, m = self.coverage, self.model
        if not p['i_reset_n']:
            assert not p['o_client_req_ready'] and not p['o_client_rsp_valid']
            for q in self.queues:
                cov.counts['canceled'] += len(q)
                q.clear()
            m.reset()
            self.command = self.event = None
            self.holds.clear()
            self.flushing = False
            self.statistics.clear()
            self.peaks = [0] * len(self.peaks)
            return
        self.check_statistics(p, b)
        if obs.item.fault and obs.item.fault[0] == 'memory':
            _, key, mask = obs.item.fault
            m.faults[key] = m.faults.get(key, 0) ^ mask
            if not m.faults[key]:
                m.faults.pop(key)
        if p['o_flush_completed']:
            self.flushing = False
        if p['i_flush'] or self.flushing:
            assert not p['o_client_req_ready'] and not p['o_client_rsp_valid']
            for q in self.queues:
                cov.counts['canceled'] += len(q)
                q.clear()
            self.holds.clear()
            if self.command and not self.command[2]:
                self.command = None
            self.flushing = not bool(p['o_flush_completed'])
            return
        # Stability is checked before accepting a transfer, so the final stalled
        # cycle and the eventual ready edge carry exactly the same payload.
        groups = [('region', 'o_region_rsp_valid', 'i_region_rsp_ready',
            ('o_region_rsp_descriptor', 'o_region_rsp_error', 'o_region_rsp_error_code')),
            ('event', 'o_event_valid', 'i_event_ready', tuple(n for n in p if n.startswith('o_event_') and n != 'o_event_valid'))]
        for key, valid, ready, names in groups:
            payload = tuple(p[n] for n in names)
            if key in self.holds:
                assert p[valid] and payload == self.holds[key], (key, 'unstable payload')
            if p[valid] and not p[ready]:
                self.holds[key] = payload
                cov.counts['management_stalls'] += 1
            else:
                self.holds.pop(key, None)
        for c, q in enumerate(self.queues):
            widths = dict(opcode=2, addr=a['A'], size=a['Z'], wdata=a['D'], wstrb=a['Y'],
                owner_id=a['O'], kernel_id=a['K'], region_id=a['RI'], generation=a['G'], tag=a['T'])
            if p['i_client_req_valid'] >> c & p['o_client_req_ready'] >> c & 1:
                x = {n: None if p['i_client_req_' + n] is None else
                    lane(p['i_client_req_' + n], w, c) for n, w in widths.items()}
                code = m.check(c, x)
                x['result'] = (0, code, 0, 0) if code or x['opcode'] == 2 else None
                x['forwarded'] = False
                q.append(x)
                cov.counts['accepted'] += 1
                cov.errors[code] += bool(code)
                if code:
                    cov.hit('local_error')
            if b['dispatch_valid'] >> c & b['dispatch_ready'] >> c & 1:
                x = next((x for x in q if x['result'] is None and not x['forwarded']), None)
                assert x is not None, ('unexpected controller dispatch', c)
                x['forwarded'] = True
                x['dispatch_tick'] = self.ticks
            if p['o_client_rsp_valid'] >> c & 1:
                assert q, ('unexpected response', c)
                x = q[0]
                actual = tuple(lane(p['o_client_rsp_' + n], w, c) for n, w in (
                    ('rdata', a['D']), ('error_code', 8), ('corrected', 1), ('uncorrectable', 1)))
                assert x['result'] is not None, ('response before bank access', c, x)
                assert actual == x['result'], (self.ticks, c, x, actual)
                for n, w in (('opcode', 2), ('tag', a['T']), ('region_id', a['RI']), ('generation', a['G'])):
                    assert lane(p['o_client_rsp_' + n], w, c) == x[n], (n, x)
                assert lane(p['o_client_rsp_error'], 1, c) == bool(actual[1])
                key = ('client', c)
                payload = actual + tuple(x[n] for n in ('opcode', 'tag', 'region_id', 'generation'))
                if key in self.holds:
                    assert self.holds[key] == payload
                if p['i_client_rsp_ready'] >> c & 1:
                    q.popleft()
                    self.holds.pop(key, None)
                    cov.counts['responses'] += 1
                else:
                    self.holds[key] = payload
                    cov.counts['response_stalls'] += 1
            elif ('client', c) in self.holds:
                raise AssertionError('Stalled response disappeared')
        grants = b['bank_req_valid'] & b['bank_req_ready']
        if grants.bit_count() > 1:
            cov.hit('parallel_banks')
        for bank in range(a['B']):
            if not grants >> bank & 1:
                continue
            client = lane(b['bank_req_tag'], a['CI'] + a['SI'], bank) >> a['SI']
            x = next((x for x in self.queues[client] if x['result'] is None and
                x['forwarded'] and x['dispatch_tick'] == self.ticks), None)
            assert x is not None, ('unsolicited bank access', client, bank)
            target, local = map_address(self.c.parameters, x['addr'])
            assert (bank, lane(b['bank_req_address'], a['BA'], bank)) == (target, local)
            assert lane(b['bank_req_size'], a['LZ'], bank) == x['size'].bit_length() - 1
            assert lane(b['bank_req_write'], 1, bank) == (x['opcode'] == 1)
            if x['opcode'] == 1:
                assert lane(b['bank_req_strobe'], a['Y'], bank) == (1 << x['size']) - 1
                assert lane(b['bank_req_data'], a['D'], bank) == x['wdata'] & ((1 << (8 * x['size'])) - 1)
            assert m.power[bank] == 0 and p['o_bank_clock_enable'] >> bank & 1
            x['result'] = m.access(x)
            cov.banks[bank] += 1
            cov.sizes[x['size']] += 1
            if x['result'][2]:
                cov.hit('corrected')
            if x['result'][3]:
                cov.hit('uncorrectable')
            if self.c.ENFORCE_REGIONS and (x['result'][2] or x['result'][3]):
                d = m.regions[x['region_id']]
                d['corrected'] |= x['result'][2]
                d['uncorrectable'] |= x['result'][3]
        if p['o_bank_conflict']:
            cov.hit('conflict')
        if p['i_region_cmd_valid'] and p['o_region_cmd_ready']:
            assert self.command is None
            x = {n.removeprefix('i_region_'): v for n, v in p.items() if n.startswith('i_region_')
                and n not in ('i_region_cmd_valid', 'i_region_rsp_ready')}
            response, code, updates = m.command(x)
            self.command = [x, (response, code, updates), False]
            if x['cmd_opcode'] != 0 or code:
                before = m.regions[x['cmd_a']] if x['cmd_a'] is not None and x['cmd_a'] < a['R'] else {}
                other = m.regions[x['cmd_b']] if x['cmd_b'] is not None and x['cmd_b'] < a['R'] else {}
                event = 4 if code else 2 if x['cmd_opcode'] == 3 else 3 if x['cmd_opcode'] == 4 else \
                    0 if response['contents'] and response['role'] == 2 else \
                    1 if not response['contents'] and before.get('contents', 0) else 5
                self.event = (event, x['cmd_a'] or 0, x['cmd_b'] or 0,
                    response['generation'], (updates.get(x['cmd_b'], other) if x['cmd_opcode'] == 3 and not code else other).get('generation', 0),
                    response['kernel'], code)
        if p['o_region_rsp_valid']:
            assert self.command is not None, 'Unexpected management response'
            x, (response, code, updates), applied = self.command
            assert p['o_region_rsp_descriptor'] == encode_descriptor(a, response), (x, response, p)
            assert (p['o_region_rsp_error'], p['o_region_rsp_error_code']) == (bool(code), code)
            if not applied:
                for r, d in updates.items():
                    m.regions[r] = d.copy()
                    if d['contents']:
                        for bank in m.banks_for_region(d):
                            m.destroyed[bank] = False
                self.command[2] = True
                cov.counts['commands'] += 1
                cov.counts[f'command_{x["cmd_opcode"]}'] += 1
                cov.counts[f'region_error_{code}'] += bool(code)
            if p['i_region_rsp_ready']:
                self.command = None
        if p['o_event_valid']:
            actual = tuple(p[n] for n in ('o_event_code', 'o_event_region_a', 'o_event_region_b',
                'o_event_generation_a', 'o_event_generation_b', 'o_event_kernel_id', 'o_event_error_code'))
            assert actual == self.event, ('event', actual, self.event)
            if p['i_event_ready']:
                self.event = None
                cov.counts['events'] += 1
        for bank in range(a['B']):
            state = lane(p['o_bank_power_state'], 2, bank)
            m.power[bank] = state
            if state == 3:
                assert not any(bank in m.banks_for_region(d) for d in m.regions)
                m.destroyed[bank] = True
            if state >= 2:
                assert p['o_bank_isolate'] >> bank & 1
                assert not p['o_bank_clock_enable'] >> bank & 1
        if p['o_drained']:
            assert not any(self.queues) and not p['o_client_rsp_valid'] and not p['o_bank_outstanding']
        if p['o_idle']:
            assert not p['o_client_outstanding'] and not p['o_client_rsp_valid']
        if p['o_error']:
            assert self.active.get('allow_error'), ('Unexpected sticky error', p['o_error_code'])
            assert not p['o_client_req_ready']

    def check_phase(self):
        assert not any(self.queues), 'Unretired public requests at test end'
        assert self.command is None and self.event is None
