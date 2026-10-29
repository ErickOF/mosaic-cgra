"""Generated contract and reproducible Python/PyUVM campaign inputs."""
from dataclasses import dataclass
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]

@dataclass(frozen=True)
class SystemConfig:
    artifacts: Path
    manifest: dict
    ports: dict
    seed: int
    random_cycles: int
    coverage_file: Path
    mode: str

    @property
    def parameters(self):
        return self.manifest['descriptor']

    @classmethod
    def from_environment(cls):
        path = Path(os.getenv('SYSTEM_ARTIFACTS', ROOT/'src/gen/system/generated'))
        return cls(path, json.loads((path/'manifest.json').read_text()),
            json.loads((path/'ports.json').read_text()), int(os.getenv('SYSTEM_SEED', '20261029')),
            int(os.getenv('SYSTEM_RANDOM_CYCLES', '1000')),
            Path(os.getenv('SYSTEM_COVERAGE_FILE', ROOT/'build/system_coverage.json')),
            os.getenv('SYSTEM_MODE', 'full'))
