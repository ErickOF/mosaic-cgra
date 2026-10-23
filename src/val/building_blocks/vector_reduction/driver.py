"""Drive stable requests, real rising edges and clockless/stalled opportunities."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver

from vector_reduction.transaction import INPUTS


class ReductionDriver(uvm_driver):
    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")

    async def sample(self, stage):
        self.active["stage"] = stage
        self.active["sample"].set()
        await ReadOnly()
        await Timer(1, unit="ps")
        assert not self.active["sample"].is_set(), f"Monitor missed {stage}"

    async def run_phase(self):
        await Timer(4, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            self.active.update(item=item, window="inputs")
            for name in INPUTS:
                getattr(cocotb.top, name).value = item.ports[name]
            await Timer(2, unit="ps")
            await self.sample("pre")
            self.active["window"] = "edge" if item.edge else "hold"
            if item.edge:
                cocotb.top.i_clk.value = 1
            await Timer(2, unit="ps")
            await self.sample("post")
            self.active["window"] = "hold"
            await Timer(3, unit="ps")
            await self.sample("held")
            cocotb.top.i_clk.value = 0
            await Timer(1, unit="ps")
            self.seq_item_port.item_done()
