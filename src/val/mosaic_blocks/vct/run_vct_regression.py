"""Python-only VCT composition and shell integration parameter campaign."""
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
from vct.defaults import DEFAULTS
from vct.dependencies import DEPENDENCIES as NAMES
from vct.test_model import ModelTests
ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f'src/rtl/{name}.sv' for name in NAMES)


def profile(label, **overrides):
    p = DEFAULTS | overrides
    p.setdefault('INPUT_ELASTIC_MASK', (1 << p['DATA_INPUT_PORTS']) - 1)
    p.setdefault('OUTPUT_ELASTIC_MASK', (1 << p['DATA_OUTPUT_PORTS']) - 1)
    return label, p


PROFILES = (
    profile('default'),
    *(profile(f'l{ln}_e{el}_fu{fu}', NUM_LANES=ln, ELEMENT_WIDTH=el,
        ACC_WIDTH=64 if el == 16 and fu == 2 else 32, WRITE_SLICE_WIDTH=min(8,el),
        FU_PROFILE=fu, SYNC_PROFILE=(ln + el + fu) % 3,
        BYPASS_PROFILE=(ln + fu) % 3, ASYNC_RESET=fu % 2)
      for ln, el, fu in product((2,4,8),(4,8,16),(0,1,2))
      if (ln,el,fu) != (4,8,1)),
    *(profile(f'protection{rf}_{control}', VRF_PROTECTION=rf, CONTROL_PROTECTION=control,
        FU_PROFILE=2, CONFIG_ASYNC=(rf + control) % 2,
        REGISTER_BYPASS=(rf + control) % 2, SYNC_PROFILE=2)
      for rf, control in product((0,1,2),repeat=2)),
    profile('latency0', LANE_LATENCY=0, MUL_LATENCY=0, MAC_LATENCY=0,
        REDUCTION_LATENCY=0, DOT_LATENCY=0, FU_PROFILE=2),
    profile('latency_max', LANE_LATENCY=4, MUL_LATENCY=3, MAC_LATENCY=4,
        REDUCTION_LATENCY=8, DOT_LATENCY=8, FU_PROFILE=2, REGISTER_BYPASS=1),
    profile('rf16', VRF_DEPTH=16, NUM_LANES=8, ELEMENT_WIDTH=4,
        WRITE_SLICE_WIDTH=4, CONFIG_WORD_COUNT=64),
    profile('odd_resources', VRF_DEPTH=3, PREDICATE_DEPTH=3, VECTOR_ACC_DEPTH=3,
        SCALAR_ACC_DEPTH=3, CONTEXT_DEPTH=3, DATA_INPUT_PORTS=3, DATA_OUTPUT_PORTS=3,
        VRF_READ_PORTS=3, VRF_WRITE_PORTS=2, RESULT_QUEUE_DEPTH=1, INPUT_FIFO_DEPTH=1,
        FU_PROFILE=2, BYPASS_PROFILE=2, SYNC_PROFILE=2),
    profile('features_off', FU_PROFILE=0, SUPPORT_MUL=0, SUPPORT_MAC=0,
        SUPPORT_SATURATION=0, SUPPORT_MINMAX=0, SUPPORT_BROADCAST=0,
        SUPPORT_LANE_SELECT=0, SUPPORT_SPATIAL_TEMPORAL=0, SUPPORT_PREDICATED_TOKEN=0,
        SYNC_PROFILE=0, RDU_TOTAL_DELAY_ENTRIES=0, INPUT_FIFO_DEPTH=0),
    profile('padding_allowed', REQUIRE_CANONICAL_FORMAT=0),
    profile('slice1', NUM_LANES=8, ELEMENT_WIDTH=16, WRITE_SLICE_WIDTH=1,
        VRF_DEPTH=4, CONFIG_WORD_COUNT=64),
    profile('contexts2', CONTEXT_DEPTH=2),
    profile('contexts16', CONTEXT_DEPTH=16),
    profile('scheduled', SYNC_PROFILE=0, INPUT_BUFFER_DEPTH=0, OUTPUT_BUFFER_DEPTH=0,
        INPUT_ELASTIC_MASK=0, OUTPUT_ELASTIC_MASK=0),
    profile('power', SUPPORT_RETENTION=1, SUPPORT_POWER_OFF=1, CONFIG_ASYNC=1,
        CONTROL_PROTECTION=1, VRF_PROTECTION=1),
)
assert len(PROFILES) == len({n for n,_ in PROFILES})
BOOLS = ('REGISTER_BYPASS','SUPPORT_SPATIAL_TEMPORAL','SUPPORT_MUL','SUPPORT_MAC',
    'SUPPORT_SATURATION','SUPPORT_MINMAX','SUPPORT_BROADCAST','SUPPORT_LANE_SELECT',
    'SUPPORT_PREDICATED_TOKEN','REQUIRE_CANONICAL_FORMAT','ASYNC_RESET')
POSITIVE = ('NUM_LANES','ELEMENT_WIDTH','ACC_WIDTH','VRF_DEPTH','VRF_READ_PORTS',
    'VRF_WRITE_PORTS','WRITE_SLICE_WIDTH','PREDICATE_DEPTH','VECTOR_ACC_DEPTH',
    'SCALAR_ACC_DEPTH','DATA_INPUT_PORTS','DATA_OUTPUT_PORTS','RESULT_QUEUE_DEPTH',
    'CONFIG_WORD_COUNT','CONTEXT_DEPTH')
