"""NoC router width/topology/flow/protection matrix with independent PyUVM ledgers."""

from datetime import UTC, datetime
import hashlib
from itertools import product
import json
from pathlib import Path
import shlex
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
from noc_router.config import DEFAULTS

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(
    ROOT / f'src/rtl/{name}.sv'
    for name in (
        'building_blocks/noc_router_pkg',
        'common/dff',
        'common/counter',
        'common/decoder',
        'common/mux',
        'common/operand_isolation',
        'common/priority_encoder',
        'basic/fifo',
        'basic/parity',
        'basic/ecc',
        'basic/round_robin_arbiter',
        'building_blocks/event_barrier_state',
        'building_blocks/event_barrier_queue',
        'building_blocks/noc_router_codec',
        'building_blocks/noc_router_buffer',
    )
)


def parameters(**overrides):
    p = DEFAULTS | overrides
    vw = max(1, (p['NUM_VCS'] - 1).bit_length())
    p.setdefault(
        'TRAFFIC_CLASS_TO_VC',
        sum((c % p['NUM_VCS']) << (c * vw) for c in range(p['NUM_TRAFFIC_CLASSES'])),
    )
    p.setdefault(
        'TRAFFIC_CLASS_TO_SERVICE', sum((c % 2) << c for c in range(p['NUM_TRAFFIC_CLASSES']))
    )
    return p


