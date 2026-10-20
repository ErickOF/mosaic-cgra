"""Directed positional coverage and protocol-correct seeded stream traffic."""

import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from width_converter.config import LONG_STALL, STALL_LIMIT, STREAM_LENGTH
from width_converter.transaction import WidthConverterItem


class WidthConverterSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('width_converter_sequence')
        self.config = config
        self.rng = random.Random(config.seed)
        self.position = 0
        self.group_user = 0
        self.serial = 0
        self.latest = None

    def data(self, keep=None, user=None, last=1):
        c = self.config
        self.serial += 1
        keep = (1 << c.in_units)-1 if keep is None else keep
        # Different physical unit patterns make reversals and compaction visible.
        data = sum(((self.serial*37 + unit*19) & ((1 << c.unit_width)-1)) << (unit*c.unit_width)
            for unit in range(c.in_units))
        if user is None:
            user = self.group_user if c.mode == 'pack' and self.position else self.serial & ((1 << c.user_width)-1)
        return dict(i_data=data, i_keep=keep, i_last=last, i_user=user)

    async def cycle(self, label, beat=None, *, valid=None, ready=1, rstb=1, flush=0, edge=True, random=False, pulse='', **overrides):
        c = self.config
        ports = dict(i_rstb=rstb, i_flush=flush, i_valid=int(beat is not None) if valid is None else valid,
            i_data='x'*c.input_width, i_keep=0, i_last='x', i_user='z'*c.user_width, i_ready=ready)
        if beat is not None:
            ports.update(beat)
        ports.update(overrides)
        item = WidthConverterItem(label, {name: bits(value, c.widths[name]) for name, value in ports.items()},
            edge=edge, random=random, pulse=pulse)
        await self.start_item(item)
        await self.finish_item(item)
        self.latest = item.observation.ports
        if edge:
            if rstb == 0 or flush == 1:
                self.position = 0
            elif item.pre.ports['i_valid'] == item.pre.ports['o_ready'] == '1':
                if c.mode == 'pack':
                    if self.position == 0:
                        self.group_user = int(item.pre.ports['i_user'], 2)
                    self.position = 0 if item.pre.ports['i_last'] == '1' or self.position == c.ratio-1 else self.position+1
        elif rstb == 0 and c.asynchronous:
            self.position = 0
        return item

    async def push(self, beat, label='push', ready=1):
        for _ in range(self.config.ratio+4):
            item = await self.cycle(label, beat, ready=ready)
            if item.pre.ports['o_ready'] == '1':
                return item
        raise AssertionError('Input failed to become ready')

    async def drain(self):
        if self.config.mode == 'pack' and self.position:
            await self.push(self.data(last=1), 'finish_partial')
        for _ in range(self.config.ratio+3):
            if self.latest is not None and self.latest['o_busy'] == '0':
                break
            await self.cycle('drain')
        assert self.latest['o_busy'] == '0', 'Drain did not finish'

    async def fill(self, *, terminal=True):
        c = self.config
        for k in range(c.ratio if c.mode == 'pack' else 1):
            await self.push(self.data(last=int(terminal and (c.mode != 'pack' or k == c.ratio-1))), 'fill', ready=0)

    async def directed(self):
        c = self.config
        await self.cycle('initial_reset', rstb=0)
        await self.cycle('idle', ready=0)
        await self.cycle('idle')
        await self.cycle('empty_clockless', edge=False)
        # All input and output keep populations, including holes and empty groups.
        for population in range(max(c.in_units, c.out_units)+1):
            for last in (0, 1):
                if c.mode == 'pack':
                    remaining = population
                    for k in range(c.ratio):
                        count = min(c.in_units, remaining)
                        await self.push(self.data(keep=(1 << count)-1, last=int(last and k == c.ratio-1)), 'population')
                        remaining -= count
                else:
                    await self.push(self.data(keep=(1 << min(population, c.in_units))-1, last=last), 'population')
                await self.drain()
        # Every physical data bit is stored and delivered as both binary values.
        for value in (0, (1 << c.input_width)-1):
            for _ in range(c.ratio if c.mode == 'pack' else 1):
                await self.push(self.data() | dict(i_data=value, i_last=0), 'binary_bits')
            await self.drain()
        # Every completion/terminal position, both keep orders and internal holes.
        for terminal in range(c.ratio):
            if c.mode == 'pack':
                for k in range(terminal+1):
                    await self.push(self.data(keep=((1 << c.in_units)-1) if k % 2 == 0 else 0,
                        last=int(k == terminal)), 'early_last')
            elif c.mode == 'unpack':
                physical = terminal if c.lsb_first else c.ratio-1-terminal
                await self.push(self.data(keep=1 << (physical*c.out_units)), 'terminal_slice')
            else:
                await self.push(self.data(), 'equal_terminal')
            await self.drain()
        # Full nonterminal groups, repeated packets and a long packet. The
        # first user value may change only at a new packing-group boundary.
        for _ in range(3):
            for k in range(STREAM_LENGTH*c.ratio):
                await self.push(self.data(last=int(k == STREAM_LENGTH*c.ratio-1)), 'continuous')
            await self.drain()
        # Exercise each stall/gap duration with both blocked input and output.
        for length in (*range(STALL_LIMIT+1), LONG_STALL):
            await self.fill(terminal=False)
            await self.cycle('buffered_clockless', edge=False, ready=0)
            pending = self.data()
            for _ in range(length):
                await self.cycle('stall', pending, ready=0)
            await self.push(pending, 'release')
            await self.drain()
            await self.push(self.data(), 'gap_baseline')
            for _ in range(length):
                await self.cycle('input_gap')
            await self.push(self.data(), 'after_gap')
            await self.drain()
        # Invalid input units may contain any X/Z bit, including on valid beats.
        for state in 'xz':
            for selected in range(c.in_units):
                keep = ((1 << c.in_units)-1) ^ (1 << selected)
                beat = self.data(keep=keep)
                word = list(bits(beat['i_data'], c.input_width))
                end = c.input_width-selected*c.unit_width
                word[end-c.unit_width:end] = state*c.unit_width
                beat['i_data'] = ''.join(word)
                await self.push(beat, 'ignored_data')
                await self.drain()
        # Cancellation from every retained occupancy/index, while both peers
        # request transfers. Flush/reset suppress both handshakes on that edge.
        states = range(c.ratio+1) if c.mode != 'equal' else range(2)
        for kind in ('reset', 'flush'):
            for state in states:
                for valid in (0, 1):
                    for ready in (0, 1):
                        await self.drain()
                        if c.mode == 'pack':
                            for _ in range(state):
                                await self.push(self.data(last=0), 'cancel_setup', ready=0)
                        elif state:
                            await self.fill(terminal=False)
                            for _ in range(state-1):
                                await self.cycle('cancel_advance')
                        await self.cycle('cancel_' + kind, self.data(), valid=valid, ready=ready,
                            rstb=int(kind != 'reset'), flush=int(kind == 'flush'))
                        await self.cycle('cancel_release')
                        await self.push(self.data(), 'after_cancellation')
                        await self.drain()
        # Between-edge reset pulses distinguish synchronous state retention from
        # asynchronous clearing; visible ports are clamped during either pulse.
        for full in (False, True):
            if full:
                await self.fill()
            await self.cycle('reset_pulse', rstb=0, ready=0, edge=False)
            await self.cycle('reset_pulse_release', ready=0, edge=False)
            await self.drain()
        # A clockless flush clamps immediately but cancels only on a clock edge.
        await self.fill()
        await self.cycle('flush_pulse', flush=1, edge=False)
        await self.cycle('flush_pulse_release', ready=0, edge=False)
        await self.drain()

    async def randomized(self):
        c, pending = self.config, None
        for index in range(c.random_cycles):
            cancel = self.rng.randrange(97) == 0
            if pending is None and self.rng.random() < 0.82:
                pending = self.data(keep=self.rng.getrandbits(c.in_units), last=int(self.rng.random() < 0.2))
                pending['i_data'] = self.rng.getrandbits(c.input_width)
                if c.mode != 'pack' or self.position == 0:
                    pending['i_user'] = self.rng.getrandbits(c.user_width)
            item = await self.cycle(f'random_{index}', pending, ready=int(self.rng.random() < 0.68),
                flush=int(cancel), random=True)
            if cancel or item.pre.ports['o_ready'] == '1' and pending is not None:
                pending = None
        if pending is not None:
            await self.push(pending, 'finish_random_pending')
        await self.drain()

    async def probe(self):
        c = self.config
        kind, state, bit = c.probe.split(':')
        bit = int(bit)
        await self.cycle('probe_reset', rstb=0)
        await self.cycle('probe_release')
        if kind == 'metadata_match':
            await self.push(self.data(user=0, last=0))
            beat = self.data(last=0)
            beat['i_user'] = 1
            await self.cycle('metadata_violation', beat)
        elif kind.startswith('producer_'):
            await self.fill()
            pending = self.data()
            await self.cycle('blocked_producer', pending, ready=0)
            field = kind.removeprefix('producer_')
            if field == 'pulse':
                await self.cycle('producer_pulse', pending, ready=0, pulse='i_data')
            else:
                name = 'i_' + field
                await self.cycle('producer_violation', pending, ready=0, **{name: (pending.get(name, 1) ^ 1)})
        else:
            beat = self.data()
            field = 'i_data' if kind == 'active_data' else kind
            word = list(bits(1 if field in ('i_rstb', 'i_valid', 'i_ready') else beat.get(field, 0), c.widths[field]))
            word[-bit-1] = state
            await self.cycle('unknown_probe', beat, **{field: ''.join(word)})
        raise AssertionError('Expected protocol assertion did not fire')

    async def body(self):
        if self.config.probe:
            await self.probe()
            return
        await self.directed()
        await self.randomized()
        await self.cycle('final_idle')
