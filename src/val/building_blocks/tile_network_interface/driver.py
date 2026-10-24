"""Clock driver and token-aware external NoC peer, independent of the checker."""

from collections import deque
from copy import deepcopy
import random
import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from mosaic_uvm.logic import bits
from tile_network_interface.model import flit, num, pack
from tile_network_interface.transaction import INPUTS, TX_FIELDS


class InterfaceDriver(uvm_driver):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.rng = random.Random(self.c.seed ^ 0xA381)
        self.cycle = self.pointer = 0
        self.clear_peer()

    def clear_peer(self):
        self.inbox = [deque() for _ in range(self.c.NUM_VCS)]
        self.tokens = [self.c.RX_VC_DEPTH] * self.c.NUM_VCS
        self.returns = deque()
        self.held = None

    async def sample(self, stage):
        self.active['stage'] = stage
        self.active['sample'].set()
        await ReadOnly()
        await Timer(1, unit='ps')
        assert not self.active['sample'].is_set(), f'Missed {stage}'

    def drive(self, item):
        c = self.c
        for packet in item.packets:
            for f in packet:
                self.inbox[f['vc']].append(deepcopy(f))
        ports = dict.fromkeys(INPUTS, 0)
        ports.update(
            i_rstb=1,
            i_tile_rx_ready=(1 << c.NUM_RX_CHANNELS) - 1,
            i_noc_tx_ready=item.peer.get('tx_ready', 1),
        )
        if item.peer.get('random'):
            ports['i_noc_tx_ready'] = int(self.rng.random() < 0.7)
            ports['i_tile_rx_ready'] = self.rng.getrandbits(c.NUM_RX_CHANNELS)
        ports['i_tile_tx_valid'] = sum(1 << n for n, b in enumerate(item.offers) if b)
        for field in TX_FIELDS:
            key = 'i_tile_tx_' + field
            width = c.widths[key] // c.NUM_TX_CHANNELS
            ports[key] = pack([b[field] if b else 0 for b in item.offers], width)
        if self.held is None and not item.peer.get('pause_rx'):
            candidates = [(self.pointer + k) % c.NUM_VCS for k in range(c.NUM_VCS)]
            self.held = next(
                (
                    v
                    for v in candidates
                    if self.inbox[v]
                    and (
                        not c.NOC_FLOW_CONTROL
                        or self.tokens[v] > 0
                        or self.inbox[v][0]['epoch'] != num(str(cocotb.top.o_link_epoch.value))
                    )
                ),
                None,
            )
        self.rx_source = self.held
        if self.held is not None:
            ports['i_noc_rx_valid'] = 1
            ports.update({'i_noc_rx_' + n: v for n, v in self.inbox[self.held][0].items()})
        self.return_source = None
        if self.returns and self.returns[0][0] <= self.cycle and not item.peer.get('pause_credit'):
            self.return_source = self.returns[0]
            _, v, epoch = self.return_source
            ports.update(i_noc_tx_credit_valid=1, i_noc_tx_credit_vc=v, i_noc_tx_credit_epoch=epoch)
        ports.update(item.controls)
        # Manual fault probes do not consume a queued peer transaction.
        if 'i_noc_rx_valid' in item.controls:
            self.rx_source = None
        if 'i_noc_tx_credit_valid' in item.controls:
            self.return_source = None
        for name in INPUTS:
            getattr(cocotb.top, name).value = bits(ports[name], c.widths[name])

    def retire(self, item):
        c, ports = self.c, item.pre.ports
        p = {n: num(v) for n, v in ports.items()}
        if not item.edge:
            return
        if p['i_rstb'] == 0 or p['i_flush'] == 1:
            self.clear_peer()
            return
        if p['i_rstb'] != 1:
            return
        # Registered returned credits belong to the previous edge's pop.
        if c.NOC_FLOW_CONTROL and p['o_noc_rx_credit_valid'] == 1:
            v = p['o_noc_rx_credit_vc']
            if p['o_noc_rx_credit_epoch'] == p['o_link_epoch']:
                self.tokens[v] += 1
                assert self.tokens[v] <= c.RX_VC_DEPTH, 'Peer received a duplicate credit'
        if self.return_source is not None:
            self.returns.popleft()
        if (
            self.rx_source is not None
            and p['i_noc_rx_valid'] == 1
            and (c.NOC_FLOW_CONTROL or p['o_noc_rx_ready'] == 1)
        ):
            v = self.rx_source
            self.inbox[v].popleft()
            if c.NOC_FLOW_CONTROL and p['i_noc_rx_epoch'] == p['o_link_epoch']:
                self.tokens[v] -= 1
                assert self.tokens[v] >= 0
            self.pointer = (v + 1) % c.NUM_VCS
            self.held = None
        if p['o_noc_tx_valid'] == 1 and (c.NOC_FLOW_CONTROL or p['i_noc_tx_ready'] == 1):
            f = flit(c, ports, 'o_noc_tx_')
            if c.NOC_FLOW_CONTROL:
                self.returns.append((self.cycle + self.rng.randint(1, 7), f['vc'], f['epoch']))
            if item.peer.get('loopback'):
                self.inbox[f['vc']].append(f)

    async def run_phase(self):
        await Timer(4, unit='ns')
        while True:
            item = await self.seq_item_port.get_next_item()
            self.active['item'] = item
            self.drive(item)
            await Timer(2, unit='ns')
            await self.sample('pre')
            if item.edge:
                cocotb.top.i_clk.value = 1
            await Timer(2, unit='ns')
            await self.sample('post')
            await Timer(3, unit='ns')
            await self.sample('held')
            self.retire(item)
            item.peer_pending = sum(map(len, self.inbox)) + len(self.returns)
            cocotb.top.i_clk.value = 0
            await Timer(3, unit='ns')
            self.cycle += int(item.edge)
            self.seq_item_port.item_done()
