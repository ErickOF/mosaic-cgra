"""Run actual 2x2/4x4 router meshes with independent end-to-end PyUVM ledgers."""

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shlex
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lib'))
from mosaic_uvm.regression import (
    parse_args,
    require_simulator,
    run_simulation,
    passed_test,
    campaign_status,
    finish_summary,
    license_unavailable,
    verification_hashes,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from run_noc_router_regression import ROOT, TEST_DIR, DEPENDENCIES, parameters

PROFILES = (
    (
        'mesh2_ready_xy',
        dict(MESH_X=2, MESH_Y=2, NUM_VCS=1, FLOW_CONTROL=0, ROUTING_ALGORITHM=0, ASYNC_RESET=0),
    ),
    (
        'mesh2_credit_yx',
        dict(MESH_X=2, MESH_Y=2, NUM_VCS=2, FLOW_CONTROL=1, ROUTING_ALGORITHM=1, ASYNC_RESET=1),
    ),
    (
        'mesh4_ready_yx',
        dict(MESH_X=4, MESH_Y=4, NUM_VCS=2, FLOW_CONTROL=0, ROUTING_ALGORITHM=1, ASYNC_RESET=1),
    ),
    (
        'mesh4_credit_xy',
        dict(MESH_X=4, MESH_Y=4, NUM_VCS=1, FLOW_CONTROL=1, ROUTING_ALGORITHM=0, ASYNC_RESET=0),
    ),
)


def simulate(args, build, rtl, geometry, seed):
    p = parameters(**geometry)
    prefix = '-Pnoc_router_mesh_tb.' if args.sim == 'icarus' else '-pvalue+noc_router_mesh_tb.'
    flags = ' '.join(shlex.quote(f'{prefix}{key}={value}') for key, value in geometry.items())
    define = (
        '-DMOSAIC_NOC_ROUTER_ASSERTIONS'
        if args.sim == 'icarus'
        else '+define+MOSAIC_NOC_ROUTER_ASSERTIONS'
    )
    sources = (
        *DEPENDENCIES,
        rtl,
        ROOT / 'src/rtl/basic/skid_buffer.sv',
        TEST_DIR / 'noc_router_mesh_tb.sv',
        TEST_DIR / 'noc_router_assertions.sv',
    )
    return run_simulation(
        args,
        ROOT,
        TEST_DIR,
        'noc_router_mesh_tb',
        'test_noc_router_mesh',
        'MeshTest',
        build,
        ' '.join(map(str, sources)),
        parameters=p,
        compile_args=f'{args.compile_args} {define} {flags}',
        environment={
            **{f'NOC_ROUTER_{key}': str(value) for key, value in p.items()},
            'NOC_ROUTER_SEED': str(seed),
            'NOC_ROUTER_RANDOM_CYCLES': str(args.random_cycles),
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
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    output = build / 'summary.json'
    output.unlink(missing_ok=True)
    sources = (*DEPENDENCIES, args.rtl, ROOT / 'src/rtl/basic/skid_buffer.sv')
    summary = dict(
        status='NOT_RUN',
        profiles=[],
        framework='PyUVM',
        simulator=args.sim,
        started_at_utc=datetime.now(UTC).isoformat(),
        verification_sha256=verification_hashes(TEST_DIR),
        source_sha256={
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sources
        },
        tni_integration='NOT_RUN',
    )
    try:
        require_simulator(args)
        for index, (name, geometry) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            print('Running', name, flush=True)
            result, log, results, coverage = simulate(
                args, build / name, args.rtl, geometry, args.seed + index
            )
            row = dict(name=name, status='FAIL', log=str(log))
            try:
                if result.returncode:
                    raise ValueError(f'make exited {result.returncode}')
                passed_test(results, 'MeshTest', 'test_noc_router_mesh')
                data = json.loads(coverage.read_text())
                if (
                    data['status'] != 'PASS'
                    or not all(data['goals'].values())
                    or data['parameters'] != parameters(**geometry)
                    or data['random_transactions'] != args.random_cycles
                ):
                    raise ValueError('Mesh coverage evidence mismatch')
                row.update(data, name=name, coverage=str(coverage), log=str(log))
            except (ValueError, OSError, KeyError, ET.ParseError) as error:
                row['error'] = str(error)
                if license_unavailable(log.read_text()):
                    row['status'] = 'NOT_RUN'
                print('\n'.join(log.read_text().splitlines()[-25:]), flush=True)
            summary['profiles'].append(row)
            print(name, row['status'], flush=True)
        summary['status'] = campaign_status(
            summary['profiles'],
            len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES)),
        )
    except (OSError, ValueError) as error:
        summary['error'] = str(error)
    finally:
        finish_summary(output, summary, 'NoC mesh')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
