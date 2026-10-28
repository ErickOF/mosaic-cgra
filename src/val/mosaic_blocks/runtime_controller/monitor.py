"""Observe transfers before the edge and settled status after the edge."""
import cocotb
from cocotb.triggers import RisingEdge, ReadOnly
from pyuvm import ConfigDB, uvm_monitor, uvm_analysis_port
from runtime_controller.transaction import INPUTS, OUTPUTS, Observation


def number(handle):
    try:
        return int(handle.value)
    except ValueError:
        return None


class RuntimeMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    async def edges(self):
        while True:
            await RisingEdge(cocotb.top.i_clk)
            item = self.active['item']
            item.pre = {n: number(getattr(cocotb.top, n)) for n in (*INPUTS, *OUTPUTS)}
            self.ap.write(Observation(item.pre, item))

    async def run_phase(self):
        task = cocotb.start_soon(self.edges())
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.active['item'].post = {
                    n: number(getattr(cocotb.top, n)) for n in OUTPUTS}
                self.active['sample'].clear()
        finally:
            task.cancel()
