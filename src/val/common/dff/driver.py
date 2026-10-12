"""Dff driver components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver


class DffDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top

    async def run_phase(self):
        await Timer(2, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            await Timer(1, unit="ps")
            self.active["item"] = item
            self.dut.i_clk.value = item.inputs.clk
            self.dut.i_rstb.value = item.inputs.rstb
            self.dut.i_enable.value = item.inputs.enable
            self.dut.i_d.value = item.inputs.data_bits(self.config.width)
            await Timer(self.config.step_ps - 2, unit="ps")
            # Sample even identical transactions, which have no input callback.
            self.active["sample"].set()
            await ReadOnly()
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "The monitor did not consume the sample"
            self.seq_item_port.item_done()
