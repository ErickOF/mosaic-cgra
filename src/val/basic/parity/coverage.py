"""Mandatory fault-role, granule, limitation, transition and X/Z coverage."""

from collections import Counter
from itertools import product
from mosaic_uvm.components import CoverageCollector
from parity.model import error_patterns, generate, known, transition


class ParityCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.single_faults, self.granule_status, self.vectors, self.fail_counts = set(), set(), set(), set()
        self.same_pairs, self.cross_pairs, self.higher = set(), set(), set()
        self.partial, self.transitions, self.unknown = set(), set(), set()
        self.checks, self.activity = Counter(), Counter()
        self.random_transactions = self.undetected_patterns = 0
        self.previous = None

    def sample(self, observation):
        self.checks[observation.stage] += 1
        if observation.stage != 'settled':
            return
        config, ports, item = self.config, observation.ports, observation.item
        self.random_transactions += int(item.random)
        for name, word in (('generate', item.source), ('data', item.data), ('parity', item.parity)):
            self.unknown.update((name, bit, state) for bit, state in enumerate(reversed(word)) if state in 'xz')
        if known(item.source + item.data + item.parity):
            source, received = int(item.source, 2), int(item.parity + item.data, 2)
            if self.previous is not None:
                self.transitions.add((transition(self.previous[0], source), transition(self.previous[1], received)))
            self.previous = source, received
        else:
            self.previous = None
        if known(ports['o_error_vector']):
            vector = int(ports['o_error_vector'], 2)
            self.vectors.add(vector)
            self.fail_counts.add((vector.bit_count(), int(ports['o_any_error'])))
            self.granule_status.update((granule, (vector >> granule) & 1) for granule in range(config.parity_width))
        if item.base is not None:
            if len(item.faults) == 1:
                self.single_faults.add(item.faults[0])
            elif len(item.faults) == 2:
                granules = tuple(config.granule(bit) for bit in item.faults)
                roles = ''.join(sorted('d' if bit < config.width else 'p' for bit in item.faults))
                if granules[0] == granules[1]:
                    self.same_pairs.add((granules[0], roles, int(ports['o_any_error'])))
                else:
                    self.cross_pairs.add(roles)
            elif len(item.faults) >= 3 and len({config.granule(bit) for bit in item.faults}) == 1:
                self.higher.add((config.granule(item.faults[0]), len(item.faults) % 2, int(ports['o_any_error'])))
            self.undetected_patterns += int(bool(item.faults) and ports['o_any_error'] == '0')
        if item.selection is not None:
            old = generate(config, f'{item.previous_source:0{config.width}b}')
            self.partial.update((granule, (item.selection >> granule) & 1,
                                 int(old[-granule-1] != ports['o_generated_parity'][-granule-1]))
                                for granule in range(config.parity_width))

    def report(self):
        c = self.config
        source_classes = {'hold', 'rise', 'fall'} | ({'change'} if c.width > 1 else set())
        same_roles = {'dp'} | ({'dd'} if c.granule_width > 1 else set())
        expected_higher = {(granule, parity, parity) for granule in range(c.parity_width)
                           for parity in ((1, 0) if c.granule_width >= 3 else (1,) if c.granule_width == 2 else ())}
        goals = dict(every_single_protected_bit=self.single_faults == set(range(c.code_width)),
            every_granule_clean_and_failing=set(product(range(c.parity_width), (0, 1))) <= self.granule_status,
            error_vector_patterns=set(error_patterns(c)) <= self.vectors,
            every_failing_granule_count={(count, int(count > 0)) for count in range(c.parity_width + 1)} <= self.fail_counts,
            same_granule_double_limit={(granule, role, 0) for granule in range(c.parity_width) for role in same_roles} <= self.same_pairs,
            cross_granule_double_detection=({'dd', 'dp', 'pp'} <= self.cross_pairs if c.parity_width > 1 else True),
            higher_odd_even_limit=expected_higher <= self.higher,
            undetected_limitation_recorded=self.undetected_patterns > 0,
            partial_write_transition_cross={(granule, selected, changed) for granule in range(c.parity_width)
                for selected, changed in ((0, 0), (1, 0), (1, 1))} <= self.partial,
            independent_cone_transition_cross=set(product(source_classes, ('hold', 'rise', 'fall', 'change'))) <= self.transitions,
            every_generation_unknown_bit=set(product(('generate',), range(c.width), 'xz')) <= self.unknown,
            every_checked_data_unknown_bit=set(product(('data',), range(c.width), 'xz')) <= self.unknown,
            every_checked_parity_unknown_bit=set(product(('parity',), range(c.parity_width), 'xz')) <= self.unknown,
            randomized_campaign=self.random_transactions == c.random_cycles,
            settled_and_held_checks=self.checks['settled'] == self.checks['held'] and self.checks['settled'] > 0)
        return dict(status='PASS' if all(goals.values()) else 'FAIL', parameters=c.parameters, seed=c.seed,
            random_transactions=self.random_transactions, goals=goals, checked_observations=dict(self.checks),
            elaboration_assertions='PASS' if c.check_internals else 'NOT_RUN', waveform_transitions=dict(self.activity),
            single_fault_bits=len(self.single_faults), expected_undetected_cases=self.undetected_patterns,
            failing_granule_counts=sorted(self.fail_counts), same_granule_double_bins=sorted(self.same_pairs),
            cross_granule_double_roles=sorted(self.cross_pairs), higher_weight_bins=sorted(self.higher),
            partial_write_bins=sorted(self.partial), independent_transition_bins=sorted(self.transitions),
            waivers=dict(same_granule_data_pairs='Unreachable with one data bit per granule' if c.granule_width == 1 else 'applicable',
                         cross_granule_faults='Unreachable with one granule' if c.parity_width == 1 else 'applicable',
                         higher_weight='Three protected bits required for triple faults; four for quadruple faults'))
