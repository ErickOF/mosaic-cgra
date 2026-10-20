"""Legal independent arrivals, exhaustive small controls and protocol violations."""

from itertools import permutations, product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from stream_join.config import LONG_WAIT, STREAM_LENGTH
from stream_join.model import lane
from stream_join.transaction import StreamJoinItem


class StreamJoinSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('stream_join_sequence')
        self.config = config
        self.rng = random.Random(config.seed)
        self.ports = {name: '0'*width for name, width in config.widths.items() if name.startswith('i_')}
        self.busy = self.intentional = False

    def pack(self, words):
        return ''.join(bits(word, self.config.width) for word in reversed(words))

    async def send(self, label, *, edge=True, random=False, four_state_data=None, quiet=False, pulse=None, **changes):
        for name, value in changes.items():
            self.ports[name] = bits(value, self.config.widths[name])
        if four_state_data is not None:
            self.intentional = four_state_data
        item = StreamJoinItem(label, self.ports, edge=edge, random=random,
            four_state_data=self.intentional, quiet=quiet, pulse=pulse)
        await self.start_item(item)
        await self.finish_item(item)
        mask = int(self.ports['i_required'], 2) if self.config.masked else self.config.all_inputs
        if edge and item.pre.ports['o_valid'] == '1' and item.pre.ports['i_ready'] == '1':
            self.busy = False
        elif any(mask & (1 << k) and self.ports['i_valid'][-k-1] == '1' for k in range(self.config.inputs)):
            self.busy = True
        return item

    async def finish(self):
        if self.busy:
            mask = int(self.ports['i_required'], 2) if self.config.masked else self.config.all_inputs
            await self.send('finish_waiting_operation', i_valid=mask, i_ready=1)
        await self.send('idle_between_operations', edge=False, i_valid=0, i_ready=1)

    async def begin(self, mask, words=None):
        await self.finish()
        if words is None:
            words = [self.rng.getrandbits(self.config.width) for _ in range(self.config.inputs)]
        await self.send('configure_idle_join', edge=False, i_required=mask, i_valid=0,
            i_data=self.pack(words), i_ready=1, four_state_data=False)

    async def ordered(self, mask, groups):
        await self.begin(mask)
        present = 0
        for group in groups:
            present |= sum(1 << k for k in group)
            await self.send('ordered_arrival', i_valid=present)

    async def controls(self):
        c = self.config
        masks = range(c.all_inputs+1) if c.masked and c.inputs <= 5 else (c.all_inputs,)
        if c.inputs <= 5:
            for mask, valid, ready in product(masks, range(c.all_inputs+1), (0, 1)):
                await self.begin(mask)
                await self.send('control_cube', edge=False, i_valid=valid, i_ready=ready)
                await self.finish()
        else:
            await self.begin(c.all_inputs)
            await self.send('no_arrivals', edge=False)
        # Each missing producer sees ready while its own valid is still low.
        for final in range(c.inputs):
            await self.begin(c.all_inputs)
            await self.send('final_missing_ready', edge=False, i_valid=c.all_inputs ^ (1 << final), i_ready=1)
            await self.send('final_arrival', i_valid=c.all_inputs)

    async def arrivals(self):
        c = self.config
        masks = range(1, c.all_inputs+1) if c.masked and c.inputs <= 5 else (c.all_inputs,)
        for mask in masks:
            selected = [k for k in range(c.inputs) if mask & (1 << k)]
            await self.ordered(mask, [selected])
            await self.ordered(mask, [(k,) for k in selected])
            await self.ordered(mask, [(k,) for k in reversed(selected)])
            if len(selected) >= 3:
                await self.ordered(mask, [selected[:-1], selected[-1:]])
            if c.inputs <= 3:
                for order in permutations(selected):
                    await self.ordered(mask, [(k,) for k in order])
        for population in (range(1, c.inputs+1) if c.masked else (c.inputs,)):
            for final in range(c.inputs):
                mask = sum(1 << ((final+offset) % c.inputs) for offset in range(population))
                await self.begin(mask)
                await self.send('individual_final_wait', i_valid=mask ^ (1 << final))
                await self.send('individual_final_arrival', i_valid=mask)
            mask = (1 << population)-1
            for length in (1, LONG_WAIT):
                await self.begin(mask)
                for _ in range(length):
                    await self.send('consumer_stall', i_valid=mask, i_ready=0)
                await self.send('consumer_release', i_ready=1)
                if population > 1:
                    await self.begin(mask)
                    for _ in range(length):
                        await self.send('early_producers_wait', i_valid=mask ^ (1 << (population-1)), i_ready=1)
                    await self.send('late_producer_arrives', i_valid=mask)
        await self.begin(c.all_inputs)
        for _ in range(STREAM_LENGTH):
            await self.send('continuous_join', i_valid=c.all_inputs, i_ready=1,
                i_data=self.rng.getrandbits(c.inputs*c.width))
        await self.finish()
        await self.begin(c.all_inputs)
        await self.send('clockless_complete', edge=False, i_valid=c.all_inputs)
        await self.send('clockless_backpressure', edge=False, i_ready=0)
        await self.send('sample_complete', i_ready=1)

    async def patterns(self):
        c = self.config
        maximum = (1 << c.width)-1
        words = {0, maximum, 1, maximum ^ 1, sum(1 << bit for bit in range(0, c.width, 2))}
        masks = range(1, c.all_inputs+1) if c.masked and c.inputs <= 5 else (c.all_inputs,)
        for mask, word in product(masks, sorted(words)):
            await self.begin(mask, [word]*c.inputs)
            await self.send('data_pattern', i_valid=mask)
        for bit in range(c.width):
            for invert in (False, True):
                values = [1 << ((bit+k) % c.width) for k in range(c.inputs)]
                await self.begin(c.all_inputs, [maximum ^ value if invert else value for value in values])
                await self.send('walking_lane_bits', i_valid=c.all_inputs)
        for state in 'xz':
            await self.begin(c.all_inputs)
            await self.send('intentional_four_state_stall', i_valid=c.all_inputs, i_ready=0,
                i_data=state*(c.inputs*c.width), four_state_data=True)
            await self.send('intentional_four_state_consume', i_ready=1)
            if c.masked:
                for optional in range(c.inputs):
                    mask = c.all_inputs ^ (1 << optional)
                    await self.begin(mask)
                    await self.send('optional_baseline', i_valid=mask, i_ready=0)
                    for value in ('0', '1', 'x', 'z'):
                        valid = list(bits(mask, c.inputs)); valid[-optional-1] = value
                        values = [lane(self.ports['i_data'], k, c.width) for k in range(c.inputs)]
                        values[optional] = value*c.width
                        await self.send('optional_activity', edge=False, quiet=True,
                            i_valid=''.join(valid), i_data=self.pack(values))
                    await self.finish()
                await self.begin(0)
                await self.send('idle_ignores_unknowns', quiet=True, i_valid=state*c.inputs,
                    i_data=state*(c.inputs*c.width), i_ready=state)
            else:
                await self.begin(c.all_inputs)
                await self.send('disabled_mask_unknown', i_required=state*c.inputs, i_valid=c.all_inputs)
            if c.inputs >= 2:
                await self.begin(c.all_inputs)
                await self.send('missing_inputs_ignore_ready', quiet=True, i_valid=0, i_ready=state)
        await self.finish()

    async def probe(self):
        c = self.config
        name, state, bit = c.probe.split(':')
        bit = int(bit)
        await self.begin(c.all_inputs, [0]*c.inputs)
        if name.startswith('mask'):
            await self.send('partial_active_mask', i_valid=1, i_ready=1)
            mask = c.all_inputs ^ 1 if name != 'mask_expand' else 1
            if name == 'mask_expand':
                # Begin a new active singleton, then introduce another input.
                await self.finish(); await self.begin(1)
                await self.send('active_singleton', i_valid=1, i_ready=0)
                mask = c.all_inputs
            if name == 'mask_pulse':
                await self.send('mask_pulse', edge=False, pulse=('i_required', mask))
            else:
                await self.send('illegal_mask_change', edge=False, i_required=mask)
        elif name.startswith('producer'):
            await self.send('early_operand', i_valid=1, i_ready=0)
            if name == 'producer_pulse':
                await self.send('producer_pulse', edge=False, pulse=('i_data', 1))
            else:
                await self.send('illegal_early_operand', edge=False, **({'i_valid': 0} if name == 'producer_valid' else {'i_data': 1}))
        elif name == 'accepted_data':
            word = list('0'*(c.width*c.inputs)); word[-bit-1] = state
            await self.send('unintentional_unknown_operand', i_valid=c.all_inputs, i_data=''.join(word), four_state_data=False)
        else:
            valid = c.all_inputs ^ (1 << bit) if name == 'i_valid' else c.all_inputs
            await self.send('unknown_control_baseline', edge=False, i_valid=valid, i_ready=0)
            word = list(self.ports[name]); word[-bit-1] = state
            await self.send('unknown_control', edge=False, **{name: ''.join(word)})
        raise AssertionError('Illegal stimulus did not trigger its live assertion')

    async def body(self):
        if self.config.probe:
            await self.probe()
            return
        await self.controls()
        await self.arrivals()
        await self.patterns()
        c = self.config
        for index in range(c.random_cycles):
            mask = int(self.ports['i_required'], 2) if c.masked and self.busy else self.rng.randrange(c.all_inputs+1) if c.masked else c.all_inputs
            previous = self.ports['i_valid']
            valid = self.rng.getrandbits(c.inputs)
            words = [self.rng.getrandbits(c.width) for _ in range(c.inputs)]
            if self.busy:
                for k in range(c.inputs):
                    if mask & (1 << k) and previous[-k-1] == '1':
                        valid |= 1 << k
                        words[k] = lane(self.ports['i_data'], k, c.width)
            await self.send(f'random_{index}', random=True, i_required=mask, i_valid=valid,
                i_data=self.pack(words), i_ready=self.rng.randrange(2), four_state_data=False)
        await self.finish()
