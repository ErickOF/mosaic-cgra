"""Native multi-channel DMA profile campaign with exact evidence validation."""
from datetime import datetime,timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import shlex
import sys
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'lib'))
from mosaic_uvm.regression import (parse_args,require_simulator,run_simulation,passed_test,parameter_guard,
    verification_hashes,license_unavailable,campaign_status,finish_summary)
ROOT=Path(__file__).resolve().parents[4];TEST_DIR=Path(__file__).resolve().parent
sys.path.insert(0,str(TEST_DIR.parent))
from dma_engine.config import DEFAULTS
DEPENDENCIES=(ROOT/'src/rtl/building_blocks/dma_engine_pkg.sv',
    *(ROOT/f'src/rtl/common/{name}.sv' for name in ('dff','counter','operand_isolation','priority_encoder')),
    *(ROOT/f'src/rtl/basic/{name}.sv' for name in ('fifo','parity','round_robin_arbiter')),
    *(ROOT/f'src/rtl/building_blocks/{name}.sv' for name in ('dma_engine_bounds','dma_engine_command_queue')))


def profile(name,**overrides):return name,DEFAULTS|overrides


PROFILES=tuple(profile(f'core_e{e}_c{k}_p{p}_a{a}',NUM_CHANNELS=2,COMMAND_QUEUE_DEPTH=2,DATA_FIFO_DEPTH=2,
    DATA_WIDTH=32,ADDR_WIDTH=8,COUNT_WIDTH=3,NUM_EVENTS=3,NUM_PROTECTION_REGIONS=3,MAX_BURST_BEATS=3,
    TRANSFER_TIMEOUT_CYCLES=128,CANCEL_TIMEOUT_CYCLES=16,SUPPORT_EVENT_START=e,SUPPORT_CANCELLATION=k,PROTECT_COMMAND_FIFO=p,ASYNC_RESET=a)
    for e,k,p,a in product((0,1),repeat=4))+tuple(profile(f'release_n{n}_q{q}_d{dq}_w{d}_a{a}',
    NUM_CHANNELS=n,COMMAND_QUEUE_DEPTH=q,DATA_FIFO_DEPTH=dq,DATA_WIDTH=d,ADDR_WIDTH=w,COUNT_WIDTH=c,
    ASYNC_RESET=a,TRANSFER_TIMEOUT_CYCLES=256,CANCEL_TIMEOUT_CYCLES=16,PROTECT_COMMAND_FIFO=int(n in (2,8)))
    for (n,q,dq,d,w,c),a in product(((1,1,1,32,32,4),(2,2,2,64,40,8),(4,4,8,128,64,16),(8,8,16,256,64,16)),(0,1)))+(
    profile('odd_queues',NUM_CHANNELS=3,COMMAND_QUEUE_DEPTH=3,DATA_FIFO_DEPTH=3,COMPLETION_QUEUE_DEPTH=3,EVENT_QUEUE_DEPTH=3,
        DATA_WIDTH=64,ADDR_WIDTH=32,COUNT_WIDTH=4,NUM_EVENTS=3,NUM_PROTECTION_REGIONS=3,TRANSFER_TIMEOUT_CYCLES=128,CANCEL_TIMEOUT_CYCLES=16),)
INVALID=(
    *((f'{name.lower()}_{label}',{name:value}) for name,(label,value) in product(
        ('NUM_CHANNELS','COMMAND_QUEUE_DEPTH','DATA_FIFO_DEPTH','COMPLETION_QUEUE_DEPTH','EVENT_QUEUE_DEPTH',
         'ADDR_WIDTH','COUNT_WIDTH','SPACE_ID_WIDTH','STREAM_ID_WIDTH','CONTEXT_ID_WIDTH','COMMAND_ID_WIDTH','PRIORITY_WIDTH',
         'NUM_EVENTS','NUM_PROTECTION_REGIONS','MAX_BURST_BEATS','TRANSFER_TIMEOUT_CYCLES','CANCEL_TIMEOUT_CYCLES'),
        (('zero',0),('negative',-1),('x',"32'bx"),('z',"32'bz")))),
    *((f'{name.lower()}_{label}',{name:value}) for name,(label,value) in product(
        ('SUPPORT_EVENT_START','SUPPORT_CANCELLATION','PROTECT_COMMAND_FIFO','ASYNC_RESET'),
        (('two',2),('negative',-1),('x',"32'bx"),('z',"32'bz")))),
    *((f'data_{value}',dict(DATA_WIDTH=value)) for value in (0,7,24,-1)),
    *((f'epoch_{value}',dict(DESCRIPTOR_EPOCH_WIDTH=value)) for value in (0,1,-1)),
    ('mode_one',dict(MODE_WIDTH=1)),('mode_three',dict(MODE_WIDTH=3)),
    ('data_x',dict(DATA_WIDTH="32'bx")),('data_z',dict(DATA_WIDTH="32'bz")),
    ('epoch_x',dict(DESCRIPTOR_EPOCH_WIDTH="32'bx")),('epoch_z',dict(DESCRIPTOR_EPOCH_WIDTH="32'bz")),
    *((f'mode_{label}',dict(MODE_WIDTH=value)) for label,value in
        (('zero',0),('negative',-1),('x',"32'bx"),('z',"32'bz"))),
    *((f'{name.lower()}_storage_overflow',{name:1073741824}) for name in
        ('NUM_CHANNELS','DATA_FIFO_DEPTH','COMPLETION_QUEUE_DEPTH','EVENT_QUEUE_DEPTH','NUM_PROTECTION_REGIONS','COUNT_WIDTH','DATA_WIDTH')),
    *((f'{name.lower()}_derived_overflow',{name:"64'h8000000000000000"}) for name in
        ('MAX_BURST_BEATS','TRANSFER_TIMEOUT_CYCLES','CANCEL_TIMEOUT_CYCLES')),
)


