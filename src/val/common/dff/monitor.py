"""Dff monitor components for specification-based PyUVM validation."""

from __future__ import annotations

import cocotb
from cocotb.triggers import First, ReadOnly, Timer
from cocotb.utils import get_sim_time
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from dff.transaction import OutputChange, Snapshot
from mosaic_uvm.logic import logic


class DffMonitor(uvm_monitor):
    """Observe settled ports and every output transition, including short glitches."""

    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top
        self.ap = uvm_analysis_port("ap", self)

    def snapshot(self) -> Snapshot:
        item = self.active["item"]
        return Snapshot(
            int(get_sim_time(unit="ps")), logic(self.dut.i_clk), logic(self.dut.i_rstb),
            logic(self.dut.i_enable), logic(self.dut.i_d), logic(self.dut.o_q),
            item.get_name() if item else "startup", item.unknown if item else None,
            item.inputs if item else None,
        )

    async def output_changes(self):
        previous = logic(self.dut.o_q)
        while True:
            await self.dut.o_q.value_change
            current = logic(self.dut.o_q)
            # Re-arm immediately: ReadOnly here could hide a transient output.
            self.ap.write(OutputChange(int(get_sim_time(unit="ps")), previous, current))
            previous = current

    async def run_phase(self):
        await Timer(1, unit="ps")
        await ReadOnly()
        self.ap.write(self.snapshot())
        output_task = cocotb.start_soon(self.output_changes())
        try:
            while True:
                await First(
                    self.dut.i_clk.value_change, self.dut.i_rstb.value_change,
                    self.dut.i_enable.value_change, self.dut.i_d.value_change,
                    self.active["sample"].wait(),
                )
                await ReadOnly()
                self.ap.write(self.snapshot())
                self.active["sample"].clear()
        finally:
            output_task.cancel()
