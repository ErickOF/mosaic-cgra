"""PyUVM mesh endpoints and independent end-to-end delivery/ordering ledger."""

from collections import defaultdict, deque
import cocotb
from cocotb.triggers import ReadOnly
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor, uvm_analysis_export, uvm_scoreboard
from mosaic_uvm.components import ActiveAgent, VerificationEnv, CoverageCollector
from mosaic_uvm.logic import bits, logic
from noc_router.config import RouterConfig
from noc_router.driver import RouterDriver
from noc_router.model import integer, part, flit
from noc_router.sequences import RouterSequence
from noc_router.transaction import RouterItem, INPUTS, OUTPUTS, Observation, EVENTS


class MeshConfig(RouterConfig):
    @property
    def nodes(self):
        return self.MESH_X * self.MESH_Y

    @property
    def widths(self):
        r = super().widths
        n = self.nodes
        for name in (
            'i_in_valid',
            'o_in_ready',
            'o_out_valid',
            'i_out_ready',
            'i_in_parity',
            'o_out_parity',
            'i_out_credit_valid',
            'o_in_credit_valid',
        ):
            r[name] = n
        for name, width in self.field_widths.items():
            r['i_in_' + name] = r['o_out_' + name] = n * width
        for prefix in ('i_out', 'o_in'):
            r[prefix + '_credit_vc'] = n * self.aliases['VW']
            r[prefix + '_credit_epoch'] = n * 2
        for name in (
            'o_active_port_enable',
            'o_active_fault_port_mask',
            'o_link_epoch',
            'o_input_vc_occupancy',
            'o_output_credit_count',
            'o_input_packet_locked',
            'o_output_packet_locked',
            'i_config_port_enable',
            'i_config_fault_port_mask',
        ):
            r[name] *= n
        for name in EVENTS:
            r['o_event_' + name] = n
        return r


class MeshMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    async def run_phase(self):
        while True:
            await self.active['sample'].wait()
            await ReadOnly()
            item = self.active['item']
            obs = Observation(
                {name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)},
                {},
                item,
                self.active['stage'],
            )
            self.ap.write(obs)
            item.observation = obs
            if obs.stage == 'pre':
                item.pre = obs
            self.active['sample'].clear()


class MeshCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.routes = set()
        self.random_cycles = 0
        self.accounting = {}
        self.flushes = 0

    def report(self):
        c = self.config
        expected = {
            (source, destination) for source in range(c.nodes) for destination in range(c.nodes)
        }
        goals = dict(
            all_source_destination_pairs=expected <= self.routes,
            random_congestion=self.random_cycles == c.random_cycles,
            coordinated_flush=self.flushes > 0,
            exact_delivery_conservation=bool(self.accounting) and self.accounting['pending'] == 0,
        )
        return dict(
            status='PASS' if all(goals.values()) else 'FAIL',
            goals=goals,
            parameters=c.parameters,
            seed=c.seed,
            route_pairs=sorted(self.routes),
            random_transactions=self.random_cycles,
            response_accounting=self.accounting,
            tni_integration='NOT_RUN',
            endpoints='behavioral flit producers/consumers',
        )


class MeshScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.pending = defaultdict(deque)
        self.accepted = self.delivered = self.canceled = 0
        self.epoch = 0
        self.output_packet = {}

    def reset(self, flush=False):
        self.canceled += sum(map(len, self.pending.values()))
        self.pending.clear()
        self.output_packet.clear()
        self.epoch = (self.epoch + 1) % 4 if flush else 0

    def output(self, p, consume=False):
        c = self.c
        for node in range(c.nodes):
            if not part(p['o_out_valid'], node, 1):
                assert all(
                    part(p['o_out_' + name], node, width) == 0
                    for name, width in c.field_widths.items()
                )
                continue
            f = flit(c, p, 'o_out', node)
            assert f['destination_node'] == node, 'Packet ejected at the wrong mesh node'
            key = (f['source_node'], f['vc'], node)
            assert self.pending[key], 'Unknown or duplicated end-to-end flit'
            expected = self.pending[key][0]
            assert expected | dict(epoch=self.epoch) == f, 'Network flit corruption or reordering'
            if consume and (c.FLOW_CONTROL or part(p['i_out_ready'], node, 1)):
                uid = (f['source_node'], f['packet_id'], f['user_metadata'])
                assert self.output_packet.get(node, uid) == uid, 'Output packets interleaved'
                if f['tail']:
                    self.output_packet.pop(node, None)
                else:
                    self.output_packet[node] = uid
                self.pending[key].popleft()
                self.delivered += 1
                self.coverage.routes.add((f['source_node'], node))

    def write(self, obs):
        c, p, item = self.c, obs.ports, obs.item
        if obs.stage == 'pre':
            if c.ASYNC_RESET and p['i_rstb'] == '0':
                self.reset()
            if p['i_rstb'] == '1' and p['i_flush'] == '0':
                self.output(p)
        if obs.stage != 'post' or not item.edge:
            return
        pre = item.pre.ports
        if pre['i_rstb'] == '0':
            self.reset()
        elif pre['i_flush'] == '1':
            self.reset(flush=True)
            self.coverage.flushes += 1
        else:
            self.output(pre, consume=True)
            accepted = integer(p['o_event_input_accept'])
            for source in range(c.nodes):
                if accepted & (1 << source):
                    f = flit(c, pre, 'i_in', source)
                    assert f['source_node'] == source
                    self.pending[(source, f['vc'], f['destination_node'])].append(f)
                    self.accepted += 1
            assert p['o_error'] == p['o_fatal_error'] == '0', 'Unexpected mesh router error'
        pending = sum(map(len, self.pending.values()))
        assert self.accepted == self.delivered + self.canceled + pending
        self.coverage.random_cycles += item.random
        self.coverage.accounting = dict(
            accepted=self.accepted,
            delivered=self.delivered,
            flushed_or_reset=self.canceled,
            pending=pending,
        )

    def check_phase(self):
        assert not any(self.pending.values()), 'Mesh retained an accepted flit'
        assert not self.output_packet, 'Mesh retained an open output packet'


class MeshAgent(ActiveAgent):
    driver_type = RouterDriver
    monitor_type = MeshMonitor


class MeshEnv(VerificationEnv):
    agent_type = MeshAgent
    scoreboard_type = MeshScoreboard
    coverage_type = MeshCoverage


