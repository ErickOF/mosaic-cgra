"""Python-only shell integration, protection and dual-clock parameter campaigns."""
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
from tile_shell.defaults import DEFAULTS
from tile_shell.dependencies import DEPENDENCIES as NAMES
from tile_shell.test_model import ModelTests
ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f'src/rtl/{name}.sv' for name in NAMES)


def profile(label, **overrides):
    p = DEFAULTS | overrides
    p.setdefault('INPUT_ELASTIC_MASK', (1 << p['DATA_INPUT_PORTS']) - 1)
    p.setdefault('OUTPUT_ELASTIC_MASK', (1 << p['DATA_OUTPUT_PORTS']) - 1)
    return label, p


PROFILES = (
    profile('default'), profile('default_async', CONFIG_ASYNC=1, ASYNC_RESET=1),
    profile('bct_width2', TILE_CLASS=0, DATA_WIDTH=2),
    *(profile(f'class{cls}', TILE_CLASS=cls, DATA_WIDTH=width,
        DATA_INPUT_PORTS=ports, DATA_OUTPUT_PORTS=ports, INPUT_BUFFER_DEPTH=depth,
        OUTPUT_BUFFER_DEPTH=depth, CONTEXT_DEPTH=contexts, CONFIG_WORD_COUNT=words,
        CONFIG_ASYNC=cls % 2, ASYNC_RESET=(cls + 1) % 2, SUPPORT_TRACE=cls % 2)
      for cls, width, ports, depth, contexts, words in (
        (0, 8, 1, 0, 1, 1), (1, 16, 2, 1, 4, 8), (2, 32, 4, 2, 8, 32),
        (3, 64, 8, 4, 16, 8), (4, 128, 4, 1, 4, 1))),
    *(profile(f'context{cp}_control{sp}_cfg{a}', DATA_WIDTH=16,
        DATA_METADATA_WIDTH=16, DATA_INPUT_PORTS=2, DATA_OUTPUT_PORTS=1,
        INPUT_ELASTIC_MASK=2, OUTPUT_ELASTIC_MASK=0, INPUT_BUFFER_DEPTH=2,
        OUTPUT_BUFFER_DEPTH=(cp + sp) % 2, PREDICATE_INPUT_PORTS=2,
        EVENT_INPUT_PORTS=2, CONTEXT_DEPTH=3, CONFIG_WORD_COUNT=3, CONFIG_DATA_WIDTH=16,
        CONTEXT_VERSION_WIDTH=8, OWNER_ID_WIDTH=4, KERNEL_ID_WIDTH=4,
        CONTEXT_PROTECTION=cp, CONTROL_PROTECTION=sp, CONFIG_ASYNC=a,
        CONFIG_QUEUE_DEPTH=3, ASYNC_RESET=(cp + sp + a) % 2,
        SUPPORT_TRACE=(cp + sp + a) % 2, SUPPORT_CONTEXT_CHECKSUM=(cp + sp + a) % 2,
        SUPPORT_RETENTION=(cp + sp + a) % 2,
        SUPPORT_POWER_OFF=((cp + sp + a) // 2) % 2)
      for cp, sp, a in product((0, 1, 2), (0, 1, 2), (0, 1))),
    profile('wide_ports', DATA_WIDTH=128, DATA_INPUT_PORTS=8, DATA_OUTPUT_PORTS=8,
        PREDICATE_INPUT_PORTS=4, PREDICATE_OUTPUT_PORTS=4, EVENT_INPUT_PORTS=4,
        EVENT_OUTPUT_PORTS=4, INPUT_BUFFER_DEPTH=4, OUTPUT_BUFFER_DEPTH=4,
        SUPPORT_TRACE=1, SUPPORT_RETENTION=1, SUPPORT_POWER_OFF=1),
    profile('version_wrap', CONTEXT_DEPTH=1, CONFIG_WORD_COUNT=1,
        CONFIG_DATA_WIDTH=8, CONTEXT_VERSION_WIDTH=4),
)
BOOLS = ('SUPPORT_CONTEXT_CHECKSUM','CONFIG_ASYNC','SUPPORT_TRACE','SUPPORT_RETENTION',
         'SUPPORT_POWER_OFF','ASYNC_RESET')
POSITIVE = tuple(k for k in DEFAULTS if k not in (*BOOLS, 'TILE_ID','TILE_CLASS',
    'INPUT_BUFFER_DEPTH','OUTPUT_BUFFER_DEPTH','CONTEXT_PROTECTION','CONTROL_PROTECTION'))
INVALID = (
    *((f'{k.lower()}_{label}', {k: v}) for k in POSITIVE for label,v in (
        ('zero',0),('negative',-1),('x',"32'bx"),('z',"32'bz"))),
    *((f'{k.lower()}_{label}', {k:v}) for k in BOOLS for label,v in (
        ('two',2),('negative',-1),('x',"32'bx"),('z',"32'bz"))),
    ('class',dict(TILE_CLASS=5)), ('context_protection',dict(CONTEXT_PROTECTION=3)),
    ('control_protection',dict(CONTROL_PROTECTION=3)),
    ('input_depth',dict(INPUT_BUFFER_DEPTH=-1)),('output_depth',dict(OUTPUT_BUFFER_DEPTH=-1)),
    ('byte_width',dict(CONFIG_DATA_WIDTH=7)), ('crc_width',dict(CONTEXT_CHECKSUM_WIDTH=16)),
    ('async_depth',dict(CONFIG_ASYNC=1,CONFIG_QUEUE_DEPTH=1)),
    ('input_mask',dict(INPUT_ELASTIC_MASK="3'b111")),
    ('output_mask',dict(OUTPUT_ELASTIC_MASK="5'b11111")),
    ('input_mask_x',dict(INPUT_ELASTIC_MASK="4'bx")),
    ('tile_id',dict(TILE_ID=65536)), ('negative_tile_id',dict(TILE_ID=-1)),
    ('metadata',dict(DATA_METADATA_WIDTH=8)), ('predicate_metadata',dict(PREDICATE_METADATA_WIDTH=1)),
    ('event_metadata',dict(EVENT_WIDTH=8)), ('trace_width',dict(SUPPORT_TRACE=1,TRACE_WIDTH=8)),
    ('error_width',dict(ERROR_CODE_WIDTH=4)), ('stall_width',dict(STALL_REASON_WIDTH=3)),
    ('storage',dict(CONTEXT_DEPTH=1048576)),
)


def hashes(rtl):
    return dict(rtl_sha256=hashlib.sha256(rtl.read_bytes()).hexdigest(),
        dependency_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in DEPENDENCIES},
        verification_sha256=verification_hashes(TEST_DIR))


def run_profile(task):
    args, build, rtl, index, name, p = task
    print('Running', name, flush=True)
    prefix = '-Ptile_shell.' if args.sim == 'icarus' else '-pvalue+tile_shell.'
    flags = ' '.join(shlex.quote(f'{prefix}{k}={v}') for k,v in p.items())
    # Untyped masks intentionally retain their literal width for strict guards.
    for key, ports in (('INPUT_ELASTIC_MASK','DATA_INPUT_PORTS'),('OUTPUT_ELASTIC_MASK','DATA_OUTPUT_PORTS')):
        literal = f"{p[ports]}'d{p[key]}"
        flags = flags.replace(shlex.quote(f'{prefix}{key}={p[key]}'),shlex.quote(f'{prefix}{key}={literal}'))
    result, log, results, coverage = run_simulation(args, ROOT, TEST_DIR, 'tile_shell',
        'test_tile_shell','TileShellTest',build/name,' '.join(map(str,(*DEPENDENCIES,rtl))),
        parameters=p,compile_args=f'{args.compile_args} {flags}',environment={
            **{f'TILE_SHELL_{k}':str(v) for k,v in p.items()},
            'TILE_SHELL_SEED':str(args.seed+index),'TILE_SHELL_RANDOM_CYCLES':str(args.random_cycles)})
    row = dict(name=name,parameters=p,status='FAIL',log=str(log))
    try:
        if result.returncode:
            raise ValueError(f'make exited {result.returncode}')
        passed_test(results,'TileShellTest','test_tile_shell')
        data = json.loads(coverage.read_text())
        if (data['status'] != 'PASS' or data['parameters'] != p or not data['goals'] or
            not all(data['goals'].values()) or data['random_transactions'] != args.random_cycles or
            data['seed'] != args.seed+index or data['hdl_assertions'] != 'NOT_RUN'):
            raise ValueError('Coverage or configuration mismatch')
        row.update(data,name=name,log=str(log),coverage=str(coverage))
    except (OSError,ValueError,KeyError,ET.ParseError) as error:
        row['error'] = str(error)
        if license_unavailable(log.read_text()):
            row['status'] = 'NOT_RUN'
        print('\n'.join(log.read_text().splitlines()[-25:]),flush=True)
    print(name,row['status'],flush=True)
    return row


def main():
    args = parse_args('tile_shell',__doc__,profiles=[n for n,_ in PROFILES],
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
        if not result.wasSuccessful():
            raise ValueError('Python model checks failed')
        require_simulator(args)
        jobs=int(os.getenv('TILE_SHELL_JOBS','4' if args.sim=='icarus' else '1'))
        if not 1 <= jobs <= 32:
            raise ValueError('TILE_SHELL_JOBS must be between 1 and 32')
        tasks=[(args,build,rtl,i,n,p) for i,(n,p) in enumerate(PROFILES) if not args.case or n in args.case]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary['profiles']=list(pool.map(run_profile,tasks))
        summary['parameter_checks']=[parameter_guard(args,build,rtl,'tile_shell',n,p,
            'tile_shell_parameters_must_be_valid',dependencies=DEPENDENCIES) for n,p in INVALID]
        summary['sources_stable']=before==hashes(rtl)
        complete=len(summary['profiles'])==(len(set(args.case)) if args.case else len(PROFILES))
        summary['status']=campaign_status((*summary['profiles'],*summary['parameter_checks'],
            summary['python_model_checks']),complete and summary['sources_stable'])
    except (OSError,ValueError) as error:
        summary['error']=str(error)
    finally:
        finish_summary(build/'summary.json',summary,'Tile shell')
    return 0 if summary['status']=='PASS' else 1

if __name__=='__main__':
    sys.exit(main())
