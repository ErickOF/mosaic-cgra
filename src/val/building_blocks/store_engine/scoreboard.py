"""Check atomic pairing, ordered ownership, payload stability, gating and counters."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from store_engine.model import StoreEngineModel, number
from store_engine.transaction import INPUTS, OUTPUTS, REQUEST


class StoreEngineScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = StoreEngineModel(self.c)
        self.initialized = False
        self.counts = [0] * 20
        self.peak = 0
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write

    def counter_step(self, out, plan, item):
        p = plan['p']
        if p['i_rstb'] == 0 and (item.edge or self.c.ASYNC_RESET):
            self.counts = [0] * 20
            self.peak = 0
        elif item.edge and plan['run']:
            pending = self.model.pending
            bits = [plan['start'], plan['finish'], plan['fail'], plan['stream'], plan['stream'],
                    plan['request'], plan['response'], plan['retire'],
                    plan['issuing'] and p['i_stream_valid'] == 0,
                    out['o_mem_req_valid'] and p['i_mem_req_ready'] == 0,
                    bool(pending and pending[0]['response'] is None),
                    len(pending) == self.c.MAX_OUTSTANDING,
                    plan['response'] and not plan['rsp_error'] and p['i_mem_rsp_error'],
                    *(plan['bad_stream'] and plan['stream_error'] == 16 + n for n in range(6)),
                    bool(plan['rsp_error'])]
            keep = item.pre.ports['i_stream_keep'].count('1')
            for n, event in enumerate(bits):
                if event:
                    self.counts[n] = min(255, self.counts[n] + (keep if n == 4 else 1))
            self.peak = max(self.peak, len(pending))
            self.coverage.saturated |= 255 in self.counts

    def storage(self, obs):
        c = self.c
        if obs.stage == 'post':
            for n in range(c.MAX_OUTSTANDING):
                for kind in ('a', 'p', 'l', 'e'):
                    key = f'{kind}{n}'
                    old, new = obs.item.pre.storage, obs.storage
                    if old[key + ':i_rstb'] == '0' and (obs.item.edge or c.ASYNC_RESET):
                        expected = '0'
                    elif obs.item.edge and old[key + ':i_enable'] == '1':
                        expected = old[key + ':i_d']
                    else:
                        expected = old[key]
                    assert new[key] == expected, f'Completion DFF capture/hold: {key}'
                    self.coverage.storage_checks += 1
        for n in range(c.MAX_OUTSTANDING):
            entry = next((e for e in self.model.pending if e['tag'] == n), None)
            assert number(obs.storage[f'a{n}']) == int(entry is not None), 'Allocation mismatch'
            assert number(obs.storage[f'p{n}']) == int(entry is not None and
                                                      entry['response'] is not None), 'Presence mismatch'
        _, plan = self.model.evaluate(obs.ports)
        tag = plan['p']['i_mem_rsp_tag']
        decoded = 1 << tag if plan['response'] and tag is not None and tag < c.MAX_OUTSTANDING else 0
        for label, enable, suppress in (
            ('descriptor', int(plan['config']), int(bool(plan['desc_error']))),
            ('response', decoded, (1 << c.MAX_OUTSTANDING) - 1 if plan['rsp_error'] else 0),
        ):
            for pin, expected in (('i_write_enable', enable), ('i_suppress', suppress),
                                  ('o_write_enable', enable & ~suppress),
                                  ('o_write_suppressed', enable & suppress)):
                assert number(obs.storage[f'gate:{label}:{pin}']) == expected, 'Write gate mismatch'
        self.coverage.gating_checks += 1

    def write(self, obs):
        if self.c.probe:
            return  # Negative runs must terminate in the native data assertion.
        p, item, stage = obs.ports, obs.item, obs.stage
        for name in INPUTS:
            expected = item.ports[name]
            assert number(p[name]) == expected if isinstance(expected, int) else p[name] == expected.lower()
        if stage == 'pre':
            if item.release:
                self.model.fault = False
            if item.fault:
                self.model.fault = True
            if self.c.ASYNC_RESET and number(p['i_rstb']) == 0:
                self.coverage.reset_observed(self.model.active, self.model.error, len(self.model.pending))
                self.model.reset()
                self.counts = [0] * 20
                self.peak = 0
                self.initialized = True
        if stage == 'edge':
            assert all(p[name] == item.pre.ports[name] for name in OUTPUTS), 'Pre-NBA sampling'
        if stage == 'post':
            old_out, plan = self.model.evaluate(item.pre.ports)
            self.counter_step(old_out, plan, item)
            event, plan = self.model.step(item.pre.ports, item.edge)
            self.initialized |= item.edge and number(p['i_rstb']) == 0
            self.coverage.record(event, obs, self.model, plan)
        if self.initialized:
            expected, _ = self.model.evaluate(p)
            for name, value in expected.items():
                assert value is not None, 'Unknown enabled data in a legal write'
                assert number(p[name]) == value, (
                    f'{name}: {p[name]} != {value} ({item.get_name()}, {stage})')
            if self.c.check_internals and stage != 'edge':
                self.storage(obs)
            if self.c.hdl_assertions and stage != 'edge':
                packed = sum(value << (8 * n) for n, value in enumerate(self.counts))
                assert number(obs.storage['counter:counts']) == packed, 'Optional counters'
                assert number(obs.storage['counter:peak']) == self.peak, 'Peak occupancy'
                assert number(obs.storage['counter:disabled_counts']) == 0
                assert number(obs.storage['counter:disabled_peak']) == 0
                self.coverage.counter_checks += 1
            if stage == 'post' and item.edge:
                pre = item.pre.ports
                if (pre['o_mem_req_valid'] == '1' and pre['i_mem_req_ready'] != '1'
                        and p['o_error'] == '0' and p['i_rstb'] == '1'):
                    assert all(pre[name] == p[name] for name in REQUEST), 'Stalled request changed'
        self.coverage.observations[stage] += 1

    def check_phase(self):
        assert self.initialized and not self.model.active and not self.model.pending
        assert self.model.accepted == self.model.retired + self.model.discarded
        assert self.model.accepted == self.model.legal_beats
