"""Directed and seeded event producers; every offered beat survives backpressure."""
import random
from cocotb.types import LogicArray
from pyuvm import uvm_sequence
from cluster.transaction import ClusterItem


class EventSequence(uvm_sequence):
    def __init__(self, config, coverage):
        super().__init__('cluster_event_contracts')
        self.c, self.coverage = config, coverage
        self.n = config.parameters['NUM_TILES']
        self.depth = config.parameters['EVENT_DEPTH']
        self.all_tiles = (1 << self.n) - 1
        self.rng = random.Random(config.seed)
        self.base = {name: 0 for name, (direction, _) in config.ports.items()
                     if direction == 'input' and name != 'i_clk'}
        self.last = {}
        self.cycle_id = 0

    async def cycle(self, *, fault=None, violate=False, **changes):
        self.base.update(changes)
        item = ClusterItem(f'events_{self.cycle_id}', self.base, fault)
        item.protocol_violation = violate
        self.cycle_id += 1
        await self.start_item(item)
        await self.finish_item(item)
        self.last = item.post
        return item

    def payloads(self, *, complete=False):
        return sum(((self.rng.getrandbits(256) & ~7) | (0 if complete else 3)) << (t * 256)
                   for t in range(self.n))

    async def reset(self):
        self.base = dict.fromkeys(self.base, 0)
        await self.cycle(i_rstb=0)
        await self.cycle()
        await self.cycle(i_rstb=1, i_event_ready=1, i_owner_id=37, i_kernel_id=91,
                         i_context_id=3, i_package_id=0x87654321, i_epoch=9)
        assert self.last['o_empty'] and not self.last['o_error']
        self.coverage.hit('reset')

    async def drain(self):
        assert not self.base['i_tile_valid'] and not any(self.base[n] for n in
            ('i_fault_valid', 'i_terminal_valid', 'i_memory_valid'))
        for _ in range(self.depth + 5):
            await self.cycle(i_event_ready=1)
            if self.last['o_empty']:
                return
        raise AssertionError(('Event queue failed to drain', self.last))

    async def critical(self, name, **changes):
        for _ in range(self.depth + 8):
            item = await self.cycle(**changes)
            if item.pre['o_' + name + '_ready']:
                self.base['i_' + name + '_valid'] = 0
                return item
        raise AssertionError(('Critical source starved', name, self.last))

    async def tiles(self, mask, **changes):
        order = []
        for _ in range(self.n + self.depth + 10):
            item = await self.cycle(i_tile_valid=mask, **changes)
            admitted = item.pre['o_tile_ready'] & mask
            if admitted:
                assert admitted.bit_count() == 1
                order.append(admitted.bit_length() - 1)
            mask &= ~admitted
            if not mask:
                self.base['i_tile_valid'] = 0
                return order
        raise AssertionError(('Tile source starved', mask, self.last))

    async def priority_and_capacity(self):
        await self.reset()
        await self.critical('fault', i_fault_valid=1, i_fault_source=241, i_fault_code=17,
                            i_terminal_valid=1, i_memory_valid=1,
                            i_memory_payload=self.rng.getrandbits(256),
                            i_tile_valid=self.all_tiles, i_tile_payload=self.payloads())
        await self.critical('terminal')
        await self.critical('memory')
        order = await self.tiles(self.all_tiles)
        assert order == list(range(self.n)), order
        await self.drain()
        self.coverage.hit('critical_priority')
        self.coverage.hit('tile_round_robin')
        await self.reset()
        for index in range(self.depth):
            item = await self.cycle(i_event_ready=0, i_memory_valid=1,
                                   i_memory_payload=self.rng.getrandbits(256))
            assert item.pre['o_memory_ready']
        self.base['i_memory_valid'] = 0
        # Hold the last tile's grant, then introduce earlier contenders. The
        # stored grant must survive both queue backpressure and critical sources.
        self.base['i_tile_payload'] = self.payloads()
        for _ in range(4):
            item = await self.cycle(i_tile_valid=1 << (self.n - 1))
            assert not item.pre['o_tile_ready'] and not item.pre['o_memory_ready']
        await self.cycle(i_owner_id=111, i_kernel_id=222, i_package_id=0x12345678,
                         i_context_id=1, i_epoch=5)
        order = await self.tiles(self.all_tiles, i_event_ready=1)
        assert order == [self.n - 1, *range(self.n - 1)], order
        await self.drain()
        assert self.coverage.counts['simultaneous_pop_push'] > 0
        self.coverage.hit('held_grant')
        self.coverage.hit('full_queue_backpressure')
        self.coverage.hit('simultaneous_pop_push')
        self.coverage.hit('full_identity_snapshot')

    async def completion(self):
        await self.reset()
        await self.tiles(self.all_tiles, i_tile_payload=self.payloads(complete=True))
        await self.drain()
        assert self.last['o_completion_mask'] == self.all_tiles
        await self.critical('terminal', i_terminal_valid=1)
        await self.drain()
        await self.tiles(1, i_clear_completion=1)
        assert self.last['o_completion_mask'] == 1 and not self.last['o_duplicate_completion']
        await self.tiles(1, i_clear_completion=0)
        assert self.last['o_duplicate_completion']
        await self.drain()
        self.coverage.hit('completion_clear_and_duplicate')

    async def unknowns(self):
        for name, value in (('i_owner_id', LogicArray('x' * 16)),
                            ('i_tile_valid', LogicArray('z' * self.n)),
                            ('i_tile_payload', LogicArray('x' * (256 * self.n))),
                            ('i_fault_valid', LogicArray('x'))):
            await self.reset()
            await self.cycle(i_tile_valid=1, i_tile_payload=self.payloads())
            self.base['i_tile_valid'] = 0
            if name == 'i_tile_valid':
                await self.cycle(**{name: value})
            else:
                await self.cycle(i_tile_valid=1, **{name: value})
            assert self.last['o_error'] and not self.last['o_tile_ready']
            assert not self.last['o_empty']
            self.base[name] = 0
            self.base['i_tile_valid'] = 0
            for _ in range(3):
                await self.cycle()
                assert self.last['o_error']
        await self.reset()
        await self.tiles(1, i_tile_payload=self.payloads())
        for _ in range(4):
            await self.cycle(i_event_ready=LogicArray('x'))
            assert self.last['o_event_valid'] and not self.last['o_error']
        await self.drain()
        self.coverage.hit('unknown_fails_closed')

    async def withdrawn_source(self):
        await self.reset()
        for _ in range(self.depth):
            item = await self.cycle(i_event_ready=0, i_memory_valid=1, i_memory_payload=11)
            assert item.pre['o_memory_ready']
        await self.cycle(i_memory_valid=0, i_tile_valid=1 << (self.n - 1),
                         i_tile_payload=self.payloads())
        assert not self.last['o_tile_ready']
        await self.cycle(i_tile_valid=0, violate=True)
        assert self.last['o_error'] and not self.last['o_tile_ready']
        for _ in range(3):
            await self.cycle(i_tile_valid=1 << (self.n - 1), i_event_ready=1)
            assert self.last['o_error'] and not self.last['o_tile_ready']
        await self.reset()
        self.coverage.hit('withdrawn_held_request_is_reported')

    async def faults(self):
        if self.c.parameters['PROTECT_EVENTS']:
            for path in ('g_events.u_queue.u_metadata.g_protection.u_parity_bit.o_q',
                         'g_events.u_queue.g_lane[0].u_fifo.o_data'):
                await self.reset()
                await self.tiles(1, i_event_ready=0, i_tile_payload=self.payloads())
                await self.cycle(fault=(path, 1))
                assert self.last['o_error'] and not self.last['o_event_valid']
                await self.cycle(fault=('release',), i_event_ready=1)
                for _ in range(3):
                    await self.cycle()
                    assert self.last['o_error'] and not self.last['o_event_valid']
                await self.reset()
            self.coverage.hit('protected_queue_fail_stop')
            await self.cycle(fault=('g_events.u_completion.stored', 1))
            assert self.last['o_error'] and not self.last['o_tile_ready']
            await self.cycle(fault=('release',))
            await self.cycle()
            assert self.last['o_error']
            await self.reset()
            self.coverage.hit('protected_completion_fail_stop')
        await self.reset()
        await self.cycle(i_tile_valid=1, i_tile_payload=self.payloads(),
                         fault=('g_events.u_sequence.o_count', 0xffffffff))
        self.base['i_tile_valid'] = 0
        assert self.last['o_error'] and self.last['o_event_sequence'] == 0xffffffff
        await self.cycle(fault=('release',))
        for _ in range(3):
            await self.cycle(i_tile_valid=1)
            assert not self.last['o_tile_ready'] and self.last['o_error']
        await self.reset()
        self.coverage.hit('sequence_exhaustion_never_wraps')
        await self.tiles(1, i_event_ready=0, i_tile_payload=self.payloads())
        await self.reset()
        self.coverage.hit('reset_with_pending')

    async def random_traffic(self):
        await self.reset()
        pending = 0
        payloads = [0] * self.n
        memory = terminal = fault = False
        memory_payload = 0
        for _ in range(self.c.random_cycles):
            for t in range(self.n):
                if not (pending >> t & 1) and self.rng.random() < .08:
                    pending |= 1 << t
                    payloads[t] = (self.rng.getrandbits(256) & ~7) | 3
            if not memory and self.rng.random() < .12:
                memory = True
                memory_payload = self.rng.getrandbits(256)
            if not terminal and self.rng.random() < .03:
                terminal = True
            if not fault and self.rng.random() < .02:
                fault = True
            item = await self.cycle(i_tile_valid=pending,
                i_tile_payload=sum(v << (t * 256) for t, v in enumerate(payloads)),
                i_memory_valid=int(memory), i_memory_payload=memory_payload,
                i_terminal_valid=int(terminal), i_fault_valid=int(fault),
                i_fault_code=17, i_fault_source=243, i_event_ready=int(self.rng.random() > .35))
            pending &= ~item.pre['o_tile_ready']
            memory &= not bool(item.pre['o_memory_ready'])
            terminal &= not bool(item.pre['o_terminal_ready'])
            fault &= not bool(item.pre['o_fault_ready'])
            self.coverage.random_transactions += 1
        self.base.update(i_memory_valid=int(memory), i_terminal_valid=int(terminal),
                         i_fault_valid=int(fault))
        for name in ('fault', 'terminal', 'memory'):
            if self.base['i_' + name + '_valid']:
                await self.critical(name, i_event_ready=1)
        await self.tiles(pending, i_event_ready=1)
        await self.drain()
        self.coverage.hit('seeded_traffic')

    async def body(self):
        await self.priority_and_capacity()
        await self.completion()
        await self.unknowns()
        await self.withdrawn_source()
        await self.faults()
        await self.random_traffic()
