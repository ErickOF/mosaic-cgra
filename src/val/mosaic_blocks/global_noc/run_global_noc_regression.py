"""Python-only global NoC topology/flow/protection integration campaign."""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shlex
import sys
import unittest
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'lib'))
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from global_noc.dependencies import SOURCES, profile
from global_noc.test_model import ModelTests
from global_noc.compatibility import run_compatibility
from generate import generate
from mosaic_uvm.regression import (parse_args,run_simulation,passed_test,parameter_guard,
    require_simulator,verification_hashes,campaign_status,finish_summary,license_unavailable)
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
DEPENDENCIES=tuple(ROOT/f'src/rtl/{n}.sv' for n in SOURCES)


def case(name,**changes):return name,profile(DRAIN_TIMEOUT_CYCLES=96,**changes)

PROFILES=(case('balanced'),case('single',NOC_X=1,NOC_Y=1),
    case('lite_one',NOC_PROFILE=0,NUM_VCS=1,FLOW_CONTROL=0,ENABLE_QOS=0),
    case('lite_two_yx',NOC_PROFILE=0,NUM_VCS=2,FLOW_CONTROL=0,ENABLE_QOS=0,
        ROUTING_ALGORITHM=1,TRAFFIC_CLASS_TO_VC=0xAA,
        LINK_PIPELINE_STAGES=1,INPUT_VC_DEPTH=2,ENDPOINT_RX_VC_DEPTH=2),
    case('ready_yx',NOC_PROFILE=0,NUM_VCS=2,ENABLE_QOS=0,FLOW_CONTROL=0,ROUTING_ALGORITHM=1,FLIT_DATA_WIDTH=64,
        ENDPOINT_DATA_WIDTH=192,INPUT_VC_DEPTH=2,ENDPOINT_RX_VC_DEPTH=2),
    case('credit_pipelines',LINK_PIPELINE_STAGES=2,CREDIT_RETURN_PIPELINE_STAGES=4,
        FLIT_DATA_WIDTH=64,ENDPOINT_DATA_WIDTH=256,ROUTING_ALGORITHM=1),
    case('protected',NOC_PROFILE=2,ENABLE_LINK_PARITY=1,BUFFER_PROTECTION=2,
        ENDPOINT_DATA_WIDTH=64),
    case('rectangle',NOC_X=3,NOC_Y=2,FLIT_DATA_WIDTH=128,ENDPOINT_DATA_WIDTH=128),
    case('four_by_four',NOC_X=4,NOC_Y=4,FLIT_DATA_WIDTH=32,ENDPOINT_DATA_WIDTH=64),
    case('shallow',INPUT_VC_DEPTH=1,ENDPOINT_RX_VC_DEPTH=1,ENDPOINT_TX_QUEUE_DEPTH=1,
        ENDPOINT_RX_QUEUE_DEPTH=1,FLIT_DATA_WIDTH=32,ENDPOINT_DATA_WIDTH=32),
    case('deep_parity',FLIT_DATA_WIDTH=64,INPUT_VC_DEPTH=8,ENDPOINT_RX_VC_DEPTH=8,ENDPOINT_TX_QUEUE_DEPTH=4,
        ENDPOINT_RX_QUEUE_DEPTH=4,BUFFER_PROTECTION=0,ENABLE_LINK_PARITY=1),
    case('buffer_parity',BUFFER_PROTECTION=1,ENDPOINT_DATA_WIDTH=64),
    case('tight_packet',NOC_X=1,NOC_Y=1,INPUT_VC_DEPTH=2,ENDPOINT_RX_VC_DEPTH=2,
        ENDPOINT_DATA_WIDTH=64,ENDPOINT_RX_QUEUE_DEPTH=1),
    case('odd_width',ENDPOINT_DATA_WIDTH=40),
    case('counters_off',ENABLE_COUNTERS=0),
)
POSITIVE=('NOC_X','NOC_Y','NUM_VCS','INPUT_VC_DEPTH','MAX_ACTIVE_FLOWS','MAX_PACKET_FLITS',
    'ENDPOINT_TX_QUEUE_DEPTH','ENDPOINT_RX_VC_DEPTH','ENDPOINT_RX_QUEUE_DEPTH')
