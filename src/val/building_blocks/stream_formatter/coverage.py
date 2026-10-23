"""Checked mode, geometry, lane, error, latency and recovery coverage."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector
from stream_formatter.model import number


class StreamFormatterCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.events = Counter()
        self.observations = Counter()
        self.crosses = {}
        self.eligible = set()
        self.lane_masks = set()
        self.modes = set()
        self.lengths = set()
        self.fault_modes = set()
        self.config_errors = set()
        self.error_positions = set()
        self.flush_states = set()
        self.reset_states = set()
        self.class_counts = Counter()
        self.random_transactions = self.storage_checks = self.isolation_checks = 0
        self.accounting = {}

    def cross(self, name, *values):
        self.crosses.setdefault(name, Counter())[str(tuple(values))] += 1

    def reset_observed(self, model):
        state = 'buffered' if model.pending is not None else 'active' if model.active else 'idle'
        self.reset_states.add(state)
        self.cross('reset_state', self.config.ASYNC_RESET, state)

    def record(self, obs, model, q):
        self.random_transactions += int(obs.item.random)
        self.accounting = dict(accepted=model.total_in, emitted=model.total_out,
                               discarded=model.discarded, outstanding=int(model.pending is not None))
        if not obs.item.edge or not q['run']:
            return
        c, p = self.config, q['p']
        d = q['descriptor']
        for key in ('start', 'input', 'output', 'finish', 'abort'):
            self.events[key] += int(q[key])
        if q['start']:
            self.modes.add(p['i_mode'])
            self.eligible.add(p['i_lane_enable'])
            self.lengths.add(p['i_frame_beats'])
            self.cross('width_lanes_profile', c.DATA_WIDTH, c.NUM_LANES, c.REGISTER_OUTPUTS)
            geometry = 'one' if p['i_row_beats'] == 1 else 'full' if p['i_row_beats'] == p['i_frame_beats'] else 'partial' if p['i_frame_beats'] % p['i_row_beats'] else 'multiple'
            length = 'one' if p['i_frame_beats'] == 1 else 'maximum' if p['i_frame_beats'] == (1 << c.COUNT_WIDTH) - 1 else 'other'
            self.cross('frame_row_geometry', length, geometry)
            self.cross('identity_mode', p['i_datatype'], p['i_channel_id'], p['i_context_id'], p['i_mode'])
            self.events['partial_row'] += int(geometry == 'partial')
        if q['error']:
            self.config_errors.add(q['error'])
            self.cross('config_error_clear', q['error'], p['i_error_clear'])
        if q['normal'] and p['i_error_clear'] == 1 and not q['active'] and not q['occupancy']:
            self.events['clear'] += 1
        if q['input']:
            self.lane_masks.add(p['i_lane_mask'])
            self.class_counts.update(q['faults'])
            self.fault_modes.update((d['i_mode'], code) for code in q['faults'])
            b = q['beat']
            self.cross('mode_mismatch', d['i_mode'], tuple(sorted(q['faults'])))
            self.cross('position_markers', 'first' if b['o_first'] else 'final' if b['o_last'] else 'middle',
                       b['o_first'], b['o_last'], b['o_row_first'], b['o_row_last'])
            self.cross('eligibility_input_effective', d['i_lane_enable'], p['i_lane_mask'], b['o_lane_mask'])
            density = 'empty' if b['o_keep'] == 0 else 'full' if b['o_keep'] == (1 << (c.DATA_WIDTH // 8)) - 1 else 'partial'
            self.cross('keep_density_effective_lanes', density, b['o_lane_mask'].bit_count())
            self.events['filtered'] += int(p['i_lane_mask'] is not None and b['o_lane_mask'] != p['i_lane_mask'])
            self.events['multiple_faults'] += int(len(q['faults']) > 1)
            if p['i_error'] == 1:
                position = 'first' if q['index'] == 0 else 'last' if q['index'] + 1 == d['i_frame_beats'] else 'middle'
                self.error_positions.add(position)
                self.cross('input_error_position', position, b['o_stream_error'])
            if q['input'] and q['output']:
                self.events['replace'] += 1
                self.cross('replace_final', b['o_last'])
        starving = bool(q['normal'] and q['active'] and d and q['index'] < d['i_frame_beats'] and p['i_valid'] == 0)
        stalled = obs.item.pre.ports['o_valid'] == '1' and p['i_ready'] == 0
        self.cross('starvation_backpressure', starving, stalled)
        self.events['starvation'] += int(starving)
        self.events['stall'] += int(stalled)
        if obs.item.random:
            self.events['random_starvation'] += int(starving)
            self.events['random_stall'] += int(stalled)
            self.events['random_fault'] += int(q['input'] and bool(q['faults']))
            self.events['random_replace'] += int(q['input'] and q['output'])
        if q['finish']:
            error = bool(model.events['o_completed_with_error'])
            self.events['error_completion' if error else 'clean_completion'] += 1
            self.events['final_error_included'] += int(error and not obs.item.pre.ports['o_input_error_seen'] == '1' and q['output_error'])
            self.cross('completion_errors', bool(model.format_seen), bool(model.input_seen), error)
        if q['flush']:
            state = 'final_buffered' if q['occupancy'] and obs.item.pre.ports['o_last'] == '0' and model.c.REGISTER_OUTPUTS and q['index'] == d['i_frame_beats'] else 'buffered' if q['occupancy'] else 'active' if q['active'] else 'idle'
            # Public payload is clamped during flush; input count identifies final storage.
            self.flush_states.add(state)
            self.cross('flush_occupancy', state, q['occupancy'])

    def report(self):
        c = self.config
        maximum = (1 << c.COUNT_WIDTH) - 1
        required_lengths = {1, min(2, maximum), min(7, maximum), maximum}
        required_modes = {(0, code) for code in range(1, 4)} | {(1, code) for code in range(1, 12)}
        goals = {name: self.events[name] > 0 for name in (
            'start', 'input', 'output', 'finish', 'abort', 'clear', 'stall', 'starvation',
            'multiple_faults', 'clean_completion', 'error_completion', 'random_stall',
            'random_starvation', 'random_fault', 'final_error_included')}
        goals.update(both_modes=self.modes == {0, 1},
                     every_eligibility=self.eligible == set(range(1, 1 << c.NUM_LANES)),
                     every_input_mask=set(range(1 << c.NUM_LANES)) <= self.lane_masks,
                     mode_fault_classes=required_modes <= self.fault_modes,
                     frame_lengths=required_lengths <= self.lengths,
                     all_config_errors=self.config_errors == set(range(1, 6)) if maximum > 1 else self.config_errors == {1, 2, 3, 5},
                     input_error_positions=({'first'} if maximum == 1 else {'first', 'middle', 'last'}) <= self.error_positions,
                     partial_rows=maximum < 3 or self.events['partial_row'] > 0,
                     flush_states={'idle', 'active'} <= self.flush_states,
                     reset_states={'idle', 'active'} <= self.reset_states,
                     ownership_accounting=self.accounting.get('outstanding') == 0 and
                        self.accounting.get('accepted', -1) == self.accounting.get('emitted', -2) + self.accounting.get('discarded', -3),
                     random_campaign=self.random_transactions == c.random_cycles,
                     actual_edges=self.observations['edge'] > 0,
                     storage_isolation=not c.check_internals or min(self.storage_checks, self.isolation_checks) > 0)
        if c.REGISTER_OUTPUTS:
            goals['registered_flush_final'] = 'final_buffered' in self.flush_states
            goals['registered_reset_buffered'] = 'buffered' in self.reset_states
            if maximum > 1:
                goals['consume_replace'] = self.events['replace'] > 0 and self.events['random_replace'] > 0
        if c.NUM_LANES > 1:
            goals['eligibility_filter'] = self.events['filtered'] > 0
        return dict(status='PASS' if all(goals.values()) else 'FAIL', framework='PyUVM',
                    parameters=c.parameters, seed=c.seed, goals=goals, events=dict(self.events),
                    accounting=self.accounting, random_transactions=self.random_transactions,
                    fault_counts=dict(self.class_counts), config_errors=sorted(self.config_errors),
                    observations=dict(self.observations), lengths=sorted(self.lengths),
                    mode_fault_classes=sorted(self.fault_modes), reset_states=sorted(self.reset_states),
                    flush_states=sorted(self.flush_states), storage_checks=self.storage_checks,
                    isolation_checks=self.isolation_checks,
                    crosses={n: dict(v) for n, v in self.crosses.items()},
                    internal_storage_assertions='PASS' if c.check_internals else 'NOT_RUN',
                    external_checks=dict.fromkeys(('lint', 'formal', 'cdc', 'rdc', 'dft', 'vc_lp',
                        'technology_synthesis', 'physical_timing', 'physical_power'), 'NOT_RUN'))
