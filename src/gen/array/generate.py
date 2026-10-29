"""Generate immutable Array-MVP integration from released cluster and NoC RTL.

The explicit placement owns identities, configuration gateways and boundary lanes.
Each native cluster is regenerated with its own manifest, rather than copying an
instance with a duplicate logical ID. All clocks use the synchronous baseline.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
RTL = ROOT / 'src/rtl'
sys.path[:0] = [str(HERE.parent/'cluster'), str(HERE.parent/'global_noc')]
spec = importlib.util.spec_from_file_location('array_cluster_generator', HERE.parent/'cluster/generate.py')
cluster = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cluster)
from global_noc_contract import validate as noc_validate, PORTS, ALIASES
from global_noc_sources import SOURCES as NOC_SOURCES
HELPERS = ('mosaic_blocks/array_pkg', 'mosaic_blocks/array_control',
           'mosaic_blocks/array_events', 'mosaic_blocks/array_noc_gateway')


def validate(d):
    keys = {'schema', 'profile', 'array_id', 'rows', 'cols', 'lifecycle_timeout',
            'clock_gating', 'power_gating', 'dvfs', 'async_clocks', 'migration', 'resizing', 'clusters'}
    if set(d) != keys or d['schema'] != 'mosaic-array-v1':
        raise ValueError('Unknown/missing descriptor fields/schema')
    if not isinstance(d['clusters'], list) or not all(isinstance(c, dict) for c in d['clusters']):
        raise ValueError('Clusters must be an explicit list of records')
    if any(type(d[k]) is not int for k in ('array_id', 'rows', 'cols', 'lifecycle_timeout')):
        raise ValueError('Geometry, identity and timeout must be known integers')
    n = len(d['clusters'])
    if n not in (1, 2) or d['rows'] != 1 or d['cols'] != n:
        raise ValueError('Qualified geometries: single-cluster bypass or linear two-cluster MVP')
    if d['profile'] != ('Array-Single-Cluster' if n == 1 else 'Array-MVP'):
        raise ValueError('Profile/topology mismatch')
    if any(d[k] is not False for k in ('power_gating', 'dvfs', 'async_clocks', 'migration', 'resizing')):
        raise ValueError('Advanced power/CDC/migration/resizing profiles are unsupported')
    if type(d['clock_gating']) is not bool or type(d['array_id']) is not int or not 0 <= d['array_id'] < 256:
        raise ValueError('Invalid array identity/clock policy')
    if type(d['lifecycle_timeout']) is not int or not 16 <= d['lifecycle_timeout'] <= 0xffffff:
        raise ValueError('Invalid transition timeout')
    ids, coordinates = set(), set()
    for c in d['clusters']:
        if set(c) != {'id', 'row', 'col', 'scratchpad_banks', 'scratchpad_bank_words', 'noc_ingress', 'noc_egress'}:
            raise ValueError('Incomplete cluster/boundary placement')
        if type(c['id']) is not int or not 0 <= c['id'] < 240 or c['id'] in ids:
            raise ValueError('Duplicate/invalid logical cluster ID')
        if any(type(c[k]) is not int for k in c):
            raise ValueError('Cluster coordinates, SRAM geometry and ports must be integers')
        coordinate = c['row'], c['col']
        if coordinate in coordinates or c['row'] != 0 or not 0 <= c['col'] < n:
            raise ValueError('Duplicate/invalid coordinate')
        if not all(type(c[k]) is int and 0 <= c[k] < 8 for k in ('noc_ingress', 'noc_egress')):
            raise ValueError('Invalid native mesh boundary')
        ids.add(c['id'])
        coordinates.add(coordinate)
    geometries = {(c['scratchpad_banks'], c['scratchpad_bank_words']) for c in d['clusters']}
    if len(geometries) != 1:
        raise ValueError('The qualified MVP requires uniform native cluster memory widths')
    return n


def toml_text(d):
    lines = [f'{k} = {json.dumps(v)}' for k, v in d.items() if k not in ('tiles', 'clusters')]
    for key in ('tiles', 'clusters'):
        for entry in d.get(key, []):
            lines += [f'\n[[{key}]]'] + [f'{k} = {json.dumps(v)}' for k, v in entry.items()]
    return '\n'.join(lines) + '\n'


def sl(signal, index, width):
    return f'{signal}[{index*width}+:{width}]' if width > 1 else f'{signal}[{index}]'


class Builder:
    def __init__(self):
        self.ports, self.wires, self.code, self.instances = {}, {}, [], []

    def port(self, name, direction, width=1):
        if self.ports.setdefault(name, (direction, width)) != (direction, width):
            raise ValueError(f'Conflicting port {name}')
        return name

    def wire(self, name, width=1):
        if self.wires.setdefault(name, width) != width:
            raise ValueError(f'Conflicting wire {name}')
        return name

    def assign(self, lhs, rhs):
        self.code.append(f'    assign {lhs} = {rhs};')

    def instance(self, module, name, catalog, mapping, parameters=None):
        if set(mapping) != set(catalog):
            raise ValueError((module, 'Unbound ports', set(mapping) ^ set(catalog)))
        params = '' if not parameters else ' #(\n' + ',\n'.join(
            f'        .{k}({v})' for k, v in parameters.items()) + '\n    )'
        self.instances.append(f'    {module}{params} u_{name} (\n' + ',\n'.join(
            f'        .{k}({v})' for k, v in mapping.items()) + '\n    );')

    def render(self, identity):
        ports = ',\n'.join(f'    {direction} wire ' + f'[{width-1}:0] ' + name
            for name, (direction, width) in self.ports.items())
        wires = '\n'.join('    wire ' + f'[{width-1}:0] ' + name + ';'
                          for name, width in self.wires.items())
        text = ('`timescale 1ns / 1ps\n`default_nettype none\n'
            '// GENERATED by src/gen/array/generate.py. Edit the descriptor/generator.\n'
            f'// Architecture fingerprint: {identity}\nmodule array (\n{ports}\n);\n{wires}\n' +
            '\n'.join(self.code) + '\n\n' + '\n\n'.join(self.instances) +
            '\nendmodule\n`default_nettype wire\n')
        lines = []
        for line in text.splitlines():
            while len(line) > 100:
                cut = max(line.rfind(t, 0, 94) for t in (' && ', ' || ', ', ', ' ? ', ' : '))
                if cut < 12:
                    cut = line.find('(') + 1 if line.lstrip().startswith('.') else -1
                    if cut < 12:
                        raise ValueError(f'Cannot wrap line: {line}')
                elif line[cut:cut+4] in (' && ', ' || '): cut += 3
                elif line[cut:cut+2] == ', ': cut += 1
                lines.append(line[:cut].rstrip())
                line = '            ' + line[cut:].lstrip()
            lines.append(line)
        return '\n'.join(lines) + '\n'


def generate(descriptor, output, artifacts):
    d = tomllib.loads(Path(descriptor).read_text())
    n = validate(d)
    artifacts = Path(artifacts)
    artifacts.mkdir(parents=True, exist_ok=True)
    native, native_paths, catalogs = [], [], []
    for index, entry in enumerate(d['clusters']):
        cd = tomllib.loads((HERE.parent/'cluster/mvp.toml').read_text())
        cd.update(cluster_id=entry['id'], clock_gating=d['clock_gating'], lifecycle_timeout=d['lifecycle_timeout'],
                  scratchpad_banks=entry['scratchpad_banks'], scratchpad_bank_words=entry['scratchpad_bank_words'])
        target = artifacts/f'cluster_{index}'
        target.mkdir(exist_ok=True)
        path = target/'descriptor.toml'
        path.write_text(toml_text(cd))
        rtl = target/f'array_cluster_{index}.sv'
        contract = cluster.generate(path, rtl, target)
        rtl.write_text(rtl.read_text().replace('module cluster (', f'module array_cluster_{index} ('))
        contract['generated_rtl_sha256'] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        (target/'manifest.json').write_text(json.dumps(contract, indent=2)+'\n')
        native.append(contract)
        native_paths.append(rtl)
        catalogs.append(json.loads((target/'ports.json').read_text()))
    p = noc_validate(dict(NOC_X=n, NOC_Y=1, NUM_ROUTERS=n, NUM_ENDPOINTS=n,
        FLIT_DATA_WIDTH=128, ENDPOINT_DATA_WIDTH=640, INPUT_VC_DEPTH=8, ENDPOINT_RX_VC_DEPTH=8,
        MAX_ACTIVE_FLOWS=2, NUM_TX_CHANNELS_PER_ENDPOINT=2, NUM_RX_CHANNELS_PER_ENDPOINT=2))
    b = Builder()
    for name in ('i_clk', 'i_rstb', 'i_test_mode', 'i_scan_enable'): b.port(name, 'input')
    cp = cluster.ports('array_control', dict(N=n))
    control = {name: b.port(name, direction, width) if name in b.ports or name.startswith(
        ('i_runtime_', 'o_runtime_')) else b.wire('control_'+name, width)
        for name, (direction, width) in cp.items()}
    for name in ('o_allocated', 'o_running', 'o_fatal', 'o_completion_mask', 'o_group_masks',
        'o_owner_ids', 'o_kernel_ids', 'o_array_package_ids', 'o_local_package_ids', 'o_context_ids',
        'o_execution_epochs', 'o_allocation_generations', 'o_array_state', 'o_first_error', 'o_busy'):
        b.port(name, 'output', cp[name][1]); b.assign(name, control[name])
    b.instance('array_control', 'control', cp, control, dict(NUM_CLUSTERS=n, TIMEOUT_CYCLES=d['lifecycle_timeout'],
                    ARCHITECTURE_HASH="256'hMANIFEST"))
    # The root and the runtime reserve mutually exclusive management operations.
    b.port('i_runtime_valid', 'input')
    b.port('o_runtime_ready', 'output')
    control['i_runtime_valid'] = b.wire('runtime_valid_admit')
    control['o_runtime_ready'] = b.wire('runtime_ready_native')
    # Replace the instance after changing its two private handshake bindings.
    b.instances.pop()
    b.instance('array_control', 'control', cp, control,
               dict(NUM_CLUSTERS=n, TIMEOUT_CYCLES=d['lifecycle_timeout'],
                    ARCHITECTURE_HASH="256'hMANIFEST"))
    maintenance = "!cfg_busy && (i_cfg_request_valid === 1'b0)"
    if n > 1: maintenance += " && (i_noc_cfg_valid === 1'b0) && !o_noc_cfg_response_valid"
    b.assign('runtime_valid_admit', 'i_runtime_valid && '+maintenance)
    b.assign('o_runtime_ready', 'runtime_ready_native && '+maintenance)
    cmaps = []
    for c, catalog in enumerate(catalogs):
        mapping = {name: name if name in ('i_clk', 'i_rstb', 'i_test_mode', 'i_scan_enable') else
            b.wire(f'c{c}_{name}', width) for name, (_, width) in catalog.items()}
        b.instance(f'array_cluster_{c}', f'cluster{c}', catalog, mapping)
        cmaps.append(mapping)
    # One array root reserves a gateway until the last local response retires.
    b.port('i_cfg_cluster_slot', 'input')
    b.port('i_cfg_array_package_id', 'input', 32)
    b.port('o_cfg_cluster_id', 'output', 8)
    b.code += ['    logic cfg_busy;', '    logic cfg_slot;',
               '    wire cfg_select = cfg_busy ? cfg_slot : i_cfg_cluster_slot;']
    req = [k for k in catalogs[0] if k.startswith('i_cfg_request_')]
    rsp = [k for k in catalogs[0] if k.startswith('o_cfg_response_')]
    for name in req + rsp + ['o_cfg_request_ready', 'i_cfg_response_ready']:
        b.port(name, *catalogs[0][name])
    b.wire('cfg_authorized')
    auth = [f"(cfg_select === 1'd{c} && control_o_allocated[{c}] && !control_o_fatal[{c}] && "
        f'i_cfg_request_owner_id === control_o_owner_ids[{16*c}+:16] && '
        f'i_cfg_request_kernel_id === control_o_kernel_ids[{16*c}+:16] && '
        f'i_cfg_array_package_id === control_o_array_package_ids[{32*c}+:32])' for c in range(n)]
    b.assign('cfg_authorized', '!control_o_busy && (i_test_mode === 1\'b0) && (' + ' || '.join(auth) + ')')
    b.assign('o_cfg_request_ready', '!cfg_busy && cfg_authorized && (' + ' || '.join(
        f"(cfg_select === 1'd{c} && {cmaps[c]['o_cfg_request_ready']})" for c in range(n)) + ')')
    for name in rsp:
        b.assign(name, 'cfg_busy ? (' + ' : '.join(f"cfg_slot == 1'd{c} ? {cmaps[c][name]}"
            for c in range(n)) + " : '0) : '0")
    b.assign('o_cfg_cluster_id', ' : '.join(f"cfg_slot == 1'd{c} ? 8'd{x['id']}"
        for c, x in enumerate(d['clusters'])) + " : 8'hff")
    b.code += ['', '    always @(posedge i_clk) begin', "        if (i_rstb !== 1'b1) begin",
        "            cfg_busy <= 1'b0;", "            cfg_slot <= 1'b0;", '        end else begin',
        '            if (i_cfg_request_valid && o_cfg_request_ready) begin',
        "                cfg_busy <= 1'b1;", '                cfg_slot <= i_cfg_cluster_slot;', '            end',
        '            if (o_cfg_response_valid && i_cfg_response_ready &&',
        "                o_cfg_response_last) cfg_busy <= 1'b0;", '        end', '    end', '']
    for c, m in enumerate(cmaps):
        for name in req:
            b.assign(m[name], f"i_cfg_request_valid && !cfg_busy && cfg_authorized && cfg_select === 1'd{c}"
                if name == 'i_cfg_request_valid' else name)
        b.assign(m['i_cfg_response_ready'], f"cfg_busy && cfg_slot == 1'd{c} && i_cfg_response_ready")
        runtime = dict(i_runtime_valid=sl(control['o_cluster_valid'], c, 1),
            i_runtime_command=control['o_cluster_command'], i_runtime_owner_id=control['o_command_owner'],
            i_runtime_kernel_id=control['o_command_kernel'], i_runtime_tag=control['o_command_tag'],
            i_runtime_package_id=sl(control['o_local_package_ids'], c, 32),
            i_runtime_context_id=sl(control['o_context_ids'], c, 8), i_runtime_resource_mask="4'hf",
            i_runtime_flags="8'd0", i_runtime_response_ready=sl(control['o_cluster_response_ready'], c, 1))
        for name, value in runtime.items(): b.assign(m[name], value)
        for suffix, target, width in [('ready', 'i_cluster_ready', 1), ('response_valid', 'i_cluster_response_valid', 1),
            ('response_command', 'i_cluster_response_command', 4), ('response_tag', 'i_cluster_response_tag', 16),
            ('response_error_code', 'i_cluster_response_error', 8)]:
            b.assign(sl(control[target], c, width), m['o_runtime_'+suffix])
        commits = dict(i_cfg_commit_valid=sl(control['o_cluster_commit_valid'], c, 1),
            i_cfg_commit_destination_mask="6'h3f", i_cfg_commit_owner_id=sl(control['o_owner_ids'], c, 16),
            i_cfg_commit_kernel_id=sl(control['o_kernel_ids'], c, 16),
            i_cfg_commit_package_id=sl(control['o_local_package_ids'], c, 32),
            i_cfg_commit_context_ids='{6{' + sl(control['o_context_ids'], c, 8) + '}}',
            i_cfg_commit_context_versions=sl(control['o_commit_versions'], c, 96),
            i_cfg_commit_epoch=f"control_o_execution_epochs[{c*8}+:4] + 4'd1")
        for name, value in commits.items(): b.assign(m[name], value)
        for suffix in ('ready', 'complete', 'error'):
            b.assign(sl(control['i_cluster_commit_'+suffix], c, 1), m['o_cfg_commit_'+suffix])
        b.assign(sl(control['i_cluster_error'], c, 1), m['o_status_fatal_error'])
        b.assign(sl(control['i_cluster_quiescent'], c, 1), m['o_status_quiescent'])
        b.code += [f'    logic [5:0] prepared_{c};', '', '    always @(posedge i_clk) begin',
            f"        if (i_rstb !== 1'b1 || ({m['i_runtime_valid']} && {m['o_runtime_ready']} &&",
            f"            {m['i_runtime_command']} == 4'd2)) prepared_{c} <= '0;",
            f"        else if ({m['i_cfg_request_valid']} && {m['o_cfg_request_ready']} &&",
            f"            {m['i_cfg_request_command']} == 5'd1)",
            f"            prepared_{c} <= prepared_{c} & ~{m['i_cfg_request_destination_mask']};",
            f"        else if ({m['o_cfg_response_valid']} && {m['i_cfg_response_ready']} &&",
            f"            {m['o_cfg_response_last']} && {m['o_cfg_response_command']} == 5'd6 &&",
            f"            {m['o_cfg_response_transaction_success']})",
            f"            prepared_{c} <= prepared_{c} | {m['o_cfg_response_success_mask']};", '    end', '']
        b.assign(sl(control['i_cluster_prepared'], c, 1), f'(&prepared_{c}) && {m["o_status_package_manifest_valid"]}')
    internal = set(req + rsp + list(runtime) + list(commits) + ['o_cfg_request_ready', 'i_cfg_response_ready', 'i_event_ready'])
    for name, (direction, width) in catalogs[0].items():
        if name in internal or name.startswith(('i_runtime_', 'o_runtime_')) or name in ('i_clk', 'i_rstb', 'i_test_mode', 'i_scan_enable'):
            continue
        public = name[:2] + 'cluster_' + name[2:]
        b.port(public, direction, n*width)
        for c, m in enumerate(cmaps):
            if name.startswith(('i_boundary_', 'o_boundary_')) and name != 'o_boundary_isolation_enable' and n > 1:
                unit = width // 8
                for lane in range(8):
                    used = lane == d['clusters'][c]['noc_egress' if name in (
                        'o_boundary_valid', 'o_boundary_data', 'o_boundary_metadata', 'i_boundary_ready') else 'noc_ingress']
                    left, right = sl(m[name], lane, unit), sl(public, c*8+lane, unit)
                    if used:
                        if direction == 'output': b.assign(right, "'0")
                    else:
                        value = right if direction == 'input' else left
                        if name in ('i_boundary_valid', 'o_boundary_valid', 'o_boundary_ready'):
                            value += f' && !control_o_fatal[{c}]'
                        b.assign(left if direction == 'input' else right, value)
            else:
                value = sl(public, c, width) if direction == 'input' else m[name]
                if name in ('i_package_valid', 'i_mst_descriptor_valid', 'i_mst_region_valid',
                            'i_mst_buffer_valid', 'i_mst_dma_in_valid', 'o_mst_dma_out_valid'):
                    value += f' && !control_o_fatal[{c}]'
                if name == 'i_memory_req_valid' or (n == 1 and name in (
                        'i_boundary_valid', 'o_boundary_valid', 'o_boundary_ready')):
                    value = f'{value} & {{{width}{{!control_o_fatal[{c}]}}}}'
                if name == 'o_boundary_isolation_enable':
                    value += f' || control_o_fatal[{c}]'
                b.assign(m[name] if direction == 'input' else sl(public, c, width), value)
    ec = cluster.ports('array_events', dict(N=n, WIDTH=389+n))
    em = {name: name if name in ('i_clk', 'i_rstb') else b.port(name, direction, width) if name.startswith(
        ('o_event_', 'i_event_')) else b.wire('events_'+name, width) for name, (direction, width) in ec.items()}
    for suffix in ('allocated', 'group_masks', 'owner_ids', 'kernel_ids', 'local_package_ids', 'execution_epochs', 'context_ids', 'terminal_valid'):
        b.assign(em['i_'+suffix], control['o_'+suffix])
    b.assign(em['i_package_ids'], control['o_array_package_ids'])
    for target, source in [('i_terminal_ready', 'o_terminal_ready'), ('i_completion', 'o_completion'),
                           ('i_event_error', 'o_error'), ('i_events_empty', 'o_empty')]: b.assign(control[target], em[source])
    for c, m in enumerate(cmaps):
        b.assign(sl(em['i_valid'], c, 1), m['o_event_valid'])
        b.assign(m['i_event_ready'], sl(em['o_ready'], c, 1))
        b.assign(sl(em['i_records'], c, 377), '{' + ', '.join(m['o_event_'+f] for f in
            ('sequence', 'severity', 'payload', 'epoch', 'package_id', 'context_id', 'kernel_id', 'owner_id', 'source_id', 'type')) + '}')
    b.instance('array_events', 'events', ec, em, dict(NUM_CLUSTERS=n,
        CLUSTER_IDS=cluster.packed([c['id'] for c in d['clusters']], 8)))
    b.port('o_interrupt', 'output'); b.assign('o_interrupt', '!events_o_empty || (|control_o_fatal)')
    if n > 1: build_noc(b, n, p, d, control, cmaps)
    else:
        for name in ('i_network_idle', 'i_network_configured'): b.assign(control[name], "1'b1")
        b.assign(control['i_network_error'], "1'b0")
    b.port('o_manifest_hash', 'output', 256); b.assign('o_manifest_hash', "256'hMANIFEST")
    b.port('o_array_id', 'output', 8); b.assign('o_array_id', f"8'd{d['array_id']}")
    dependencies = tuple(dict.fromkeys((*cluster.SOURCES, *NOC_SOURCES, 'mosaic_blocks/global_noc', *HELPERS)))
    contract = dict(schema='mosaic-array-contract-v1', descriptor=d, noc_parameters=p,
        cluster_table=[dict(slot=i, **entry, manifest_sha256=native[i]['manifest_sha256'],
            tile_count=4, capacity=native[i]['geometry']['capacity'], profile='Cluster-MVP',
            memory_boundary=i, config_gateway=i, noc_endpoint=i, clock='i_clk', reset='i_rstb')
            for i, entry in enumerate(d['clusters'])],
        packet=dict(endpoint_bits=640, flit_bits=128, fragments=5, vc=0, envelope=[32, 512], padding=[544, 96]),
        allocation='disjoint whole clusters, immutable mask per owner/kernel; no resize',
        configuration='one reserved array gateway; native configuration_network roots',
        commit='all PREPARE/manifests, captured versions; native COMMIT then VALIDATE; held START',
        events='dedicated ungated parity-protected control network; payload256/sequence32',
        epoch='8-bit array ABI restricted to native nonwrapping epochs 0..15; reset at exhaustion',
        noc_epoch='independent transport epoch; privileged configuration only while all clusters free',
        memory='three native permission-checked SRAM clients and one MST per cluster',
        power='native clock gating; common clock; always powered',
        unsupported=['balanced/heterogeneous/sparse arrays', 'standalone services', 'global barriers',
            'power gating/retention/DVFS', 'CDC/asynchronous reset', 'migration/resizing',
            'NoC reconfiguration/flush while allocated', 'per-class inter-cluster request/response protocols'],
        dependency_sha256={f'src/rtl/{s}.sv': hashlib.sha256((RTL/f'{s}.sv').read_bytes()).hexdigest() for s in dependencies},
        generator_sha256={str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for directory in (HERE, HERE.parent/'cluster', HERE.parent/'global_noc') for path in directory.glob('*.py')},
        signoff=dict(validation='Python-only', synthesis='Design Compiler (deferred)', lint='NOT_RUN',
                     formal='NOT_RUN', physical='NOT_CHARACTERIZED'))
    contract['features'] = dict(global_noc=n > 1, synchronous=True, cluster_exclusive=True,
        clock_gating=d['clock_gating'], power_gating=False, migration=False, resizing=False)
    contract['tables'] = dict(
        CLUSTER_PRESENT_MASK=(1 << n)-1,
        CLUSTER_ID_TABLE=[c['id'] for c in d['clusters']],
        CLUSTER_PROFILE_TABLE=['Cluster-MVP']*n,
        CLUSTER_MANIFEST_HASH_TABLE=[c['manifest_sha256'] for c in native],
        CLUSTER_COORDINATE_TABLE=[[c['row'], c['col']] for c in d['clusters']],
        CLUSTER_CAPABILITY_TABLE=[dict(BCT=3, MST=1, context_depth=4)]*n,
        CLUSTER_TILE_COUNT_TABLE=[4]*n,
        CLUSTER_SCRATCHPAD_TABLE=[dict(capacity=c['geometry']['capacity'],
            banks=c['descriptor']['scratchpad_banks']) for c in native],
        CLUSTER_CLOCK_DOMAIN_TABLE=['i_clk']*n,
        CLUSTER_POWER_DOMAIN_TABLE=['always_powered']*n,
        STANDALONE_TILE_TABLE=[],
        GLOBAL_ROUTER_TABLE=[dict(id=c, x=c, y=0) for c in range(n)] if n > 1 else [],
        GLOBAL_LINK_TABLE=[dict(source=0, destination=1, port=2),
            dict(source=1, destination=0, port=4)] if n > 1 else [],
        NOC_ENDPOINT_TABLE=[dict(cluster=c['id'], endpoint=i, channel=0,
            ingress=c['noc_ingress'], egress=c['noc_egress']) for i, c in enumerate(d['clusters'])]
            if n > 1 else [],
        TRAFFIC_CLASS_TO_VC_TABLE=[0, 0, 1, 2, 3, 3, 0, 0],
        TRAFFIC_CLASS_TO_SERVICE_TABLE=[0, 0, 0, 0, 1, 1, 0, 0],
        CHANNEL_DEPENDENCY_TABLE=dict(data='VC0 complete-packet reservations',
            events='dedicated ungated control network', configuration='dedicated gateway',
            proof='router XY graph only; system/application deadlock proof deferred'),
        CONFIG_GATEWAY_TABLE=[dict(cluster=c['id'], slot=i, local_endpoints=6)
            for i, c in enumerate(d['clusters'])],
        EVENT_ENDPOINT_TABLE=[dict(cluster=c['id'], slot=i) for i, c in enumerate(d['clusters'])],
        MEMORY_BOUNDARY_TABLE=[dict(cluster=c['id'], slot=i, clients=3, mst_channels=1,
            arbitration='native round-robin permission-checked banked scratchpad')
            for i, c in enumerate(d['clusters'])],
        ALLOCATION_REGION_TABLE=[dict(cluster=c['id'], mask=1 << i) for i, c in enumerate(d['clusters'])],
        COUNTER_SOURCE_TABLE=['per-cluster eight saturating 48-bit coherent counters',
                              'NoC accepted/delivered packet counters'],
        ERROR_SOURCE_TABLE=['array control', 'cluster native faults', 'protected event queue',
                            'NoC transport and authenticated stream gateways'],
        RESET_ORDER_TABLE=['common synchronous assertion, gate wake, native validity reset',
                           'explicit configuration and runtime launch after reset'],
        POWER_SEQUENCE_TABLE=['always powered; native gate-safe clock enable only'])
    identity = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
    contract['manifest_sha256'] = identity
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(b.render(identity).replace("256'hMANIFEST", "256'h"+identity))
    contract['generated_rtl_sha256'] = hashlib.sha256(output.read_bytes()).hexdigest()
    (artifacts/'manifest.json').write_text(json.dumps(contract, indent=2)+'\n')
    (artifacts/'ports.json').write_text(json.dumps(b.ports, indent=2)+'\n')
    def relative(path): return str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    (artifacts/'sources.f').write_text('\n'.join([f'src/rtl/{s}.sv' for s in dependencies] +
        [relative(path) for path in native_paths] + [relative(output)])+'\n')
    return contract


def build_noc(b, n, p, d, control, cmaps):
    a = {alias: p[key] for alias, key in ALIASES.items()}
    a.update(K=16, TB=80, TC=3, VW=2, OCC=4, CW=4, TO=2, VO=4, RO=2)
    nc = {name: (direction.lower(), cluster.arithmetic(width, a)) for name, (direction, width) in PORTS.items()}
    nm = {}
    for name, (direction, width) in nc.items():
        if name in ('i_noc_clk', 'i_noc_rstb'): nm[name] = 'i_clk' if name.endswith('clk') else 'i_rstb'
        elif name.startswith(('i_cfg_', 'o_cfg_')): nm[name] = b.port(name[:2]+'noc_'+name[2:], direction, width)
        else: nm[name] = b.wire('noc_'+name, width)
    nm['i_cfg_valid'] = b.wire('noc_cfg_admit')
    allowed = 'control_o_allocated == 0 && !control_o_busy && !cfg_busy && events_o_empty && (i_test_mode === 1\'b0)'
    b.assign(nm['i_cfg_valid'], 'i_noc_cfg_valid && '+allowed)
    nm['o_cfg_ready'] = b.wire('noc_cfg_ready')
    b.assign('o_noc_cfg_ready', nm['o_cfg_ready']+' && '+allowed)
    b.assign(nm['i_endpoint_clk'], '{'+str(n)+'{i_clk}}')
    b.assign(nm['i_endpoint_rstb'], '{'+str(n)+'{i_rstb}}')
    b.assign(nm['i_run'], '(|control_o_running) && (i_test_mode === 1\'b0)')
    for key in ('i_error_clear', 'i_drain_valid', 'i_drain_tag', 'i_flush_valid', 'i_flush_tag', 'i_drain_all', 'i_drain_flow_mask'):
        b.assign(nm[key], "'0")
    b.assign(nm['i_lifecycle_ready'], "1'b1"); b.assign(nm['i_response_reserved'], "'0")
    b.instance('global_noc', 'global_noc', nc, nm, p)
    for target, source in [('i_network_idle', 'o_idle'), ('i_network_configured', 'o_configured')]: b.assign(control[target], nm[source])
    b.wire('gateway_errors', n)
    b.assign(control['i_network_error'], nm['o_error']+' || (|gateway_errors)')
    for k, width in [('idle', 1), ('accepted_packets', 64), ('delivered_packets', 64)]:
        b.port('o_noc_'+k, 'output', width); b.assign('o_noc_'+k, nm['o_'+k])
    gc = cluster.ports('array_noc_gateway', {})
    for c, m in enumerate(cmaps):
        other = 1-c
        gm = dict(i_clk='i_clk', i_rstb='i_rstb', i_sequence_clear=
            "i_noc_cfg_valid && o_noc_cfg_ready && i_noc_cfg_command == 3'd4",
            i_enable=f'control_o_running[{c}] && control_o_running[{other}] && '
                f'control_o_owner_ids[{c*16}+:16] == control_o_owner_ids[{other*16}+:16] && '
                f'control_o_kernel_ids[{c*16}+:16] == control_o_kernel_ids[{other*16}+:16] && '
                f'control_o_array_package_ids[{c*32}+:32] == control_o_array_package_ids[{other*32}+:32] && (i_test_mode === 1\'b0)',
            i_owner=sl(control['o_owner_ids'], c, 16), i_kernel=sl(control['o_kernel_ids'], c, 16),
            i_source_package=sl(control['o_local_package_ids'], c, 32),
            i_destination_package=sl(control['o_local_package_ids'], other, 32),
            i_source_epoch=sl(control['o_execution_epochs'], c, 8),
            i_destination_epoch=sl(control['o_execution_epochs'], other, 8),
            i_context=sl(control['o_context_ids'], c, 8), i_generation=m['o_status_allocation_generation'],
            i_noc_epoch=nm['o_execution_epoch'], i_mst_epoch=m['o_mst_execution_epoch'],
            i_destination_generation=cmaps[other]['o_status_allocation_generation'],
            i_destination_mst_epoch=cmaps[other]['o_mst_execution_epoch'], o_error=f'gateway_errors[{c}]')
        for key, native_name, width, lane in (
            ('i_cluster_valid', 'o_boundary_valid', 1, d['clusters'][c]['noc_egress']),
            ('o_cluster_ready', 'i_boundary_ready', 1, d['clusters'][c]['noc_egress']),
            ('i_cluster_data', 'o_boundary_data', 32, d['clusters'][c]['noc_egress']),
            ('i_cluster_metadata', 'o_boundary_metadata', 512, d['clusters'][c]['noc_egress']),
            ('o_cluster_valid', 'i_boundary_valid', 1, d['clusters'][c]['noc_ingress']),
            ('i_cluster_ready', 'o_boundary_ready', 1, d['clusters'][c]['noc_ingress']),
            ('o_cluster_data', 'i_boundary_data', 32, d['clusters'][c]['noc_ingress']),
            ('o_cluster_metadata', 'i_boundary_metadata', 512, d['clusters'][c]['noc_ingress'])):
            gm[key] = sl(m[native_name], lane, width)
        for key, name, width in (
            ('o_tx_valid', 'i_tile_tx_valid', 1), ('i_tx_ready', 'o_tile_tx_ready', 1),
            ('o_tx_data', 'i_tile_tx_data', 640), ('o_tx_packet_id', 'i_tile_tx_packet_id', 16),
            ('o_tx_user_metadata', 'i_tile_tx_user_metadata', 64), ('i_rx_valid', 'o_tile_rx_valid', 1),
            ('o_rx_ready', 'i_tile_rx_ready', 1), ('i_rx_data', 'o_tile_rx_data', 640),
            ('i_rx_keep', 'o_tile_rx_keep', 80), ('i_rx_error', 'o_tile_rx_error', 8),
            ('i_rx_source', 'o_tile_rx_source_node', 8)):
            gm[key] = sl(nm[name], 2*c, width)
        b.instance('array_noc_gateway', f'gateway{c}', gc, gm, dict(SOURCE_NODE=c, DESTINATION_NODE=other, FLOW_ID=c+1))
        for name, (direction, total) in nc.items():
            if not name.startswith('i_tile_tx_'): continue
            width = total//(2*n)
            b.assign(sl(nm[name], 2*c+1, width), "'0")
            if name in ('i_tile_tx_valid', 'i_tile_tx_data', 'i_tile_tx_packet_id', 'i_tile_tx_user_metadata'): continue
            value = {'i_tile_tx_keep': "{80{1'b1}}", 'i_tile_tx_last': "1'b1",
                'i_tile_tx_context_id': sl(control['o_context_ids'], c, 8),
                'i_tile_tx_destination_node': f"8'd{other}", 'i_tile_tx_destination_endpoint': "8'd0"}.get(name, "'0")
            b.assign(sl(nm[name], 2*c, width), value)
        b.assign(sl(nm['i_tile_rx_ready'], 2*c+1, 1), "1'b0")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--descriptor', type=Path, default=HERE/'mvp.toml')
    parser.add_argument('--output', type=Path, default=RTL/'mosaic_blocks/array.sv')
    parser.add_argument('--artifacts', type=Path, default=HERE/'generated')
    args = parser.parse_args()
    generate(args.descriptor, args.output, args.artifacts)

if __name__ == '__main__': main()
