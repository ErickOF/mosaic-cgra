"""Sample actual ports before NBA, after settling, and during held cycles."""
import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from exp_unit.transaction import INPUTS, OUTPUTS, Observation


class ExpUnitMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    def observe(self, stage):
        item = self.active['item']
        observation = Observation({name: logic(getattr(cocotb.top, name))
                                   for name in (*INPUTS, *OUTPUTS)},
                                  {index: logic(handle) for index, handle in self.active['storage'].items()},
                                  {name: logic(handle) for name, handle in self.arithmetic.items()},
                                  item, stage)
        self.ap.write(observation)
        item.observation = observation
        if stage == 'pre':
            item.pre = observation

    async def edges(self):
        while True:
            await RisingEdge(cocotb.top.i_clk)
            self.observe('edge')

    async def run_phase(self):
        await Timer(2, unit='ns')
        self.arithmetic = {}
        if self.active['check_internals']:
            self.active['storage'].update({s: cocotb.top.g_unit.g_stage[s].u_slice.stored_data
                                          for s in range(self.active['depth'])})
            bank = cocotb.top.g_unit
            self.arithmetic.update(product_e=bank.product_e, z2=bank.z2, mantissa=bank.mantissa)
            if hasattr(bank, 'g_base_e'):
                self.arithmetic.update(base_e_enable=bank.g_base_e.enabled,
                    base_e_a=bank.g_base_e.u_multiply.g_datapath.isolated_a,
                    base_e_b=bank.g_base_e.u_multiply.g_datapath.isolated_b)
            if hasattr(bank, 'g_interpolation'):
                block = bank.g_interpolation.u_interpolate
                self.arithmetic.update(interpolation_enable=bank.g_interpolation.enabled,
                    interpolation_a=block.u_multiply.g_datapath.isolated_a,
                    interpolation_b=block.u_multiply.g_datapath.isolated_b,
                    interpolation_product=block.full_product, interpolation_sum=block.interpolated)
        task = cocotb.start_soon(self.edges())
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.observe(self.active['stage'])
                self.active['sample'].clear()
        finally:
            task.cancel()