INVALID=tuple((f'{k}_{label}',{k:v}) for k in POSITIVE
    for label,v in (('zero',0),('negative',-1),('x',"32'bx"),('z',"32'bz")))+(
    ('endpoint_count',dict(NUM_ENDPOINTS=3)),('router_count',dict(NUM_ROUTERS=5)),
    ('profile',dict(NOC_PROFILE=3)),('profile_x',dict(NOC_PROFILE="32'bx")),
    ('protected_missing',dict(NOC_PROFILE=2)),('balanced_vcs',dict(NUM_VCS=2)),
    ('lite_dependency',dict(NOC_PROFILE=0)),('depth_mismatch',dict(ENDPOINT_RX_VC_DEPTH=2)),
    ('asynchronous_endpoint',dict(ASYNC_ENDPOINT_MASK=1)),('asynchronous_reset',dict(ASYNC_RESET=1)),
    ('control_protection',dict(CONTROL_PROTECTION=1)),('segmentation',dict(MAX_PACKET_FLITS=2)),
    ('fragment_width',dict(FRAGMENT_INDEX_WIDTH=1)),('unaligned_flit',dict(FLIT_DATA_WIDTH=31)),
    ('unaligned_beat',dict(ENDPOINT_DATA_WIDTH=127)),('flow_control',dict(FLOW_CONTROL=2)),
    ('route',dict(ROUTING_ALGORITHM=2)),('stages',dict(LINK_PIPELINE_STAGES=5)),
    ('credit_stages',dict(CREDIT_RETURN_PIPELINE_STAGES=-1)),('trace',dict(ENABLE_TRACE=1)),
    ('metadata_width',dict(USER_METADATA_WIDTH=32)),('class_map',dict(TRAFFIC_CLASS_TO_VC=0)),
    ('service_map',dict(TRAFFIC_CLASS_TO_SERVICE=0)),('output_pipeline',dict(ROUTER_OUTPUT_PIPELINE=0)),
    ('partial_packet_capacity',dict(INPUT_VC_DEPTH=2,ENDPOINT_RX_VC_DEPTH=2)),
    ('balanced_ready',dict(FLOW_CONTROL=0)),
    ('timeout_overflow',dict(DRAIN_TIMEOUT_CYCLES="64'd4294967296")),
    ('class_count',dict(NUM_TRAFFIC_CLASSES=9)),
    ('critical_tx_channel',dict(NUM_TX_CHANNELS_PER_ENDPOINT=1)),
    ('critical_rx_channel',dict(NUM_RX_CHANNELS_PER_ENDPOINT=1)),
)


def hashes(rtl):
    paths=(*DEPENDENCIES,rtl,*sorted((ROOT/'src/gen/global_noc').glob('*.py')))
    return dict(source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths},verification_sha256=verification_hashes(HERE))


