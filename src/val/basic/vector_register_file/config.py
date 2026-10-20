"""Expected vector geometry and reproducible four-state storage campaigns."""

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps


@dataclass(frozen=True)
class VectorRegisterFileConfig:
    lane_width: int
    lanes: int
    slice_width: int
    depth: int
    read_ports: int
    write_ports: int
    broadcast: bool
    seed: int
    random_cycles: int
    check_internals: bool
    probe: str
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('VECTOR_REGISTER_FILE_' + name, str(default)), 0)
        internal, broadcast = setting('CHECK_INTERNALS', 1), setting('HAS_BROADCAST', 1)
        assert internal in (0, 1) and broadcast in (0, 1)
        report = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/vector_register_file/results.xml')).with_name('coverage.json')
        config = cls(setting('LANE_WIDTH', 32), setting('NUM_LANES', 4), setting('WRITE_SLICE_WIDTH', 8),
            setting('DEPTH', 16), setting('NUM_READ_PORTS', 2), setting('NUM_WRITE_PORTS', 1), bool(broadcast),
            setting('SEED', 20261020), setting('RANDOM_CYCLES', 2000), bool(internal),
            os.getenv('VECTOR_REGISTER_FILE_ASSERTION_PROBE', ''),
            Path(os.getenv('VECTOR_REGISTER_FILE_COVERAGE_FILE', str(report))))
        assert min(config.lane_width, config.lanes, config.slice_width, config.depth, config.read_ports, config.write_ports) >= 1
        assert config.lane_width % config.slice_width == 0 and config.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use TEST_SETTLE_NS=0 for RTL checks'
        assert get_time_from_sim_steps(1, unit='ps') <= 1, 'Use 1 ps precision or finer'
        return config

    @property
    def slices_per_lane(self):
        return self.lane_width // self.slice_width

    @property
    def mask_width(self):
        return self.lanes*self.slices_per_lane

    @property
    def width(self):
        return self.lanes*self.lane_width

    @property
    def address_width(self):
        return max(1, (self.depth-1).bit_length())

    @property
    def parameters(self):
        return dict(LANE_WIDTH=self.lane_width, NUM_LANES=self.lanes, WRITE_SLICE_WIDTH=self.slice_width,
            DEPTH=self.depth, NUM_READ_PORTS=self.read_ports, NUM_WRITE_PORTS=self.write_ports,
            HAS_BROADCAST=int(self.broadcast))

    @property
    def derived(self):
        return dict(VECTOR_WIDTH=self.width, SLICES_PER_LANE=self.slices_per_lane, MASK_WIDTH=self.mask_width,
            ADDR_WIDTH=self.address_width, READ_ADDR_WIDTH=self.read_ports*self.address_width,
            WRITE_ADDR_WIDTH=self.write_ports*self.address_width, READ_DATA_WIDTH=self.read_ports*self.width,
            WRITE_DATA_WIDTH=self.write_ports*self.width, READ_LANE_ENABLE_WIDTH=self.read_ports*self.lanes,
            WRITE_MASK_WIDTH=self.write_ports*self.mask_width)

    @property
    def widths(self):
        return dict(i_read_enable=self.read_ports, i_read_lane_enable=self.read_ports*self.lanes,
            i_read_address=self.read_ports*self.address_width, o_read_data=self.read_ports*self.width,
            i_write_enable=self.write_ports, i_write_mask=self.write_ports*self.mask_width,
            i_write_broadcast=self.write_ports, i_write_address=self.write_ports*self.address_width,
            i_write_data=self.write_ports*self.width)
