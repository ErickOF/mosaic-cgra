"""Drive independent clock events and legal ready/valid endpoint traffic."""

import cocotb
from cocotb.handle import Deposit, Force, Release
from cocotb.triggers import ReadOnly, Timer
from cocotb.utils import get_sim_time
from pyuvm import ConfigDB, uvm_driver

from mosaic_uvm.logic import logic
from async_fifo.transaction import CHAINS, INPUTS, INTERNALS, OUTPUTS, Snapshot


def snapshot(check_internals: bool) -> Snapshot:
    dut = cocotb.top
    return Snapshot(
        {name: logic(getattr(dut, name)) for name in (*INPUTS, *OUTPUTS)},
        ({name: logic(getattr(dut, name)) for name in INTERNALS}
         | {f"memory[{index}]": logic(word) for index, word in enumerate(dut.memory)})
        if check_internals else {},
        {name: tuple(logic(stage) for stage in getattr(dut, name)) for name in CHAINS}
        if check_internals else {},
    )


class AsyncFifoDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, "", "config")
        self.active = ConfigDB().get(self, "", "active")
        self.forced = None

    def inject(self, fault):
        # Restore the saved digital state before clocks restart. No injected
        # metastability is allowed to reach a functional stage in positive tests.
        if self.forced:
            handle, value = self.forced
            handle.value = Release()
            handle.value = Deposit(value)
            self.forced = None
        if fault:
            name, index, value = fault
            handle = getattr(cocotb.top, name)[index]
            self.forced = handle, handle.value
            handle.value = Force(value * len(handle))

    async def run_phase(self):
        await Timer(3, unit="ps")
        while True:
            item = await self.seq_item_port.get_next_item()
            await Timer(item.delay_ps - 3, unit="ps")
            old = {domain: logic(getattr(cocotb.top, f"i_{domain}_clk")) for domain in "wr"}
            self.active.update(item=item, allowed={domain: False for domain in "wr"})
            for name, value in item.inputs.items():
                if not name.endswith("_clk"):
                    getattr(cocotb.top, name).value = value
            for domain in "wr":
                self.active["allowed"][domain] = str(item.inputs[f"i_{domain}_rstb"]) == "0"
            self.inject(item.fault)
            await Timer(1, unit="ps")
            self.active["before"] = snapshot(self.config.check_internals)
            for domain in "wr":
                value = item.inputs[f"i_{domain}_clk"]
                self.active["allowed"][domain] |= old[domain] == "0" and value == 1
                getattr(cocotb.top, f"i_{domain}_clk").value = value
            await Timer(1, unit="ps")
            self.active["time_ps"] = int(get_sim_time(unit="ps"))
            self.active["sample"].set()
            await ReadOnly()
            await Timer(1, unit="ps")
            assert not self.active["sample"].is_set(), "Monitor missed the clock event"
            self.active["allowed"] = {domain: False for domain in "wr"}
            self.seq_item_port.item_done()
