"""WriteGate driver components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from mosaic_uvm.logic import bits


class WriteGateDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")

    async def sample(self, stage):
        assert not self.active["sample"].is_set(), "Monitor missed a sample"
        self.active["stage"] = stage
        self.active["sample"].set()
        await ReadOnly()

    async def run_phase(self):
        await Timer(5, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            await Timer(1, unit="ps")
            write, suppress = bits(item.inputs.write, self.config.width), bits(item.inputs.suppress, self.config.width)
            unchanged = (write == str(cocotb.top.i_write_enable.value).lower()
                         and suppress == str(cocotb.top.i_suppress.value).lower())
            self.active.update(item=item, quiet=unchanged, capture_window=False)
            cocotb.top.i_write_enable.value = write
            cocotb.top.i_suppress.value = suppress
            if self.config.integration:
                inputs = item.inputs
                assert inputs.destination in ("register", "memory") and 0 <= inputs.address < 4
                cocotb.top.i_write_data.value = bits(inputs.data, self.config.width)
                cocotb.top.i_destination.value = inputs.destination == "memory"
                cocotb.top.i_address.value = inputs.address
                cocotb.top.i_capture_valid.value = inputs.protocol == "accepted"
            await Timer(self.config.sample_ns, unit="ns")
            await self.sample("settled")
            self.active["quiet"] = True
            if self.config.integration:
                await Timer(1, unit="ps")
                self.active["capture_window"] = True
                cocotb.top.i_clk.value = 1
                await Timer(1, unit="ps")
                await self.sample("captured")
                self.active["capture_window"] = False
            await Timer(item.hold_ns, unit="ns")
            await self.sample("held")
            await Timer(1, unit="ps")
            if self.config.integration:
                cocotb.top.i_clk.value = 0
                await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor missed the held sample"
            self.seq_item_port.item_done()
