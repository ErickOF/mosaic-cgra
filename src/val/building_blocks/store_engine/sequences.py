"""Independent ordered write peer and stream source with adversarial schedules."""

from collections import deque
import random
from pyuvm import uvm_sequence
from store_engine.model import number
from store_engine.transaction import INPUTS, DESCRIPTOR, STREAM, StoreEngineItem


class StoreEngineSequence(uvm_sequence):
    def __init__(self, c):
        super().__init__('store_engine_sequence')
        self.c = c
        self.rng = random.Random(c.seed)
        self.p = dict.fromkeys(INPUTS, 0) | dict(i_rstb=1, i_mem_req_ready=1)
        self.peer = {}
        self.order = deque()
        self.current = None
        self.descriptor_state = None
        self.source_index = 0
        self.next_tag = 0
        self.error_positions = set()
        self.last = None

    def descriptor(self, mode=1, size=0, count=None, sign=0):
        c = self.c
        maximum = (1 << c.COUNT_WIDTH) - 1
        limit = (1 << c.ADDR_WIDTH) - 1
        element = 1 << size
        sign = 0 if mode == 0 else sign
        inner = min(maximum, count or c.MAX_OUTSTANDING * 4 + 7)
        outer = min(maximum, 3) if mode == 2 else 1
        if mode == 0 or sign:
            outer = min(outer, max(1, (limit + 1) // element))
            inner = min(inner, max(1, (limit + 1) // element // outer))
        base = ((limit + 1) // element - 1) * element if sign < 0 else 0
        return dict(i_mode=mode, i_base_address=base, i_inner_count=inner, i_outer_count=outer,
                    i_inner_stride=(sign * element) & limit,
                    i_outer_stride=(sign * inner * element if mode == 2 else 0) & limit,
                    i_element_size_log2=size, i_address_space=self.rng.getrandbits(c.SPACE_ID_WIDTH),
                    i_channel_id=self.rng.getrandbits(c.CHANNEL_ID_WIDTH),
                    i_context_id=self.rng.getrandbits(c.CONTEXT_ID_WIDTH),
                    i_expect_end_of_stream=self.rng.randrange(2))

    def beat(self, **changes):
        d = self.descriptor_state
        row, col = divmod(self.source_index, d['i_inner_count'])
        last = self.source_index + 1 == d['i_inner_count'] * d['i_outer_count']
        return dict(i_stream_data=self.rng.getrandbits(self.c.DATA_WIDTH),
                    i_stream_keep=(1 << (1 << d['i_element_size_log2'])) - 1,
                    i_stream_first=int(self.source_index == 0), i_stream_last=int(last),
                    i_stream_row_first=int(col == 0), i_stream_row_last=int(col + 1 == d['i_inner_count']),
                    i_stream_end_of_stream=int(last and d['i_expect_end_of_stream']), i_stream_error=0,
                    i_stream_channel_id=d['i_channel_id'], i_stream_context_id=d['i_context_id']) | changes

    def response(self, order='random'):
        tags = [tag for tag in self.order if self.peer[tag]['response'] is None]
        if not tags:
            return {}
        tag = tags[-1] if order == 'reverse' else tags[0] if order == 'in_order' else self.rng.choice(tags)
        return dict(i_mem_rsp_valid=1, i_mem_rsp_tag=tag, i_mem_rsp_error=self.peer[tag]['error'])

    async def tick(self, label='cycle', *, offer=False, edge=True, random=False,
                   fault=False, release=False, **values):
        d = self.descriptor_state
        if (offer and self.current is None and d and number(self.last['o_error']) == 0 and
                self.source_index < d['i_inner_count'] * d['i_outer_count']):
            self.current = self.beat()
        ports = self.p | dict(i_config_valid=0, i_mem_rsp_valid=0, i_error_clear=0,
                              i_stream_valid=int(self.current is not None))
        if self.current is not None:
            ports.update(self.current)
        ports.update(values)
        item = StoreEngineItem(label, ports, edge=edge, random=random, fault=fault, release=release)
        await self.start_item(item)
        await self.finish_item(item)
        pre, post = item.pre.ports, item.observation.ports
        if ports['i_rstb'] == 0 and (edge or self.c.ASYNC_RESET):
            self.peer.clear()
            self.order.clear()
            self.current = self.descriptor_state = None
            self.next_tag = 0
        elif edge and ports['i_rstb'] == 1:
            if number(pre['o_config_ready']) and ports['i_config_valid'] == 1:
                self.source_index = 0
                self.current = None
            if number(pre['o_mem_rsp_ready']) and ports['i_mem_rsp_valid'] == 1:
                tag = number(ports['i_mem_rsp_tag'])
                if tag in self.peer and self.peer[tag]['response'] is None and ports['i_mem_rsp_error'] in (0, 1):
                    self.peer[tag]['response'] = ports['i_mem_rsp_error']
            if number(post['o_response_retired']):
                tag = self.order.popleft()
                assert self.peer[tag]['response'] is not None, 'Peer observed premature retirement'
                del self.peer[tag]
            if number(pre['o_mem_req_valid']) and ports['i_mem_req_ready'] == 1:
                assert number(pre['i_stream_valid']) and number(pre['o_stream_ready']), 'Unpaired peer write'
                tag = number(pre['o_mem_req_tag'])
                assert tag not in self.peer, 'Memory peer observed early tag reuse'
                self.peer[tag] = dict(error=int(self.source_index in self.error_positions), response=None)
                self.order.append(tag)
                self.next_tag = (tag + 1) % self.c.MAX_OUTSTANDING
                self.source_index += 1
            if number(pre['o_stream_ready']) and ports['i_stream_valid'] == 1:
                self.current = None
        self.last = post
        return post

    async def reset(self):
        await self.tick('clockless_reset', edge=False, i_rstb=0)
        await self.tick('reset', i_rstb=0)
        await self.tick('release', release=True)

    async def recover(self):
        self.current = None
        await self.tick('clear', i_error_clear=1)
        await self.tick('after_clear')
        assert number(self.last['o_error']) == 0

    async def configure(self, d):
        self.current = None
        self.p.update(d)
        for _ in range(8):
            post = await self.tick('configure', i_config_valid=1)
            if number(post['o_command_started']) or number(post['o_command_failed']):
                self.descriptor_state = d if number(post['o_command_started']) else None
                return post
        raise AssertionError('Configuration was not consumed')

    async def drain(self, order='random', adversarial=False, *, random=False):
        for _ in range(10000):
            vals = self.response(order)
            vals['i_mem_req_ready'] = int(not adversarial or self.rng.random() > .3)
            await self.tick('drain', offer=not adversarial or self.rng.random() > .3,
                            random=random, **vals)
            if not number(self.last['o_busy']):
                assert not self.peer and not self.order, 'Engine stopped with owned writes'
                self.current = None
                return self.last
        raise AssertionError('Fair memory/source did not drain')

    async def traffic(self):
        c = self.c
        for mode in range(3):
            for size in range(c.max_log2 + 1):
                for sign in (-1, 0, 1):
                    if mode == 0 and sign != 0 or sign == 1 and c.ADDR_WIDTH == 1:
                        continue
                    await self.configure(self.descriptor(mode, size, sign=sign))
                    await self.drain(('in_order', 'reverse', 'random')[(mode + size) % 3], True)
        # Fill all slots, then capture youngest completions behind a missing head.
        d = self.descriptor()
        self.error_positions = {0, d['i_inner_count'] // 2, d['i_inner_count'] - 1}
        await self.configure(d)
        for _ in range(c.MAX_OUTSTANDING):
            await self.tick('fill', offer=True)
        assert len(self.peer) == c.MAX_OUTSTANDING
        for _ in range(16):
            await self.tick('full_hold', i_error_clear=1)
        for _ in range(c.MAX_OUTSTANDING):
            await self.tick('reverse_response', **self.response('reverse'))
        await self.drain('in_order')
        # Fast in-order peer enables allocation, response and retirement together.
        await self.configure(self.descriptor(count=40))
        await self.drain('in_order')
        for position in (0, 1, 2):
            self.error_positions = {position}
            await self.configure(self.descriptor(count=3))
            post = await self.drain('in_order')
            assert number(post['o_completed_with_error']) == 1
        self.error_positions = set()
        for state in (0, 'x', 'z', 0):
            await self.configure(self.descriptor(count=3))
            for _ in range(4):
                await self.tick('request_stall', offer=True, i_mem_req_ready=state)
                await self.tick('clockless_stall', edge=False, i_mem_req_ready=state)
            await self.drain()
        if c.DATA_WIDTH > 8:
            await self.configure(self.descriptor(size=0, count=1))
            self.current = self.beat(i_stream_data='x' * (c.DATA_WIDTH - 8) + '10100101')
            await self.drain()
        # Saturation of the small verification counter copies is deterministic.
        for _ in range(90):
            await self.configure(self.descriptor(count=3))
            await self.drain('in_order')

    async def descriptors(self):
        c = self.c
        cases = [dict(i_mode=3), dict(i_inner_count=0), dict(i_outer_count=0), dict(i_outer_count=2),
                 dict(i_inner_count=2, i_inner_stride=(1 << c.ADDR_WIDTH) - 1)]
        if c.max_log2:
            cases += [dict(i_element_size_log2=1, i_base_address=1),
                      dict(i_mode=1, i_element_size_log2=1, i_inner_stride=1),
                      dict(i_mode=2, i_element_size_log2=1, i_outer_stride=1)]
        if c.max_log2 < (1 << c.aliases['ELEMENT_SIZE_WIDTH']) - 1:
            cases.append(dict(i_element_size_log2=c.max_log2 + 1))
        for change in cases:
            post = await self.configure(self.descriptor(count=1) | change)
            assert number(post['o_command_failed']) and not number(post['o_command_started'])
            await self.recover()
        for field in DESCRIPTOR:
            for state in 'xz':
                post = await self.configure(self.descriptor(count=1) | {field: state * c.widths[field]})
                assert number(post['o_error_code']) == 9
                await self.recover()

    async def stream_faults(self):
        c = self.c
        fields = [name for name in STREAM if name != 'i_stream_data']
        for field in fields:
            for owned in (0, c.MAX_OUTSTANDING):
                await self.configure(self.descriptor(count=c.MAX_OUTSTANDING + 4))
                for _ in range(owned):
                    await self.tick('owners', offer=True)
                good = self.beat()
                self.current = good | {field: good[field] ^ 1}
                post = await self.tick('fault:' + field, i_mem_req_ready=0)
                assert number(post['o_stream_accepted']) and not number(post['o_request_accepted'])
                assert number(post['o_error'])
                await self.drain('reverse')
                await self.recover()
            for state in 'xz':
                for owned in (0, c.MAX_OUTSTANDING):
                    await self.configure(self.descriptor(count=c.MAX_OUTSTANDING + 4))
                    for _ in range(owned):
                        await self.tick('owners', offer=True)
                    self.current = self.beat(**{field: state * c.widths[field]})
                    post = await self.tick('unknown_stream', i_mem_req_ready=0)
                    assert number(post['o_error_code']) == 16
                    await self.drain('reverse')
                    await self.recover()
        for position in (0, 1, 2):
            await self.configure(self.descriptor(count=3))
            while self.source_index < position:
                await self.tick('before_poison', offer=True, **self.response('in_order'))
            self.current = self.beat(i_stream_error=1)
            await self.tick('poison_position', i_mem_req_ready=0)
            assert number(self.last['o_error_code']) == 17
            await self.drain('reverse')
            await self.recover()
        # Pairwise priority, independent of the order of enum values in the RTL.
        fault_fields = ('i_stream_error', 'i_stream_context_id', 'i_stream_channel_id',
                        'i_stream_keep', 'i_stream_first')
        for first in range(len(fault_fields)):
            for second in range(first + 1, len(fault_fields)):
                await self.configure(self.descriptor(count=3))
                beat = self.beat()
                for n in (first, second):
                    field = fault_fields[n]
                    beat[field] ^= 1
                self.current = beat
                post = await self.tick('priority')
                assert number(post['o_error_code']) == 17 + first
                await self.drain()
                await self.recover()

    async def protocol_faults(self):
        c = self.c
        for field in ('i_mem_rsp_tag', 'i_mem_rsp_error'):
            for state in 'xz':
                post = await self.tick('unknown_response', i_mem_rsp_valid=1,
                                       **{field: state * c.widths[field]})
                assert number(post['o_error_code']) == 15 and not number(post['o_command_failed'])
                await self.recover()
        await self.tick('unallocated', i_mem_rsp_valid=1, i_mem_rsp_tag=0)
        await self.recover()
        if c.MAX_OUTSTANDING < 1 << c.aliases['TAG_WIDTH']:
            await self.tick('tag_range', i_mem_rsp_valid=1, i_mem_rsp_tag=c.MAX_OUTSTANDING)
            await self.recover()
        await self.configure(self.descriptor())
        await self.tick('too_early', offer=True, i_mem_rsp_valid=1, i_mem_rsp_tag=self.next_tag)
        assert number(self.last['o_error_code']) == 13
        await self.drain()
        await self.recover()
        await self.configure(self.descriptor())
        for _ in range(c.MAX_OUTSTANDING):
            await self.tick('allocate', offer=True)
        rsp = self.response('reverse')
        await self.tick('first_response', **rsp)
        await self.tick('duplicate', **rsp)
        assert number(self.last['o_error_code']) == 14
        await self.tick('first_error_wins', i_mem_rsp_valid=1,
                        i_mem_rsp_tag='x' * c.aliases['TAG_WIDTH'], i_error_clear=1)
        assert number(self.last['o_error_code']) == 14
        await self.drain('reverse')
        await self.recover()
        if c.check_internals:
            for issued in sorted({0, 1, min(3, c.MAX_OUTSTANDING)}):
                await self.configure(self.descriptor())
                for _ in range(issued):
                    await self.tick('before_agu_fault', offer=True)
                await self.tick('agu_fault', fault=True)
                assert number(self.last['o_error_code']) == 11
                await self.tick('release_agu', release=True)
                await self.drain('reverse')
                await self.recover()

    async def concurrent_faults(self):
        # Response faults have priority even when a malformed beat is consumed.
        await self.configure(self.descriptor(count=3))
        self.current = self.beat(i_stream_keep=0)
        await self.tick('response_and_stream_fault', i_mem_rsp_valid=1, i_mem_rsp_tag=self.next_tag)
        assert number(self.last['o_error_code']) == 13
        assert number(self.last['o_stream_accepted']) and not number(self.last['o_request_accepted'])
        await self.recover()
        # Unknown stream control precedes a simultaneous upstream poison report.
        await self.configure(self.descriptor(count=3))
        self.current = self.beat(i_stream_first='x', i_stream_error=1)
        await self.tick('unknown_and_poison')
        assert number(self.last['o_error_code']) == 16
        await self.recover()
        # A duplicate on the final retirement must suppress normal completion.
        await self.configure(self.descriptor(count=1))
        await self.tick('final_write', offer=True)
        rsp = self.response('in_order')
        await self.tick('final_response', **rsp)
        await self.tick('fatal_at_final_retirement', **rsp)
        assert number(self.last['o_error_code']) == 14
        assert number(self.last['o_command_failed']) and not number(self.last['o_command_completed'])
        await self.recover()
        for invalid in (False, True):
            self.p.update(self.descriptor(count=1) | ({'i_mode': 3} if invalid else {}))
            await self.tick('response_and_descriptor_fault', i_config_valid=1,
                            i_mem_rsp_valid=1, i_mem_rsp_tag=0)
            assert number(self.last['o_error_code']) == 13
            assert number(self.last['o_command_failed'])
            assert number(self.last['o_command_started']) == int(not invalid)
            await self.recover()

    async def random_campaign(self):
        c = self.c
        for _ in range(c.random_cycles):
            values = dict(i_mem_req_ready=int(self.rng.random() > .3))
            if self.rng.random() > .25:
                values.update(self.response())
            if number(self.last['o_config_ready']):
                d = self.descriptor(self.rng.randrange(3), self.rng.randrange(c.max_log2 + 1),
                                    count=self.rng.randint(1, 30),
                                    sign=self.rng.choice((-1, 0, 1) if c.ADDR_WIDTH > 1 else (-1, 0)))
                self.p.update(d)
                self.descriptor_state = d
                self.source_index = 0
                self.error_positions = {0, self.rng.randrange(30)}
                values['i_config_valid'] = 1
            await self.tick('random', offer=self.rng.random() > .3, random=True, **values)
            assert number(self.last['o_error']) == 0, 'Random peer produced a fatal protocol fault'
        await self.drain()
        self.error_positions = set()

    async def body(self):
        await self.reset()
        if self.c.probe:
            byte, state = self.c.probe.split(':')
            await self.configure(self.descriptor(size=self.c.max_log2, count=1))
            data = list('0' * self.c.DATA_WIDTH)
            data[-1 - 8 * int(byte)] = state
            self.current = self.beat(i_stream_data=''.join(data))
            await self.tick('data_probe')
            raise AssertionError('Native data assertion did not terminate the probe')
        await self.traffic()
        await self.descriptors()
        await self.stream_faults()
        await self.protocol_faults()
        await self.concurrent_faults()
        for state in 'xz':
            await self.tick('unknown_config_valid', i_config_valid=state)
            await self.tick('unknown_stream_valid', i_stream_valid=state)
            await self.tick('unknown_response_valid', i_mem_rsp_valid=state)
            await self.tick('unknown_reset', i_rstb=state, edge=False)
            await self.tick('unknown_reset_edge', i_rstb=state)
        for phase in range(4):
            await self.configure(self.descriptor())
            if phase:
                await self.tick('before_reset', offer=True)
            if phase == 2:
                await self.tick('respond_before_reset', **self.response())
            if phase == 3:
                self.current = self.beat(i_stream_error=1)
                await self.tick('drain_before_reset')
                assert number(self.last['o_error']) and number(self.last['o_busy'])
            await self.reset()
        await self.random_campaign()
        for _ in range(3):
            await self.tick('idle')
