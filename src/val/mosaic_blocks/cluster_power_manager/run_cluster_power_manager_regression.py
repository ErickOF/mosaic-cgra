"""Python-only cluster power sequencing, wake, drain, fault and protection campaign."""
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
sys.path.insert(0, str(ROOT / 'src/gen/cluster_power_manager'))
from cluster_power_manager_contract import profile, BOUNDS, BOOLEANS, FIXED, UNSUPPORTED
from cluster_power_manager_sources import PATHS
from cluster_power_manager.test_model import ModelTests
from generate import generate
from mosaic_uvm.regression import (parse_args, run_simulation, passed_test, parameter_guard,
    require_simulator, verification_hashes, campaign_status, finish_summary, license_unavailable)


def case(name, **changes):
    return name, profile(**(dict(DRAIN_TIMEOUT_CYCLES=256, TILE_ACK_TIMEOUT_CYCLES=128,
        POWER_TIMEOUT_CYCLES=128, CLOCK_TIMEOUT_CYCLES=128, RELOAD_TIMEOUT_CYCLES=128) | changes))


PROFILES = (
    case('balanced'),
    case('single', NUM_TILES=1, NUM_CLOCK_GROUPS=1, NUM_WAKE_SOURCES=1,
         NUM_ISOLATION_GROUPS=1, NUM_RETENTION_GROUPS=1, NUM_RESET_GROUPS=1,
         NUM_BOUNDARY_ENDPOINTS=1, NUM_STALL_REASONS=1),
    case('expanded', NUM_TILES=32, NUM_CLOCK_GROUPS=32, NUM_WAKE_SOURCES=32,
         NUM_ISOLATION_GROUPS=32, NUM_RETENTION_GROUPS=32, NUM_RESET_GROUPS=32,
         NUM_BOUNDARY_ENDPOINTS=32, NUM_STALL_REASONS=32, NUM_SRAM_POWER_GROUPS=8,
         NUM_POWER_SWITCH_GROUPS=8),
    case('shallow', NUM_TILES=2, NUM_CLOCK_GROUPS=3, NUM_ISOLATION_GROUPS=3,
         EVENT_QUEUE_DEPTH=2, IDLE_ENTRY_CYCLES=1, MIN_GATED_RESIDENCY_CYCLES=1),
    case('automatic_off', AUTO_CLOCK_GATE_ENABLE=0, NUM_TILES=2),
    case('synchronous_status', ASYNC_PHYSICAL_STATUS=0, NUM_TILES=2),
    case('deep_sync_async_reset', POWER_GOOD_SYNC_STAGES=4, CLOCK_STATUS_SYNC_STAGES=3,
         VOLTAGE_STATUS_SYNC_STAGES=4, ASYNC_RESET=1, NUM_TILES=2),
    case('counters_rollback_off', ENABLE_COUNTERS=0, SUPPORT_ROLLBACK=0, NUM_TILES=2),
    case('parity', POWER_PROFILE=4, CONTROL_PROTECTION=1, NUM_TILES=2),
    case('secded', POWER_PROFILE=4, CONTROL_PROTECTION=2, NUM_TILES=1,
         NUM_CLOCK_GROUPS=1, NUM_RESET_GROUPS=1),
)
POSITIVE = ('NUM_TILES', 'NUM_CLOCK_GROUPS', 'NUM_WAKE_SOURCES', 'NUM_STALL_REASONS',
            'NUM_ISOLATION_GROUPS', 'NUM_RETENTION_GROUPS', 'NUM_RESET_GROUPS',
            'NUM_POWER_SWITCH_GROUPS', 'NUM_SRAM_POWER_GROUPS', 'NUM_BOUNDARY_ENDPOINTS',
            'IDLE_ENTRY_CYCLES', 'CLOCK_STABLE_CYCLES', 'POWER_STABLE_CYCLES',
            'DRAIN_TIMEOUT_CYCLES', 'CLOCK_TIMEOUT_CYCLES', 'RELOAD_TIMEOUT_CYCLES')
