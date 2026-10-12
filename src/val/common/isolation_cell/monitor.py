"""IsolationCell monitor components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from isolation_cell.transaction import Observation, OutputActivity


class IsolationCellMonitor(uvm_monitor):
    """Sample actual ports and capture every observable isolated output change."""

    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top
        self.ap = uvm_analysis_port("ap", self)

    async def output_activity(self):
        while True:
            await self.dut.o_data.value_change
            # Re-arm immediately so a glitch cannot hide before ReadOnly.
            self.ap.write(OutputActivity(str(self.dut.o_data.value).lower(), self.active["quiet"]))

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
                    item.get_name(), str(self.dut.i_isolate.value).lower(),
                    str(self.dut.i_data.value).lower(), str(self.dut.o_data.value).lower(),
                    item.inputs, item.unknown, self.active["quiet"],
                ))
                self.active["sample"].clear()
        finally:
            output_task.cancel()
