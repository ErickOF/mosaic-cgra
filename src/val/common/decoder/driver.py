"""Decoder driver components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver


class DecoderDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top

    async def run_phase(self):
        await Timer(2, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            # Move out of the previous transaction's ReadOnly phase.
            await Timer(1, unit="ps")
            self.active["item"] = item
            self.active["quiet"] = str(self.dut.i_enable.value) == "0" and item.inputs.enable == 0
            self.dut.i_enable.value = item.inputs.enable
            self.dut.i_select.value = item.inputs.select_bits(self.config.select_width)
            await Timer(self.config.sample_ns, unit="ns")
            self.active["sample"].set()
            await ReadOnly()
            # Let the passive monitor finish before the sequence can end.
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "The monitor did not consume the sample"
            self.seq_item_port.item_done()
