"""Python-only BCT composition and shell integration parameter campaign."""
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
from bct.defaults import DEFAULTS
from bct.dependencies import DEPENDENCIES as NAMES
from bct.test_model import ModelTests
ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f'src/rtl/{name}.sv' for name in NAMES)


def profile(label, **overrides):
    p = DEFAULTS | overrides
    from mosaic_uvm.tile_selection import DEFAULT_ENABLES
    for name, minimum in DEFAULT_ENABLES["BCT"].items():
        p[name] = overrides.get(name, int(p["FU_PROFILE"] >= minimum))
    p.setdefault('INPUT_ELASTIC_MASK', (1 << p['DATA_INPUT_PORTS']) - 1)
    p.setdefault('OUTPUT_ELASTIC_MASK', (1 << p['DATA_OUTPUT_PORTS']) - 1)
    return label, p


PROFILES = (
    profile('default'),
    profile('synth_width2', DATA_WIDTH=2, MULTIPLY_OPERAND_WIDTH=1),
    *(profile(f'fu{fu}_w{width}_mw{narrow}_sync{sync}', FU_PROFILE=fu, DATA_WIDTH=width,
        MULTIPLY_OPERAND_WIDTH=narrow, SYNC_PROFILE=sync, ASYNC_RESET=sync % 2,
        RF_DEPTH=(4, 8, 16)[sync], BYPASS_PROFILE=sync,
        REGISTER_BYPASS=sync % 2, ALU_LATENCY=sync % 2,
        MULTIPLY_LATENCY=sync * 2, MAC_LATENCY=4 - sync * 2)
      for fu, width, narrow in ((0, 2, 1), (1, 4, 2), (2, 6, 3), (0, 8, 4),
                                (0, 16, 8), (0, 32, 16),
                                (1, 16, 8), (1, 32, 16), (2, 32, 8), (2, 32, 16))
      for sync in (0, 1, 2)),
    *(profile(f'protection{rf}_{control}', RF_PROTECTION=rf, CONTROL_PROTECTION=control,
        FU_PROFILE=2, MULTIPLY_OPERAND_WIDTH=8, SYNC_PROFILE=2,
        CONFIG_ASYNC=(rf + control) % 2, ASYNC_RESET=(rf + control) % 2)
      for rf, control in product((0, 1, 2), repeat=2)),
    profile('depth1', CONTEXT_DEPTH=1, RF_DEPTH=4, PREDICATE_DEPTH=1,
        FU_PROFILE=0, DATA_WIDTH=8, MULTIPLY_OPERAND_WIDTH=4, SYNC_PROFILE=2),
    profile('depth8', CONTEXT_DEPTH=8, RF_DEPTH=32, DATA_INPUT_PORTS=2,
        DATA_OUTPUT_PORTS=2, FU_PROFILE=2, MULTIPLY_OPERAND_WIDTH=8),
    profile('depth16', CONTEXT_DEPTH=16, RF_DEPTH=16, CONFIG_WORD_COUNT=16,
        DATA_INPUT_PORTS=8, DATA_OUTPUT_PORTS=8, INPUT_FIFO_DEPTH=1, RESULT_QUEUE_DEPTH=1),
    profile('features_off', FU_PROFILE=0, SUPPORT_SATURATION=0, SUPPORT_MINMAX=0,
        SUPPORT_SPATIAL_TEMPORAL=0, SUPPORT_PREDICATED_TOKEN=0, SYNC_PROFILE=0,
        RDU_TOTAL_DELAY_ENTRIES=0, INPUT_FIFO_DEPTH=0, ACCUMULATOR_COUNT=0),
    profile('noncanonical_allowed', FU_PROFILE=2, REQUIRE_CANONICAL_NARROW=0),
    profile('wide_codeword', DATA_WIDTH=512, RF_PROTECTION=2, FU_PROFILE=0,
        MULTIPLY_OPERAND_WIDTH=8, CONFIG_WORD_COUNT=16),
    profile('latency3', FU_PROFILE=2, MULTIPLY_OPERAND_WIDTH=8,
        MULTIPLY_LATENCY=3, MAC_LATENCY=3, ALU_LATENCY=0),
    profile('odd_resources', FU_PROFILE=2, MULTIPLY_OPERAND_WIDTH=8,
        CONTEXT_DEPTH=3, RF_DEPTH=3, PREDICATE_DEPTH=1, ACCUMULATOR_COUNT=2,
        IMMEDIATE_COUNT=2, RF_READ_PORTS=3, RF_WRITE_PORTS=2, SYNC_PROFILE=2,
        DATA_INPUT_PORTS=3, DATA_OUTPUT_PORTS=2),
    profile('scheduled', SYNC_PROFILE=0, INPUT_ELASTIC_MASK=0, OUTPUT_ELASTIC_MASK=0,
        INPUT_BUFFER_DEPTH=0, OUTPUT_BUFFER_DEPTH=0),
    profile('power', SUPPORT_RETENTION=1, SUPPORT_POWER_OFF=1, CONFIG_ASYNC=1),
)
assert len(PROFILES) == len({name for name, _ in PROFILES})
BOOLS = ('REGISTER_BYPASS','SUPPORT_SPATIAL_TEMPORAL','SUPPORT_PREDICATED_TOKEN',
         'SUPPORT_SATURATION','SUPPORT_MINMAX','REQUIRE_CANONICAL_NARROW','ASYNC_RESET')
