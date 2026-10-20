"""Layout vectors, exhaustive practical fault pairs, syndrome sweeps and X/Z."""

from itertools import combinations, product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from ecc.model import encode
from ecc.transaction import EccItem


class EccSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('ecc_sequence')
        self.config = config
        self.rng = random.Random(config.seed)

    async def send(self, label, source, received, *, base=None, faults=(), random=False):
        item=EccItem(label,bits(source,self.config.width),bits(received,self.config.code_width),base=base,faults=faults,random=random)
        await self.start_item(item)
        await self.finish_item(item)

    async def fault(self, label, base, faults=(), *, source=None, random=False):
        received=encode(self.config,base) ^ sum(1 << bit for bit in faults)
        await self.send(label,self.rng.getrandbits(self.config.width) if source is None else source,received,
                        base=base,faults=faults,random=random)

    async def patterns(self):
        config=self.config
        maximum=(1 << config.width)-1
        patterns={0,maximum,int(('01'*config.width)[:config.width],2),int(('10'*config.width)[:config.width],2)}
        patterns.update(1 << bit for bit in range(config.width))
        patterns.update(maximum ^ (1 << bit) for bit in range(config.width))
        for value in sorted(patterns):
            await self.fault('data_pattern',value,source=value)
        if config.width<=8:
            for value in range(1 << config.width):
                await self.fault('exhaustive_encode',value,source=value)
        if config.code_width<=13:
            for received in range(1 << config.code_width):
                await self.send('exhaustive_received',self.rng.getrandbits(config.width),received)

    async def all_faults(self):
        config=self.config
        for base in (0,(1 << config.width)-1):
            for bit in range(config.code_width):
                await self.fault('single_fault',base,(bit,),source=base ^ ((1 << config.width)-1))
        # Linear parity guarantees are additionally checked with a nonzero base
        # so fail-closed data cannot pass merely because the original was zero.
        base=self.rng.getrandbits(config.width) or 1
        # Exhaustive decoder faults hold the unrelated encoder input steady.
        # Separate transition/random campaigns exercise simultaneous activity.
        independent_source=base ^ ((1 << config.width)-1)
        for pair in combinations(range(config.code_width),2):
            await self.fault('double_fault',base,pair,source=independent_source)
        for syndrome,overall in product(range(1 << config.parity_bits),(0,1)):
            positions=[(1 << parity)-1 for parity in range(config.parity_bits) if syndrome & (1 << parity)]
            if len(positions)%2 != overall:
                positions.append(config.hamming_width)
            await self.fault('syndrome_class',base,positions,source=independent_source)
        # These are outside the guarantee: three flips mimic a different data
        # bit; a four-bit valid-codeword difference is completely undetected.
        await self.fault('miscorrection_example',0,(0,1,config.hamming_width))
        valid_difference=encode(config,1)
        await self.fault('undetected_example',0,tuple(bit for bit in range(config.code_width) if valid_difference & (1 << bit)))
        if config.width>1:
            await self.fault('large_uncorrectable_example',base,(0,1,2,3))
        triples=list(combinations(range(config.code_width),3)) if config.code_width<=13 else [tuple(sorted(self.rng.sample(range(config.code_width),3))) for _ in range(256)]
        for triple in triples:
            await self.fault('triple_characterization',base,triple,source=independent_source)

    async def independence_and_unknowns(self):
        config=self.config
        encodings=(0,1) if config.width==1 else (0,1,(1 << config.width)-1)
        for source,received in product(encodings,(0,1,3)):
            await self.send('transition_baseline',0,0)
            await self.send('independent_transitions',source,received)
        for state in 'xz':
            source_base=bits(self.rng.getrandbits(config.width),config.width)
            known_received=encode(config,self.rng.getrandbits(config.width))
            for bit in range(config.width):
                source=list(source_base)
                source[-bit-1]=state
                await self.send('unknown_encode',''.join(source),known_received)
            known_source=self.rng.getrandbits(config.width)
            received_base=bits(encode(config,self.rng.getrandbits(config.width)),config.code_width)
            for bit in range(config.code_width):
                received=list(received_base)
                received[-bit-1]=state
                await self.send('unknown_decode',known_source,''.join(received))
            await self.send('all_unknown',state*config.width,state*config.code_width)
        await self.send('mixed_unknown',''.join('xz'[bit%2] for bit in range(config.width)),
                        ''.join('zx'[bit%2] for bit in range(config.code_width)))

    async def body(self):
        await self.send('initial_zero',0,0,base=0)
        await self.patterns()
        await self.all_faults()
        await self.independence_and_unknowns()
        config=self.config
        for index in range(config.random_cycles):
            base=self.rng.getrandbits(config.width)
            weight=self.rng.choice((0,1,2,3,min(4,config.code_width)))
            faults=tuple(sorted(self.rng.sample(range(config.code_width),weight)))
            await self.fault(f'random:{index}',base,faults,random=True)
        for _ in range(8):
            await self.send('stable_idle',0,0,base=0)
