"""Generated public ABI plus reproducible Python-only campaign configuration."""
from dataclasses import dataclass
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]

@dataclass(frozen=True)
class ClusterConfig:
    manifest: dict
    ports: dict
    seed: int
    random_cycles: int
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        artifacts = Path(os.getenv('CLUSTER_ARTIFACTS', ROOT / 'src/gen/cluster/generated'))
        return cls(json.loads((artifacts / 'manifest.json').read_text()),
            json.loads((artifacts / 'ports.json').read_text()),
            int(os.getenv('CLUSTER_SEED', '20261026')),
            int(os.getenv('CLUSTER_RANDOM_CYCLES', '1000')),
            Path(os.getenv('CLUSTER_COVERAGE_FILE', ROOT / 'build/cluster/coverage.json')))

    @property
    def parameters(self):
        return self.manifest['descriptor']

    @property
    def widths(self):
        return {name: spec[1] for name, spec in self.ports.items()}
