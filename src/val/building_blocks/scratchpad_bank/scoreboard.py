"""Check ordered responses, exact commits, reset persistence and protection."""
import cocotb
from mosaic_uvm.logic import bits
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from scratchpad_bank.driver import disturb
from scratchpad_bank.model import ScratchpadBankModel, number, splice
from scratchpad_bank.transaction import INPUTS, OUTPUTS, REQUEST, RESPONSE


class ScratchpadBankScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = ScratchpadBankModel(self.c)
        self.initialized = False
        self.previous = None
        self.counts = [0] * 23
        self.peak = 0
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write

    def counter_step(self, ports, edge, protocol):
        m, c = self.model, self.c
        out, q = m.evaluate(ports, protocol)
        p, e = q['p'], q['entry']
        if p['i_rstb'] == 0 and (edge or c.ASYNC_RESET):
            self.counts = [0] * 23
            self.peak = 0
        elif edge and q['run']:
            corrected = bad = False
            if q['capture']:
                read = m.reads[0]
                _, _, corrected, bad = m.decode(read['entry'], read['raw'])
            good = q['accept'] and not e['error']
            reading = good and not e['write']
            writing = good and e['write']
            scrub = q['commit'] and not m.work['entry']['write']
            events = [reading, writing, reading, writing,
                      q['consume'] and out['o_rsp_write'] == 0,
                      q['consume'] and out['o_rsp_write'] == 1,
                      q['normal'] and p['i_req_valid'] == 1 and not out['o_req_ready'],
                      out['o_rsp_valid'] and p['i_rsp_ready'] == 0,
                      q['normal'] and q['occupancy'] == c.MAX_OUTSTANDING,
                      writing and e['mask'] not in (0, (1 << c.bytes) - 1),
                      good and e['rmw'],
                      q['normal'] and p['i_req_valid'] == 1 and m.work is not None,
                      corrected, scrub, bad and c.PROTECTION_MODE == 1,
                      bad and c.PROTECTION_MODE == 2,
                      *(q['accept'] and e['error'] == n for n in range(1, 7)),
                      q['flushing'] and not m.flush_seen]
            for n, event in enumerate(events):
                if event:
                    weight = e['size'] if n == 2 else e['mask'].bit_count() if n == 3 else 1
                    self.counts[n] = min(255, self.counts[n] + weight)
            self.peak = max(self.peak, q['occupancy'])
            self.coverage.saturated |= 255 in self.counts

    def storage(self, obs, plan):
        m, c = self.model, self.c
        if obs.stage == 'post':
            old = obs.item.pre.storage
            for n in range(c.MAX_OUTSTANDING):
                for bank in ('metadata', 'result', 'allocated', 'present', 'awaiting'):
                    key = f'{n}:{bank}:'
                    expected = old[key + 'o_q']
                    if old[key + 'i_rstb'] == '0' and (obs.item.edge or c.ASYNC_RESET):
                        expected = '0' * len(expected)
                    elif obs.item.edge and old[key + 'i_enable'] == '1':
                        expected = old[key + 'i_d']
                    assert obs.storage[key + 'o_q'] == expected, f'Completion DFF capture/hold {key}'
                    self.coverage.storage_checks += 1
        for name, raw in obs.storage.items():
            if name.startswith('memory:'):
                word = int(name.split(':')[1])
                assert raw == m.memory[word], f'Raw storage mismatch word {word}: {raw} != {m.memory[word]}'
                self.coverage.memory_checks += 1
        for n in range(c.MAX_OUTSTANDING):
            entry = next((e for e in m.pending if e['slot'] == n), None)
            assert number(obs.storage[f'{n}:allocated:o_q']) == int(entry is not None)
            assert number(obs.storage[f'{n}:present:o_q']) == int(entry is not None and entry['result'] is not None)
            assert number(obs.storage[f'{n}:awaiting:o_q']) == int(any(r['entry']['slot'] == n for r in m.reads))
        assert number(obs.storage['issue_pointer']) == m.next_slot
        assert number(obs.storage['retire_pointer']) == (m.pending[0]['slot'] if m.pending else m.next_slot)
        assert number(obs.storage['work_state']) == (0 if m.work is None else 1 if m.work['stage'] == 'wait' else 2)
        physical = plan['physical']
        expected = dict(i_enable=int(physical is not None), i_write=int(physical is not None and physical['write']),
                        i_addr=physical['word'] if physical else 0, i_wmask=physical['mask'] if physical else 0,
                        i_wdata=0 if not physical or not physical['write'] else
                            splice('0' * c.stored_width, physical['data'], physical['bitmask']))
        for name, value in expected.items():
            assert obs.storage['backend:' + name] == bits(value, len(obs.storage['backend:' + name])), f'Backend {name}'
        error = plan['entry']['error'] if plan['accept'] else 0
        assert number(obs.storage['illegal_events']) == (1 << (error - 1) if error else 0)
        assert number(obs.storage['read_bytes']) == (plan['entry']['size'] if plan['accept'] and not error and not plan['entry']['write'] else 0)
        assert number(obs.storage['write_bytes']) == (plan['entry']['mask'].bit_count() if plan['accept'] and not error and plan['entry']['write'] else 0)
        self.coverage.backend_checks += 1

    def write(self, obs):
        item, p, stage = obs.item, obs.ports, obs.stage
        for name in INPUTS:
            value = item.ports[name]
            assert number(p[name]) == value if isinstance(value, int) else p[name] == value.lower()
        if stage == 'pre':
            if item.fault:
                word, mask, state = item.fault
                self.model.memory[word] = disturb(self.model.memory[word], mask, state)
                self.coverage.fault_observed(mask, state)
            if self.c.ASYNC_RESET and number(p['i_rstb']) == 0:
                self.coverage.reset_observed(self.model)
                self.model.reset()
                self.counts = [0] * 23
                self.peak = 0
                self.initialized = True
        if stage == 'edge':
            assert all(p[n] == item.pre.ports[n] for n in OUTPUTS), 'Expected pre-NBA observation'
        if stage == 'post':
            if item.edge and number(item.pre.ports['i_rstb']) == 0:
                self.coverage.reset_observed(self.model)
            self.counter_step(item.pre.ports, item.edge, item.protocol)
            plan = self.model.step(item.pre.ports, item.edge, item.protocol)
            self.initialized |= item.edge and number(p['i_rstb']) == 0
            self.coverage.record(obs, self.model, plan)
        if self.initialized:
            expected, plan = self.model.evaluate(p, item.protocol)
            for name, value in expected.items():
                assert p[name] == bits(value, len(p[name])), f'{name}: {p[name]} != {value} ({item.get_name()} {stage})'
            if self.c.check_internals and stage != 'edge':
                self.storage(obs, plan)
            if self.c.instrumentation and stage != 'edge':
                packed = sum(value << (8 * n) for n, value in enumerate(self.counts))
                assert number(obs.storage['counter:counts']) == packed, 'Optional event counters'
                assert number(obs.storage['counter:peak']) == self.peak, 'Peak occupancy'
                assert number(obs.storage['counter:disabled_counts']) == 0
                assert number(obs.storage['counter:disabled_peak']) == 0
                self.coverage.counter_checks += 1
            if stage == 'pre' and self.previous:
                old = self.previous
                if old['i_rstb'] == p['i_rstb'] == '1' and old['i_flush'] == p['i_flush'] == '0':
                    if old['i_req_valid'] == '1' and old['o_req_ready'] == '0':
                        assert p['i_req_valid'] == '1'
                        assert all(old[n] == p[n] for n in REQUEST), 'SCRATCHPAD_BANK_PROTOCOL: stalled request changed'
                    if old['o_rsp_valid'] == '1' and old['i_rsp_ready'] != '1':
                        assert all(old[n] == p[n] for n in RESPONSE), 'Stalled response changed'
            if stage == 'post' and item.edge:
                self.previous = dict(item.pre.ports)
        self.coverage.observations[stage] += 1

    def check_phase(self):
        m = self.model
        assert self.initialized and not m.pending and not m.reads and not m.work
        assert m.total_in == m.total_out + m.discarded
        if self.c.check_internals:
            memory = cocotb.top.g_bank.u_storage.g_shell.u_backend.g_inferred.memory
            for n, expected in enumerate(m.memory):
                assert str(memory[n].value).lower() == expected, f'Final raw word {n}'
