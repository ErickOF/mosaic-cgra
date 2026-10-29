"""Production ABI and reproducible simulation configuration."""
from dataclasses import dataclass
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src/gen/cluster_power_manager'))
from cluster_power_manager_contract import DEFAULTS, PORTS, WIDTHS, CODES, pack, unpack, profile


@dataclass(frozen=True)
class PowerConfig:
    parameters: dict[str, int]
    seed: int
    random_cycles: int
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        p = profile()
        p = {k: int(os.getenv('CLUSTER_POWER_MANAGER_' + k, str(v)), 0) for k, v in p.items()}
        results = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/cluster_power_manager/results.xml'))
        return cls(p, int(os.getenv('CLUSTER_POWER_MANAGER_SEED', '20261028')),
                   int(os.getenv('CLUSTER_POWER_MANAGER_RANDOM_CYCLES', '1000')),
                   Path(os.getenv('CLUSTER_POWER_MANAGER_COVERAGE_FILE',
                                  str(results.with_name('coverage.json')))))

    @property
    def widths(self):
        return {n: eval(w, {'__builtins__': {}}, self.parameters) for n, (_, w) in PORTS.items()}
