"""Starter PyUVM test for the counter's default parameter configuration."""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge
from pyuvm import test, uvm_test


@test(timeout_time=1, timeout_unit="us")
class CounterTest(uvm_test):
    async def run_phase(self):
        self.raise_objection()
        dut = cocotb.top
        dut.i_clk.value = 0
        dut.i_rstb.value = 0
        dut.i_enable.value = 0
        dut.i_clear.value = 0
        dut.i_load.value = 0
        dut.i_direction.value = 0
        dut.i_load_value.value = 0
        cocotb.start_soon(Clock(dut.i_clk, 10, unit="ns").start())

        async def cycle(count, *, overflow=0, underflow=0, terminal=0, **inputs):
            await FallingEdge(dut.i_clk)
            for name, value in inputs.items():
                getattr(dut, f"i_{name}").value = value
            await RisingEdge(dut.i_clk)
            await ReadOnly()
            for name, expected in {
                "count": count,
                "overflow": overflow,
                "underflow": underflow,
                "terminal": terminal,
            }.items():
                actual = int(getattr(dut, f"o_{name}").value)
                assert actual == expected, f"o_{name}: expected {expected}, got {actual}"

        await cycle(0)  # Synchronous reset.
        await cycle(1, rstb=1, enable=1)
        await cycle(2)
        await cycle(2, enable=0)  # Disabled hold.
        await cycle(1, enable=1, direction=1)

        maximum = (1 << len(dut.o_count)) - 1
        await cycle(maximum, terminal=1, load=1, load_value=maximum, direction=0)
        await cycle(maximum, overflow=1, terminal=1, load=0)  # Saturating up.
        await cycle(maximum, terminal=1, enable=0)  # Overflow pulse clears.

        # Clear wins over load and enable; load above wins over enable.
        await cycle(0, clear=1, load=1, load_value=9, enable=1)
        await cycle(0, underflow=1, terminal=1, clear=0, load=0, direction=1)
        await cycle(0, terminal=1, enable=0)  # Underflow pulse clears.
        await cycle(9, load=1, load_value=9)
        await cycle(0, terminal=1, rstb=0)  # Reset wins over load.
        self.drop_objection()
