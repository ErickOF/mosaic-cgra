"""Mandatory edge, fanout, partial-progress, flush and delivery accounting goals."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector
from local_switch.model import number


def maximum_matching(c):
    reachable = {frozenset()}
    for o in range(c.NUM_OUTPUTS):
        reachable |= {used | {i} for used in tuple(reachable) for i in range(c.NUM_INPUTS)
                      if i not in used and (i, o) in c.edges}
    return max(map(len, reachable))


class LocalSwitchCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.events = Counter()
        self.observations = Counter()
        self.edges = set()
        self.fanouts = set()
        self.occupancies = set()
        self.flushed_masks = set()
        self.flush_occupancies = set()
        self.reset_occupancies = set()
        self.first_multicast = set()
        self.last_multicast = set()
        self.first = set()
        self.last = set()
        self.errors = set()
        self.unknowns = set()
        self.random_transactions = self.storage_checks = self.decode_checks = 0
        self.accounting = {}

    def record(self, events, obs, model, plan):
        c = self.config
        self.accounting = model.accounting()
        self.random_transactions += int(obs.item.random)
        self.occupancies.add(sum(bool(model.pending(i)) for i in range(c.NUM_INPUTS)))
        for name, raw in obs.item.pre.ports.items():
            if name.startswith('i_') and number(raw) is None:
                self.unknowns.add(name)
        if not obs.item.edge:
            return
        self.events.update({n: int(bool(value)) for n, value in events.items()})
        if plan['run'] and plan['detected']:
            self.errors.add(plan['detected'])
        pre = obs.item.pre.ports
        for i, accepted in enumerate(plan['accept']):
            if not plan['run'] or not accepted:
                continue
            pending = model.pending(i)
            self.edges |= {(i, o) for o in range(c.NUM_OUTPUTS) if pending >> o & 1}
            self.fanouts.add((i, pending.bit_count()))
            if plan['complete'][i]:
                self.events['replacement'] += 1
                if obs.item.random:
                    self.events['random_replacement'] += 1
        for o, transferred in enumerate(plan['transfer']):
            if not transferred or not plan['run']:
                continue
            source = model.select[o]
            old_pending = (int(pre['o_pending_delivery'], 2) >> (source * c.NUM_OUTPUTS)) & ((1 << c.NUM_OUTPUTS) - 1)
            if old_pending == (1 << o):
                self.last.add((source, o))
                if plan['delivery_tokens'][o].destinations.bit_count() > 1:
                    self.last_multicast.add((source, o))
            if old_pending == model.destinations(source):
                self.first.add((source, o))
                if plan['delivery_tokens'][o].destinations.bit_count() > 1:
                    self.first_multicast.add((source, o))
        if plan['flush']:
            packed = int(pre['o_pending_delivery'], 2)
            self.flush_occupancies.add(int(pre['o_input_buffered'], 2).bit_count())
            for i in range(c.NUM_INPUTS):
                mask = (packed >> (i * c.NUM_OUTPUTS)) & ((1 << c.NUM_OUTPUTS) - 1)
                self.flushed_masks.add((i, mask))
        if plan['run'] and plan['traffic'] and obs.item.random:
            if int(events.get('o_event_input_stall', 0)):
                self.events['random_input_stall'] += 1
            if int(events.get('o_event_output_stall', 0)):
                self.events['random_output_stall'] += 1
        if int(pre['o_output_valid'], 2) and int(events.get('o_event_output_transfer', 0)) == int(pre['o_output_valid'], 2):
            self.events['all_outputs_transfer'] += 1

    def report(self):
        c = self.config
        required = ('reset', 'o_config_accepted', 'o_config_rejected', 'o_flushed',
                    'o_event_input_accept', 'o_event_output_transfer', 'o_event_input_stall',
                    'o_event_output_stall', 'o_event_item_complete', 'replacement',
                    'random_input_stall', 'random_output_stall', 'random_replacement', 'all_outputs_transfer')
        goals = {n: self.events[n] > 0 for n in required}
        fanouts = {(i, n) for i in range(c.NUM_INPUTS) for n in range(1, 1 + (
            sum(source == i for source, _ in c.edges) if c.SUPPORT_MULTICAST else
            int(any(source == i for source, _ in c.edges))))}
        flush_masks = {(i, 0) for i in range(c.NUM_INPUTS)}
        for i in range(c.NUM_INPUTS):
            destinations = [o for source, o in sorted(c.edges) if source == i]
            if c.SUPPORT_MULTICAST:
                flush_masks |= {(i, sum(1 << o for k, o in enumerate(destinations) if mask >> k & 1))
                                for mask in range(1 << len(destinations))}
            else:
                flush_masks |= {(i, 1 << o) for o in destinations}
        expected_errors = {4}
        if c.NUM_INPUTS == 1 or c.NUM_INPUTS & (c.NUM_INPUTS - 1):
            expected_errors.add(1)
        if len(c.edges) < c.NUM_INPUTS * c.NUM_OUTPUTS:
            expected_errors.add(2)
        if not c.SUPPORT_MULTICAST and any(sum(source == i for source, _ in c.edges) > 1
                                         for i in range(c.NUM_INPUTS)):
            expected_errors.add(3)
        if c.check_internals:
            expected_errors |= {5, 6, 7}
            goals['payload_storage'] = self.storage_checks > 0
            goals['shared_route_decode'] = self.decode_checks > 0
        goals.update(every_physical_edge=self.edges == c.edges,
                     every_fanout=self.fanouts == fanouts,
                     every_occupancy=self.occupancies == set(range(maximum_matching(c) + 1)),
                     every_flush_occupancy=self.flush_occupancies == set(range(maximum_matching(c) + 1)),
                     every_reset_occupancy=self.reset_occupancies == set(range(maximum_matching(c) + 1)),
                     every_flush_mask=flush_masks <= self.flushed_masks,
                     every_first_consumer=self.first == c.edges,
                     every_last_consumer=self.last == c.edges,
                     every_error_class=expected_errors <= self.errors,
                     unknown_injection=len(self.unknowns) >= 7,
                     random_campaign=self.random_transactions == c.random_cycles,
                     ownership_accounting=bool(self.accounting) and all(
                         row['accepted'] == row['discarded'] + row.get('completed', row.get('delivered', 0))
                         and row['pending'] == 0 for rows in self.accounting.values() for row in rows))
        if c.SUPPORT_MULTICAST and any(n > 1 for _, n in fanouts):
            goals['multicast'] = self.events['o_event_multicast_accept'] > 0
            multicast_edges = {(i, o) for i, o in c.edges if sum(source == i for source, _ in c.edges) > 1}
            goals['first_multicast_consumers'] = self.first_multicast == multicast_edges
            goals['last_multicast_consumers'] = self.last_multicast == multicast_edges
        return dict(status='PASS' if all(goals.values()) else 'FAIL', framework='PyUVM',
            parameters=c.parameters, seed=c.seed, goals=goals, events=dict(self.events),
            accounting=self.accounting, observations=dict(self.observations),
            random_transactions=self.random_transactions, storage_checks=self.storage_checks,
            decode_checks=self.decode_checks,
            physical_edges=sorted(self.edges), fanouts=sorted(self.fanouts),
            flushed_masks=sorted(self.flushed_masks), occupancies=sorted(self.occupancies),
            flush_occupancies=sorted(self.flush_occupancies), reset_occupancies=sorted(self.reset_occupancies),
            first_multicast_consumers=sorted(self.first_multicast), last_multicast_consumers=sorted(self.last_multicast),
            error_classes=sorted(self.errors), parameter_reachable_error_classes=sorted(expected_errors),
            unknown_fields=sorted(self.unknowns),
            hdl_assertions='PASS' if c.hdl_assertions else 'NOT_RUN',
            internal_storage_assertions='PASS' if c.check_internals else 'NOT_RUN',
            external_checks=dict.fromkeys(('formal', 'commercial_lint', 'cdc', 'rdc', 'dft',
                'vc_lp', 'technology_synthesis', 'physical_timing', 'physical_power'), 'NOT_RUN'))
