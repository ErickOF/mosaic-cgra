"""Drive real ready-valid ports; optional protected-state faults use simulator force."""
import cocotb
from cocotb.handle import Force, Release
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from runtime_controller.transaction import INPUTS


class RuntimeDriver(uvm_driver):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')

    async def run_phase(self):
        forced = None
        await Timer(1, unit='ns')
        while True:
            item = await self.seq_item_port.get_next_item()
            self.active['item'] = item
            dut = cocotb.top
            dut.i_clk.value = 0
            if forced is not None:
                forced.value = Release()
                forced = None
            for name in INPUTS:
                getattr(dut, name).value = item.ports[name]
            await Timer(2, unit='ns')
            if mask := self.active.pop('inject', 0):
                forced = dut.g_runtime.u_control.stored
                forced.value = Force(int(forced.value) ^ mask)
            await Timer(2, unit='ns')
            dut.i_clk.value = 1
            await Timer(4, unit='ns')
            self.active['sample'].set()
            await ReadOnly()
            await Timer(2, unit='ns')
            self.seq_item_port.item_done()
