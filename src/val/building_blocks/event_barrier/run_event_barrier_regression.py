"""Run representative event/barrier profiles and strict elaboration guards."""
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import shlex
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lib'))
from mosaic_uvm.regression import (campaign_status, finish_summary, license_unavailable,
    parameter_guard, parse_args, passed_test, require_simulator, run_simulation, verification_hashes)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from event_barrier.config import DEFAULTS

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / ('src/rtl/' + name + '.sv') for name in (
    'building_blocks/event_barrier_pkg', 'common/dff', 'common/counter',
    'common/operand_isolation', 'common/decoder', 'common/priority_encoder',
    'basic/fifo', 'basic/parity', 'basic/round_robin_arbiter',
    'building_blocks/event_barrier_state', 'building_blocks/event_barrier_queue'))


def profile(events=16, count=4, waits=4, barriers=4, participants=16, depth=4,
            protected=0, reset=0, consume=1, cancel=1, barrier_events=1, generation=4,
            context=8, tag=8):
    parameters = DEFAULTS | dict(NUM_EVENTS=events, EVENT_COUNT_WIDTH=count, NUM_WAIT_SLOTS=waits,
        WAIT_RESULT_QUEUE_DEPTH=depth, NUM_BARRIERS=barriers, MAX_PARTICIPANTS=participants,
        BARRIER_RELEASE_QUEUE_DEPTH=depth, PROTECT_STATE=protected, ASYNC_RESET=reset,
        SUPPORT_WAIT_CONSUME=consume, SUPPORT_WAIT_CANCEL=cancel, SUPPORT_BARRIER_EVENTS=barrier_events,
        GENERATION_WIDTH=generation, CONTEXT_ID_WIDTH=context, WAITER_TAG_WIDTH=tag, BARRIER_TAG_WIDTH=tag)
    name = f'e{events}_c{count}_w{waits}_b{barriers}_p{participants}_d{depth}_prot{protected}_r{reset}_features{consume}{cancel}{barrier_events}_g{generation}_ctx{context}_tag{tag}'
    return name, parameters


PROFILES = tuple(dict(
    [profile(events=e, count=k, waits=w, barriers=b, participants=p, depth=d,
             protected=protected, reset=reset)
     for e, k, w, b, p, d in ((4, 1, 1, 1, 4, 1), (16, 2, 2, 2, 16, 2),
                             (16, 4, 4, 4, 16, 4), (32, 4, 8, 8, 32, 3),
                             (64, 8, 8, 8, 64, 3), (3, 2, 3, 3, 5, 3))
     for protected, reset in product((0, 1), repeat=2)] +
    [profile(events=3, count=2, waits=3, barriers=2, participants=3, depth=1,
             protected=1, reset=reset, consume=consume, cancel=cancel, barrier_events=event,
             generation=2, context=1, tag=2)
     for reset, consume, cancel, event in product((0, 1), repeat=4)] +
    [profile(events=1, count=1, waits=1, barriers=1, participants=2, depth=1,
             protected=1, reset=reset, generation=2, context=1, tag=1) for reset in (0, 1)]
    + [profile(events=2, count=1, waits=2, barriers=1, participants=1, depth=2,
               reset=reset, generation=2) for reset in (0, 1)]
).items())
INVALID = tuple((f'{name.lower()}_{label}', {name: value})
    for name in list(DEFAULTS)[:11] for label, value in
    (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'{name.lower()}_{label}', {name: value}) for name in list(DEFAULTS)[11:]
    for label, value in (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + (
    ('generation_one', dict(GENERATION_WIDTH=1)),
    ('packed_overflow', dict(NUM_EVENTS=1073741824, EVENT_COUNT_WIDTH=8)),
    ('arrived_overflow', dict(NUM_BARRIERS=1073741824)),
    ('queue_overflow', dict(WAIT_RESULT_QUEUE_DEPTH=1073741824)),
)


def main():
    args = parse_args('event_barrier', __doc__, profiles=[name for name, _ in PROFILES],
                      seed=20261021, rtl_category='building_blocks')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, profiles=[],
                   parameter_checks=[], started_at_utc=datetime.now(timezone.utc).isoformat(),
                   scope='selected_profiles' if args.case else 'representative_event_barrier_profiles',
                   external_checks=dict.fromkeys(('formal', 'commercial_lint', 'cdc', 'rdc', 'dft',
                       'vc_lp', 'technology_synthesis', 'physical_timing', 'physical_power'), 'NOT_RUN'))
    try:
        summary['rtl_sha256'] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary['dependency_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                        for p in DEPENDENCIES}
        summary['verification_sha256'] = verification_hashes(TEST_DIR)
        require_simulator(args)
        for index, (name, parameters) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            print('Running', name, flush=True)
            prefix = '-Pevent_barrier.' if args.sim == 'icarus' else '-pvalue+event_barrier.'
            flags = ' '.join(shlex.quote(f'{prefix}{key}={value}') for key, value in parameters.items())
            result, log, results, coverage = run_simulation(args, ROOT, TEST_DIR,
                'event_barrier', 'test_event_barrier', 'EventBarrierTest', build / name,
                ' '.join(map(str, (*DEPENDENCIES, rtl))), parameters=parameters,
                compile_args=f'{args.compile_args} {flags}', environment={
                    **{f'EVENT_BARRIER_{key}': str(value) for key, value in parameters.items()},
                    'EVENT_BARRIER_SEED': str(args.seed + index),
                    'EVENT_BARRIER_RANDOM_CYCLES': str(args.random_cycles),
                    'EVENT_BARRIER_CHECK_INTERNALS': '1', 'EVENT_BARRIER_HDL_ASSERTIONS': '1'})
            row = dict(name=name, status='FAIL', parameters=parameters, log=str(log))
            try:
                if result.returncode:
                    raise ValueError(f'make exited {result.returncode}')
                passed_test(results, 'EventBarrierTest', 'test_event_barrier')
                data = json.loads(coverage.read_text())
                if (data['status'] != 'PASS' or data['hdl_assertions'] != 'PASS' or data['parameters'] != parameters or
                    not data['goals'] or not all(data['goals'].values()) or
                    data['random_transactions'] != args.random_cycles or data['seed'] != args.seed + index):
                    raise ValueError('Coverage evidence mismatch')
                row.update(data, name=name, log=str(log), coverage=str(coverage))
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                row['error'] = str(error)
                if license_unavailable(log.read_text()):
                    row['status'] = 'NOT_RUN'
                print('\n'.join(log.read_text().splitlines()[-22:]), flush=True)
            summary['profiles'].append(row)
            print(name, row['status'], flush=True)
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'event_barrier', name, values,
            'event_barrier_parameters_must_be_valid', dependencies=DEPENDENCIES) for name, values in INVALID]
        complete = len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES)) and len(summary['parameter_checks']) == len(INVALID)
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks']), complete)
    except (OSError, ValueError) as error:
        summary['error'] = str(error)
        print(error, file=sys.stderr)
    finally:
        finish_summary(build / 'summary.json', summary, 'Event/barrier')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
