"""Run PyUVM parameter profiles and Python-driven illegal-parameter probes."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lib'))
from mosaic_uvm.regression import (
    campaign_status,
    finish_summary,
    license_unavailable,
    parameter_guard,
    parse_args,
    passed_test,
    require_simulator,
    run_simulation,
    verification_hashes,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tile_power_controller.config import DEFAULTS

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(
    ROOT / f'src/rtl/{name}.sv'
    for name in (
        'building_blocks/tile_power_controller_pkg',
        'common/dff',
        'common/counter',
        'common/reset_synchronizer',
    )
)


def profile(label, **overrides):
    p = DEFAULTS | overrides
    if 'WAKEUP_CLOCK_GROUP_MASK' not in overrides:
        p['WAKEUP_CLOCK_GROUP_MASK'] = (1 << p['NUM_CLOCK_GROUPS']) - 1
    return label, p


PROFILES = (
    profile('default'),
    profile('default_async', ASYNC_RESET=1),
    *(
        profile(
            f'g{groups}_w{wakes}_feature{feature}_r{reset}',
            NUM_CLOCK_GROUPS=groups,
            NUM_WAKE_SOURCES=wakes,
            NUM_STALL_REASONS=(1, 3, 4, 5)[index],
            CONTEXT_ID_WIDTH=(1, 3, 8, 13)[index],
            SUPPORT_POWER_GATING=int(feature > 0),
            SUPPORT_RETENTION=int(feature == 2),
            ASYNC_RESET=reset,
            WAKE_ON_EVENT=(index + wakes + feature + reset) % 2,
            IDLE_ENTRY_CYCLES=1 if index % 2 == 0 else 5,
            MIN_IDLE_RESIDENCY_CYCLES=1 if index % 2 == 0 else 3,
            WAKEUP_STABILIZE_CYCLES=1 if index % 2 == 0 else 3,
            ISOLATION_SETUP_CYCLES=1 if index % 2 == 0 else 4,
            POWER_STABLE_CYCLES=1 if index % 2 == 0 else 3,
            RESET_HOLD_CYCLES=1 if index % 2 == 0 else 4,
            DRAIN_TIMEOUT_CYCLES=7,
            ACK_TIMEOUT_CYCLES=5,
            POWER_TIMEOUT_CYCLES=32,
            POWER_GOOD_SYNC_STAGES=2 + index % 3,
            CLOCK_GROUP_ALWAYS_ON_MASK=sum(1 << g for g in range(groups) if g % 2),
            WAKEUP_CLOCK_GROUP_MASK=sum(1 << g for g in range(groups) if g % 3 == 0),
        )
        for (index, groups), wakes, feature, reset in product(
            enumerate((1, 4, 8, 16)), (1, 4, 8), (0, 1, 2), (0, 1)
        )
    ),
    *(
        profile(
            f'minimum_feature{feature}_r{reset}',
            NUM_CLOCK_GROUPS=3,
            NUM_WAKE_SOURCES=3,
            NUM_STALL_REASONS=2,
            CONTEXT_ID_WIDTH=2,
            IDLE_ENTRY_CYCLES=1,
            MIN_IDLE_RESIDENCY_CYCLES=1,
            WAKEUP_STABILIZE_CYCLES=1,
            ISOLATION_SETUP_CYCLES=1,
            POWER_STABLE_CYCLES=1,
            RESET_HOLD_CYCLES=1,
            DRAIN_TIMEOUT_CYCLES=1,
            ACK_TIMEOUT_CYCLES=1,
            POWER_TIMEOUT_CYCLES=8,
            SUPPORT_POWER_GATING=int(feature > 0),
            SUPPORT_RETENTION=int(feature == 2),
            ASYNC_RESET=reset,
            WAKEUP_CLOCK_GROUP_MASK=0,
            CLOCK_GROUP_ALWAYS_ON_MASK=0,
        )
        for feature, reset in product((0, 1, 2), (0, 1))
    ),
)
POSITIVE = (
    'NUM_CLOCK_GROUPS',
    'NUM_WAKE_SOURCES',
    'NUM_STALL_REASONS',
    'CONTEXT_ID_WIDTH',
    'IDLE_ENTRY_CYCLES',
    'MIN_IDLE_RESIDENCY_CYCLES',
    'WAKEUP_STABILIZE_CYCLES',
    'ISOLATION_SETUP_CYCLES',
    'POWER_STABLE_CYCLES',
    'RESET_HOLD_CYCLES',
    'DRAIN_TIMEOUT_CYCLES',
    'ACK_TIMEOUT_CYCLES',
    'POWER_TIMEOUT_CYCLES',
)
INVALID = (
    tuple(
        (f'{key}_{label}', {key: value})
        for key in POSITIVE
        for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))
    )
    + tuple(
        (f'{key}_{label}', {key: value})
        for key in ('SUPPORT_RETENTION', 'SUPPORT_POWER_GATING', 'WAKE_ON_EVENT', 'ASYNC_RESET')
        for label, value in (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))
    )
    + tuple(
        (f'sync_{label}', dict(POWER_GOOD_SYNC_STAGES=value))
        for label, value in (
            ('zero', 0),
            ('one', 1),
            ('negative', -1),
            ('x', "32'bx"),
            ('z', "32'bz"),
        )
    )
    + tuple(
        (f'{key}_{label}', {key: value})
        for key in ('CLOCK_GROUP_ALWAYS_ON_MASK', 'WAKEUP_CLOCK_GROUP_MASK')
        for label, value in (('short', "3'h0"), ('long', "5'h0"), ('x', "4'bx"), ('z', "4'bz"))
    )
    + (
        ('retention_without_power', dict(SUPPORT_RETENTION=1)),
        ('cycle_overflow', dict(IDLE_ENTRY_CYCLES=2147483647)),
        ('timeout_overflow', dict(POWER_TIMEOUT_CYCLES=4294967296)),
        ('groups_overflow', dict(NUM_CLOCK_GROUPS=2147483647)),
        ('sync_overflow', dict(POWER_GOOD_SYNC_STAGES=2147483647)),
    )
)


def run_profile(task):
    args, build, rtl, index, name, parameters = task
    print('Running', name, flush=True)
    prefix = (
        '-Ptile_power_controller.' if args.sim == 'icarus' else '-pvalue+tile_power_controller.'
    )
    overrides = parameters | {
        key: f"{parameters['NUM_CLOCK_GROUPS']}'h{parameters[key]:x}"
        for key in ('CLOCK_GROUP_ALWAYS_ON_MASK', 'WAKEUP_CLOCK_GROUP_MASK')
    }
    flags = ' '.join(shlex.quote(f'{prefix}{k}={v}') for k, v in overrides.items())
    result, log, results, coverage = run_simulation(
        args,
        ROOT,
        TEST_DIR,
        'tile_power_controller',
        'test_tile_power_controller',
        'TilePowerControllerTest',
        build / name,
        ' '.join(map(str, (*DEPENDENCIES, rtl))),
        parameters=parameters,
        compile_args=f'{args.compile_args} {flags}',
        environment={
            **{f'TILE_POWER_CONTROLLER_{key}': str(value) for key, value in parameters.items()},
            'TILE_POWER_CONTROLLER_SEED': str(args.seed + index),
            'TILE_POWER_CONTROLLER_RANDOM_CYCLES': str(args.random_cycles),
        },
    )
    row = dict(
        name=name, parameters=parameters, seed=args.seed + index, status='FAIL', log=str(log)
    )
    try:
        if result.returncode:
            raise ValueError(f'make exited {result.returncode}')
        passed_test(results, 'TilePowerControllerTest', 'test_tile_power_controller')
        data = json.loads(coverage.read_text())
        if (
            data['status'] != 'PASS'
            or data['parameters'] != parameters
            or not data['goals']
            or not all(data['goals'].values())
            or data['seed'] != args.seed + index
            or data['random_transactions'] != args.random_cycles
            or data['hdl_assertions'] != 'NOT_RUN'
        ):
            raise ValueError('Coverage evidence mismatch')
        if data['internal_timer_checks'] != 'PASS':
            raise ValueError('Internal timer checks missing')
        row.update(data, name=name, log=str(log), coverage=str(coverage))
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        row['error'] = str(error)
        if license_unavailable(log.read_text()):
            row['status'] = 'NOT_RUN'
        print('\n'.join(log.read_text().splitlines()[-24:]), flush=True)
    print(name, row['status'], flush=True)
    return row


def main():
    args = parse_args(
        'tile_power_controller',
        __doc__,
        profiles=[n for n, _ in PROFILES],
        seed=20261023,
        rtl_category='building_blocks',
    )
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    output = build / 'summary.json'
    output.unlink(missing_ok=True)
    summary = dict(
        status='NOT_RUN',
        framework='PyUVM',
        simulator=args.sim,
        profiles=[],
        parameter_checks=[],
        started_at_utc=datetime.now(timezone.utc).isoformat(),
        validation_mode='Python-only',
        synthesis='Design Compiler (deferred)',
        scope='selected_profiles' if args.case else 'representative_parameter_matrix',
    )
    try:
        summary['rtl_sha256'] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary['dependency_sha256'] = {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in DEPENDENCIES
        }
        summary['verification_sha256'] = verification_hashes(TEST_DIR)
        require_simulator(args)
        jobs = int(os.getenv('TILE_POWER_CONTROLLER_JOBS', '4' if args.sim == 'icarus' else '1'))
        if not 1 <= jobs <= 32:
            raise ValueError('TILE_POWER_CONTROLLER_JOBS must be between 1 and 32')
        summary['jobs'] = jobs
        tasks = [
            (args, build, rtl, index, name, parameters)
            for index, (name, parameters) in enumerate(PROFILES)
            if not args.case or name in args.case
        ]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary['profiles'] = list(pool.map(run_profile, tasks))
        summary['parameter_checks'] = [
            parameter_guard(
                args,
                build,
                rtl,
                'tile_power_controller',
                name,
                values,
                'tile_power_controller_parameters_must_be_valid',
                dependencies=DEPENDENCIES,
            )
            for name, values in INVALID
        ]
        complete = len(summary['profiles']) == (
            len(set(args.case)) if args.case else len(PROFILES)
        ) and len(summary['parameter_checks']) == len(INVALID)
        stable = (
            summary['rtl_sha256'] == hashlib.sha256(rtl.read_bytes()).hexdigest()
            and all(
                summary['dependency_sha256'][str(p.relative_to(ROOT))]
                == hashlib.sha256(p.read_bytes()).hexdigest()
                for p in DEPENDENCIES
            )
            and summary['verification_sha256'] == verification_hashes(TEST_DIR)
        )
        summary['sources_stable'] = stable
        summary['status'] = campaign_status(
            (*summary['profiles'], *summary['parameter_checks']), complete and stable
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        summary['error'] = str(error)
        print(error, file=sys.stderr)
    finally:
        finish_summary(output, summary, 'Tile-power-controller')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
