"""WriteGate monitor components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from write_gate.transaction import Activity, Observation


class WriteGateMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    async def activity(self, name):
        signal = getattr(cocotb.top, name)
        previous = str(signal.value).lower()
        while True:
            await signal.value_change
            quiet, capture = self.active["quiet"], self.active["capture_window"]
            await ReadOnly()
            value = str(signal.value).lower()
            if value != previous:
                self.ap.write(Activity(name, value, quiet, capture))
                previous = value

    async def run_phase(self):
        await Timer(4, unit="ps")
        await ReadOnly()
        signals = ["o_write_enable", "o_write_suppressed"]
        if self.config.integration:
            signals += ["o_register_state", "o_memory_state"]
        tasks = [cocotb.start_soon(self.activity(name)) for name in signals]
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                extra = (
                    str(cocotb.top.i_write_data.value).lower(), int(cocotb.top.i_destination.value),
                    int(cocotb.top.i_address.value), int(cocotb.top.i_capture_valid.value),
                    str(cocotb.top.o_register_state.value).lower(), str(cocotb.top.o_memory_state.value).lower(),
                ) if self.config.integration else (None,) * 6
                self.ap.write(Observation(
                    self.active["item"], self.active["stage"],
                    str(cocotb.top.i_write_enable.value).lower(), str(cocotb.top.i_suppress.value).lower(),
                    str(cocotb.top.o_write_enable.value).lower(), str(cocotb.top.o_write_suppressed.value).lower(),
                    *extra,
                ))
                self.active["sample"].clear()
        finally:
            for task in tasks:
                task.cancel()
