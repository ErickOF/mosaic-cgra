"""Retention driver components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from cocotb.utils import get_sim_time
from pyuvm import ConfigDB, uvm_driver
from mosaic_uvm.logic import bits
from retention_register.model import ports


class RetentionDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")

    async def run_phase(self):
        await Timer(3, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            previous = ports()
            reset = str(item.inputs.rstb).lower()
            falling_reset = str(previous.rstb) == "1" and reset in "0xz" or str(previous.rstb) in "xz" and reset == "0"
            self.active.update(item=item, stage="settled", time_ps=int(get_sim_time(unit="ps")),
                               allowed=previous.clk == 0 and item.inputs.clk == 1 or self.config.async_reset and falling_reset)
            for port, value in (("i_clk", item.inputs.clk), ("i_rstb", item.inputs.rstb), ("i_enable", item.inputs.enable),
                                ("i_save", item.inputs.save), ("i_restore", item.inputs.restore)):
                getattr(cocotb.top, port).value = value
            cocotb.top.i_d.value = bits(item.inputs.data, self.config.width)
            await Timer(1, unit="ps")
            self.active["sample"].set()
            await ReadOnly()
            self.active["allowed"] = False
            await Timer(item.duration_ps - 2, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor missed settled sample"
            self.active["stage"] = "held"
            self.active["sample"].set()
            await ReadOnly()
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor missed held sample"
            self.seq_item_port.item_done()
