"""Directed event/ownership boundaries, safe idle X/Z and constrained random traffic."""

from itertools import product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from performance_counters.model import fields, pack
from performance_counters.transaction import INPUTS, PerformanceCountersItem


class PerformanceCountersSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('performance_counters_sequence')
        self.config = config
        self.rng = random.Random(config.seed)
        self.ports = {name: '0'*config.widths[name] for name in INPUTS}
        self.all_counters = (1 << config.counters) - 1
        self.all_events = (1 << config.events) - 1

    async def send(self, label, *, edge=True, random=False, **changes):
        for name, value in changes.items():
            self.ports[name] = bits(value, self.config.widths[name])
        item = PerformanceCountersItem(label, self.ports, edge=edge, random=random)
        await self.start_item(item)
        await self.finish_item(item)
        return item

    def increments(self, value):
        return pack([value]*self.config.events, self.config.increment_width)

    async def reset(self):
        await self.send('reset_priority', i_rstb=0, i_global_enable=1, i_counter_enable=self.all_counters,
            i_freeze=0, i_clear=self.all_counters, i_event_select=0, i_event_valid=self.all_events,
            i_event_increment=self.increments(1), i_threshold_enable=0, i_threshold_value=0,
            i_snapshot=int(self.config.snapshot), i_read_enable=0, i_read_index=0, i_read_snapshot=0)
        await self.send('release', edge=False, i_rstb=1, i_clear=0, i_snapshot=0)

    async def clear_configure(self, selections=None, threshold=None):
        config = self.config
        await self.send('clear_configuration', i_clear=self.all_counters, i_global_enable=1,
            i_counter_enable=self.all_counters, i_freeze=0, i_event_select=pack(selections or [0]*config.counters, config.event_address_width),
            i_threshold_enable=self.all_counters if threshold is not None else 0,
            i_threshold_value=pack([threshold or 0]*config.counters, config.width),
            i_event_valid=self.all_events, i_event_increment=self.increments(1), i_snapshot=0,
            i_read_enable=0, i_read_snapshot=0, i_read_index=0)
        await self.send('clear_release', edge=False, i_clear=0)

    async def read_all(self):
        for snapshot in range(2 if self.config.snapshot else 1):
            for c in range(self.config.counters):
                await self.send('indexed_read', edge=False, i_read_enable=1, i_read_snapshot=snapshot, i_read_index=c)
        await self.send('read_disable', edge=False, i_read_enable=0, i_read_snapshot=0)

    async def assignment_and_gating(self):
        config = self.config
        await self.read_all()  # Every snapshot read is invalid before first capture.
        for offset in range(config.events):
            await self.clear_configure([(c + offset) % config.events for c in range(config.counters)])
            for amount in sorted({0, 1, config.increment_maximum//2, config.increment_maximum}):
                increments = [(amount + e) & config.increment_maximum for e in range(config.events)]
                await self.send('distinct_packed_events', i_event_increment=pack(increments, config.increment_width))
            await self.send('back_to_back', i_event_increment=self.increments(1))
            await self.send('back_to_back')
            await self.read_all()
        for e in range(config.events):
            await self.clear_configure([e]*config.counters)
            for amount in sorted({0, 1, config.increment_maximum//2, config.increment_maximum}):
                await self.send('shared_event', i_event_increment=self.increments(amount))
            await self.send('independent_clear', i_clear=1, i_event_increment=self.increments(1))
            await self.send('independent_enable', i_clear=0, i_counter_enable=self.all_counters ^ 1)
        # Isolate every increment bit, including those above counter width.
        # Other high bits cannot hide a missing contributor to sticky overflow.
        for bit in range(config.increment_width):
            await self.clear_configure()
            await self.send('one_hot_increment', i_event_increment=self.increments(1 << bit))
            await self.read_all()
        await self.clear_configure()
        for global_enable, enabled, freeze in product((0, 1), repeat=3):
            await self.send('enable_freeze_cross', i_global_enable=global_enable,
                i_counter_enable=self.all_counters*enabled, i_freeze=freeze, i_event_increment=self.increments(1))
        await self.send('freeze_clear_priority', i_global_enable=1, i_counter_enable=self.all_counters,
            i_freeze=1, i_clear=self.all_counters)
        await self.clear_configure()

    async def fill_to(self, target):
        maximum = self.config.increment_maximum
        whole, rest = divmod(target, maximum)
        for _ in range(whole):
            await self.send('boundary_setup', i_event_increment=self.increments(maximum))
        if rest:
            await self.send('boundary_remainder', i_event_increment=self.increments(rest))

    async def arithmetic_and_thresholds(self):
        config = self.config
        if config.boundary_feasible:
            threshold = config.maximum if config.threshold else None
            await self.clear_configure(threshold=threshold)
            await self.fill_to(config.maximum - 1)
            await self.send('exact_maximum', i_event_increment=self.increments(1))
            await self.send('overflow_after_exact_maximum')
            await self.send('sticky_overflow', i_event_increment=self.increments(config.increment_maximum))
            if config.snapshot:
                await self.send('capture_overflow', i_snapshot=1)
                await self.send('clear_preserves_snapshot', i_clear=1, i_snapshot=0)
                await self.read_all()
            if config.threshold and not config.saturate and config.increment_width > 1:
                await self.clear_configure(threshold=config.maximum)
                await self.fill_to(config.maximum - 1)
                await self.send('wrap_across_threshold', i_event_increment=self.increments(2))
                await self.send('threshold_pulse_clears', i_event_valid=0)
        if config.threshold:
            threshold = min(3, config.maximum)
            await self.clear_configure(threshold=threshold)
            await self.send('below_threshold_zero', i_event_increment=self.increments(0))
            for _ in range(threshold + 2):
                await self.send('unit_threshold_crossing', i_event_increment=self.increments(1))
            await self.send('threshold_no_event', i_event_valid=0)
            await self.send('reserved_zero_threshold', i_clear=self.all_counters, i_threshold_value=0)
            for freeze in (0, 1):
                await self.send('threshold_error_blocks_update', i_clear=0, i_event_valid=self.all_events, i_freeze=freeze)
        if config.events < 1 << config.event_address_width:
            await self.clear_configure([config.events]*config.counters)
            for freeze in (0, 1):
                await self.send('invalid_event_blocks_update', i_freeze=freeze)
        await self.clear_configure()

    async def snapshots_and_resets(self):
        config = self.config
        for snapshot, update, clear in product(range(2 if config.snapshot else 1), (0, 1), (0, 1)):
            await self.send('snapshot_update_clear_cross', i_snapshot=snapshot, i_event_valid=self.all_events*update,
                i_clear=self.all_counters*clear, i_event_increment=self.increments(1))
            await self.read_all()
        for _ in range(2):
            await self.send('live_before_reset', i_rstb=1, i_clear=0, i_event_valid=self.all_events, i_snapshot=int(config.snapshot))
            await self.send('between_edge_reset', edge=False, i_rstb=0)
            await self.send('pulse_release', edge=False, i_rstb=1, i_event_valid=0, i_snapshot=0)
            await self.read_all()
        await self.reset()
        await self.read_all()
        await self.clear_configure()

    async def ownership_and_idle_unknowns(self):
        config = self.config
        alternative = 1 if config.events == 1 else config.events - 1
        await self.send('clear_old_owner', i_clear=self.all_counters, i_counter_enable=0)
        await self.send('assign_cleared_disabled_owner', i_clear=0,
            i_event_select=pack([alternative]*config.counters, config.event_address_width))
        await self.clear_configure()
        for state in 'xz':
            await self.send('global_disabled_unknowns', i_global_enable=0, i_counter_enable=self.all_counters, i_clear=self.all_counters,
                i_event_select=state*config.widths['i_event_select'], i_event_valid=state*config.events,
                i_event_increment=state*config.widths['i_event_increment'], i_read_enable=0,
                i_read_index=state*config.counter_address_width, i_read_snapshot=state if config.snapshot else 0)
            await self.send('per_counter_disabled_unknowns', i_global_enable=1, i_counter_enable=0)
            # Restore configuration while disabled AND already clear; clear the
            # next owner before enabling, so idle X/Z never bypasses ownership.
            await self.clear_configure()
            await self.send('invalid_event_ignores_increment', i_event_valid=0,
                i_event_increment=state*config.widths['i_event_increment'])
            if config.events > 1:
                increments = [bits(1, config.increment_width)] + [state*config.increment_width]*(config.events-1)
                await self.send('unselected_events_ignored', i_event_valid=state*(config.events-1)+'1',
                    i_event_increment=''.join(reversed(increments)))
            await self.send('frozen_events_ignored', i_freeze=1, i_event_valid=state*config.events,
                i_event_increment=state*config.widths['i_event_increment'])
            await self.clear_configure()

    async def randomized(self):
        config, rng = self.config, self.rng
        for index in range(config.random_cycles):
            clear = rng.getrandbits(config.counters) if rng.randrange(5) == 0 else 0
            selections = [int(word, 2) for word in fields(self.ports['i_event_select'], config.event_address_width)]
            thresholds = [int(word, 2) for word in fields(self.ports['i_threshold_value'], config.width)]
            threshold_enable = int(self.ports['i_threshold_enable'], 2)
            for c in range(config.counters):
                if (clear >> c) & 1:
                    selections[c] = rng.randrange(1 << config.event_address_width)
                    if config.threshold:
                        thresholds[c] = rng.choice((0, 1, min(3, config.maximum), config.maximum, rng.getrandbits(config.width)))
                        threshold_enable = (threshold_enable & ~(1 << c)) | (rng.randrange(2) << c)
            increments = [rng.choice((0, 1, config.increment_maximum, rng.getrandbits(config.increment_width))) for _ in range(config.events)]
            await self.send(f'random:{index}', random=True, i_rstb=int(rng.randrange(97) != 0),
                i_global_enable=int(rng.randrange(5) != 0), i_counter_enable=rng.getrandbits(config.counters),
                i_freeze=int(rng.randrange(7) == 0), i_clear=clear,
                i_event_select=pack(selections, config.event_address_width), i_event_valid=rng.getrandbits(config.events),
                i_event_increment=pack(increments, config.increment_width), i_threshold_enable=threshold_enable,
                i_threshold_value=pack(thresholds, config.width), i_snapshot=int(config.snapshot and rng.randrange(5) == 0),
                i_read_enable=rng.randrange(2), i_read_snapshot=int(config.snapshot and rng.randrange(2) == 0),
                i_read_index=rng.randrange(config.counters))

    async def probe(self):
        config = self.config
        await self.clear_configure(threshold=1 if config.threshold else None)
        await self.send('probe_live_state', i_read_enable=1, i_read_index=0)
        field, state, bit = config.probe.split(':')
        if field == 'configuration_boundary':
            selection = int(self.ports['i_event_select'], 2) ^ 1
            await self.send('illegal_reassignment', i_event_select=selection, i_freeze=int(state))
        elif field == 'threshold_boundary':
            await self.send('illegal_threshold_change', i_threshold_enable=0, i_freeze=int(state))
        elif field == 'unsupported_snapshot':
            await self.send('unsupported_snapshot_control', **{state: 1})
        elif field == 'unsupported_threshold':
            await self.send('unsupported_threshold_control', **{state: 1})
        elif field == 'i_read_index_range':
            await self.send('out_of_range_read', i_read_index=config.counters)
        else:
            word = list(self.ports[field])
            word[len(word)-1-int(bit)] = state
            await self.send('unknown_consumed_input', **{field: ''.join(word)})
        assert False, 'Illegal stimulus did not trigger its live assertion'

    async def body(self):
        await self.reset()
        if self.config.probe:
            await self.probe()
            return
        await self.assignment_and_gating()
        await self.arithmetic_and_thresholds()
        await self.snapshots_and_resets()
        await self.ownership_and_idle_unknowns()
        await self.randomized()
