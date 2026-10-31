"""Clock driver with explicit link and protected-state fault injection."""

import cocotb
from cocotb.handle import Force, Release
from cocotb.triggers import Timer
from pyuvm import ConfigDB, uvm_driver


class MeshDriver(uvm_driver):
    def build_phase(self):
        self.active = ConfigDB().get(self, "", "active")
        self.forced = None

    async def run_phase(self):
        while True:
            item = await self.seq_item_port.get_next_item()
            self.active["item"] = item
            d = cocotb.top
            d.i_clk.value = 0
            for n, v in item.ports.items():
                getattr(d, n).value = v
            if item.fault:
                if item.fault[0] == "release":
                    self.forced.value = Release()
                    self.forced = None
                else:
                    path, mask = item.fault
                    target = d
                    for part in path.split("."):
                        if "[" in part:
                            name, index = part[:-1].split("[")
                            target = getattr(target, name)[int(index)]
                        else:
                            target = getattr(target, part)
                    self.forced = target
                    target.value = Force(int(target.value) ^ mask)
            await Timer(4, unit="ns")
            self.active["pre"].set()
            await Timer(1, unit="ns")
            d.i_clk.value = 1
            await Timer(4, unit="ns")
            self.active["post"].set()
            await Timer(1, unit="ns")
            self.seq_item_port.item_done()
