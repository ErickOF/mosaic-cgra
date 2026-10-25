"""Independent memory peer, adversarial directed traffic and seeded random cycles."""
from collections import deque
import random
from pyuvm import uvm_sequence
from load_engine.model import number
from load_engine.transaction import INPUTS, DESCRIPTOR, LoadEngineItem


class LoadEngineSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('load_engine_sequence')
        self.c = config
        self.rng = random.Random(config.seed)
        self.p = dict.fromkeys(INPUTS, 0)
        self.p.update(i_rstb=1, i_mem_req_ready=1, i_stream_ready=1)
        self.peer = {}
        self.order = deque()
        self.serial = 0
        self.issued = 0
        self.error_positions = set()
        self.last = None

    async def tick(self, label='cycle', *, edge=True, random=False, fault=False, release=False, **values):
        ports = self.p | dict(i_config_valid=0, i_mem_rsp_valid=0, i_error_clear=0) | values
        item = LoadEngineItem(label, ports, edge=edge, random=random, fault=fault, release=release)
        await self.start_item(item)
        await self.finish_item(item)
        pre, post = item.pre.ports, item.observation.ports
        if ports['i_rstb'] == 0 and (edge or self.c.ASYNC_RESET):
            self.peer.clear()
            self.order.clear()
        elif edge and ports['i_rstb'] == 1:
            if number(pre['o_config_ready']) and ports['i_config_valid'] == 1:
                self.issued = 0
            if number(pre['o_mem_rsp_ready']) and ports['i_mem_rsp_valid'] == 1:
                tag = number(ports['i_mem_rsp_tag'])
                if tag in self.peer and not self.peer[tag]['responded'] and ports['i_mem_rsp_error'] in (0, 1):
                    self.peer[tag]['responded'] = True
            if number(pre['o_stream_valid']) and ports['i_stream_ready'] == 1:
                tag = self.order.popleft()
                assert self.peer[tag]['responded'], 'Peer observed premature retirement'
                del self.peer[tag]
            if number(pre['o_mem_req_valid']) and ports['i_mem_req_ready'] == 1:
                tag = number(pre['o_mem_req_tag'])
                assert tag not in self.peer, 'Memory peer detected early tag reuse'
                self.peer[tag] = dict(data=self.rng.getrandbits(self.c.DATA_WIDTH),
                                      error=int(self.issued in self.error_positions), responded=False)
                self.order.append(tag)
                self.issued += 1
        self.last = post
        self.serial += 1
        return post

    def response(self, order='random'):
        tags = [tag for tag in self.order if not self.peer[tag]['responded']]
        if not tags:
            return {}
        tag = tags[-1] if order == 'reverse' else tags[0] if order == 'in_order' else self.rng.choice(tags)
        return dict(i_mem_rsp_valid=1, i_mem_rsp_tag=tag, i_mem_rsp_data=self.peer[tag]['data'],
                    i_mem_rsp_error=self.peer[tag]['error'])

    def descriptor(self, mode=1, size=0, count=None, sign=0):
        c = self.c
        limit = (1 << c.ADDR_WIDTH) - 1
        maximum = (1 << c.COUNT_WIDTH) - 1
        element = 1 << size
        if mode == 0:
            sign = 0
        inner = min(maximum, count or c.MAX_OUTSTANDING * 4 + 7)
        outer = min(maximum, 3) if mode == 2 else 1
        if sign:
            outer = min(outer, max(1, (limit + 1) // element))
        if mode == 0 or sign:
            inner = min(inner, max(1, (limit + 1) // element // outer))
        step = sign * element
        row = sign * inner * element if mode == 2 else 0
        base = element * ((limit + 1) // element - 1) if sign < 0 else 0
        return dict(i_mode=mode, i_element_size_log2=size, i_base_address=base,
                    i_inner_count=inner, i_outer_count=outer, i_inner_stride=step & limit,
                    i_outer_stride=row & limit, i_address_space=self.rng.getrandbits(c.SPACE_ID_WIDTH),
                    i_channel_id=self.rng.getrandbits(c.CHANNEL_ID_WIDTH),
                    i_context_id=self.rng.getrandbits(c.CONTEXT_ID_WIDTH),
                    i_emit_end_of_stream=self.rng.randrange(2))

    async def configure(self, descriptor):
        self.p.update(descriptor)
        for _ in range(8):
            post = await self.tick('configure', i_config_valid=1)
            if number(post['o_command_started']) or number(post['o_command_failed']):
                return post
        raise AssertionError('Descriptor was not consumed')

    async def drain(self, order='random', adversarial=False):
        for cycle in range(10000):
            values = self.response(order)
            values.update(i_mem_req_ready=int(not adversarial or self.rng.random() > .25),
                          i_stream_ready=int(not adversarial or self.rng.random() > .35))
            post = await self.tick('drain', **values)
            if not number(post['o_busy']):
                assert not self.peer, 'Engine finished with memory transactions owned'
                return post
        raise AssertionError('Drain did not terminate with a fair memory peer')

    async def reset(self, active=False):
        await self.tick('clockless reset', edge=False, i_rstb=0)
        await self.tick('coordinated reset', i_rstb=0)
        await self.tick('reset release', release=True)

    async def recover(self):
        await self.tick('error clear', i_error_clear=1)
        await self.tick('after error clear')
        assert number(self.last['o_error']) == 0 and number(self.last['o_config_ready']) == 1

    async def traffic(self):
        c = self.c
        for mode in range(3):
            for size in range(c.max_log2 + 1):
                for sign in (-1, 0, 1):
                    if mode == 0 and sign != 0:
                        continue
                    if sign == 1 and c.ADDR_WIDTH == 1:
                        continue
                    await self.configure(self.descriptor(mode, size, sign=sign))
                    await self.drain(('in_order', 'reverse', 'random')[(mode + size) % 3], True)
        # Force every occupancy and store younger responses behind a missing head.
        descriptor = self.descriptor()
        count = descriptor['i_inner_count']
        self.error_positions = {0, count // 2, count - 1}
        await self.configure(descriptor)
        for _ in range(c.MAX_OUTSTANDING + 4):
            await self.tick('fill table', i_stream_ready=0)
        assert len(self.peer) == c.MAX_OUTSTANDING
        for _ in range(c.MAX_OUTSTANDING):
            await self.tick('reverse responses', i_stream_ready=0, **self.response('reverse'))
        for _ in range(12):
            await self.tick('persistent stream stall', i_stream_ready=0, i_error_clear=1)
        await self.drain('in_order')
        # With >=3 slots this reaches a steady request/response/retirement pipeline.
        descriptor = self.descriptor(count=7)
        count = descriptor['i_inner_count']
        self.error_positions = {0, count // 2, count - 1}
        await self.configure(descriptor)
        await self.drain('in_order')
        self.error_positions = set()
        # Hold a request across unknown ready and clockless input changes.
        await self.configure(self.descriptor())
        for ready in (0, 'x', 'z', 0):
            await self.tick('request hold', i_mem_req_ready=ready, i_stream_ready=0,
                            **{n: self.rng.getrandbits(c.widths[n]) for n in DESCRIPTOR})
            await self.tick('clockless hold', edge=False, i_mem_req_ready=0)
        await self.drain()

    async def illegal_descriptors(self):
        c = self.c
        cases = [dict(i_mode=3), dict(i_inner_count=0), dict(i_outer_count=0),
                 dict(i_outer_count=2),
                 dict(i_base_address=0, i_inner_count=2, i_inner_stride=(1 << c.ADDR_WIDTH) - 1),
                 dict(i_mode=0, i_base_address=(1 << c.ADDR_WIDTH) - 1, i_inner_count=2)]
        if c.max_log2:
            cases += [dict(i_element_size_log2=1, i_base_address=1),
                      dict(i_element_size_log2=1, i_inner_stride=1),
                      dict(i_mode=2, i_element_size_log2=1, i_outer_stride=1)]
        if c.max_log2 < (1 << c.aliases['ELEMENT_SIZE_WIDTH']) - 1:
            cases.append(dict(i_element_size_log2=c.max_log2 + 1))
        for changes in cases:
            post = await self.configure(self.descriptor(count=1) | changes)
            assert number(post['o_command_failed']) and not number(post['o_command_started'])
            await self.recover()
        for name in DESCRIPTOR:
            for value in ('x', 'z'):
                d = self.descriptor(count=1) | {name: value * c.widths[name]}
                post = await self.configure(d)
                assert number(post['o_error_code']) == 9
                await self.recover()

    async def protocol_faults(self):
        c = self.c
        # Unsolicited response while idle must not report a failed command.
        for field in ('i_mem_rsp_tag', 'i_mem_rsp_error'):
            for bit in ('x', 'z'):
                post = await self.tick('unknown response', i_mem_rsp_valid=1,
                                       **{field: bit * c.widths[field]})
                assert number(post['o_error_code']) == 15 and not number(post['o_command_failed'])
                await self.recover()
        await self.tick('unallocated tag', i_mem_rsp_valid=1, i_mem_rsp_tag=0)
        await self.recover()
        if c.MAX_OUTSTANDING < 1 << c.aliases['TAG_WIDTH']:
            await self.tick('illegal tag', i_mem_rsp_valid=1, i_mem_rsp_tag=c.MAX_OUTSTANDING)
            await self.recover()
        # A response concurrent with its first request is too early: its tag was
        # unallocated before this edge. The newly allocated slot must still drain.
        await self.configure(self.descriptor())
        tag = number(self.last['o_mem_req_tag'])
        await self.tick('same-cycle premature response', i_mem_rsp_valid=1, i_mem_rsp_tag=tag)
        assert number(self.last['o_error_code']) == 13
        await self.drain()
        await self.recover()
        # Malformed control while owners exist cannot discard any of those owners.
        await self.configure(self.descriptor())
        for _ in range(min(3, c.MAX_OUTSTANDING)):
            await self.tick('owners before malformed response', i_stream_ready=0)
        await self.tick('unknown response during command', i_mem_rsp_valid=1,
                        i_mem_rsp_error='x', i_mem_req_ready=0, i_stream_ready=0)
        await self.drain('reverse')
        await self.recover()
        # Duplicate response must preserve the first response and drain all owners.
        await self.configure(self.descriptor())
        for _ in range(c.MAX_OUTSTANDING + 2):
            await self.tick('allocate before fatal', i_stream_ready=0)
        response = self.response('in_order')
        await self.tick('first response', i_stream_ready=0, **response)
        post = await self.tick('duplicate response', i_stream_ready=0, **response)
        assert number(post['o_error_code']) == 14
        await self.tick('prohibited error clear', i_error_clear=1, i_stream_ready=0)
        await self.tick('later fatal preserves first', i_mem_rsp_valid=1, i_mem_rsp_tag='x' * c.aliases['TAG_WIDTH'],
                        i_stream_ready=0)
        await self.drain('reverse')
        await self.recover()
        # Failed reads must not expose unknown response data on the stream.
        self.error_positions = {0}
        await self.configure(self.descriptor(count=1))
        await self.tick('single failed read')
        response = self.response()
        response['i_mem_rsp_data'] = 'x' * c.DATA_WIDTH
        await self.tick('unknown failed-read data', **response)
        await self.drain()
        self.error_positions = set()
        if c.check_internals:
            for issued in sorted({0, 1, min(3, c.MAX_OUTSTANDING)}):
                await self.configure(self.descriptor())
                for _ in range(issued):
                    await self.tick('issue before AGU fault', i_stream_ready=0)
                post = await self.tick('AGU runtime fault', fault=True, i_stream_ready=0)
                assert number(post['o_error_code']) == 11
                await self.tick('release fault', release=True, i_stream_ready=0)
                await self.drain('reverse')
                await self.recover()

    async def random_campaign(self):
        c = self.c
        for cycle in range(c.random_cycles):
            values = dict(i_mem_req_ready=int(self.rng.random() > .3),
                          i_stream_ready=int(self.rng.random() > .4))
            if self.rng.random() > .3:
                values.update(self.response())
            if number(self.last['o_config_ready']):
                mode = self.rng.randrange(3)
                size = self.rng.randrange(c.max_log2 + 1)
                sign = self.rng.choice((-1, 0, 1) if c.ADDR_WIDTH > 1 else (-1, 0))
                self.p.update(self.descriptor(mode, size, count=self.rng.randint(1, 20), sign=sign))
                values['i_config_valid'] = 1
                self.error_positions = {self.rng.randrange(20)}
            await self.tick('random traffic', random=True, **values)
        await self.drain()

    async def body(self):
        await self.reset()
        await self.traffic()
        await self.illegal_descriptors()
        await self.protocol_faults()
        for value in ('x', 'z'):
            await self.tick('unknown config valid', i_config_valid=value)
            await self.tick('unknown response valid', i_mem_rsp_valid=value)
            await self.tick('unknown reset hold', edge=False, i_rstb=value)
            await self.tick('unknown reset edge', i_rstb=value)
        # Coordinated resets in request, response-wait and stream-stall states.
        for phase in range(3):
            await self.configure(self.descriptor())
            if phase:
                await self.tick('request before reset', i_stream_ready=0)
            if phase == 2:
                await self.tick('response before reset', i_stream_ready=0, **self.response())
                for value in ('x', 'z'):
                    await self.tick('unknown stream ready', i_stream_ready=value)
            await self.reset(True)
        await self.random_campaign()
        for _ in range(3):
            await self.tick('final idle')
