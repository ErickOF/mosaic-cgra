"""Run the decorated PyUVM test and check the actual vector_reduction elaboration."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test

from vector_reduction.config import ReductionConfig
from vector_reduction.env import ReductionEnv
from vector_reduction.sequences import ReductionSequence
from vector_reduction.transaction import INPUTS


@test(timeout_time=1, timeout_unit="ms")
class ReductionTest(uvm_test):
    def build_phase(self):
        c = self.config = ReductionConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f"Wrong port width: {name}"
        if c.check_internals:
            for name, value in c.parameters.items():
                handle = getattr(cocotb.top, name)
                observed = int(handle.value)
                # Some VPI backends expose signed parameters as raw packed bits.
                if value < 0 and observed >= 0:
                    observed -= 1 << len(handle)
                assert observed == value, f"Wrong parameter: {name}"
            assert int(cocotb.top.PACKED_WIDTH.value) == c.count * c.element
            assert int(cocotb.top.SUM_WIDTH.value) == c.sum_width
            assert int(cocotb.top.ACTIVE_COUNT_WIDTH.value) == c.count_width
            for op in range(5):
                assert hasattr(cocotb.top.g_reduction.g_operation[op], "g_enabled") == (
                    op in c.enabled_opcodes
                ), f"Tree removal: {op}"
        if c.hdl_assertions:
            assert hasattr(cocotb.top.g_reduction, "u_assertions"), "HDL checker missing"
        ConfigDB().set(self, "env.*", "config", c)
        ConfigDB().set(
            self,
            "env.*",
            "active",
            {"item": None, "window": "initial", "sample": Event(), "internals": {}},
        )
        self.env = ReductionEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await ReductionSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
