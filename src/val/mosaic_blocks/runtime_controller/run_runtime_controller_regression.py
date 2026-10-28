"""Python-only runtime policy, protocol, resource and protection campaign."""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shlex
import sys
import unittest
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(HERE.parents[1] / 'lib'))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(ROOT / 'src/gen/runtime_controller'))
from runtime_controller_contract import profile, BOUNDS, UNSUPPORTED
from runtime_controller_sources import PATHS
from runtime_controller.test_model import ModelTests
from generate import generate
from mosaic_uvm.regression import (parse_args, run_simulation, passed_test, parameter_guard,
    require_simulator, verification_hashes, campaign_status, finish_summary, license_unavailable)


def case(name, **changes):
    return name, profile(ACTION_TIMEOUT_CYCLES=128, POLICY_SAMPLE_INTERVAL=32,
                         HIGH_PRIORITY_BURST_LIMIT=2, **changes)


PROFILES = (
    case('balanced'),
    case('static_single', RUNTIME_PROFILE=0, NUM_CLUSTERS=1, MAX_PENDING_KERNELS=4, MAX_OWNERS=2),
    case('static_array', RUNTIME_PROFILE=0, NUM_CLUSTERS=4, MAX_PENDING_KERNELS=4),
    case('partitioned_two', NUM_CLUSTERS=2, MAX_PENDING_KERNELS=4, MAX_PACKAGE_VARIANTS=2,
         AGE_COUNTER_WIDTH=8, AGE_ESCALATION_CYCLES=16),
    case('shallow', MAX_PENDING_KERNELS=4, SUBMISSION_QUEUE_DEPTH=2, ACTION_QUEUE_DEPTH=2,
         RESPONSE_QUEUE_DEPTH=2, EVENT_QUEUE_DEPTH=2, COUNTER_SNAPSHOT_SLOTS=2,
         AGE_COUNTER_WIDTH=8, AGE_ESCALATION_CYCLES=8),
    case('parity', NUM_CLUSTERS=2, MAX_PENDING_KERNELS=4, MAX_PACKAGE_VARIANTS=2, CONTROL_PROTECTION=1),
    case('secded', NUM_CLUSTERS=1, MAX_PENDING_KERNELS=2, MAX_PACKAGE_VARIANTS=1,
         MAX_OWNERS=1, CONTROL_PROTECTION=2),
    case('monitoring_off', NUM_CLUSTERS=2, MAX_PENDING_KERNELS=4, MAX_PACKAGE_VARIANTS=2,
         ENABLE_QOS=0, ENABLE_SAFE_SUSPEND=0, ENABLE_POWER_POLICY=0,
         ENABLE_COUNTER_FEEDBACK=0, ENABLE_DEADLINE_MONITORING=0, ENABLE_FAULT_AWARE_ALLOCATION=0),
    case('heterogeneous', MEMORY_BANDWIDTH_CAPACITY=0xfffffff0, OWNER_ID_TABLE=0x4003030220011001,
         CLUSTER_CAPABILITY_TABLE=0x00000003000000010000000300000001,
         CLUSTER_MEMORY_PORT_TABLE=0x0003000300030003,
         CLUSTER_SCRATCHPAD_REGION_TABLE=0x0000000f0000000f0000000f0000000f),
    case('expanded', NUM_CLUSTERS=8, MAX_OWNERS=8, MAX_DMA_CHANNELS=8, MAX_MEMORY_PORTS=8,
         MAX_SCRATCHPAD_REGIONS=32, MAX_EVENT_NAMESPACES=32),
)
POSITIVE = ('NUM_CLUSTERS', 'MAX_PENDING_KERNELS', 'MAX_ACTIVE_KERNELS', 'MAX_OWNERS',
            'MAX_PACKAGE_VARIANTS', 'MAX_DMA_CHANNELS', 'MAX_MEMORY_PORTS',
            'MAX_SCRATCHPAD_REGIONS', 'MAX_EVENT_NAMESPACES', 'NUM_PRIORITY_LEVELS',
            'SUBMISSION_QUEUE_DEPTH', 'ACTION_QUEUE_DEPTH', 'RESPONSE_QUEUE_DEPTH',
            'EVENT_QUEUE_DEPTH', 'COUNTER_SNAPSHOT_SLOTS', 'AGE_COUNTER_WIDTH')
