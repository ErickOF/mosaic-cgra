"""Retention monitor components for specification-based PyUVM validation."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from retention_register.model import ports
from retention_register.transaction import Activity, Observation


class RetentionMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)
        self.image = getattr(cocotb.top, "retained_image", None) if self.config.check_image else None
        if self.config.check_image:
            assert self.image is not None and len(self.image) == self.config.width, "Portable retained_image is required"

    async def activity(self, signal, handle):
        previous = logic(handle)
        while True:
            await handle.value_change
            allowed = self.active["allowed"]
            await ReadOnly()
            value = logic(handle)
            if value != previous:
                self.ap.write(Activity(signal, value, ports(), allowed))
                previous = value

    async def run_phase(self):
        await Timer(1, unit="ps")
        await ReadOnly()
        tasks = [cocotb.start_soon(self.activity("o_q", cocotb.top.o_q))]
        if self.image is not None:
            tasks.append(cocotb.start_soon(self.activity("retained_image", self.image)))
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                self.ap.write(Observation(self.active["time_ps"], ports(), logic(cocotb.top.o_q),
                                          logic(self.image) if self.image is not None else None,
                                          self.active["item"], self.active["stage"]))
                self.active["sample"].clear()
        finally:
            for task in tasks:
                task.cancel()
