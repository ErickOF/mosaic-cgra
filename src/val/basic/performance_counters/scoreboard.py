"""Check all architectural state, readback, ownership boundaries and hold activity."""

from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from performance_counters.model import PerformanceCountersModel, fields, pack, protocol_violation
from performance_counters.transaction import Activity, INPUTS, OUTPUTS


class PerformanceCountersScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.model = PerformanceCountersModel(self.config)
        self.previous_shadow = None

    def write(self, observation):
        if isinstance(observation, Activity):
            assert not observation.quiet, f'Quiet-waveform assertion failed: {observation.name}'
            self.coverage.transitions[observation.name] += 1
            return
        config, model = self.config, self.model
        ports, item, stage = observation.ports, observation.item, observation.stage
        for name in INPUTS:
            assert ports[name] == item.ports[name], f'Stimulus was coerced: {name}'
        violation = protocol_violation(config, ports)
        if violation:
            # Verify explicitly specified invalid-index/unknown-selector outputs
            # before reporting the live interface assertion that rejects them.
            if model.initialized and violation in ('i_event_select', 'i_read_index_unknown', 'i_read_index_range', 'i_read_snapshot'):
                expected = model.outputs(ports)
                names = ('o_config_error',) if violation == 'i_event_select' else ('o_read_data', 'o_read_overflow', 'o_read_valid')
                for name in names:
                    assert ports[name] == expected[name], f'Invalid-input assertion failed: {name}'
            assert False, f'Protocol assertion failed: {violation}'

        capture = False
        if stage == 'pre' and config.asynchronous and ports['i_rstb'] == '0':
            model.reset(ports)
            if not item.edge:
                self.coverage.reset_pulses += 1
        if stage == 'post' and item.edge:
            self.coverage.random_transactions += int(item.random)
            if ports['i_rstb'] == '0':
                model.reset(ports)
                self.coverage.resets += 1
            else:
                assert model.initialized, 'A reset edge is required before transactions'
                self.coverage.boundaries.update(model.configuration_changes(ports))
                records = model.step(ports)
                self.coverage.record(records, ports)
                capture = config.snapshot and ports['i_snapshot'] == '1'
        if stage == 'pre' and not item.edge and ports['i_rstb'] == '0' and not config.asynchronous:
            self.coverage.reset_pulses += 1
        if model.initialized:
            expected = model.outputs(ports)
            for name in OUTPUTS:
                assert ports[name] == expected[name], f'Counter-bank assertion failed: {name}: {ports[name]} != {expected[name]} ({item.get_name()}, {stage})'
            if config.check_internals:
                assert observation.internals['live_counts'] == pack(model.live, config.width), 'Live-state assertion failed'
                if model.snapshot_valid:
                    assert observation.internals['snapshot_counts'] == pack(model.shadow, config.width), 'Coherent-snapshot assertion failed'
                    assert observation.internals['snapshot_overflow'] == pack(model.shadow_overflow, 1), 'Snapshot-overflow assertion failed'
                self.check_isolation(observation)
            self.coverage.observe(observation, model)
        if config.check_internals:
            shadow = tuple(observation.internals[name] for name in ('snapshot_counts', 'snapshot_overflow'))
            if self.previous_shadow is not None and not capture:
                assert shadow == self.previous_shadow, 'Unreset shadow-storage hold assertion failed'
            self.previous_shadow = shadow
        self.coverage.observations[stage] += 1

    def check_isolation(self, observation):
        config, ports, model = self.config, observation.ports, self.model
        selections = fields(ports['i_event_select'], config.event_address_width)
        increments = fields(ports['i_event_increment'], config.increment_width)
        for c, selection in enumerate(selections):
            eligible = (ports['i_rstb'] == '1' and ports['i_global_enable'] == '1'
                and ports['i_counter_enable'][-c-1] == '1' and ports['i_freeze'] == '0'
                and ports['i_clear'][-c-1] == '0' and model.configuration_error(ports, c) == '0')
            amount = 0
            if eligible:
                e = int(selection, 2)
                if ports['i_event_valid'][-e-1] == '1':
                    amount = int(increments[e], 2)
            enabled = amount > 0 and not (config.saturate and model.live[c] == config.maximum)
            count, increment = (model.live[c], amount) if enabled else (0, 0)
            for name, expected in (('isolated_count', count), ('isolated_increment', increment), ('wide_sum', count + increment)):
                assert int(observation.internals[f'{name}:{c}'], 2) == expected, f'Operand-isolation assertion failed: {name}:{c}'
