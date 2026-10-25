"""Run exactly one decorated PyUVM test against the actual elaborated parameters."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test

from predicate_unit.config import PredicateConfig
from predicate_unit.env import PredicateEnv
from predicate_unit.sequences import PredicateSequence
from predicate_unit.transaction import INPUTS


@test(timeout_time=1, timeout_unit="ms")
class PredicateTest(uvm_test):
    def build_phase(self):
        c = self.config = PredicateConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f"Wrong port width: {name}"
        if c.check_internals:
            for name, value in c.parameters.items():
                assert int(getattr(cocotb.top, name).value) == value, (
                    f"Wrong parameter: {name}"
                )
            assert int(cocotb.top.ADDR_WIDTH.value) == c.address_width
        if c.hdl_assertions:
            assert hasattr(cocotb.top.g_predicate, "u_assertions"), (
                "HDL checker missing"
            )
        ConfigDB().set(self, "env.*", "config", c)
        ConfigDB().set(
            self,
            "env.*",
            "active",
            {"item": None, "window": "initial", "sample": Event(), "internals": {}},
        )
        self.env = PredicateEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await PredicateSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
