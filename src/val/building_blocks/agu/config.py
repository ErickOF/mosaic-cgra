"""Expected geometry, four-state precision, and reproducible campaign settings."""

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps
from agu.transaction import INPUTS, OUTPUTS


@dataclass(frozen=True)
class AguConfig:
    width: int
    count: int
    max_element: int
    space: int
    channel: int
    context: int
    asynchronous: bool
    check_internals: bool
    hdl_assertions: bool
    seed: int
    random_cycles: int
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('AGU_'+name, str(default)), 0)
        flags = [setting(name, default) for name,default in
            (('ASYNC_RESET',0), ('CHECK_INTERNALS',1), ('HDL_ASSERTIONS',1))]
        assert set(flags) <= {0,1}
        report = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/agu/results.xml')).with_name('coverage.json')
        c = cls(*(setting(name, default) for name,default in (
            ('ADDR_WIDTH',32), ('COUNT_WIDTH',16), ('MAX_ELEMENT_BYTES',16),
            ('SPACE_ID_WIDTH',2), ('CHANNEL_ID_WIDTH',4), ('CONTEXT_ID_WIDTH',8))),
            *map(bool,flags), setting('SEED',20261020), setting('RANDOM_CYCLES',2000),
            Path(os.getenv('AGU_COVERAGE_FILE',str(report))))
        assert c.width >= 1 and c.count >= 1 and c.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS','0')) == 0, 'Use TEST_SETTLE_NS=0 for RTL checks'
        assert get_time_from_sim_steps(1,unit='ps') <= 1
        return c

    @property
    def max_log2(self):
        return self.max_element.bit_length()-1

    @property
    def size_width(self):
        return max(1,self.max_log2.bit_length())

    @property
    def mask(self):
        return (1 << self.width)-1

    @property
    def count_max(self):
        return (1 << self.count)-1

    @property
    def parameters(self):
        return dict(ADDR_WIDTH=self.width, COUNT_WIDTH=self.count, MAX_ELEMENT_BYTES=self.max_element,
            SPACE_ID_WIDTH=self.space, CHANNEL_ID_WIDTH=self.channel, CONTEXT_ID_WIDTH=self.context,
            ASYNC_RESET=int(self.asynchronous), MODE_WIDTH=2)

    @property
    def widths(self):
        widths = dict.fromkeys((*INPUTS,*OUTPUTS),1)
        widths.update(i_mode=2, o_error_code=4, o_addresses_accepted=2*self.count)
        for prefix in ('i_','o_'):
            widths.update({prefix+name:size for name,size in (('element_size_log2',self.size_width),
                ('address_space',self.space), ('channel_id',self.channel), ('context_id',self.context))})
        widths.update({name:self.width for name in ('i_base_address','i_inner_stride','i_outer_stride','o_address')})
        widths.update({name:self.count for name in ('i_inner_count','i_outer_count','o_inner_index','o_outer_index')})
        return widths
