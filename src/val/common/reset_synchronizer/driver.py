"""ResetSynchronizer driver components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from cocotb.utils import get_sim_time
from pyuvm import ConfigDB, uvm_driver
from mosaic_uvm.logic import logic
from reset_synchronizer.model import reset_negedge


class ResetSynchronizerDriver(uvm_driver):
    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")

    async def run_phase(self):
        await Timer(3, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            old_clk, old_reset = logic(cocotb.top.i_clk), logic(cocotb.top.i_async_rstb)
            rising = old_clk == "0" and item.clk == 1
            self.active.update(item=item, stage="settled", time_ps=int(get_sim_time(unit="ps")),
                               allowed=rising or reset_negedge(old_reset, item.rstb), rising_clock=rising)
            cocotb.top.i_clk.value = item.clk
            cocotb.top.i_async_rstb.value = item.rstb
            await Timer(1, unit="ps")
            self.active["sample"].set()
            await ReadOnly()
            self.active["allowed"] = False
            # Reserve 1 ps to leave ReadOnly before the next drive. Actual
            # drive-to-drive spacing equals duration_ps, including short pulses.
            await Timer(item.duration_ps - 2, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor missed settled sample"
            self.active["stage"] = "held"
            self.active["sample"].set()
            await ReadOnly()
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor missed held sample"
            self.seq_item_port.item_done()
