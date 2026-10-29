"""Production event-collector port dimensions and reproducible Python profiles."""
from dataclasses import dataclass
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'src/gen/cluster'))
from generate import ports


@dataclass(frozen=True)
class EventConfig:
    parameters: dict[str, int]
    ports: dict[str, tuple[str, int]]
    seed: int
    random_cycles: int
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        p = {name: int(os.getenv('CLUSTER_EVENTS_' + name, str(value)), 0)
             for name, value in dict(NUM_TILES=4, EVENT_DEPTH=12, PROTECT_EVENTS=1,
                                     TILE_ID_TABLE=0x03020100).items()}
        results = Path(os.environ.get('COCOTB_RESULTS_FILE', 'build/cluster_events/results.xml'))
        return cls(p, ports('cluster_events', dict(N=p['NUM_TILES'])),
                   int(os.environ.get('CLUSTER_EVENTS_SEED', '20261028')),
                   int(os.environ.get('CLUSTER_EVENTS_RANDOM_CYCLES', '1000')),
                   Path(os.environ.get('CLUSTER_EVENTS_COVERAGE_FILE',
                                       str(results.with_name('coverage.json')))))

    @property
    def widths(self):
        return {name: width for name, (_, width) in self.ports.items()}