def simulate(args,build,rtl,parameters,seed):
    prefix='-Pdma_engine.' if args.sim=='icarus' else '-pvalue+dma_engine.'
    flags=' '.join(shlex.quote(f'{prefix}{name}={value}') for name,value in parameters.items())
    return run_simulation(args,ROOT,TEST_DIR,'dma_engine','test_dma_engine','DmaEngineTest',build,
        ' '.join(map(str,(*DEPENDENCIES,rtl))),parameters=parameters,compile_args=f'{args.compile_args} {flags}',
        environment={**{f'DMA_ENGINE_{name}':str(value) for name,value in parameters.items()},
            'DMA_ENGINE_SEED':str(seed),'DMA_ENGINE_RANDOM_CYCLES':str(args.random_cycles),'DMA_ENGINE_HDL_ASSERTIONS':'1'})


def main():
    args=parse_args('dma_engine',__doc__,profiles=[name for name,_ in PROFILES],seed=20261020,rtl_category='building_blocks')
    build,rtl=args.build_dir.resolve(),args.rtl.resolve();build.mkdir(parents=True,exist_ok=True)
    output=build/'summary.json';output.unlink(missing_ok=True)
    summary=dict(status='NOT_RUN',framework='PyUVM',simulator=args.sim,profiles=[],parameter_checks=[],
        started_at_utc=datetime.now(timezone.utc).isoformat(),specification='specs/building-blocks/mosaic-dma-engine/README.md',
        scope='selected_profiles' if args.case else 'representative_dma_profiles',
        external_checks=dict.fromkeys(('formal','commercial_lint','cdc','rdc','dft','vc_lp','technology_synthesis',
            'sequential_equivalence','physical_timing','physical_power','real_load_store_backends','mosaic_contracts'),'NOT_RUN'))
    try:
        summary['rtl_sha256']=hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary['dependency_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in DEPENDENCIES}
        summary['verification_sha256']=verification_hashes(TEST_DIR);require_simulator(args)
        for index,(name,p) in enumerate(PROFILES):
            if args.case and name not in args.case:continue
            print(f'Running {name}',flush=True)
            result,log,results,coverage=simulate(args,build/name,rtl,p,args.seed+index)
            row=dict(name=name,status='FAIL',parameters=p,log=str(log))
            try:
                if result.returncode:raise ValueError(f'make exited {result.returncode}')
                passed_test(results,'DmaEngineTest','test_dma_engine');data=json.loads(coverage.read_text())
                if (data['status']!='PASS' or data['parameters']!=p or not data['goals'] or not all(data['goals'].values())
                    or data.get('hdl_handshake_assertions')!='PASS' or data.get('private_byte_assertions')!='PASS'
                    or data['random_transactions']!=args.random_cycles or data['seed']!=args.seed+index):raise ValueError('Coverage evidence mismatch')
                row.update(data,name=name,log=str(log),coverage=str(coverage))
            except (OSError,ValueError,KeyError,ET.ParseError) as error:
                row['error']=str(error)
                if license_unavailable(log.read_text()):row['status']='NOT_RUN'
                print('\n'.join(log.read_text().splitlines()[-25:]),flush=True)
            summary['profiles'].append(row);print(name,row['status'],flush=True)
        summary['parameter_checks']=[parameter_guard(args,build,rtl,'dma_engine',name,p,
            'dma_engine_parameters_must_be_valid',dependencies=DEPENDENCIES) for name,p in INVALID]
        complete=len(summary['profiles'])==(len(set(args.case)) if args.case else len(PROFILES)) and len(summary['parameter_checks'])==len(INVALID)
        summary['status']=campaign_status((*summary['profiles'],*summary['parameter_checks']),complete)
    except (OSError,ValueError) as error:summary['error']=str(error);print(error,file=sys.stderr)
    finally:finish_summary(output,summary,'DMA engine')
    return 0 if summary['status']=='PASS' else 1


if __name__=='__main__':sys.exit(main())
