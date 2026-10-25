"""Coverage records checked state transitions and explicit qualification limits."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector
from event_barrier.model import number


class EventBarrierCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.events = Counter()
        self.observations = Counter()
        self.counts = set()
        self.any_winners = set()
        self.wait_slots = set()
        self.barriers = set()
        self.participants = set()
        self.occupancies = [set(), set()]
        self.faults = set()
        self.random_transactions = 0
        self.unknowns = set()
        self.error_codes = set()
        self.mutations = set()
        self.wait_cross = set()
        self.generation_wraps = 0
        self.previous_generation = None

    def record(self, events, obs, model, before):
        self.events.update(events)
        p, c = obs.item.pre.ports, self.config
        value = lambda name: number(p[name])
        self.random_transactions += int(obs.item.random)
        if obs.item.fault:
            self.faults.add(obs.item.fault)
        for name, raw in p.items():
            if name.startswith('i_') and number(raw) is None:
                self.unknowns.add(name)
        for e, count in enumerate(model.counts):
            self.counts.add((e, count))
        self.occupancies[0].add(len(model.results))
        self.occupancies[1].add(len(model.releases))
        self.error_codes.add(model.error)
        if 'event_wait_complete' in events:
            r = model.results[-1]
            self.wait_slots.add(r['slot'])
            self.wait_cross.add((r['mode'], bool(r['consumed_mask'])))
            if r['mode'] == 0:
                self.any_winners.add(r['matched_mask'].bit_length() - 1)
            if r['consumed_mask']:
                self.mutations.add(2)
        if 'post_accepted' in events:
            self.mutations.add(0)
        if 'ack_accepted' in events:
            self.mutations.add(1)
        if 'barrier_arrival_accepted' in events:
            b, participant = value('i_barrier_arrival_id'), value('i_barrier_participant_id')
            self.barriers.add(b)
            self.participants.add((b, participant))
        if 'event_barrier_release' in events:
            r = model.releases[-1]
            if r['event_enable']:
                self.mutations.add(3)
            if r['generation'] == (1 << c.GENERATION_WIDTH) - 1:
                self.generation_wraps += 1

    def report(self):
        c = self.config
        required = ('config_accepted', 'config_rejected', 'post_accepted', 'post_rejected',
                    'ack_accepted', 'ack_rejected', 'wait_armed', 'wait_rejected',
                    'wait_cancel_not_found', 'barrier_configured', 'barrier_config_rejected',
                    'barrier_arrival_accepted', 'barrier_arrival_rejected',
                    'event_wait_complete', 'event_barrier_release', 'event_mutation_stall', 'flushed',
                    'reset', 'result_pop', 'release_pop')
        goals = {name: self.events[name] > 0 for name in required}
        goals.update(all_count_values=len(self.counts) == c.NUM_EVENTS * (1 << c.EVENT_COUNT_WIDTH),
                     every_any_winner=self.any_winners == set(range(c.NUM_EVENTS)),
                     every_wait_slot=self.wait_slots == set(range(c.NUM_WAIT_SLOTS)),
                     every_barrier=self.barriers == set(range(c.NUM_BARRIERS)),
                     every_participant=len(self.participants) == c.NUM_BARRIERS * c.MAX_PARTICIPANTS,
                     wait_queue_all_occupancies=self.occupancies[0] == set(range(c.WAIT_RESULT_QUEUE_DEPTH + 1)),
                     release_queue_all_occupancies=self.occupancies[1] == set(range(c.BARRIER_RELEASE_QUEUE_DEPTH + 1)),
                     generation_wrap=self.generation_wraps > 0,
                     unknown_injection=len(self.unknowns) >= 10,
                     random_transactions=self.random_transactions == c.random_cycles,
                     all_mutation_clients=self.mutations == ({0, 1, 2, 3} if c.SUPPORT_BARRIER_EVENTS and c.SUPPORT_WAIT_CONSUME else
                         {0, 1, 3} if c.SUPPORT_BARRIER_EVENTS else {0, 1, 2} if c.SUPPORT_WAIT_CONSUME else {0, 1}))
        if c.MAX_PARTICIPANTS > 1:
            goals['duplicate_arrival'] = self.events['event_duplicate_arrival'] > 0
        if c.SUPPORT_WAIT_CANCEL:
            goals['canceled'] = self.events['wait_canceled'] > 0
        if c.PROTECT_STATE and c.check_internals:
            goals['protected_state_injections'] = self.faults == {'policy', 'event', 'wait', 'barrier', 'generation', 'queue'}
        return dict(status='PASS' if all(goals.values()) else 'FAIL', framework='PyUVM',
                    parameters=c.parameters, seed=c.seed, random_transactions=self.random_transactions,
                    goals=goals, events=dict(self.events), observations=dict(self.observations),
                    count_bins=len(self.counts), any_winners=sorted(self.any_winners),
                    wait_cross=sorted(self.wait_cross), mutation_clients=sorted(self.mutations),
                    errors=sorted(self.error_codes), unknown_inputs=sorted(self.unknowns),
                    faults=sorted(self.faults),
                    protected_state_injection='PASS' if self.faults else 'NOT_RUN',
                    hdl_assertions='PASS' if c.hdl_assertions else 'NOT_RUN',
                    external_checks=dict.fromkeys(('formal', 'vcs', 'cdc', 'rdc', 'dft', 'vc_lp',
                        'technology_synthesis', 'physical_timing', 'physical_power'), 'NOT_RUN'))
