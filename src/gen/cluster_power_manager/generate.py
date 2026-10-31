"""Publish the clocked platform tables, local ABI and physical integration limits."""
import argparse
import hashlib
import json
from pathlib import Path
from cluster_power_manager_contract import PORTS, LAYOUTS, ENUMS, profile, validate
from cluster_power_manager_sources import ROOT, PATHS

COUNTERS = (*ENUMS['state'], 'transitions', 'wakes', 'timeouts', 'rollbacks',
            'commands_accepted', 'commands_rejected', 'bad_wakes', 'fatal_cycles',
            'corrected_control_cycles')


def generate(parameters: dict[str, int], output: Path) -> dict:
    p = validate(parameters)
    layouts = {}
    for name, fields in LAYOUTS.items():
        offset = 0
        layouts[name] = {}
        for field, width in fields:
            layouts[name][field] = dict(lsb=offset, width=width)
            offset += width
    tg = max(1, (p['NUM_CLOCK_GROUPS'] - 1).bit_length())
    ig = max(1, (p['NUM_ISOLATION_GROUPS'] - 1).bit_length())
    stable = {
        'RESET': dict(root=0, groups=0, isolation='all', resets='all', endpoints=0, accept=0),
        'ACTIVE': dict(root=1, groups='tile requests OR busy OR not-quiescent', isolation=0,
                       resets=0, endpoints='validated', accept='authorized and not held'),
        'STALLED': dict(root=1, groups='tile requests OR busy OR not-quiescent', isolation=0,
                        resets=0, endpoints='validated', accept='authorized and not held'),
        'IDLE_ON': dict(root=1, groups='tile requests OR busy OR not-quiescent', isolation=0,
                        resets=0, endpoints='validated', accept=0),
        'CLOCK_GATED': dict(root=0, groups=0, isolation=0, resets=0, endpoints=0, accept=0),
        'ERROR': dict(root=0, groups=0, isolation='all', resets='all', endpoints=0, accept=0),
        'TEST': dict(root='authorized safe test override', groups='same as root',
                     isolation='all', resets='all', endpoints=0, accept=0)}
    result = dict(schema='mosaic-cluster-power-manager-v1', parameters=p, ports=PORTS,
        layouts=layouts, encodings={k: dict(enumerate(v)) for k, v in ENUMS.items()},
        power_domain_table=[dict(name='cluster_shared_supply', supply='always_on', owner='system',
            tile_regions=list(range(p['NUM_TILES'])), independent_switches=False)],
        clock_domain_table=[dict(name='aon', stops=False, owner='system'),
            dict(name='functional_root', stops=True, owner='cluster_power_manager',
                 source='independent i_functional_clk')],
        tile_region_table=[dict(tile=t, controller='tile_power_controller',
            clock_group=p['TILE_CLOCK_GROUP_TABLE'] >> (t * tg) & ((1 << tg) - 1))
            for t in range(p['NUM_TILES'])],
        boundary_endpoint_table=[dict(endpoint=e,
            isolation_group=p['BOUNDARY_ISOLATION_TABLE'] >> (e * ig) & ((1 << ig) - 1),
            scope='local injection/ejection only; transit router outside this manager')
            for e in range(p['NUM_BOUNDARY_ENDPOINTS'])],
        reset_group_table=[dict(group=r, order=r, release='functional reset_synchronizer')
                           for r in range(p['NUM_RESET_GROUPS'])],
        stable_state_table=stable,
        operating_point_table=[dict(point=0, voltage_id=0, clock_id=0,
            voltage=None, frequency=None, characterization='external platform, NOT_RUN')],
        state_policy_table=[dict(id=0, states=list(stable), supply='always on',
            retention=False, off=False, dvfs=False, sram_mode=0)],
        retained_state_table=[],
        transition_table=dict(gate=['hold execution/injection', 'complete drain', 'endpoint disable ACK',
            'all tile IDLE terminals', 'root/group clock stop', 'qualified stopped ACK'],
            wake=['root/groups enabled', 'qualified source/voltage/clock ACK', 'tile configure/RUN',
            'full-identity package/endpoint validation', 'deisolation ACK', 'endpoint enable ACK',
            'stabilization and array authorization'],
            recovery=['safe clamps/reset', 'power qualification', 'clock qualification',
            'ordered reset release', 'tile configuration/RUN', 'reload and revalidation',
            'deisolation/endpoint acknowledgements', 'IDLE_ON']),
        emergency_table=dict(action='registered ERROR row, no retries or implicit release',
            errors=['power loss', 'clock loss', 'voltage fault', 'thermal', 'identity/control unknown',
                    'unexpected physical ACK', 'integrity', 'post-drain timeout']),
        clock_wrapper_table=dict(root='common/clock_gate', groups='common/clock_gate',
            reset='common/reset_synchronizer', clamps='common/isolation_cell',
            mapping='behavioral RTL cells; PDK mapping and UPF deferred'),
        energy_table=dict(characterized=False, watts=None, joules=None, break_even=None,
            interpretation='Clock pulse counts are functional evidence, not energy or PPA signoff'),
        counter_table=dict(width=64, saturating=True, index=dict(enumerate(COUNTERS)),
            wake_source_width=32, group_gated_cycle_width=32),
        transport=dict(frontend='synchronous AON ready/valid, one outstanding command',
            terminal='one immutable response per accepted command except coordinated global reset',
            validation='full identity plus nonwrapping serial/tag and external boot generation',
            events='delivery sequence is assigned at dequeue; first fatal has dedicated storage',
            overflow='diagnostic overflow is sticky; reserved terminal storage is independent',
            physical_status='independent stable levels through selectable synchronizers; no bus CDC'),
        integration=dict(instantiated=['one released tile controller per region', 'root/group clock gates',
            'ordered functional reset synchronizers', 'endpoint isolation clamps', 'protected storage',
            'queues and counters'],
            modeled=['cluster workload and scratchpad/local network drain', 'array authorization',
                     'package and endpoint validation authority', 'physical status acknowledgements'],
            required=['Route real cluster drain/status and endpoint signals through this interface',
                'AON inputs and synchronous peers must remain powered and clocked',
                'System reset must reconcile all old obligations and change i_system_reset_generation',
                'Physical ACK peers must acknowledge actual controls, never inferred state labels',
                'Retiring operations remain enabled during drain; suppress writes only after full drain']),
        unsupported=['Retention', 'OFF', 'DVFS', 'SRAM low power', 'asynchronous command bus',
                     'trace', 'full cluster/array vertical RTL integration', 'physical net energy claims'],
        signoff=dict(python_simulation='see regression summary', hdl_assertions='NOT_RUN',
            lint='NOT_RUN', formal='NOT_RUN', synthesis='Design Compiler (deferred)',
            cdc='NOT_RUN', upf='NOT_RUN', sta='NOT_RUN', power='NOT_RUN', ppa='NOT_RUN'))
    files = (*PATHS, *sorted(Path(__file__).parent.glob('*.py')))
    result['source_sha256'] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in files}
    result['contract_sha256'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).with_name('generated') / 'profile.json')
    args = parser.parse_args()
    generate(profile(), args.output)
    print('Generated', args.output)


if __name__ == '__main__':
    main()
