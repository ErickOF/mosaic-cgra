"""Persistent independent source, fair consumer and adversarial frame schedules."""
import random
from pyuvm import uvm_sequence
from stream_formatter.model import number
from stream_formatter.transaction import CLAIMS, CONFIG, INPUTS, StreamFormatterItem


class StreamFormatterSequence(uvm_sequence):
    def __init__(self, c):
        super().__init__('stream_formatter_sequence')
        self.c = c
        self.rng = random.Random(c.seed)
        self.p = dict.fromkeys(INPUTS, 0) | dict(i_rstb=1, i_ready=1)
        self.d = self.current = self.last = None
        self.index = 0

    def descriptor(self, length=7, row=None, mode=0, lanes=None):
        length = min(length, (1 << self.c.COUNT_WIDTH) - 1)
        return dict(i_mode=mode, i_frame_beats=length, i_row_beats=min(row or length, length),
                    i_lane_enable=lanes or (1 << self.c.NUM_LANES) - 1,
                    i_datatype=self.rng.getrandbits(self.c.DATATYPE_WIDTH),
                    i_channel_id=self.rng.getrandbits(self.c.CHANNEL_ID_WIDTH),
                    i_context_id=self.rng.getrandbits(self.c.CONTEXT_ID_WIDTH),
                    i_emit_end_of_stream=self.rng.randrange(2))

    def beat(self, mask=None, **changes):
        c, d, index = self.c, self.d, self.index
        row, col = divmod(index, d['i_row_beats'])
        final = index + 1 == d['i_frame_beats']
        mask = self.rng.getrandbits(c.NUM_LANES) if mask is None else mask
        lane_bytes = c.DATA_WIDTH // 8 // c.NUM_LANES
        keep = sum(self.rng.randint(1, (1 << lane_bytes) - 1) << (k * lane_bytes)
                   for k in range(c.NUM_LANES) if mask >> k & 1)
        return dict(i_data=self.rng.getrandbits(c.DATA_WIDTH), i_lane_mask=mask, i_keep=keep,
                    i_first=int(index == 0), i_last=int(final), i_row_first=int(col == 0),
                    i_row_last=int(col + 1 == d['i_row_beats'] or final),
                    i_end_of_stream=int(final and d['i_emit_end_of_stream']),
                    i_stream_datatype=d['i_datatype'], i_stream_channel_id=d['i_channel_id'],
                    i_stream_context_id=d['i_context_id'], i_error=0) | changes

    async def tick(self, label='cycle', *, offer=False, edge=True, random=False, **changes):
        if offer and self.current is None and self.d and self.index < self.d['i_frame_beats']:
            self.current = self.beat()
        ports = self.p | dict(i_config_valid=0, i_valid=int(self.current is not None),
                              i_flush=0, i_error_clear=0)
        if self.current:
            ports.update(self.current)
        ports.update(changes)
        item = StreamFormatterItem(label, ports, edge=edge, random=random)
        await self.start_item(item)
        await self.finish_item(item)
        pre, post = item.pre.ports, item.observation.ports
        if ports['i_rstb'] == 0 and (edge or self.c.ASYNC_RESET) or edge and ports['i_flush'] == 1:
            self.current = self.d = None
            self.index = 0
        elif edge and ports['i_rstb'] == 1:
            if number(pre['o_config_ready']) and ports['i_config_valid'] == 1:
                self.index = 0
                self.current = None
            if number(pre['o_ready']) and ports['i_valid'] == 1:
                self.index += 1
                self.current = None
        self.last = post
        return post

    async def reset(self):
        await self.tick('reset_hold', edge=False, i_rstb=0)
        await self.tick('reset', i_rstb=0)
        await self.tick('release')

    async def configure(self, d):
        assert self.current is None
        self.p.update(d)
        self.d = d
        post = await self.tick('configure', i_config_valid=1)
        assert number(post['o_frame_started']) or number(post['o_error'])
        if number(post['o_error']):
            self.d = None
        return post

    async def drain(self, adversarial=False):
        limit = (self.d['i_frame_beats'] if self.d else 1) * 20 + 100
        for _ in range(limit):
            await self.tick('drain', offer=not adversarial or self.rng.random() > .3,
                            i_ready=int(not adversarial or self.rng.random() > .3))
            if not number(self.last['o_busy']):
                assert self.current is None
                return
        raise AssertionError('Fair producer/consumer did not finish')

    async def frames(self):
        c = self.c
        maximum = (1 << c.COUNT_WIDTH) - 1
        for mode in (0, 1):
            for length in sorted({1, min(2, maximum), min(7, maximum)}):
                for row in sorted({1, length, min(3, length)}):
                    await self.configure(self.descriptor(length, row, mode))
                    await self.drain(True)
        # Exact maximum supported count exercises terminal comparison without wrap.
        await self.configure(self.descriptor(maximum, min(7, maximum)))
        await self.drain()
        for lanes in range(1, 1 << c.NUM_LANES):
            await self.configure(self.descriptor(1, mode=lanes % 2, lanes=lanes))
            self.current = self.beat(mask=(1 << c.NUM_LANES) - 1)
            await self.drain()
        for mask in range(1 << c.NUM_LANES):
            await self.configure(self.descriptor(1, mode=1))
            self.current = self.beat(mask=mask)
            await self.drain()
        # Explicit full, one-byte and alternating sparse keep; inactive bytes X/Z.
        for keep in ((1 << (c.DATA_WIDTH // 8)) - 1, 1, sum(1 << b for b in range(0, c.DATA_WIDTH // 8, 2))):
            for state in 'xz':
                await self.configure(self.descriptor(1, mode=1))
                lane_bytes = c.DATA_WIDTH // 8 // c.NUM_LANES
                mask = sum(1 << k for k in range(c.NUM_LANES) if keep >> (k * lane_bytes) & ((1 << lane_bytes) - 1))
                data = ''.join(f'{self.rng.getrandbits(8):08b}' if keep >> b & 1 else state * 8
                               for b in reversed(range(c.DATA_WIDTH // 8)))
                self.current = self.beat(mask=mask, i_keep=keep, i_data=data)
                await self.drain()
        # One final upstream error must contribute even without an older sticky bit.
        for position in sorted({0, min(1, maximum - 1), min(2, maximum - 1)}):
            await self.configure(self.descriptor(min(3, maximum), mode=1))
            while self.index < self.d['i_frame_beats']:
                self.current = self.beat(mask=1, i_error=int(self.index == position))
                await self.tick('input_error')
                if self.current is not None:
                    # Capacity stalls preserve the same source beat.
                    await self.tick('input_error_hold')
            await self.drain()
            assert number(self.last['o_completed_with_error']) or number(self.last['o_frame_completed']) == 0

    async def faults(self):
        c = self.c
        for mode in (0, 1):
            for field in CLAIMS:
                await self.configure(self.descriptor(1, mode=mode))
                beat = self.beat(mask=1)
                beat['i_' + field] ^= 1
                self.current = beat
                await self.drain()
                assert number(self.last['o_format_error_seen']) == mode
            for change in ({'i_lane_mask': 0, 'i_keep': 0}, {'i_lane_mask': 1, 'i_keep': 0},
                           {'i_lane_mask': 0, 'i_keep': 1}):
                await self.configure(self.descriptor(1, mode=mode))
                self.current = self.beat(mask=1, **change)
                await self.drain()
            for field in ('lane_mask', 'keep', 'error', *CLAIMS):
                name = 'i_' + field
                for state in 'xz':
                    await self.configure(self.descriptor(1, mode=mode))
                    self.current = self.beat(mask=1, **{name: state * c.widths[name]})
                    await self.drain()
                    assert number(self.last['o_format_error_seen']) == int(mode or field in ('lane_mask', 'keep', 'error'))
            await self.configure(self.descriptor(1, mode=mode))
            beat = self.beat(mask=1, i_keep=0, i_error=1)
            for field in CLAIMS:
                beat['i_' + field] ^= 1
            self.current = beat
            await self.drain()
        cases = [dict(i_frame_beats=0), dict(i_row_beats=0), dict(i_lane_enable=0)]
        if c.COUNT_WIDTH > 1:
            cases.append(dict(i_frame_beats=1, i_row_beats=2))
        for field in CONFIG:
            cases.extend({field: state * c.widths[field]} for state in 'xz')
        for change in cases:
            await self.configure(self.descriptor(1) | change)
            code = number(self.last['o_config_error_code'])
            await self.tick('sticky', i_config_valid=1)
            assert number(self.last['o_config_error_code']) == code
            await self.tick('flush_preserves_config_error', i_flush=1, i_error_clear=1)
            assert number(self.last['o_config_error_code']) == code
            await self.tick('clear', i_error_clear=1)
            assert not number(self.last['o_error'])

    async def recovery(self):
        for phase in ('idle', 'active', 'buffered', 'final_buffered'):
            if phase != 'idle':
                await self.configure(self.descriptor(1 if phase == 'final_buffered' else 7))
                if phase in ('buffered', 'final_buffered'):
                    await self.tick('before_flush', offer=True, i_ready=0)
            await self.tick('clockless_flush', edge=False, i_flush=1)
            await self.tick('flush', i_flush=1, i_valid=1, i_ready=1, i_config_valid=1)
            await self.tick('flush_held', i_flush=1)
            await self.tick('after_flush')
            assert number(self.last['o_idle'])
        for phase in ('idle', 'active', 'buffered'):
            if phase != 'idle':
                await self.configure(self.descriptor(7))
                if phase == 'buffered':
                    await self.tick('before_reset', offer=True, i_ready=0)
            await self.reset()
        await self.configure(self.descriptor(7, row=2, mode=1))
        for state in (0, 'x', 'z'):
            for _ in range(5):
                await self.tick('blocked', offer=True, i_ready=state, i_error_clear=1)
                await self.tick('clockless_hold', edge=False, i_ready=state)
        await self.drain()
        for field in ('i_config_valid', 'i_valid', 'i_flush', 'i_rstb'):
            for state in 'xz':
                await self.tick('unknown_idle_control', **{field: state})
        # Unknown reset/flush while an output is held must freeze, then recover.
        await self.configure(self.descriptor(7))
        await self.tick('pending', offer=True, i_ready=0)
        for field in ('i_flush', 'i_rstb'):
            for state in 'xz':
                await self.tick('unknown_active_control', i_ready=0, **{field: state})
        await self.drain()

    async def random_campaign(self):
        for _ in range(self.c.random_cycles):
            values = dict(i_ready=int(self.rng.random() > .35))
            if number(self.last['o_config_ready']):
                d = self.descriptor(self.rng.randint(1, 20), self.rng.randint(1, 5), self.rng.randrange(2),
                                    self.rng.randrange(1, 1 << self.c.NUM_LANES))
                self.p.update(d)
                self.d, self.index = d, 0
                values['i_config_valid'] = 1
            if (not values.get('i_config_valid') and self.current is None and self.d and
                    self.index < self.d['i_frame_beats'] and self.rng.random() > .3):
                self.current = self.beat()
                if self.rng.random() < .3:
                    field = self.rng.choice(CLAIMS)
                    self.current['i_' + field] ^= 1
                if self.rng.random() < .1:
                    self.current['i_error'] = 1
            await self.tick('random', random=True, **values)
        await self.drain()

    async def body(self):
        await self.reset()
        if self.c.probe:
            byte, state = self.c.probe.split(':')
            await self.configure(self.descriptor(1))
            data = list('0' * self.c.DATA_WIDTH)
            data[-1 - 8 * int(byte)] = state
            self.current = self.beat(mask=(1 << self.c.NUM_LANES) - 1,
                                     i_keep=(1 << (self.c.DATA_WIDTH // 8)) - 1, i_data=''.join(data))
            await self.tick('selected_byte_probe')
            await self.tick('probe_output')
            raise AssertionError('Selected-byte checker did not reject unknown data')
        await self.frames()
        await self.faults()
        await self.recovery()
        await self.random_campaign()
        for _ in range(3):
            await self.tick('idle')
