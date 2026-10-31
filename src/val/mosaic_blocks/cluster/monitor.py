"""Passive sampling uses public signals; no functional hierarchy accesses."""
import cocotb
from cocotb.triggers import ReadOnly
from pyuvm import ConfigDB, uvm_monitor, uvm_analysis_port
from cluster.transaction import Observation

class ClusterMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.config = ConfigDB().get(self, '', 'config')
        self.ap = uvm_analysis_port('ap', self)

    async def sample(self, phase):
        while True:
            await self.active[phase].wait()
            await ReadOnly()
            self.active[phase].clear()
            p = {}
            for name in self.config.ports:
                value = getattr(cocotb.top, name).value
                p[name] = int(value) if value.is_resolvable else None
            item = self.active['item']
            setattr(item, phase, p)
            self.ap.write(Observation(p, phase, item))

    async def run_phase(self):
        pre = cocotb.start_soon(self.sample('pre'))
        try:
            await self.sample('post')
        finally:
            pre.cancel()
