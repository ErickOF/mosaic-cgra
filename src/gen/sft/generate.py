"""Publish a reproducible SFT profile, connectivity and numerical ABI description."""
import argparse
import hashlib
import json
from pathlib import Path
from contract import DEFAULTS, FIELDS, connectivity, profile, validate
from sft_sources import SOURCES

ROOT = Path(__file__).resolve().parents[3]


def generate(parameters, output):
    p=validate(parameters)
    operations = {0: 'ENABLE_ALU', 1: 'ENABLE_MULTIPLIER', 2: 'ENABLE_LUT',
        3: 'ENABLE_POLYNOMIAL', 4: 'ENABLE_RECIPROCAL', 5: 'ENABLE_RSQRT',
        6: 'ENABLE_EXPONENTIAL', 7: 'ENABLE_REDUCTION', 8: 'ENABLE_FORMATTER',
        9: 'ENABLE_ACCUMULATOR'}
    inventory = [flag.removeprefix('ENABLE_').lower() for flag in operations.values() if p[flag]]
    result=dict(schema='mosaic-sft-local-v1',parameters=p,fu_inventory=inventory,
        context_fields={k:dict(offset=o,width=w) for k,(o,w) in FIELDS.items()},
        connectivity=connectivity(p),formats={0:'opaque native bits, without conversion',1:'input fixed-point',
            2:'output fixed-point',3:'exact reduction (SUMSQ has twice the input fraction)'},
        bank_policy='selected image in each immutable context; disjoint native physical bank slice',
        issue=dict(slots_per_cycle=1,max_inflight=p['MAX_INFLIGHT'],
            execution='one shared engine; no out-of-order FU overlap',retirement='acceptance order',
            timing='3 engine edges for exact ops; native tagged handshake latency for approximations; queue and backpressure add wait'),
        numerical_models={str(op):[hex(0x53460000 | quality<<8 | op) for quality in range(3)]
            for op, flag in operations.items() if p[flag]},
        numerical_policy='native fixed-point primitives; explicit format conversion only',
        signoff=dict(python_simulation='see regression summary',synthesis='Design Compiler (deferred)',
            lint='NOT_RUN',formal='NOT_RUN',physical='NOT_RUN',power='NOT_RUN'))
    result['rtl_sha256']={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [*(ROOT/f'src/rtl/{name}.sv' for name in SOURCES),
                     ROOT/'src/rtl/mosaic_blocks/sft.sv']}
    result['contract_sha256']=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile',type=int,choices=range(4),default=1)
    parser.add_argument('--output',type=Path,default=Path(__file__).with_name('generated')/'profile.json')
    args=parser.parse_args()
    result=generate(profile(FU_PROFILE=args.profile),args.output)
    print('Generated',args.output,result['contract_sha256'])
