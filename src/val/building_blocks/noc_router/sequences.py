"""Packet generators and independent upstream/downstream flow-control peers."""

from collections import deque
from itertools import product
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from noc_router.model import integer, part
from noc_router.transaction import RouterItem, INPUTS


class RouterSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('noc_router_sequence')
        self.c = config
        self.rng = random.Random(config.seed)
        self.nonce = self.tick = 0
        self.epoch = [0] * 5
        self.upstream = [config.INPUT_VC_DEPTH] * (5 * config.NUM_VCS)
        self.returns = [deque() for _ in range(5)]
        self.configured = False

    def packet(self, port, destination, *, vc=0, length=1, traffic_class=None, **changes):
        c = self.c
        self.nonce += 1
        length = min(length, 1 << c.FRAGMENT_INDEX_WIDTH)
        if traffic_class is None:
            traffic_class = next(
                index
                for index in range(c.NUM_TRAFFIC_CLASSES)
                if (c.TRAFFIC_CLASS_TO_VC >> (index * c.aliases['VW']))
                & ((1 << c.aliases['VW']) - 1)
                == vc
            )
        invariant = dict(
            source_node=port % (c.MESH_X * c.MESH_Y),
            source_endpoint=port,
            destination_node=destination,
            destination_endpoint=2,
            context_id=self.nonce,
            message_type=1,
            traffic_class=traffic_class,
            packet_id=self.nonce,
            stream_last=1,
            user_metadata=self.nonce * 5 + port,
            vc=vc,
            epoch=self.epoch[port],
        )
        invariant.update(changes)
        records = [
            invariant
            | dict(
                data=self.nonce * 31 + index,
                keep=(1 << (c.FLIT_DATA_WIDTH // 8)) - 1,
                head=int(index == 0),
                tail=int(index == length - 1),
                fragment_index=index,
                error=0,
            )
            for index in range(length)
        ]
        return [
            {name: value & ((1 << c.field_widths[name]) - 1) for name, value in record.items()}
            for record in records
        ]

    async def cycle(
        self,
        label,
        *,
        incoming=None,
        ready=31,
        edge=True,
        random=False,
        fault=None,
        auto_credit=True,
        **overrides,
    ):
        c = self.c
        incoming = incoming or {}
        values = dict.fromkeys(INPUTS, 0)
        values.update(i_rstb=1, i_out_ready=ready)
        for port, f in incoming.items():
            values['i_in_valid'] |= 1 << port
            parity = 0
            for name, width in c.field_widths.items():
                value = f[name] & ((1 << width) - 1)
                values['i_in_' + name] |= value << (port * width)
                parity ^= value.bit_count() & 1
            if c.ENABLE_LINK_PARITY:
                values['i_in_parity'] |= parity << port
        if c.FLOW_CONTROL and auto_credit:
            for port in range(5):
                if self.returns[port] and self.returns[port][0][0] <= self.tick:
                    _, vc, epoch = self.returns[port].popleft()
                    values['i_out_credit_valid'] |= 1 << port
                    values['i_out_credit_vc'] |= vc << (port * c.aliases['VW'])
                    values['i_out_credit_epoch'] |= epoch << (port * c.LINK_EPOCH_WIDTH)
        values.update(overrides)
        item = RouterItem(
            label,
            {name: bits(value, c.widths[name]) for name, value in values.items()},
            edge=edge,
            fault=fault,
            random=random,
        )
        await self.start_item(item)
        await self.finish_item(item)
        if edge:
            self.tick += 1
            post = item.observation.ports
            pre = item.pre.ports
            if values['i_rstb'] == 0 or values.get('i_flush') == 1:
                self.returns = [deque() for _ in range(5)]
                self.upstream = [c.INPUT_VC_DEPTH] * (5 * c.NUM_VCS)
                if values['i_rstb'] == 0:
                    self.configured = False
            else:
                if c.FLOW_CONTROL:
                    for port, f in incoming.items():
                        # Credit sends are launches; a containment sink intentionally
                        # consumes the spent credit until coordinated recovery.
                        index = port * c.NUM_VCS + f['vc']
                        if f['vc'] < c.NUM_VCS:
                            self.upstream[index] -= 1
                    for port in range(5):
                        if part(post['o_in_credit_valid'], port, 1):
                            vc = part(post['o_in_credit_vc'], port, c.aliases['VW'])
                            self.upstream[port * c.NUM_VCS + vc] += 1
                        if part(pre['o_out_valid'], port, 1):
                            vc = part(pre['o_out_vc'], port, c.aliases['VW'])
                            epoch = part(pre['o_out_epoch'], port, c.LINK_EPOCH_WIDTH)
                            self.returns[port].append((self.tick + 2, vc, epoch))
            self.epoch = [part(post['o_link_epoch'], port, c.LINK_EPOCH_WIDTH) for port in range(5)]
        return item

    async def reset(self):
        await self.cycle('reset', i_rstb=0)
        await self.cycle('reset', i_rstb=0)

    async def configure(self, enable=None, fault=0):
        if enable is None:
            enable = sum(1 << p for p in self.c.usable_ports())
        item = await self.cycle(
            'configuration',
            i_config_valid=1,
            i_config_port_enable=enable,
            i_config_fault_port_mask=fault,
        )
        self.configured = item.observation.ports['o_config_accepted'] == '1'
        return item

    async def send(
        self,
        packets,
        label='packet',
        *,
        stalls=False,
        ready_mask=31,
        draining=False,
        auto_credit=True,
    ):
        pending = {port: deque(flits) for port, flits in packets.items()}
        for _ in range(1000):
            incoming = {
                port: queue[0]
                for port, queue in pending.items()
                if queue
                and (
                    not self.c.FLOW_CONTROL
                    or self.upstream[port * self.c.NUM_VCS + queue[0]['vc']] > 0
                )
            }
            if not any(pending.values()):
                return
            ready = self.rng.getrandbits(5) if stalls else ready_mask
            item = await self.cycle(
                label,
                incoming=incoming,
                ready=ready,
                i_drain=int(draining),
                auto_credit=auto_credit,
            )
            accepted = integer(item.observation.ports['o_event_input_accept'])
            for port in incoming:
                if accepted & (1 << port):
                    pending[port].popleft()
        raise AssertionError(
            f'Packet producer failed: {label}, upstream={self.upstream}, '
            f'pending={pending}, ports={item.observation.ports}, '
            f'internal={item.observation.internal}'
        )

    async def drain(self):
        for _ in range(1000):
            item = await self.cycle('drain')
            if item.observation.ports['o_idle'] == '1':
                for _ in range(5):
                    await self.cycle('settled')
                return
        raise AssertionError('Accepted traffic failed to drain')

    def destinations(self):
        c = self.c
        targets = {}
        from noc_router.model import route

        for node in range(c.MESH_X * c.MESH_Y):
            targets.setdefault(route(c, node), node)
        return targets

    async def directed(self):
        c = self.c
        # Every usable input, next hop, VC and class, including one-flit packets.
        for port in c.usable_ports():
            for destination in self.destinations().values():
                for tc in range(c.NUM_TRAFFIC_CLASSES):
                    vc = (c.TRAFFIC_CLASS_TO_VC >> (tc * c.aliases['VW'])) & (
                        (1 << c.aliases['VW']) - 1
                    )
                    await self.send(
                        {
                            port: self.packet(
                                port,
                                destination,
                                vc=vc,
                                traffic_class=tc,
                                length=1 + tc % min(3, (1 << c.FRAGMENT_INDEX_WIDTH)),
                            )
                        }
                    )
                    await self.drain()
        # All nonconflicting outputs operate concurrently; all-to-one traffic
        # exercises packet reservations and normal/high competition on the same link.
        targets = self.destinations()
        await self.send(
            {port: self.packet(port, targets[port], length=3) for port in c.usable_ports()},
            'parallel',
        )
        await self.drain()
        destination = c.ROUTER_Y * c.MESH_X + c.ROUTER_X
        for repeat in range(6):
            await self.send(
                {
                    port: self.packet(
                        port, destination, vc=repeat % c.NUM_VCS, length=1 + repeat % 3
                    )
                    for port in c.usable_ports()
                },
                'contention',
                stalls=True,
            )
        await self.drain()

    async def fill_and_stall(self):
        c = self.c
        local = c.ROUTER_Y * c.MESH_X + c.ROUTER_X
        targets = self.destinations()
        for port, vc in product(c.usable_ports(), range(c.NUM_VCS)):
            destination = targets.get(port, local)
            if c.FLOW_CONTROL:
                # Spend every downstream credit, withholding legitimate returns.
                for _ in range(c.OUTPUT_INITIAL_CREDITS):
                    await self.send(
                        {port: self.packet(port, destination, vc=vc)},
                        'credit_exhaust',
                        auto_credit=False,
                    )
                    for _ in range(100):
                        item = await self.cycle('credit_exhaust_wait', auto_credit=False)
                        if item.observation.ports['o_idle'] == '1':
                            break
            packets = []
            for _ in range(c.INPUT_VC_DEPTH + c.OUTPUT_PIPELINE):
                packets.extend(self.packet(port, destination, vc=vc))
            await self.send({port: packets}, 'fill_fifo', ready_mask=0, auto_credit=False)
            for _ in range(32):
                await self.cycle('full_stall', ready=0, auto_credit=False)
            await self.drain()
        if c.FLOW_CONTROL:
            # Again exhaust local VC0, then return one credit at a time. This
            # deliberately stalls each phase of one multi-flit packet.
            for _ in range(c.OUTPUT_INITIAL_CREDITS):
                await self.send({0: self.packet(0, local)}, 'phase_prime', auto_credit=False)
                for _ in range(100):
                    item = await self.cycle('phase_prime_wait', auto_credit=False)
                    if item.observation.ports['o_idle'] == '1':
                        break
        pending = deque(self.packet(0, local, length=3))
        for index in range(300):
            incoming = (
                {0: pending[0]} if pending and (not c.FLOW_CONTROL or self.upstream[0] > 0) else {}
            )
            overrides = {}
            if (
                c.FLOW_CONTROL
                and index % 7 == 1
                and self.returns[0]
                and self.returns[0][0][0] <= self.tick
            ):
                _, vc, epoch = self.returns[0].popleft()
                overrides = dict(i_out_credit_valid=1, i_out_credit_vc=vc, i_out_credit_epoch=epoch)
            item = await self.cycle(
                'phase_stall',
                incoming=incoming,
                ready=31 if index % 7 == 3 else 0,
                auto_credit=False,
                **overrides,
            )
            if incoming and integer(item.observation.ports['o_event_input_accept']) & 1:
                pending.popleft()
            if not pending and item.observation.ports['o_idle'] == '1':
                break
        else:
            raise AssertionError('Packet phases failed to make bounded progress')
        await self.drain()

    async def qos(self):
        c = self.c
        if not c.ENABLE_QOS or len(c.usable_ports()) < 2:
            return
        normal = [
            tc for tc in range(c.NUM_TRAFFIC_CLASSES) if not (c.TRAFFIC_CLASS_TO_SERVICE >> tc) & 1
        ]
        high = [tc for tc in range(c.NUM_TRAFFIC_CLASSES) if (c.TRAFFIC_CLASS_TO_SERVICE >> tc) & 1]
        if not normal or not high:
            return
        local = c.ROUTER_Y * c.MESH_X + c.ROUTER_X
        packets = {}
        for port in c.usable_ports():
            tc = normal[0] if port == 0 else high[0]
            vc = (c.TRAFFIC_CLASS_TO_VC >> (tc * c.aliases['VW'])) & ((1 << c.aliases['VW']) - 1)
            packets[port] = []
            for _ in range(2 * c.HIGH_SERVICE_BURST_LIMIT + 4):
                packets[port].extend(self.packet(port, local, vc=vc, traffic_class=tc))
        await self.send(packets, 'qos_competition')
        await self.drain()

    async def errors_and_control(self):
        c = self.c
        local = c.ROUTER_Y * c.MESH_X + c.ROUTER_X
        await self.configure(enable=0)
        await self.cycle('clear_configuration_error', i_error_clear=1)
        packet = self.packet(0, c.MESH_X * c.MESH_Y, length=2)
        await self.send({0: packet}, 'illegal_route')
        await self.drain()
        await self.cycle('clear_route_error', i_error_clear=1)
        packet = self.packet(0, local, length=3)
        packet[1]['destination_node'] = (local + 1) % (c.MESH_X * c.MESH_Y)
        packet[1]['head'] = 1
        packet[1]['packet_id'] ^= 1
        await self.send({0: packet}, 'body_integrity')
        await self.drain()
        await self.cycle('clear_protocol_error', i_error_clear=1)
        # Coordinated flush discards an open ingress packet and held output.
        packet = self.packet(0, local, length=3)
        await self.cycle('before_flush', incoming={0: packet[0]}, ready=0)
        await self.cycle('held_before_flush', ready=0)
        await self.cycle('flush_owned', i_flush=1)
        stale = self.packet(0, local)[0]
        stale['epoch'] = (self.epoch[0] - 1) % (1 << c.LINK_EPOCH_WIDTH)
        await self.cycle('stale_epoch', incoming={0: stale})
        # A pre-FIFO stale sink returns no credit; coordinated recovery restores it.
        await self.cycle('recover_stale_credit', i_flush=1)
        # Stop new heads, but finish a packet whose head has already entered.
        packet = self.packet(0, local, length=3)
        await self.send({0: packet[:1]}, 'head_before_drain')
        other = c.usable_ports()[-1]
        if other != 0:
            await self.cycle(
                'drain_blocks_head', incoming={other: self.packet(other, local)[0]}, i_drain=1
            )
        await self.send({0: packet[1:]}, 'body_during_drain', draining=True)
        for _ in range(1000):
            item = await self.cycle('draining', i_drain=1)
            if item.observation.ports['o_drain_done'] == '1':
                break
        else:
            raise AssertionError('Drain failed to finish an open ingress packet')
        # Credit ownership after deliberately rejected drain traffic is reset by flush.
        await self.cycle('flush_drained', i_flush=1)
        for field in ('i_in_vc', 'i_in_head', 'i_in_epoch', 'i_in_destination_node'):
            offered = self.packet(0, local)[0]
            await self.cycle(
                'unknown_ownership', incoming={0: offered}, **{field: 'x' * c.widths[field]}
            )
            await self.reset()
            await self.configure()
        if not c.FLOW_CONTROL:
            await self.cycle(
                'ignored_credit_inputs',
                i_out_credit_valid='x' * 5,
                i_out_credit_vc='x' * c.widths['i_out_credit_vc'],
                i_out_credit_epoch='x' * c.widths['i_out_credit_epoch'],
            )
        else:
            await self.cycle(
                'illegal_credit',
                i_out_credit_valid=1,
                i_out_credit_vc=0,
                i_out_credit_epoch=self.epoch[0],
            )
            await self.cycle('clear_credit_error', i_error_clear=1)

    async def containment(self):
        """Exercise rejected configuration, quarantines and coordinated recovery."""
        c = self.c
        local = c.ROUTER_Y * c.MESH_X + c.ROUTER_X
        enable = sum(1 << port for port in c.usable_ports())
        await self.cycle('unknown_configuration', i_config_valid=1, i_config_port_enable='xxxxx')
        await self.cycle('clear_unknown_configuration', i_error_clear=1)
        for output, destination in self.destinations().items():
            if output == 0:
                continue
            await self.configure(enable=enable, fault=1 << output)
            await self.send({0: self.packet(0, destination, length=2)}, 'fault_masked_route')
            await self.drain()
            await self.cycle('clear_masked_route', i_error_clear=1)
            await self.configure(enable=enable & ~(1 << output))
            item = await self.cycle(
                'disabled_input', incoming={output: self.packet(output, local)[0]}
            )
            assert integer(item.observation.ports['o_event_input_accept']) == 0
            await self.cycle('recover_disabled_input', i_flush=1)
            await self.configure()
        if c.NUM_VCS < (1 << c.aliases['VW']):
            f = self.packet(0, local)[0] | dict(vc=c.NUM_VCS)
            await self.cycle('out_of_range_vc', incoming={0: f})
            await self.cycle('recover_vc_sink', i_flush=1)
        if c.NUM_TRAFFIC_CLASSES < (1 << c.TRAFFIC_CLASS_WIDTH):
            f = self.packet(0, local)[0] | dict(traffic_class=c.NUM_TRAFFIC_CLASSES)
            await self.send({0: [f]}, 'out_of_range_class')
            await self.drain()
            await self.cycle('clear_class_error', i_error_clear=1)
        f = self.packet(0, local)[0] | dict(head=0, fragment_index=1)
        await self.send({0: [f]}, 'orphan_tail')
        await self.drain()
        await self.cycle('clear_orphan_error', i_error_clear=1)
        # Reset after an accepted head, body, or tail while the output is stalled.
        for phase in range(3):
            packet = self.packet(0, local, length=3)
            await self.send({0: packet[: phase + 1]}, 'active_reset')
            await self.cycle('held_active_reset', ready=0, auto_credit=False)
            await self.reset()
            await self.configure()
        if c.FLOW_CONTROL:
            await self.cycle(
                'stale_credit',
                i_out_credit_valid=1,
                i_out_credit_epoch=(self.epoch[0] - 1) % (1 << c.LINK_EPOCH_WIDTH),
            )
            await self.cycle('clear_stale_credit', i_error_clear=1)

    async def buffer_faults(self):
        c = self.c
        if not c.BUFFER_PROTECTION:
            return
        local = c.ROUTER_Y * c.MESH_X + c.ROUTER_X
        import cocotb

        for mask in (1, 4, 1 << 10) if c.BUFFER_PROTECTION == 2 else (1,):
            await self.reset()
            await self.configure()
            await self.cycle('fault_target', incoming={0: self.packet(0, local)[0]}, ready=0)
            bank = cocotb.top.g_router.g_input_vc[0].u_buffer
            lane = int(bank.read_pointer.value)
            item = await self.cycle('stored_single_fault', ready=0, fault=(0, 0, lane, mask))
            if c.BUFFER_PROTECTION == 1:
                assert item.observation.ports['o_fatal_error'] == '1'
                await self.cycle('flush_fatal', i_flush=1)
                item = await self.cycle('fatal_survives_clear', i_error_clear=1)
                assert item.observation.ports['o_fatal_error'] == '1'
            else:
                assert item.observation.ports['o_fatal_error'] == '0'
                await self.drain()
        if c.BUFFER_PROTECTION == 2:
            await self.reset()
            await self.configure()
            await self.cycle('double_target', incoming={0: self.packet(0, local)[0]}, ready=0)
            lane = int(cocotb.top.g_router.g_input_vc[0].u_buffer.read_pointer.value)
            await self.cycle('stored_double_fault', ready=0, fault=(0, 0, lane, 3))
            await self.drain()
            await self.reset()
            await self.configure()
            await self.cycle('ownership_target', incoming={0: self.packet(0, local)[0]}, ready=0)
            bank = cocotb.top.g_router.g_input_vc[0].u_buffer
            lane = int(bank.read_pointer.value)
            word = bank.g_lane[lane].u_fifo.g_fifo.memory[0]
            item = await self.cycle(
                'stored_ownership_fault', ready=0, fault=(0, 0, lane, 1 << (len(word) - 1))
            )
            assert item.observation.ports['o_fatal_error'] == '1'
            await self.cycle('flush_ownership_fatal', i_flush=1)
            item = await self.cycle('ownership_fatal_survives', i_error_clear=1)
            assert item.observation.ports['o_fatal_error'] == '1'
        await self.reset()
        await self.configure()

    async def link_faults(self):
        c = self.c
        if not c.ENABLE_LINK_PARITY:
            return
        local = c.ROUTER_Y * c.MESH_X + c.ROUTER_X
        for name in c.field_widths:
            await self.reset()
            await self.configure()
            f = self.packet(0, local)[0]
            parity = sum(value.bit_count() for value in f.values()) % 2
            f[name] ^= 1
            item = await self.cycle('link_fault_' + name, incoming={0: f}, i_in_parity=parity)
            assert item.observation.ports['o_fatal_error'] == '1'
            assert item.observation.ports['o_error_code'] == format(12, '05b')
        await self.reset()
        await self.configure()

    async def randomized(self):
        c = self.c
        pending = {port: deque() for port in c.usable_ports()}
        for index in range(c.random_cycles):
            for port in pending:
                if not pending[port] and self.rng.random() < 0.4:
                    vc = self.rng.randrange(c.NUM_VCS)
                    pending[port].extend(
                        self.packet(
                            port,
                            self.rng.randrange(c.MESH_X * c.MESH_Y),
                            vc=vc,
                            length=self.rng.randrange(1, min(4, 1 << c.FRAGMENT_INDEX_WIDTH)),
                        )
                    )
            incoming = {
                port: q[0]
                for port, q in pending.items()
                if q and (not c.FLOW_CONTROL or self.upstream[port * c.NUM_VCS + q[0]['vc']] > 0)
            }
            item = await self.cycle(
                'random', incoming=incoming, ready=self.rng.getrandbits(5), random=True
            )
            accepted = integer(item.observation.ports['o_event_input_accept'])
            for port in incoming:
                if accepted & (1 << port):
                    pending[port].popleft()
        await self.send(pending, 'random_finish')
        await self.drain()

    async def body(self):
        await self.reset()
        await self.configure()
        await self.directed()
        await self.fill_and_stall()
        await self.qos()
        await self.errors_and_control()
        await self.containment()
        await self.buffer_faults()
        await self.link_faults()
        await self.randomized()
        await self.drain()
