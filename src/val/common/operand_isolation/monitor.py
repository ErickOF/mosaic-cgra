"""OperandIsolation monitor components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from operand_isolation.transaction import Observation, OutputActivity


class OperandIsolationMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    async def output_activity(self):
        previous = str(cocotb.top.o_data.value).lower()
        while True:
            await cocotb.top.o_data.value_change
            quiet = self.active["quiet"]
            # Sample after combinational delta cycles. Finite pulses persisting
            # into this phase are detected even between transaction samples.
            await ReadOnly()
            value = str(cocotb.top.o_data.value).lower()
            if value != previous:
                self.ap.write(OutputActivity(value, quiet))
                previous = value

    async def run_phase(self):
        await Timer(1, unit="ps")
        await ReadOnly()
        activity_task = cocotb.start_soon(self.output_activity())
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                item = self.active["item"]
                self.ap.write(Observation(
                    item.get_name(), str(cocotb.top.i_data.value).lower(),
                    str(cocotb.top.i_isolate.value).lower(), str(cocotb.top.o_data.value).lower(),
                    item.inputs, item.expected_unknown, self.active["stage"], item.hold_ns,
                ))
                self.active["sample"].clear()
        finally:
            activity_task.cancel()
