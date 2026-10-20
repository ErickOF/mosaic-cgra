"""Deterministic lane/offset sweeps, legal producer stalls and seeded traffic."""

import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from data_aligner.coverage import patterns
from data_aligner.transaction import AlignerItem, FRAME_INPUTS, INPUTS


class AlignerSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('data_aligner_sequence')
        self.config = config
        self.rng = random.Random(config.seed)
        self.ports = {name: '0' * config.widths[name] for name in INPUTS}
        self.index = 0

    async def send(self, label, *, random=False, **changes):
        for name, value in changes.items():
            self.ports[name] = bits(value, self.config.widths[name])
        item = AlignerItem(label, self.ports, random=random)
        await self.start_item(item)
        await self.finish_item(item)
        return item

    async def cycle(self, label, *, random=False, **changes):
        await self.send(label + ':prepare', i_clk=0, **changes)
        return await self.send(label, i_clk=1, random=random)

    def frame(self, *, direction=None, offset=0, mask=None, last=None, unknown=None):
        config = self.config
        n = config.word_bytes
        self.index += 1
        mask = (1 << (2*n))-1 if mask is None else mask
        # Byte identities distinguish source lanes even in the largest profile.
        data = [bits((lane + 17*self.index) % 256, 8) if mask & (1 << lane) or unknown is None else unknown * 8 for lane in range(2*n)]
        return dict(i_valid=1, i_data_lo=''.join(reversed(data[:n])), i_data_hi=''.join(reversed(data[n:])),
                    i_strb_lo=mask & ((1 << n)-1), i_strb_hi=mask >> n, i_offset=offset,
                    i_shift_high=config.directions[0] if direction is None else direction,
                    i_last=self.index % 2 if last is None else last,
                    i_user=self.rng.getrandbits(config.user_width))

    async def transfer(self, label, **frame):
        item = await self.cycle(label, i_rstb=1, i_flush=0, i_ready=1, **frame)
        assert item.pre.ports['o_ready'] == '1', 'Ready producer failed to make progress'
        return item

    async def drain(self):
        await self.cycle('drain', i_rstb=1, i_flush=0, i_valid=0, i_ready=1)

    async def reset(self):
        await self.cycle('reset', i_rstb=0, i_flush=0, i_valid=0, i_ready=0)
        await self.send('reset_release', i_clk=0, i_rstb=1)

    async def offsets_and_lanes(self):
        config = self.config
        for direction in config.directions:
            for offset in range(config.word_bytes):
                for mask in patterns(2*config.word_bytes):
                    await self.transfer('strobe_offset', **self.frame(direction=direction, offset=offset, mask=mask))
            for source in range(2*config.word_bytes):
                for offset in sorted({0, config.word_bytes-1}):
                    await self.transfer('single_byte', **self.frame(direction=direction, offset=offset, mask=1 << source))
            for state in ('x', 'z'):
                for mask in (0, 1, 1 << (2*config.word_bytes-1)):
                    await self.transfer('unstrobed_unknown', **self.frame(direction=direction, offset=config.word_bytes-1, mask=mask, unknown=state))
        for _ in range(16):
            await self.transfer('peak_rate', **self.frame())
        await self.drain()
        for state in ('x', 'z'):
            ignored = {name: state * self.config.widths[name] for name in FRAME_INPUTS if name != 'i_valid'}
            await self.cycle('ignored_idle_controls', i_valid=0, i_ready=1, **ignored)

    async def backpressure(self):
        for last in (0, 1):
            if self.config.registered:
                frame = self.frame(last=last)
                await self.cycle('fill_stall', i_rstb=1, i_flush=0, i_ready=0, **frame)
            frame = self.frame(last=last)
            for _ in range(64):
                await self.cycle('prolonged_stall', i_ready=0, **frame)
            await self.cycle('consume_replace', i_ready=1, **frame)
            await self.drain()

    async def cancel_and_errors(self):
        # Idle configuration controls are ignored. Live illegal requests remain
        # stable until flush cancels the producer's stalled request.
        invalid = [(offset, self.config.directions[0]) for offset in range(self.config.word_bytes, 1 << self.config.offset_width)]
        invalid += [(0, direction) for direction in (0, 1) if direction not in self.config.directions]
        for offset, direction in invalid:
            await self.cycle('inactive_configuration', i_valid=0, i_offset=offset, i_shift_high=direction, i_ready=1)
            if self.config.registered:
                await self.cycle('fill_before_error', i_ready=0, **self.frame())
            frame = self.frame(offset=offset, direction=direction)
            await self.cycle('illegal_stalled', i_ready=0, **frame)
            await self.cycle('illegal_drain', i_ready=1, **frame)
            await self.cycle('cancel_illegal', i_flush=1)
            await self.cycle('release_illegal', i_flush=0, i_valid=0)
        await self.cycle('flush_idle', i_flush=1, i_valid=0)
        await self.cycle('release_idle', i_flush=0)
        if self.config.registered:
            for ready in (0, 1):
                await self.cycle('fill_flush', i_ready=0, **self.frame())
                await self.cycle('flush_buffered', i_flush=1, i_ready=ready, **self.frame())
                await self.cycle('release_flush', i_flush=0, i_valid=0, i_ready=1)
            await self.cycle('fill_reset', i_ready=0, **self.frame())
            # Assert and release without an edge first: only the asynchronous
            # profile may erase the stored payload and occupancy at this point.
            await self.send('reset_between_edges', i_clk=0, i_rstb=0, i_valid=0)
            await self.send('reset_pulse_release', i_clk=0, i_rstb=1)
        await self.reset()
        await self.drain()

    async def randomized(self):
        held = None
        config = self.config
        for index in range(config.random_cycles):
            reset = self.rng.randrange(97) == 0
            flush = not reset and self.rng.randrange(53) == 0
            if held is None:
                direction = self.rng.choice(config.directions)
                frame = self.frame(direction=direction, offset=self.rng.randrange(config.word_bytes),
                                   mask=self.rng.getrandbits(2*config.word_bytes),
                                   unknown=self.rng.choice((None, 'x', 'z')))
                frame['i_valid'] = int(self.rng.randrange(5) != 0)
            else:
                frame = held
            item = await self.cycle(f'random:{index}', random=True, i_rstb=int(not reset), i_flush=int(flush),
                                    i_ready=int(self.rng.randrange(4) == 0), **frame)
            held = ({name: self.ports[name] for name in FRAME_INPUTS}
                    if not reset and not flush and self.ports['i_valid'] == '1' and item.pre.ports['o_ready'] == '0' else None)
        if held:
            await self.cycle('finish_held', i_rstb=1, i_flush=0, i_ready=1, **held)
        await self.drain()

    async def probe(self):
        field, state = self.config.probe.split(':')
        frame = self.frame()
        if field == 'input_stability':
            if self.config.registered:
                await self.cycle('probe_fill', i_ready=0, **frame)
                frame = self.frame()
            await self.cycle('probe_stall', i_ready=0, **frame)
            await self.send('probe_instability', i_clk=0, i_user=int(self.ports['i_user'], 2) ^ 1)
        else:
            request = dict(frame, i_clk=0, i_rstb=1, i_flush=0, i_ready=1)
            request[field] = state * self.config.widths[field]
            await self.send('unknown_probe', **request)
        assert False, 'Protocol probe was not detected'

    async def body(self):
        await self.reset()
        if self.config.probe:
            await self.probe()
            return
        await self.offsets_and_lanes()
        await self.backpressure()
        await self.cancel_and_errors()
        await self.randomized()
