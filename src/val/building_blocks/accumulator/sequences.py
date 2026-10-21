"""Exhaustive small-width, boundary, atomicity and seeded stateful campaigns."""

from itertools import product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from accumulator.config import LONG_STALL, STREAM_LENGTH
from accumulator.coverage import boundary_values
from accumulator.model import Command
from accumulator.transaction import AccumulatorItem


class AccumulatorSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('accumulator_sequence')
        self.config = config
        self.rng = random.Random(config.seed)

    def vector(self, value):
        c = self.config
        return sum(value << (k*c.width) for k in range(c.lanes))

    async def cycle(self, label, *, command=None, mask=None, data=None, signed=0, saturate=0,
            enable=1, valid=None, rstb=1, edge=True, random=False, pulse='', **overrides):
        c = self.config
        active = command is not None
        ports = dict(i_rstb=rstb, i_clock_enable=enable, i_valid=int(active) if valid is None else valid,
            i_command=int(command) if active else 'xx', i_lane_mask=c.all_lanes if mask is None else mask,
            i_data=self.vector(1) if data is None else data, i_signed=signed, i_saturate=saturate)
        ports.update(overrides)
        item = AccumulatorItem(label, {name:bits(value, c.widths[name]) for name, value in ports.items()},
            edge=edge, random=random, pulse=pulse)
        await self.start_item(item)
        await self.finish_item(item)
        return item

    async def reset(self, **kwargs):
        return await self.cycle('reset', rstb=0, **kwargs)

    async def initialization(self):
        c = self.config
        for command, old, new in product((Command.CLEAR, Command.LOAD), (-1, 0, 1), (0, 1)):
            await self.reset()
            if old != -1:
                await self.cycle('establish_old_type', command=Command.LOAD, signed=old, data=self.vector(c.word_mask))
            await self.cycle('establish_new_type', command=command, signed=new, data=0)
        for command in Command:
            await self.reset()
            await self.cycle('uninitialized_command', command=command)
        # One selected invalid lane prevents valid peers from updating. CLEAR
        # and LOAD also exercise the same mixed-validity masks as legal updates.
        for bad, command in product(range(c.lanes), Command):
            await self.reset()
            await self.cycle('initialize_other_lanes', command=Command.LOAD, mask=c.all_lanes ^ (1 << bad), data=self.vector(2 & c.word_mask))
            await self.cycle('one_invalid_lane', command=command)
        for bad, command, signed in product(range(c.lanes), (Command.ADD, Command.SUB), (0, 1)):
            await self.cycle('uniform_type', command=Command.CLEAR, signed=signed)
            await self.cycle('one_mismatched_type', command=Command.LOAD, mask=1 << bad, signed=1-signed)
            await self.cycle('atomic_type_failure', command=command, signed=signed)
        for command in Command:
            await self.cycle('initialize_mask_sweep', command=Command.CLEAR)
            for population in range(c.lanes+1):
                await self.cycle('mask_population', command=command, mask=(1 << population)-1)
            alternating = sum(1 << k for k in range(c.lanes) if k % 2 == 0)
            for mask in (0, c.all_lanes, alternating, c.all_lanes ^ alternating):
                await self.cycle('mask_shape', command=command, mask=mask)
            for k in range(c.lanes):
                await self.cycle('walking_lane', command=command, mask=1 << k,
                    data=sum(((j+1) & c.word_mask) << (j*c.width) for j in range(c.lanes)))

    async def arithmetic(self):
        c = self.config
        values = range(1 << c.width) if c.lanes == 1 and c.width <= 4 else boundary_values(c.width)
        # An independent LOAD precedes every request. This tests every numerical
        # transition, including runtime-rejected feature and saturation modes.
        for left, right, command, signed, saturate in product(values, values, Command, (0, 1), (0, 1)):
            await self.cycle('numerical_setup', command=Command.LOAD, data=self.vector(left), signed=signed)
            await self.cycle('numerical_transition', command=command, data=self.vector(right), signed=signed, saturate=saturate)
        for command in Command:
            await self.cycle('stream_initialize', command=Command.CLEAR)
            for index in range(STREAM_LENGTH):
                await self.cycle('dependent_stream', command=command,
                    data=self.vector((index if command == Command.LOAD else 1) & c.word_mask))

    async def unknowns(self):
        c = self.config
        await self.cycle('unknowns_initialize', command=Command.CLEAR)
        for state in 'xz':
            for pattern in product('01'+state, repeat=2):
                if state in pattern:
                    for mask in (0, c.all_lanes):
                        await self.cycle('unknown_command', command=Command.ADD, mask=mask, i_command=''.join(pattern))
            for command, k in product(Command, range(c.lanes)):
                word = list(bits(c.all_lanes, c.lanes));word[-k-1] = state
                await self.cycle('unknown_mask', command=command, i_lane_mask=''.join(word))
            for name, command, mask in product(('i_signed', 'i_saturate'), Command, (0, c.all_lanes)):
                await self.cycle('unknown_global_control', command=command, mask=mask, **{name:state})
            await self.cycle('ignored_invalid_fields', valid=0, i_command=state*2, i_lane_mask=state*c.lanes,
                i_data=state*(c.width*c.lanes), i_signed=state, i_saturate=state)
            await self.cycle('ignored_stalled_fields', enable=0, valid=state, i_command=state*2,
                i_lane_mask=state*c.lanes, i_data=state*(c.width*c.lanes), i_signed=state, i_saturate=state)
            await self.cycle('clear_ignores_data', command=Command.CLEAR, data=state*(c.width*c.lanes))
            for command in (Command.LOAD, Command.ADD, Command.SUB):
                for k in range(c.lanes):
                    await self.cycle('typed_masked_setup', command=Command.CLEAR)
                    word = list(state*(c.width*c.lanes))
                    end = len(word)-k*c.width
                    word[end-c.width:end] = bits(1, c.width)
                    await self.cycle('masked_unknown_data', command=command, mask=1 << k, data=''.join(word))
                await self.cycle('all_zero_mask_unknown_data', command=command, mask=0, data=state*(c.width*c.lanes))

    async def resets_and_stalls(self):
        c = self.config
        for population, enable, valid in product(range(c.lanes+1), (0, 1), (0, 1)):
            await self.reset()
            await self.cycle('reset_setup', command=Command.LOAD, mask=(1 << population)-1, signed=1, data=self.vector(c.word_mask))
            await self.reset(command=Command.LOAD, data=0, enable=enable, valid=valid)
        for full in (False, True):
            await self.reset()
            if full:
                await self.cycle('pulse_setup', command=Command.LOAD, signed=1, data=self.vector(c.word_mask))
            await self.cycle('clockless_before_reset', enable=0, command=Command.LOAD, data=0, edge=False, pulse='i_data')
            await self.cycle('between_edge_reset', rstb=0, enable=0, edge=False)
            await self.cycle('between_edge_release', enable=0, edge=False)
            await self.cycle('clockless_data_pulse', enable=0, valid=1, command=Command.ADD, data=0, edge=False, pulse='i_data')
            await self.cycle('clockless_command_pulse', enable=0, command=Command.LOAD, edge=False, pulse='i_command')
        for command, length in product(Command, (*range(5), LONG_STALL)):
            await self.cycle('stall_initialize', command=Command.CLEAR)
            await self.cycle('stall_response', command=command)
            for _ in range(length):
                await self.cycle('stalled', command=Command.LOAD, enable=0, signed=1, data=self.rng.getrandbits(c.width*c.lanes))
            await self.cycle('resume', command=command)
        # Compatible ownership preserves state across scheduled stalls. A type
        # change is rejected until an explicit architectural reload occurs.
        await self.cycle('owner_initialize', command=Command.LOAD, signed=1)
        await self.cycle('owner_preserve', command=Command.ADD, enable=0)
        await self.cycle('owner_continue', command=Command.ADD, signed=1)
        await self.cycle('owner_incompatible', command=Command.ADD, signed=0)
        await self.cycle('owner_reload', command=Command.LOAD, signed=0)
        await self.cycle('owner_resume', command=Command.ADD, signed=0)

    async def randomized(self):
        c = self.config
        for index in range(c.random_cycles):
            await self.cycle(f'random_{index}', command=self.rng.randrange(4), mask=self.rng.getrandbits(c.lanes),
                data=self.rng.getrandbits(c.width*c.lanes), signed=self.rng.randrange(2),
                saturate=int(self.rng.random() < 0.25), enable=int(self.rng.random() < 0.85),
                valid=int(self.rng.random() < 0.85), rstb=int(self.rng.randrange(120) != 0), random=True)

    async def probe(self):
        c = self.config
        field, state, bit = c.probe.split(':');bit = int(bit)
        await self.reset()
        await self.cycle('probe_initialize', command=Command.CLEAR)
        name = 'i_data' if field == 'active_data' else field
        word = list(bits(0 if name == 'i_data' else 1, c.widths[name]));word[-bit-1] = state
        await self.cycle('protocol_violation', command=Command.LOAD, **{name:''.join(word)})
        raise AssertionError('Expected protocol assertion did not fire')

    async def body(self):
        if self.config.probe:
            await self.probe()
            return
        await self.reset(enable=0)
        await self.initialization()
        await self.arithmetic()
        await self.unknowns()
        await self.resets_and_stalls()
        await self.randomized()
        await self.cycle('final_bubble', valid=0)