class MeshSequence(RouterSequence):
    def __init__(self, config):
        super().__init__(config)
        self.epoch = [0] * config.nodes
        self.upstream = [2] * (config.nodes * config.NUM_VCS)
        self.returns = [deque() for _ in range(config.nodes)]

    async def cycle(self, label, *, incoming=None, ready=None, random=False, **overrides):
        c = self.c
        incoming = incoming or {}
        values = dict.fromkeys(INPUTS, 0)
        values.update(i_rstb=1, i_out_ready=(1 << c.nodes) - 1 if ready is None else ready)
        for source, f in incoming.items():
            values['i_in_valid'] |= 1 << source
            for name, width in c.field_widths.items():
                values['i_in_' + name] |= (f[name] & ((1 << width) - 1)) << (source * width)
        if c.FLOW_CONTROL:
            for node in range(c.nodes):
                if self.returns[node] and self.returns[node][0][0] <= self.tick:
                    _, vc, epoch = self.returns[node].popleft()
                    values['i_out_credit_valid'] |= 1 << node
                    values['i_out_credit_vc'] |= vc << (node * c.aliases['VW'])
                    values['i_out_credit_epoch'] |= epoch << (node * 2)
        values.update(overrides)
        item = RouterItem(
            label,
            {name: bits(value, c.widths[name]) for name, value in values.items()},
            random=random,
        )
        await self.start_item(item)
        await self.finish_item(item)
        self.tick += 1
        p, pre = item.observation.ports, item.pre.ports
        if values['i_rstb'] == 0 or values.get('i_flush') == 1:
            self.upstream = [2] * (c.nodes * c.NUM_VCS)
            self.returns = [deque() for _ in range(c.nodes)]
        elif c.FLOW_CONTROL:
            for source, f in incoming.items():
                self.upstream[source * c.NUM_VCS + f['vc']] -= 1
            for node in range(c.nodes):
                if part(p['o_in_credit_valid'], node, 1):
                    vc = part(p['o_in_credit_vc'], node, c.aliases['VW'])
                    self.upstream[node * c.NUM_VCS + vc] += 1
                if part(pre['o_out_valid'], node, 1):
                    vc = part(pre['o_out_vc'], node, c.aliases['VW'])
                    epoch = part(pre['o_out_epoch'], node, 2)
                    self.returns[node].append((self.tick + 2, vc, epoch))
        self.epoch = [part(p['o_link_epoch'], node * 5, 2) for node in range(c.nodes)]
        return item

    async def traffic(self, pending, *, cycles=None):
        c = self.c
        for index in range(cycles if cycles is not None else 20000):
            if cycles is None and not any(pending.values()):
                return
            if cycles is not None:
                for source, q in pending.items():
                    if not q and self.rng.random() < 0.2:
                        vc = self.rng.randrange(c.NUM_VCS)
                        q.extend(self.packet(source, self.rng.randrange(c.nodes), vc=vc, length=3))
            incoming = {
                node: q[0]
                for node, q in pending.items()
                if q and (not c.FLOW_CONTROL or self.upstream[node * c.NUM_VCS + q[0]['vc']] > 0)
            }
            item = await self.cycle(
                'mesh_random' if cycles else 'mesh_directed',
                incoming=incoming,
                ready=self.rng.getrandbits(c.nodes) if cycles else None,
                random=cycles is not None,
            )
            accepted = integer(item.observation.ports['o_event_input_accept'])
            for node in incoming:
                if accepted & (1 << node):
                    pending[node].popleft()
        if cycles is None:
            raise AssertionError('Mesh injection failed to make bounded progress')

    async def drain(self):
        for _ in range(20000):
            item = await self.cycle('mesh_drain')
            if item.observation.ports['o_idle'] == '1':
                for _ in range(5):
                    await self.cycle('mesh_settled')
                return
        raise AssertionError('Mesh failed to drain')

    async def body(self):
        c = self.c
        await self.cycle('reset', i_rstb=0)
        await self.cycle('reset', i_rstb=0)
        enables = sum(
            sum(1 << p for p in c.usable_ports(node % c.MESH_X, node // c.MESH_X)) << (node * 5)
            for node in range(c.nodes)
        )
        await self.cycle('mesh_configuration', i_config_valid=1, i_config_port_enable=enables)
        for offset in range(c.nodes):
            pending = {
                source: deque(
                    self.packet(
                        source, (source + offset) % c.nodes, vc=offset % c.NUM_VCS, length=3
                    )
                )
                for source in range(c.nodes)
            }
            await self.traffic(pending)
            await self.drain()
        pending = {source: deque() for source in range(c.nodes)}
        await self.traffic(pending, cycles=c.random_cycles)
        await self.traffic(pending)
        await self.drain()
        # Every router and the valid-ready link bridges participate in one flush.
        await self.cycle(
            'mesh_before_flush',
            incoming={
                source: self.packet(source, (source + 1) % c.nodes, length=3)[0]
                for source in range(c.nodes)
            },
            ready=0,
        )
        await self.cycle('mesh_flush', i_flush=1)
        await self.drain()
        item = await self.cycle('mesh_network_drained', i_drain=1)
        assert item.observation.ports['o_drain_done'] == '1'