INVALID = tuple((f'{name}_{label}', {name: value}) for name in POSITIVE
                for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + (
    ('adaptive', dict(RUNTIME_PROFILE=2)), ('active_above_pending', dict(MAX_PENDING_KERNELS=2)),
    ('active_above_clusters', dict(NUM_CLUSTERS=2, MAX_ACTIVE_KERNELS=4)),
    ('clusters_per_kernel', dict(MAX_CLUSTERS_PER_KERNEL=5)),
    ('static_active', dict(RUNTIME_PROFILE=0, MAX_ACTIVE_KERNELS=2)),
    ('static_variants', dict(RUNTIME_PROFILE=0, MAX_PACKAGE_VARIANTS=2)),
    ('protection', dict(CONTROL_PROTECTION=3)), ('owner_zero', dict(OWNER_ID_TABLE=0)),
    ('owner_duplicate', dict(OWNER_ID_TABLE="64'h0001000100010001")),
    ('age_promotion_unrepresentable', dict(AGE_COUNTER_WIDTH=2)),
    ('timeout_overflow', dict(ACTION_TIMEOUT_CYCLES="64'd4294967296")),
    ('table_x', dict(CLUSTER_CAPABILITY_TABLE="128'bx")),
) + tuple((name, {name: 1}) for name in UNSUPPORTED) + tuple(
    (f'{name}_wrong_abi', {name: 1}) for name in BOUNDS if name.endswith('_WIDTH')
    and name not in ('AGE_COUNTER_WIDTH',)) + tuple(
    (f'{name}_not_boolean', {name: 2}) for name in ('ENABLE_QOS', 'ENABLE_POWER_POLICY',
    'ENABLE_COUNTER_FEEDBACK', 'ENABLE_SAFE_SUSPEND', 'ENABLE_DEADLINE_MONITORING'))


def hashes(rtl):
    sources = (*PATHS[:-1], rtl, *sorted((ROOT / 'src/gen/runtime_controller').glob('*.py')))
    return dict(source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sources}, verification_sha256=verification_hashes(HERE))


def run_case(task):
    args, rtl, index, name, p = task
    build = args.build_dir.resolve() / name
    generate(p, build / 'profile.json')
    prefix = '-Pruntime_controller.' if args.sim == 'icarus' else '-pvalue+runtime_controller.'
    # Explicit widths prevent Icarus truncating packed platform tables to 32 bits.
    flags = ' '.join(shlex.quote(f"{prefix}{k}={max(32, v.bit_length())}'d{v}") for k, v in p.items())
    print('Running', name, flush=True)
    result, log, results, coverage = run_simulation(args, ROOT, HERE, 'runtime_controller',
        'test_runtime_controller', 'RuntimeControllerTest', build,
        ' '.join(map(str, (*PATHS[:-1], rtl))), parameters=p,
        compile_args=f'{args.compile_args} {flags}', environment={
            **{f'RUNTIME_CONTROLLER_{k}': str(v) for k, v in p.items()},
            'RUNTIME_CONTROLLER_SEED': str(args.seed + index),
            'RUNTIME_CONTROLLER_RANDOM_CYCLES': str(args.random_cycles)})
    row = dict(name=name, status='FAIL', parameters=p, log=str(log))
    try:
        if result.returncode:
            raise ValueError(f'make exited {result.returncode}')
        passed_test(results, 'RuntimeControllerTest', 'test_runtime_controller')
        data = json.loads(coverage.read_text())
        if data['status'] != 'PASS' or data['parameters'] != p or not all(data['goals'].values()):
            raise ValueError('Coverage/configuration mismatch')
        if data['seed'] != args.seed + index or data['random_transactions'] != args.random_cycles:
            raise ValueError('Seed/random duration mismatch')
        row.update(data, name=name, log=str(log), coverage=str(coverage))
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        row['error'] = str(error)
        if license_unavailable(log.read_text()):
            row['status'] = 'NOT_RUN'
        print('\n'.join(log.read_text().splitlines()[-35:]), flush=True)
    print(name, row['status'], flush=True)
    return row


def main():
    args = parse_args('runtime_controller', __doc__, [name for name, _ in PROFILES],
                      seed=20261027, rtl_category='mosaic_blocks')
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    rtl = args.rtl.resolve()
    before = hashes(rtl)
    summary = dict(status='FAIL', started_at_utc=datetime.now(UTC).isoformat(),
                   simulator=args.sim, seed=args.seed, profiles=[], parameter_checks=[], **before,
                   signoff=dict(python_simulation='this campaign', hdl_assertions='NOT_RUN',
                                lint='NOT_RUN', formal='NOT_RUN', synthesis='Design Compiler (deferred)'))
    try:
        with (build / 'python_model_tests.log').open('w') as log:
            result = unittest.TextTestRunner(stream=log).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(ModelTests))
        summary['python_model_checks'] = dict(status='PASS' if result.wasSuccessful() else 'FAIL',
                                             tests=result.testsRun)
        if not result.wasSuccessful():
            raise ValueError('Python reference model tests failed')
        require_simulator(args)
        tasks = [(args, rtl, i, name, p) for i, (name, p) in enumerate(PROFILES)
                 if not args.case or name in args.case]
        with ThreadPoolExecutor(max_workers=3 if args.sim == 'icarus' else 1) as pool:
            summary['profiles'] = list(pool.map(run_case, tasks))
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'runtime_controller',
            name, p, 'runtime_controller_parameters_must_be_valid', dependencies=PATHS[:-1])
            for name, p in INVALID]
        summary['sources_stable'] = before == hashes(rtl)
        complete = len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES))
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks'],
            summary['python_model_checks']), complete and summary['sources_stable'])
    except (OSError, ValueError, KeyError) as error:
        summary['error'] = str(error)
    finally:
        finish_summary(build / 'summary.json', summary, 'Runtime controller')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
