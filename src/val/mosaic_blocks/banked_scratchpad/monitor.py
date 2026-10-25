"""Observe public transfers and the real controller-to-bank request arbitration."""
import cocotb
from cocotb.triggers import RisingEdge
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from banked_scratchpad.transaction import INPUTS, OUTPUTS, Observation
from banked_scratchpad.model import number


class ScratchpadMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    async def run_phase(self):
        while True:
            await RisingEdge(cocotb.top.i_clk)
            item = self.active['item']
            p = {n: number(getattr(cocotb.top, n).value) for n in (*INPUTS, *OUTPUTS)}
            core = cocotb.top.g_scratchpad
            banks = {n: number(getattr(core, n).value) for n in (
                'statistics', 'outstanding_peaks',
                'dispatch_valid', 'dispatch_ready', 'dispatch_tag',
                'bank_req_valid', 'bank_req_ready', 'bank_req_write', 'bank_req_address',
                'bank_req_size', 'bank_req_data', 'bank_req_strobe', 'bank_req_tag')}
            item.pre = p
            self.ap.write(Observation(p, banks, item))
