"""Lint and synthesize every ALU profile, checking combinational structure."""

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from run_scalar_alu_regression import ROOT, TEST_DIR, DEPENDENCIES, PROFILES
from mosaic_uvm.regression import verification_hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--yosys', default='yosys')
    parser.add_argument('--verilator', default='verilator')
    parser.add_argument('--build-dir', required=True, type=Path)
    parser.add_argument('--case', action='append', choices=[name for name, _ in PROFILES])
    args = parser.parse_args()
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    sources = (*DEPENDENCIES, ROOT / 'src/rtl/building_blocks/scalar_alu.sv')
    summary = dict(
        status='NOT_RUN',
        profiles=[],
        started_at_utc=datetime.now(UTC).isoformat(),
        source_sha256={
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources
        },
        verification_sha256=verification_hashes(TEST_DIR),
        technology_mapping='NOT_RUN',
        commercial_lint='NOT_RUN',
        cdc='NOT_RUN',
        rdc='NOT_RUN',
        physical_timing='NOT_RUN',
        physical_power='NOT_RUN',
    )
    try:
        yosys, verilator = shutil.which(args.yosys), shutil.which(args.verilator)
        if yosys is None or verilator is None:
            raise FileNotFoundError('Static checks require Verilator and Yosys with slang')
        summary['yosys_version'] = subprocess.check_output([yosys, '-V'], text=True).strip()
        summary['verilator_version'] = subprocess.check_output(
            [verilator, '--version'], text=True
        ).strip()
        for name, p in PROFILES:
            if args.case and name not in args.case:
                continue
            case = build / name
            case.mkdir(exist_ok=True)
            row = dict(name=name, parameters=p, status='FAIL')
            log = case / 'lint.log'
            with log.open('w') as output:
                lint = subprocess.run(
                    [
                        verilator,
                        '--lint-only',
                        '--top-module',
                        'scalar_alu',
                        '-Wall',
                        *(f'-G{k}={v}' for k, v in p.items()),
                        *map(str, sources),
                    ],
                    stdout=output,
                    stderr=subprocess.STDOUT,
                )
            row.update(lint='PASS' if lint.returncode == 0 else 'FAIL', lint_log=str(log))
            script = (
                'read_slang --top scalar_alu '
                + ' '.join(f'-G{k}={v}' for k, v in p.items())
                + ' '
                + ' '.join(str(path.relative_to(ROOT)) for path in sources)
                + '\nprep -top scalar_alu -flatten\nopt\ncheck -assert\nscc -expect 0\nstat\n'
                + 'write_json netlist.json\n'
            )
            # read_slang gets repository-relative inputs; standard Yosys output
            # commands accept quoted absolute destinations, including external builds.
            script = script.replace(
                'write_json netlist.json', 'write_json ' + json.dumps(str(case / 'netlist.json'))
            )
            (case / 'synth.ys').write_text(script)
            log = case / 'synth.log'
            with log.open('w') as output:
                synth = subprocess.run(
                    [yosys, '-Q', '-T', '-s', str(case / 'synth.ys')],
                    cwd=ROOT,
                    stdout=output,
                    stderr=subprocess.STDOUT,
                )
            row.update(
                generic_synthesis='PASS' if synth.returncode == 0 else 'FAIL', synth_log=str(log)
            )
            if synth.returncode == 0:
                netlist = json.loads((case / 'netlist.json').read_text())['modules']['scalar_alu']
                types = {cell['type'].lower() for cell in netlist['cells'].values()}
                forbidden = {
                    kind
                    for kind in types
                    if any(
                        token in kind
                        for token in ('dff', 'latch', 'mem', '$mul', '$div', '$mod', 'blackbox')
                    )
                }
                row['forbidden_cells'] = sorted(forbidden)
                row['cell_count'] = len(netlist['cells'])
                row['cell_types'] = sorted(types)
                no_clock_reset = not any(
                    'clk' in port or 'rst' in port for port in netlist['ports']
                )
                row['combinational_structure'] = (
                    'PASS' if not forbidden and no_clock_reset else 'FAIL'
                )
                if lint.returncode == 0 and row['combinational_structure'] == 'PASS':
                    row['status'] = 'PASS'
            summary['profiles'].append(row)
            print(name, row['status'], flush=True)
        count = len(set(args.case)) if args.case else len(PROFILES)
        if len(summary['profiles']) == count and all(
            p['status'] == 'PASS' for p in summary['profiles']
        ):
            summary['status'] = 'PASS'
        else:
            summary['status'] = 'FAIL'
    except (FileNotFoundError, subprocess.SubprocessError) as error:
        summary['error'] = str(error)
    except (OSError, ValueError, KeyError, AssertionError) as error:
        summary['status'] = 'FAIL'
        summary['error'] = str(error)
    finally:
        summary['finished_at_utc'] = datetime.now(UTC).isoformat()
        (build / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(f'Scalar ALU static {summary["status"]}: {build / "summary.json"}')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
