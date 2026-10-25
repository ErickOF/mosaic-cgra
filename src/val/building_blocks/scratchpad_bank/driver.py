"""Clock coordinator and explicitly requested verification-only fault injection."""
import cocotb
from cocotb.handle import Force, Release
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from scratchpad_bank.transaction import INPUTS


def disturb(raw, mask, state):
    word = list(raw)
    for bit in range(len(word)):
        if mask >> bit & 1:
            word[-1 - bit] = state or ('0' if word[-1 - bit] == '1' else '1')
    return ''.join(word)


class ScratchpadBankDriver(uvm_driver):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.forced = []

    async def sample(self, stage):
        self.active['stage'] = stage
        self.active['sample'].set()
        await ReadOnly()
        await Timer(1, unit='ps')
        assert not self.active['sample'].is_set()

    async def run_phase(self):
        await Timer(4, unit='ns')
        while True:
            item = await self.seq_item_port.get_next_item()
            self.active['item'] = item
            for handle in self.forced:
                handle.value = Release()
            self.forced = []
            for name in INPUTS:
                getattr(cocotb.top, name).value = item.ports[name]
            core = cocotb.top.g_bank
            if item.fault:
                word, mask, state = item.fault
                handle = core.u_storage.g_shell.u_backend.g_inferred.memory[word]
                handle.value = disturb(str(handle.value).lower(), mask, state)
            if item.protocol:
                for name, value in item.protocol.items():
                    handle = getattr(core, name)
                    handle.value = Force(value)
                    self.forced.append(handle)
            await Timer(2, unit='ns')
            await self.sample('pre')
            if item.edge:
                cocotb.top.i_clk.value = 1
            await Timer(2, unit='ns')
            await self.sample('post')
            await Timer(3, unit='ns')
            await self.sample('held')
            cocotb.top.i_clk.value = 0
            await Timer(3, unit='ns')
            self.seq_item_port.item_done()
