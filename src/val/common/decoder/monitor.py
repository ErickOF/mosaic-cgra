"""Decoder monitor components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from decoder.transaction import Observation, OutputActivity


class DecoderMonitor(uvm_monitor):
    """Read actual ports and monitor activity throughout disabled intervals."""

    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")
        self.dut = cocotb.top
        self.ap = uvm_analysis_port("ap", self)

    async def output_activity(self, signal):
        handle = getattr(self.dut, signal)
        while True:
            await handle.value_change
            # Re-arm immediately, preserving observable transients that
            # could disappear before a settled combinational sample.
            self.ap.write(OutputActivity(signal, str(handle.value).lower(), self.active["quiet"]))

    async def run_phase(self):
        await Timer(1, unit="ps")
        await ReadOnly()
        tasks = [cocotb.start_soon(self.output_activity(name)) for name in ("o_decoded", "o_select_valid")]
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                item = self.active["item"]
                self.ap.write(Observation(
                    item.get_name(), str(self.dut.i_enable.value).lower(),
                    str(self.dut.i_select.value).lower(), str(self.dut.o_decoded.value).lower(),
                    str(self.dut.o_select_valid.value).lower(), item.inputs, self.active["quiet"],
                ))
                # Consume each notification once, even if two identical input
                # transactions produce no HDL value-change callbacks.
                self.active["sample"].clear()
        finally:
            for task in tasks:
                task.cancel()
