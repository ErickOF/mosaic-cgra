"""Check actual transfers, every public output and qualified storage writes."""
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from load_engine.model import LoadEngineModel, address, number
from load_engine.transaction import INPUTS, OUTPUTS


class LoadEngineScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = LoadEngineModel(self.c)
        self.initialized = False
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write

    def storage(self, obs, plan, metadata):
        c = self.c
        for key, raw in obs.storage.items():
            if key.startswith('gate:'):
                continue  # Combinational policy pins are checked independently below.
            kind, n = key[0], int(key[1:])
            if kind in ('a', 'p'):
                owned = next((e for e in self.model.pending if e['tag'] == n), None)
                expected = int(owned is not None) if kind == 'a' else int(
                    owned is not None and owned['response'] is not None)
                if self.initialized:
                    assert number(raw) == expected, f'{key}: ownership or response-present mismatch'
                continue
            capture = obs.item.edge and plan['run'] and (
                plan['request'] and n == self.model_tag if kind == 'm' else
                plan['response'] and not plan['rsp_error'] and n == plan['p']['i_mem_rsp_tag'])
            if not capture:
                assert raw == obs.item.pre.storage[key], f'Unqualified payload write: {key}'
            else:
                expected = metadata if kind == 'm' else (
                    (plan['p']['i_mem_rsp_error'] << c.DATA_WIDTH) |
                    (0 if plan['p']['i_mem_rsp_error'] else plan['p']['i_mem_rsp_data']))
                assert number(raw) == expected, f'Wrong payload capture: {key}'
            self.coverage.storage_checks += 1

    def write_gates(self, obs, plan):
        """Predict write policy from the independent ledger and public inputs."""
        c = self.c
        tag = plan['p']['i_mem_rsp_tag']
        selected = (1 << tag if plan['response'] and tag is not None
                    and tag < c.MAX_OUTSTANDING else 0)
        rejected = bool(plan['desc_error'])
        bad_response = bool(plan['rsp_error'])
        for label, enabled, suppressed in (
            ('descriptor', int(plan['config']), int(rejected)),
            ('response', selected, ((1 << c.MAX_OUTSTANDING) - 1) if bad_response else 0),
        ):
            values = {
                'i_write_enable': enabled,
                'i_suppress': suppressed,
                'o_write_enable': enabled & ~suppressed,
                'o_write_suppressed': enabled & suppressed,
            }
            for pin, expected in values.items():
                assert number(obs.storage[f'gate:{label}:{pin}']) == expected, (
                    f'Load-engine write gate {label}.{pin} violates the event contract')
            self.coverage.write_gate_states.add((label, bool(enabled), bool(suppressed)))
        if plan['response'] and not bad_response:
            self.coverage.response_write_tags.add(tag)
        if bad_response:
            self.coverage.suppressed_response_errors.add(plan['rsp_error'])
        self.coverage.write_gate_checks += 1

    def write(self, obs):
        item, p, stage = obs.item, obs.ports, obs.stage
        for name in INPUTS:
            expected = item.ports[name]
            assert (number(p[name]) == expected if isinstance(expected, int) else
                    p[name].lower() == expected.lower()), f'Stimulus changed: {name}'
        if stage == 'pre':
            if item.release:
                self.model.fault = False
            if item.fault:
                self.model.fault = True
            if self.c.ASYNC_RESET and number(p['i_rstb']) == 0:
                self.model.reset()
                self.initialized = True
        if stage == 'edge':
            assert all(p[n] == item.pre.ports[n] for n in OUTPUTS), 'Not a pre-NBA observation'
        if stage == 'post':
            _, plan = self.model.evaluate(item.pre.ports)
            self.model_tag = self.model.next_tag
            metadata = 0
            if plan['request']:
                m = address(self.c, self.model.descriptor, self.model.cursor)
                metadata = (m['keep'] << self.c.CHANNEL_ID_WIDTH) | m['channel_id']
                metadata = (metadata << self.c.CONTEXT_ID_WIDTH) | m['context_id']
                for name in ('first', 'last', 'row_first', 'row_last', 'end_of_stream'):
                    metadata = (metadata << 1) | m[name]
            events, plan = self.model.step(item.pre.ports, item.edge)
            if item.edge and number(p['i_rstb']) == 0:
                self.initialized = True
            if self.c.check_internals:
                self.storage(obs, plan, metadata)
            self.coverage.record(events, obs, self.model, plan)
        if self.initialized:
            expected, current_plan = self.model.evaluate(p)
            if self.c.check_internals and stage != 'edge':
                self.write_gates(obs, current_plan)
            for name, value in expected.items():
                assert number(p[name]) == value, f'{name}: {p[name]} != {value} ({item.get_name()}, {stage})'
        self.coverage.observations[stage] += 1

    def check_phase(self):
        assert self.initialized and not self.model.pending and not self.model.active
        assert self.model.accepted == self.model.delivered + self.model.discarded
