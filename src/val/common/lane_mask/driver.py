"""LaneMask driver components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from lane_mask.constants import SOURCES


class LaneMaskDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top

    async def run_phase(self):
        await Timer(2, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            # Leave the preceding read-only phase before writing all controls.
            await Timer(1, unit="ps")
            self.active["item"] = item
            for name, value in zip(("i_operation_valid", *SOURCES), item.inputs.ports(self.config.lanes), strict=True):
                getattr(self.dut, name).value = value
            await Timer(self.config.sample_ns, unit="ns")
            self.active["sample"].set()
            await ReadOnly()
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor did not consume the sample"
            self.seq_item_port.item_done()