POSITIVE = ('DATA_WIDTH','DATA_INPUT_PORTS','DATA_OUTPUT_PORTS','CONTEXT_DEPTH','RF_DEPTH',
'PREDICATE_DEPTH','IMMEDIATE_COUNT','RF_READ_PORTS','RF_WRITE_PORTS','RESULT_QUEUE_DEPTH',
'MULTIPLY_OPERAND_WIDTH')
INVALID = (
    *((f'{k.lower()}_{label}', {k:v}) for k in POSITIVE for label,v in (
        ('zero',0),('negative',-1),('x',"32'bx"),('z',"32'bz"))),
    *((f'{k.lower()}_{label}', {k:v}) for k in BOOLS for label,v in (
        ('two',2),('negative',-1),('x',"32'bx"),('z',"32'bz"))),
    *((f'{k.lower()}_{label}',{k:v}) for k in ('FU_PROFILE','BYPASS_PROFILE','SYNC_PROFILE',
                                          'RF_PROTECTION','CONTROL_PROTECTION') for label,v in (
        ('bad',3),('negative',-1),('x',"32'bx"),('z',"32'bz"))),
    *((f'{k.lower()}_{label}',{k:v}) for k in ('ALU_LATENCY','MULTIPLY_LATENCY','MAC_LATENCY',
        'ACCUMULATOR_COUNT','RDU_TOTAL_DELAY_ENTRIES','INPUT_FIFO_DEPTH') for label,v in (
        ('negative',-1),('x',"32'bx"),('z',"32'bz"))),
    ('metadata_flag',dict(DATA_METADATA_WIDTH=18)),
    ('storage_overflow',dict(DATA_WIDTH=65536, RF_DEPTH=65536)),
    ('too_narrow',dict(DATA_WIDTH=1)), ('product_width',dict(MULTIPLY_OPERAND_WIDTH=17)),
    ('alu_latency',dict(ALU_LATENCY=2)), ('multiply_latency',dict(MULTIPLY_LATENCY=5)),
    ('mac_latency',dict(MAC_LATENCY=5)), ('read_ports',dict(RF_READ_PORTS=1)),
    ('accumulators',dict(FU_PROFILE=2,ACCUMULATOR_COUNT=0)),
    ('rdu_budget',dict(RDU_TOTAL_DELAY_ENTRIES=0)),
    ('elastic_depth',dict(SYNC_PROFILE=2,INPUT_FIFO_DEPTH=0)),
)


def hashes(rtl):
    return dict(rtl_sha256=hashlib.sha256(rtl.read_bytes()).hexdigest(),
        dependency_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in DEPENDENCIES},
        verification_sha256=verification_hashes(TEST_DIR))


def run_profile(task):
    args, build, rtl, index, name, p = task
    print('Running', name, flush=True)
    prefix = '-Pbct.' if args.sim == 'icarus' else '-pvalue+bct.'
    values = p.copy()
    for name_mask, port_count in (('INPUT_ELASTIC_MASK','DATA_INPUT_PORTS'),('OUTPUT_ELASTIC_MASK','DATA_OUTPUT_PORTS')):
        values[name_mask] = f"{p[port_count]}'d{p[name_mask]}"
    flags = ' '.join(shlex.quote(f'{prefix}{k}={v}') for k,v in values.items())
    result, log, results, coverage = run_simulation(args, ROOT, TEST_DIR, 'bct',
        'test_bct','BctTest',build/name,' '.join(map(str,(*DEPENDENCIES,rtl))),
        parameters=p,compile_args=f'{args.compile_args} {flags}',environment={
            **{f'BCT_{k}':str(v) for k,v in p.items()},
            'BCT_SEED':str(args.seed+index),'BCT_RANDOM_CYCLES':str(args.random_cycles)})
    row = dict(name=name,parameters=p,status='FAIL',log=str(log))
    try:
        if result.returncode: raise ValueError(f'make exited {result.returncode}')
        passed_test(results,'BctTest','test_bct')
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
    args = parse_args('bct',__doc__,profiles=[n for n,_ in PROFILES],
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
        jobs=int(os.getenv('BCT_JOBS','4' if args.sim=='icarus' else '1'))
        if not 1 <= jobs <= 32: raise ValueError('BCT_JOBS must be between 1 and 32')
        tasks=[(args,build,rtl,i,n,p) for i,(n,p) in enumerate(PROFILES) if not args.case or n in args.case]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary['profiles']=list(pool.map(run_profile,tasks))
        summary['parameter_checks']=[parameter_guard(args,build,rtl,'bct',n,p,
            'bct_parameters_must_be_valid',dependencies=DEPENDENCIES) for n,p in INVALID]
        summary['sources_stable']=before==hashes(rtl)
        complete=len(summary['profiles'])==(len(set(args.case)) if args.case else len(PROFILES))
        summary['status']=campaign_status((*summary['profiles'],*summary['parameter_checks'],
            summary['python_model_checks']),complete and summary['sources_stable'])
    except (OSError,ValueError) as error:
        summary['error']=str(error)
    finally:
        finish_summary(build/'summary.json',summary,'BCT')
    return 0 if summary['status']=='PASS' else 1

if __name__=='__main__':
    sys.exit(main())
