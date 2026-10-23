"""Prove all ALU outputs for arbitrary two-state inputs in the release profiles.

Requires Yosys with the slang frontend. Four-state containment is checked by
simulation; these combinational proofs do not qualify physical timing or power.
"""

import argparse
from datetime import UTC, datetime
import hashlib
from itertools import product
import json
from pathlib import Path
import shutil
import subprocess
import sys

from run_scalar_alu_regression import ROOT, TEST_DIR, DEPENDENCIES, DEFAULTS
from mosaic_uvm.regression import verification_hashes

PROFILES = tuple(
    (f'w{w}_s{s}_m{m}', DEFAULTS | dict(DATA_WIDTH=w, SUPPORT_SATURATION=s, SUPPORT_MINMAX=m))
    for w, s, m in product((1, 2, 3, 4, 5, 8, 16, 32, 64), range(2), range(2))
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--yosys', default='yosys')
    parser.add_argument('--build-dir', required=True, type=Path)
    parser.add_argument('--case', action='append', choices=[name for name, _ in PROFILES])
    parser.add_argument('--timeout', type=int, default=120)
    args = parser.parse_args()
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    sources = (
        *DEPENDENCIES,
        ROOT / 'src/rtl/building_blocks/scalar_alu.sv',
        TEST_DIR / 'scalar_alu_assertions.sv',
    )
    summary = dict(
        status='NOT_RUN',
        profiles=[],
        started_at_utc=datetime.now(UTC).isoformat(),
        scope='All opcodes, operands, enable and mode controls; two-state combinational inputs',
        source_sha256={
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sources
        },
        verification_sha256=verification_hashes(TEST_DIR),
        technology_mapping='NOT_RUN',
        physical_timing='NOT_RUN',
        physical_power='NOT_RUN',
    )
    tool = shutil.which(args.yosys)
    try:
        if tool is None:
            raise FileNotFoundError(f'Yosys executable missing: {args.yosys}')
        summary['tool_version'] = subprocess.check_output([tool, '-V'], text=True).strip()
        for name, p in PROFILES:
            if args.case and name not in args.case:
                continue
            case = build / name
            case.mkdir(exist_ok=True)
            script = (
                'read_slang --top scalar_alu -D FORMAL -D MOSAIC_SCALAR_ALU_ASSERTIONS '
                + ' '.join(f'-G{key}={value}' for key, value in p.items())
                + ' '
                + ' '.join(str(path.relative_to(ROOT)) for path in sources)
                + '\nprep -top scalar_alu -flatten\nchformal -lower\nopt\ncheck -assert\n'
                + 'sat -verify -prove-asserts -set-def-inputs -show-inputs -show-outputs\n'
            )
            (case / 'prove.ys').write_text(script)
            log = case / 'formal.log'
            row = dict(name=name, parameters=p, status='FAIL', log=str(log))
            try:
                with log.open('w') as output:
                    result = subprocess.run(
                        [tool, '-Q', '-T', '-s', str(case / 'prove.ys')],
                        stdout=output,
                        stderr=subprocess.STDOUT,
                        timeout=args.timeout,
                        cwd=ROOT,
                    )
                text = log.read_text()
                if (
                    result.returncode == 0
                    and 'SAT proof finished - no model found: SUCCESS!' in text
                ):
                    row['status'] = 'PASS'
                elif 'No such command: read_slang' in text:
                    row['status'] = 'NOT_RUN'
                    row['error'] = 'Yosys slang frontend unavailable'
            except subprocess.TimeoutExpired:
                row['status'] = 'NOT_RUN'
                row['error'] = f'Proof exceeded {args.timeout} seconds'
            summary['profiles'].append(row)
            print(name, row['status'], flush=True)
        expected = len(set(args.case)) if args.case else len(PROFILES)
        rows = summary['profiles']
        if len(rows) == expected and all(row['status'] == 'PASS' for row in rows):
            summary['status'] = 'PASS'
        elif any(row['status'] == 'FAIL' for row in rows):
            summary['status'] = 'FAIL'
    except (OSError, subprocess.SubprocessError) as error:
        summary['error'] = str(error)
    finally:
        summary['finished_at_utc'] = datetime.now(UTC).isoformat()
        (build / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(f'Scalar ALU formal {summary["status"]}: {build / "summary.json"}', flush=True)
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
