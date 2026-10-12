"""Mux monitor components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mux.transaction import Observation, OutputActivity


class MuxMonitor(uvm_monitor):
    """Read actual ports and capture both outputs throughout quiet intervals."""

    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    async def output_activity(self, signal):
        handle = getattr(cocotb.top, signal)
        previous = str(handle.value).lower()
        while True:
            await handle.value_change
            quiet = self.active["quiet"]
            # Blocking defaults inside always_comb can expose intermediate
            # callback values in the same time step. Check functional activity
            # after delta cycles; a pulse lasting into this read-only phase fails.
            await ReadOnly()
            value = str(handle.value).lower()
            if value != previous:
                self.ap.write(OutputActivity(signal, value, quiet))
                previous = value

    async def run_phase(self):
        await Timer(1, unit="ps")
        await ReadOnly()
        tasks = [cocotb.start_soon(self.output_activity(name)) for name in ("o_data", "o_select_valid")]
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                item = self.active["item"]
                self.ap.write(Observation(
                    item.get_name(), str(cocotb.top.i_data.value).lower(), str(cocotb.top.i_select.value).lower(),
                    str(cocotb.top.o_data.value).lower(), str(cocotb.top.o_select_valid.value).lower(),
                    item.inputs, self.active["stage"], self.active["kind"], item.hold_ns,
                ))
                self.active["sample"].clear()
        finally:
            for task in tasks:
                task.cancel()
