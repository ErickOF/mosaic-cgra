"""Expected SRAM geometry, backend identity and deterministic campaign settings."""
from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps

LONG_STALL = 32
STREAM_LENGTH = 32


@dataclass(frozen=True)
class SramConfig:
    width: int
    depth: int
    granule: int
    tag_width: int
    latency: int
    credits: int
    asynchronous: bool
    backend: str
    seed: int
    random_cycles: int
    check_internals: bool
    probe: str
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        def setting(name, default): return int(os.getenv('SRAM_WRAPPER_'+name, str(default)), 0)
        asynchronous, internal = setting('ASYNC_RESET', 0), setting('CHECK_INTERNALS', 1)
        assert asynchronous in (0, 1) and internal in (0, 1)
        report = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/sram_wrapper/results.xml')).with_name('coverage.json')
        c = cls(*(setting(name, default) for name, default in (('DATA_WIDTH', 32), ('DEPTH', 1024),
            ('MASK_GRANULARITY', 8), ('TAG_WIDTH', 4), ('READ_LATENCY', 1), ('MAX_OUTSTANDING_READS', 4))),
            bool(asynchronous), os.getenv('SRAM_WRAPPER_BACKEND', 'inferred'), setting('SEED', 20261019),
            setting('RANDOM_CYCLES', 2000), bool(internal), os.getenv('SRAM_WRAPPER_ASSERTION_PROBE', ''),
            Path(os.getenv('SRAM_WRAPPER_COVERAGE_FILE', str(report))))
        assert min(c.width,c.depth,c.granule,c.tag_width,c.latency) >= 1 and c.width % c.granule == 0
        assert c.credits >= c.latency and c.random_cycles >= 1000 and c.backend in ('inferred', 'reference')
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use zero-delay RTL checks'
        assert get_time_from_sim_steps(1, unit='ps') <= 1, 'Use 1 ps precision or finer'
        return c

    @property
    def parameters(self):
        return dict(DATA_WIDTH=self.width, DEPTH=self.depth, MASK_GRANULARITY=self.granule,
            TAG_WIDTH=self.tag_width, READ_LATENCY=self.latency, MAX_OUTSTANDING_READS=self.credits,
            ASYNC_RESET=int(self.asynchronous))

    @property
    def address_width(self): return max(1, (self.depth-1).bit_length())
    @property
    def mask_width(self): return self.width//self.granule
    @property
    def count_width(self): return self.credits.bit_length()
    @property
    def widths(self):
        from sram_wrapper.transaction import INPUTS, OUTPUTS
        return dict(dict.fromkeys((*INPUTS, *OUTPUTS),1), i_req_addr=self.address_width,
            i_req_wdata=self.width, i_req_wmask=self.mask_width, i_req_tag=self.tag_width,
            o_rsp_rdata=self.width, o_rsp_tag=self.tag_width, o_outstanding_reads=self.count_width)
