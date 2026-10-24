"""Directed protocol and numerical crosses, exhaustive reduced inputs, random traffic."""
from itertools import product
from random import Random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from rsqrt_unit.images import seeds
from rsqrt_unit.model import encode, evaluate, number
from rsqrt_unit.ports import INPUTS
from rsqrt_unit.transaction import RsqrtItem


def address_operands(c):
    # Highest two ordinary leading-one positions exercise both exponent parities.
    values = {1, (1 << c.INPUT_WIDTH) - 1}
    for p in (c.INPUT_WIDTH - 2, c.INPUT_WIDTH - 1):
        for region in range(1 << c.SEED_MANTISSA_ADDRESS_WIDTH):
            center = (1 << (c.SEED_MANTISSA_ADDRESS_WIDTH + 1)) + 2 * region + 1
            shift = p - c.SEED_MANTISSA_ADDRESS_WIDTH - 1
            m = center << shift if shift >= 0 else center >> -shift
            for operand in (m - 1, m, m + 1):
                if 0 < operand < 1 << c.INPUT_WIDTH:
                    values.add(operand)
    for p in range(c.INPUT_WIDTH):
        values |= {max(1, (1 << p) - 1), 1 << p,
                   min((1 << c.INPUT_WIDTH) - 1, (1 << p) + 1)}
    return sorted(values)


def reachable_addresses(c):
    return {evaluate(c, dict(operand=m, input_signed=0, output_signed=0,
        add_epsilon=0, epsilon=0, iterations=0, round_mode=mode,
        predicate=1, context_id=0, tag=0))[1]['address']
        for m in address_operands(c) for mode in (0, 1)}


class RsqrtSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('reciprocal_sequence')
        self.c = config
        self.rng = Random(config.seed)
        self.bus = dict.fromkeys(INPUTS, 0) | dict(i_rstb=1, i_result_ready=1)
        self.serial = 0
        self.last = {}

    async def cycle(self, label='cycle', *, edge=True, random=False, fault=None, **ports):
        self.bus.update(ports)
        item = RsqrtItem(f'{self.serial}:{label}', {name: bits(
            value * self.c.widths[name] if isinstance(value, str) else
            value & ((1 << self.c.widths[name]) - 1), self.c.widths[name])
            for name, value in self.bus.items()}, edge=edge, random=random, fault=fault)
        self.serial += 1
        await self.start_item(item)
        await self.finish_item(item)
        self.last = {name: number(value) for name, value in item.observation.ports.items()}
        return item

    async def reset_unit(self):
        await self.cycle('clockless_reset', edge=False, i_rstb=0,
            i_request_valid=0, i_flush=0, i_drain=0, i_error_clear=0, i_result_ready=1)
        await self.cycle('reset', i_rstb=0)
        for _ in range(3):
            await self.cycle('reset_release', i_rstb=1)

    async def drain(self, asserted=False):
        for _ in range(4 * self.c.latency + self.c.OUTPUT_QUEUE_DEPTH + 20):
            await self.cycle('drain', i_request_valid=0, i_result_ready=1,
                i_flush=0, i_drain=int(asserted), i_error_clear=0)
            if self.last['o_idle']:
                if asserted:
                    assert self.last['o_drain_done']
                await self.cycle('drain_release', i_drain=0)
                return
        raise AssertionError('Rsqrt evaluation did not drain')

    def fields(self, operand, signed=0, iterations=0, mode=0, predicate=1,
               output_signed=0, add_epsilon=0, epsilon=0):
        return dict(i_request_operand=operand, i_request_input_signed=signed,
            i_request_output_signed=output_signed, i_request_add_epsilon=add_epsilon,
            i_request_epsilon=epsilon, i_request_iterations=iterations,
            i_request_round_mode=mode, i_request_predicate=predicate,
            i_request_context_id=(self.serial * 13) % (1 << self.c.CONTEXT_ID_WIDTH),
            i_request_tag=self.serial % (1 << self.c.REQUEST_TAG_WIDTH))

    async def request(self, operand, signed=0, iterations=0, mode=0, predicate=1,
                      label='request', **extra):
        fields = self.fields(operand, signed, iterations, mode, predicate, **extra)
        for _ in range(4 * self.c.latency + 30):
            item = await self.cycle(label, i_request_valid=1, **fields)
            if number(item.pre.ports['o_request_ready']):
                await self.cycle('release_request', i_request_valid=0)
                return item
        raise AssertionError('Request was never accepted')

    async def body(self):
        c = self.c
        await self.reset_unit()
        # Fixed deterministic ordered trace is compared across both architectures.
        operands = address_operands(c)
        boundaries = {0, 1, 2, 3, (1 << c.INPUT_WIDTH) - 1,
            1 << (c.INPUT_WIDTH - 1), (1 << (c.INPUT_WIDTH - 1)) - 1}
        for p in range(c.INPUT_WIDTH):
            boundaries |= {max(1, (1 << p) - 1), 1 << p,
                           min((1 << c.INPUT_WIDTH) - 1, (1 << p) + 1)}
        for operand in sorted(set(operands) | boundaries):
            for count, mode in product(range(c.MAX_ITERATIONS + 1), (0, 1)):
                await self.request(operand, iterations=count, mode=mode, label='equivalence')
        for operand in sorted(boundaries):
            for sign, out, count, mode in product((0, 1), (0, 1),
                    range(c.MAX_ITERATIONS + 1), (0, 1)):
                await self.request(operand, sign, count, mode,
                    output_signed=out, label='equivalence')
        await self.drain()
        for count, mode, sign in product(range(c.MAX_ITERATIONS + 1), (0, 1), (0, 1)):
            await self.request(0, sign, count, mode, predicate=0, label='predicated_zero')
            await self.request((1 << c.INPUT_WIDTH) - 1, sign, count, mode,
                               predicate=0, label='predicated_nonzero')
        await self.drain()
        # Every representable reduced input, including zero and both signed modes.
        if c.INPUT_WIDTH <= 8:
            for operand, sign, out, count, mode in product(range(1 << c.INPUT_WIDTH),
                    (0, 1), (0, 1), range(c.MAX_ITERATIONS + 1), (0, 1)):
                await self.request(operand, sign, count, mode, output_signed=out, label='exhaustive')
            await self.drain()
        # Epsilon legality, rescue, carry, all sign/output crosses, and suppression.
        maximum = (1 << c.INPUT_WIDTH) - 1
        for operand, sign, out, eps, count, mode in product(
                (0, 1, maximum, 1 << (c.INPUT_WIDTH - 1)), (0, 1), (0, 1),
                (0, 1, maximum), range(c.MAX_ITERATIONS + 1), (0, 1)):
            await self.request(operand, sign, count, mode, output_signed=out,
                add_epsilon=1, epsilon=eps, label='epsilon_cross')
        for out, sign, operand in product((0, 1), (0, 1), (0, maximum)):
            await self.request(operand, sign, c.MAX_ITERATIONS, predicate=0,
                output_signed=out, add_epsilon=c.SUPPORT_EPSILON, epsilon=maximum,
                label='suppressed_epsilon')
        await self.drain()
        for count in range(c.MAX_ITERATIONS + 1):
            await self.request(3, iterations=count, label='latency')
            await self.drain()
        # Continuous traffic demonstrates II=1 or the declared iterative II.
        for count in range(c.MAX_ITERATIONS + 1):
            ticks = []
            fields = self.fields(3, iterations=count)
            for _ in range(12 * c.latency):
                item = await self.cycle('throughput', i_request_valid=1,
                    i_result_ready=1, **fields)
                if number(item.pre.ports['o_request_ready']):
                    ticks.append(self.serial)
                    fields = self.fields(3, iterations=count)
                if len(ticks) == 10:
                    break
            assert len(ticks) == 10
            expected = 1 if c.EVALUATION_ARCH else 4 + 3 * count
            assert all(b - a == expected for a, b in zip(ticks, ticks[1:]))
            await self.cycle('throughput_end', i_request_valid=0)
            await self.drain()
        # Fill every pipeline/queue position and maintain valid/payload on stalls.
        fields = self.fields(5, iterations=c.MAX_ITERATIONS)
        for _ in range((c.latency + c.OUTPUT_QUEUE_DEPTH + 5) * c.latency):
            item = await self.cycle('backpressure', i_request_valid=1,
                i_result_ready=0, **fields)
            if number(item.pre.ports['o_request_ready']):
                fields = self.fields(7, iterations=c.MAX_ITERATIONS)
        for _ in range(4 * c.latency + 10):
            item = await self.cycle('release_backpressure', i_result_ready=1,
                i_request_valid=1, **fields)
            if number(item.pre.ports['o_request_ready']):
                break
        else:
            raise AssertionError('Blocked request failed to resume')
        await self.cycle(i_request_valid=0)
        await self.drain(asserted=True)
        # Flush and synchronous/asynchronous reset at every physical phase.
        for phase in range(c.latency):
            await self.cycle('phase_accept', i_request_valid=1,
                **self.fields(3, iterations=c.MAX_ITERATIONS))
            for _ in range(phase):
                await self.cycle('phase_advance', i_request_valid=0)
            await self.cycle(f'flush_phase_{phase}', i_request_valid=0, i_flush=1,
                i_result_ready=0)
            await self.cycle('flush_release', i_flush=0, i_result_ready=1)
            await self.drain()
            await self.cycle('reset_phase_accept', i_request_valid=1,
                **self.fields(3, iterations=c.MAX_ITERATIONS))
            for _ in range(phase):
                await self.cycle('phase_advance', i_request_valid=0)
            await self.reset_unit()
        if c.MAX_ITERATIONS < (1 << c.widths['i_request_iterations']) - 1:
            await self.request(1, iterations=c.MAX_ITERATIONS + 1, label='illegal_iterations')
            await self.drain()
        # All active X/Z fields fail closed; inactive valid never consumes payload.
        for unknown in ('x', 'z'):
            for name in ('i_request_operand', 'i_request_input_signed', 'i_request_output_signed',
                    'i_request_add_epsilon', 'i_request_iterations',
                    'i_request_round_mode', 'i_request_predicate', 'i_request_context_id',
                    'i_request_tag'):
                await self.cycle('unknown_request', i_request_valid=1,
                    **(self.fields(3) | {name: unknown}))
                await self.cycle('unknown_release', i_request_valid=0, **self.fields(3))
            if c.SUPPORT_EPSILON:
                await self.cycle('unknown_active_epsilon', i_request_valid=1,
                    **(self.fields(3, add_epsilon=1) | {'i_request_epsilon': unknown}))
                await self.cycle('epsilon_release', i_request_valid=0, **self.fields(3))
            # An inactive epsilon is isolated before capture and may contain X/Z.
            await self.cycle('unknown_inactive_epsilon', i_request_valid=1,
                **(self.fields(3) | {'i_request_epsilon': unknown}))
            await self.cycle('epsilon_release', i_request_valid=0, **self.fields(3))
            await self.drain()
            for name in ('i_rstb', 'i_flush', 'i_drain', 'i_request_valid',
                         'i_result_ready', 'i_error_clear'):
                await self.cycle('unknown_control', **{name: unknown})
                await self.cycle('unknown_release', **{name: 0 if name in
                    ('i_flush', 'i_drain', 'i_request_valid', 'i_error_clear') else 1})
        await self.cycle('error_clear', i_error_clear=1)
        await self.cycle('error_clear_release', i_error_clear=0)
        # Fault every codeword bit, not just payload bits. SECDED corrects without
        # scrubbing; parity and unknown bits require fatal containment and reset.
        for fault_operand in (1 << (c.INPUT_WIDTH - 2), 1 << (c.INPUT_WIDTH - 1)):
            address = evaluate(c, dict(operand=fault_operand, input_signed=0, output_signed=0,
                add_epsilon=0, epsilon=0, iterations=0, round_mode=0, predicate=1,
                context_id=0, tag=0))[1]['address']
            seed = seeds(c.INTERNAL_WIDTH, c.INTERNAL_FRACTION_WIDTH,
                         c.SEED_MANTISSA_ADDRESS_WIDTH)[address]
            code, width = encode(seed, c.INTERNAL_WIDTH, c.SEED_PROTECTION)
            faults = ([1 << bit for bit in range(width)] if c.SEED_PROTECTION else [])
            if c.SEED_PROTECTION == 2:
                faults += [(1 << bit) | (1 << ((bit + 1) % width)) for bit in range(width)]
            faults += ['x' * width]
            for fault in faults:
                value = fault if isinstance(fault, str) else code ^ fault
                await self.cycle('seed_fault', fault=('seed', address, value))
                await self.request(fault_operand, iterations=c.MAX_ITERATIONS)
                await self.drain()
                if c.SEED_PROTECTION != 2 or isinstance(fault, str) or fault.bit_count() > 1:
                    assert self.last['o_fatal_error']
                    await self.cycle('fatal_flush', i_flush=1, i_error_clear=1)
                    await self.cycle('fatal_clear', i_flush=0)
                    assert self.last['o_fatal_error']
                else:
                    assert not self.last['o_fatal_error'] and self.last['o_error']
                await self.cycle('seed_repair', fault=('release',), i_error_clear=0)
                await self.reset_unit()
        for kind in (('state', 'queue', 'errors', 'identity', 'internal') if c.SEED_PROTECTION
                     else ('identity', 'internal')):
            if kind in ('identity', 'internal'):
                # Containment must cancel a visible stalled result as well as
                # stop new requests, with no handshake on the fault edge.
                await self.request(3, iterations=c.MAX_ITERATIONS)
                for _ in range(c.latency + 2):
                    await self.cycle('hold_before_fault', i_result_ready=0)
                assert self.last['o_result_valid']
            await self.cycle('ownership_fault', fault=(kind,))
            assert self.last['o_fatal_error']
            if kind in ('identity', 'internal'):
                await self.cycle('identity_restore', fault=('release',))
            await self.reset_unit()
        if c.SEED_PROTECTION:
            await self.cycle('fatal_latch_fault', fault=('errors', 16))
            assert self.last['o_fatal_error']
            await self.reset_unit()
        # Random source obeys stability while valid/ready is blocked. Flush/reset
        # explicitly cancels the offered token; token accounting is scoreboard-owned.
        fields = self.fields(1)
        pending = False
        for index in range(c.random_cycles):
            if not pending:
                fields = self.fields(self.rng.randrange(1 << c.INPUT_WIDTH),
                    self.rng.randrange(2), self.rng.randrange(c.MAX_ITERATIONS + 1),
                    self.rng.randrange(2), int(self.rng.random() > .15),
                    output_signed=self.rng.randrange(2),
                    add_epsilon=int(c.SUPPORT_EPSILON and self.rng.random() < .5),
                    epsilon=self.rng.randrange(1 << c.INPUT_WIDTH))
                pending = self.rng.random() < .85
            item = await self.cycle('random', random=True, i_request_valid=int(pending),
                i_result_ready=int(self.rng.random() < .65), **fields)
            if number(item.pre.ports['o_request_ready']):
                pending = False
        if pending:
            for _ in range(4 * c.latency + 20):
                item = await self.cycle('finish_random_offer', i_request_valid=1,
                    i_result_ready=1, **fields)
                if number(item.pre.ports['o_request_ready']):
                    break
            else:
                raise AssertionError('Random offered request failed to complete')
        await self.cycle('random_release', i_request_valid=0)
        await self.drain()