def profiles():
    rows = []
    for index, (flow, routing, pipeline, protection) in enumerate(
        product((0, 1), (0, 1), (0, 1), (0, 1, 2))
    ):
        name = f'core_f{flow}_r{routing}_p{pipeline}_b{protection}'
        rows.append(
            (
                name,
                parameters(
                    FLOW_CONTROL=flow,
                    ROUTING_ALGORITHM=routing,
                    OUTPUT_PIPELINE=pipeline,
                    BUFFER_PROTECTION=protection,
                    ROUTER_X=1,
                    ROUTER_Y=1,
                    NUM_VCS=(1, 2, 4)[index % 3],
                    INPUT_VC_DEPTH=(1, 2, 4, 8)[index % 4],
                    OUTPUT_INITIAL_CREDITS=(1, 2, 4, 8)[index % 4],
                    FLIT_DATA_WIDTH=(32, 64, 128)[(index // 3) % 3],
                    ENABLE_QOS=index % 2,
                    ENABLE_LINK_PARITY=(index // 2) % 2,
                    ASYNC_RESET=(index // 3) % 2,
                ),
            )
        )
    # Every boundary coordinate in each required mesh, rather than one generic edge.
    for mesh in (2, 4, 8):
        for x, y in product(range(mesh), repeat=2):
            if x not in (0, mesh - 1) and y not in (0, mesh - 1):
                continue
            name = f'mesh{mesh}_x{x}_y{y}'
            rows.append(
                (
                    name,
                    parameters(
                        MESH_X=mesh,
                        MESH_Y=mesh,
                        ROUTER_X=x,
                        ROUTER_Y=y,
                        NUM_VCS=1,
                        INPUT_VC_DEPTH=1,
                        OUTPUT_INITIAL_CREDITS=1,
                        FLOW_CONTROL=(x + y) % 2,
                        ROUTING_ALGORITHM=(x + y + 1) % 2,
                        ASYNC_RESET=(x + y) % 2,
                        ENABLE_QOS=0,
                        OUTPUT_PIPELINE=(x + y + 1) % 2,
                    ),
                )
            )
    rows += [
        (
            'mesh8_interior',
            parameters(MESH_X=8, MESH_Y=8, ROUTER_X=3, ROUTER_Y=4, NUM_VCS=4, ROUTING_ALGORITHM=1),
        ),
        (
            'odd_geometry',
            parameters(
                MESH_X=3,
                MESH_Y=5,
                ROUTER_X=1,
                ROUTER_Y=2,
                NUM_VCS=3,
                NUM_TRAFFIC_CLASSES=9,
                TRAFFIC_CLASS_WIDTH=4,
                INPUT_VC_DEPTH=3,
                OUTPUT_INITIAL_CREDITS=3,
                ROUTING_ALGORITHM=1,
            ),
        ),
        (
            'single_node',
            parameters(
                MESH_X=1,
                MESH_Y=1,
                NUM_VCS=1,
                FLOW_CONTROL=0,
                ENABLE_QOS=0,
                HIGH_SERVICE_BURST_LIMIT=0,
                FLIT_DATA_WIDTH=8,
                OUTPUT_PIPELINE=0,
                LINK_EPOCH_WIDTH=1,
            ),
        ),
        (
            'wide_secded',
            parameters(
                FLIT_DATA_WIDTH=256,
                BUFFER_PROTECTION=2,
                ENABLE_LINK_PARITY=1,
                INPUT_VC_DEPTH=1,
                OUTPUT_INITIAL_CREDITS=1,
            ),
        ),
        (
            'custom_class_map',
            parameters(
                NUM_VCS=3,
                NUM_TRAFFIC_CLASSES=3,
                TRAFFIC_CLASS_WIDTH=2,
                TRAFFIC_CLASS_TO_VC=0b100100,
                TRAFFIC_CLASS_TO_SERVICE=0b100,
                HIGH_SERVICE_BURST_LIMIT=1,
                FLOW_CONTROL=0,
                ROUTER_X=2,
                ROUTER_Y=2,
                BUFFER_PROTECTION=1,
            ),
        ),
    ]
    return tuple(rows)


PROFILES = profiles()
POSITIVE = (
    'MESH_X',
    'MESH_Y',
    'FLIT_DATA_WIDTH',
    'NUM_VCS',
    'INPUT_VC_DEPTH',
    'OUTPUT_INITIAL_CREDITS',
    'NUM_TRAFFIC_CLASSES',
    'NODE_ID_WIDTH',
    'ENDPOINT_ID_WIDTH',
    'CONTEXT_ID_WIDTH',
    'MESSAGE_TYPE_WIDTH',
    'TRAFFIC_CLASS_WIDTH',
    'PACKET_ID_WIDTH',
    'FRAGMENT_INDEX_WIDTH',
    'USER_METADATA_WIDTH',
    'ERROR_WIDTH',
    'LINK_EPOCH_WIDTH',
)
BOOLEANS = ('ENABLE_QOS', 'ENABLE_LINK_PARITY', 'OUTPUT_PIPELINE', 'ASYNC_RESET')
INVALID = (
    *(
        (f'{name.lower()}_{label}', {name: value})
        for name, (label, value) in product(
            POSITIVE, (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))
        )
    ),
    *(
        (f'{name.lower()}_{label}', {name: value})
        for name, (label, value) in product(
            BOOLEANS, (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))
        )
    ),
    ('router_x_negative', dict(ROUTER_X=-1)),
    ('router_y_negative', dict(ROUTER_Y=-1)),
    ('router_x_boundary', dict(ROUTER_X=4)),
    ('router_y_boundary', dict(ROUTER_Y=4)),
    ('flow_control_reserved', dict(FLOW_CONTROL=2)),
    ('routing_reserved', dict(ROUTING_ALGORITHM=2)),
    ('protection_reserved', dict(BUFFER_PROTECTION=3)),
    ('burst_zero', dict(HIGH_SERVICE_BURST_LIMIT=0)),
    ('byte_alignment', dict(FLIT_DATA_WIDTH=9)),
    ('node_encoding', dict(NODE_ID_WIDTH=3)),
    ('class_encoding', dict(NUM_TRAFFIC_CLASSES=9)),
    ('credit_epoch', dict(LINK_EPOCH_WIDTH=1)),
    ('vc_map_range', dict(NUM_VCS=3, TRAFFIC_CLASS_TO_VC="16'h0003")),
    ('vc_map_unknown', dict(TRAFFIC_CLASS_TO_VC="8'bx")),
    ('service_map_unknown', dict(TRAFFIC_CLASS_TO_SERVICE="8'bx")),
    ('geometry_overflow', dict(NUM_VCS=1073741824, INPUT_VC_DEPTH=1073741824)),
    ('mesh_overflow', dict(MESH_X="64'd4294967296", MESH_Y="64'd4294967296")),
)


def simulate(args, build, rtl, p, seed):
    prefix = '-Pnoc_router.' if args.sim == 'icarus' else '-pvalue+noc_router.'
    flags = ' '.join(shlex.quote(f'{prefix}{key}={value}') for key, value in p.items())
    return run_simulation(
        args,
        ROOT,
        TEST_DIR,
        'noc_router',
        'test_noc_router',
        'RouterTest',
        build,
        ' '.join(map(str, (*DEPENDENCIES, rtl))),
        parameters=p,
        compile_args=f'{args.compile_args} {flags}',
        environment={
            **{f'NOC_ROUTER_{key}': str(value) for key, value in p.items()},
            'NOC_ROUTER_SEED': str(seed),
            'NOC_ROUTER_RANDOM_CYCLES': str(args.random_cycles),
            'NOC_ROUTER_HDL_ASSERTIONS': '1',
        },
    )


def main():
    args = parse_args(
        'noc_router',
        __doc__,
        profiles=[name for name, _ in PROFILES],
        seed=20261022,
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
        specification='specs/building-blocks/mosaic-noc-router/README.md',
        started_at_utc=datetime.now(UTC).isoformat(),
        external_checks=dict.fromkeys(
            (
                'formal_network',
                'tni_integration',
                'commercial_lint',
                'cdc',
                'rdc',
                'dft',
                'vc_lp',
                'technology_synthesis',
                'sequential_equivalence',
                'physical_timing',
                'physical_power',
                'mosaic_contracts',
            ),
            'NOT_RUN',
        ),
    )
    try:
        summary['rtl_sha256'] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary['dependency_sha256'] = {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in DEPENDENCIES
        }
        summary['verification_sha256'] = verification_hashes(TEST_DIR)
        require_simulator(args)
        for index, (name, p) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            print('Running', name, flush=True)
            result, log, results, coverage = simulate(args, build / name, rtl, p, args.seed + index)
            row = dict(name=name, parameters=p, status='FAIL', log=str(log))
            try:
                if result.returncode:
                    raise ValueError(f'make exited {result.returncode}')
                passed_test(results, 'RouterTest', 'test_noc_router')
                data = json.loads(coverage.read_text())
                if (
                    data['status'] != 'PASS'
                    or data['parameters'] != p
                    or not data['goals']
                    or not all(data['goals'].values())
                    or data['random_transactions'] != args.random_cycles
                    or data['seed'] != args.seed + index
                ):
                    raise ValueError('Coverage evidence mismatch')
                row.update(data, name=name, log=str(log), coverage=str(coverage))
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                row['error'] = str(error)
                if license_unavailable(log.read_text()):
                    row['status'] = 'NOT_RUN'
                print('\n'.join(log.read_text().splitlines()[-20:]), flush=True)
            summary['profiles'].append(row)
            print(name, row['status'], flush=True)
        summary['parameter_checks'] = [
            parameter_guard(
                args,
                build,
                rtl,
                'noc_router',
                name,
                p,
                'noc_router_parameters_must_be_valid',
                dependencies=DEPENDENCIES,
            )
            for name, p in INVALID
        ]
        complete = len(summary['profiles']) == (
            len(set(args.case)) if args.case else len(PROFILES)
        ) and len(summary['parameter_checks']) == len(INVALID)
        summary['status'] = campaign_status(
            (*summary['profiles'], *summary['parameter_checks']), complete
        )
    except (OSError, ValueError) as error:
        summary['error'] = str(error)
        print(error, file=sys.stderr)
    finally:
        finish_summary(output, summary, 'NoC router')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
