"""Legal bypass/stall traffic, reset boundaries, bit transport and negative probes."""

from itertools import product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from skid_buffer.config import LONG_STALL, STALL_LIMIT, STREAM_LENGTH
from skid_buffer.coverage import OPERATION_PAIRS, START_FULL
from skid_buffer.transaction import SkidBufferItem


class SkidBufferSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('skid_buffer_sequence')
        self.config = config
        self.rng = random.Random(config.seed)
        self.ports = dict(i_rstb='0', i_valid='0', i_data='0'*config.width, i_ready='0')
        self.pending = None

    async def send(self, label, *, edge=True, random=False, four_state_data=False, pulse=False, **changes):
        for name, value in changes.items():
            self.ports[name] = bits(value, self.config.widths[name])
        item = SkidBufferItem(label, self.ports, edge=edge, random=random, four_state_data=four_state_data, pulse=pulse)
        await self.start_item(item)
        await self.finish_item(item)
        if item.ports['i_rstb'] == '0':
            self.pending = None
        elif edge and item.pre.ports['o_ready'] == '1':
            self.pending = None
        elif item.ports['i_valid'] == '1' and item.pre.ports['o_ready'] == '0':
            self.pending = item.ports['i_data']
        return item

    async def drain(self):
        # A full release edge does not accept a waiting producer. Keep the offer
        # for a second edge, where it bypasses an empty entry and is accepted.
        for _ in range(2):
            if self.pending is not None:
                await self.send('waiting_producer', i_rstb=1, i_valid=1, i_data=self.pending, i_ready=1)
        await self.send('drain', i_rstb=1, i_valid=0, i_ready=1)

    async def fill(self, word=None):
        await self.drain()
        await self.send('capture', i_valid=1, i_ready=0, i_data=self.rng.getrandbits(self.config.width) if word is None else word)

    async def operation(self, name):
        valid, ready = dict(idle=(0, 0), bypass=(1, 1), capture=(1, 0), hold=(0, 0), release=(0, 1))[name]
        await self.send(name, i_valid=valid, i_ready=ready, i_data=self.rng.getrandbits(self.config.width))

    def representatives(self):
        width = self.config.width
        maximum = (1 << width)-1
        return {0, maximum, 1, maximum ^ 1,
            sum(1 << bit for bit in range(0, width, 2)), sum(1 << bit for bit in range(1, width, 2))}

    async def directed(self):
        c = self.config
        await self.send('initial_reset', i_rstb=0)
        await self.send('reset_release', edge=False, i_rstb=1)
        for previous, following in sorted(OPERATION_PAIRS):
            await (self.fill() if START_FULL[previous] else self.drain())
            await self.operation(previous)
            await self.operation(following)
        for count, valid, ready in product((0, 1), repeat=3):
            await (self.fill() if count else self.drain())
            await self.send('reset_handshake_priority', i_rstb=0, i_valid=valid, i_ready=ready)
            await self.send('reset_release', i_rstb=1, i_valid=0, i_ready=0)
            await self.fill()
            await self.drain()
        for count in (0, 1):
            await (self.fill() if count else self.drain())
            await self.send('between_edge_reset', edge=False, i_rstb=0, i_valid=1, i_ready=1)
            await self.send('between_edge_release', edge=False, i_rstb=1, i_valid=0, i_ready=0)
            await self.drain()
        for count, valid, ready in product((0, 1), repeat=3):
            await (self.fill() if count else self.drain())
            await self.send('clockless_bypass_and_ready', edge=False, i_valid=valid, i_ready=ready, i_data=self.rng.getrandbits(c.width))
            await self.send('next_real_edge', i_ready=1)
            await self.drain()
        for word, length, waiting in product(sorted(self.representatives()), (*range(STALL_LIMIT+1), LONG_STALL), (0, 1)):
            await self.fill(word)
            offer = self.rng.getrandbits(c.width)
            for _ in range(length):
                await self.send('buffered_hold', i_valid=waiting, i_ready=0, i_data=offer)
            await self.send('buffered_release', i_valid=waiting, i_ready=1, i_data=offer)
            await self.drain()
        await self.drain()
        for _ in range(STREAM_LENGTH):
            await self.send('continuous_bypass', i_valid=1, i_ready=1, i_data=self.rng.getrandbits(c.width))
        await self.drain()
        for _ in range(LONG_STALL):
            await self.send('producer_idle', i_valid=0, i_ready=1, i_data=self.rng.getrandbits(c.width))

    async def patterns(self):
        c = self.config
        maximum = (1 << c.width)-1
        patterns = self.representatives()
        patterns.update(1 << bit for bit in range(c.width))
        patterns.update(maximum ^ (1 << bit) for bit in range(c.width))
        for word in sorted(patterns):
            await self.drain()
            await self.send('bypass_pattern', i_valid=1, i_ready=1, i_data=word)
            await self.send('capture_pattern', i_valid=1, i_ready=0)
            await self.send('hold_pattern', i_valid=0, i_ready=0, i_data=self.rng.getrandbits(c.width))
            await self.drain()
        for state in 'xz':
            for occupied in (0, 1):
                await (self.fill() if occupied else self.drain())
                await self.send('invalid_unknown_payload', i_valid=0, i_ready=0, i_data=state*c.width)
                await self.drain()
            words = [state*c.width]
            for bit in range(c.width):
                word = list(bits(maximum, c.width))
                word[-bit-1] = state
                words.append(''.join(word))
            for word in words:
                await self.drain()
                await self.send('intentional_four_state_bypass', four_state_data=True, i_valid=1, i_ready=1, i_data=word)
                await self.send('intentional_four_state_capture', four_state_data=True, i_valid=1, i_ready=0)
                await self.send('intentional_four_state_hold', i_valid=0, i_ready=0)
                await self.drain()

    async def probe(self):
        await self.send('probe_reset', i_rstb=0)
        await self.send('probe_release', i_rstb=1)
        name, state, bit = self.config.probe.split(':')
        if name.startswith('producer'):
            await self.fill(0)
            await self.send('pending_producer', i_valid=1, i_ready=0, i_data=1)
            if name == 'producer_pulse':
                await self.send('illegal_pulse', edge=False, pulse=True)
            else:
                await self.send('illegal_producer', edge=False, **({'i_valid': 0} if name == 'producer_valid' else {'i_data': 0}))
        elif name.startswith('accepted_'):
            word = list(bits(0, self.config.width))
            word[-int(bit)-1] = state
            await self.send('unintentional_unknown_data', i_valid=1, i_ready=int(name == 'accepted_bypass'), i_data=''.join(word))
        else:
            if name.endswith('_empty'):name = name.removesuffix('_empty')
            else:await self.fill(1)
            await self.send('unknown_control', **{name: state})
        raise AssertionError('Illegal stimulus did not trigger its live assertion')

    async def body(self):
        if self.config.probe:
            await self.probe()
            return
        await self.directed()
        await self.patterns()
        c = self.config
        for index in range(c.random_cycles):
            reset, valid, ready = int(self.rng.random() >= 0.03), self.rng.randrange(2), self.rng.randrange(2)
            data = self.rng.getrandbits(c.width)
            if reset and self.pending is not None:
                valid, data = 1, self.pending
            await self.send(f'random_{index}', random=True, i_rstb=reset, i_valid=valid, i_ready=ready, i_data=data)
        await self.drain()
        await self.send('final_idle', i_valid=0, i_ready=0)
