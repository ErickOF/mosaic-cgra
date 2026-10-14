"""PyUVM entry point for the independent combinational SECDED cones."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from ecc.config import EccConfig
from ecc.env import EccEnv
from ecc.sequences import EccSequence


@test(timeout_time=1,timeout_unit='ms')
class EccTest(uvm_test):
    def build_phase(self):
        config=self.config=EccConfig.from_environment()
        for name,width in config.widths.items():
            assert len(getattr(cocotb.top,name))==width,f'Wrong interface width: {name}'
        assert (1 << config.parity_bits)>=config.width+config.parity_bits+1
        if config.check_internals:
            for name,expected in dict(DATA_WIDTH=config.width,HAMMING_PARITY_BITS=config.parity_bits,
                                      HAMMING_WIDTH=config.hamming_width,CODE_WIDTH=config.code_width,POSITION_WIDTH=config.position_width).items():
                assert int(getattr(cocotb.top,name).value)==expected,f'Wrong elaborated width: {name}'
        config.coverage_file.unlink(missing_ok=True)
        ConfigDB().set(self,'env.*','config',config)
        ConfigDB().set(self,'env.*','active',dict(item=None,quiet=set(),sample=Event()))
        self.env=EccEnv('env',self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_encode_data.value=0
        cocotb.top.i_decode_codeword.value=0
        await EccSequence(self.config).start(self.env.sequencer)
        await Timer(1,unit='ps')
        await ReadOnly()
        self.drop_objection()
