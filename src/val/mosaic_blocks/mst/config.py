"""Public geometry and reproducible Python simulation configuration."""
from dataclasses import dataclass
import os
from pathlib import Path
from mst.defaults import DEFAULTS, PORTS


def clog(n):
    return max(1, (n - 1).bit_length())


def dimensions(p):
    mapping = dict(A='ADDR_WIDTH', D='SHELL_DATA_WIDTH', MD='MEMORY_DATA_WIDTH',
        NI='NUM_STREAM_INPUTS', NO='NUM_STREAM_OUTPUTS', NL='NUM_LOAD_CHANNELS',
        NS='NUM_STORE_CHANNELS', NM='NUM_SCRATCHPAD_CLIENTS', NDI='NUM_DMA_INGRESS_CHANNELS',
        NDO='NUM_DMA_EGRESS_CHANNELS', C='COUNT_WIDTH', NC='CONTEXT_DEPTH', N='CONFIG_WORD_COUNT',
        W='CONFIG_DATA_WIDTH', Q='COMMAND_QUEUE_DEPTH', NR='NUM_PROTECTION_REGIONS',
        NB='NUM_BUFFER_ROLES', NE='NUM_EVENTS', RI='REGION_ID_WIDTH', BU='BUFFER_ID_WIDTH',
        O='OWNER_ID_WIDTH', K='KERNEL_ID_WIDTH', PK='PACKAGE_ID_WIDTH', V='CONTEXT_VERSION_WIDTH',
        J='COMMAND_ID_WIDTH', DG='DESCRIPTOR_GENERATION_WIDTH', AL='ALLOCATION_GENERATION_WIDTH',
        EP='EXECUTION_EPOCH_WIDTH', SP='SPACE_ID_WIDTH', ST='STREAM_ID_WIDTH', DT='DATATYPE_WIDTH',
        PR='PRIORITY_WIDTH', M='DATA_METADATA_WIDTH', E='EVENT_WIDTH', TI='TILE_ID_WIDTH',
        AV='ARCH_VERSION_WIDTH', CP='CAPABILITY_ID_WIDTH', BI='INPUT_BUFFER_DEPTH',
        BO='OUTPUT_BUFFER_DEPTH', P='PREDICATE_WIDTH', PM='PREDICATE_METADATA_WIDTH',
        PI='PREDICATE_INPUT_PORTS', PO='PREDICATE_OUTPUT_PORTS', INE='EVENT_INPUT_PORTS',
        EO='EVENT_OUTPUT_PORTS', T='RUNTIME_TAG_WIDTH', S='STALL_REASON_WIDTH',
        ER='ERROR_CODE_WIDTH', TR='TRACE_WIDTH')
    a = {k: p[v] for k, v in mapping.items()}
    a.update(ED=max(a['D'], a['MD']), H=a['NL'] + a['NS'], SG=64)
    a.update(SY=a['D'] // 8, MY=a['MD'] // 8, EY=a['ED'] // 8)
    a.update(HCI=clog(a['H']), LCI=clog(a['NL']), SCI=clog(a['NS']),
        CH=clog(max(a[k] for k in ('NI', 'NO', 'NM', 'NDI', 'NDO'))),
        CI=clog(a['NC']), WI=clog(a['N']), BY=a['W'] // 8, IM=a['W'] * a['N'],
        OC=clog(a['Q'] + 1), EI=clog(a['NE']), TW=clog(p['TRANSFER_TIMEOUT_CYCLES'] + 1),
        CT=clog(p['CANCEL_TIMEOUT_CYCLES'] + 1), LOG=(a['EY'] - 1).bit_length(),
        SI=clog(max(p['MAX_OUTSTANDING_READS'], p['MAX_OUTSTANDING_WRITES'])),
        FI=clog(a['EY'] + 1), MBW=clog(a['MY'] + 1))
    a.update(SZ=clog(a['LOG'] + 1), MSZ=clog((a['MY'] - 1).bit_length() + 1),
        BC=2 * a['C'] + a['LOG'] + 2, AT=a['EP'] + a['SG'] + a['SI'] + a['FI'])
    a['MT'] = a['HCI'] + a['AT']
    from mst.layout import FIELDS
    for n, alias in dict(identity='IDW', mode='MOW', endpoint='ENW', format='FOW',
        events='EVW', control='CTW', region='RGW', buffer='BUW').items():
        a[alias] = sum(eval(w, {'__builtins__': {}}, a) for _, w in FIELDS[n])
    a['DESC'] = a['IDW'] + a['MOW'] + 2 * a['ENW'] + a['FOW'] + a['EVW'] + a['CTW']
    return a


@dataclass(frozen=True)
class MstConfig:
    parameters: dict
    seed: int
    random_cycles: int
    coverage_file: Path

    @classmethod
    def from_environment(cls):
        p = {n: int(os.getenv('MST_' + n, str(v)), 0) for n, v in DEFAULTS.items()}
        for n, k in (('INPUT_ELASTIC_MASK', 'NUM_STREAM_INPUTS'),
                     ('OUTPUT_ELASTIC_MASK', 'NUM_STREAM_OUTPUTS')):
            p[n] = int(os.getenv('MST_' + n, str((1 << p[k]) - 1)), 0)
        return cls(p, int(os.getenv('MST_SEED', '20261025')),
            int(os.getenv('MST_RANDOM_CYCLES', '20')), Path(os.getenv('MST_COVERAGE_FILE',
            str(Path(os.getenv('COCOTB_RESULTS_FILE', 'build/mst/results.xml'))
                .with_name('coverage.json')))))

    def __getattr__(self, name):
        aliases = dict(DATA_WIDTH='SHELL_DATA_WIDTH', DATA_INPUT_PORTS='NUM_STREAM_INPUTS',
                       DATA_OUTPUT_PORTS='NUM_STREAM_OUTPUTS')
        return self.parameters[aliases.get(name, name)]

    @property
    def aliases(self):
        return dimensions(self.parameters)

    @property
    def widths(self):
        return {n: eval(w, {'__builtins__': {}}, self.aliases) for n, (_, w) in PORTS.items()}
