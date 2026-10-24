"""Directed adversarial packets followed by reproducible concurrent traffic."""

from copy import deepcopy
import random
from pyuvm import uvm_sequence
from mosaic_uvm.logic import bits
from tile_network_interface.model import expand, num, parity
from tile_network_interface.transaction import FLIT_FIELDS, InterfaceItem


class InterfaceSequence(uvm_sequence):
    def __init__(self, c):
        super().__init__('tile_network_interface_sequence')
        self.c = c
        self.rng = random.Random(c.seed)
        self.serial = self.cycle = 0
        self.last = None
        self.context = 0

    def beat(self, channel=0, **overrides):
        c, r = self.c, self.rng
        self.serial += 1
        result = dict(
            data=r.getrandbits(c.TILE_DATA_WIDTH),
            keep=r.randint(1, (1 << c.aliases['TB']) - 1),
            last=self.serial % 2,
            context_id=self.context,
            message_type=r.getrandbits(c.MESSAGE_TYPE_WIDTH),
            traffic_class=self.serial % c.NUM_TRAFFIC_CLASSES,
            packet_id=self.serial % (1 << c.PACKET_ID_WIDTH),
            user_metadata=r.getrandbits(c.USER_METADATA_WIDTH),
            error=r.getrandbits(c.ERROR_WIDTH),
            destination_node=c.LOCAL_NODE_ID,
            destination_endpoint=channel % c.NUM_RX_CHANNELS,
        )
        return result | overrides

    def packet(self, endpoint=0, **overrides):
        epoch = num(self.last.post.ports['o_link_epoch']) if self.last else 0
        return expand(
            self.c,
            self.beat(endpoint, **overrides),
            self.rng.randrange(self.c.NUM_TX_CHANNELS),
            epoch,
        )

    async def tick(
        self,
        label='idle',
        offers=None,
        *,
        packets=(),
        peer=None,
        edge=True,
        random=False,
        **controls,
    ):
        item = InterfaceItem(
            f'{self.cycle}:{label}',
            offers or [None] * self.c.NUM_TX_CHANNELS,
            controls,
            packets=packets,
            peer=peer,
            edge=edge,
            random=random,
        )
        await self.start_item(item)
        await self.finish_item(item)
        self.last = item
        self.cycle += 1
        return item

    async def wait(self, count, label='wait', **kwargs):
        for _ in range(count):
            await self.tick(label, **kwargs)

    async def drain(self, *, peer=None):
        limit = 400 + 40 * self.c.fragments * (self.c.NUM_TX_CHANNELS + self.c.NUM_VCS)
        for _ in range(limit):
            item = await self.tick('drain', peer=peer)
            if num(item.post.ports['o_idle']) == 1 and item.peer_pending == 0:
                await self.wait(3, 'drain-settled', peer=peer)
                return
        raise AssertionError('No progress while draining the peer and interface')

    async def configure(self, **values):
        c = self.c
        item = await self.tick(
            'configure',
            i_config_valid=1,
            **(
                dict(
                    i_config_tx_enable=(1 << c.NUM_TX_CHANNELS) - 1,
                    i_config_rx_enable=(1 << c.NUM_RX_CHANNELS) - 1,
                    i_config_context_check=1,
                    i_config_context_id=0,
                )
                | values
            ),
        )
        assert num(item.post.ports['o_config_accepted']) == 1
        self.context = values.get('i_config_context_id', 0)

    async def send(self, offers, *, peer=None):
        pending = deepcopy(offers)
        for _ in range(200 + 30 * self.c.fragments * self.c.NUM_TX_CHANNELS):
            item = await self.tick('tile-offers', pending, peer=peer)
            ready = num(item.pre.ports['o_tile_tx_ready'])
            pending = [None if ready >> n & 1 else beat for n, beat in enumerate(pending)]
            if not any(pending):
                return
        raise AssertionError('Tile source could not enqueue')

    async def bad_packet(self, label, packet):
        await self.tick(label, packets=[packet])
        await self.drain()
        await self.tick('clear-error', i_error_clear=1)

    async def body(self):
        c = self.c
        await self.tick('reset', i_rstb=0)
        await self.tick('reset-held', i_rstb=0, edge=False)
        await self.tick('unconfigured', [self.beat(n) for n in range(c.NUM_TX_CHANNELS)])
        await self.configure()
        await self.tick(
            'reject-config', i_config_valid=1, i_config_context_id='x' * c.CONTEXT_ID_WIDTH
        )
        assert num(self.last.post.ports['o_config_rejected']) == 1
        await self.tick('clear-error', i_error_clear=1)
        for name in (
            'i_config_tx_enable',
            'i_config_rx_enable',
            'i_config_context_check',
            'i_config_context_id',
        ):
            for unknown in ('x', 'z'):
                await self.tick(
                    'unknown-config-' + name, i_config_valid=1, **{name: unknown * c.widths[name]}
                )
                assert num(self.last.post.ports['o_config_rejected']) == 1
                await self.tick('clear-error', i_error_clear=1)
        # Every channel/class and each byte lane receives nonzero, sparse data.
        for tc in range(c.NUM_TRAFFIC_CLASSES):
            await self.send(
                [
                    self.beat(n, traffic_class=tc, keep=1 << ((tc + n) % c.aliases['TB']))
                    for n in range(c.NUM_TX_CHANNELS)
                ],
                peer={'loopback': True},
            )
            await self.drain(peer={'loopback': True})
        for endpoint in range(c.NUM_RX_CHANNELS):
            for tc in range(c.NUM_TRAFFIC_CLASSES):
                await self.tick(
                    'rx-endpoints-classes', packets=[self.packet(endpoint, traffic_class=tc)]
                )
        await self.drain()
        if not c.NOC_FLOW_CONTROL:
            await self.send([self.beat()] + [None] * (c.NUM_TX_CHANNELS - 1), peer={'tx_ready': 0})
            for fragment in range(c.fragments):
                await self.wait(3, 'fragment-stalled', peer={'tx_ready': 0})
                assert num(self.last.pre.ports['o_noc_tx_valid']) == 1
                assert num(self.last.pre.ports['o_noc_tx_fragment_index']) == fragment
                for unknown in ('x', 'z'):
                    await self.tick('unknown-tx-ready', i_noc_tx_ready=unknown)
                await self.tick('fragment-advance')
            await self.drain()
            await self.tick('clear-error', i_error_clear=1)
        await self.tick('rx-unknown-ready-packet', packets=[self.packet()], i_tile_rx_ready=0)
        await self.wait(10 + c.fragments * 3, 'rx-ready-held', i_tile_rx_ready=0)
        assert num(self.last.pre.ports['o_tile_rx_valid']) != 0
        for unknown in ('x', 'z'):
            await self.tick('unknown-tile-ready', i_tile_rx_ready=unknown * c.NUM_RX_CHANNELS)
        await self.drain()
        await self.tick('clear-error', i_error_clear=1)
        # Fill ejection queues/completion slots, then release all destinations.
        packets = [
            self.packet(n % c.NUM_RX_CHANNELS, traffic_class=n % c.NUM_TRAFFIC_CLASSES)
            for n in range((c.RX_QUEUE_DEPTH + 3) * c.NUM_RX_CHANNELS * c.NUM_VCS)
        ]
        await self.tick('rx-backpressure', packets=packets, i_tile_rx_ready=0)
        await self.wait(40 + 4 * c.fragments * len(packets), 'rx-blocked', i_tile_rx_ready=0)
        await self.drain()
        # Exhaust all credit/queue capacity or stall every valid-ready fragment.
        for _ in range(c.TX_QUEUE_DEPTH):
            await self.send(
                [self.beat(n) for n in range(c.NUM_TX_CHANNELS)],
                peer={'pause_credit': True, 'tx_ready': 0},
            )
        await self.wait(
            20 + c.fragments * c.NUM_TX_CHANNELS,
            'tx-blocked',
            offers=[self.beat(n) for n in range(c.NUM_TX_CHANNELS)],
            peer={'pause_credit': True, 'tx_ready': 0},
        )
        await self.tick(
            'drain-blocks-injection', [self.beat(n) for n in range(c.NUM_TX_CHANNELS)], i_drain=1
        )
        await self.drain()
        await self.tick('drain-done', i_drain=1)
        assert num(self.last.post.ports['o_drain_done']) == 1
        # Reset/flush exercise accepted work in queues, partial packets and serializer.
        for reset in (False, True):
            await self.send(
                [self.beat(n) for n in range(c.NUM_TX_CHANNELS)],
                peer={'tx_ready': 0, 'pause_credit': True},
            )
            partial = self.packet()[: max(1, c.fragments - 1)]
            await self.tick(
                'partial',
                packets=[partial],
                i_tile_rx_ready=0,
                peer={'tx_ready': 0, 'pause_credit': True},
            )
            await self.wait(
                3, 'partial-wait', i_tile_rx_ready=0, peer={'tx_ready': 0, 'pause_credit': True}
            )
            if reset:
                await self.tick('reset-held-active', i_rstb=0, edge=False)
                await self.tick('reset-active', i_rstb=0)
                await self.configure()
            else:
                await self.tick('flush-active', i_flush=1)
                assert num(self.last.post.ports['o_flushed']) == 1
        # Cancel a queued TX beat before its first launch, including one-flit credit profiles.
        await self.send(
            [self.beat(n) for n in range(c.NUM_TX_CHANNELS)],
            peer={'tx_ready': 0, 'pause_credit': True},
        )
        await self.tick('flush-before-launch', i_flush=1)
        for _ in range((1 << c.LINK_EPOCH_WIDTH) + 1):
            await self.tick('flush-epoch-wrap', i_flush=1)
        await self.tick('flush-release')
        await self.tick('clear-error', i_error_clear=1)
        # Rejected tile beats never occupy storage.
        for fields in (dict(keep=0), dict(context_id=1)):
            await self.send([self.beat(0, **fields)] + [None] * (c.NUM_TX_CHANNELS - 1))
            await self.drain()
            await self.tick('clear-error', i_error_clear=1)
        if c.NUM_TRAFFIC_CLASSES < 1 << c.aliases['TC']:
            await self.send(
                [self.beat(traffic_class=c.NUM_TRAFFIC_CLASSES)] + [None] * (c.NUM_TX_CHANNELS - 1)
            )
            await self.tick('clear-error', i_error_clear=1)
        await self.configure(i_config_tx_enable=0, i_config_rx_enable=0)
        await self.send([self.beat(n) for n in range(c.NUM_TX_CHANNELS)])
        await self.bad_packet('disabled-rx', self.packet())
        await self.configure()
        # Malformed streams are quarantined; the next valid header recovers.
        faults = [
            ('orphan', 'head', 0),
            ('tail', 'tail', int(c.fragments != 1)),
            ('destination', 'destination_node', c.LOCAL_NODE_ID ^ 1),
            ('context', 'context_id', 1),
            ('keep', 'keep', 0),
        ]
        if c.NUM_VCS > 1:
            faults.append(('vc-map', 'vc', (c.vc(0) + 1) % c.NUM_VCS))
        if c.NUM_TRAFFIC_CLASSES < 1 << c.aliases['TC']:
            faults.append(('class', 'traffic_class', c.NUM_TRAFFIC_CLASSES))
        if c.NUM_RX_CHANNELS < 1 << c.ENDPOINT_ID_WIDTH:
            faults.append(('endpoint', 'destination_endpoint', c.NUM_RX_CHANNELS))
        for label, field, value in faults:
            packet = self.packet(traffic_class=0)
            for f in packet:
                if field not in ('head', 'tail') or f is packet[0]:
                    f[field] = value
                f['parity'] = parity(c, f) if c.ENABLE_LINK_PARITY else 0
            await self.bad_packet(label, packet)
            await self.tick('recovery-packet', packets=[self.packet()])
            await self.drain()
        if c.fragments > 1:
            for label in ('sideband', 'index', 'restart'):
                packet = self.packet()
                if label == 'sideband':
                    packet[-1]['packet_id'] ^= 1
                elif label == 'index':
                    packet[-1]['fragment_index'] = 0
                else:
                    packet = packet[:-1] + self.packet(traffic_class=packet[0]['traffic_class'])
                for f in packet:
                    f['parity'] = parity(c, f) if c.ENABLE_LINK_PARITY else 0
                await self.bad_packet(label, packet)
        if c.fragments * c.NOC_FLIT_DATA_WIDTH > c.TILE_DATA_WIDTH:
            packet = self.packet()
            f = packet[-1]
            unused = c.aliases['TB'] % c.aliases['FB']
            f['data'] = bits(num(f['data']) | (1 << (unused * 8)), c.NOC_FLIT_DATA_WIDTH)
            f['parity'] = parity(c, f) if c.ENABLE_LINK_PARITY else 0
            await self.bad_packet('padding', packet)
        if c.ENABLE_LINK_PARITY:
            for field in FLIT_FIELDS:
                if field == 'vc' and c.NUM_VCS == 1:
                    continue
                packet = self.packet(traffic_class=0)
                f = packet[0]
                f[field] = num(f[field]) ^ 1
                if field == 'data':
                    f[field] = bits(f[field], c.NOC_FLIT_DATA_WIDTH)
                if field == 'vc' and c.fragments > 1:
                    # A corrupt VC splits the packet across contexts; coordinated flush recovers.
                    await self.tick('parity-vc', packets=[packet])
                    await self.wait(10 + 4 * c.fragments, 'quarantine-vc')
                    await self.tick('flush-corrupt-vc', i_flush=1)
                    await self.tick('clear-error', i_error_clear=1)
                else:
                    await self.bad_packet('parity-' + field, packet)
        # Stale ownership must not enter the new epoch or release its credits.
        stale = self.packet()
        for f in stale:
            f['epoch'] ^= 1
            f['parity'] = parity(c, f) if c.ENABLE_LINK_PARITY else 0
        await self.bad_packet('stale', stale)
        if c.NOC_FLOW_CONTROL:
            await self.tick(
                'excess-credit',
                i_noc_tx_credit_valid=1,
                i_noc_tx_credit_vc=0,
                i_noc_tx_credit_epoch=num(self.last.post.ports['o_link_epoch']),
            )
            await self.tick('clear-error', i_error_clear=1)
            await self.tick(
                'old-credit',
                i_noc_tx_credit_valid=1,
                i_noc_tx_credit_epoch=num(self.last.post.ports['o_link_epoch']) ^ 1,
            )
            await self.tick('clear-error', i_error_clear=1)
        if c.NOC_FLOW_CONTROL:
            # Deliberately violate sender credits only after the VC FIFO is full.
            packets = [
                self.packet(traffic_class=0) for _ in range(c.RX_QUEUE_DEPTH + c.RX_VC_DEPTH + 4)
            ]
            await self.tick('overflow-fill', packets=packets, i_tile_rx_ready=0)
            await self.wait(
                20 + len(packets) * c.fragments * 3, 'overflow-blocked', i_tile_rx_ready=0
            )
            v = c.vc(0)
            from tile_network_interface.model import lane

            assert (
                lane(self.last.post.ports['o_rx_vc_occupancy'], v, c.aliases['VO']) == c.RX_VC_DEPTH
            )
            f = self.packet(traffic_class=0)[0]
            await self.tick(
                'overflow-violation',
                i_noc_rx_valid=1,
                i_tile_rx_ready=0,
                **{'i_noc_rx_' + n: value for n, value in f.items()},
            )
            assert num(self.last.post.ports['o_error_code']) == 9
            await self.tick(
                'fatal-holds-admission',
                [self.beat(n) for n in range(c.NUM_TX_CHANNELS)],
                i_tile_rx_ready=0,
            )
            assert num(self.last.pre.ports['o_tile_tx_ready']) == 0
            await self.tick('flush-fatal', i_flush=1)
            await self.tick('clear-error', i_error_clear=1)
        # Four-state probes cannot grant control or mutate state without an edge.
        for name in (
            'i_drain',
            'i_flush',
            'i_config_valid',
            'i_error_clear',
            'i_tile_tx_valid',
            'i_noc_rx_valid',
        ):
            for unknown in ('x', 'z'):
                await self.tick('unknown-' + name, **{name: unknown * c.widths[name]})
                await self.tick('clear-error', i_error_clear=1)
        from tile_network_interface.transaction import TX_FIELDS

        for field in TX_FIELDS:
            if field == 'data':
                continue
            width = c.widths['i_tile_tx_' + field] // c.NUM_TX_CHANNELS
            for unknown in ('x', 'z'):
                offers = [self.beat(**{field: unknown * width})] + [None] * (c.NUM_TX_CHANNELS - 1)
                await self.send(offers)
                await self.tick('clear-error', i_error_clear=1)
        for field in FLIT_FIELDS:
            if field in ('data', 'parity'):
                continue
            packet = self.packet(traffic_class=0)
            f = packet[0]
            width = c.widths['i_noc_rx_' + field]
            for unknown in ('x', 'z'):
                fields = {'i_noc_rx_' + n: v for n, v in f.items()}
                fields['i_noc_rx_' + field] = unknown * width
                await self.tick('unknown-rx-' + field, i_noc_rx_valid=1, **fields)
                await self.tick('clear-error', i_error_clear=1)
        if c.NUM_VCS < 1 << c.aliases['VW']:
            fields = {'i_noc_rx_' + n: v for n, v in self.packet(traffic_class=0)[0].items()}
            fields['i_noc_rx_vc'] = c.NUM_VCS
            await self.tick('invalid-rx-vc', i_noc_rx_valid=1, **fields)
            await self.tick('clear-error', i_error_clear=1)
        for name in ('i_noc_tx_credit_valid', 'i_noc_tx_credit_vc', 'i_noc_tx_credit_epoch'):
            for unknown in ('x', 'z'):
                fields = dict(
                    i_noc_tx_credit_valid=1,
                    i_noc_tx_credit_epoch=num(self.last.post.ports['o_link_epoch']),
                )
                fields[name] = unknown * c.widths[name]
                await self.tick('unknown-credit-' + name, **fields)
                await self.tick('clear-error', i_error_clear=1)
        if c.NOC_FLOW_CONTROL and c.NUM_VCS < 1 << c.aliases['VW']:
            await self.tick(
                'invalid-credit-vc',
                i_noc_tx_credit_valid=1,
                i_noc_tx_credit_vc=c.NUM_VCS,
                i_noc_tx_credit_epoch=num(self.last.post.ports['o_link_epoch']),
            )
            await self.tick('clear-error', i_error_clear=1)
        await self.tick('no-edge', [self.beat(n) for n in range(c.NUM_TX_CHANNELS)], edge=False)
        # Disabled bytes clamp unknown data; valid bytes may carry four-state data.
        if not c.ENABLE_LINK_PARITY:
            await self.send(
                [self.beat(data='x' * c.TILE_DATA_WIDTH, keep=1)]
                + [None] * (c.NUM_TX_CHANNELS - 1),
                peer={'loopback': True},
            )
            await self.drain(peer={'loopback': True})
        pending = [None] * c.NUM_TX_CHANNELS
        for cycle in range(c.random_cycles):
            for n in range(c.NUM_TX_CHANNELS):
                if pending[n] is None and self.rng.random() < 0.3:
                    pending[n] = self.beat(n)
            packets = (
                [self.packet(self.rng.randrange(c.NUM_RX_CHANNELS))]
                if self.rng.random() < 0.12
                else []
            )
            if packets and cycle % 19 == 0:
                f = packets[0][-1]
                if c.ENABLE_LINK_PARITY:
                    f['parity'] ^= 1
                else:
                    f['destination_node'] ^= 1
            item = await self.tick(
                'random',
                pending,
                packets=packets,
                random=True,
                peer={'random': True},
                i_drain=int(cycle % 101 in range(91, 101)),
            )
            ready = num(item.pre.ports['o_tile_tx_ready'])
            pending = [None if ready >> n & 1 else beat for n, beat in enumerate(pending)]
            if cycle in (399, 799, 1199):
                await self.tick('random-flush', i_flush=1)
                await self.configure(i_config_context_id=self.context ^ 1)
        await self.send(pending)
        await self.drain()
        await self.tick('clear-final-error', i_error_clear=1)
