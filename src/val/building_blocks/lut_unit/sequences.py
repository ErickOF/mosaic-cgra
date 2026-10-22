"""Programmable image recipes, numerical sweeps, lifecycle and protection stress."""
from random import Random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from lut_unit.images import image_value
from lut_unit.model import code_width, number
from lut_unit.transaction import INPUTS, LutUnitItem


class LutUnitSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('lut_unit_sequence')
        self.c = config
        self.rng = Random(config.seed)
        self.bus = dict.fromkeys(INPUTS, 0) | dict(i_rstb=1, i_result_ready=1,
            i_program_response_ready=1, i_lookup_predicate=1)
        self.last = {}
        self.serial = 0

    async def cycle(self, label='cycle', *, edge=True, random=False, fault=None, **ports):
        self.bus.update(ports)
        item = LutUnitItem(f'{self.serial}_{label}',
            {n: bits(v * self.c.widths[n] if isinstance(v, str) and len(v) == 1 else v,
                     self.c.widths[n]) for n, v in self.bus.items()},
            edge=edge, random=random, fault=fault)
        self.serial += 1
        await self.start_item(item)
        await self.finish_item(item)
        self.last = {n: number(v) for n, v in item.observation.ports.items()}
        return item

    async def program(self, command, bank=0, address=0, data=0, table_id=7, quality=1):
        ports = dict(i_program_valid=1, i_program_command=command, i_program_bank=bank,
                     i_program_address=address, i_program_write_data=data,
                     i_program_table_id=table_id & ((1 << self.c.TABLE_ID_WIDTH) - 1),
                     i_program_quality_id=quality & ((1 << self.c.QUALITY_ID_WIDTH) - 1))
        for _ in range(10000):
            item = await self.cycle('program', **ports)
            if number(item.pre.ports['o_program_ready']) == 1:
                break
        else:
            raise AssertionError('Programming command blocked')
        await self.cycle('program_release', i_program_valid=0)

    async def lookup(self, coordinate, bank=0, *, signed=0, output_signed=0,
                     interpolate=0, rounding=0, predicate=1):
        ports = dict(i_lookup_valid=1, i_lookup_coordinate=coordinate & ((1 << self.c.aliases['INDEX_WIDTH']) - 1),
            i_lookup_bank=bank, i_lookup_index_signed=signed, i_lookup_output_signed=output_signed,
            i_lookup_interpolate=interpolate, i_lookup_round_mode=rounding,
            i_lookup_predicate=predicate, i_lookup_context_id=self.serial & ((1 << self.c.CONTEXT_ID_WIDTH) - 1),
            i_lookup_tag=self.serial & ((1 << self.c.LOOKUP_TAG_WIDTH) - 1))
        for _ in range(10000):
            item = await self.cycle('lookup', **ports)
            if number(item.pre.ports['o_lookup_ready']) == 1:
                break
        else:
            raise AssertionError('Lookup blocked')
        await self.cycle('lookup_release', i_lookup_valid=0)

    async def drain(self):
        for _ in range(10000):
            if self.last.get('o_idle'):
                return
            await self.cycle('drain', i_lookup_valid=0, i_program_valid=0,
                             i_result_ready=1, i_program_response_ready=1, i_drain=0)
        raise AssertionError('Queues failed to drain')

    async def clear(self):
        await self.drain()
        await self.cycle('error_clear', i_error_clear=1)
        await self.cycle('error_clear_release', i_error_clear=0)

    def image(self, bank, address, kind=0):
        return image_value(self.c.OUTPUT_WIDTH, bank, address, kind)

    async def load_bank(self, bank, kind=0):
        if self.last.get('o_bank_valid', 0) >> bank & 1:
            await self.program(3, bank)
        for address in range(1 << self.c.ADDRESS_WIDTH):
            await self.program(0, bank, address, self.image(bank, address, kind))
        for address in range(1 << self.c.ADDRESS_WIDTH):
            await self.program(1, bank, address)
        await self.program(2, bank, table_id=bank + 7, quality=kind)

    async def body(self):
        c = self.c
        depth, scale = 1 << c.ADDRESS_WIDTH, 1 << c.INDEX_FRACTION_WIDTH
        maximum = (depth - 1) * scale
        await self.cycle('reset', i_rstb=0)
        await self.cycle('release', i_rstb=1)
        await self.lookup(0)  # Invalid-bank response retains its token identity.
        await self.clear()
        await self.program(3)
        await self.clear()
        await self.program(2)
        await self.clear()
        # Coverage-off permits publication without programming; start fresh before
        # loading the deterministic images used by every numerical reference.
        await self.cycle('startup_reset', i_rstb=0)
        await self.cycle('startup_release', i_rstb=1)
        for bank in range(c.NUM_BANKS):
            await self.load_bank(bank, bank % 3)
            await self.program(1, bank, depth - 1)
            await self.program(0, bank, 0, 99)
            await self.clear()
            await self.program(2, bank)
            await self.clear()
        # Each integer boundary, both signed interpretations and fraction corners.
        for bank in range(c.NUM_BANKS):
            for address in range(depth):
                await self.lookup(address * scale, bank, output_signed=address % 2)
            for coordinate in (-scale, -1, 0, 1, scale // 2, scale - 1,
                               maximum - 1, maximum, maximum + 1,
                               (1 << c.aliases['INDEX_WIDTH']) - 1):
                for signed in (0, 1):
                    for output_signed in (0, 1):
                        for rounding in (0, 1):
                            await self.lookup(coordinate, bank, signed=signed,
                                output_signed=output_signed, interpolate=c.SUPPORT_INTERPOLATION,
                                rounding=rounding)
            await self.lookup(maximum + 1, bank, predicate=0, interpolate=0)
        await self.drain()
        if not c.SUPPORT_INTERPOLATION:
            await self.lookup(scale // 2, interpolate=1)
            await self.clear()
        if c.NUM_BANKS == 1 or c.NUM_BANKS & (c.NUM_BANKS - 1):
            await self.lookup(0, bank=c.NUM_BANKS)
            await self.clear()
            await self.program(1, bank=c.NUM_BANKS)
            await self.clear()
        # Busy invalidation rejects while an outstanding result owns the image.
        await self.cycle('stall_results', i_result_ready=0)
        await self.lookup(scale // 2, interpolate=c.SUPPORT_INTERPOLATION)
        for _ in range(c.LOOKUP_PIPELINE_DEPTH + 1):
            await self.cycle('wait_queued')
        await self.program(3)
        await self.cycle('release_results', i_result_ready=1)
        await self.clear()
        # Saturate both queues, then exercise flush with a held program response.
        await self.cycle('fill_setup', i_result_ready=0, i_program_response_ready=0)
        for _ in range(c.LOOKUP_PIPELINE_DEPTH + c.LOOKUP_RESPONSE_DEPTH):
            await self.lookup(scale // 2, interpolate=c.SUPPORT_INTERPOLATION)
        for _ in range(c.PROGRAM_RESPONSE_DEPTH):
            await self.program(1)
        await self.cycle('full_backpressure', i_lookup_valid=1, i_program_valid=1)
        await self.cycle('lookup_flush', i_flush=1, i_lookup_valid=0, i_program_valid=0)
        await self.cycle('flush_release', i_flush=0, i_result_ready=1, i_program_response_ready=1)
        await self.drain()
        # Lifecycle/write priority holds the complete same-bank lookup request.
        await self.cycle('same_bank_write', i_program_valid=1, i_program_command=0,
            i_program_bank=0, i_program_address=0, i_program_write_data=9,
            i_lookup_valid=1, i_lookup_bank=0, i_lookup_coordinate=0,
            i_lookup_predicate=1, i_lookup_interpolate=0)
        await self.cycle('same_bank_write_release', i_program_valid=0)
        await self.cycle('same_bank_lookup_release', i_lookup_valid=0)
        await self.clear()
        # Simultaneous same-bank readback is held while lookup owns the port.
        await self.cycle('read_conflict', i_lookup_valid=1, i_lookup_coordinate=scale,
                         i_program_valid=1, i_program_command=1, i_program_bank=0, i_lookup_bank=0)
        await self.cycle('read_conflict_release', i_lookup_valid=0)
        await self.cycle('channels_idle', i_program_valid=0)
        await self.drain()
        await self.cycle('predicated_readback', i_program_valid=1, i_program_command=1,
            i_program_bank=0, i_lookup_valid=1, i_lookup_bank=0, i_lookup_predicate=0)
        await self.cycle('predicated_readback_release', i_program_valid=0, i_lookup_valid=0,
                         i_lookup_predicate=1)
        await self.drain()
        if c.NUM_BANKS > 1:
            await self.program(3, 1)
            await self.cycle('different_bank_write', i_program_valid=1, i_program_command=0,
                i_program_bank=1, i_program_address=0, i_program_write_data=9,
                i_lookup_valid=1, i_lookup_bank=0, i_lookup_coordinate=0)
            await self.cycle('different_bank_release', i_program_valid=0, i_lookup_valid=0)
            await self.drain()
            await self.load_bank(1, 1)
        # Drain prevents new intake and permits programming after lookup empties.
        await self.lookup(0)
        await self.cycle('drain_request', i_drain=1, i_lookup_valid=1, i_program_valid=1)
        for _ in range(c.LOOKUP_PIPELINE_DEPTH + c.LOOKUP_RESPONSE_DEPTH + 2):
            await self.cycle('drain_wait', i_lookup_valid=0)
        await self.cycle('drain_release', i_drain=0, i_program_valid=0)
        await self.drain()
        # Explicit ties, negative half deltas and descending unsigned endpoints.
        await self.program(3)
        for address in range(depth):
            value = (1, 2, 5, 2, (1 << c.OUTPUT_WIDTH) - 1, 0)[address % 6]
            await self.program(0, 0, address, value)
        await self.program(2, table_id=15, quality=2)
        for address in range(min(depth - 1, 6)):
            for fraction in (1, scale // 2 - 1, scale // 2, scale // 2 + 1, scale - 1):
                for signed in (0, 1):
                    for rounding in (0, 1):
                        await self.lookup(address * scale + fraction, output_signed=signed,
                            interpolate=c.SUPPORT_INTERPOLATION, rounding=rounding)
        await self.drain()
        # Exercise version wrap with inexpensive complete images; large images
        # retain the same modulo arithmetic, checked at each individual commit.
        if c.TABLE_VERSION_WIDTH <= 2 and (not c.TRACK_PROGRAM_COVERAGE or depth <= 16):
            for version in range(1 << c.TABLE_VERSION_WIDTH):
                await self.program(3)
                if c.TRACK_PROGRAM_COVERAGE:
                    for address in range(depth):
                        await self.program(0, 0, address, self.image(0, address))
                await self.program(2, table_id=version, quality=version)
        # Unknown active controls hold requests; direct-mode rounding is ignored.
        controls = ('i_drain', 'i_error_clear', 'i_lookup_valid', 'i_result_ready',
                    'i_program_valid', 'i_program_response_ready', 'i_flush', 'i_rstb')
        for name in controls:
            old = self.bus[name]
            for unknown in ('x', 'z'):
                await self.cycle('unknown_' + name, **{name: unknown})
                await self.cycle('known_' + name, **{name: old})
            await self.clear()
        for name in ('i_lookup_bank', 'i_lookup_coordinate', 'i_lookup_predicate',
                     'i_lookup_context_id', 'i_lookup_tag', 'i_lookup_interpolate'):
            old = self.bus[name]
            await self.cycle('unknown_payload_' + name, i_lookup_valid=1, **{name: 'x'})
            await self.cycle('known_payload_' + name, i_lookup_valid=0, **{name: old})
            await self.clear()
        for name in ('i_program_bank', 'i_program_command', 'i_program_address', 'i_program_write_data'):
            old = self.bus[name]
            await self.cycle('unknown_program_' + name, i_program_valid=1, **{name: 'z'})
            await self.cycle('known_program_' + name, i_program_valid=0, **{name: old})
            await self.clear()
        await self.lookup(0, rounding='x')
        await self.drain()
        # Random requests hold their complete packet until the actual handshake.
        lookup_pending = program_pending = False
        for _ in range(c.random_cycles):
            fields = dict(i_result_ready=int(self.rng.random() < .63),
                          i_program_response_ready=int(self.rng.random() < .6),
                          i_drain=0, i_flush=0)
            if not lookup_pending:
                fields.update(i_lookup_valid=int(self.rng.random() < .8),
                    i_lookup_coordinate=self.rng.randrange(1 << c.aliases['INDEX_WIDTH']),
                    i_lookup_bank=self.rng.randrange(c.NUM_BANKS), i_lookup_index_signed=self.rng.randrange(2),
                    i_lookup_output_signed=self.rng.randrange(2), i_lookup_interpolate=self.rng.randrange(2),
                    i_lookup_round_mode=self.rng.randrange(2), i_lookup_predicate=int(self.rng.random() < .9),
                    i_lookup_context_id=self.rng.randrange(1 << c.CONTEXT_ID_WIDTH),
                    i_lookup_tag=self.rng.randrange(1 << c.LOOKUP_TAG_WIDTH))
            if not program_pending:
                fields.update(i_program_valid=int(self.rng.random() < .35), i_program_command=1,
                    i_program_bank=self.rng.randrange(c.NUM_BANKS), i_program_address=self.rng.randrange(depth),
                    i_program_write_data=0)
            item = await self.cycle('random', random=True, **fields)
            lookup_pending = bool(number(item.pre.ports['i_lookup_valid']) and not number(item.pre.ports['o_lookup_ready']))
            program_pending = bool(number(item.pre.ports['i_program_valid']) and not number(item.pre.ports['o_program_ready']))
        # Preserve pending producers until accepted before ending random traffic.
        for _ in range(c.LOOKUP_PIPELINE_DEPTH + c.LOOKUP_RESPONSE_DEPTH + c.PROGRAM_RESPONSE_DEPTH + 4):
            item = await self.cycle('random_release', i_lookup_valid=int(lookup_pending),
                i_program_valid=int(program_pending), i_result_ready=1, i_program_response_ready=1)
            lookup_pending &= not bool(number(item.pre.ports['o_lookup_ready']))
            program_pending &= not bool(number(item.pre.ports['o_program_ready']))
        await self.cycle('random_end', i_lookup_valid=0, i_program_valid=0)
        await self.clear()
        if c.check_internals and c.BUFFER_PROTECTION:
            # Each bit is checked while the bank is invalid, so parity failures
            # cannot poison unrelated tests. Restore each injected word afterward.
            await self.program(3)
            for bit in range(code_width(c.OUTPUT_WIDTH, c.BUFFER_PROTECTION)):
                await self.program(0, 0, 0, 5)
                await self.cycle('inject_bit', fault=('table', 0, 0, 1 << bit))
                await self.program(1, 0, 0)
                await self.clear()
            if c.BUFFER_PROTECTION == 2 and c.OUTPUT_WIDTH > 256:
                await self.program(0, 0, 0, 5)
                await self.cycle('cross_stripe_double', fault=('table', 0, 0, 1 | (1 << 266)))
                await self.program(1, 0, 0)
                await self.clear()
            await self.program(0, 0, 0, 5)
            # Other entries retain their programmed bits; coverage must be rebuilt.
            if c.TRACK_PROGRAM_COVERAGE:
                for address in range(1, depth):
                    await self.program(0, 0, address, self.image(0, address))
            await self.program(2)
            await self.cycle('visible_fault', fault=('table', 0, 0, 3 if c.BUFFER_PROTECTION == 2 else 1))
            await self.lookup(0)
            await self.drain()
            await self.cycle('fatal_error_clear', i_error_clear=1)
            await self.cycle('fatal_error_clear_release', i_error_clear=0)
            await self.cycle('fatal_flush', i_flush=1)
            await self.cycle('fatal_flush_release', i_flush=0)
            await self.program(2)  # Fatal blocks commit.
            await self.drain()
            await self.program(3)  # No outstanding reference: recovery can start.
            await self.program(0, 0, 0, 5)
            await self.clear()
            for kind in ('metadata', 'queue'):
                await self.cycle('internal_fault', fault=(kind, 0, 0, 2 if kind == 'metadata' else 1))
                await self.cycle('internal_fault_hold')
                await self.cycle('internal_fault_reset', i_rstb=0)
                await self.cycle('internal_fault_release', i_rstb=1)
        # Reset from both stalled streams and distinguish reset between edges.
        await self.load_bank(0)
        await self.cycle('reset_pending_setup', i_result_ready=0, i_program_response_ready=0)
        await self.lookup(0)
        await self.program(1)
        await self.cycle('between_edges_assert', edge=False, i_rstb=0)
        await self.cycle('between_edges_release', edge=False, i_rstb=1)
        await self.cycle('final_reset', i_rstb=0)
        await self.cycle('final_release', i_rstb=1, i_result_ready=1, i_program_response_ready=1)
        await self.cycle('final_idle')
