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
    inventory=['lut','scalar_alu','exact_reduction','sumsq_multiplier','accumulator']
    if p['FU_PROFILE']>=1:inventory+=['polynomial','scalar_multiplier']
    if p['FU_PROFILE']>=2:inventory+=['reciprocal','rsqrt']
    if p['FU_PROFILE']==3:inventory+=['exp_e','exp2']
    result=dict(schema='mosaic-sft-local-v1',parameters=p,fu_inventory=inventory,
        context_fields={k:dict(offset=o,width=w) for k,(o,w) in FIELDS.items()},
        connectivity=connectivity(p),formats={0:'opaque native bits, without conversion',1:'input fixed-point',
            2:'output fixed-point',3:'exact reduction (SUMSQ has twice the input fraction)'},
        bank_policy='selected image in each immutable context; disjoint native physical bank slice',
        issue=dict(slots_per_cycle=1,max_inflight=p['MAX_INFLIGHT'],
            execution='one shared engine; no out-of-order FU overlap',retirement='acceptance order',
            timing='3 engine edges for exact ops; native tagged handshake latency for approximations; queue and backpressure add wait'),
        numerical_models={str(op):[hex(0x53460000 | quality<<8 | op) for quality in range(3)]
            for op in [0,2,7,8,9]+([1,3] if p['FU_PROFILE'] else [])+
                ([4,5] if p['FU_PROFILE']>=2 else [])+([6] if p['FU_PROFILE']==3 else [])},
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
