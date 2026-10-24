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
from tile_network_interface.config import DEFAULTS

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(
    ROOT / f'src/rtl/{name}.sv'
    for name in (
        'building_blocks/tile_network_interface_pkg',
        'common/dff',
        'common/counter',
        'common/operand_isolation',
        'common/decoder',
        'common/priority_encoder',
        'basic/fifo',
        'basic/parity',
        'basic/round_robin_arbiter',
        'building_blocks/event_barrier_state',
        'building_blocks/event_barrier_queue',
    )
)


def profile(label, **overrides):
    p = DEFAULTS | overrides
    vw = max(1, (p['NUM_VCS'] - 1).bit_length())
    if 'TRAFFIC_CLASS_TO_VC' not in overrides:
        p['TRAFFIC_CLASS_TO_VC'] = sum(
            (n % p['NUM_VCS']) << (n * vw) for n in range(p['NUM_TRAFFIC_CLASSES'])
        )
    return label, p


PROFILES = (
    profile('default'),
    *(
        profile(
            f'd{td}_f{fd}_flow{flow}_parity{parity}',
            TILE_DATA_WIDTH=td,
            NOC_FLIT_DATA_WIDTH=fd,
            NOC_FLOW_CONTROL=flow,
            ENABLE_LINK_PARITY=parity,
            ASYNC_RESET=(td // 32 + fd // 32 + parity) % 2,
            NUM_TX_CHANNELS=(1, 2, 4, 8)[(td // 32 + fd // 32) % 4],
            NUM_RX_CHANNELS=(8, 4, 2, 1)[(td // 32 + fd // 32) % 4],
            NUM_VCS=(1, 2, 4)[(td // 32 + fd // 32) % 3],
            TX_QUEUE_DEPTH=(1, 2, 4, 8)[(td // 32 + fd // 32) % 4],
            RX_QUEUE_DEPTH=(8, 4, 2, 1)[(td // 32 + fd // 32) % 4],
            RX_VC_DEPTH=(1, 2, 4, 8)[(td // 32 + fd // 32 + 1) % 4],
            TX_INITIAL_CREDITS_PER_VC=(1, 2, 4, 8)[(td // 32 + fd // 32 + 2) % 4],
        )
        for td, fd, flow, parity in product((32, 64, 128, 256), (32, 64, 128), (0, 1), (0, 1))
    ),
    *(
        profile(
            f'edge{index}_flow{flow}_r{reset}',
            **geometry,
            NOC_FLOW_CONTROL=flow,
            ASYNC_RESET=reset,
            ENABLE_LINK_PARITY=reset,
        )
        for index, geometry in enumerate(
            (
                dict(
                    NUM_TX_CHANNELS=3,
                    NUM_RX_CHANNELS=5,
                    NUM_VCS=3,
                    NUM_TRAFFIC_CLASSES=5,
                    TILE_DATA_WIDTH=40,
                    NOC_FLIT_DATA_WIDTH=24,
                    TX_QUEUE_DEPTH=3,
                    RX_QUEUE_DEPTH=3,
                    RX_VC_DEPTH=3,
                    TX_INITIAL_CREDITS_PER_VC=3,
                    LOCAL_NODE_ID=7,
                ),
                dict(
                    NUM_TX_CHANNELS=1,
                    NUM_RX_CHANNELS=1,
                    NUM_VCS=1,
                    NUM_TRAFFIC_CLASSES=1,
                    TILE_DATA_WIDTH=8,
                    NOC_FLIT_DATA_WIDTH=128,
                    TX_QUEUE_DEPTH=1,
                    RX_VC_DEPTH=1,
                    RX_QUEUE_DEPTH=1,
                    NODE_ID_WIDTH=1,
                    ENDPOINT_ID_WIDTH=1,
                    CONTEXT_ID_WIDTH=1,
                    MESSAGE_TYPE_WIDTH=1,
                    PACKET_ID_WIDTH=1,
                    USER_METADATA_WIDTH=1,
                    ERROR_WIDTH=1,
                    LINK_EPOCH_WIDTH=1,
                    TX_INITIAL_CREDITS_PER_VC=1,
                ),
                dict(
                    NUM_TX_CHANNELS=2,
                    NUM_RX_CHANNELS=3,
                    NUM_VCS=4,
                    NUM_TRAFFIC_CLASSES=3,
                    TILE_DATA_WIDTH=24,
                    NOC_FLIT_DATA_WIDTH=16,
                    TRAFFIC_CLASS_TO_VC=63,
                    LINK_EPOCH_WIDTH=3,
                    TX_INITIAL_CREDITS_PER_VC=1,
                ),
            )
        )
        for flow, reset in product((0, 1), (0, 1))
    ),
)
POSITIVE = (
    'NUM_TX_CHANNELS',
    'NUM_RX_CHANNELS',
    'TILE_DATA_WIDTH',
    'NOC_FLIT_DATA_WIDTH',
    'TX_QUEUE_DEPTH',
    'RX_VC_DEPTH',
    'RX_QUEUE_DEPTH',
    'NUM_VCS',
    'NUM_TRAFFIC_CLASSES',
    'NODE_ID_WIDTH',
    'ENDPOINT_ID_WIDTH',
    'CONTEXT_ID_WIDTH',
    'MESSAGE_TYPE_WIDTH',
    'PACKET_ID_WIDTH',
    'USER_METADATA_WIDTH',
    'ERROR_WIDTH',
    'LINK_EPOCH_WIDTH',
)
INVALID = (
    tuple(
        (f'{key}_{label}', {key: value})
        for key in POSITIVE
        for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))
    )
    + tuple(
        (f'{key}_{label}', {key: value})
        for key in ('ASYNC_RESET', 'ENABLE_LINK_PARITY', 'NOC_FLOW_CONTROL')
        for label, value in (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))
    )
    + (
        ('tile_not_bytes', dict(TILE_DATA_WIDTH=15)),
        ('flit_not_bytes', dict(NOC_FLIT_DATA_WIDTH=7)),
        ('tx_endpoints', dict(NUM_TX_CHANNELS=5, ENDPOINT_ID_WIDTH=2)),
        ('rx_endpoints', dict(NUM_RX_CHANNELS=5, ENDPOINT_ID_WIDTH=2)),
        ('node_negative', dict(LOCAL_NODE_ID=-1)),
        ('node_overflow', dict(LOCAL_NODE_ID=256)),
        ('node_unknown', dict(LOCAL_NODE_ID="32'bx")),
        ('credit_zero', dict(NOC_FLOW_CONTROL=1, TX_INITIAL_CREDITS_PER_VC=0)),
        ('credit_negative', dict(NOC_FLOW_CONTROL=1, TX_INITIAL_CREDITS_PER_VC=-1)),
        ('credit_unknown', dict(NOC_FLOW_CONTROL=1, TX_INITIAL_CREDITS_PER_VC="32'bx")),
        ('short_map', dict(TRAFFIC_CLASS_TO_VC="7'h0")),
        ('long_map', dict(TRAFFIC_CLASS_TO_VC="9'h0")),
        ('unknown_map', dict(TRAFFIC_CLASS_TO_VC="8'bx")),
        ('z_map', dict(TRAFFIC_CLASS_TO_VC="8'bz")),
        ('range_map', dict(NUM_VCS=3, TRAFFIC_CLASS_TO_VC="16'h3")),
        ('storage_overflow', dict(TILE_DATA_WIDTH=1073741824)),
        ('product_overflow', dict(NUM_VCS=1073741824, NUM_TRAFFIC_CLASSES=1073741824)),
    )
)


def run_profile(task):
    args, build, rtl, index, name, parameters = task
    print('Running', name, flush=True)
    prefix = (
        '-Ptile_network_interface.' if args.sim == 'icarus' else '-pvalue+tile_network_interface.'
    )
    vw = max(1, (parameters['NUM_VCS'] - 1).bit_length())
    overrides = parameters | dict(
        TRAFFIC_CLASS_TO_VC=f"{parameters['NUM_TRAFFIC_CLASSES'] * vw}'h{parameters['TRAFFIC_CLASS_TO_VC']:x}"
    )
    flags = ' '.join(shlex.quote(f'{prefix}{k}={v}') for k, v in overrides.items())
    result, log, results, coverage = run_simulation(
        args,
        ROOT,
        TEST_DIR,
        'tile_network_interface',
        'test_tile_network_interface',
        'TileNetworkInterfaceTest',
        build / name,
        ' '.join(map(str, (*DEPENDENCIES, rtl))),
        parameters=parameters,
        compile_args=f'{args.compile_args} {flags}',
        environment={
            **{f'TILE_NETWORK_INTERFACE_{key}': str(value) for key, value in parameters.items()},
            'TILE_NETWORK_INTERFACE_SEED': str(args.seed + index),
            'TILE_NETWORK_INTERFACE_RANDOM_CYCLES': str(args.random_cycles),
        },
    )
    row = dict(
        name=name, parameters=parameters, seed=args.seed + index, status='FAIL', log=str(log)
    )
    try:
        if result.returncode:
            raise ValueError(f'make exited {result.returncode}')
        passed_test(results, 'TileNetworkInterfaceTest', 'test_tile_network_interface')
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
        for accounting in data['accounting'].values():
            if (
                accounting['pending']
                or accounting['accepted'] != accounting['completed'] + accounting['canceled']
            ):
                raise ValueError('Ownership accounting mismatch')
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
        'tile_network_interface',
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
        jobs = int(os.getenv('TILE_NETWORK_INTERFACE_JOBS', '4' if args.sim == 'icarus' else '1'))
        if not 1 <= jobs <= 32:
            raise ValueError('TILE_NETWORK_INTERFACE_JOBS must be between 1 and 32')
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
                'tile_network_interface',
                name,
                values,
                'tile_network_interface_parameters_must_be_valid',
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
        finish_summary(output, summary, 'Tile-network-interface')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