def run_case(task):
    args,rtl,index,name,p=task
    build=args.build_dir.resolve()/name
    generate(p,build/'profile.json')
    prefix='-Pglobal_noc.' if args.sim=='icarus' else '-pvalue+global_noc.'
    flags=' '.join(shlex.quote(f'{prefix}{k}={v}') for k,v in p.items())
    print('Running',name,flush=True)
    result,log,results,coverage=run_simulation(args,ROOT,HERE,'global_noc','test_global_noc',
        'GlobalNocTest',build,' '.join(map(str,(*DEPENDENCIES,rtl))),parameters=p,
        compile_args=f'{args.compile_args} {flags}',environment={
            **{f'GLOBAL_NOC_{k}':str(v) for k,v in p.items()},
            'GLOBAL_NOC_SEED':str(args.seed+index),'GLOBAL_NOC_RANDOM_CYCLES':str(args.random_cycles)})
    row=dict(name=name,status='FAIL',parameters=p,log=str(log))
    try:
        if result.returncode:raise ValueError(f'make exited {result.returncode}')
        passed_test(results,'GlobalNocTest','test_global_noc')
        data=json.loads(coverage.read_text())
        if data['status']!='PASS' or data['parameters']!=p or not all(data['goals'].values()):
            raise ValueError('Coverage/configuration mismatch')
        if data['seed']!=args.seed+index or data['random_transactions']!=args.random_cycles:
            raise ValueError('Seed/random duration mismatch')
        row.update(data,name=name,log=str(log),coverage=str(coverage))
    except (OSError,ValueError,KeyError,ET.ParseError) as error:
        row['error']=str(error)
        if license_unavailable(log.read_text()):row['status']='NOT_RUN'
        print('\n'.join(log.read_text().splitlines()[-35:]),flush=True)
    print(name,row['status'],flush=True)
    return row


def main():
    args=parse_args('global_noc',__doc__,profiles=[n for n,_ in PROFILES],
        seed=20261027,rtl_category='mosaic_blocks')
    build=args.build_dir.resolve();build.mkdir(parents=True,exist_ok=True)
    rtl=args.rtl.resolve()
    summary=dict(status='NOT_RUN',framework='PyUVM',simulator=args.sim,profiles=[],parameter_checks=[],
        validation_mode='Python-only',synthesis='Design Compiler (deferred)',
        started_at_utc=datetime.now(UTC).isoformat())
    try:
        before=hashes(rtl);summary.update(before)
        with (build/'python_model_tests.log').open('w') as log:
            result=unittest.TextTestRunner(stream=log).run(unittest.defaultTestLoader.loadTestsFromTestCase(ModelTests))
        summary['python_model_checks']=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun)
        if not result.wasSuccessful():raise ValueError('Python reference model tests failed')
        require_simulator(args)
        tasks=[(args,rtl,i,n,p) for i,(n,p) in enumerate(PROFILES) if not args.case or n in args.case]
        with ThreadPoolExecutor(max_workers=3 if args.sim=='icarus' else 1) as pool:
            summary['profiles']=list(pool.map(run_case,tasks))
        summary['parameter_checks']=[parameter_guard(args,build,rtl,'global_noc',n,p,
            'global_noc_parameters_must_be_valid',dependencies=DEPENDENCIES) for n,p in INVALID]
        native_guards=[]
        for module,credit in (('noc_router','OUTPUT_INITIAL_CREDITS'),
                              ('tile_network_interface','TX_INITIAL_CREDITS_PER_VC')):
            native=ROOT/f'src/rtl/building_blocks/{module}.sv'
            dependencies=tuple(p for p in DEPENDENCIES if p!=native)
            for label,value in (('negative',-1),('x',"32'bx"),('z',"32'bz"),('over_capacity',3)):
                native_guards.append(parameter_guard(args,build,native,module,
                    f'{module}_packet_credit_{label}',dict(PACKET_CREDIT_RESERVATION=value),
                    module+'_parameters_must_be_valid',dependencies=dependencies))
        summary['parameter_checks'].extend(native_guards)
        summary['compatibility']=run_compatibility(args,build)
        summary['sources_stable']=before==hashes(rtl)
        complete=len(summary['profiles'])==(len(set(args.case)) if args.case else len(PROFILES))
        summary['status']=campaign_status((*summary['profiles'],*summary['parameter_checks'],
            summary['python_model_checks'],*summary['compatibility']),complete and summary['sources_stable'])
    except (OSError,ValueError,KeyError) as error:summary['error']=str(error)
    finally:finish_summary(build/'summary.json',summary,'Global NoC')
    return 0 if summary['status']=='PASS' else 1

if __name__=='__main__':sys.exit(main())
