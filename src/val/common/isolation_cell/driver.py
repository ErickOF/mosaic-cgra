"""IsolationCell driver components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver


class IsolationCellDriver(uvm_driver):
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
            # Clamp assertion/release may change the output. Only an interval
            # that starts and stays isolated is required to have no activity.
            self.active["quiet"] = (
                str(self.dut.i_isolate.value) == str(self.config.active_control)
                and item.inputs.isolate == self.config.active_control
            )
            self.dut.i_isolate.value = item.inputs.isolate
            self.dut.i_data.value = item.inputs.data_bits(self.config.width)
            await Timer(self.config.sample_ns, unit="ns")
            self.active["sample"].set()
            await ReadOnly()
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "The monitor did not consume the sample"
            self.seq_item_port.item_done()
