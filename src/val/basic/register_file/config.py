"""Expected geometry and reproducible, four-state RTL campaign settings."""

from dataclasses import dataclass
from decimal import Decimal
import os
from pathlib import Path
from cocotb.utils import get_time_from_sim_steps


@dataclass(frozen=True)
class RegisterFileConfig:
    width: int
    depth: int
    read_ports: int
    write_ports: int
    seed: int
    random_cycles: int
    check_internals: bool
    probe: str
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('REGISTER_FILE_' + name, str(default)), 0)
        internal = setting('CHECK_INTERNALS', 1)
        assert internal in (0, 1)
        report = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/register_file/results.xml')).with_name('coverage.json')
        config = cls(setting('DATA_WIDTH', 32), setting('DEPTH', 32), setting('NUM_READ_PORTS', 2),
            setting('NUM_WRITE_PORTS', 1), setting('SEED', 20261019), setting('RANDOM_CYCLES', 2000),
            bool(internal), os.getenv('REGISTER_FILE_ASSERTION_PROBE', ''),
            Path(os.getenv('REGISTER_FILE_COVERAGE_FILE', str(report))))
        assert min(config.width, config.depth, config.read_ports, config.write_ports) >= 1
        assert config.random_cycles >= 1000
        assert Decimal(os.getenv('TEST_SETTLE_NS', '0')) == 0, 'Use TEST_SETTLE_NS=0 for zero-delay RTL checks'
        assert get_time_from_sim_steps(1, unit='ps') <= 1, 'Use 1 ps precision or finer'
        return config

    @property
    def address_width(self):
        return max(1, (self.depth - 1).bit_length())

    @property
    def parameters(self):
        return dict(DATA_WIDTH=self.width, DEPTH=self.depth,
            NUM_READ_PORTS=self.read_ports, NUM_WRITE_PORTS=self.write_ports)

    @property
    def widths(self):
        return dict(i_read_enable=self.read_ports, i_read_address=self.read_ports*self.address_width,
            o_read_data=self.read_ports*self.width, i_write_enable=self.write_ports,
            i_write_address=self.write_ports*self.address_width, i_write_data=self.write_ports*self.width)
