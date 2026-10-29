"""Passive comparison of every event field, source grant and completion bit."""
from collections import Counter
from pyuvm import ConfigDB, uvm_subscriber
from cluster.events_model import EventLedger
from mosaic_uvm.components import CoverageCollector


class EventCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.cycles = 0
        self.counts = Counter()
        self.random_transactions = 0
        names = ['reset', 'critical_priority', 'tile_round_robin', 'held_grant',
                 'full_queue_backpressure', 'simultaneous_pop_push', 'full_identity_snapshot',
                 'completion_clear_and_duplicate', 'unknown_fails_closed',
                 'sequence_exhaustion_never_wraps', 'seeded_traffic', 'reset_with_pending',
                 'withdrawn_held_request_is_reported']
        if self.config.parameters['PROTECT_EVENTS']:
            names += ['protected_queue_fail_stop', 'protected_completion_fail_stop']
        self.goals = dict.fromkeys(names, False)
        self.sources = set()

    def hit(self, name):
        assert name in self.goals, name
        self.goals[name] = True

    def report(self):
        return dict(status='PASS' if all(self.goals.values()) else 'FAIL',
                    goals=self.goals, parameters=self.config.parameters, seed=self.config.seed,
                    cycles=self.cycles, counts=dict(self.counts), sources=sorted(self.sources),
                    random_transactions=self.random_transactions)


class EventScoreboard(uvm_subscriber):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.model = self.fresh()
        self.held = None
        self.ingress_held = {}

    def fresh(self):
        p = self.c.parameters
        return EventLedger(p['NUM_TILES'], p['EVENT_DEPTH'],
                           [p['TILE_ID_TABLE'] >> (t * 8) & 255 for t in range(p['NUM_TILES'])])

    def write(self, obs):
        if obs.phase != 'pre':
            return
        c, p = self.coverage, obs.ports
        c.cycles += 1
        if p['i_rstb'] != 1:
            c.counts['reset_invalidated_records'] += len(self.model.queue)
            self.model = self.fresh()
            self.held = None
            self.ingress_held.clear()
            return
        if not p['o_error'] and not getattr(obs.item, 'protocol_violation', False):
            for t in range(self.c.parameters['NUM_TILES']):
                valid = (p['i_tile_valid'] or 0) >> t & 1
                ready = p['o_tile_ready'] >> t & 1
                payload = p['i_tile_payload'] >> (256 * t) & ((1 << 256) - 1)
                if t in self.ingress_held:
                    assert valid and payload == self.ingress_held[t], ('Producer changed held beat', t)
                if valid and not ready:
                    self.ingress_held[t] = payload
                else:
                    self.ingress_held.pop(t, None)
        else:
            self.ingress_held.clear()
        corruption = None
        if obs.item.fault and obs.item.fault[0] != 'release':
            path = obs.item.fault[0]
            if 'u_sequence' in path:
                self.model.sequence = 0xffffffff
            else:
                corruption = 'queue' if 'u_queue' in path else 'completion'
        expected, accepted, concurrent = self.model.step(p, corruption=corruption)
        for name, value in expected.items():
            assert p[name] == value, (obs.item.get_name(), name, p[name], value)
        payload = tuple(p['o_event_' + field] for field in ('type', 'source_id', 'owner_id',
            'kernel_id', 'context_id', 'package_id', 'epoch', 'payload', 'severity', 'sequence'))
        if corruption == 'queue':
            self.held = None  # A corrupt transport is invalid until coordinated reset.
        if self.held is not None:
            assert p['o_event_valid'] and payload == self.held
        self.held = payload if p['o_event_valid'] and p['i_event_ready'] != 1 else None
        if accepted is not None:
            c.counts['accepted'] += 1
            if isinstance(accepted, int):
                c.sources.add(accepted)
                c.counts['tile_' + str(accepted)] += 1
            else:
                c.counts[accepted] += 1
        if p['o_event_valid'] and p['i_event_ready'] == 1:
            c.counts['delivered'] += 1
        if concurrent:
            c.counts['simultaneous_pop_push'] += 1
        if p['o_event_valid'] and p['i_event_ready'] != 1:
            c.counts['held_output_cycles'] += 1
        if p['o_error']:
            c.counts['contained_cycles'] += 1

    def check_phase(self):
        self.model.drained()
        assert self.held is None and not self.ingress_held
        assert self.coverage.counts['accepted'] == self.coverage.counts['delivered'] + \
            self.coverage.counts['reset_invalidated_records']
        assert self.coverage.sources == set(range(self.c.parameters['NUM_TILES']))
