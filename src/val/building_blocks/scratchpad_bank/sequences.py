"""Persistent requester, independent response stalls, SEUs and coordinated recovery."""
import random
from pyuvm import uvm_sequence
from scratchpad_bank.model import number
from scratchpad_bank.transaction import INPUTS, ScratchpadBankItem


class ScratchpadBankSequence(uvm_sequence):
    def __init__(self, c):
        super().__init__('scratchpad_bank_sequence')
        self.c = c
        self.rng = random.Random(c.seed)
        self.p = dict.fromkeys(INPUTS, 0) | dict(i_rstb=1, i_rsp_ready=1)
        self.current = self.last = None
        self.issue_slot = self.last_slot = 0

    def request(self, write=False, word=0, size=None, offset=0, mask=None, data=None):
        c = self.c
        size = c.byte_log if size is None else size
        return dict(i_req_write=int(write), i_req_address=word * c.bytes + offset,
                    i_req_size_log2=size, i_req_wdata=self.rng.getrandbits(c.DATA_WIDTH) if data is None else data,
                    i_req_wstrobe=((1 << (1 << size)) - 1) if mask is None else mask,
                    i_req_tag=self.rng.getrandbits(c.TAG_WIDTH))

    async def tick(self, label='cycle', *, edge=True, random=False, fault=None, protocol=None, **changes):
        ports = self.p | dict(i_req_valid=int(self.current is not None), i_flush=0, i_error_clear=0)
        if self.current:
            ports.update(self.current)
        ports.update(changes)
        item = ScratchpadBankItem(label, ports, edge=edge, random=random, fault=fault, protocol=protocol)
        await self.start_item(item)
        await self.finish_item(item)
        pre, post = item.pre.ports, item.observation.ports
        if ports['i_rstb'] == 0 and (edge or self.c.ASYNC_RESET) or edge and ports['i_flush'] == 1:
            self.current = None
            self.issue_slot = 0
        elif edge and ports['i_rstb'] == 1 and number(pre['o_req_ready']) and ports['i_req_valid'] == 1:
            self.current = None
            self.last_slot = self.issue_slot
            self.issue_slot = (self.issue_slot + 1) % self.c.MAX_OUTSTANDING
        self.last = post
        return item

    async def send(self, request, **changes):
        assert self.current is None
        self.current = request
        for _ in range(200):
            item = await self.tick('request', **changes)
            if self.current is None:
                return item
        raise AssertionError('Fair request did not accept')

    async def drain(self):
        for _ in range(200):
            await self.tick('drain')
            if number(self.last['o_busy']) == 0 and self.current is None:
                return
        raise AssertionError('Fair response peer did not drain')

    async def transaction(self, request):
        item = await self.send(request)
        await self.drain()
        return item

    async def reset(self):
        await self.tick('clockless_reset', edge=False, i_rstb=0)
        await self.tick('reset', i_rstb=0)
        await self.tick('release')

    async def flush(self):
        await self.tick('clockless_flush', edge=False, i_flush=1)
        await self.tick('flush', i_flush=1)
        assert number(self.last['o_flush_completed']) == 1
        await self.tick('held_flush', i_flush=1)
        assert number(self.last['o_flush_completed']) == 0
        await self.tick('after_flush')

    async def initialize(self):
        # Unwritten words are deliberately tested before any initialization.
        await self.transaction(self.request(word=self.c.DEPTH_WORDS - 1))
        for word in range(self.c.DEPTH_WORDS):
            await self.send(self.request(True, word))
        await self.drain()

    async def addressing(self):
        c = self.c
        for size in range(c.byte_log + 1):
            for offset in range(0, c.bytes, 1 << size):
                for mask in {(1 << (1 << size)) - 1, 1, 0,
                             sum(1 << n for n in range(0, 1 << size, 2))}:
                    await self.send(self.request(True, size=size, offset=offset, mask=mask))
                    await self.send(self.request(size=size, offset=offset))
        await self.drain()
        for _ in range(4):
            for write in (False, True, True, False):
                await self.send(self.request(write))
        await self.drain()
        for _ in range(c.MAX_OUTSTANDING):
            await self.send(self.request(True), i_rsp_ready=0)
        assert number(self.last['o_outstanding']) == c.MAX_OUTSTANDING
        self.current = self.request()
        for _ in range(12):
            await self.tick('full_stall', i_rsp_ready=0, i_error_clear=1)
        while self.current:
            await self.tick('resume')
        await self.drain()
        if c.MAX_OUTSTANDING > 1:
            await self.send(self.request(), i_rsp_ready=0)
            await self.send(self.request(True), i_rsp_ready=0)
            await self.drain()
        # Masked-off data may be unknown; reads ignore their write-only controls.
        for state in 'xz':
            await self.transaction(self.request(True, size=0, mask=1,
                data=state * (c.DATA_WIDTH - 8) + '10100101'))
            r = self.request()
            r.update(i_req_wdata=state * c.DATA_WIDTH, i_req_wstrobe=state * c.bytes)
            await self.transaction(r)

    async def illegal(self):
        c = self.c
        changes = []
        if c.DEPTH_WORDS * c.bytes < 1 << c.aliases['A']:
            changes.append(dict(i_req_address=c.DEPTH_WORDS * c.bytes))
        if c.byte_log < (1 << c.aliases['S']) - 1:
            changes.append(dict(i_req_size_log2=c.byte_log + 1))
        if c.bytes >= 2:
            changes.extend((dict(i_req_address=c.bytes - 1, i_req_size_log2=1),
                            dict(i_req_size_log2=0, i_req_wstrobe=2)))
        if c.bytes >= 4:
            changes.append(dict(i_req_address=1, i_req_size_log2=1))
        for write in (False, True):
            for change in changes:
                if 'i_req_wstrobe' not in change or write:
                    await self.transaction(self.request(write) | change)
        for field in ('i_req_write', 'i_req_address', 'i_req_size_log2', 'i_req_tag', 'i_req_wstrobe'):
            for state in 'xz':
                await self.transaction(self.request(True) | {field: state * c.widths[field]})
        for state in 'xz':
            await self.tick('unknown_valid', i_req_valid=state)
            await self.send(self.request(), i_rsp_ready=0)
            for _ in range(c.BACKEND_READ_LATENCY + 4):
                await self.tick('unknown_ready', i_rsp_ready=state)
            await self.drain()

    async def faults(self):
        c = self.c
        if not c.check_internals:
            return
        for bit in range(c.stored_width):
            await self.transaction(self.request(True))
            await self.tick('single_bit_fault', fault=(0, 1 << bit, ''))
            await self.transaction(self.request())
        await self.transaction(self.request(True))
        for state in ('xz' if c.PROTECTION_MODE else ''):
            await self.tick('unknown_storage', fault=(0, 1, state))
            await self.transaction(self.request())
            await self.transaction(self.request(True))
        if c.PROTECTION_MODE == 2:
            for mask in {3, 5, (1 << (c.stored_width - 1)) | 1, (1 << (c.stored_width - 2)) | 2}:
                await self.transaction(self.request(True))
                await self.tick('double_bit_fault', fault=(0, mask, ''))
                await self.transaction(self.request())
                if c.bytes > 1:
                    await self.transaction(self.request(True, size=0, mask=1))
            if c.bytes > 1:
                await self.transaction(self.request(True))
                await self.tick('correctable_old_rmw', fault=(0, 1, ''))
                await self.transaction(self.request(True, size=0, mask=1))
        if c.PROTECTION_MODE == 1:
            # Even parity has no guarantee against a same-granule two-bit error.
            await self.transaction(self.request(True))
            await self.tick('parity_even_fault', fault=(0, 3, ''))
            await self.transaction(self.request())
            if c.PARITY_GRANULARITY > 8:
                await self.transaction(self.request(True))
                await self.tick('bad_old_parity_rmw', fault=(0, 1 << 8, ''))
                await self.transaction(self.request(True, size=0, mask=1))
                await self.transaction(self.request(True, size=(c.PARITY_GRANULARITY // 8).bit_length() - 1))
            if c.PARITY_GRANULARITY < c.DATA_WIDTH:
                await self.transaction(self.request(True))
                await self.tick('unrelated_granule_fault', fault=(0, 1, ''))
                await self.transaction(self.request(size=0, offset=c.PARITY_GRANULARITY // 8))
        await self.transaction(self.request(True))
        # An offered write cannot pass a correcting read or later scrub.
        if c.PROTECTION_MODE == 2:
            await self.tick('before_scrub_race', fault=(0, 1, ''))
            await self.send(self.request())
            await self.send(self.request(True))
            await self.drain()
            await self.transaction(self.request())

    async def recovery(self):
        c = self.c
        await self.flush()
        await self.send(self.request(True), i_rsp_ready=0)
        await self.flush()
        await self.transaction(self.request())
        await self.send(self.request(), i_rsp_ready=0)
        await self.flush()
        rmw_possible = c.bytes > 1 and (c.PROTECTION_MODE == 2 or c.PROTECTION_MODE == 1 and c.PARITY_GRANULARITY > 8)
        if rmw_possible:
            for at_commit in (False, True):
                await self.transaction(self.request(True))
                await self.send(self.request(True, size=0, mask=1), i_rsp_ready=0)
                if at_commit:
                    for _ in range(c.BACKEND_READ_LATENCY + 1):
                        await self.tick('rmw_wait', i_rsp_ready=0)
                await self.flush()
                await self.transaction(self.request())
        await self.reset()
        await self.send(self.request(True), i_rsp_ready=0)
        await self.reset()
        await self.transaction(self.request())
        if rmw_possible:
            await self.send(self.request(True, size=0, mask=1))
            await self.reset()
            await self.transaction(self.request())
        for field in ('i_rstb', 'i_flush'):
            for state in 'xz':
                await self.send(self.request(), i_rsp_ready=0)
                for _ in range(c.BACKEND_READ_LATENCY + 3):
                    await self.tick('unknown_global_control', i_rsp_ready=0, **{field: state})
                await self.drain()
        if c.check_internals:
            for protocol in ({'backend_rsp_valid': 1, 'backend_rsp_tag': 0},
                             {'backend_rsp_valid': 'x'}, {'backend_rsp_valid': 'z'}):
                await self.tick('internal_protocol_fault', protocol=protocol)
                assert number(self.last['o_error_code']) == 9
                await self.tick('first_internal_error')
                await self.tick('clear_internal_error', i_error_clear=1)
                assert number(self.last['o_error']) == 0
            await self.send(self.request(), i_rsp_ready=0)
            for _ in range(c.BACKEND_READ_LATENCY + 2):
                await self.tick('wait_duplicate_target', i_rsp_ready=0)
            # Its live slot is still owned, but its backend result is already stored.
            await self.tick('duplicate_result', i_rsp_ready=0,
                            protocol={'backend_rsp_valid': 1, 'backend_rsp_tag': self.last_slot})
            await self.tick('busy_clear_ignored', i_error_clear=1, i_rsp_ready=0)
            assert number(self.last['o_error'])
            await self.drain()
            await self.tick('quiescent_clear', i_error_clear=1)
            assert number(self.last['o_error']) == 0
        await self.transaction(self.request(True))

    async def random_campaign(self):
        c = self.c
        for index in range(c.random_cycles):
            fault = None
            changes = dict(i_rsp_ready=int(self.rng.random() > .3))
            if index == 0 and c.check_internals:
                self.current = self.request()
                fault = (0, 1, '')
            elif index > c.BACKEND_READ_LATENCY + 8 and self.rng.random() < .025:
                changes['i_flush'] = 1
            elif self.current is None and self.rng.random() > .25:
                size = self.rng.randrange(c.byte_log + 1)
                word = self.rng.randrange(c.DEPTH_WORDS)
                offset = self.rng.randrange(c.bytes // (1 << size)) * (1 << size)
                mask = self.rng.choice((0, (1 << (1 << size)) - 1, self.rng.getrandbits(1 << size)))
                self.current = self.request(bool(self.rng.randrange(2)), word, size, offset, mask)
            await self.tick('random', random=True, fault=fault, **changes)
        await self.drain()

    async def body(self):
        await self.reset()
        if self.c.probe.startswith('read:'):
            await self.transaction(self.request(True))
            await self.tick('unknown_initialized_word', fault=(0, 1, self.c.probe.split(':')[1]))
            await self.transaction(self.request())
            raise AssertionError('Initialized-read checker did not reject unknown data')
        if self.c.probe:
            bit, state = self.c.probe.split(':')
            data = list('0' * self.c.DATA_WIDTH)
            data[-1 - int(bit)] = state
            self.current = self.request(True, data=''.join(data))
            await self.tick('unknown_selected_write')
            raise AssertionError('Selected-write checker did not reject unknown input')
        await self.initialize()
        await self.addressing()
        await self.illegal()
        await self.faults()
        await self.recovery()
        await self.random_campaign()
        for _ in range(3):
            await self.tick('idle')
