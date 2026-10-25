"""Check all outputs, storage effects, completion ownership and capture enables."""
from collections import deque
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from scratchpad_controller.model import ControllerModel, fields, number, raw, unpack
from scratchpad_controller.transaction import OUTPUTS, REQ_FIELDS, RSP_FIELDS


class ControllerScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = ControllerModel(self.c)
        self.memory = [dict() for _ in range(self.c.NUM_BANKS)]
        self.bank_obligations = [deque() for _ in range(self.c.NUM_BANKS)]
        self.bank_models = []
        if self.c.integration:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from scratchpad_bank.config import ScratchpadBankConfig, DEFAULTS
            from scratchpad_bank.model import ScratchpadBankModel
            c = self.c
            parameters = DEFAULTS | dict(DATA_WIDTH=c.DATA_WIDTH, DEPTH_WORDS=c.BANK_DEPTH_WORDS,
                TAG_WIDTH=c.aliases['K'], MAX_OUTSTANDING=3, BACKEND_READ_LATENCY=2,
                PROTECTION_MODE=c.protection, ASYNC_RESET=c.ASYNC_RESET)
            bank_config = ScratchpadBankConfig(parameters, c.seed, c.random_cycles, True,
                                              c.coverage_file, '')
            self.bank_models = [ScratchpadBankModel(bank_config) for _ in range(c.NUM_BANKS)]
        self.counts = [0] * (self.c.NUM_CLIENTS * 15 + self.c.NUM_BANKS * 10 +
                            self.c.NUM_CLIENTS * self.c.NUM_BANKS + 2)
        self.peaks = [0] * self.c.NUM_CLIENTS
        self.initialized = False
        self.previous = None
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write

    def counters_step(self, ports, item, q):
        c, p = self.c, q['p']
        if p['i_rstb'] == 0 and (item.edge or c.ASYNC_RESET):
            self.counts = [0] * len(self.counts)
            self.peaks = [0] * c.NUM_CLIENTS
        elif item.edge and q['run'] and item.peer.get('counter_enable', 1) == 1:
            if item.peer.get('counter_clear', 0) == 1:
                self.counts = [0] * len(self.counts)
                self.peaks = [0] * c.NUM_CLIENTS
                self.coverage.events['counter_clear'] += 1
                return
            inc = [0] * len(self.counts)
            req_valid = unpack(ports['i_client_req_valid'], c.NUM_CLIENTS, 1)
            ready = unpack(ports['i_client_rsp_ready'], c.NUM_CLIENTS, 1)
            issuing = q['active'] and not self.model.error and not q['perm_accept']
            for n in range(c.NUM_CLIENTS):
                req = q['reqs'][n]
                accepted = n in q['allocations']
                routed = accepted and not q['errors'][n]
                read_bytes = (1 << req['size_log2']) if routed and not req['write'] else 0
                write_bytes = req['wstrobe'].bit_count() if routed and req['write'] else 0
                denied = accepted and q['errors'][n] == 10
                inc[n * 15:n * 15 + 15] = [int(accepted), int(n in q['retirements']), read_bytes,
                    write_bytes, int(any(n in v for v in q['candidates']) and not accepted),
                    int(issuing and req_valid[n] == 1 and len(self.model.queues[n]) == c.MAX_OUTSTANDING_PER_CLIENT),
                    int(q['client_responses'][n] is not None and ready[n] != 1),
                    int(sum(t == n for t in q['targets']) > 1 and q['active']), int(denied),
                    *(int(accepted and q['errors'][n] == code) for code in range(1, 7))]
                if denied:
                    inc[c.NUM_CLIENTS * 15 + c.NUM_BANKS * 10 + n * c.NUM_BANKS + q['mapped'][n][0]] = 1
                self.peaks[n] = max(self.peaks[n], len(self.model.queues[n]))
            bank_valid = unpack(ports['i_bank_rsp_valid'], c.NUM_BANKS, 1)
            for b in range(c.NUM_BANKS):
                req = q['bank_requests'][b]
                accepted = b in q['bank_accept']
                collected = b in q['bank_collect'] and not q['malformed'][b]
                k = c.NUM_CLIENTS * 15 + b * 10
                inc[k:k + 10] = [int(accepted and not req['write']), int(accepted and req['write']),
                    (1 << req['size_log2']) if accepted and not req['write'] else 0,
                    req['wstrobe'].bit_count() if accepted and req['write'] else 0,
                    int(len(q['candidates'][b]) > 1), int(len(q['candidates'][b]) > int(accepted)),
                    int(req is not None and not accepted),
                    int(q['active'] and bank_valid[b] == 1 and b not in q['bank_collect']),
                    int(collected and q['rsps'][b]['corrected'] == 1),
                    int(collected and q['rsps'][b]['uncorrectable'] == 1)]
            inc[-2:] = [int(q['start']), int(q['run'] and (q['start'] or self.model.flushing))]
            self.counts = [min(255, old + step) for old, step in zip(self.counts, inc)]
            self.coverage.saturated |= 255 in self.counts
        elif item.edge and q['run']:
            self.coverage.events['counter_disabled'] += 1

    def storage_effects(self, obs, q):
        c, p = self.c, obs.ports
        if c.integration:
            return
        if number(p['i_rstb']) == 0:
            self.bank_obligations = [deque() for _ in range(c.NUM_BANKS)]
            return
        if not q['run']:
            return
        for b in q['bank_collect']:
            if not q['malformed'][b] and not q['rsps'][b]['error']:
                assert q['rsps'][b]['rdata'] is not None, 'SCRATCHPAD_CONTROLLER_PROTOCOL: unknown successful read data'
            if obs.item.peer.get('inject') or q['malformed'][b]:
                continue
            assert self.bank_obligations[b], f'Unsolicited bank completion {b}'
            expected = self.bank_obligations[b].popleft()
            actual = q['rsps'][b]
            assert actual['tag'] == expected['tag'] and actual['write'] == expected['write']
            if not actual['error']:
                assert actual['rdata'] is not None, 'SCRATCHPAD_CONTROLLER_PROTOCOL: unknown successful read data'
                assert actual['rdata'] == expected['data'], f'Storage data bank {b}: {actual} != {expected}'
            self.coverage.storage_checks += 1
        for b in q['bank_accept']:
            e = q['bank_requests'][b]
            address = e['address']
            size = 1 << e['size_log2']
            data = 0
            if e['write']:
                assert isinstance(e['wdata'], int), 'SCRATCHPAD_CONTROLLER_PROTOCOL: unknown selected write data'
                for k in range(size):
                    if e['wstrobe'] >> k & 1:
                        self.memory[b][address + k] = e['wdata'] >> (k * 8) & 255
            else:
                data = sum(self.memory[b].get(address + k, 0) << (k * 8) for k in range(size))
            self.bank_obligations[b].append(dict(tag=e['tag'], write=e['write'], data=data))
        for b, bit in enumerate(q['flush']):
            if bit:
                self.bank_obligations[b].clear()

    def check_banks(self, obs):
        from scratchpad_bank.transaction import PORTS as BANK_PORTS, OUTPUTS as BANK_OUTPUTS
        for b, model in enumerate(self.bank_models):
            ports = {n: obs.storage[f'bank:{b}:{n}'] for n in BANK_PORTS}
            if obs.stage == 'pre' and 'fault' in obs.item.peer:
                source, word, mask = obs.item.peer['fault']
                if b == source:
                    model.memory[word] = raw(int(model.memory[word], 2) ^ mask, model.c.stored_width)
                    self.coverage.events['physical_fault'] += 1
            if obs.stage == 'pre' and self.c.ASYNC_RESET and number(ports['i_rstb']) == 0:
                model.reset()
            if obs.stage == 'post':
                before = {n: obs.item.pre.storage[f'bank:{b}:{n}'] for n in BANK_PORTS}
                model.step(before, obs.item.edge)
            if self.initialized and obs.stage != 'edge':
                expected, _ = model.evaluate(ports)
                for n in BANK_OUTPUTS:
                    assert ports[n] == raw(expected[n], len(ports[n])), f'Integrated bank {b} {n}'
                for word in range(self.c.BANK_DEPTH_WORDS):
                    assert obs.storage[f'memory:{b}:{word}'] == model.memory[word], f'Integrated raw memory {b}:{word}'
                self.coverage.storage_checks += 1

    def check_storage(self, obs):
        c, m = self.c, self.model
        for n in range(c.NUM_CLIENTS):
            assert number(obs.storage[f'{n}:occupancy']) == len(m.queues[n])
            assert number(obs.storage[f'{n}:issue']) == m.issue[n]
            assert number(obs.storage[f'{n}:retire']) == (m.queues[n][0]['slot'] if m.queues[n] else m.issue[n])
            for s in range(c.MAX_OUTSTANDING_PER_CLIENT):
                entry = next((e for e in m.queues[n] if e['slot'] == s), None)
                assert number(obs.storage[f'{n}:{s}:allocated:o_q']) == int(entry is not None)
                assert number(obs.storage[f'{n}:{s}:present:o_q']) == int(entry is not None and entry['result'] is not None)
                if obs.stage == 'post':
                    for kind in ('metadata', 'result', 'allocated', 'present'):
                        key = f'{n}:{s}:{kind}:'
                        old = obs.item.pre.storage
                        expected = old[key + 'o_q']
                        if old[key + 'i_rstb'] == '0' and (obs.item.edge or c.ASYNC_RESET):
                            expected = '0' * len(expected)
                        elif obs.item.edge and old[key + 'i_enable'] == '1':
                            expected = old[key + 'i_d']
                        assert obs.storage[key + 'o_q'] == expected, f'Completion capture/hold {key}'
                        self.coverage.capture_checks += 1
        for b in range(c.NUM_BANKS):
            assert number(obs.storage[f'pointer:{b}']) == m.rpointer[b], 'Request RR pointer'
            assert number(obs.storage[f'pending:{b}']) == int(m.pending[b] is not None), 'Held grant'
        assert unpack(obs.storage['read_permission'], c.NUM_CLIENTS * c.NUM_BANKS, 1) == m.read
        assert unpack(obs.storage['write_permission'], c.NUM_CLIENTS * c.NUM_BANKS, 1) == m.write

    def write(self, obs):
        stage, item, p = obs.stage, obs.item, obs.ports
        if stage == 'pre' and self.c.ASYNC_RESET and number(p['i_rstb']) == 0:
            self.model.reset()
            self.counts = [0] * len(self.counts)
            self.peaks = [0] * self.c.NUM_CLIENTS
            self.initialized = True
            self.bank_obligations = [deque() for _ in range(self.c.NUM_BANKS)]
        if stage == 'edge':
            assert all(p[n] == item.pre.ports[n] for n in OUTPUTS), 'Outputs changed before NBA'
        if stage == 'post':
            _, q = self.model.evaluate(item.pre.ports)
            self.counters_step(item.pre.ports, item, q)
            if item.edge:
                self.storage_effects(item.pre, q)
            self.coverage.record(item, self.model, q)
            self.model.step(item.pre.ports, item.edge)
            m = self.model
            self.coverage.accounting = dict(accepted=m.accepted, retired=m.retired, canceled=m.canceled,
                                            outstanding=sum(map(len, m.queues)))
            self.initialized |= number(p['i_rstb']) == 0 and item.edge
        if self.c.integration:
            self.check_banks(obs)
        if self.initialized:
            expected, q = self.model.evaluate(p)
            for name, value in expected.items():
                assert p[name] == value, f'{name}: {p[name]} != {value} ({item.get_name()} {stage})'
            if stage != 'edge':
                self.check_storage(obs)
            if self.c.instrumentation and stage != 'edge':
                assert unpack(obs.storage['counter:counts'], len(self.counts), 8) == self.counts, 'Optional counters'
                assert unpack(obs.storage['counter:peaks'], len(self.peaks), 8) == self.peaks, 'Peak occupancy'
                assert number(obs.storage['counter:disabled_counts']) == 0
                assert number(obs.storage['counter:disabled_peaks']) == 0
                self.coverage.counter_checks += 1
            self.coverage.observations[stage] += 1
        if stage == 'pre' and self.previous is not None and number(p['i_rstb']) == 1 and number(p['i_flush']) == 0:
            old = self.previous
            if number(old['i_rstb']) == 1 and number(old['i_flush']) == 0 and not number(old['o_error']):
                for side, count in [('bank', self.c.NUM_BANKS), ('client', self.c.NUM_CLIENTS)]:
                    kind = 'req' if side == 'bank' else 'rsp'
                    ready = f"{'i' if side == 'bank' else 'i'}_{side}_{kind}_ready"
                    for n, (valid, accepted) in enumerate(zip(unpack(old[f'o_{side}_{kind}_valid'], count, 1),
                                                              unpack(old[ready], count, 1))):
                        if valid == 1 and accepted != 1:
                            for f in (REQ_FIELDS if kind == 'req' else RSP_FIELDS):
                                key = f'o_{side}_{kind}_{f}'
                                width = self.c.widths[key] // count
                                assert unpack(p[key], count, width)[n] == unpack(old[key], count, width)[n], f'Stalled {key}'
        if stage == 'pre' and self.c.integration and self.previous is not None:
            if number(p['i_rstb']) == 1 and number(p['i_flush']) == 0 and number(self.previous['i_rstb']) == 1:
                for b in range(self.c.NUM_BANKS):
                    old = self.previous_storage
                    prefix = f'bank:{b}:'
                    if old[prefix + 'i_flush'] == '0' and obs.storage[prefix + 'i_flush'] == '0':
                        for kind, source, sink, names in [('req', 'i', 'o', REQ_FIELDS), ('rsp', 'o', 'i', RSP_FIELDS)]:
                            if old[prefix + f'{source}_{kind}_valid'] == '1' and old[prefix + f'{sink}_{kind}_ready'] != '1':
                                assert obs.storage[prefix + f'{source}_{kind}_valid'] == '1', 'Bank peer withdrew valid'
                                for name in names:
                                    pin = prefix + f'{source}_{kind}_{name}'
                                    assert obs.storage[pin] == old[pin], f'Bank interface stability {pin}'
        if stage == 'post':
            self.previous = item.pre.ports
            self.previous_storage = item.pre.storage

    def check_phase(self):
        m = self.model
        assert not any(m.queues)
        assert m.accepted == m.retired + m.canceled
        self.coverage.accounting = dict(accepted=m.accepted, retired=m.retired, canceled=m.canceled,
                                        outstanding=sum(map(len, m.queues)))
