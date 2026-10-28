"""Public geometry and reproducible simulation controls."""
from dataclasses import dataclass
from functools import cached_property
import os
from pathlib import Path
from global_noc.dependencies import profile, aliases, PORTS

@dataclass(frozen=True)
class NocConfig:
    parameters: dict
    seed: int
    random_cycles: int
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        defaults=profile()
        p=profile(**{k:int(os.getenv('GLOBAL_NOC_'+k,str(v)),0) for k,v in defaults.items()})
        result=Path(os.getenv('COCOTB_RESULTS_FILE','build/global_noc/results.xml'))
        return cls(p,int(os.getenv('GLOBAL_NOC_SEED','20261027')),
            int(os.getenv('GLOBAL_NOC_RANDOM_CYCLES','2000')),
            Path(os.getenv('GLOBAL_NOC_COVERAGE_FILE',str(result.with_name('coverage.json')))))

    @cached_property
    def a(self): return aliases(self.parameters)

    @cached_property
    def widths(self):
        return {n:eval(w,{'__builtins__':{}},self.a) for n,(_,w) in PORTS.items()}
