"""Observe real handshakes and continuously reject unclocked state changes."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor

from mosaic_uvm.logic import logic
from async_fifo.driver import snapshot
from async_fifo.transaction import Activity, Observation


class AsyncFifoMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    async def activity(self, name, domain):
        handle = getattr(cocotb.top, name)
        previous = logic(handle)
        while True:
            await handle.value_change
            allowed = self.active["allowed"][domain]
            await ReadOnly()
            value = logic(handle)
            if value != previous:
                self.ap.write(Activity(name, value, allowed))
                previous = value

    async def run_phase(self):
        await Timer(2, unit="ps")
        await ReadOnly()
        watched = {"o_w_full": "w", "o_w_level": "w", "o_r_empty": "r",
                   "o_r_level": "r", "o_r_data": "r"}
        if self.config.check_internals:
            watched.update({f"{domain}_{kind}": domain for domain in "wr" for kind in ("bin", "gray")})
        tasks = [cocotb.start_soon(self.activity(name, domain)) for name, domain in watched.items()]
        try:
            while True:
                await self.active["sample"].wait()
                await ReadOnly()
                observation = Observation(self.active["before"], snapshot(self.config.check_internals),
                                          self.active["time_ps"], self.active["item"])
                self.ap.write(observation)
                observation.item.observation = observation
                self.active["sample"].clear()
        finally:
            for task in tasks:
                task.cancel()
