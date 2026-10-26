"""Passive native samples and a generic mesh view for shared cycle checking."""

import cocotb
from cocotb.triggers import ReadOnly
from pyuvm import ConfigDB, uvm_monitor, uvm_analysis_port
from predicate_network.transaction import INPUTS, OUTPUTS, Observation, virtual


class PredicateMonitor(uvm_monitor):
    def build_phase(self):
        self.c = ConfigDB().get(self, "", "config")
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
            # Only inactive unknown value lanes may canonicalize. Mask and active
            # values are still checked by RTL; malformed-input probes are explicit.
            for prefix in ("i_pred_tx", "i_boundary_pred"):
                if p[prefix + "_value"] is None:
                    raw = str(getattr(cocotb.top, prefix + "_value").value)
                    p[prefix + "_value"] = int(raw.replace("X", "0").replace("Z", "0"), 2)
            p = virtual(p, self.c.aliases)
            item = self.active["item"]
            setattr(item, phase, p)
            self.ap.write(Observation(p, phase, item))

    async def run_phase(self):
        task = cocotb.start_soon(self.sample("pre"))
        try:
            await self.sample("post")
        finally:
            task.cancel()
