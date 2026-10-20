"""Mandatory offset/lane/route crosses and elastic-stream lifecycle coverage."""

from collections import Counter, defaultdict
from mosaic_uvm.components import CoverageCollector


def pattern_class(mask, count):
    if mask == 0:
        return 'empty'
    if mask == (1 << count) - 1:
        return 'full'
    population = mask.bit_count()
    if population == 1:
        return 'single'
    base = (1 << population) - 1
    if mask == base:
        return 'first'
    if mask == base << (count - population):
        return 'final'
    if mask >> ((mask & -mask).bit_length() - 1) == base:
        return 'middle'
    return 'sparse'


def patterns(count):
    maximum = (1 << count) - 1
    values = {0, maximum, 1, 1 << (count - 1), (1 << max(1, count // 2)) - 1,
              maximum ^ ((1 << max(1, count // 2)) - 1), sum(1 << lane for lane in range(0, count, 2))}
    if count >= 4:
        values.add(3 << 1)
    return tuple(sorted(values))


def output_class(masks):
    low, high, spill = masks
    if low and high:
        return 'split'
    if low:
        return 'low'
    if high:
        return 'high'
    return 'spill_only' if spill else 'empty'


class AlignerCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.bins = defaultdict(set)
        self.transitions = Counter()
        self.checks = Counter()
        self.totals = {}
        self.peak = self.peak_run = self.stall = self.stall_run = 0
        self.random_transactions = 0

    def sample(self, observation, event, model):
        p, config = observation.ports, self.config
        self.checks[observation.stage] += 1
        if p['o_valid'] == '1':
            self.bins['last_stall'].add((int(p['o_last']), int(p['i_ready'] == '0')))
        if event['reset']:
            self.bins['reset_occupancy'].add(int(event['occupancy']))
        if event['flush']:
            self.bins['flush_occupancy'].add(int(event['occupancy']))
            if event['occupancy']:
                self.bins['flush_context'].add('replacing' if p['i_ready'] == '1' and p['i_valid'] == '1' else 'stalled')
            else:
                self.bins['flush_context'].add('idle')
        if not event['rising']:
            return
        if observation.item.get_name() == 'ignored_idle_controls':
            self.bins['ignored_controls'].update(set(p['i_offset']) & {'x', 'z'})
        self.random_transactions += observation.item.random
        if p['i_rstb'] == '1' and p['i_flush'] == '0':
            if p['o_config_error'] == '1':
                if int(p['i_offset'], 2) >= config.word_bytes:
                    self.bins['illegal_offsets'].add(int(p['i_offset'], 2))
                if int(p['i_shift_high']) not in config.directions:
                    self.bins['illegal_directions'].add(int(p['i_shift_high']))
            self.bins['occupancy'].add('full' if event['occupancy'] else 'empty')
            if event['occupancy'] and not event['consumed']:
                self.bins['occupancy'].add('stalled')
            if event['consumed']:
                self.bins['occupancy'].add('consumed')
            if event['accepted'] and event['consumed']:
                self.bins['occupancy'].add('replaced')
            self.peak_run = self.peak_run + 1 if event['accepted'] and event['consumed'] else 0
            self.peak = max(self.peak, self.peak_run)
            self.stall_run = self.stall_run + 1 if p['o_valid'] == '1' and p['i_ready'] == '0' else 0
            self.stall = max(self.stall, self.stall_run)
        if not event['accepted']:
            return
        frame, routes = event['frame']
        direction, offset = int(p['i_shift_high']), int(p['i_offset'], 2)
        mask = int(p['i_strb_hi'] + p['i_strb_lo'], 2)
        masks = tuple(int(frame[name], 2) for name in ('o_strb_lo', 'o_strb_hi', 'o_spill_strb'))
        self.bins['direction_offset'].add((direction, offset))
        self.bins['direction_spill'].add((direction, bool(masks[2])))
        self.bins['direction_class'].add((direction, output_class(masks)))
        self.bins['pattern_offset'].add((pattern_class(mask, 2 * config.word_bytes), offset))
        self.bins['unaligned_nonempty'].add((int(frame['o_unaligned']), bool(mask)))
        self.bins['metadata_last'].add(int(p['i_last']))
        for state in ('x', 'z'):
            if state in p['i_data_hi'] + p['i_data_lo']:
                self.bins['ignored_data'].add(state)
        for source, destination, lane in routes:
            self.bins['offset_source'].add((offset, source))
            self.bins['source_destination'].add((direction, source // config.word_bytes, destination))
            self.bins['destination_lane'].add((destination, lane))
            if destination == 2:
                self.bins['spill_lane'].add((direction, lane))
        if mask and mask & (mask - 1) == 0:
            self.bins['single_source'].add((direction, mask.bit_length() - 1))

    def report(self):
        config = self.config
        n = config.word_bytes
        expected = defaultdict(set)
        for direction in config.directions:
            for offset in range(n):
                expected['direction_offset'].add((direction, offset))
                for source in range(2 * n):
                    expected['offset_source'].add((offset, source))
                    position = source + (offset if direction else -offset)
                    destination = 2 if position < 0 or position >= 2 * n else position // n
                    expected['source_destination'].add((direction, source // n, destination))
                    if destination == 2:
                        lane = n + position if position < 0 else position - 2 * n
                        expected['spill_lane'].add((direction, lane))
                for mask in patterns(2 * n):
                    expected['pattern_offset'].add((pattern_class(mask, 2 * n), offset))
                    counts = [0, 0, 0]
                    for source in range(2 * n):
                        if mask & (1 << source):
                            position = source + (offset if direction else -offset)
                            counts[2 if position < 0 or position >= 2 * n else position // n] += 1
                    expected['direction_class'].add((direction, output_class(counts)))
            expected['single_source'].update((direction, source) for source in range(2 * n))
            expected['direction_spill'].add((direction, False))
            if n > 1:
                expected['direction_spill'].add((direction, True))
                expected['direction_class'].add((direction, 'spill_only'))
        expected['destination_lane'].update((destination, lane) for destination in (0, 1) for lane in range(n))
        for direction, lane in expected['spill_lane']:
            expected['destination_lane'].add((2, lane))
        expected['unaligned_nonempty'] = {(0, False), (0, True)} | ({(1, True)} if n > 1 else set())
        expected['last_stall'] = {(last, stalled) for last in (0, 1) for stalled in (0, 1)}
        expected['ignored_data'] = {'x', 'z'}
        expected['ignored_controls'] = {'x', 'z'}
        expected['metadata_last'] = {0, 1}
        expected['illegal_offsets'] = set(range(n, 1 << config.offset_width))
        expected['illegal_directions'] = set((0, 1)) - set(config.directions)
        expected['reset_occupancy'] = {0, 1} if config.registered else {0}
        expected['flush_occupancy'] = {0, 1} if config.registered else {0}
        if config.registered:
            expected['occupancy'] = {'empty', 'full', 'stalled', 'consumed', 'replaced'}
            expected['flush_context'] = {'idle', 'stalled', 'replacing'}
        goals = {name: values <= self.bins[name] for name, values in expected.items()}
        goals.update(peak_throughput=self.peak >= 8, prolonged_backpressure=self.stall >= 32,
                     randomized=self.random_transactions >= config.random_cycles,
                     transaction_conservation=self.totals.get('accepted', 0) == self.totals.get('consumed', 0) + self.totals.get('cancelled', 0),
                     three_phase_checks=self.checks['pre'] == self.checks['post'] == self.checks['held'] and self.checks['post'] > 0)
        return dict(status='PASS' if all(goals.values()) else 'FAIL', parameters=config.parameters, seed=config.seed,
                    goals=goals, missing={name: sorted(values - self.bins[name], key=repr) for name, values in expected.items() if values - self.bins[name]},
                    bins={name: sorted(values, key=repr) for name, values in self.bins.items()},
                    checked_observations=dict(self.checks), random_transactions=self.random_transactions,
                    transactions=self.totals, maximum_peak_run=self.peak, maximum_stall=self.stall,
                    structural_assertions='PASS' if config.check_internals else 'NOT_RUN', waveform_transitions=dict(self.transitions),
                    waivers=dict(disabled_directions=sorted(set((0, 1))-set(config.directions)),
                                 spill='No legal nonzero offset' if n == 1 else 'Low spill lane 0 and high spill final lane are unreachable',
                                 registered_lifecycle='applicable' if config.registered else 'Combinational profile has no occupancy',
                                 strobe_classes=sorted({'empty','full','single','first','middle','final','sparse'} - {pattern_class(mask,2*n) for mask in patterns(2*n)})))
