"""Drive complete public cycles; faults affect actual production storage only."""
import os
import cocotb
from cocotb.handle import Force, Release
from cocotb.triggers import Timer
from pyuvm import ConfigDB, uvm_driver
from banked_scratchpad.transaction import INPUTS


class ScratchpadDriver(uvm_driver):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.forced = None

    async def run_phase(self):
        while True:
            item = await self.seq_item_port.get_next_item()
            self.active['item'] = item
            if os.getenv('BANKED_SCRATCHPAD_DEBUG'):
                print(item.get_name(), flush=True)
            d = cocotb.top
            d.i_clk.value = 0
            for n in INPUTS:
                getattr(d, n).value = item.ports[n]
            if item.fault:
                kind, index, mask = item.fault
                core = d.g_scratchpad
                if kind == 'memory':
                    bank, word = index
                    h = core.g_bank[bank].u_bank.g_bank.u_storage.g_shell.u_backend.g_inferred.memory[word]
                    h.value = int(h.value) ^ mask
                elif kind == 'release':
                    self.forced.value = Release()
                    self.forced = None
                else:
                    h = core.g_region[index].u_descriptor.stored if kind == 'descriptor' else \
                        core.g_client[index].u_control.stored if kind == 'control' else \
                        core.completion_tag
                    self.forced = h
                    h.value = Force(int(h.value) ^ mask)
            await Timer(5, unit='ns')
            if item.edge:
                d.i_clk.value = 1
            await Timer(5, unit='ns')
            item.post = {n: getattr(d, n).value for n in self.active['outputs']}
            self.active['completion_pending'] = int(d.g_scratchpad.completion_valid.value)
            self.seq_item_port.item_done()
