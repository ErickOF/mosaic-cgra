"""Directed boundaries, legal held producers, intentional probes and seeded traffic."""

from itertools import product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from fifo.transaction import FifoItem, INPUTS


class FifoSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('fifo_sequence')
        self.config = config
        self.rng = random.Random(config.seed)
        self.ports = {name: '0' * config.widths[name] for name in INPUTS}
        self.index = 0

    async def send(self, label, *, edge=True, random=False, **changes):
        for name, value in changes.items():
            self.ports[name] = bits(value, self.config.widths[name])
        item = FifoItem(label, self.ports, edge=edge, random=random)
        await self.start_item(item)
        await self.finish_item(item)
        return item

    def data(self):
        self.index += 1
        return (self.rng.getrandbits(self.config.width) ^ self.index) & ((1 << self.config.width) - 1)

    async def reset(self):
        await self.send('reset_edge', i_rstb=0, i_valid=1, i_ready=1, i_data=self.data())
        await self.send('release', edge=False, i_rstb=1, i_valid=0, i_ready=0)

    async def fill(self, count):
        for _ in range(count):
            await self.send('fill', i_valid=1, i_ready=0, i_data=self.data())

    async def drain(self):
        for _ in range(self.config.depth + 1):
            await self.send('drain', i_rstb=1, i_valid=0, i_ready=1)

    async def boundaries(self):
        for count in range(self.config.depth + 1):
            for valid, ready in product((0, 1), repeat=2):
                await self.reset()
                await self.fill(count)
                await self.send('occupancy_cross', i_valid=valid, i_ready=ready, i_data=self.data())
                # Reset explicitly cancels a possible held producer obligation.
                await self.reset()
            await self.fill(count)
            await self.reset()
        await self.fill(self.config.depth)
        pending = self.data()
        for _ in range(64):
            await self.send('long_stall', i_valid=1, i_ready=0, i_data=pending)
        await self.send('first_full_replacement', i_valid=1, i_ready=1, i_data=pending)
        for _ in range(max(16, 4 * self.config.depth)):
            await self.send('full_rate_replacement', i_valid=1, i_ready=1, i_data=self.data())
        await self.drain()
        # Several pure-write/pure-read wraps, in addition to simultaneous wraps.
        for _ in range(4):
            await self.fill(self.config.depth)
            await self.drain()

    async def resets_and_payloads(self):
        for count in sorted({0, 1, self.config.depth // 2, self.config.depth}):
            await self.reset()
            await self.fill(count)
            # With no edge, only asynchronous reset may discard the queue.
            await self.send('between_edge_reset', edge=False, i_rstb=0, i_valid=1, i_ready=1)
            await self.send('pulse_release', edge=False, i_rstb=1, i_valid=0, i_ready=0)
            await self.drain()
        mask = (1 << self.config.width) - 1
        patterns = [0, mask, mask // 3, mask ^ (mask // 3)]
        patterns += [1 << bit for bit in range(self.config.width)]
        patterns += [mask ^ (1 << bit) for bit in range(self.config.width)]
        for data in patterns:
            await self.send('data_patterns', i_valid=1, i_ready=1, i_data=data)
        await self.drain()
        for state, bit in product('xz', range(self.config.width)):
            word = list('0' * self.config.width)
            word[self.config.width - 1 - bit] = state
            await self.send('intentional_four_state_payload', i_valid=1, i_ready=1, i_data=''.join(word))
        await self.drain()

    async def randomized(self):
        held = None
        for index in range(self.config.random_cycles):
            reset = self.rng.randrange(97) == 0
            valid, data = held if held is not None else (int(self.rng.randrange(4) != 0), self.data())
            item = await self.send(f'random:{index}', random=True, i_rstb=int(not reset),
                                   i_valid=valid, i_data=data, i_ready=int(self.rng.randrange(2) == 0))
            held = ((valid, data) if not reset and valid and item.pre.ports['o_ready'] == '0' else None)
        if held is not None:
            await self.send('finish_held', i_rstb=1, i_valid=held[0], i_data=held[1], i_ready=1)
        await self.drain()

    async def probe(self):
        field, state = self.config.probe.split(':')
        if field in ('producer_data', 'producer_valid'):
            await self.fill(self.config.depth)
            data = self.data()
            await self.send('probe_stall', i_valid=1, i_ready=0, i_data=data)
            changes = dict(i_data=data ^ 1) if field == 'producer_data' else dict(i_valid=0)
            await self.send('probe_unstable_producer', **changes)
        else:
            # Live state makes reset poisoning observable as well as illegal.
            await self.fill(1)
            await self.send('probe_unknown_control', **{field: state})
        assert False, 'Protocol probe was not detected'

    async def body(self):
        await self.reset()
        if self.config.probe:
            await self.probe()
            return
        await self.boundaries()
        await self.resets_and_payloads()
        await self.randomized()
