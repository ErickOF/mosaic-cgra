"""Public dimensions and deterministic Python campaign settings."""
from dataclasses import dataclass
import os
from pathlib import Path
from sft.defaults import DEFAULTS, PORTS

@dataclass(frozen=True)
class SftConfig:
    parameters: dict
    seed: int
    random_cycles: int
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        p = {n: int(os.getenv('SFT_' + n, str(v)), 0) for n, v in DEFAULTS.items()}
        for name, ports in (('INPUT_ELASTIC_MASK', 'DATA_INPUT_PORTS'),
                            ('OUTPUT_ELASTIC_MASK', 'DATA_OUTPUT_PORTS')):
            p[name] = int(os.getenv('SFT_' + name, str((1 << p[ports]) - 1)), 0)
        return cls(p, int(os.getenv('SFT_SEED', '20261027')),
                   int(os.getenv('SFT_RANDOM_CYCLES', '1000')),
                   Path(os.getenv('SFT_COVERAGE_FILE', str(Path(os.getenv(
                       'COCOTB_RESULTS_FILE', 'build/sft/results.xml')).with_name('coverage.json')))))

    @property
    def DATA_WIDTH(self):
        return self.parameters['SHELL_DATA_WIDTH']

    def __getattr__(self, name):
        if name in self.parameters:
            return self.parameters[name]
        raise AttributeError(name)

    @property
    def aliases(self):
        p = self.parameters
        names = dict(TI='TILE_ID_WIDTH', AV='ARCH_VERSION_WIDTH', CP='CAPABILITY_ID_WIDTH',
            D='SHELL_DATA_WIDTH', M='DATA_METADATA_WIDTH', NI='DATA_INPUT_PORTS', NO='DATA_OUTPUT_PORTS',
            BI='INPUT_BUFFER_DEPTH', BO='OUTPUT_BUFFER_DEPTH', P='PREDICATE_WIDTH',
            PM='PREDICATE_METADATA_WIDTH', PI='PREDICATE_INPUT_PORTS', PO='PREDICATE_OUTPUT_PORTS',
            E='EVENT_WIDTH', EI='EVENT_INPUT_PORTS', EO='EVENT_OUTPUT_PORTS', C='CONTEXT_DEPTH',
            W='CONFIG_DATA_WIDTH', N='CONFIG_WORD_COUNT', Q='CONFIG_QUEUE_DEPTH', O='OWNER_ID_WIDTH',
            K='KERNEL_ID_WIDTH', V='CONTEXT_VERSION_WIDTH', T='RUNTIME_TAG_WIDTH',
            S='STALL_REASON_WIDTH', ER='ERROR_CODE_WIDTH', TR='TRACE_WIDTH')
        a = {n: p[key] for n, key in names.items()}
        return a | dict(CI=max(1, (p['CONTEXT_DEPTH'] - 1).bit_length()),
                        WI=max(1, (p['CONFIG_WORD_COUNT'] - 1).bit_length()),
                        BY=p['CONFIG_DATA_WIDTH'] // 8,
                        IM=p['CONFIG_DATA_WIDTH'] * p['CONFIG_WORD_COUNT'])

    @property
    def widths(self):
        # Expressions come from the versioned public port catalog, not user input.
        return {n: eval(w, {'__builtins__': {}}, self.aliases) for n, (_, w) in PORTS.items()}
