"""Event-path subcampaign invoked by the existing cluster Python regression."""
import json
from pathlib import Path
import shlex
import xml.etree.ElementTree as ET
from mosaic_uvm.regression import run_simulation, passed_test, license_unavailable


def event_case(name, tiles=4, depth=12, protection=1, ids=None):
    ids = tuple(range(tiles)) if ids is None else ids
    return name, dict(NUM_TILES=tiles, EVENT_DEPTH=depth, PROTECT_EVENTS=protection,
                      TILE_ID_TABLE=sum(value << (t * 8) for t, value in enumerate(ids)))


EVENT_PROFILES = (
    event_case('single', 1, 1),
    event_case('mvp'),
    event_case('shallow', depth=1),
    event_case('permuted', depth=3, ids=(37, 9, 201, 88)),
    event_case('sixteen', 16, 24),
    event_case('maximum', 64, 72),
    event_case('unprotected', depth=5, protection=0),
)
EVENT_INVALID = tuple((f'events_{name}_{label}', {name: value})
    for name in ('NUM_TILES', 'EVENT_DEPTH')
    for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + (
    ('events_tiles_over', dict(NUM_TILES=65)), ('events_depth_over', dict(EVENT_DEPTH=129)),
    ('events_duplicate_id', dict(TILE_ID_TABLE=0)),
    ('events_reserved_id', dict(TILE_ID_TABLE="32'hff020100")),
    ('events_id_x', dict(TILE_ID_TABLE="32'bx")),
    ('events_id_z', dict(TILE_ID_TABLE="32'bz")),
) + tuple((f'events_protection_{label}', dict(PROTECT_EVENTS=value)) for label, value in (
    ('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz")))


def run_events(task):
    args, root, test_dir, build, index, name, p, sources = task
    prefix = '-Pcluster_events.' if args.sim == 'icarus' else '-pvalue+cluster_events.'
    # Packed logical IDs can exceed 32 bits. Never let the simulator truncate them.
    flags = ' '.join(shlex.quote(f"{prefix}{k}={max(32, v.bit_length())}'d{v}") for k, v in p.items())
    result, log, results, coverage = run_simulation(args, root, test_dir, 'cluster_events',
        'test_cluster_events', 'ClusterEventsTest', build / 'events' / name, sources,
        parameters=p, compile_args=f'{args.compile_args} {flags}', environment={
            **{f'CLUSTER_EVENTS_{k}': str(v) for k, v in p.items()},
            'CLUSTER_EVENTS_SEED': str(args.seed + index),
            'CLUSTER_EVENTS_RANDOM_CYCLES': str(args.random_cycles)})
    row = dict(name=name, status='FAIL', scope='production event collector', log=str(log))
    try:
        if result.returncode:
            raise ValueError(f'make exited {result.returncode}')
        passed_test(results, 'ClusterEventsTest', 'test_cluster_events')
        data = json.loads(coverage.read_text())
        if (data['status'] != 'PASS' or data['parameters'] != p or not data['goals'] or
                not all(data['goals'].values()) or data['seed'] != args.seed + index or
                data['random_transactions'] != args.random_cycles):
            raise ValueError('Event coverage/parameter/seed mismatch')
        row.update(data, coverage=str(coverage))
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        row['error'] = str(error)
        if license_unavailable(log.read_text()):
            row['status'] = 'NOT_RUN'
        print('\n'.join(log.read_text().splitlines()[-28:]), flush=True)
    print('Event collector', name, row['status'], flush=True)
    return row
