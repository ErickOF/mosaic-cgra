"""Drive independent clock phases and hierarchical protection fault probes."""
import cocotb
from cocotb.handle import Force, Release
from cocotb.triggers import Timer, ReadOnly
from pyuvm import ConfigDB, uvm_driver
from tile_shell.transaction import INPUTS

class TileShellDriver(uvm_driver):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.c = ConfigDB().get(self, '', 'config')
        self.forced = None

    async def run_phase(self):
        await Timer(2, unit='ns')
        while True:
            item = await self.seq_item_port.get_next_item()
            self.active['item'] = item
            d = cocotb.top
            d.i_clk.value = 0
            d.i_cfg_clk.value = 0
            for n in INPUTS:
                getattr(d, n).value = item.ports[n]
            if item.fault:
                if item.fault[0] == 'release':
                    self.forced.value = Release()
                    self.forced = None
                else:
                    kind, index, mask = item.fault
                    b = d.g_shell
                    self.forced = (b.u_context_memory.context_valid if kind == 'validity' else
                        b.u_control.stored_valid if kind == 'state_validity' else
                        b.u_control.stored if kind == 'control' else
                        b.u_context_memory.context_data[index] if kind == 'context' else
                        b.g_data_out[index].u_channel.g_buffer.u_queue.u_metadata.u_data.o_q)
                    self.forced.value = Force(int(self.forced.value) ^ mask)
            await Timer(2, unit='ns')
            if self.c.CONFIG_ASYNC and item.cfg_edge and item.phase == 0:
                d.i_cfg_clk.value = 1
            await Timer(2, unit='ns')
            if item.core_edge:
                d.i_clk.value = 1
                if not self.c.CONFIG_ASYNC:
                    d.i_cfg_clk.value = 1
            await Timer(2, unit='ns')
            if self.c.CONFIG_ASYNC and item.cfg_edge and item.phase == 1:
                d.i_cfg_clk.value = 1
            await Timer(2, unit='ns')
            self.active['sample'].set()
            await ReadOnly()
            await Timer(2, unit='ns')
            self.seq_item_port.item_done()
