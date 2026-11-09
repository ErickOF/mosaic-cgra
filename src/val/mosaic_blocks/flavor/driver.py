"""Drive public interfaces only; no hierarchical forces or implementation probes."""

import cocotb
from cocotb.triggers import Timer
from pyuvm import uvm_component


class FabricDriver(uvm_component):
    def build_phase(self):
        self.dut = cocotb.top
        self.cycles = 0
        self.physical_peers = []

    async def cycle(self, values=None, sample=()):
        self.dut.i_clk.value = 0
        for name, value in (values or {}).items():
            getattr(self.dut, name).value = value
        for request, acknowledgement in self.physical_peers:
            value = getattr(self.dut, request).value
            getattr(self.dut, acknowledgement).value = int(value) if value.is_resolvable else 0
        await Timer(5, unit="ns")
        observed = {name: int(getattr(self.dut, name).value) for name in sample}
        self.dut.i_clk.value = 1
        await Timer(5, unit="ns")
        self.cycles += 1
        return observed

    async def request(self, prefix, channel, values, expected):
        valid = f"i_{prefix}_{channel}_request_valid"
        ready = f"o_{prefix}_{channel}_request_ready"
        response = f"o_{prefix}_{channel}_response_"
        for _ in range(200):
            observed = await self.cycle(values | {valid: 1}, [ready])
            if observed[ready]:
                break
        else:
            raise AssertionError(f"{prefix}: {channel} request timed out")
        for _ in range(200):
            observed = await self.cycle({valid: 0}, [response + "valid", response + "error_code"] +
                                        [response + key for key in expected])
            if observed[response + "valid"]:
                for key, value in expected.items():
                    assert observed[response + key] == value, (prefix, channel, key, observed)
                return
        raise AssertionError(f"{prefix}: {channel} response timed out")
