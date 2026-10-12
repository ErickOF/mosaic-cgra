"""ClockGate monitor components for specification-based PyUVM validation."""

from __future__ import annotations

import cocotb
from cocotb.triggers import First, ReadOnly, Timer
from cocotb.utils import get_sim_time
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from clock_gate.transaction import OutputChange, Snapshot
from mosaic_uvm.logic import logic


class ClockGateMonitor(uvm_monitor):
    """Check settled inputs and capture every observable output transition."""

    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top
        self.ap = uvm_analysis_port("ap", self)

    def snapshot(self, item) -> Snapshot:
        return Snapshot(
            int(get_sim_time(unit="ps")), logic(self.dut.i_clk),
            logic(self.dut.i_enable), logic(self.dut.i_test_enable),
            logic(self.dut.o_gclk), item.get_name() if item else "startup",
            item.unknown if item else None,
        )

    async def output_changes(self):
        previous = logic(self.dut.o_gclk)
        while True:
            await self.dut.o_gclk.value_change
            current = logic(self.dut.o_gclk)
            # Do not wait for ReadOnly here: doing so would miss a transient
            # that returns to its original value within the same time step.
            self.ap.write(OutputChange(
                int(get_sim_time(unit="ps")), previous, current,
                logic(self.dut.i_clk),
            ))
            previous = current

    async def run_phase(self):
        await Timer(1, unit="ps")
        await ReadOnly()
        self.ap.write(self.snapshot(None))
        output_task = cocotb.start_soon(self.output_changes())
        try:
            while True:
                await First(
                    self.dut.i_clk.value_change, self.dut.i_enable.value_change,
                    self.dut.i_test_enable.value_change,
                )
                item = self.active["item"]
                await ReadOnly()
                self.ap.write(self.snapshot(item))
        finally:
            output_task.cancel()