INVALID = (
    *((f'{k.lower()}_{label}',{k:v}) for k in POSITIVE for label,v in (
        ('zero',0),('negative',-1),('x',"32'bx"),('z',"32'bz"))),
    *((f'{k.lower()}_{label}',{k:v}) for k in BOOLS for label,v in (
        ('two',2),('negative',-1),('x',"32'bx"),('z',"32'bz"))),
    *((f'{k.lower()}_{label}',{k:v}) for k in ('FU_PROFILE','BYPASS_PROFILE','SYNC_PROFILE',
        'VRF_PROTECTION','CONTROL_PROTECTION') for label,v in (
        ('bad',3),('negative',-1),('x',"32'bx"),('z',"32'bz"))),
    *((f'{k.lower()}_{label}',{k:v}) for k in ('LANE_LATENCY','MUL_LATENCY','MAC_LATENCY',
        'REDUCTION_LATENCY','DOT_LATENCY','RDU_TOTAL_DELAY_ENTRIES','INPUT_FIFO_DEPTH')
      for label,v in (('negative',-1),('x',"32'bx"),('z',"32'bz"))),
    ('lane_count3',dict(NUM_LANES=3)), ('element_width7',dict(ELEMENT_WIDTH=7)),
    ('acc_width15',dict(ACC_WIDTH=15)), ('dot_width',dict(FU_PROFILE=2,ACC_WIDTH=16)),
    ('slice_nondivisor',dict(WRITE_SLICE_WIDTH=3)), ('slice_too_wide',dict(WRITE_SLICE_WIDTH=16)),
    ('lane_latency5',dict(LANE_LATENCY=5)), ('mul_misaligned',dict(MUL_LATENCY=2)),
    ('mac_misaligned',dict(MAC_LATENCY=2)), ('reduction_latency9',dict(REDUCTION_LATENCY=9)),
    ('dot_latency9',dict(DOT_LATENCY=9)), ('read_ports1',dict(VRF_READ_PORTS=1)),
    ('rdu_capacity',dict(RDU_TOTAL_DELAY_ENTRIES=1)),
    ('elastic_depth',dict(SYNC_PROFILE=2,INPUT_FIFO_DEPTH=0)),
    ('metadata_width',dict(DATA_METADATA_WIDTH=16)),
)


def hashes(rtl):
    reused = {f'reused/{folder}/{path.name}': hashlib.sha256(path.read_bytes()).hexdigest()
              for folder in ('bct','tile_shell')
              for path in (TEST_DIR.parent / folder).glob('*.py')}
    return dict(rtl_sha256=hashlib.sha256(rtl.read_bytes()).hexdigest(),
        dependency_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in DEPENDENCIES},
        verification_sha256=verification_hashes(TEST_DIR) | reused)


def run_profile(task):
    args, build, rtl, index, name, p = task
    print('Running', name, flush=True)
    prefix = '-Pvct.' if args.sim == 'icarus' else '-pvalue+vct.'
    values = p.copy()
    for name_mask, port_count in (('INPUT_ELASTIC_MASK','DATA_INPUT_PORTS'),('OUTPUT_ELASTIC_MASK','DATA_OUTPUT_PORTS')):
        values[name_mask] = f"{p[port_count]}'d{p[name_mask]}"
    flags = ' '.join(shlex.quote(f'{prefix}{k}={v}') for k,v in values.items())
    result, log, results, coverage = run_simulation(args, ROOT, TEST_DIR, 'vct',
        'test_vct','VctTest',build/name,' '.join(map(str,(*DEPENDENCIES,rtl))),
        parameters=p,compile_args=f'{args.compile_args} {flags}',environment={
            **{f'VCT_{k}':str(v) for k,v in p.items()},
            'VCT_SEED':str(args.seed+index),'VCT_RANDOM_CYCLES':str(args.random_cycles)})
    row = dict(name=name,parameters=p,status='FAIL',log=str(log))
    try:
        if result.returncode: raise ValueError(f'make exited {result.returncode}')
        passed_test(results,'VctTest','test_vct')
        data = json.loads(coverage.read_text())
        if (data['status'] != 'PASS' or data['parameters'] != p | dict(DATA_WIDTH=p['NUM_LANES'] * p['ACC_WIDTH'], PREDICATE_WIDTH=p['NUM_LANES']) or not data['goals'] or
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
    args = parse_args('vct',__doc__,profiles=[n for n,_ in PROFILES],
        seed=20261025,rtl_category='mosaic_blocks')
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
        jobs=int(os.getenv('VCT_JOBS','4' if args.sim=='icarus' else '1'))
        if not 1 <= jobs <= 32: raise ValueError('VCT_JOBS must be between 1 and 32')
        tasks=[(args,build,rtl,i,n,p) for i,(n,p) in enumerate(PROFILES) if not args.case or n in args.case]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary['profiles']=list(pool.map(run_profile,tasks))
        summary['parameter_checks']=[parameter_guard(args,build,rtl,'vct',n,p,
            'vct_parameters_must_be_valid',dependencies=DEPENDENCIES) for n,p in INVALID]
        summary['parameter_checks'].append(parameter_guard(args,build,rtl,'vct',
            'context_image_capacity',{'CONFIG_WORD_COUNT':1},
            'vct_context_image_must_fit',dependencies=DEPENDENCIES))
        summary['sources_stable']=before==hashes(rtl)
        complete=len(summary['profiles'])==(len(set(args.case)) if args.case else len(PROFILES))
        summary['status']=campaign_status((*summary['profiles'],*summary['parameter_checks'],
            summary['python_model_checks']),complete and summary['sources_stable'])
    except (OSError,ValueError) as error:
        summary['error']=str(error)
    finally:
        finish_summary(build/'summary.json',summary,'VCT')
    return 0 if summary['status']=='PASS' else 1

if __name__=='__main__':
    sys.exit(main())
