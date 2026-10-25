"""Python-only loop, safe-point, arithmetic and protection campaigns."""
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
from mosaic_uvm.regression import (campaign_status, finish_summary, license_unavailable,
    parameter_guard, parse_args, passed_test, require_simulator, run_simulation, verification_hashes)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from loop_controller.config import DEFAULTS

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f'src/rtl/{name}.sv' for name in (
    'building_blocks/loop_controller_pkg', 'common/dff', 'common/decoder',
    'common/priority_encoder', 'common/write_gate', 'common/operand_isolation', 'basic/parity',
    'building_blocks/event_barrier_state'))


def profile(depth, index, trip, linear, ii, bounded, suspend, abort, protect, reset):
    parameters = DEFAULTS | dict(MAX_LOOP_DEPTH=depth, INDEX_WIDTH=index, TRIP_COUNT_WIDTH=trip,
        LINEAR_COUNT_WIDTH=linear, II_WIDTH=ii, SUPPORT_BOUNDED_MODE=bounded,
        SUPPORT_SUSPEND=suspend, SUPPORT_ABORT=abort, PROTECT_STATE=protect, ASYNC_RESET=reset,
        NUM_EVENTS=3, CONTEXT_ID_WIDTH=3, RUN_ID_WIDTH=3)
    return f'd{depth}_i{index}_t{trip}_l{linear}_ii{ii}_b{bounded}_s{suspend}_a{abort}_p{protect}_r{reset}', parameters


# Width/depth coverage plus every independent feature combination at depth three.
PROFILES = tuple(dict([('default', DEFAULTS)] + [profile(d, i, t, 12, 8, 1, 1, 1, p, r)
    for (d, i, t), p, r in product(((1, 16, 16), (2, 32, 16), (3, 64, 32),
                                  (4, 32, 32), (8, 16, 16)), (0, 1), (0, 1))] +
    [profile(3, 16, 16, 12, 2, b, s, a, p, r)
     for b, s, a, p, r in product((0, 1), repeat=5)]).items())
INVALID = tuple((f'{name.lower()}_{label}', {name: value}) for name in list(DEFAULTS)[:9]
    for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'{name.lower()}_{label}', {name: value}) for name in list(DEFAULTS)[9:]
    for label, value in (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + (
    ('epoch_one', dict(CONFIG_EPOCH_WIDTH=1)),
    ('packed_overflow', dict(INDEX_WIDTH=1073741824)),
    ('depth_overflow', dict(MAX_LOOP_DEPTH=1073741824)),
)


def run_profile(task):
    args, build, rtl, index, name, parameters = task
    print('Running', name, flush=True)
    prefix = '-Ploop_controller.' if args.sim == 'icarus' else '-pvalue+loop_controller.'
    flags = ' '.join(shlex.quote(f'{prefix}{key}={value}') for key, value in parameters.items())
    result, log, results, coverage = run_simulation(
        args, ROOT, TEST_DIR, 'loop_controller', 'test_loop_controller', 'LoopControllerTest',
        build / name, ' '.join(map(str, (*DEPENDENCIES, rtl))), parameters=parameters,
        compile_args=f'{args.compile_args} {flags}', environment={
            **{f'LOOP_CONTROLLER_{key}': str(value) for key, value in parameters.items()},
            'LOOP_CONTROLLER_SEED': str(args.seed + index),
            'LOOP_CONTROLLER_RANDOM_CYCLES': str(args.random_cycles),
            'LOOP_CONTROLLER_CHECK_INTERNALS': '1', 'LOOP_CONTROLLER_HDL_ASSERTIONS': '0',
        },
    )
    row = dict(name=name, parameters=parameters, status='FAIL', log=str(log))
    try:
        if result.returncode:
            raise ValueError(f'make exited {result.returncode}')
        passed_test(results, 'LoopControllerTest', 'test_loop_controller')
        data = json.loads(coverage.read_text())
        if (
            data['status'] != 'PASS' or data['parameters'] != parameters
            or not data['goals'] or not all(data['goals'].values())
            or data['hdl_assertions'] != 'NOT_RUN' or data['selection_assertions'] != 'PASS'
            or data['seed'] != args.seed + index
            or data['random_transactions'] != args.random_cycles
        ):
            raise ValueError('Coverage evidence mismatch')
        row.update(data, name=name, log=str(log), coverage=str(coverage))
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        row['error'] = str(error)
        if license_unavailable(log.read_text()):
            row['status'] = 'NOT_RUN'
        print('\n'.join(log.read_text().splitlines()[-25:]), flush=True)
    print(name, row['status'], flush=True)
    return row


def main():
    args = parse_args('loop_controller', __doc__, profiles=[n for n, _ in PROFILES],
                      seed=20261022, rtl_category='building_blocks')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    output = build / 'summary.json'
    output.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, profiles=[],
        validation_mode='Python-only', synthesis='Design Compiler (deferred)',
        parameter_checks=[], started_at_utc=datetime.now(timezone.utc).isoformat(),
        scope='selected_profiles' if args.case else 'representative_loop_controller_profiles')
    try:
        summary['rtl_sha256'] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary['dependency_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in DEPENDENCIES}
        summary['verification_sha256'] = verification_hashes(TEST_DIR)
        require_simulator(args)
        jobs = int(os.getenv('LOOP_CONTROLLER_JOBS', '4' if args.sim == 'icarus' else '1'))
        if not 1 <= jobs <= 32:
            raise ValueError('LOOP_CONTROLLER_JOBS must be between 1 and 32')
        summary['jobs'] = jobs
        tasks = [
            (args, build, rtl, index, name, parameters)
            for index, (name, parameters) in enumerate(PROFILES)
            if not args.case or name in args.case
        ]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary['profiles'] = list(pool.map(run_profile, tasks))
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'loop_controller', name, values,
            'loop_controller_parameters_must_be_valid', dependencies=DEPENDENCIES) for name, values in INVALID]
        complete = len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES)) and len(summary['parameter_checks']) == len(INVALID)
        stable = (
            summary['rtl_sha256'] == hashlib.sha256(rtl.read_bytes()).hexdigest()
            and all(summary['dependency_sha256'][str(p.relative_to(ROOT))]
                == hashlib.sha256(p.read_bytes()).hexdigest() for p in DEPENDENCIES)
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
        finish_summary(output, summary, 'Loop-controller')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
