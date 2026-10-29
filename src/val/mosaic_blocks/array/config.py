"""Immutable generated ABI and reproducible Python-only simulation settings."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]

@dataclass(frozen=True)
class ArrayConfig:
    artifacts: Path
    manifest: dict
    ports: dict
    seed: int
    random_cycles: int
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        a = Path(os.getenv('ARRAY_ARTIFACTS', ROOT/'src/gen/array/generated'))
        return cls(a, json.loads((a/'manifest.json').read_text()),
            json.loads((a/'ports.json').read_text()), int(os.getenv('ARRAY_SEED', '20261028')),
            int(os.getenv('ARRAY_RANDOM_CYCLES', '1000')),
            Path(os.getenv('ARRAY_COVERAGE_FILE', ROOT/'build/array/coverage.json')))

    @property
    def parameters(self): return self.manifest['descriptor']
