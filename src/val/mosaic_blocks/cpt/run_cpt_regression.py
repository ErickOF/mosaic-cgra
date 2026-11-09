"""Python-only CPT control composition and shell integration parameter campaign."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import shlex
import sys
import unittest
import xml.etree.ElementTree as ET
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lib'))
from mosaic_uvm.regression import (campaign_status, finish_summary, license_unavailable,
    parameter_guard, parse_args, passed_test, require_simulator, run_simulation, verification_hashes)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cpt.defaults import DEFAULTS
from cpt.dependencies import DEPENDENCIES as NAMES
from cpt.test_model import ModelTests
ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f'src/rtl/{name}.sv' for name in NAMES)


from cpt_contract import profile as parameters
from generate import generate as generate_profile


def profile(name, **changes):
    return name, parameters(**changes)


LOCAL=dict(FU_PROFILE=0,SUPPORT_CONTEXT_COORDINATION=0,
           SUPPORT_CLUSTER_LIFECYCLE=0,SUPPORT_TIMEOUT=0)
PROFILES=(
    profile('default'),
    profile('local',**LOCAL),
    profile('small',PREDICATE_LANES=3,PREDICATE_DEPTH=3,MAX_LOOP_DEPTH=2,INDEX_WIDTH=8,
        TRIP_COUNT_WIDTH=8,NUM_EVENTS=3,NUM_WAIT_SLOTS=1,NUM_BARRIERS=1,MAX_PARTICIPANTS=3,
        EVENT_COUNT_WIDTH=2,MAX_OUTSTANDING_ACTIONS=1,CONTROL_REGISTER_DEPTH=4),
    profile('single_lane',PREDICATE_LANES=1,MAX_LOOP_DEPTH=1,NUM_EVENTS=1,EVENT_COUNT_WIDTH=2,
        MAX_PARTICIPANTS=1,CONTEXT_DEPTH=1),
    profile('wide_predicate',PREDICATE_LANES=16,PREDICATE_DEPTH=16,MAX_LOOP_DEPTH=3,
        LOOP_EXPORT_LEVELS=2,CONTROL_REGISTER_DEPTH=16,MAX_PRIORITY_BURST=1),
    profile('event_parity',EVENT_PROTECTION=1,EVENT_OUTPUT_FIFO_DEPTH=1,
        WAIT_RESULT_QUEUE_DEPTH=1,BARRIER_RELEASE_QUEUE_DEPTH=1),
    profile('context_ecc_async',CONTEXT_PROTECTION=2,CONFIG_ASYNC=1,
        MAX_OUTSTANDING_ACTIONS=2,INPUT_BUFFER_DEPTH=2,OUTPUT_BUFFER_DEPTH=2),
    profile('features_off',**LOCAL,SUPPORT_PREDICATED_TOKEN=0,REQUIRE_CANONICAL_FORMAT=0,
        MAX_LOOP_DEPTH=2,INDEX_WIDTH=16,TRIP_COUNT_WIDTH=16),
)
POSITIVE=('PREDICATE_DEPTH','PREDICATE_LANES','MAX_LOOP_DEPTH','NUM_EVENTS',
    'NUM_WAIT_SLOTS','NUM_BARRIERS','EVENT_OUTPUT_FIFO_DEPTH','MAX_OUTSTANDING_ACTIONS')
INVALID=(
    *((f'{key.lower()}_{label}',{key:value}) for key in POSITIVE
      for label,value in (('zero',0),('negative',-1),('x',"32'bx"),('z',"32'bz"))),
    ('adaptive',dict(FU_PROFILE=2)),('checkpoint',dict(SUPPORT_CHECKPOINT=1)),
    ('namespaces',dict(NUM_EVENT_NAMESPACES=2)),('event_record',dict(EVENT_RECORD_WIDTH=64)),
    ('predicate_protection',dict(PREDICATE_PROTECTION=1)),
    ('control_protection',dict(CONTROL_PROTECTION=1)),
    ('async_reset',dict(ASYNC_RESET=1)),('invalid_action_enable',dict(ENABLE_ACTIONS=2)),
    ('action_capacity',dict(ACTION_QUEUE_DEPTH=1)),
    ('loop_export',dict(LOOP_EXPORT_LEVELS=5)),('config_words',dict(CONFIG_WORD_COUNT=8)),
    ('unknown_profile',dict(FU_PROFILE="32'bx")),
    ('tile_width',dict(TILE_ID_WIDTH=0)),('source_id',dict(TILE_ID=16)),
    ('data_mask',dict(INPUT_ELASTIC_MASK=0)),('queue_geometry',dict(CONFIG_ASYNC=1,CONFIG_QUEUE_DEPTH=3)),
    ('config_async_x',dict(CONFIG_ASYNC="32'bx")),('checksum',dict(SUPPORT_CONTEXT_CHECKSUM=0)),
)


def hashes(rtl):
    files = (*DEPENDENCIES, rtl, *sorted((ROOT/'src/gen/cpt').glob('*.py')))
    return dict(source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in files},
                verification_sha256=verification_hashes(TEST_DIR))


def run_profile(task):
    args, build, rtl, index, name, p = task
    print('Running', name, flush=True)
    generate_profile(p,build/name/'profile.json')
    prefix = '-Pcpt.' if args.sim == 'icarus' else '-pvalue+cpt.'
    values = p.copy()
    for name_mask, port_count in (('INPUT_ELASTIC_MASK','DATA_INPUT_PORTS'),('OUTPUT_ELASTIC_MASK','DATA_OUTPUT_PORTS')):
        values[name_mask] = f"{p[port_count]}'d{p[name_mask]}"
    flags = ' '.join(shlex.quote(f'{prefix}{k}={v}') for k,v in values.items())
    result, log, results, coverage = run_simulation(args, ROOT, TEST_DIR, 'cpt',
        'test_cpt','CptTest',build/name,' '.join(map(str,(*DEPENDENCIES,rtl))),
        parameters=p,compile_args=f'{args.compile_args} {flags}',environment={
            **{f'CPT_{k}':str(v) for k,v in p.items()},
            'CPT_SEED':str(args.seed+index),'CPT_RANDOM_CYCLES':str(args.random_cycles)})
    row = dict(name=name,parameters=p,status='FAIL',log=str(log))
    try:
        if result.returncode: raise ValueError(f'make exited {result.returncode}')
        passed_test(results,'CptTest','test_cpt')
        data = json.loads(coverage.read_text())
        if (data['status'] != 'PASS' or data['parameters'] != p or not data['goals'] or
            not all(data['goals'].values()) or data['random_transactions'] != args.random_cycles or
            data['seed'] != args.seed+index or data['hdl_assertions'] != 'NOT_RUN'):
            raise ValueError('Coverage or configuration mismatch')
        row.update(data,name=name,log=str(log),coverage=str(coverage))
    except (OSError,ValueError,KeyError,ET.ParseError) as error:
        row['error'] = str(error)
        if license_unavailable(log.read_text()): row['status'] = 'NOT_RUN'
        print('\n'.join(log.read_text().splitlines()[-24:]),flush=True)
    print(name,row['status'],flush=True)
    return row


def main():
    args = parse_args('cpt',__doc__,profiles=[n for n,_ in PROFILES],
        seed=20261027,rtl_category='mosaic_blocks')
    build,rtl = args.build_dir.resolve(),args.rtl.resolve()
    build.mkdir(parents=True,exist_ok=True)
    summary = dict(status='NOT_RUN',framework='PyUVM',simulator=args.sim,profiles=[],parameter_checks=[],
        validation_mode='Python-only',synthesis='Design Compiler (deferred)',
        started_at_utc=datetime.now(timezone.utc).isoformat())
    try:
        before=hashes(rtl)
        summary.update(before)
        with (build/'python_model_tests.log').open('w') as log:
            result=unittest.TextTestRunner(stream=log).run(unittest.defaultTestLoader.loadTestsFromTestCase(ModelTests))
        summary['python_model_checks']=dict(status='PASS' if result.wasSuccessful() else 'FAIL',tests=result.testsRun)
        if not result.wasSuccessful(): raise ValueError('Python model checks failed')
        require_simulator(args)
        jobs=int(os.getenv('CPT_JOBS','3' if args.sim=='icarus' else '1'))
        if not 1 <= jobs <= 32: raise ValueError('CPT_JOBS must be between 1 and 32')
        tasks=[(args,build,rtl,i,n,p) for i,(n,p) in enumerate(PROFILES) if not args.case or n in args.case]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary['profiles']=list(pool.map(run_profile,tasks))
        summary['parameter_checks']=[parameter_guard(args,build,rtl,'cpt',n,p,
            'cpt_parameters_must_be_valid',dependencies=DEPENDENCIES) for n,p in INVALID]
        summary['sources_stable']=before==hashes(rtl)
        complete=len(summary['profiles'])==(len(set(args.case)) if args.case else len(PROFILES))
        summary['status']=campaign_status((*summary['profiles'],*summary['parameter_checks'],
            summary['python_model_checks']),complete and summary['sources_stable'])
    except (OSError,ValueError,KeyError) as error:
        summary['error']=str(error)
    finally:
        finish_summary(build/'summary.json',summary,'CPT')
    return 0 if summary['status']=='PASS' else 1

if __name__=='__main__':
    sys.exit(main())
