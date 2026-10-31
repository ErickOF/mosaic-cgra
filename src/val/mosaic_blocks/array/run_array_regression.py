"""Python-only array campaign with generated composition and source provenance."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import tomllib
ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT/'src/val'), str(HERE.parent), str(ROOT/'src/val/lib')]
spec = importlib.util.spec_from_file_location('array_generator', ROOT/'src/gen/array/generate.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)
from mosaic_uvm.regression import (parse_args, require_simulator, run_simulation,
    passed_test, verification_hashes, parameter_guard, finish_summary, campaign_status)
PROFILES = ('single', 'mvp', 'permuted', 'ungated', 'concurrent', 'partial_commit')


def descriptor_for(name):
    d = tomllib.loads((ROOT/'src/gen/array/mvp.toml').read_text())
    if name == 'single':
        d.update(profile='Array-Single-Cluster', cols=1, clusters=d['clusters'][:1])
    if name == 'permuted':
        d['array_id'] = 17
        d['clusters'][0]['id'], d['clusters'][1]['id'] = 203, 37
    if name == 'ungated': d['clock_gating'] = False
    return d


def hashes():
    paths = [ROOT/f'src/rtl/{s}.sv' for s in dict.fromkeys((*generator.cluster.SOURCES,
        *generator.NOC_SOURCES, 'mosaic_blocks/global_noc', *generator.HELPERS))]
    for directory in ('array', 'cluster', 'global_noc'):
        paths += list((ROOT/f'src/gen/{directory}').glob('*.py'))
    paths.append(ROOT/'src/gen/array/mvp.toml')
    # Include imported released codecs, models and transaction helpers in provenance.
    paths += list((ROOT/'src/val').rglob('*.py'))
    return dict(source_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths}, verification_sha256=verification_hashes(HERE))


def run_profile(task):
    args, build, name = task
    target = build/name; target.mkdir(parents=True, exist_ok=True)
    path = target/'descriptor.toml'; path.write_text(generator.toml_text(descriptor_for(name)))
    artifacts = target/'architecture'
    contract = generator.generate(path, target/'array.sv', artifacts)
    sources = ' '.join((artifacts/'sources.f').read_text().splitlines())
    result, log, xml, coverage = run_simulation(args, ROOT, HERE, 'array', 'test_array', 'ArrayTest',
        target/'simulation', sources, parameters=contract['descriptor'], environment={
            'ARRAY_ARTIFACTS': str(artifacts), 'ARRAY_SEED': str(args.seed+PROFILES.index(name)),
            'ARRAY_RANDOM_CYCLES': str(args.random_cycles), 'ARRAY_MODE': name})
    row = dict(name=name, status='FAIL', log=str(log))
    try:
        if result.returncode: raise ValueError(f'make exited {result.returncode}')
        passed_test(xml, 'ArrayTest', 'test_array')
        data = json.loads(coverage.read_text())
        if data['status'] != 'PASS' or not data['goals'] or not all(data['goals'].values()):
            raise ValueError('Missing required coverage')
        if (data['parameters'] != contract['descriptor'] or data['manifest_sha256'] != contract['manifest_sha256']
                or data['seed'] != args.seed+PROFILES.index(name) or data['random_cycles'] != args.random_cycles
                or data['hdl_assertions'] != 'NOT_RUN'):
            raise ValueError('Manifest/profile mismatch')
        row.update(data, coverage=str(coverage))
    except (OSError, ValueError, KeyError) as error:
        row['error'] = str(error)
        print('\n'.join(log.read_text().splitlines()[-24:]), flush=True)
    print(name, row['status'], flush=True)
    return row


def run_control(args, build):
    target = build/'controller'
    target.mkdir(parents=True, exist_ok=True)
    descriptor = target/'descriptor.toml'
    descriptor.write_text(generator.toml_text(descriptor_for('mvp')))
    artifacts = target/'architecture'
    contract = generator.generate(descriptor, target/'unused_array.sv', artifacts)
    sources = ' '.join(str(ROOT/f'src/rtl/{name}.sv') for name in dict.fromkeys((
        *generator.cluster.SOURCES, *generator.NOC_SOURCES, 'mosaic_blocks/global_noc', *generator.HELPERS)))
    flag = '-P' if args.sim == 'icarus' else '-pvalue+'
    result, log, xml, coverage = run_simulation(args, ROOT, HERE, 'array_control',
        'test_array_control', 'ArrayControlTest', target/'simulation', sources,
        compile_args=args.compile_args+f' {flag}array_control.TIMEOUT_CYCLES=32',
        parameters=dict(NUM_CLUSTERS=2, TIMEOUT_CYCLES=32), environment={
            'ARRAY_ARTIFACTS': str(artifacts), 'ARRAY_SEED': str(args.seed+100),
            'ARRAY_RANDOM_CYCLES': str(args.random_cycles)})
    row = dict(name='controller', status='FAIL', log=str(log))
    try:
        if result.returncode: raise ValueError(f'make exited {result.returncode}')
        passed_test(xml, 'ArrayControlTest', 'test_array_control')
        data = json.loads(coverage.read_text())
        if (data['status'] != 'PASS' or len(data['goals']) != 9 or not all(data['goals'].values())
                or data['manifest_sha256'] != contract['manifest_sha256'] or data['seed'] != args.seed+100):
            raise ValueError('Controller coverage/provenance mismatch')
        row.update(data, coverage=str(coverage), control_parameters=dict(NUM_CLUSTERS=2, TIMEOUT_CYCLES=32))
    except (OSError, ValueError, KeyError) as error:
        row['error'] = str(error)
        print(log.read_text()[-3500:], flush=True)
    print('controller', row['status'], flush=True)
    return row


def main():
    args = parse_args('array', __doc__, profiles=PROFILES, seed=20261028, rtl_category='mosaic_blocks')
    build = args.build_dir.resolve(); build.mkdir(parents=True, exist_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, profiles=[],
        parameter_checks=[], validation_mode='Python-only', synthesis='Design Compiler (deferred)', lint='NOT_RUN')
    try:
        before = hashes(); summary.update(before)
        from mosaic_blocks.array.test_model import ModelTests
        with (build/'python_model_tests.log').open('w') as log:
            result = unittest.TextTestRunner(stream=log).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(ModelTests))
        summary['python_model_checks'] = dict(status='PASS' if result.wasSuccessful() else 'FAIL', tests=result.testsRun)
        if not result.wasSuccessful(): raise ValueError('Python model tests failed')
        require_simulator(args)
        selected = [name for name in PROFILES if not args.case or name in args.case]
        # Two native clusters are more expensive than a mocked control harness.
        with ThreadPoolExecutor(max_workers=2) as pool:
            summary['profiles'] = list(pool.map(run_profile, [(args, build, name) for name in selected]))
        summary['controller'] = run_control(args, build)
        dependencies = tuple(ROOT/f'src/rtl/{s}.sv' for s in dict.fromkeys((
            *generator.cluster.SOURCES, *generator.NOC_SOURCES, 'mosaic_blocks/global_noc', *generator.HELPERS)))
        for label, values in [('zero', dict(NUM_CLUSTERS=0)), ('over', dict(NUM_CLUSTERS=5)),
                              ('negative', dict(NUM_CLUSTERS=-1)), ('unknown', dict(NUM_CLUSTERS="32'bx")),
                              ('timeout_short', dict(TIMEOUT_CYCLES=1)), ('timeout_over', dict(TIMEOUT_CYCLES=0x1000000))]:
            summary['parameter_checks'].append(parameter_guard(args, build,
                ROOT/'src/rtl/mosaic_blocks/array_control.sv', 'array_control', label, values,
                'array_control_parameters_must_be_valid', dependencies=tuple(
                    p for p in dependencies if p.name != 'array_control.sv')))
        for module, invalid in (
            ('array_events', [('zero_clusters', dict(NUM_CLUSTERS=0)),
                ('excess_clusters', dict(NUM_CLUSTERS=5)), ('zero_depth', dict(EVENT_DEPTH=0)),
                ('excess_depth', dict(EVENT_DEPTH=129)), ('duplicate_ids', dict(CLUSTER_IDS=0)),
                ('reserved_id', dict(CLUSTER_IDS=0xf000))]),
            ('array_noc_gateway', [('self_route', dict(DESTINATION_NODE=0)),
                ('bad_source', dict(SOURCE_NODE=2)), ('zero_flow', dict(FLOW_ID=0)),
                ('excess_flow', dict(FLOW_ID=65536))])):
            for label, values in invalid:
                summary['parameter_checks'].append(parameter_guard(args, build,
                    ROOT/f'src/rtl/mosaic_blocks/{module}.sv', module, module+'_'+label, values,
                    module+'_parameters_must_be_valid', dependencies=tuple(
                        p for p in dependencies if p.name != module+'.sv')))
        summary['sources_stable'] = before == hashes()
        summary['status'] = campaign_status([*summary['profiles'], summary['controller'],
            *summary['parameter_checks'], summary['python_model_checks']], summary['sources_stable'])
    except (OSError, ValueError, KeyError) as error: summary['error'] = str(error)
    finally: finish_summary(build/'summary.json', summary, 'Array')
    return 0 if summary['status'] == 'PASS' else 1

if __name__ == '__main__': sys.exit(main())
