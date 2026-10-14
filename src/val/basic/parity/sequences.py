"""Directed fault mathematics, partial-granule activity, independence and X/Z."""

from itertools import combinations, product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from parity.model import encode, error_patterns
from parity.transaction import ParityItem


class ParitySequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('parity_sequence')
        self.config = config
        self.rng = random.Random(config.seed)

    async def send(self, label, source, received, *, base=None, faults=(), random=False, selection=None, previous_source=None):
        config = self.config
        code = bits(received, config.code_width)
        item = ParityItem(label, bits(source, config.width), code[-config.width:], code[:config.parity_width],
                          base=base, faults=faults, random=random, selection=selection, previous_source=previous_source)
        await self.start_item(item)
        await self.finish_item(item)

    async def fault(self, label, base, faults=(), *, source=0, random=False):
        await self.send(label, source, encode(self.config, base) ^ sum(1 << bit for bit in faults),
                        base=base, faults=faults, random=random)

    async def data_patterns(self):
        config = self.config
        maximum = (1 << config.width) - 1
        patterns = {0, maximum, sum(1 << bit for bit in range(0, config.width, 2)), sum(1 << bit for bit in range(1, config.width, 2))}
        patterns.update(1 << bit for bit in range(config.width))
        patterns.update(maximum ^ (1 << bit) for bit in range(config.width))
        for value in sorted(patterns):
            await self.fault('clean_data_pattern', value, source=value)
        if config.width <= 8:
            for value in range(1 << config.width):
                await self.fault('exhaustive_generation', value, source=value)
        if config.code_width <= 12:
            for received in range(1 << config.code_width):
                await self.send('exhaustive_checker', self.rng.getrandbits(config.width), received)

    async def faults(self):
        config = self.config
        maximum = (1 << config.width) - 1
        for base in (0, maximum):
            for bit in range(config.code_width):
                await self.fault('every_single_fault', base, (bit,), source=base ^ maximum)
        base = self.rng.getrandbits(config.width) or 1
        source = base ^ maximum
        for granule in range(config.parity_width):
            protected = config.protected_bits(granule)
            if config.granule_width <= 32:
                pairs = combinations(protected, 2)
            else:
                # Bound quadratic simulation growth for very wide granules,
                # while covering every data+parity pair and adjacent data pair.
                pairs = sorted({(bit, protected[-1]) for bit in protected[:-1]} |
                               set(zip(protected[:-2], protected[1:-1])) | {(protected[0], protected[-2])})
            for pair in pairs:
                await self.fault('same_granule_expected_undetected', base, pair, source=source)
            for weight in sorted({3, 4, len(protected)}):
                if 3 <= weight <= len(protected):
                    await self.fault('higher_weight_characterization', base, protected[:weight], source=source)
        count = config.parity_width
        pairs = (combinations(range(count), 2) if count <= 16 else sorted(
            {(granule, granule + 1) for granule in range(count - 1)} | {(0, granule) for granule in range(1, count)}))
        for first, second in pairs:
            for a, b in product((first * config.granule_width, config.width + first),
                                (second * config.granule_width, config.width + second)):
                await self.fault('cross_granule_detected', base, (a, b), source=source)
        for vector in error_patterns(config):
            await self.fault('error_vector_pattern', base,
                tuple(config.width + granule for granule in range(count) if vector & (1 << granule)), source=source)

    async def partial_writes(self):
        config = self.config
        base = self.rng.getrandbits(config.width)
        received = encode(config, self.rng.getrandbits(config.width))
        for selection in error_patterns(config):
            for odd in (0, 1):
                await self.send('partial_write_baseline', base, received)
                mask = sum((1 << (granule * config.granule_width)) for granule in range(config.parity_width) if selection & (1 << granule))
                # Even updates change two data bits where possible. A selected
                # one-bit granule may also be written with its unchanged value.
                if not odd:
                    mask = mask | (mask << 1) if config.granule_width > 1 else 0
                await self.send('partial_write_granule_update', base ^ mask, received,
                                selection=selection, previous_source=base)

    async def independence_and_unknowns(self):
        config = self.config
        source_pairs = [(0, 0), (0, 1), (1, 0)] + ([(1, (1 << config.width) - 1)] if config.width > 1 else [])
        for source, received in product(source_pairs, ((0, 0), (0, 1), (1, 0), (1, 2))):
            await self.send('transition_baseline', source[0], received[0])
            await self.send('independent_transition_cross', source[1], received[1])
        for state in 'xz':
            known_source = self.rng.getrandbits(config.width)
            received = bits(encode(config, self.rng.getrandbits(config.width)), config.code_width)
            source = bits(known_source, config.width)
            for bit in range(config.width):
                word = list(source)
                word[-bit-1] = state
                await self.send('unknown_generation', ''.join(word), received)
            for bit in range(config.code_width):
                word = list(received)
                word[-bit-1] = state
                await self.send('unknown_checker', known_source, ''.join(word))
            if config.parity_width > 1:
                word = list(received)
                word[-1] = state
                other_parity = config.width + config.parity_width - 1
                word[-other_parity-1] = str(1 - int(word[-other_parity-1]))
                await self.send('known_error_dominates_unknown', known_source, ''.join(word))
            await self.send('all_unknown', state * config.width, state * config.code_width)
        await self.send('mixed_unknown', ''.join('xz'[bit % 2] for bit in range(config.width)),
                        ''.join('zx'[bit % 2] for bit in range(config.code_width)))

    async def body(self):
        await self.send('initial_zero', 0, 0, base=0)
        await self.data_patterns()
        await self.faults()
        await self.partial_writes()
        await self.independence_and_unknowns()
        config = self.config
        for index in range(config.random_cycles):
            source = self.rng.getrandbits(config.width)
            if index % 2:
                # Arbitrary received parity is not assumed to come from this
                # codec or to be associated with the generation input.
                await self.send(f'random:{index}', source, self.rng.getrandbits(config.code_width), random=True)
            else:
                base = self.rng.getrandbits(config.width)
                weight = self.rng.randrange(min(9, config.code_width + 1))
                await self.fault(f'random:{index}', base, tuple(self.rng.sample(range(config.code_width), weight)),
                                 source=source, random=True)
        for _ in range(8):
            await self.send('stable_idle', 0, 0, base=0)
