"""Observe AON handshakes and actual gated-clock pulse widths independently."""
from collections import Counter
import cocotb
from cocotb.triggers import RisingEdge, FallingEdge, ReadOnly
from cocotb.utils import get_sim_time
from pyuvm import ConfigDB, uvm_monitor, uvm_analysis_port
from cluster_power_manager.transaction import INPUTS, OUTPUTS, Observation


def number(handle):
    try:
        return int(handle.value)
    except ValueError:
        return None


class PowerMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.c = ConfigDB().get(self, '', 'config')
        self.ap = uvm_analysis_port('ap', self)
        self.clock_edges = Counter()

    async def clocks(self, handle, name, bit=None):
        previous = None
        high_time = None
        while True:
            await handle.value_change
            value = number(handle)
            value = value if bit is None or value is None else value >> bit & 1
            if value == previous:
                continue
            now = get_sim_time(unit='ns')
            if value == 1:
                self.clock_edges[name] += 1
                high_time = now
            elif value == 0 and high_time is not None:
                assert now - high_time == 5, ('Truncated functional clock high pulse', name, now, high_time)
                high_time = None
            previous = value

    async def edges(self):
        while True:
            await RisingEdge(cocotb.top.i_aon_clk)
            item = self.active['item']
            item.pre = {n: number(getattr(cocotb.top, n)) for n in (*INPUTS, *OUTPUTS)}
            self.ap.write(Observation(item.pre, dict(self.clock_edges)))

    async def run_phase(self):
        tasks = [cocotb.start_soon(self.edges()),
                 cocotb.start_soon(self.clocks(cocotb.top.o_cluster_clk, 'root'))]
        tasks += [cocotb.start_soon(self.clocks(cocotb.top.o_group_clk, f'group{g}', g))
                  for g in range(self.c.parameters['NUM_CLOCK_GROUPS'])]
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.active['item'].post = {
                    n: number(getattr(cocotb.top, n)) for n in OUTPUTS}
                self.active['sample'].clear()
        finally:
            for task in tasks:
                task.cancel()