INVALID = tuple((f'{name}_{label}', {name: value}) for name in POSITIVE
                for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + (
    ('retentive_profile', dict(POWER_PROFILE=1)), ('gated_profile', dict(POWER_PROFILE=2)),
    ('dvfs_profile', dict(POWER_PROFILE=3)), ('invalid_profile', dict(POWER_PROFILE=5)),
    ('protected_without_codec', dict(POWER_PROFILE=4)), ('invalid_codec', dict(CONTROL_PROTECTION=3)),
    ('multiple_points', dict(NUM_OPERATING_POINTS=2)), ('shallow_event', dict(EVENT_QUEUE_DEPTH=1)),
    ('tile_limit', dict(NUM_TILES=33)), ('wake_limit', dict(NUM_WAKE_SOURCES=33)),
    ('switch_limit', dict(NUM_POWER_SWITCH_GROUPS=9)),
    ('sync_depth', dict(POWER_GOOD_SYNC_STAGES=1)),
    ('timer_overflow', dict(CLOCK_TIMEOUT_CYCLES="64'd4294967296")),
    ('tile_table_x', dict(TILE_CLOCK_GROUP_TABLE="64'bx")),
    ('tile_table_group', dict(NUM_CLOCK_GROUPS=3, TILE_CLOCK_GROUP_TABLE=3)),
    ('endpoint_table_group', dict(NUM_ISOLATION_GROUPS=3, BOUNDARY_ISOLATION_TABLE=3)),
) + tuple((name, {name: 1}) for name in UNSUPPORTED) + tuple(
    (f'{name}_wrong_abi', {name: 1}) for name in FIXED) + tuple(
    (f'{name}_not_boolean', {name: 2}) for name in BOOLEANS)


def hashes(rtl):
    sources = (*PATHS[:-1], rtl, *sorted((ROOT / 'src/gen/cluster_power_manager').glob('*.py')))
    return dict(source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sources}, verification_sha256=verification_hashes(HERE))


def run_case(task):
    args, rtl, index, name, p = task
    build = args.build_dir.resolve() / name
    generate(p, build / 'profile.json')
    prefix = '-Pcluster_power_manager.' if args.sim == 'icarus' else '-pvalue+cluster_power_manager.'
    # Explicit widths prevent Icarus truncating packed platform tables to 32 bits.
    flags = ' '.join(shlex.quote(f"{prefix}{k}={max(32, v.bit_length())}'d{v}") for k, v in p.items())
    print('Running', name, flush=True)
    result, log, results, coverage = run_simulation(args, ROOT, HERE, 'cluster_power_manager',
        'test_cluster_power_manager', 'ClusterPowerManagerTest', build,
        ' '.join(map(str, (*PATHS[:-1], rtl))), parameters=p,
        compile_args=f'{args.compile_args} {flags}', environment={
            **{f'CLUSTER_POWER_MANAGER_{k}': str(v) for k, v in p.items()},
            'CLUSTER_POWER_MANAGER_SEED': str(args.seed + index),
            'CLUSTER_POWER_MANAGER_RANDOM_CYCLES': str(args.random_cycles)})
    row = dict(name=name, status='FAIL', parameters=p, log=str(log))
    try:
        if result.returncode:
            raise ValueError(f'make exited {result.returncode}')
        passed_test(results, 'ClusterPowerManagerTest', 'test_cluster_power_manager')
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
    args = parse_args('cluster_power_manager', __doc__, [name for name, _ in PROFILES],
                      seed=20261028, rtl_category='mosaic_blocks')
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
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'cluster_power_manager',
            name, p, 'cluster_power_manager_parameters_must_be_valid', dependencies=PATHS[:-1])
            for name, p in INVALID]
        summary['sources_stable'] = before == hashes(rtl)
        complete = len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES))
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks'],
            summary['python_model_checks']), complete and summary['sources_stable'])
    except (OSError, ValueError, KeyError) as error:
        summary['error'] = str(error)
    finally:
        finish_summary(build / 'summary.json', summary, 'Cluster power manager')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
