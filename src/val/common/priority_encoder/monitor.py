"""PriorityEncoder monitor components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from priority_encoder.constants import SIGNALS
from priority_encoder.transaction import Observation, OutputActivity


class PriorityEncoderMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    async def output_activity(self, signal):
        handle = getattr(cocotb.top, signal)
        previous = str(handle.value).lower()
        while True:
            await handle.value_change
            quiet = self.active["quiet"]
            # Ignore transient callback values inside one combinational delta
            # evaluation, but catch finite pulses before transaction sampling.
            await ReadOnly()
            value = str(handle.value).lower()
            if value != previous:
                self.ap.write(OutputActivity(signal, value, quiet))
                previous = value

    async def run_phase(self):
        await Timer(1, unit="ps")
        await ReadOnly()
        tasks = [cocotb.start_soon(self.output_activity(signal)) for signal in SIGNALS]
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                item = self.active["item"]
                self.ap.write(Observation(
                    item.get_name(), str(cocotb.top.i_request.value).lower(),
                    tuple(str(getattr(cocotb.top, signal).value).lower() for signal in SIGNALS),
                    item.request, item.expected_ambiguity, self.active["stage"], item.hold_ns,
                ))
                self.active["sample"].clear()
        finally:
            for task in tasks:
                task.cancel()
