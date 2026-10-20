"""Reachable conversion crosses and elastic-stream lifecycle coverage."""

from collections import Counter, defaultdict
from itertools import product
from mosaic_uvm.components import CoverageCollector
from packer.model import boundary_values, illegal_causes


def mask_class(mask, count):
    return 'empty' if mask == 0 else 'full' if mask == (1 << count) - 1 else 'sparse'


class PackerCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.bins = defaultdict(set)
        self.checks, self.transitions = Counter(), Counter()
        self.cancellations, self.pulses = set(), set()
        self.random_transactions = self.stall = self.peak = self.max_stall = self.max_peak = 0
        self.totals = dict(accepted=0, consumed=0, cancelled=0)

    def record(self, item, event, model):
        ports, pre, config = item.ports, item.pre.ports, self.config
        self.random_transactions += int(item.random)
        self.totals = dict(accepted=model.accepted, consumed=model.consumed, cancelled=model.cancelled)
        if event['reset'] or event['flush']:
            self.cancellations.add(('reset' if event['reset'] else 'flush', event['occupancy']))
            self.stall = self.peak = 0
            return
        mode = tuple(int(ports[name]) for name in ('i_signed', 'i_saturate', 'i_reverse')) if ports['i_valid'] == '1' else None
        if pre['o_config_error'] == '1':
            self.bins['illegal_modes'].add(mode)
            self.bins['error_causes'].update(illegal_causes(config, mode))
            if pre['o_valid'] == '1':
                self.bins['old_result_during_error'].add('drained' if event['consumed'] else 'stalled')
        if pre['o_valid'] == '1':
            stalled = ports['i_ready'] == '0'
            self.bins['last_backpressure'].add((int(pre['o_last']), int(stalled)))
            self.stall = self.stall + 1 if stalled else 0
            self.max_stall = max(self.max_stall, self.stall)
        else:
            self.stall = 0
        self.peak = self.peak + 1 if event['accepted'] and event['consumed'] else 0
        self.max_peak = max(self.max_peak, self.peak)
        if config.registered:
            self.bins['lifecycle'].add('empty' if event['occupancy'] == 0 else 'occupied')
            if event['occupancy'] and not event['consumed']:
                self.bins['lifecycle'].add('stalled')
            if event['consumed']:
                self.bins['lifecycle'].add('replaced' if event['accepted'] else 'drained')
            if not event['occupancy'] and event['accepted']:
                self.bins['lifecycle'].add('captured')
        if event['accepted']:
            result, routes = event['frame']
            self.bins['modes'].add(mode)
            self.bins['masks'].add(mask_class(int(ports['i_lane_valid'], 2), config.elements))
            self.bins['metadata'].add((int(ports['i_last']), int(ports['i_user'], 2) == 0))
            for lane, (valid, overflow, saturated) in enumerate(zip(reversed(result['o_lane_valid']), reversed(result['o_overflow']), reversed(result['o_saturated']))):
                self.bins['lane_status'].add((lane, int(valid), int(overflow)))
                self.bins['lane_saturation'].add((lane, int(saturated)))
            for route in routes:
                self.bins['routes'].add((mode[2], route['source'], route['destination']))
                self.bins['range'].add((mode[0], route['value_class']))
                self.bins['boundaries'].add((mode[0], route['source'], route['raw']))
            if item.get_name() == 'invalid_lane_unknown':
                self.bins['invalid_unknown'].update(state for state in ports['i_data'] if state in 'xz')

    def report(self):
        config = self.config
        expected = dict(
            modes=set(config.modes),
            illegal_modes=set(product((0, 1), repeat=3)) - set(config.modes),
            routes={(reverse, lane, config.elements - 1 - lane if reverse else lane)
                    for reverse in range(1 + config.reverse) for lane in range(config.elements)},
            lane_status={(lane, valid, overflow) for lane in range(config.elements)
                         for valid, overflow in (((0, 0), (1, 0), (1, 1)) if config.narrowing else ((0, 0), (1, 0)))},
            lane_saturation=set(product(range(config.elements), range(1 + (config.narrowing and config.saturation)))),
            range={(signed, category) for signed in range(1 + config.signed)
                   for category in (('below', 'in_range', 'above') if signed and config.narrowing else
                                    ('in_range', 'above') if config.narrowing else ('in_range',))},
            boundaries={(signed, lane, raw) for signed in range(1 + config.signed) for lane in range(config.elements)
                        for raw in boundary_values(config, signed)},
            masks={'empty', 'full'} | ({'sparse'} if config.elements > 1 else set()),
            last_backpressure=set(product((0, 1), repeat=2)),
            metadata=set(product((0, 1), repeat=2)),
            invalid_unknown={'x', 'z'})
        expected['error_causes'] = {cause for mode in expected['illegal_modes'] for cause in illegal_causes(config, mode)}
        if config.registered:
            expected['lifecycle'] = {'empty', 'occupied', 'stalled', 'captured', 'replaced', 'drained'}
            if expected['illegal_modes']:
                expected['old_result_during_error'] = {'stalled', 'drained'}
        goals = {name: values <= self.bins[name] for name, values in expected.items()}
        goals.update(reset_flush_by_occupancy={(kind, occupancy) for kind in ('reset', 'flush')
                     for occupancy in range(1 + config.registered)} <= self.cancellations,
                     between_edge_pulses=self.pulses == {'reset', 'flush'},
                     long_backpressure=self.max_stall >= 64, peak_throughput=self.max_peak >= 16,
                     randomized_campaign=self.random_transactions == config.random_cycles,
                     beat_conservation=self.totals['accepted'] == self.totals['consumed'] + self.totals['cancelled'],
                     three_phase_checks=self.checks['pre'] == self.checks['post'] == self.checks['held'] and self.checks['pre'] > 0)
        return dict(status='PASS' if all(goals.values()) else 'FAIL', parameters=config.parameters, seed=config.seed,
                    random_transactions=self.random_transactions, goals=goals,
                    missing={name: sorted(values - self.bins[name], key=repr) for name, values in expected.items() if values - self.bins[name]},
                    bins={name: sorted(values, key=repr) for name, values in self.bins.items()},
                    transactions=self.totals, checked_observations=dict(self.checks), maximum_stall=self.max_stall,
                    maximum_peak_run=self.max_peak, reset_flush_bins=sorted(self.cancellations),
                    structural_assertions='PASS' if config.check_internals else 'NOT_RUN', waveform_transitions=dict(self.transitions),
                    waivers=dict(unsigned_below_minimum='Unsigned source values cannot be negative',
                                 overflow='Only narrowing profiles can overflow', saturation='Only enabled narrowing saturation can clamp',
                                 sparse_mask='Unreachable with one element' if config.elements == 1 else 'applicable',
                                 registered_lifecycle='applicable' if config.registered else 'Combinational profile has no occupancy'))
