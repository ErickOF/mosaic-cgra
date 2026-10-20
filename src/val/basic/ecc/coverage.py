"""Every single bit, unordered pair, syndrome class, and independent cone cross."""

from collections import Counter, defaultdict
from itertools import combinations, product
from mosaic_uvm.components import CoverageCollector
from ecc.model import known


def transition(previous, current):
    count = (previous ^ current).bit_count()
    return 'stable' if count == 0 else 'one' if count == 1 else 'many'


class EccCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.bins = defaultdict(set)
        self.activity = Counter()
        self.checks = Counter()
        self.random_checks = 0
        self.previous = None

    def sample(self, observation):
        self.checks[observation.stage] += 1
        if observation.stage != 'settled':
            return
        config, p, item = self.config, observation.ports, observation.item
        self.random_checks += item.random
        if known(item.encode):
            value = int(item.encode, 2)
            if value == 0:
                self.bins['patterns'].add('zero')
            if value == (1 << config.width)-1:
                self.bins['patterns'].add('ones')
            if value.bit_count() == 1:
                self.bins['walking_one'].add(value.bit_length()-1)
            complement = value ^ ((1 << config.width)-1)
            if complement.bit_count() == 1:
                self.bins['walking_zero'].add(complement.bit_length()-1)
        for signal, width in (('i_encode_data',config.width),('i_decode_codeword',config.code_width)):
            for bit,char in enumerate(reversed(p[signal])):
                if char in 'xz':
                    self.bins[signal + '_unknown'].add((bit,char))
        if known(item.received):
            classification = next(name for name in ('no_error','corrected','uncorrectable') if p['o_'+name] == '1')
            self.bins['syndrome_parity'].add((int(p['o_syndrome'],2),int(p['o_overall_parity_error'])))
            if item.base is not None:
                weight = min(len(item.faults),3)
                self.bins['weight_class'].add((weight,classification))
                if len(item.faults)==1:
                    bit=item.faults[0]
                    self.bins['single_bits'].add(bit)
                    self.bins['position_role'].add((int(p['o_error_position'],2),config.role(bit)))
                    self.bins['role_scrub'].add((config.role(bit),int(p['o_corrected']),int(p['o_scrub_required'])))
                if len(item.faults)==2:
                    self.bins['double_pairs'].add(tuple(sorted(item.faults)))
                    self.bins['double_roles'].add(tuple(sorted(config.role(bit) for bit in item.faults)))
                if len(item.faults)>2 and classification=='corrected' and int(p['o_decoded_data'],2)!=item.base:
                    self.bins['larger_fault_examples'].add('miscorrected')
                if len(item.faults)>2 and classification=='no_error' and int(p['o_decoded_data'],2)!=item.base:
                    self.bins['larger_fault_examples'].add('undetected')
            if known(item.encode):
                current=(int(item.encode,2),int(item.received,2))
                if self.previous is not None:
                    self.bins['cone_transitions'].add(tuple(transition(old,new) for old,new in zip(self.previous,current)))
                self.previous=current
        else:
            self.previous=None

    def report(self):
        config = self.config
        pairs=set(combinations(range(config.code_width),2))
        roles={config.role(bit) for bit in range(config.code_width)}
        expected={
            'single_bits':set(range(config.code_width)),
            'position_role':{(bit,config.role(bit)) for bit in range(config.code_width)},
            'role_scrub':{(role,1,1) for role in roles},
            'double_pairs':pairs,
            'double_roles':{tuple(sorted((config.role(first),config.role(second)))) for first,second in pairs},
            'syndrome_parity':set(product(range(1 << config.parity_bits),(0,1))),
            'patterns':{'zero','ones'},
            'walking_one':set(range(config.width)), 'walking_zero':set(range(config.width)),
            'i_encode_data_unknown':set(product(range(config.width),'xz')),
            'i_decode_codeword_unknown':set(product(range(config.code_width),'xz')),
            'cone_transitions':set(product(('stable','one') if config.width==1 else ('stable','one','many'),('stable','one','many'))),
            'weight_class':{(0,'no_error'),(1,'corrected'),(2,'uncorrectable'),(3,'corrected'),(3,'no_error')} | ({(3,'uncorrectable')} if config.width>1 else set()),
            'larger_fault_examples':{'miscorrected','undetected'},
        }
        goals={name:required <= self.bins[name] for name,required in expected.items()}
        goals.update(randomized=self.random_checks>=config.random_cycles,
                     settled_and_held=self.checks['settled']==self.checks['held'] and self.checks['held']>0,
                     parity_bound_minimal=(1 << config.parity_bits)>=config.width+config.parity_bits+1 and
                         (config.parity_bits==1 or (1 << (config.parity_bits-1))<config.width+config.parity_bits))
        return dict(status='PASS' if all(goals.values()) else 'FAIL',parameters=config.parameters,seed=config.seed,
                    geometry=dict(parity_bits=config.parity_bits,hamming_width=config.hamming_width,code_width=config.code_width),
                    goals=goals,missing={name:sorted(required-self.bins[name],key=repr) for name,required in expected.items() if required-self.bins[name]},
                    bins={name:sorted(values,key=repr) for name,values in self.bins.items()},
                    checked_observations=dict(self.checks),random_transactions=self.random_checks,
                    structural_assertions='PASS' if config.check_internals else 'NOT_RUN',waveform_transitions=dict(self.activity),
                    waivers=dict(out_of_range_syndrome='No unused syndrome' if config.hamming_width==(1 << config.parity_bits)-1 else 'All unused syndromes tested',
                                 larger_fault_uncorrectable='No such pattern in the four-bit minimum code' if config.width==1 else 'applicable',
                                 double_pairs='Every unordered pair simulated; no simulation waiver'))
