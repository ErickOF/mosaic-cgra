"""Explicit DUT parameters, port geometry, and reproducible campaign settings."""
from dataclasses import dataclass
import os
from pathlib import Path
from banked_scratchpad.defaults import DEFAULTS, PORTS


def dimensions(p):
    d, b, c, n, r = (p[k] for k in ('DATA_WIDTH', 'NUM_BANKS', 'NUM_CLIENTS',
        'MAX_OUTSTANDING_PER_CLIENT', 'NUM_REGIONS'))
    y = d // 8
    capacity = b * p['BANK_DEPTH_WORDS'] * y
    a = max(1, (capacity - 1).bit_length())
    names = dict(D=d, B=b, C=c, N=n, R=r, Y=y, A=a,
        BA=max(1, (p['BANK_DEPTH_WORDS'] * y - 1).bit_length()), Z=y.bit_length(),
        LZ=max(1, (y.bit_length() - 1).bit_length()),
        RI=max(1, (r - 1).bit_length()), CI=max(1, (c - 1).bit_length()),
        BI=max(1, (b - 1).bit_length()), SI=max(1, (n - 1).bit_length()),
        CO=n.bit_length(), RO=(c * n).bit_length(),
        BO=max(n, p['BACKEND_READ_LATENCY']).bit_length(),
        O=p['OWNER_ID_WIDTH'], K=p['KERNEL_ID_WIDTH'], G=p['REGION_GENERATION_WIDTH'],
        BG=p['BUFFER_GROUP_WIDTH'], T=p['CLIENT_TAG_WIDTH'], capacity=capacity)
    names['DW'] = sum(w for _, w in descriptor_fields(names))
    return names


def descriptor_fields(a):
    return [('valid', 1), ('base', a['A']), ('limit', a['A'] + 1), ('owner', a['O']),
        ('kernel', a['K']), ('state', 3), ('contents', 1), ('read_mask', a['C']),
        ('write_mask', a['C']), ('generation', a['G']), ('group_id', a['BG']),
        ('role', 2), ('corrected', 1), ('uncorrectable', 1)]


@dataclass(frozen=True)
class ScratchpadConfig:
    parameters: dict
    seed: int
    random_cycles: int
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        def setting(key, default):
            return int(os.getenv('BANKED_SCRATCHPAD_' + key, str(default)), 0)
        results = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/banked_scratchpad/results.xml'))
        return cls({k: setting(k, v) for k, v in DEFAULTS.items()},
            setting('SEED', 20261026), setting('RANDOM_CYCLES', 2000),
            Path(os.getenv('BANKED_SCRATCHPAD_COVERAGE_FILE',
                str(results.with_name('coverage.json')))))

    @property
    def a(self):
        return dimensions(self.parameters)

    @property
    def widths(self):
        return {k: eval(w, {'__builtins__': {}}, self.a) for k, (_, w) in PORTS.items()}

    def __getattr__(self, name):
        return self.parameters[name]
