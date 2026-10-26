"""Python-only MST composition and shell integration parameter campaign."""
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
from mst.defaults import DEFAULTS
from mst.dependencies import DEPENDENCIES as NAMES
from mst.test_model import ModelTests
ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f'src/rtl/{name}.sv' for name in NAMES)


def profile(label, **overrides):
    p = DEFAULTS | overrides
    p.setdefault('INPUT_ELASTIC_MASK', (1 << p['NUM_STREAM_INPUTS']) - 1)
    p.setdefault('OUTPUT_ELASTIC_MASK', (1 << p['NUM_STREAM_OUTPUTS']) - 1)
    return label, p


PROFILES = (
    profile('default'),
    profile('equal32', SHELL_DATA_WIDTH=32, MEMORY_DATA_WIDTH=32, MAX_ELEMENT_BYTES=4),
    profile('narrow32', SHELL_DATA_WIDTH=32, MEMORY_DATA_WIDTH=128),
    profile('wide128', SHELL_DATA_WIDTH=128, MEMORY_DATA_WIDTH=32),
    profile('byte', SHELL_DATA_WIDTH=8, MEMORY_DATA_WIDTH=8, MAX_ELEMENT_BYTES=1),
    profile('wide256', SHELL_DATA_WIDTH=256, MEMORY_DATA_WIDTH=64, MAX_ELEMENT_BYTES=32),
    profile('memory256', SHELL_DATA_WIDTH=64, MEMORY_DATA_WIDTH=256, MAX_ELEMENT_BYTES=32),
    profile('depth1', CONTEXT_DEPTH=1, COMMAND_QUEUE_DEPTH=1, READ_DATA_FIFO_DEPTH=1,
        WRITE_DATA_FIFO_DEPTH=1, COMPLETION_QUEUE_DEPTH=1, EVENT_QUEUE_DEPTH=1,
        MAX_OUTSTANDING_READS=1, MAX_OUTSTANDING_WRITES=1, NUM_BUFFER_ROLES=2,
        NUM_PROTECTION_REGIONS=1, NUM_EVENTS=4),
    profile('odd_resources', NUM_LOAD_CHANNELS=2, NUM_STORE_CHANNELS=3,
        NUM_STREAM_INPUTS=3, NUM_STREAM_OUTPUTS=2, NUM_SCRATCHPAD_CLIENTS=2,
        NUM_DMA_INGRESS_CHANNELS=2, NUM_DMA_EGRESS_CHANNELS=2, COMMAND_QUEUE_DEPTH=3,
        MAX_OUTSTANDING_READS=3, MAX_OUTSTANDING_WRITES=3, NUM_BUFFER_ROLES=3,
        NUM_PROTECTION_REGIONS=3, CONTEXT_DEPTH=3),
    profile('multi_channel', NUM_LOAD_CHANNELS=3, NUM_STORE_CHANNELS=3,
        NUM_SCRATCHPAD_CLIENTS=2, ASYNC_RESET=1),
    profile('parity', COMMAND_PROTECTION=1, FIFO_PROTECTION=1, CONTROL_PROTECTION=1,
        CONTEXT_PROTECTION=1, ASYNC_RESET=1),
    profile('ecc', COMMAND_PROTECTION=2, FIFO_PROTECTION=2, CONTROL_PROTECTION=2,
        CONTEXT_PROTECTION=2),
    profile('mixed', COMMAND_PROTECTION=2, FIFO_PROTECTION=1, CONTROL_PROTECTION=2,
        CONFIG_ASYNC=1),
    profile('power', SUPPORT_RETENTION=1, SUPPORT_POWER_OFF=1, CONFIG_ASYNC=1),
    profile('features_off', SHELL_DATA_WIDTH=64, MEMORY_DATA_WIDTH=64, MAX_ELEMENT_BYTES=8,
        SUPPORT_2D=0, SUPPORT_LOCAL_COPY=0, SUPPORT_UNALIGNED=0,
        SUPPORT_WIDTH_CONVERSION=0, SUPPORT_ELEMENT_CONVERSION=0, SUPPORT_EVENT_START=0,
        SUPPORT_COMMAND_CHAINING=0, SUPPORT_DOUBLE_BUFFER=0, SUPPORT_CANCELLATION=0),
    profile('short_timers', TRANSFER_TIMEOUT_CYCLES=255, CANCEL_TIMEOUT_CYCLES=63,
        MAX_OUTSTANDING_READS=2, MAX_OUTSTANDING_WRITES=2, COUNT_WIDTH=8),
)
POSITIVE = ('ADDR_WIDTH', 'SHELL_DATA_WIDTH', 'MEMORY_DATA_WIDTH', 'NUM_LOAD_CHANNELS',
    'NUM_STORE_CHANNELS', 'NUM_STREAM_INPUTS', 'NUM_STREAM_OUTPUTS',
    'NUM_SCRATCHPAD_CLIENTS', 'COMMAND_QUEUE_DEPTH', 'COMPLETION_QUEUE_DEPTH',
    'MAX_OUTSTANDING_READS', 'MAX_OUTSTANDING_WRITES', 'COUNT_WIDTH', 'MAX_ELEMENT_BYTES',
    'NUM_PROTECTION_REGIONS', 'NUM_BUFFER_ROLES', 'NUM_EVENTS', 'DESCRIPTOR_GENERATION_WIDTH')
