"""Run the always-on clock and a separate fixed functional clock source."""
import cocotb
from cocotb.clock import Clock
from cocotb.handle import Force, Release
from cocotb.types import LogicArray
from cocotb.triggers import Timer, ReadOnly
from pyuvm import ConfigDB, uvm_driver
from cluster_power_manager.transaction import INPUTS


class PowerDriver(uvm_driver):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')

    async def run_phase(self):
        dut = cocotb.top
        source = cocotb.start_soon(Clock(dut.i_functional_clk, 10, unit='ns').start(start_high=False))
        forced = None
        try:
            await Timer(1, unit='ns')
            while True:
                item = await self.seq_item_port.get_next_item()
                self.active['item'] = item
                dut.i_aon_clk.value = 0
                if forced is not None:
                    forced.value = Release()
                    forced = None
                for name in INPUTS:
                    getattr(dut, name).value = LogicArray(item.ports[name]) if isinstance(item.ports[name], str) else item.ports[name]
                await Timer(3, unit='ns')
                if mask := self.active.pop('inject', 0):
                    forced = dut.g_manager.u_state.stored
                    forced.value = Force(int(forced.value) ^ mask)
                await Timer(4, unit='ns')
                dut.i_aon_clk.value = 1
                await Timer(8, unit='ns')
                self.active['sample'].set()
                await ReadOnly()
                await Timer(5, unit='ns')
                self.seq_item_port.item_done()
        finally:
            source.cancel()
