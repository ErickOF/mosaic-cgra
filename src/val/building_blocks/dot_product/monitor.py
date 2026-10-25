"""Passive port sampling, pre-NBA edges and continuous pipeline-storage watches."""
import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from dot_product.transaction import Activity, INPUTS, OUTPUTS, Observation


class DotProductMonitor(uvm_monitor):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    def handles(self):
        bank = cocotb.top.g_datapath
        handles = {}
        for index in range(self.c.terms):
            term = bank.g_term[index].g_active
            for name in ('isolated_a', 'isolated_b', 'product'):
                handles[f'term:{index}:{name}'] = getattr(term, name)
            if self.c.latency >= 2:
                handles[f'storage:product:{index}'] = term.g_registered.stored_product
        if self.c.latency >= 2:
            for name in ('work_mask', 'work_signed', 'work_accumulate', 'work_saturate'):
                handles['storage:' + name] = getattr(bank, name)
            if self.c.accumulate:
                handles['storage:work_accumulator'] = bank.work_accumulator
        for index in range(self.c.latency - int(self.c.latency >= 2)):
            stage = bank.g_response_pipeline.g_stage[index]
            handles[f'storage:response:{index}'] = stage.u_data.o_q
        if self.c.accumulate:
            for name in ('isolated_dot', 'isolated_accumulator'):
                handles[name] = getattr(bank.g_accumulation, name)
        return handles

    def observe(self, stage):
        item = self.active['item']
        observation = Observation(
            {name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)},
            {name: logic(handle) for name, handle in self.active['internals'].items()},
            item, stage)
        self.ap.write(observation)
        item.observation = observation
        if stage == 'pre':
            item.pre = observation

    async def edges(self):
        while True:
            await RisingEdge(cocotb.top.i_clk)
            self.observe('edge')

    async def watch(self, name, handle):
        previous = logic(handle)
        while True:
            await handle.value_change
            await ReadOnly()
            current = logic(handle)
            window = self.active['window']
            storage = name.startswith('storage:')
            asynchronous_reset = self.c.asynchronous and logic(cocotb.top.i_rstb) == '0'
            forbidden = storage and window != 'edge' or window == 'hold'
            forbidden |= not storage and window == 'inputs' and not asynchronous_reset
            if current != previous and forbidden:
                self.ap.write(Activity(name, current))
            previous = current

    async def run_phase(self):
        await Timer(2, unit='ps')
        await ReadOnly()
        if self.c.check_internals:
            self.active['internals'].update(self.handles())
        tasks = [cocotb.start_soon(self.edges())]
        watched = {name: handle for name, handle in self.active['internals'].items()
                   if name.startswith('storage:')}
        if self.c.latency:
            watched.update({name: getattr(cocotb.top, name) for name in OUTPUTS})
        tasks.extend(cocotb.start_soon(self.watch(name, handle)) for name, handle in watched.items())
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.observe(self.active['stage'])
                self.active['sample'].clear()
        finally:
            for task in tasks:
                task.cancel()
