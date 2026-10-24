"""Sample actual ports before NBA, after settling, and during held cycles."""
import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from local_switch.transaction import INPUTS, OUTPUTS, Observation


class LocalSwitchMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    def observe(self, stage):
        item = self.active['item']
        observation = Observation({name: logic(getattr(cocotb.top, name))
                                   for name in (*INPUTS, *OUTPUTS)},
                                  {index: logic(handle) for index, handle in self.active['storage'].items()},
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
        if self.active['check_internals']:
            bank = cocotb.top.g_switch
            for n in range(self.active['inputs']):
                node = bank.g_input[n]
                self.active['storage'].update({f'd{n}': node.u_buffer.g_slice.slice_data,
                    f'v{n}': node.u_buffer.g_slice.u_valid.o_q, f'p{n}': node.u_pending.o_q})
            for o in range(len(cocotb.top.o_output_valid)):
                output = bank.g_output[o]
                self.active['storage'].update({f'decode{o}': output.u_source_decode.o_decoded,
                    f'decode_valid{o}': output.u_source_decode.o_select_valid,
                    f'select{o}': output.u_source.i_select,
                    f'mux_inputs{o}': output.u_source.i_data})
        task = cocotb.start_soon(self.edges())
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.observe(self.active['stage'])
                self.active['sample'].clear()
        finally:
            task.cancel()
