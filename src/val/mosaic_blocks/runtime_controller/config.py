"""Resolve and verify the exact production configuration used by the simulator."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src/gen/runtime_controller'))
from runtime_controller_contract import DEFAULTS, PORTS, WIDTHS, CODES, pack, unpack, profile


@dataclass(frozen=True)
class RuntimeConfig:
    parameters: dict[str, int]
    seed: int
    random_cycles: int
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        p = profile()
        p = {k: int(os.environ.get(f'RUNTIME_CONTROLLER_{k}', v)) for k, v in p.items()}
        return cls(p, int(os.environ.get('RUNTIME_CONTROLLER_SEED', 20261027)),
                   int(os.environ.get('RUNTIME_CONTROLLER_RANDOM_CYCLES', 1000)),
                   Path(os.environ.get('RUNTIME_CONTROLLER_COVERAGE_FILE',
                        str(Path(os.environ.get('COCOTB_RESULTS_FILE',
                            'build/runtime_controller/results.xml')).with_name('coverage.json')))))

    @property
    def widths(self):
        return {name: eval(width, {'__builtins__': {}}, self.parameters)
                for name, (_, width) in PORTS.items()}

    @property
    def owners(self):
        return [self.parameters['OWNER_ID_TABLE'] >> (o * 16) & 0xffff
                for o in range(self.parameters['MAX_OWNERS'])]
