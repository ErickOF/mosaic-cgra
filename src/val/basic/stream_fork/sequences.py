"""Multicast masks, independent consumers, replacement, reset and stable offers."""

from itertools import product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from stream_fork.config import LONG_STALL, STREAM_LENGTH
from stream_fork.transaction import StreamForkItem


class StreamForkSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('stream_fork_sequence')
        self.config = config
        self.rng = random.Random(config.seed)
        self.ports = {name: '0'*width for name, width in config.widths.items() if name.startswith('i_')}
        self.pending = None

    async def send(self, label, *, edge=True, random=False, four_state_data=False, pulse=False, **changes):
        for name, value in changes.items():
            self.ports[name] = bits(value, self.config.widths[name])
        item = StreamForkItem(label, self.ports, edge=edge, random=random, four_state_data=four_state_data, pulse=pulse)
        await self.start_item(item)
        await self.finish_item(item)
        if item.ports['i_rstb'] == '0' or edge and item.pre.ports['o_ready'] == '1':
            self.pending = None
        elif item.ports['i_valid'] == '1' and item.pre.ports['o_ready'] == '0':
            self.pending = (item.ports['i_data'], item.ports['i_destination'])
        return item

    async def drain(self):
        if self.pending is not None:
            data, mask = self.pending
            await self.send('accept_waiting_producer', i_rstb=1, i_valid=1,
                i_data=data, i_destination=mask, i_ready=self.config.all_outputs)
        await self.send('drain', i_rstb=1, i_valid=0, i_ready=self.config.all_outputs)

    async def fill(self, mask=None, data=None, *, four_state_data=False):
        await self.drain()
        await self.send('fill', i_valid=1, i_ready=0,
            i_destination=self.config.all_outputs if mask is None else mask,
            i_data=self.rng.getrandbits(self.config.width) if data is None else data,
            four_state_data=four_state_data)

    async def complete(self, mask, *, staggered=False, replacement=False):
        selected = [k for k in range(self.config.outputs) if mask & (1 << k)]
        groups = [1 << k for k in selected] if staggered else [mask]
        for index, ready in enumerate(groups):
            await self.send('deliver_copy', i_valid=int(replacement and index == len(groups)-1),
                i_ready=ready, i_data=self.rng.getrandbits(self.config.width), i_destination=self.config.all_outputs)
        await self.drain()

    async def directed(self):
        c = self.config
        await self.send('initial_reset', i_rstb=0)
        await self.send('reset_release', edge=False, i_rstb=1)
        masks = range(1, c.all_outputs+1) if c.masked and c.outputs <= 5 else (c.all_outputs,)
        for mask, staggered, replacement in product(masks, (False, True), (False, True)):
            await self.fill(mask)
            await self.complete(mask if c.masked else c.all_outputs, staggered=staggered, replacement=replacement)

        # Rotate a population-sized mask around each possible final consumer.
        for population in (range(1, c.outputs+1) if c.masked else (c.outputs,)):
            for final in range(c.outputs):
                mask = sum(1 << ((final+offset) % c.outputs) for offset in range(population))
                await self.fill(mask)
                await self.send('last_consumer_held', i_valid=0, i_ready=mask ^ (1 << final))
                await self.send('last_consumer', i_ready=1 << final)
                await self.drain()
                await self.fill(mask)
                await self.send('first_consumer', i_valid=0, i_ready=1 << final)
                await self.drain()

        for length in (1, LONG_STALL):
            await self.fill()
            word = self.rng.getrandbits(c.width)
            for _ in range(length):
                await self.send('all_outputs_stalled', i_valid=1, i_ready=0, i_data=word, i_destination=c.all_outputs)
            await self.send('complete_and_replace', i_ready=c.all_outputs)
            await self.drain()

        # Keep only one destination outstanding for a long tail while every
        # completed consumer toggles ready independently of input admission.
        for final in range(c.outputs):
            await self.fill()
            await self.send('prepare_long_tail', i_valid=0, i_ready=c.all_outputs ^ (1 << final))
            word = self.rng.getrandbits(c.width)
            for _ in range(LONG_STALL):
                await self.send('independent_long_tail', i_valid=1, i_data=word,
                    i_destination=1 << final, i_ready=self.rng.getrandbits(c.outputs) & ~(1 << final))
            await self.send('release_long_tail', i_ready=c.all_outputs)
            await self.drain()

        # Serial consumption visits every pending population and readiness class.
        await self.fill()
        for k in range(c.outputs):
            await self.send('partial_hold', i_valid=0, i_ready=0)
            await self.send('partial_consume', i_ready=1 << k)
        for population in range(1, c.outputs+1):
            await self.fill()
            await self.send('prepare_simultaneous_remaining', i_valid=0,
                i_ready=c.all_outputs ^ ((1 << population)-1))
            await self.send('consume_all_remaining', i_ready=c.all_outputs)
        await self.fill()
        for _ in range(STREAM_LENGTH):
            await self.send('continuous_multicast', i_valid=1, i_ready=c.all_outputs,
                i_destination=c.all_outputs, i_data=self.rng.getrandbits(c.width))
        await self.drain()
        for _ in range(LONG_STALL):
            await self.send('idle', i_valid=0, i_data=self.rng.getrandbits(c.width))

        for population, pulse in product(range(c.outputs+1), (False, True)):
            await self.fill()
            await self.send('prepare_reset_population', i_valid=0,
                i_ready=c.all_outputs ^ ((1 << population)-1))
            await self.send('reset_priority', edge=not pulse, i_rstb=0,
                i_valid=1, i_data=self.rng.getrandbits(c.width), i_destination=c.all_outputs, i_ready=c.all_outputs)
            await self.send('reset_release', edge=False, i_rstb=1, i_valid=0, i_ready=0)
            await self.drain()

        for occupied, valid in product((0, 1), repeat=2):
            await (self.fill() if occupied else self.drain())
            await self.send('clockless_forward_boundary', edge=False, i_valid=valid,
                i_data=self.rng.getrandbits(c.width), i_destination=c.all_outputs, i_ready=0)
            await self.send('next_edge', i_ready=c.all_outputs)
            await self.drain()

    async def patterns(self):
        c = self.config
        maximum = (1 << c.width)-1
        words = {0, maximum, 1, maximum ^ 1, sum(1 << k for k in range(0, c.width, 2))}
        masks = range(1, c.all_outputs+1) if c.masked and c.outputs <= 5 else (c.all_outputs,)
        for mask, word in product(masks, sorted(words)):
            await self.fill(mask, word)
            await self.drain()
        for bit in range(c.width):
            for word in (1 << bit, maximum ^ (1 << bit)):
                await self.fill(data=word)
                await self.drain()
        for state in 'xz':
            await self.fill(data=state*c.width, four_state_data=True)
            await self.send('four_state_stall', i_valid=0, i_ready=0)
            await self.drain()
            await self.send('ignored_invalid_payload', i_valid=0, i_data=state*c.width)
            await self.send('ignored_empty_ready', i_ready=state*c.outputs)
            await self.send('restore_ready', i_ready=0)
            for k in range(c.outputs):
                await self.fill()
                await self.send('consume_one_output', i_valid=0, i_ready=1 << k)
                ready = list(bits(0, c.outputs))
                ready[-k-1] = state
                await self.send('ignored_completed_ready', i_ready=''.join(ready))
                await self.drain()
            if not c.masked:
                await self.fill(mask=state*c.outputs, data=0)
                await self.drain()

    async def probe(self):
        c = self.config
        await self.send('probe_reset', i_rstb=0)
        await self.send('probe_release', i_rstb=1)
        name, state, bit = c.probe.split(':')
        await self.fill(data=0)
        if name.startswith('producer'):
            await self.send('blocked_offer', i_valid=1, i_ready=0, i_data=1, i_destination=1)
            if name == 'producer_pulse':
                await self.send('illegal_pulse', edge=False, pulse=True)
            else:
                change = {'i_valid': 0} if name == 'producer_valid' else {'i_destination': 2} if name == 'producer_mask' else {'i_data': 0}
                await self.send('illegal_offer', edge=False, **change)
        elif name == 'accepted_data':
            await self.drain()
            word = list(bits(0, c.width))
            word[-int(bit)-1] = state
            await self.send('unintentional_unknown_data', i_valid=1, i_data=''.join(word), i_destination=1)
        elif name == 'zero_destination':
            await self.send('illegal_zero_mask', i_valid=1, i_destination=0)
        else:
            word = list(bits(c.all_outputs if name in ('i_ready', 'i_destination') else 1, c.widths[name]))
            word[-int(bit)-1] = state
            await self.send('unknown_control', **(dict(i_valid=1, i_destination=1) | {name: ''.join(word)}))
        raise AssertionError('Illegal stimulus did not trigger its live assertion')

    async def body(self):
        if self.config.probe:
            await self.probe()
            return
        await self.directed()
        await self.patterns()
        c = self.config
        for index in range(c.random_cycles):
            reset, valid = int(self.rng.random() >= 0.02), self.rng.randrange(2)
            data, mask = self.rng.getrandbits(c.width), self.rng.randrange(1, c.all_outputs+1)
            if reset and self.pending is not None:
                valid, (data, mask) = 1, self.pending
            await self.send(f'random_{index}', random=True, i_rstb=reset, i_valid=valid,
                i_data=data, i_destination=mask, i_ready=self.rng.getrandbits(c.outputs))
        await self.drain()
        await self.send('final_idle', i_valid=0, i_ready=0)
