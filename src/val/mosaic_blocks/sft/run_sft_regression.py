"""Python-only SFT composition and shell integration parameter campaign."""
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
from sft.defaults import DEFAULTS
from sft.dependencies import DEPENDENCIES as NAMES
from sft.test_model import ModelTests
from sft.characterize import characterize
ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f'src/rtl/{name}.sv' for name in NAMES)


from contract import profile as parameters
from generate import generate as generate_profile


def profile(name, **changes):
    return name, parameters(**changes)


SMALL = dict(LUT_ADDRESS_WIDTH=2, LUT_BANKS=2, POLY_BANKS=2, CONTEXT_DEPTH=2)
PROFILES = (
    profile('default'),
    profile('small_geometry', LUT_ADDRESS_WIDTH=1, LUT_INDEX_FRACTION_WIDTH=1,
            LUT_BANKS=1, POLY_BANKS=1, CONTEXT_DEPTH=3, INPUT_WIDTH=4,
            INPUT_FRAC_BITS=2, OUTPUT_WIDTH=8, OUTPUT_FRAC_BITS=4,
            REDUCTION_LANES=2, REDUCTION_ELEMENT_WIDTH=3, MAX_REDUCTION_ELEMENTS=16,
            LOCAL_RF_DEPTH=3, RESULT_QUEUE_DEPTH=1, MAX_INFLIGHT=1, BYPASS_PROFILE=2),
    profile('minimal', **SMALL, FU_PROFILE=0),
    profile('balanced', **SMALL),
    profile('norm', **SMALL, FU_PROFILE=2),
    profile('transformer', **SMALL, FU_PROFILE=3),
    profile('none', **SMALL, SYNC_PROFILE=0, BYPASS_PROFILE=0),
    profile('parity', **SMALL, CONTROL_PROTECTION=1, TABLE_PROTECTION=1,
            COEFFICIENT_PROTECTION=1, CONTEXT_PROTECTION=1, CONFIG_ASYNC=1),
    profile('ecc', **SMALL, FU_PROFILE=3, CONTROL_PROTECTION=2, TABLE_PROTECTION=2,
            COEFFICIENT_PROTECTION=2, CONTEXT_PROTECTION=2),
    profile('features_off', LUT_ADDRESS_WIDTH=2, LUT_BANKS=1, POLY_BANKS=1,
            FU_PROFILE=0, BYPASS_PROFILE=0, SUPPORT_LOCAL_CHAINING=0,
            SUPPORT_INTERPOLATION=0, SUPPORT_SATURATION=0, SUPPORT_PREDICATED_TOKEN=0,
            SUPPORT_SPATIAL_TEMPORAL=0, CONTEXT_DEPTH=1),
    profile('polynomial_unrolled', **SMALL, POLY_EVALUATION_ARCH=1, BYPASS_PROFILE=2),
    profile('wide', **SMALL, FU_PROFILE=2, SHELL_DATA_WIDTH=128,
            REDUCTION_LANES=3, REDUCTION_ELEMENT_WIDTH=8, INPUT_WIDTH=8,
            INPUT_FRAC_BITS=4, OUTPUT_FRAC_BITS=8, BYPASS_PROFILE=2,
            LOCAL_RF_DEPTH=3, INPUT_FIFO_DEPTH=3, RESULT_QUEUE_DEPTH=3, MAX_INFLIGHT=3),
)
POSITIVE = ('SHELL_DATA_WIDTH', 'INPUT_WIDTH', 'OUTPUT_WIDTH', 'LUT_BANKS',
            'POLY_BANKS', 'CONTEXT_DEPTH', 'LOCAL_RF_DEPTH', 'REDUCTION_STATE_DEPTH',
            'INPUT_FIFO_DEPTH', 'RESULT_QUEUE_DEPTH', 'MAX_INFLIGHT')
BOOLS = ('SUPPORT_SPATIAL_TEMPORAL', 'SUPPORT_INTERPOLATION', 'SUPPORT_SATURATION',
         'SUPPORT_PREDICATED_TOKEN', 'SUPPORT_LOCAL_CHAINING', 'REQUIRE_CANONICAL_FORMAT')
