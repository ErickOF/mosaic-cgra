"""PriorityEncoder driver components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from mosaic_uvm.logic import bits


class PriorityEncoderDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")

    async def run_phase(self):
        await Timer(2, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            await Timer(1, unit="ps")
            request = bits(item.request, self.config.width)
            self.active.update(item=item, stage="settled", quiet=str(cocotb.top.i_request.value).lower() == request)
            cocotb.top.i_request.value = request
            await Timer(self.config.sample_ns, unit="ns")
            self.active["sample"].set()
            await ReadOnly()
            self.active["quiet"] = True
            await Timer(item.hold_ns, unit="ns")
            assert not self.active["sample"].is_set(), "Monitor missed the settled sample"
            self.active["stage"] = "held"
            self.active["sample"].set()
            await ReadOnly()
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor missed the held sample"
            self.seq_item_port.item_done()
