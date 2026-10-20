"""Read DUT ports and continuously observe each destination and storage bit."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor

from mosaic_uvm.logic import logic
from bypass_network.transaction import Activity, INPUTS, OUTPUTS, Observation, unpack


class BypassNetworkMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    async def activity(self, signal):
        handle = getattr(cocotb.top, signal)
        previous = logic(handle)
        while True:
            await handle.value_change
            quiet = self.active["quiet"].get(signal, 0)
            await ReadOnly()
            current = logic(handle)
            if previous != current:
                self.ap.write(Activity(signal, previous, current, quiet))
                previous = current

    async def run_phase(self):
        await Timer(2, unit="ps")
        await ReadOnly()
        watched = (*OUTPUTS, *(("registered_data", "registered_valid") if self.config.check_internals else ()))
        tasks = [cocotb.start_soon(self.activity(name)) for name in watched]
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                ports = {name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)}
                self.ap.write(Observation(
                    ports,
                    unpack(logic(cocotb.top.registered_data), self.config.width) if self.config.check_internals else None,
                    unpack(logic(cocotb.top.registered_valid), 1) if self.config.check_internals else None,
                    self.active["item"], self.active["stage"],
                ))
                self.active["sample"].clear()
        finally:
            for task in tasks:
                task.cancel()
