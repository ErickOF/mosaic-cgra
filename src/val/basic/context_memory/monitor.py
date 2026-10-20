"""Observe every read port, validity bit, and portable storage word."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from context_memory.transaction import Activity, INPUTS, OUTPUTS, Observation


class ContextMemoryMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    async def activity(self, name, handle):
        previous = logic(handle)
        while True:
            await handle.value_change
            quiet = self.active["quiet"].get(name, 0)
            await ReadOnly()
            current = logic(handle)
            if current != previous:
                self.ap.write(Activity(name, previous, current, quiet))
                previous = current

    async def run_phase(self):
        await Timer(2, unit="ps")
        await ReadOnly()
        handles = {name: getattr(cocotb.top, name) for name in OUTPUTS}
        if self.config.check_internals:
            handles["context_valid"] = cocotb.top.context_valid
            handles.update({f"context_data[{index}]": cocotb.top.context_data[index] for index in range(self.config.depth)})
        tasks = [cocotb.start_soon(self.activity(name, handle)) for name, handle in handles.items()]
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                self.ap.write(Observation(
                    {name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)},
                    tuple(logic(cocotb.top.context_data[index]) for index in range(self.config.depth)) if self.config.check_internals else None,
                    logic(cocotb.top.context_valid) if self.config.check_internals else None,
                    self.active["item"], self.active["stage"],
                ))
                self.active["sample"].clear()
        finally:
            for task in tasks:
                task.cancel()
