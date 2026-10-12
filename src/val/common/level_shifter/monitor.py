"""LevelShifter monitor components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from level_shifter.transaction import Observation, OutputActivity
from mosaic_uvm.logic import bits as data_bits


class LevelShifterMonitor(uvm_monitor):
    """Sample actual ports and observe output changes throughout stable intervals."""

    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    async def output_activity(self):
        while True:
            await cocotb.top.o_data.value_change
            # Re-arm immediately so a transient cannot hide before ReadOnly.
            self.ap.write(OutputActivity(str(cocotb.top.o_data.value).lower(), self.active["stable"]))

    async def run_phase(self):
        await Timer(1, unit="ps")
        await ReadOnly()
        output_task = cocotb.start_soon(self.output_activity())
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                item = self.active["item"]
                self.ap.write(Observation(
                    item.get_name(), str(cocotb.top.i_data.value).lower(), str(cocotb.top.o_data.value).lower(),
                    data_bits(item.data, self.config.width), self.active["stage"], item.hold_ns,
                ))
                self.active["sample"].clear()
        finally:
            output_task.cancel()
