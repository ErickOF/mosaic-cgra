"""Decorated PyUVM entry point with independent geometry and port checks."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from width_converter.config import WidthConverterConfig
from width_converter.env import WidthConverterEnv
from width_converter.sequences import WidthConverterSequence
from width_converter.transaction import INPUTS


@test(timeout_time=1, timeout_unit='ms')
class WidthConverterTest(uvm_test):
    def build_phase(self):
        c = self.config = WidthConverterConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong interface width: {name}'
        if c.check_internals:
            for name, value in c.parameters.items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong elaborated parameter: {name}'
            for name, value in dict(IN_UNITS=c.in_units, OUT_UNITS=c.out_units,
                    NARROW_WIDTH=min(c.input_width, c.output_width), WIDE_WIDTH=max(c.input_width, c.output_width),
                    RATIO=c.ratio, SLICE_INDEX_WIDTH=max(1, (c.ratio-1).bit_length())).items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong derived parameter: {name}'
            assert len(cocotb.top.g_converter.buffered_data) == max(c.input_width, c.output_width)
            assert len(cocotb.top.g_converter.buffered_keep) == c.wide_units
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, quiet=set(), writable_bits=set(),
            position=0, cancelled=True, sample=Event(), internals={}))
        self.env = WidthConverterEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await WidthConverterSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        await ReadOnly()
        self.drop_objection()