INVALID = (
    *((f'{key.lower()}_{label}', {key:value}) for key in POSITIVE
      for label,value in (('zero',0),('negative',-1),('x',"32'bx"),('z',"32'bz"))),
    *((f'{key.lower()}_{label}', {key:value}) for key in BOOLS
      for label,value in (('two',2),('negative',-1),('x',"32'bx"),('z',"32'bz"))),
    ('profile',dict(FU_PROFILE=4)), ('profile_x',dict(FU_PROFILE="32'bx")),
    ('rdu',dict(SYNC_PROFILE=1)), ('fp16',dict(SUPPORT_FP16=1)),
    ('bf16',dict(SUPPORT_BF16=1)), ('credits',dict(MAX_INFLIGHT=9)),
    ('sumsq_width',dict(REDUCTION_ACC_WIDTH=32)),
    ('payload',dict(REDUCTION_LANES=5)), ('image',dict(CONFIG_WORD_COUNT=1)),
    ('metadata',dict(DATA_METADATA_WIDTH=159)), ('async_reset',dict(ASYNC_RESET=1)),
    ('table_protection',dict(TABLE_PROTECTION=3)),
    ('coefficient_protection',dict(COEFFICIENT_PROTECTION=3)),
    ('control_protection',dict(CONTROL_PROTECTION=3)),
    ('fraction',dict(INPUT_FRAC_BITS=16)), ('exp_pipeline',dict(EXP_PIPELINE_DEPTH=4)),
)


def hashes(rtl):
    files = (*DEPENDENCIES, rtl, *sorted((ROOT/'src/gen/sft').glob('*.py')))
    models = tuple(path for unit in ('polynomial_unit','reciprocal_unit','rsqrt_unit','exp_unit')
                   for path in (ROOT/'src/val/building_blocks'/unit).glob('*.py'))
    return dict(source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in (*files,*models)},
                verification_sha256=verification_hashes(TEST_DIR))


def run_profile(task):
    args, build, rtl, index, name, p = task
    print('Running', name, flush=True)
    generate_profile(p,build/name/'profile.json')
    characterize(p,build/name/'accuracy.json')
    prefix = '-Psft.' if args.sim == 'icarus' else '-pvalue+sft.'
    values = p.copy()
    for name_mask, port_count in (('INPUT_ELASTIC_MASK','DATA_INPUT_PORTS'),('OUTPUT_ELASTIC_MASK','DATA_OUTPUT_PORTS')):
        values[name_mask] = f"{p[port_count]}'d{p[name_mask]}"
    flags = ' '.join(shlex.quote(f'{prefix}{k}={v}') for k,v in values.items())
    result, log, results, coverage = run_simulation(args, ROOT, TEST_DIR, 'sft',
        'test_sft','SftTest',build/name,' '.join(map(str,(*DEPENDENCIES,rtl))),
        parameters=p,compile_args=f'{args.compile_args} {flags}',environment={
            **{f'SFT_{k}':str(v) for k,v in p.items()},
            'SFT_SEED':str(args.seed+index),'SFT_RANDOM_CYCLES':str(args.random_cycles)})
    row = dict(name=name,parameters=p,status='FAIL',log=str(log))
    try:
        if result.returncode: raise ValueError(f'make exited {result.returncode}')
        passed_test(results,'SftTest','test_sft')
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
    args = parse_args('sft',__doc__,profiles=[n for n,_ in PROFILES],
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
        accuracy=characterize(parameters(FU_PROFILE=3),build/'accuracy.json')
        summary['numerical_characterization']=dict(status='PASS',sha256=accuracy['sha256'],rows=len(accuracy['rows']))
        require_simulator(args)
        jobs=int(os.getenv('SFT_JOBS','3' if args.sim=='icarus' else '1'))
        if not 1 <= jobs <= 32: raise ValueError('SFT_JOBS must be between 1 and 32')
        tasks=[(args,build,rtl,i,n,p) for i,(n,p) in enumerate(PROFILES) if not args.case or n in args.case]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary['profiles']=list(pool.map(run_profile,tasks))
        summary['parameter_checks']=[parameter_guard(args,build,rtl,'sft',n,p,
            'sft_parameters_must_be_valid',dependencies=DEPENDENCIES) for n,p in INVALID]
        summary['sources_stable']=before==hashes(rtl)
        complete=len(summary['profiles'])==(len(set(args.case)) if args.case else len(PROFILES))
        summary['status']=campaign_status((*summary['profiles'],*summary['parameter_checks'],
            summary['python_model_checks']),complete and summary['sources_stable'])
    except (OSError,ValueError,KeyError) as error:
        summary['error']=str(error)
    finally:
        finish_summary(build/'summary.json',summary,'SFT')
    return 0 if summary['status']=='PASS' else 1

if __name__=='__main__':
    sys.exit(main())
