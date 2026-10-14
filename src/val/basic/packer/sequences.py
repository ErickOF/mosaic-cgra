"""Numerical boundaries, mode/mask sweeps, legal stalls and seeded traffic."""

from itertools import product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from packer.model import boundary_values
from packer.transaction import FRAME_INPUTS, INPUTS, PackerItem


class PackerSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('packer_sequence')
        self.config = config
        self.rng = random.Random(config.seed)
        self.ports = {name: '0' * config.widths[name] for name in INPUTS}
        self.index = 0

    async def send(self, label, *, edge=True, random=False, **changes):
        for name, value in changes.items():
            self.ports[name] = bits(value, self.config.widths[name])
        item = PackerItem(label, self.ports, edge=edge, random=random)
        await self.start_item(item)
        await self.finish_item(item)
        return item

    def frame(self, mode=(0, 0, 0), *, mask=None, value=None, last=None, user=None, invalid_unknown=None):
        config = self.config
        self.index += 1
        mask = (1 << config.elements) - 1 if mask is None else mask
        words = []
        for lane in range(config.elements):
            data = self.rng.getrandbits(config.source_width) if value is None else value
            words.append(invalid_unknown * config.source_width if invalid_unknown and not mask & (1 << lane) else bits(data, config.source_width))
        return dict(i_valid=1, i_data=''.join(reversed(words)), i_lane_valid=mask,
                    i_signed=mode[0], i_saturate=mode[1], i_reverse=mode[2],
                    i_last=self.index % 2 if last is None else last,
                    i_user=self.rng.getrandbits(config.user_width) if user is None else user)

    async def reset(self):
        await self.send('reset_edge', i_rstb=0, i_flush=0, i_ready=1, **self.frame())
        await self.send('reset_release', edge=False, i_rstb=1, i_valid=0, i_ready=1)

    async def drain(self):
        await self.send('drain', i_rstb=1, i_flush=0, i_valid=0, i_ready=1)

    async def conversions(self):
        config = self.config
        maximum = (1 << config.elements) - 1
        masks = (range(1 << config.elements) if config.elements <= 4 else sorted(
            {0, maximum, sum(1 << lane for lane in range(0, config.elements, 2))} |
            {1 << lane for lane in range(config.elements)} | {maximum ^ (1 << lane) for lane in range(config.elements)}))
        for mode in config.modes:
            for value in boundary_values(config, mode[0]):
                await self.send('numerical_boundary', i_ready=1, **self.frame(mode, value=value))
            if config.source_width <= 4:
                for value in range(1 << config.source_width):
                    await self.send('exhaustive_small_element', i_ready=1, **self.frame(mode, value=value))
            for mask in masks:
                await self.send('mode_mask_cross', i_ready=1, **self.frame(mode, mask=mask))
            for state, lane in product('xz', range(config.elements)):
                await self.send('invalid_lane_unknown', i_ready=1,
                                **self.frame(mode, mask=maximum ^ (1 << lane), invalid_unknown=state))
            for last, zero in product((0, 1), repeat=2):
                await self.send('last_metadata_cross', i_ready=1,
                                **self.frame(mode, last=last, user=0 if zero else (1 << config.user_width) - 1))
        await self.drain()
        for state in 'xz':
            changes = {name: state * config.widths[name] for name in FRAME_INPUTS if name != 'i_valid'}
            await self.send('ignored_idle_fields', i_valid=0, i_ready=1, **changes)
        await self.drain()

    async def backpressure(self):
        for last in (0, 1):
            if self.config.registered:
                await self.send('fill_before_stall', i_ready=0, **self.frame(last=last))
            frame = self.frame(last=last)
            for _ in range(64):
                await self.send('prolonged_stall', i_ready=0, **frame)
            await self.send('consume_replace', i_ready=1, **frame)
            await self.drain()
        for _ in range(20):
            await self.send('peak_stream', i_ready=1, **self.frame(self.rng.choice(self.config.modes)))
        await self.drain()

    async def illegal_modes(self):
        for mode in sorted(set(product((0, 1), repeat=3)) - set(self.config.modes)):
            await self.reset()
            if self.config.registered:
                await self.send('old_legal_result', i_ready=0, **self.frame())
            frame = self.frame(mode)
            await self.send('illegal_stalled', i_ready=0, **frame)
            await self.send('illegal_old_result_drains', i_ready=1, **frame)
            # Illegal input remains a held request until flush cancels it.
            await self.send('cancel_illegal_request', i_flush=1, i_valid=0)
            await self.send('release_error', i_flush=0, i_valid=0)

    async def cancellation(self):
        for occupied in range(1 + self.config.registered):
            for kind in ('reset', 'flush'):
                await self.reset()
                if occupied:
                    await self.send('fill_cancel', i_ready=0, **self.frame())
                control = dict(i_rstb=0) if kind == 'reset' else dict(i_flush=1)
                await self.send('pulse_' + kind, edge=False, i_valid=0, **control)
                await self.send('release_pulse', edge=False, i_rstb=1, i_flush=0, i_valid=0)
                await self.drain()
                if occupied:
                    await self.send('refill_cancel', i_ready=0, **self.frame())
                await self.send('cancel_attempted_replacement', i_ready=1, **self.frame(), **control)
                await self.send('release_cancel', i_rstb=1, i_flush=0, i_valid=0)
        # A flush must also cancel a valid output while downstream is stalled.
        if self.config.registered:
            await self.send('fill_stalled_flush', i_ready=0, **self.frame())
            await self.send('flush_stalled', i_flush=1, i_valid=1, i_ready=0)
            await self.send('release_stalled_flush', i_flush=0, i_valid=0, i_ready=1)

    async def randomized(self):
        held = None
        for index in range(self.config.random_cycles):
            reset = self.rng.randrange(127) == 0
            flush = not reset and self.rng.randrange(71) == 0
            frame = held if held is not None else self.frame(self.rng.choice(self.config.modes), mask=self.rng.getrandbits(self.config.elements))
            if held is None:
                frame['i_valid'] = int(self.rng.randrange(4) != 0)
            item = await self.send(f'random:{index}', random=True, i_rstb=int(not reset), i_flush=int(flush),
                                   i_ready=int(self.rng.randrange(3) != 0), **frame)
            held = (frame if not reset and not flush and frame['i_valid'] and item.pre.ports['o_ready'] == '0' else None)
        if held is not None:
            await self.send('finish_held_request', i_rstb=1, i_flush=0, i_ready=1, **held)
        await self.drain()

    async def probe(self):
        field, state = self.config.probe.split(':')
        if field == 'input_stability':
            if self.config.registered:
                await self.send('probe_fill', i_ready=0, **self.frame())
            await self.send('probe_stall', i_ready=0, **self.frame())
            await self.send('probe_changed_' + state, **{state: int(self.ports[state], 2) ^ 1})
        else:
            if self.config.registered:
                await self.send('probe_live_state', i_ready=0, **self.frame())
            frame = self.frame()
            frame.update({field: state * self.config.widths[field]})
            frame.setdefault('i_ready', 1)
            await self.send('probe_unknown_' + field, **frame)
        assert False, 'Protocol probe was not detected'

    async def body(self):
        await self.reset()
        if self.config.probe:
            await self.probe()
            return
        await self.conversions()
        await self.backpressure()
        await self.illegal_modes()
        await self.cancellation()
        await self.randomized()
