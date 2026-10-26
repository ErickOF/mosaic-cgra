"""Passive public-port sampler, coordinated before and after each clock edge."""

import cocotb
from cocotb.triggers import ReadOnly
from pyuvm import ConfigDB, uvm_monitor, uvm_analysis_port
from static_mesh.transaction import INPUTS, OUTPUTS, Observation


class MeshMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")
        self.ap = uvm_analysis_port("ap", self)

    async def sample(self, phase):
        while True:
            await self.active[phase].wait()
            await ReadOnly()
            self.active[phase].clear()
            p = {}
            for n in (*INPUTS, *OUTPUTS):
                value = getattr(cocotb.top, n).value
                p[n] = int(value) if value.is_resolvable else None
            item = self.active["item"]
            setattr(item, phase, p)
            self.ap.write(Observation(p, phase, item))

    async def run_phase(self):
        task = cocotb.start_soon(self.sample("pre"))
        try:
            await self.sample("post")
        finally:
            task.cancel()
