"""Observe real ports, pre-NBA rising edges, isolation cones and pipeline banks."""
import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from mac.transaction import Activity, INPUTS, OUTPUTS, Observation


class MacMonitor(uvm_monitor):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    def handles(self):
        core = cocotb.top.g_mac.u_core.g_datapath
        term = core.g_term[0].g_active
        handles = {name: getattr(term, name) for name in ('isolated_a', 'isolated_b', 'product')}
        handles.update({name: getattr(core, name) for name in
                        ('work_valid', 'work_illegal', 'work_signed', 'payload')})
        handles.update({name: getattr(core.g_accumulation, name) for name in
                        ('isolated_dot', 'isolated_accumulator')})
        if self.c.latency >= 2:
            handles['storage:product'] = term.g_registered.stored_product
            control = core.g_product_controls
            handles['control:product'] = control.u_control.o_q
            for name in ('work_mask', 'work_signed', 'work_accumulate',
                         'work_saturate', 'work_accumulator'):
                handles['storage:' + name] = getattr(core, name)
        for index in range(self.c.latency - int(self.c.latency >= 2)):
            stage = core.g_response_pipeline.g_stage[index]
            handles[f'control:response:{index}'] = stage.u_control.o_q
            handles[f'storage:response:{index}'] = stage.u_data.o_q
        return handles

    def observe(self, stage):
        item = self.active['item']
        obs = Observation(
            {name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)},
            {name: logic(handle) for name, handle in self.active['internals'].items()}, item, stage)
        self.ap.write(obs)
        item.observation = obs
        if stage == 'pre':
            item.pre = obs

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
            control = name.startswith('control:')
            asynchronous_reset = self.c.asynchronous and logic(cocotb.top.i_rstb) == '0'
            allowed = window in ('initial', 'edge') or control and asynchronous_reset
            if current != previous and not allowed:
                self.ap.write(Activity(name, current))
            previous = current

    async def run_phase(self):
        await Timer(2, unit='ps')
        await ReadOnly()
        if self.c.check_internals:
            self.active['internals'].update(self.handles())
        tasks = [cocotb.start_soon(self.edges())]
        watched = {name: handle for name, handle in self.active['internals'].items()
                   if name.startswith(('storage:', 'control:'))}
        try:
            tasks.extend(cocotb.start_soon(self.watch(name, handle))
                         for name, handle in watched.items())
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.observe(self.active['stage'])
                self.active['sample'].clear()
        finally:
            for task in tasks:
                task.cancel()
