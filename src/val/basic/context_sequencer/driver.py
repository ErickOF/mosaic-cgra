"""Drive controls before the clock and sample pre-edge, post-edge, and hold."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from mosaic_uvm.logic import logic
from context_sequencer.constants import INPUTS, INTERNALS, OUTPUTS, REGISTERED


class SequencerDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")

    async def sample(self, stage):
        self.active["stage"] = stage
        self.active["sample"].set()
        await ReadOnly()
        await Timer(1, unit="ps")
        assert not self.active["sample"].is_set(), f"Monitor missed {stage} sample"

    async def run_phase(self):
        await Timer(6, unit="ps")
        registered = REGISTERED | {"internal:" + name for name in INTERNALS}
        while True:
            item = await self.seq_item_port.get_next_item()
            old_clock = logic(cocotb.top.i_clk)
            reset = self.config.async_reset and item.ports["i_rstb"] == "0"
            self.active.update(item=item, quiet=set() if reset else registered)
            for name in INPUTS:
                if name != "i_clk":
                    getattr(cocotb.top, name).value = item.ports[name]
            await Timer(1, unit="ps")
            await self.sample("pre")
            rising = old_clock == "0" and item.ports["i_clk"] == "1"
            self.active["quiet"] = set() if rising or reset else registered
            cocotb.top.i_clk.value = item.ports["i_clk"]
            await Timer(1, unit="ps")
            await self.sample("post")
            self.active["quiet"] = set(OUTPUTS) | {"internal:" + name for name in INTERNALS}
            await Timer(item.hold_ps, unit="ps")
            await self.sample("held")
            self.seq_item_port.item_done()
