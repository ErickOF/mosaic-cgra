"""Rerun released component Python suites with legacy admission and no HDL checks."""
import json
from pathlib import Path
import shlex
import sys
import xml.etree.ElementTree as ET
from global_noc.dependencies import SOURCES
from mosaic_uvm.regression import run_simulation, passed_test, license_unavailable
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'src/val/building_blocks'))
from noc_router.run_noc_router_regression import PROFILES as ROUTER_PROFILES
from tile_network_interface.run_tile_network_interface_regression import PROFILES as TNI_PROFILES


def run_compatibility(args,build):
    selected=(('noc_router','RouterTest',ROUTER_PROFILES,'core_f1_r0_p1_b0'),
        ('noc_router','RouterTest',ROUTER_PROFILES,'core_f0_r1_p0_b1'),
        ('tile_network_interface','TileNetworkInterfaceTest',TNI_PROFILES,'default'),
        ('tile_network_interface','TileNetworkInterfaceTest',TNI_PROFILES,'d128_f32_flow1_parity1'))
    reports=[]
    for module,test,profiles,name in selected:
        p=dict(next(parameters for label,parameters in profiles if label==name))
        prefix=f'-P{module}.' if args.sim=='icarus' else f'-pvalue+{module}.'
        overrides=p.copy()
        if module=='tile_network_interface':
            vw=max(1,(p['NUM_VCS']-1).bit_length())
            overrides['TRAFFIC_CLASS_TO_VC']=f"{p['NUM_TRAFFIC_CLASSES']*vw}'h{p['TRAFFIC_CLASS_TO_VC']:x}"
        flags=' '.join(shlex.quote(f'{prefix}{key}={value}') for key,value in overrides.items())
        path=build/'compatibility'/f'{module}_{name}'
        namespace=module.upper()
        sources=' '.join(str(ROOT/f'src/rtl/{n}.sv') for n in SOURCES)
        result,log,results,coverage=run_simulation(args,ROOT,ROOT/f'src/val/building_blocks/{module}',
            module,'test_'+module,test,path,sources,parameters=p,
            compile_args=f'{args.compile_args} {flags}',environment={
                **{f'{namespace}_{key}':str(value) for key,value in p.items()},
                f'{namespace}_SEED':str(args.seed),f'{namespace}_RANDOM_CYCLES':str(args.random_cycles),
                f'{namespace}_HDL_ASSERTIONS':'0'})
        row=dict(name=f'{module}_{name}',status='FAIL',log=str(log),hdl_assertions='NOT_RUN')
        try:
            if result.returncode:raise ValueError(f'make exited {result.returncode}')
            passed_test(results,test,'test_'+module)
            data=json.loads(coverage.read_text())
            if data['status']!='PASS' or not all(data['goals'].values()):
                raise ValueError('Legacy component coverage failed')
            row.update(status='PASS',coverage=str(coverage))
        except (OSError,ValueError,KeyError,ET.ParseError) as error:
            row['error']=str(error)
            if license_unavailable(log.read_text()):row['status']='NOT_RUN'
        print('Compatibility',row['name'],row['status'],flush=True)
        reports.append(row)
    return reports
