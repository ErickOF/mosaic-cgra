"""Observe all real outputs and reject finite changes during quiet windows."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from context_sequencer.constants import INPUTS, INTERNALS, OUTPUTS
from context_sequencer.transaction import Activity, Observation


class SequencerMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    async def activity(self, name, handle):
        previous = logic(handle)
        while True:
            await handle.value_change
            quiet = name in self.active["quiet"]
            await ReadOnly()
            current = logic(handle)
            if current != previous:
                self.ap.write(Activity(name, previous, current, quiet))
                previous = current

    async def run_phase(self):
        await Timer(5, unit="ps")
        await ReadOnly()
        handles = {name: getattr(cocotb.top, name) for name in OUTPUTS}
        if self.config.check_internals:
            handles.update({"internal:" + name: getattr(cocotb.top.g_controller, name) for name in INTERNALS})
        tasks = [cocotb.start_soon(self.activity(name, handle)) for name, handle in handles.items()]
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                observation = Observation({name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)},
                    {name: logic(getattr(cocotb.top.g_controller, name)) for name in INTERNALS} if self.config.check_internals else {},
                    self.active["item"], self.active["stage"])
                self.ap.write(observation)
                observation.item.observation = observation
                self.active["sample"].clear()
        finally:
            for task in tasks:
                task.cancel()
