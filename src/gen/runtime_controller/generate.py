"""Publish the runtime v1 layout, platform tables, recovery contract and provenance."""
import argparse
import hashlib
import json
from pathlib import Path
from runtime_controller_contract import PORTS, LAYOUTS, ENUMS, profile, validate
from runtime_controller_sources import ROOT, PATHS

COUNTERS = ('submission_cycles', 'admitted_cycles', 'rejected_cycles', 'success_result_cycles',
            'failed_result_cycles', 'accepted_action_cycles', 'matching_response_cycles',
            'quarantined_response_cycles', 'applied_event_cycles', 'foreign_event_cycles',
            'duplicate_event_cycles', 'event_gap_cycles', 'deadline_warning_cycles',
            'coherent_snapshot_cycles', 'action_timeout_cycles', 'corrected_state_cycles')


def generate(parameters: dict[str, int], output: Path) -> dict:
    p = validate(parameters)
    layouts = {}
    for name, fields in LAYOUTS.items():
        offset = 0
        layouts[name] = {}
        for field, width in fields:
            layouts[name][field] = dict(lsb=offset, width=width)
            offset += width
    clusters = [dict(id=c, present=bool(p['CLUSTER_PRESENT_MASK'] >> c & 1),
        capabilities=p['CLUSTER_CAPABILITY_TABLE'] >> (32 * c) & 0xffffffff,
        compatible_clusters=p['CLUSTER_COMPATIBILITY_TABLE'] >> (16 * c) & 0xffff,
        memory_ports=p['CLUSTER_MEMORY_PORT_TABLE'] >> (16 * c) & 0xffff,
        scratchpad_regions=p['CLUSTER_SCRATCHPAD_REGION_TABLE'] >> (32 * c) & 0xffffffff,
        clock_domain='runtime_sync', power_domain='external_peer') for c in range(p['NUM_CLUSTERS'])]
    result = dict(schema='mosaic-runtime-controller-v1', reconciliation_abi=0x4d52540100000001,
        parameters=p, clusters=clusters, ports=PORTS, layouts=layouts,
        encodings={k: dict(enumerate(values)) for k, values in ENUMS.items()},
        owners=[p['OWNER_ID_TABLE'] >> (16 * o) & 0xffff for o in range(p['MAX_OWNERS'])],
        services=['configuration', 'dma', 'memory', 'noc', 'event', 'power'],
        mandatory_services=['configuration', 'event', 'power when enabled'],
        resource_model=dict(exclusive=['complete clusters', 'DMA channels', 'memory ports',
            'scratchpad regions', 'event namespaces', 'counter namespaces'],
            shared=['memory bandwidth', 'NoC bandwidth', 'power reservation units'],
            minimum_reservations='No loans of reserved capacity to best effort',
            units='Normalized platform reservation units; watts/bytes-per-second are adapter contracts'),
        package_selection='Closest legal exact precompiled mask to preferred count, then variant index',
        scheduler=dict(ranking='min(priority + age // AGE_ESCALATION_CYCLES, levels - 1)',
            ties='accepted-grant round robin; infeasible requests do not consume fairness budget',
            burst='After burst limit, select minimum eligible rank; then normal maximum rank',
            bound='In accepted admissions while eligible; finite pending set ages to top rank',
            wall_clock_bound='Requires eventually responding peers, input/output readiness and finite kernels'),
        action_model=dict(outstanding=1, tag_reuse=False, timer_starts='command acceptance',
            response='Full identity, endpoint, command and tag; complete mask required on success',
            timeout='Keep the original action and shadow ownership; accept only its late terminal',
            late_success='Rollback pre-start or abort/drain post-start; never continue launch',
            uncertain='Contain; explicit authorized destructive recovery must drain and release'),
        state_graph=dict(launch=['SUBMITTED','VALIDATING','WAIT_RESOURCES','RESERVING','ALLOCATING',
            'CONFIGURING','READY','STARTING','RUNNING'],
            completion=['RUNNING','DRAINING','COMPLETED','RELEASING','FREE'],
            suspend=['RUNNING','SUSPEND_PENDING','SUSPENDED','STARTING','RUNNING'],
            recovery=['ERROR','TERMINATING','RELEASING','FREE']),
        event_contract=dict(source_ids='clusters 0..N-1, authoritative array/system adapter N',
            completion='Aggregated full-mask compute event plus external visibility when requested',
            ordering='Per full kernel identity and source; starts at sequence 0; no wrap',
            gaps='Contain and require authorized destructive recovery',
            diagnostic_overflow='Sticky status; terminal notices and critical ingress use separate queues'),
        clock_contract=dict(domain='one synchronous controller/adapter clock',
            reset='Local reset requires global clean reconciliation; never implies remote release',
            clock_enable='Root request only; no generated clocks',
            test='Functional handshakes suppressed during test/scan',
            power='Ready/good qualification; external WAKE/IDLE sequencing; no physical power gating'),
        counters=dict(width=64, saturating=True, index=dict(enumerate(COUNTERS)),
            note='Coincident events coalesce per cycle; per-kernel run/allocated cycles saturate'),
        components=['round_robin_arbiter','priority_encoder','counter','performance_counters',
            'event_barrier_queue','fifo','tile_shell_state','dff','parity','ecc'],
        assumptions=['System authenticates and normalizes descriptors and policy commands',
            'Array and service adapters are authoritative and return exactly one terminal per accepted action',
            'NO_EFFECT means no side effects; uncertain effects are never reported as NO_EFFECT',
            'Guaranteed reservations are physically enforced by the configured service adapters',
            'Service ACTIVATE/RESUME installs the new epoch; array START/RESUME accepts it atomically',
            'Drain/abort acknowledgements include externally visible DMA/memory obligations',
            'Clean reconciliation proves all old actions, events, remote resources and output obligations invalidated',
            'Controller-owned event namespaces carry only events that require runtime policy'],
        unsupported=['Adaptive profile','resizing','migration','online mapping','CDC/asynchronous reset',
            'physical retention/isolation/clock or voltage switching','trace',
            'hard latency guarantees and nonzero energy budgets','automatic timeout query/replay',
            'arbitrary preemption','vertical RTL integration of the absent array/system adapters'],
        signoff=dict(python_simulation='see regression summary', hdl_assertions='NOT_RUN',
            lint='NOT_RUN', formal='NOT_RUN', synthesis='Design Compiler (deferred)',
            physical='NOT_RUN', power='NOT_RUN'))
    files = (*PATHS, *sorted(Path(__file__).parent.glob('*.py')))
    result['source_sha256'] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                               for path in files}
    result['contract_sha256'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('generated') / 'profile.json')
    args = parser.parse_args()
    generate(profile(), args.output)
    print('Generated', args.output)


if __name__ == '__main__':
    main()
