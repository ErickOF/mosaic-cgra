"""Passive pre-edge handshakes and post-edge status observations."""

import cocotb
from cocotb.triggers import ReadOnly
from pyuvm import ConfigDB, uvm_monitor, uvm_analysis_port
from configuration_network.transaction import Observation


class NetworkMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    async def sample(self, phase):
        while True:
            await self.active[phase].wait()
            await ReadOnly()
            self.active[phase].clear()
            p = {
                n: (int(v) if v.is_resolvable else None)
                for n in self.config.widths
                for v in [getattr(cocotb.top, n).value]
            }
            item = self.active["item"]
            setattr(item, phase, p)
            self.ap.write(Observation(p, phase, item))

    async def run_phase(self):
        task = cocotb.start_soon(self.sample("pre"))
        try:
            await self.sample("post")
        finally:
            task.cancel()
