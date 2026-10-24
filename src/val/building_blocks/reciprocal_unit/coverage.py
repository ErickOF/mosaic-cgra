"""Report coverage only from checked responses, events and actual handshakes."""
from collections import Counter
import hashlib
import json
from mosaic_uvm.components import CoverageCollector


class ReciprocalCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.accepted = self.returned = self.discarded = self.random_cycles = 0
        self.flushes = self.unknowns = self.fatal_events = self.max_occupancy = 0
        self.events = Counter()
        self.signs = set()
        self.leading = set()
        self.addresses = set()
        self.address_iterations = set()
        self.iterations = set()
        self.modes = set()
        self.zero_signed = set()
        self.ties = set()
        self.shifts = set()
        self.statuses = set()
        self.latencies = set()
        self.directions = set()
        self.labels = set()
        self.fault_masks = set()
        self.ownership_faults = set()
        self.trace = []
        self.exhaustive_inputs = set()

    def complete(self, token, latency):
        request, result, stats = (token[k] for k in ('request', 'result', 'stats'))
        self.iterations.add(result['iterations'])
        self.modes.add(request['round_mode'])
        self.statuses.add(tuple(result[k] for k in ('overflow', 'underflow', 'predicated', 'error')))
        if result['divide_by_zero']:
            self.zero_signed.add(result['signed'])
        if stats['active']:
            self.signs.add((request['signed'], stats['negative']))
            self.leading.add(stats['leading'])
            self.addresses.add(stats['address'])
            self.address_iterations.add((stats['address'], request['iterations']))
            self.shifts.add((stats['output_shift'] > 0) - (stats['output_shift'] < 0))
            self.ties |= stats['ties']
            self.directions |= stats['directions']
        if 'equivalence' in token['label']:
            self.trace.append({k: v for k, v in result.items() if k not in ('context_id', 'tag')})
        if 'exhaustive' in token['label']:
            self.exhaustive_inputs.add((request['operand'], request['signed'],
                                       request['iterations'], request['round_mode']))
        if 'latency' in token['label']:
            self.latencies.add((request['iterations'], latency))

    def report(self):
        from reciprocal_unit.model import encode, evaluate
        from reciprocal_unit.sequences import reachable_addresses
        c = self.config
        reachable = reachable_addresses(c)
        word_bits = encode(0, c.INTERNAL_WIDTH, c.SEED_PROTECTION)[1]
        required_ties = set()
        required_boundaries = set()
        required_directions = set()
        from reciprocal_unit.sequences import address_operands
        for operand in address_operands(c):
            for count in range(c.MAX_ITERATIONS + 1):
                for mode in (0, 1):
                    result, stats = evaluate(c, dict(operand=operand, signed=0,
                        iterations=count, round_mode=mode, predicate=1, context_id=0, tag=0))
                    required_ties |= stats['ties']
                    required_directions |= stats['directions']
                    required_boundaries.add(tuple(result[k] for k in (
                        'overflow', 'underflow', 'predicated', 'error')))
        goals = dict(directed_rounding_ties=required_ties <= self.ties,
            numerical_boundaries=required_boundaries <= self.statuses,
            newton_directions=required_directions <= self.directions,
            normalization_events=self.events['normalize'] > 0,
            seed_events=self.events['seed_lookup'] > 0,
            iteration_events=(self.events['iteration'] > 0) == bool(c.MAX_ITERATIONS),
            flush_every_phase={f'flush_phase_{p}' for p in range(c.latency)} <= self.labels,
every_iteration=self.iterations == set(range(c.MAX_ITERATIONS + 1)),
            both_round_modes=self.modes == {0, 1}, signedness=self.signs == {(0, False), (1, False), (1, True)},
            every_leading_one=self.leading == set(range(c.INPUT_WIDTH)),
            every_reachable_seed_address=reachable <= self.addresses,
            seed_by_iterations={(a, i) for a in reachable for i in range(c.MAX_ITERATIONS + 1)}
                <= self.address_iterations,
            zero_both_signedness=self.zero_signed == {0, 1},
            exact_latency={(i, c.latency if c.EVALUATION_ARCH else 3 + 2 * i)
                for i in range(c.MAX_ITERATIONS + 1)} <= self.latencies,
            output_backpressure=self.events['result_stall'] > 0,
            request_backpressure=self.events['request_stall'] > 0,
            full_queue=self.max_occupancy == c.OUTPUT_QUEUE_DEPTH,
            predication=any(s[2] for s in self.statuses), flush=self.flushes > 0,
            unknowns=self.unknowns > 0, fatal_containment=self.fatal_events > 0,
            ownership_faults={'state', 'queue', 'errors', 'identity', 'internal'} <= self.ownership_faults
                if c.SEED_PROTECTION else {'identity', 'internal'} <= self.ownership_faults,
            seed_faults=({1 << b for b in range(word_bits)} <= self.fault_masks
                if c.SEED_PROTECTION else 'x' in self.fault_masks),
            exhaustive_reduced_inputs=(len(self.exhaustive_inputs) ==
                (1 << c.INPUT_WIDTH) * 2 * 2 * (c.MAX_ITERATIONS + 1)
                if c.INPUT_WIDTH <= 8 else True),
            randomized_traffic=self.random_cycles == c.random_cycles,
            conservation=self.accepted == self.returned + self.discarded)
        return dict(status='PASS' if all(goals.values()) else 'FAIL', goals=goals,
            parameters=c.parameters, seed=c.seed, random_transactions=self.random_cycles,
            accepted=self.accepted, returned=self.returned, discarded=self.discarded,
            flushes=self.flushes, unknowns=self.unknowns, fatal_events=self.fatal_events,
            events=dict(self.events), addresses=sorted(self.addresses),
            reachable_addresses=sorted(reachable), leading=sorted(self.leading),
            ties=sorted(self.ties), directions=sorted(self.directions), shifts=sorted(self.shifts),
            latencies=sorted(self.latencies), exhaustive_inputs=len(self.exhaustive_inputs),
            arithmetic_signature=hashlib.sha256(json.dumps(self.trace, sort_keys=True).encode()).hexdigest(),
            hdl_assertions='NOT_RUN', synthesis='Design Compiler (deferred)')
