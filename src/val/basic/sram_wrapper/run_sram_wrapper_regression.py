"""Run masked memory, fixed-latency, read-credit and replaceable-backend campaigns."""

from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import shlex
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lib'))
from mosaic_uvm.regression import (
    campaign_status, finish_summary, license_unavailable, parameter_guard, parse_args,
    passed_test, require_simulator, run_simulation, verification_hashes,
)

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT/f'src/rtl/common/{name}.sv' for name in ('dff', 'counter', 'decoder', 'operand_isolation'))


def geometry(width,depth,granule,tag,latency,credits,asynchronous):
    return f'w{width}_d{depth}_g{granule}_t{tag}_l{latency}_c{credits}_a{asynchronous}',dict(
        DATA_WIDTH=width,DEPTH=depth,MASK_GRANULARITY=granule,TAG_WIDTH=tag,
        READ_LATENCY=latency,MAX_OUTSTANDING_READS=credits,ASYNC_RESET=asynchronous)


GEOMETRIES=(
    (1,1,1,1,1,1),(1,3,1,1,2,2),(8,1,8,1,1,2),(8,3,1,3,1,4),(8,5,8,4,2,2),
    (16,3,4,3,2,3),(16,5,1,4,3,3),(16,8,8,4,3,7),(24,5,8,4,4,4),(24,16,3,7,4,9),
    (32,1,8,4,1,1),(32,3,8,4,1,4),(32,5,8,1,2,5),(32,8,32,4,3,4),(32,31,8,7,2,4),
    (32,32,8,4,4,6),(32,33,8,4,1,8),(32,1024,8,4,1,4),(64,3,8,4,2,3),(64,16,1,4,3,7),
    (128,3,8,4,1,2),(256,5,8,7,4,9),(257,3,1,7,2,5))
PROFILES=tuple((name,p,'inferred') for name,p in (geometry(*g,a) for g,a in product(GEOMETRIES,(0,1))))+tuple(
    ('reference_'+name,p,'reference') for name,p in (geometry(*g,a) for g,a in product(
        (GEOMETRIES[0],GEOMETRIES[3],GEOMETRIES[5],GEOMETRIES[7]),(0,1))))
INVALID=(
    *((f'{name.lower()}_{label}',{name:value}) for name in ('DATA_WIDTH','DEPTH','MASK_GRANULARITY','TAG_WIDTH','READ_LATENCY','MAX_OUTSTANDING_READS')
      for label,value in (('zero',0),('negative',-1),('x',"32'bx"),('z',"32'bz"))),
    ('mask_uneven',dict(MASK_GRANULARITY=3)),('mask_too_wide',dict(MASK_GRANULARITY=64)),
    ('insufficient_credits',dict(READ_LATENCY=3,MAX_OUTSTANDING_READS=2)),
    *((f'async_reset_{label}',dict(ASYNC_RESET=value)) for label,value in (('two',2),('negative',-1),('x',"32'bx"),('z',"32'bz"))),
)
PROBE_PARAMETERS=geometry(8,3,2,3,2,3,0)[1]
PROBES=(
    *((f'{name}:{state}:0',name,dict(ASYNC_RESET=a)) for name,state,a in product(
        ('i_rstb','i_flush','i_req_valid','i_rsp_ready','i_req_write'),'xz',(0,1))),
    *((f'{name}:{state}:{bit}',name,dict(ASYNC_RESET=a)) for name,width in (('i_req_addr',2),('i_req_wmask',4))
      for state,bit,a in product('xz',range(width),(0,1))),
    *((f'enabled_write_data:{state}:{bit}','enabled_write_data',dict(ASYNC_RESET=a)) for state,bit,a in product('xz',range(8),(0,1))),
    *((f'read_tag:{state}:{bit}','read_tag',dict(ASYNC_RESET=a)) for state,bit,a in product('xz',range(3),(0,1))),
    *((f'{kind}:0:0','requester_stability',dict(ASYNC_RESET=a)) for kind,a in product(
        ('requester_valid','requester_i_req_write','requester_i_req_addr','requester_i_req_wdata','requester_i_req_wmask','requester_i_req_tag','requester_pulse'),(0,1))),
)
BACKENDS=dict(inferred=ROOT/'src/rtl/basic/sram_wrapper_backend.sv',reference=TEST_DIR/'sram_wrapper_model_backend.sv')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def simulate(args, build, rtl, parameters, seed, probe='', backend='inferred'):
    prefix = '-Psram_wrapper.' if args.sim == 'icarus' else '-pvalue+sram_wrapper.'
    flags = ' '.join(shlex.quote(f'{prefix}{name}={value}') for name, value in parameters.items())
    return run_simulation(args, ROOT, TEST_DIR, 'sram_wrapper', 'test_sram_wrapper', 'SramTest', build,
        ' '.join(map(str, (*DEPENDENCIES, BACKENDS[backend], rtl))), parameters=parameters, compile_args=f'{args.compile_args} {flags}',
        environment={**{f'SRAM_WRAPPER_{name}': str(value) for name, value in parameters.items()},
            'SRAM_WRAPPER_SEED': str(seed), 'SRAM_WRAPPER_RANDOM_CYCLES': str(args.random_cycles),
            'SRAM_WRAPPER_BACKEND':backend,'SRAM_WRAPPER_CHECK_INTERNALS': '1', 'SRAM_WRAPPER_ASSERTION_PROBE': probe})


