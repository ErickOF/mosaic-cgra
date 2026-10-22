"""Integer boundaries, complete small intervals, elastic stress and fault recovery."""
from itertools import product
import random
import gmpy2 as g
from pyuvm import uvm_sequence
from exp_unit.model import direct_integer, number
from exp_unit.transaction import ExpUnitItem, INPUTS


class ExpUnitSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('exp_unit_sequence')
        self.c = config
        self.rng = random.Random(config.seed)
        self.index = 0
        self.last = None
        self.base = dict.fromkeys(INPUTS, 0)
        self.base.update(i_rstb=1, i_result_ready=1, i_request_predicate=1)

    async def cycle(self, label='idle', *, edge=True, random=False, fault=None, release=False, **ports):
        self.index += 1
        item = ExpUnitItem(f'{self.index}_{label}', self.base | ports, edge=edge,
                           random=random, fault=fault, release=release)
        await self.start_item(item)
        await self.finish_item(item)
        self.last = item.observation.ports
        return item

    def request(self, x=0, base=None, interpolate=0, mode=0, signed=0, predicate=1):
        c = self.c
        return dict(i_request_valid=1, i_request_operand=x % (1 << c.INPUT_WIDTH),
            i_request_base=(0 if c.SUPPORT_EXP_E else 1) if base is None else base,
            i_request_interpolate=interpolate, i_request_round_mode=mode,
            i_request_output_signed=signed, i_request_predicate=predicate,
            i_request_context_id=self.index % (1 << c.CONTEXT_ID_WIDTH),
            i_request_tag=self.index % (1 << c.REQUEST_TAG_WIDTH))

    async def send(self, **request):
        for _ in range(200):
            item = await self.cycle('request', **request)
            if number(item.pre.ports['o_request_ready']):
                return item
        raise AssertionError('Persistent request starved')

    async def drain(self):
        for _ in range(4 * (self.c.PIPELINE_DEPTH + self.c.OUTPUT_QUEUE_DEPTH + 2)):
            await self.cycle('drain', i_drain=1)
            if number(self.last['o_drain_done']):
                break
        else:
            raise AssertionError('Drain did not finish')
        await self.cycle()

    async def reset(self, release=False):
        await self.cycle('reset_clockless', i_rstb=0, edge=False, release=release)
        await self.cycle('reset', i_rstb=0)
        await self.cycle()

    async def arithmetic(self):
        c = self.c
        for base, interpolation, rounding, signed in product((0, 1), repeat=4):
            if (base == 0 and not c.SUPPORT_EXP_E or base == 1 and not c.SUPPORT_EXP2 or
                    interpolation and not c.SUPPORT_INTERPOLATION):
                await self.send(**self.request(base=base, interpolate=interpolation,
                                               mode=rounding, signed=signed))
                continue
            if c.INPUT_WIDTH <= 8:
                values = range(-(1 << (c.INPUT_WIDTH - 1)), 1 << (c.INPUT_WIDTH - 1))
            else:
                values = {0, 1, -1, (1 << (c.INPUT_WIDTH - 1)) - 1, -(1 << (c.INPUT_WIDTH - 1))}
                for integer in range(-18, 17):
                    for adjacent in (-1, 0, 1):
                        values.add((integer << c.INPUT_FRACTION_WIDTH) + adjacent)
                for segment in range((2 << c.TABLE_ADDRESS_WIDTH) + 1):
                    with g.context(precision=256):
                        x = g.mpfr(segment) * (1 << c.INPUT_FRACTION_WIDTH) / (2 << c.TABLE_ADDRESS_WIDTH)
                        if base == 0:
                            x *= g.log(g.mpfr(2))
                        center = direct_integer(x)
                    for adjacent in (-1, 0, 1):
                        values.add(center + adjacent)
                        values.add(-center + adjacent)
                if base == 1 and c.INPUT_FRACTION_WIDTH > c.RANGE_FRACTION_WIDTH:
                    half = 1 << (c.INPUT_FRACTION_WIDTH - c.RANGE_FRACTION_WIDTH - 1)
                    for quotient in range(-3, 4):
                        for adjacent in (-1, 0, 1):
                            values.add((2 * quotient + 1) * half + adjacent)
                low, high = -(1 << (c.INPUT_WIDTH - 1)), 1 << (c.INPUT_WIDTH - 1)
                values = sorted(x for x in values if low <= x < high)
            for x in values:
                await self.send(**self.request(x, base, interpolation, rounding, signed))
            await self.drain()
        for predicate in (0, 1):
            await self.send(**self.request(predicate=predicate))
        await self.drain()
        # Nominal latency is edge t -> edge t + PIPELINE_DEPTH.
        await self.send(**self.request())
        accepted = self.index
        for elapsed in range(1, c.PIPELINE_DEPTH + 1):
            await self.cycle('fixed_latency')
            assert number(self.last['o_result_valid']) == int(elapsed == c.PIPELINE_DEPTH)
        assert self.index - accepted == c.PIPELINE_DEPTH
        await self.drain()

    async def flow_control(self):
        c = self.c
        for _ in range(c.PIPELINE_DEPTH + c.OUTPUT_QUEUE_DEPTH):
            await self.send(**(self.request(1) | dict(i_result_ready=0)))
        waiting = self.request(-1)
        for _ in range(5):
            item = await self.cycle('full_backpressure', i_result_ready=0, **waiting)
            assert number(item.pre.ports['o_request_ready']) == 0
        for _ in range(3 * (c.PIPELINE_DEPTH + c.OUTPUT_QUEUE_DEPTH)):
            await self.cycle('drain_with_held_request', i_drain=1, **waiting)
            if number(self.last['o_drain_done']):
                break
        assert number(self.last['o_drain_done']) == 1
        await self.send(**waiting)
        await self.drain()
        for stage in range(c.PIPELINE_DEPTH + 1):
            await self.send(**self.request(stage - 2))
            for _ in range(stage):
                await self.cycle()
            await self.cycle('flush_phase', i_flush=1, i_result_ready=0)
            await self.cycle()
            assert number(self.last['o_idle']) == 1
            await self.send(**self.request())
            for _ in range(stage):
                await self.cycle()
            await self.reset()
        await self.cycle('flush_overrides_drain', i_flush=1, i_drain=1)
        assert number(self.last['o_drain_done']) == 0
        # Clockless opportunities cannot advance registers.
        await self.send(**self.request(1))
        for _ in range(4):
            await self.cycle('clockless', edge=False)
        await self.drain()

    async def unknowns(self):
        c = self.c
        request = self.request()
        for state in 'xz':
            for name in ('i_request_operand', 'i_request_base', 'i_request_output_signed',
                         'i_request_interpolate', 'i_request_round_mode', 'i_request_predicate',
                         'i_request_context_id', 'i_request_tag'):
                await self.cycle('unknown_request', **(request | {name: state * c.widths[name]}))
            for name in ('i_rstb', 'i_drain', 'i_flush', 'i_request_valid', 'i_result_ready', 'i_error_clear'):
                await self.cycle('unknown_control', **{name: state})
        await self.cycle('clear_error', i_error_clear=1)
        assert number(self.last['o_error']) == 0

    async def faults(self):
        c = self.c
        if not c.check_internals:
            return
        await self.cycle('identity_fault', fault=('identity', 0, 1))
        assert number(self.last['o_fatal_error']) == 1
        await self.reset()
        assert number(self.last['o_fatal_error']) == 1, 'Persistent identity fault must reassert'
        await self.reset(release=True)
        if not c.TABLE_PROTECTION:
            return
        control_width = 12 + c.CONTEXT_ID_WIDTH + c.REQUEST_TAG_WIDTH
        await self.send(**self.request())
        await self.cycle('ownership_fault', fault=('stage', 0, 1 << control_width))
        assert number(self.last['o_fatal_error']) == 1
        await self.reset(release=True)
        endpoints = (0, 1) if c.SUPPORT_INTERPOLATION else (0,)
        for endpoint in endpoints:
            masks = (4, 3) if c.TABLE_PROTECTION == 2 else (1,)
            for mask in masks:
                await self.cycle('table_fault', fault=('rom', endpoint, mask))
                await self.send(**self.request(0, interpolate=int(bool(c.SUPPORT_INTERPOLATION))))
                for _ in range(c.PIPELINE_DEPTH + 3):
                    await self.cycle()
                corrected = c.TABLE_PROTECTION == 2 and mask.bit_count() == 1
                assert number(self.last['o_fatal_error']) == int(not corrected)
                if not corrected:
                    await self.cycle('fatal_flush', i_flush=1)
                    await self.cycle('fatal_error_clear', i_error_clear=1)
                    assert number(self.last['o_fatal_error']) == 1
                await self.reset(release=True)

    async def randomized(self):
        c, rng = self.c, self.rng
        pending = None
        for opportunity in range(c.random_cycles):
            if opportunity % 151 == 0:
                pending = None
                await self.cycle('random_flush', random=True, i_flush=1)
                continue
            if pending is None and rng.random() < .85:
                pending = self.request(rng.getrandbits(c.INPUT_WIDTH), rng.randrange(2),
                    rng.randrange(2), rng.randrange(2), rng.randrange(2), int(rng.random() > .15))
            item = await self.cycle('random', random=True, i_result_ready=int(rng.random() < .7),
                                    **(pending or {}))
            if pending and number(item.pre.ports['o_request_ready']):
                pending = None
        if pending:
            await self.send(**pending)
        await self.drain()

    async def body(self):
        await self.reset()
        await self.arithmetic()
        await self.flow_control()
        await self.unknowns()
        await self.faults()
        await self.randomized()
        await self.reset()
