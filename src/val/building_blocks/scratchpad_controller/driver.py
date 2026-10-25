"""Clock driver and programmable bank endpoints; no prediction of DUT outputs."""
import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from scratchpad_controller.model import pack
from scratchpad_controller.peer import BankPeers
from scratchpad_controller.transaction import INPUTS, REQ_FIELDS


class ControllerDriver(uvm_driver):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.peers = BankPeers(self.c)

    async def sample(self, stage):
        self.active['stage'] = stage
        self.active['sample'].set()
        await ReadOnly()
        await Timer(1, unit='ps')
        assert not self.active['sample'].is_set()

    async def run_phase(self):
        await Timer(4, unit='ns')
        c = self.c
        while True:
            item = await self.seq_item_port.get_next_item()
            self.active['item'] = item
            if c.instrumentation:
                dut = cocotb.top.u_controller if c.integration else cocotb.top
                instrument = dut.g_controller.u_instrumentation
                instrument.test_enable.value = item.peer.get('counter_enable', 1)
                instrument.test_clear.value = item.peer.get('counter_clear', 0)
            if c.integration and 'fault' in item.peer:
                bank, word, mask = item.peer['fault']
                memory = cocotb.top.g_bank[bank].u_bank.g_bank.u_storage.g_shell.u_backend.g_inferred.memory
                handle = memory[word]
                handle.value = int(handle.value) ^ mask
            ports = dict.fromkeys(INPUTS, 0) | item.controls
            ports['i_client_req_valid'] = pack([int(e is not None) for e in item.clients], 1)
            for name in REQ_FIELDS:
                key = 'i_client_req_' + name
                ports[key] = pack([e[name] if e else 0 for e in item.clients], c.widths[key] // c.NUM_CLIENTS)
            if not c.integration:
                ports.update(self.peers.inputs(item.peer))
            if c.integration:
                request_enable = item.peer.get('ready', (1 << c.NUM_BANKS) - 1)
                response_enable = item.peer.get('launch', (1 << c.NUM_BANKS) - 1)
                if item.post is not None:
                    raise AssertionError('Transaction reused')
                if hasattr(self, 'previous'):
                    from scratchpad_controller.model import unpack
                    old = self.previous
                    for b in range(c.NUM_BANKS):
                        before = self.previous_storage
                        if before[f'bank:{b}:i_req_valid'] == '1' and before[f'bank:{b}:o_req_ready'] != '1':
                            request_enable |= 1 << b
                    for b, (valid, ready) in enumerate(zip(
                            unpack(old['i_bank_rsp_valid'], c.NUM_BANKS, 1),
                            unpack(old['o_bank_rsp_ready'], c.NUM_BANKS, 1))):
                        if valid == 1 and ready != 1:
                            response_enable |= 1 << b
                cocotb.top.i_bank_request_enable.value = request_enable
                cocotb.top.i_bank_response_enable.value = response_enable
            ports.update(item.peer.get('ports', {}))
            for name, value in ports.items():
                if not (c.integration and name.startswith('i_bank_')):
                    getattr(cocotb.top, name).value = value
            await Timer(2, unit='ns')
            await self.sample('pre')
            if item.edge:
                cocotb.top.i_clk.value = 1
            if not c.integration:
                self.peers.step(item.pre.ports, item.edge, item.peer)
            await Timer(2, unit='ns')
            await self.sample('post')
            self.previous = item.pre.ports
            self.previous_storage = item.pre.storage
            await Timer(3, unit='ns')
            await self.sample('held')
            cocotb.top.i_clk.value = 0
            await Timer(3, unit='ns')
            self.seq_item_port.item_done()