def assertion_probes(args, build, rtl):
    reports = []
    for index, (probe, expected, overrides) in enumerate(PROBES):
        name = f'{index:03d}_{probe.replace(":", "_").replace(",", "_")}'
        result, log, results, _ = simulate(args, build/'assertion_probes'/name, rtl,
            PROBE_PARAMETERS | overrides, args.seed, probe)
        diagnostic = log.read_text(encoding='utf-8')
        try:
            cases = ET.parse(results).findall('.//testcase')
            rejected = (result.returncode != 0 and len(cases) == 1
                and cases[0].get('name') == 'SramTest'
                and cases[0].get('classname') == 'test_sram_wrapper'
                and cases[0].find('failure') is not None
                and f'AssertionError: Protocol assertion failed: {expected}' in diagnostic)
        except (OSError, ET.ParseError):
            rejected = False
        report = dict(name=name, expected_assertion=expected, expected_test_failure=rejected, log=str(log),
            status='NOT_RUN' if license_unavailable(diagnostic) else 'PASS' if rejected else 'FAIL')
        reports.append(report)
        print(f"Assertion {name}: {report['status']}", flush=True)
        if not rejected and report['status'] != 'NOT_RUN':
            print('\n'.join(diagnostic.splitlines()[-18:]), flush=True)
    return reports


def main():
    args = parse_args('sram_wrapper', __doc__, profiles=[name for name, _, _ in PROFILES], seed=20261019, rtl_category='basic')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    report_file = build/'summary.json'
    report_file.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, rtl=str(rtl),
        scope='selected_profiles' if args.case else 'representative_memory_latency_credit_reset_and_backend_profiles',
        specification='specs/basic/mosaic-sram-wrapper/README.md',
        started_at_utc=datetime.now(timezone.utc).isoformat(), profiles=[], parameter_checks=[], assertion_probes=[],
        external_checks=dict.fromkeys(('hdl_sva', 'formal', 'commercial_lint', 'cdc', 'rdc', 'dft', 'vc_lp',
            'technology_synthesis', 'physical_timing', 'physical_power', 'vendor_macro_equivalence', 'canonical_memory_contract', 'power_off_state_policy'), 'NOT_RUN'))
    try:
        summary['rtl_sha256'] = digest(rtl)
        summary['dependency_sha256'] = {str(path.relative_to(ROOT)): digest(path) for path in DEPENDENCIES}
        summary['verification_sha256'] = verification_hashes(TEST_DIR)
        summary['backend_sha256'] = {name:digest(path) for name,path in BACKENDS.items()}
        require_simulator(args)
        summary['status'] = 'FAIL'
        for index, (name, parameters, backend) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            print(f'Running {name}, seed={args.seed + index}', flush=True)
            result, log, results, coverage_file = simulate(args, build/name, rtl, parameters, args.seed + index, backend=backend)
            report = dict(name=name, status='FAIL', parameters=parameters, log=str(log))
            try:
                if result.returncode:
                    raise ValueError(f'make exited with status {result.returncode}')
                passed_test(results, 'SramTest', 'test_sram_wrapper')
                coverage = json.loads(coverage_file.read_text(encoding='utf-8'))
                if (coverage['status'] != 'PASS' or coverage['parameters'] != parameters or coverage['backend'] != backend or not coverage['goals']
                        or not all(coverage['goals'].values()) or coverage['elaboration_assertions'] != 'PASS'
                        or coverage['internal_storage_assertions'] != 'PASS'):
                    raise ValueError('Coverage or elaborated geometry did not match')
                if coverage['seed'] != args.seed + index or coverage['random_transactions'] != args.random_cycles:
                    raise ValueError('Campaign random settings did not match')
                report.update(coverage, name=name, log=str(log), coverage=str(coverage_file))
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                report['error'] = str(error)
                if license_unavailable(log.read_text(encoding='utf-8')):
                    report['status'] = 'NOT_RUN'
                print('\n'.join(log.read_text().splitlines()[-25:]), flush=True)
            summary['profiles'].append(report)
            print(f"{name}: {report['status']}", flush=True)
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'sram_wrapper', name, parameters,
            'sram_wrapper_parameters_must_be_valid', dependencies=(*DEPENDENCIES,BACKENDS['inferred'])) for name, parameters in INVALID]
        summary['assertion_probes'] = assertion_probes(args, build, rtl)
        complete = (len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES))
            and len(summary['parameter_checks']) == len(INVALID) and len(summary['assertion_probes']) == len(PROBES))
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks'], *summary['assertion_probes']), complete)
    except (OSError, ValueError) as error:
        summary['error'] = str(error)
        print(f'SRAM-wrapper regression could not run: {error}', file=sys.stderr)
    finally:
        finish_summary(report_file, summary, 'SRAM-wrapper')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
