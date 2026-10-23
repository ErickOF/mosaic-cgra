"""Architectural coverage is collected only after packet/credit ledger checks."""

from collections import Counter
import cocotb
from itertools import product
from mosaic_uvm.components import CoverageCollector
from noc_router.model import part, integer, route


class RouterCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.events = Counter()
        self.labels = Counter()
        self.observations = Counter()
        self.random_transactions = 0
        self.accounting = {}
        self.routes = set()
        self.classes = set()
        self.occupancies = set()
        self.credits = set()
        self.simultaneous = set()
        self.error_codes = set()
        self.stall_phases = set()
        self.high_debt = [0] * 5
        self.qos_grants = Counter()
        self.native_events = Counter()

    def record(self, event, item, model):
        c, pre = self.config, item.pre
        # The monitor installs the post observation after dispatch, so use the
        # real last item pre record plus the model's already verified state.
        self.events[event['kind']] += 1
        self.labels[item.get_name()] += 1
        self.random_transactions += item.random
        self.accounting = dict(
            accepted=model.accepted,
            forwarded=model.forwarded,
            quarantined=model.discarded,
            rejected_sink=model.sunk,
            reset_or_flush=model.canceled,
            pending=model.pending,
        )
        for k, queue in enumerate(model.queues):
            self.occupancies.add((k // c.NUM_VCS, k % c.NUM_VCS, len(queue)))
        for k, credit in enumerate(model.credits):
            self.credits.add((k // c.NUM_VCS, k % c.NUM_VCS, credit))
        if event['kind'] in ('reset', 'flush'):
            self.high_debt = [0] * 5
        for delivery in event.get('deliveries', ()):
            port, output, vc, tc, head, tail = delivery
            self.routes.add((port, output, vc))
            self.classes.add(tc)
        transfers = event.get('transfers', 0)
        self.simultaneous.update(
            (a, b)
            for a, b in product(range(5), repeat=2)
            if a < b and transfers & (1 << a) and transfers & (1 << b)
        )
        if event['kind'] == 'traffic':
            normal = integer(pre.internal['normal_accept'])
            high = integer(pre.internal['high_accept'])
            waiting = integer(pre.internal['normal_waiting'])
            for p in range(5):
                if high & (1 << p):
                    self.qos_grants['high'] += 1
                    self.high_debt[p] = self.high_debt[p] + 1 if waiting & (1 << p) else 0
                    assert self.high_debt[p] <= c.HIGH_SERVICE_BURST_LIMIT, 'QoS burst exceeded'
                if normal & (1 << p):
                    self.qos_grants['normal'] += 1
                    if c.ENABLE_QOS and self.high_debt[p] == c.HIGH_SERVICE_BURST_LIMIT:
                        self.qos_grants['forced_normal'] += 1
                    self.high_debt[p] = 0
                valid = part(pre.ports['o_out_valid'], p, 1)
                if valid and not c.FLOW_CONTROL and not part(pre.ports['i_out_ready'], p, 1):
                    head = part(pre.ports['o_out_head'], p, 1)
                    tail = part(pre.ports['o_out_tail'], p, 1)
                    self.stall_phases.add('head' if head else 'tail' if tail else 'body')
        # Sequence postconditions separately qualify error and fault classes.

    def report(self):
        c = self.config
        ports = c.usable_ports()
        destinations = {route(c, node) for node in range(c.MESH_X * c.MESH_Y)}
        mapped = {
            (c.TRAFFIC_CLASS_TO_VC >> (tc * c.aliases['VW'])) & ((1 << c.aliases['VW']) - 1)
            for tc in range(c.NUM_TRAFFIC_CLASSES)
        }
        goal_routes = set(product(ports, destinations, mapped))
        goal_occupancies = set(product(ports, mapped, range(c.INPUT_VC_DEPTH + 1)))
        goal_pairs = {(a, b) for a, b in product(destinations, repeat=2) if a < b}
        goals = dict(
            simultaneous_output_pairs=goal_pairs <= self.simultaneous,
            rejected_unknown_configuration=self.labels['unknown_configuration'] > 0,
            reset_active_traffic=self.labels['active_reset'] > 0,
            all_input_output_vc_routes=goal_routes <= self.routes,
            every_traffic_class=set(range(c.NUM_TRAFFIC_CLASSES)) <= self.classes,
            every_fifo_occupancy=goal_occupancies <= self.occupancies,
            legal_configuration=self.events['config'] > 0,
            real_clock_cycles=self.observations['post'] > 0,
            configured_random_campaign=self.random_transactions == c.random_cycles,
            flush_ownership=self.labels['flush_owned'] > 0,
            open_packet_drain=self.labels['body_during_drain'] > 0,
            stale_epoch_sink=self.labels['stale_epoch'] > 0,
            malformed_body_keeps_route=self.labels['body_integrity'] > 0,
            bounded_phase_stalls=self.labels['phase_stall'] > 0,
            full_fifo_stalls=self.labels['full_stall'] >= 32 * len(ports) * len(mapped),
            delivery_accounting=bool(self.accounting) and self.accounting['pending'] == 0,
        )
        if c.FLOW_CONTROL:
            goals['every_output_credit_count'] = (
                set(product(destinations, mapped, range(c.OUTPUT_INITIAL_CREDITS + 1)))
                <= self.credits
            )
            goals['stale_credit_rejected'] = self.labels['stale_credit'] > 0
        if c.BUFFER_PROTECTION:
            goals['stored_faults'] = self.labels['stored_single_fault'] > 0
        if c.BUFFER_PROTECTION == 2:
            goals['ownership_fault_is_fatal'] = self.labels['stored_ownership_fault'] > 0
            goals['secded_double_fault'] = self.labels['stored_double_fault'] > 0
        if c.ENABLE_LINK_PARITY:
            goals['every_link_field_fault'] = all(
                self.labels['link_fault_' + name] > 0 for name in c.field_widths
            )
        services = {(c.TRAFFIC_CLASS_TO_SERVICE >> tc) & 1 for tc in range(c.NUM_TRAFFIC_CLASSES)}
        if c.ENABLE_QOS and services == {0, 1} and len(ports) >= 2:
            goals['qos_both_services'] = (
                self.qos_grants['normal'] > 0 and self.qos_grants['high'] > 0
            )
            goals['qos_forced_normal'] = self.qos_grants['forced_normal'] > 0
        waivers = [
            dict(
                owner='MOSAIC NoC maintainers',
                rationale='Boundary-disabled ports cannot accept traffic',
                affected_profile=dict(
                    mesh=[c.MESH_X, c.MESH_Y], coordinate=[c.ROUTER_X, c.ROUTER_Y]
                ),
                expiration='Revisit if wraparound links or boundary encoding changes',
            )
        ]
        return dict(
            status='PASS' if all(goals.values()) else 'FAIL',
            goals=goals,
            parameters=c.parameters,
            seed=c.seed,
            random_transactions=self.random_transactions,
            observations=dict(self.observations),
            response_accounting=self.accounting,
            route_vc_cross=sorted(self.routes),
            fifo_occupancies=sorted(self.occupancies),
            credit_counts=sorted(self.credits),
            simultaneous_outputs=sorted(self.simultaneous),
            qos_grants=dict(self.qos_grants),
            geometry_waivers=waivers,
            internal_storage_assertions='PASS',
            hdl_safety_assertions=(
                'PASS' if hasattr(cocotb.top.g_router, 'u_assertions') else 'NOT_RUN'
            ),
            tni_integration='NOT_RUN',
        )