INVALID = (
    *((f'{k.lower()}_{label}', {k:v}) for k in POSITIVE for label,v in (
        ('zero',0),('negative',-1),('x',"32'bx"),('z',"32'bz"))),
    *((f'{k.lower()}_bad', {k:3}) for k in (
        'COMMAND_PROTECTION', 'FIFO_PROTECTION', 'CONTROL_PROTECTION')),
    ('width24', dict(SHELL_DATA_WIDTH=24)),
    ('metadata', dict(DATA_METADATA_WIDTH=8)),
    ('event_width', dict(EVENT_WIDTH=32)),
    ('context_image', dict(CONFIG_WORD_COUNT=1)),
    ('region_id', dict(REGION_ID_WIDTH=1)),
    ('buffer_id', dict(BUFFER_ID_WIDTH=1, NUM_BUFFER_ROLES=3)),
    ('combined_channels', dict(NUM_LOAD_CHANNELS=8, NUM_STORE_CHANNELS=1)),
    ('space_width', dict(SPACE_ID_WIDTH=1)),
    ('stream_identity', dict(STREAM_ID_WIDTH=1, NUM_STREAM_INPUTS=8)),
    ('predicate_ports', dict(PREDICATE_INPUT_PORTS=2)),
    ('event_ports', dict(EVENT_OUTPUT_PORTS=2)),
    ('invalid_feature', dict(SUPPORT_CANCELLATION=2)),
    ('unknown_feature', dict(SUPPORT_UNALIGNED="32'bx")),
)
UNRELEASED = tuple((k.lower(), {k:1}) for k in ('SUPPORT_3D', 'SUPPORT_CIRCULAR',
    'SUPPORT_GATHER', 'SUPPORT_SCATTER', 'SUPPORT_ATOMICS', 'SUPPORT_MULTICAST',
    'SUPPORT_DIRECT_MEMORY_PROXY', 'ASYNC_SCRATCHPAD_CLOCK', 'ASYNC_DMA_CLOCK'))


def hashes(rtl):
    reused = TEST_DIR.parent / 'tile_shell'
    return dict(reused_python_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest()
        for p in reused.glob('*.py')}, rtl_sha256=hashlib.sha256(rtl.read_bytes()).hexdigest(),
        dependency_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in DEPENDENCIES},
        verification_sha256=verification_hashes(TEST_DIR))


def run_profile(task):
    args, build, rtl, index, name, p = task
    print('Running', name, flush=True)
    prefix = '-Pmst.' if args.sim == 'icarus' else '-pvalue+mst.'
    values = p.copy()
    for name_mask, port_count in (('INPUT_ELASTIC_MASK','NUM_STREAM_INPUTS'),('OUTPUT_ELASTIC_MASK','NUM_STREAM_OUTPUTS')):
        values[name_mask] = f"{p[port_count]}'d{p[name_mask]}"
    flags = ' '.join(shlex.quote(f'{prefix}{k}={v}') for k,v in values.items())
    result, log, results, coverage = run_simulation(args, ROOT, TEST_DIR, 'mst',
        'test_mst','MstTest',build/name,' '.join(map(str,(*DEPENDENCIES,rtl))),
        parameters=p,compile_args=f'{args.compile_args} {flags}',environment={
            **{f'MST_{k}':str(v) for k,v in p.items()},
            'MST_SEED':str(args.seed+index),'MST_RANDOM_CYCLES':str(args.random_cycles)})
    row = dict(name=name,parameters=p,status='FAIL',log=str(log))
    try:
        if result.returncode: raise ValueError(f'make exited {result.returncode}')
        passed_test(results,'MstTest','test_mst')
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
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sim', choices=('vcs', 'icarus'), default='vcs')
    parser.add_argument('--build-dir', type=Path, required=True)
    parser.add_argument('--rtl', type=Path, default=ROOT/'src/rtl/mosaic_blocks/mst.sv')
    parser.add_argument('--seed', type=int, default=20261025)
    parser.add_argument('--random-cycles', type=int, default=30)
    parser.add_argument('--compile-args', default='')
    parser.add_argument('--sim-args', default='')
    parser.add_argument('--sim-bin-dir', type=Path)
    parser.add_argument('--make', default='make')
    parser.add_argument('--case', action='append', choices=[n for n,_ in PROFILES])
    args = parser.parse_args()
    if args.random_cycles < 1:
        parser.error('--random-cycles must be positive')
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
        jobs=int(os.getenv('MST_JOBS','4' if args.sim=='icarus' else '1'))
        if not 1 <= jobs <= 32: raise ValueError('MST_JOBS must be between 1 and 32')
        tasks=[(args,build,rtl,i,n,p) for i,(n,p) in enumerate(PROFILES) if not args.case or n in args.case]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary['profiles']=list(pool.map(run_profile,tasks))
        summary['parameter_checks']=[parameter_guard(args,build,rtl,'mst',n,p,
            'mst_parameters_must_be_valid',dependencies=DEPENDENCIES) for n,p in INVALID]
        summary['parameter_checks'] += [parameter_guard(args,build,rtl,'mst',n,p,
            'mst_profile_requires_released_adapter',dependencies=DEPENDENCIES) for n,p in UNRELEASED]
        summary['sources_stable']=before==hashes(rtl)
        complete=len(summary['profiles'])==(len(set(args.case)) if args.case else len(PROFILES))
        summary['status']=campaign_status((*summary['profiles'],*summary['parameter_checks'],
            summary['python_model_checks']),complete and summary['sources_stable'])
    except (OSError,ValueError) as error:
        summary['error']=str(error)
    finally:
        finish_summary(build/'summary.json',summary,'MST')
    return 0 if summary['status']=='PASS' else 1

if __name__=='__main__':
    sys.exit(main())
