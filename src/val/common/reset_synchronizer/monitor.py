"""ResetSynchronizer monitor components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from reset_synchronizer.transaction import Activity, Observation


class ResetSynchronizerMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)
        self.stage_handle = getattr(cocotb.top, "sync_stages", None) if self.config.check_stages else None
        if self.config.check_stages:
            assert self.stage_handle is not None and len(self.stage_handle) == self.config.stages, "Portable sync_stages vector is required"

    async def activity(self, signal, handle):
        previous = logic(handle)
        while True:
            await handle.value_change
            allowed, rising = self.active["allowed"], self.active["rising_clock"]
            await ReadOnly()
            value = logic(handle)
            if value != previous:
                self.ap.write(Activity(signal, value, logic(cocotb.top.i_clk), logic(cocotb.top.i_async_rstb), allowed, rising))
                previous = value

    async def run_phase(self):
        await Timer(1, unit="ps")
        await ReadOnly()
        tasks = [cocotb.start_soon(self.activity("o_rstb", cocotb.top.o_rstb))]
        if self.stage_handle is not None:
            tasks.append(cocotb.start_soon(self.activity("sync_stages", self.stage_handle)))
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                item = self.active["item"]
                self.ap.write(Observation(
                    self.active["time_ps"], logic(cocotb.top.i_clk), logic(cocotb.top.i_async_rstb),
                    logic(cocotb.top.o_rstb), logic(self.stage_handle) if self.stage_handle is not None else None,
                    item.get_name(), item, self.active["stage"],
                ))
                self.active["sample"].clear()
        finally:
            for task in tasks:
                task.cancel()
