"""Drive controls before edges; coordinate pre-edge, post-edge, and held samples."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver

from mosaic_uvm.logic import logic
from bypass_network.model import quiet_masks
from bypass_network.transaction import INPUTS


class BypassNetworkDriver(uvm_driver):
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
        await Timer(3, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            old = {name: logic(getattr(cocotb.top, name)) for name in INPUTS}
            pre = item.ports | {"i_clk": old["i_clk"]}
            self.active.update(item=item, quiet=quiet_masks(self.config, old, pre))
            for name, value in item.ports.items():
                if name != "i_clk":
                    getattr(cocotb.top, name).value = value
            await Timer(1, unit="ps")
            await self.sample("pre")
            rising = old["i_clk"] == "0" and item.ports["i_clk"] == "1"
            self.active["quiet"] = quiet_masks(self.config, pre, item.ports, rising=rising)
            cocotb.top.i_clk.value = item.ports["i_clk"]
            await Timer(1, unit="ps")
            await self.sample("post")
            self.active["quiet"] = {name: (1 << len(getattr(cocotb.top, name))) - 1 for name in self.active["quiet"]
                                    if self.config.check_internals or not name.startswith("registered_")}
            await Timer(item.hold_ps, unit="ps")
            await self.sample("held")
            self.seq_item_port.item_done()
