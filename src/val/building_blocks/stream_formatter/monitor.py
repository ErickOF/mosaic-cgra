"""Observe real pre-NBA edges, settled ports, storage and isolation operands."""
import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from mosaic_uvm.logic import logic
from pyuvm import uvm_analysis_port, uvm_monitor
from stream_formatter.transaction import INPUTS, OUTPUTS, Observation


class StreamFormatterMonitor(uvm_monitor):
    def build_phase(self):
        from pyuvm import ConfigDB
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    def observe(self, stage):
        item = self.active['item']
        obs = Observation({n: logic(getattr(cocotb.top, n)) for n in (*INPUTS, *OUTPUTS)},
                          {n: logic(h) for n, h in self.active['storage'].items()}, item, stage)
        self.ap.write(obs)
        item.observation = obs
        if stage == 'pre':
            item.pre = obs

    async def edges(self):
        while True:
            await RisingEdge(cocotb.top.i_clk)
            self.observe('edge')

    async def run_phase(self):
        await Timer(2, unit='ns')
        if self.active['check_internals']:
            core = cocotb.top.g_formatter
            banks = {'configuration': core.u_configuration}
            if self.active['registered']:
                slice_core = core.g_registered.u_slice.g_slice
                banks['slice_valid'] = slice_core.u_valid
                self.active['storage']['slice_data'] = slice_core.slice_data
                self.active['storage']['slice_enable'] = slice_core.data_enable
                self.active['storage']['slice_input'] = core.g_registered.u_slice.i_data
            for name, bank in banks.items():
                for pin in ('o_q', 'i_d', 'i_enable', 'i_rstb'):
                    self.active['storage'][name + ':' + pin] = getattr(bank, pin)
            for name in ('claims', 'expected_claims', 'detected', 'format_error_events', 'row_index'):
                self.active['storage'][name] = getattr(core, name)
            for pin in ('i_write_enable', 'i_suppress', 'o_write_enable', 'o_write_suppressed'):
                self.active['storage']['gate:' + pin] = getattr(core.u_configuration_write, pin)
        task = cocotb.start_soon(self.edges())
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.observe(self.active['stage'])
                self.active['sample'].clear()
        finally:
            task.cancel()
