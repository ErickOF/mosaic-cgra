"""Functional bins and exact ownership totals from checked public transfers."""

from collections import Counter
from mosaic_uvm.components import CoverageCollector
from tile_network_interface.model import lane, num


class InterfaceCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.counts = Counter()
        self.tx_channels, self.rx_endpoints, self.classes, self.fragments = (
            set(),
            set(),
            set(),
            set(),
        )
        self.errors = set()
        self.model = None

    def sample(self, observation, q, model):
        p, c = observation.ports, self.config
        self.counts['cycles'] += 1
        self.counts['random_transactions'] += int(observation.item.random)
        for n in q['tx_accept']:
            if n not in q['tx_drop']:
                self.tx_channels.add(n)
                self.classes.add(q['tx_beats'][n]['traffic_class'])
        self.rx_endpoints.update(q['rx_consume'])
        if q['tx_transfer']:
            self.fragments.add(q['tx_output']['fragment_index'])
        self.errors.add(q['error']) if q['error'] else None
        for name, hit in dict(
            tx=q['tx_transfer'],
            rx=q['rx_accept'],
            config=q['config_good'],
            config_rejected=q['config_accept'] and not q['config_good'],
            drop=bool(q['tx_drop'])
            or q['rx_direct_drop']
            or bool(q['process'] and q['process'][3]),
            parity=bool(q['process'] and q['process'][4]),
            flush=q['flush'] and not q['empty'],
            drain=num(p['i_drain']) == 1,
            reset=num(p['i_rstb']) == 0,
            simultaneous=bool(q['tx_transfer'] and q['rx_accept']),
            tx_stall=bool(num(p['i_tile_tx_valid']) and not q['tx_accept']),
            rx_stall=bool(num(p['o_tile_rx_valid']) and num(p['i_tile_rx_ready']) == 0),
            tx_full=any(len(x) == c.TX_QUEUE_DEPTH for x in model.tx),
            rx_full=any(len(x) == c.RX_QUEUE_DEPTH for x in model.rx),
            vc_full=any(len(x) == c.RX_VC_DEPTH for x in model.vc_queues),
            credit_zero=bool(c.NOC_FLOW_CONTROL and 0 in model.credits),
            credit_return=q['credit_return'] is not None,
        ).items():
            self.counts[name] += int(hit)

    def report(self):
        c, m = self.config, self.model
        goals = {
            k: self.counts[k] > 0
            for k in (
                'tx',
                'rx',
                'config',
                'config_rejected',
                'drop',
                'flush',
                'drain',
                'simultaneous',
                'tx_stall',
                'rx_stall',
                'tx_full',
                'rx_full',
            )
        }
        goals |= dict(
            tx_channels=len(self.tx_channels) == c.NUM_TX_CHANNELS,
            rx_endpoints=len(self.rx_endpoints) == c.NUM_RX_CHANNELS,
            traffic_classes=len(self.classes) == c.NUM_TRAFFIC_CLASSES,
            all_fragments=len(self.fragments) == c.fragments,
            random_cycles=self.counts['random_transactions'] == c.random_cycles,
            malformed=10 in self.errors,
            unknown_control=14 in self.errors,
            stale=7 in self.errors,
            disabled=16 in self.errors,
            context=6 in self.errors,
            keep=1 in self.errors,
            destination=5 in self.errors,
            canceled_tx=m.discarded_tx > 0,
            recovered=m.error == 0,
        )
        if c.ENABLE_LINK_PARITY:
            goals['parity'] = self.counts['parity'] > 0 and 13 in self.errors
        if c.NOC_FLOW_CONTROL:
            goals.update(
                credit_zero=self.counts['credit_zero'] > 0,
                credit_return=self.counts['credit_return'] > 0,
                excess_credit=8 in self.errors,
                receive_overflow=9 in self.errors,
            )
        return dict(
            status='PASS' if all(goals.values()) else 'FAIL',
            goals=goals,
            parameters=c.parameters,
            seed=c.seed,
            random_transactions=self.counts['random_transactions'],
            counters=dict(self.counts),
            errors=sorted(self.errors),
            tx_channels=sorted(self.tx_channels),
            rx_endpoints=sorted(self.rx_endpoints),
            classes=sorted(self.classes),
            fragments=sorted(self.fragments),
            accounting=dict(
                tx=dict(
                    accepted=m.accepted_tx,
                    completed=m.sent_tx,
                    canceled=m.discarded_tx,
                    pending=sum(map(len, m.tx)),
                ),
                rx=dict(
                    accepted=m.accepted_rx,
                    completed=m.delivered_rx,
                    canceled=m.discarded_rx,
                    pending=sum(map(len, m.rx)) + sum(map(len, m.completed)),
                ),
                tx_flits=dict(
                    accepted=m.accepted_tx * c.fragments,
                    completed=m.tx_flits,
                    canceled=m.canceled_tx_flits,
                    pending=0,
                ),
                rx_flits=dict(
                    accepted=m.rx_flits,
                    completed=m.popped_rx_flits,
                    canceled=m.canceled_rx_flits,
                    pending=0,
                ),
            ),
            framework='PyUVM',
            validation_mode='Python-only',
            hdl_assertions='NOT_RUN',
            synthesis='Design Compiler (deferred)',
        )
