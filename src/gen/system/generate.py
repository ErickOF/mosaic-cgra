"""Generate synchronous, canonical System-RTL around one released array.

The schema owns register addresses, descriptor layouts, transaction bindings and
platform limits. Other bus, CDC, power and scheduling profiles are rejected.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('system_array_generator', HERE.parent/'array/generate.py')
array = importlib.util.module_from_spec(spec)
spec.loader.exec_module(array)

REGISTERS = {
    'IDENTITY': (0x0000, 'RO'), 'VERSION': (0x0004, 'RO'),
    'GEOMETRY': (0x0008, 'RO'), 'QUEUES': (0x000c, 'RO'),
    'STATUS': (0x0010, 'RO'), 'STATE': (0x0014, 'RO'),
    'SYSTEM_HASH': (0x0040, 'RO', 8), 'ARRAY_HASH': (0x0060, 'RO', 8),
    'PROGRAM_BUFFER': (0x1000, 'RW'), 'PROGRAM_OFFSET': (0x1004, 'RW'),
    'PROGRAM_COUNT_GENERATION': (0x1008, 'RW'), 'PROGRAM_DOORBELL': (0x100c, 'WO'),
    'NATIVE_EPOCHS': (0x2000, 'RO'), 'NATIVE_GENERATIONS': (0x2004, 'RO'),
    'SCRATCHPAD_GENERATIONS': (0x2008, 'RO'), 'PROGRAM_STATUS': (0x1010, 'RO'), 'PROGRAM_DISCARD': (0x1018, 'WO'),
    'PROGRAM_RESULT': (0x101c, 'RO'), 'PROGRAM_CANCEL': (0x1020, 'WO'),
    'BUFFER_INDEX': (0x3000, 'RW'), 'BUFFER_BASE_LO': (0x3004, 'RW'),
    'BUFFER_BASE_HI': (0x3008, 'RW'), 'BUFFER_SIZE': (0x300c, 'RW'),
    'BUFFER_OWNER_KERNEL': (0x3010, 'RW'), 'BUFFER_GENERATION_PERMISSIONS': (0x3014, 'RW'),
    'BUFFER_COMMIT': (0x3020, 'WO'), 'BUFFER_DISCARD': (0x3024, 'WO'),
    'BUFFER_STATUS': (0x3028, 'RO'), 'BUFFER_FENCE': (0x3040, 'WO'),
    'INTERRUPT_MASK': (0x4000, 'RW'), 'EVENT_COUNT': (0x4004, 'RO'),
    'INTERRUPT_STATUS': (0x4008, 'RO'), 'EVENT_ACK': (0x4020, 'WO'),
    'EVENT_HEAD': (0x4040, 'RO', 16), 'COUNTER_SNAPSHOT': (0x5000, 'WO'),
    'COUNTER_VALID': (0x5004, 'RO'), 'COUNTERS': (0x5010, 'RO', 8),
    'FIRST_ERROR': (0x7000, 'RO'), 'ERROR_CLEAR': (0x7004, 'WO'),
    'DRAIN': (0x7008, 'WO'), 'ERROR_ADDRESS_LO': (0x7010, 'RO'),
    'ERROR_ADDRESS_HI': (0x7014, 'RO'), 'ERROR_IDENTITY': (0x7018, 'RO'),
    'LAST_ARRAY_RESPONSE': (0x7100, 'RO', 32),
}
HELPERS = ('mosaic_blocks/system_pkg', 'mosaic_blocks/system_core')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def profile_text(descriptor):
    """System profiles are flat; `clusters` is a count, not an array descriptor."""
    return '\n'.join(f'{key} = {json.dumps(value)}' for key, value in descriptor.items()) + '\n'


def validate(d):
    expected = {'schema', 'profile', 'clusters', 'buffers', 'command_depth', 'event_depth',
                'memory_data_width', 'memory_timeout', 'control_protocol', 'memory_protocol',
                'hardware_runtime', 'async_clocks', 'power_gating', 'dvfs', 'coherence',
                'translation', 'trace', 'direct_results', 'system_clock_gating', 'max_active_kernels'}
    if set(d) != expected or d['schema'] != 'mosaic-system-v1' or d['profile'] != 'System-RTL':
        raise ValueError('Only the versioned System-RTL schema is implemented')
    if any(type(d[k]) is not int for k in ('clusters', 'buffers', 'command_depth', 'event_depth',
        'memory_data_width', 'memory_timeout', 'max_active_kernels')):
        raise ValueError('Geometry, widths and timeout must be integers')
    if d['clusters'] not in (1, 2) or not 1 <= d['buffers'] <= 8 or not 1 <= d['command_depth'] <= 8:
        raise ValueError('Unsupported array/buffer/command geometry')
    if not 1 <= d['event_depth'] <= 32 or d['memory_data_width'] not in (64, 128):
        raise ValueError('Unsupported event depth or memory width')
    if not 16 <= d['memory_timeout'] <= 0xffffff or d['max_active_kernels'] != 1:
        raise ValueError('Unsupported timeout or kernel count')
    if d['control_protocol'] != 'canonical' or d['memory_protocol'] != 'canonical':
        raise ValueError('Platform bus adapters are not released in this repository')
    for key in ('hardware_runtime', 'async_clocks', 'power_gating', 'dvfs', 'coherence',
                'translation', 'trace', 'direct_results', 'system_clock_gating'):
        if d[key] is not False:
            raise ValueError(f'Unsupported feature: {key}')
    return d


def native_groups(catalog, n):
    """Field order is explicit in the generated descriptor schema, not port order ABI."""
    def fields(names, divide=False):
        return [(name, catalog[name][1]//n if divide else catalog[name][1]) for name in names]
    runtime = [k for k in catalog if k.startswith('i_runtime_') and k not in (
        'i_runtime_valid', 'i_runtime_response_ready', 'i_runtime_owner_id', 'i_runtime_kernel_id',
        'i_runtime_array_package_id', 'i_runtime_manifest_hash', 'i_runtime_tag')]
    cfg = [k for k in catalog if k.startswith('i_cfg_request_') and k not in (
        'i_cfg_request_valid', 'i_cfg_request_owner_id', 'i_cfg_request_kernel_id', 'i_cfg_request_tag')]
    package = [k for k in catalog if k.startswith('i_cluster_package_') and k not in (
        'i_cluster_package_valid', 'i_cluster_package_response_ready', 'i_cluster_package_owner_id',
        'i_cluster_package_kernel_id', 'i_cluster_package_tag')]
    noc = [k for k in catalog if k.startswith('i_noc_cfg_') and k not in (
        'i_noc_cfg_valid', 'i_noc_cfg_response_ready', 'i_noc_cfg_owner_id',
        'i_noc_cfg_kernel_id', 'i_noc_cfg_tag')]
    groups = {
        0: dict(name='runtime', fields=fields(runtime), valid='i_runtime_valid', ready='o_runtime_ready',
            response='o_runtime_response_valid', response_ready='i_runtime_response_ready',
            error='o_runtime_response_error_code', tag='o_runtime_response_tag',
            outputs=[k for k in catalog if k.startswith('o_runtime_response_') and k != 'o_runtime_response_valid']),
        1: dict(name='configuration', fields=fields(cfg), valid='i_cfg_request_valid', ready='o_cfg_request_ready',
            response='o_cfg_response_valid', response_ready='i_cfg_response_ready',
            error='o_cfg_response_error_code', tag='o_cfg_response_tag', last='o_cfg_response_last',
            outputs=[k for k in catalog if k.startswith('o_cfg_response_') and k != 'o_cfg_response_valid']),
        2: dict(name='package', fields=fields(package, True), valid='i_cluster_package_valid',
            ready='o_cluster_package_ready', response='o_cluster_package_response_valid',
            response_ready='i_cluster_package_response_ready', error='o_cluster_package_response_error_code',
            tag='o_cluster_package_response_tag', outputs=['o_cluster_package_response_error_code',
                'o_cluster_package_response_tag'], local=True),
        3: dict(name='region', fields=fields(['i_cluster_mst_region_index', 'i_cluster_mst_region_record'], True),
            valid='i_cluster_mst_region_valid', ready='o_cluster_mst_region_ready',
            response='o_cluster_mst_region_response_valid', response_ready='i_cluster_mst_region_response_ready',
            error='o_cluster_mst_region_response_code', local=True,
            outputs=['o_cluster_mst_region_response_code']),
        4: dict(name='buffer', fields=fields(['i_cluster_mst_buffer_index', 'i_cluster_mst_buffer_record'], True),
            valid='i_cluster_mst_buffer_valid', ready='o_cluster_mst_buffer_ready',
            response='o_cluster_mst_buffer_response_valid', response_ready='i_cluster_mst_buffer_response_ready',
            error='o_cluster_mst_buffer_response_code', local=True,
            outputs=['o_cluster_mst_buffer_response_code']),
        5: dict(name='descriptor', fields=fields([k for k in catalog if k.startswith('i_cluster_mst_descriptor_')
            and k != 'i_cluster_mst_descriptor_valid'], True), valid='i_cluster_mst_descriptor_valid',
            ready='o_cluster_mst_descriptor_ready', response='o_cluster_mst_descriptor_accepted',
            error='o_cluster_mst_rejection_code', local=True, outputs=['o_cluster_mst_rejection_code']),
        6: dict(name='noc', fields=fields(noc), valid='i_noc_cfg_valid', ready='o_noc_cfg_ready',
            response='o_noc_cfg_response_valid', response_ready='i_noc_cfg_response_ready',
            error='o_noc_cfg_response_status', tag='o_noc_cfg_response_tag',
            outputs=[k for k in catalog if k.startswith('o_noc_cfg_response_') and k != 'o_noc_cfg_response_valid']),
    }
    if n == 1:
        groups.pop(6)
    for kind, group in groups.items():
        group['kind'] = kind
        offset = 0
        group['payload'] = []
        for name, width in group['fields']:
            group['payload'].append(dict(name=name, offset=offset, width=width))
            offset += width
        group['payload_bits'] = offset
        assert offset <= 1536
    return groups


def generate(descriptor=HERE/'rtl.toml', output=ROOT/'src/rtl/mosaic_blocks/system.sv', artifacts=HERE/'generated'):
    descriptor, output, artifacts = Path(descriptor), Path(output), Path(artifacts)
    d = validate(tomllib.loads(descriptor.read_text()))
    artifacts.mkdir(parents=True, exist_ok=True)
    ad = tomllib.loads((HERE.parent/'array/mvp.toml').read_text())
    if d['clusters'] == 1:
        ad.update(profile='Array-Single-Cluster', cols=1, clusters=ad['clusters'][:1])
    ap = artifacts/'array'
    ap.mkdir(exist_ok=True)
    (ap/'descriptor.toml').write_text(array.toml_text(ad))
    ac = array.generate(ap/'descriptor.toml', ap/'array.sv', ap)
    catalog = json.loads((ap/'ports.json').read_text())
    groups = native_groups(catalog, d['clusters'])
    cp = array.cluster.ports('system_core', dict(N=d['clusters'], B=d['buffers'], D=d['memory_data_width']))
    b = array.Builder()
    core = {}
    for name, (direction, width) in cp.items():
        if name.startswith(('i_array_', 'o_array_', 'i_dispatch_', 'o_dispatch_')):
            core[name] = b.wire('core_'+name, width)
        else:
            core[name] = b.port(name, direction, width)
    b.port('i_scan_enable', 'input')
    am = {name: b.wire('array_'+name, width) for name, (_, width) in catalog.items()}
    am.update(i_clk='i_clk', i_rstb='i_rstb', i_test_mode='i_test_mode', i_scan_enable='i_scan_enable')
    # Core/array handshake payloads are private. No raw functional array control escapes.
    for source, target in [('native_epochs', 'cluster_mst_execution_epoch'),
        ('native_generations', 'cluster_status_allocation_generation'),
        ('scratchpad_generations', 'cluster_status_scratchpad_generation'), ('manifest_hash', 'manifest_hash'), ('allocated', 'allocated'),
        ('running', 'running'), ('fatal', 'fatal')]:
        b.assign(core['i_array_'+source], am['o_'+target])
    for source, target in [('type','type'), ('source','source_id'), ('owner','owner_id'),
        ('kernel','kernel_id'), ('package','package_id'), ('epoch','epoch'), ('context','context_id'),
        ('payload','payload'), ('sequence','sequence'), ('severity','severity'), ('valid','valid')]:
        b.assign(core['i_array_event_'+source], am['o_event_'+target])
    b.assign(am['i_event_ready'], core['o_array_event_ready'])
    driven = {'i_clk', 'i_rstb', 'i_test_mode', 'i_scan_enable', 'i_event_ready'}
    # Native status remains observable; it is never a substitute for host completion.
    for name in ('o_allocated','o_running','o_fatal','o_allocation_generations',
                 'o_execution_epochs','o_local_package_ids','o_array_state','o_first_error',
                 'o_cluster_status_tile_versions','o_cluster_status_scratchpad_generation',
                 'o_cluster_status_manifest_hash','o_cluster_status_allocation_generation',
                 'o_cluster_mst_completion_valid','o_cluster_mst_completion_identity',
                 'o_cluster_mst_completion_bytes_read',
                 'o_cluster_mst_completion_bytes_written','o_cluster_mst_completion_status',
                 'o_cluster_mst_completion_partial','o_cluster_mst_completion_effects_unknown',
                 'o_cluster_mst_error','o_cluster_mst_idle'):
        public = 'o_array_'+name[2:]
        b.port(public, 'output', catalog[name][1]); b.assign(public, am[name])
    if d['clusters'] > 1:
        for name in ('o_noc_accepted_packets','o_noc_delivered_packets','o_noc_idle'):
            public = 'o_array_'+name[2:]
            b.port(public,'output',catalog[name][1]); b.assign(public,am[name])
    build_dispatcher(b, core, am, catalog, groups, d['clusters'], ac['manifest_sha256'])
    # Fill only unused native boundaries. Session-end is a persistent command below.
    for name, (direction, _) in catalog.items():
        if direction == 'input' and name not in driven and name not in b.bound:
            value = "'1" if name in ('i_cluster_mst_completion_ready', 'i_cluster_mst_rejection_ready',
                'i_cluster_mst_dma_out_ready', 'i_cluster_memory_rsp_ready', 'i_cluster_boundary_ready') else "'0"
            b.assign(am[name], value)
    b.instance('array','array',catalog,am)
    parameters = dict(NUM_CLUSTERS=d['clusters'], NUM_BUFFERS=d['buffers'],
        COMMAND_DEPTH=d['command_depth'], EVENT_DEPTH=d['event_depth'], MEM_DATA_WIDTH=d['memory_data_width'],
        MEMORY_TIMEOUT=d['memory_timeout'], SRAM_BYTES=ac['native_clusters'][0]['geometry']['capacity']
            if 'native_clusters' in ac else ad['clusters'][0]['scratchpad_banks']*ad['clusters'][0]['scratchpad_bank_words']*8,
        SYSTEM_HASH="256'hSYSTEM_ID", ARRAY_HASH="256'h"+ac['manifest_sha256'])
    b.instance('system_core','core',cp,core,parameters)
    tables = dict(REGISTER_BLOCK_TABLE=[dict(base=i<<12,size=4096) for i in range(9)],
        REGISTER_FIELD_TABLE={k:dict(offset=v[0], access=v[1], words=v[2] if len(v)>2 else 1)
            for k,v in REGISTERS.items()},
        ADDRESS_REGION_TABLE=[dict(base=0x100000,limit='2^64',translation='physical')],
        REQUESTER_PERMISSION_TABLE=dict(owner='requester_id', privileged_min=4, administrator=1),
        KERNEL_SLOT_TABLE=[dict(slot=0,clusters=d['clusters'])], PACKAGE_SLOT_TABLE=['array resident package'],
        BUFFER_DESCRIPTOR_TABLE=dict(count=d['buffers'],generation_bits=16,ownership=['host','dma','transfer','invalid']),
        DMA_CHANNEL_TABLE=[dict(channel=0,kind='serialized canonical memory to native SRAM bridge',max_bytes=4096)],
        MEMORY_REQUESTER_TABLE=['program/configuration fetch','input/output transfer'],
        MEMORY_PORT_ROUTE_TABLE=[dict(port=0,outstanding=1,id_bits=16,read_burst_bytes=256,write_burst_bytes=d['memory_data_width']//8)],
        EVENT_ROUTE_TABLE=dict(record_bits=512,sequence_bits=32,ack='explicit full sequence',depth=d['event_depth']),
        INTERRUPT_ROUTE_TABLE=dict(output=0,kind='level',mask_bits=8,fatal='unmaskable'),
        COUNTER_SELECT_TABLE=['host accepted controls','external read bytes','committed write bytes','queued events'],
        ERROR_SOURCE_TABLE=['host','descriptor','buffer','memory','fence','array','protected queues'],
        CLOCK_DOMAIN_TABLE=['i_clk common synchronous'], RESET_DOMAIN_TABLE=['i_rstb common synchronous'],
        POWER_DOMAIN_TABLE=['always powered'], RESET_ORDER_TABLE=['platform drains old memory and acknowledges reset',
            'native array manifest match','doorbell admission'], POWER_SEQUENCE_TABLE=['native array clock gates only'],
        TEST_MODE_TABLE=['idle-only test entry','functional doorbells blocked','native scan override'])
    deps = {str((ROOT/f'src/rtl/{p}.sv').relative_to(ROOT)):digest(ROOT/f'src/rtl/{p}.sv') for p in HELPERS}
    contract = dict(schema='mosaic-system-v1',descriptor=d,array_manifest_sha256=ac['manifest_sha256'],
        register_map=tables['REGISTER_FIELD_TABLE'],groups=groups,tables=tables,
        descriptor_layout=dict(bytes=256,alignment=256,payload_offset=64,payload_bits=1536,
            magic=0x5359534d,schema=1,crc='CRC32C whole record with bytes 28..31 zero',
            header_fields=dict(magic=[0,32],schema=[32,16],kind=[48,8],flags=[56,8],owner=[64,16],
                kernel=[80,16],package=[96,32],generation=[128,16],epoch=[144,8],slot=[152,8],
                payload_bits=[160,16],tag=[192,16],crc=[224,32],system_hash=[256,256])),
        array=ac,dependency_sha256=deps,generator_sha256={str(Path(__file__).relative_to(ROOT)):digest(__file__)},
        limits=dict(active_kernels=1,whole_array_allocation=True,memory_ports=1,outstanding=1,
            max_transfer_bytes=4096,descriptor_burst_bytes=256,partial_writes='IRQ mask only',byte_order='little',
            async_clocks=False,system_clock_gating=False,configuration='memory-resident canonical records'),
        external_obligations=['trusted requester and privilege attributes','software cache clean/invalidate',
            'platform fence visibility acknowledgement','memory reset acknowledgement only after stale responses drain'],
        unsupported=['balanced four-cluster array','AXI/APB/TileLink/platform adapters','hardware runtime',
            'concurrent kernels','CDC','power gating/retention/DVFS','coherence/IOMMU',
            'trace/direct result window','chained/strided/unaligned DMA','memory response reordering'],
        signoff=dict(validation='Python-only',synthesis='Design Compiler (deferred)',lint='NOT_RUN',
            formal='NOT_RUN',physical='NOT_CHARACTERIZED'))
    identity = hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest()
    contract['manifest_sha256'] = identity
    # Keep long generated signal bindings within the repository's 100-column limit.
    formatted = []
    for line in b.code:
        operator = next((op for op in (' <= ', ' = ', ' === ', ' !== ') if op in line), None)
        if len(line) > 100 and operator:
            left, right = line.split(operator, 1)
            formatted.extend([left + operator.rstrip(), '            ' + right])
        else:
            formatted.append(line)
    b.code = formatted
    text = b.render(identity).replace('module array (','module system (').replace(
        'src/gen/array/generate.py','src/gen/system/generate.py').replace("256'hSYSTEM_ID","256'h"+identity)
    output.parent.mkdir(parents=True,exist_ok=True); output.write_text(text)
    contract['generated_rtl_sha256'] = digest(output)
    (artifacts/'manifest.json').write_text(json.dumps(contract,indent=2)+'\n')
    (artifacts/'registers.json').write_text(json.dumps(contract['register_map'],indent=2)+'\n')
    (artifacts/'descriptors.json').write_text(json.dumps(dict(layout=contract['descriptor_layout'],groups=groups),indent=2)+'\n')
    (artifacts/'ports.json').write_text(json.dumps(b.ports,indent=2)+'\n')
    sources = (ap/'sources.f').read_text().splitlines()
    register_package = artifacts/'system_registers_pkg.sv'
    definitions = ['`timescale 1ns / 1ps', '// GENERATED canonical MMIO byte offsets.',
        'package system_registers_pkg;', '    typedef enum logic [31:0] {']
    definitions += [f"        SYS_REG_{key} = 32'h{value[0]:04x}" +
        (',' if index + 1 < len(REGISTERS) else '')
        for index, (key, value) in enumerate(REGISTERS.items())]
    definitions += ['    } system_register_t;',
        '    function automatic logic system_register_readonly(input logic [31:0] address);',
        "        system_register_readonly = 1'b0;"]
    for key, value in REGISTERS.items():
        if value[1] == 'RO':
            words = value[2] if len(value) > 2 else 1
            definitions += [f'        if (address >= SYS_REG_{key} &&',
                f"            address < SYS_REG_{key} + 32'd{words*4})",
                "            system_register_readonly = 1'b1;"]
    definitions += ['    endfunction', 'endpackage', '']
    register_package.write_text('\n'.join(definitions))
    sources += ['src/rtl/mosaic_blocks/system_pkg.sv',
        str(register_package.relative_to(ROOT)) if register_package.is_relative_to(ROOT) else str(register_package),
        'src/rtl/mosaic_blocks/system_core.sv']
    sources += [str(output.relative_to(ROOT)) if output.is_relative_to(ROOT) else str(output)]
    (artifacts/'sources.f').write_text('\n'.join(dict.fromkeys(sources))+'\n')
    header = ['/* GENERATED System-RTL register and descriptor ABI. */','#ifndef MOSAIC_SYSTEM_H',
        '#define MOSAIC_SYSTEM_H','#include <stdint.h>',f'#define MOSAIC_SYSTEM_HASH "{identity}"',
        '#define MOSAIC_SYSTEM_RECORD_BYTES 256u','#define MOSAIC_SYSTEM_RECORD_ALIGNMENT 256u']
    header += [f'#define MOSAIC_SYS_{k} 0x{v[0]:04x}u' for k,v in REGISTERS.items()]
    header += ['/* Words are little endian; writes require an explicit commit/doorbell. */',
        'typedef struct { uint32_t words[64]; } mosaic_system_record_t;','#endif','']
    (artifacts/'system.h').write_text('\n'.join(header))
    names=('system_registers_pkg.sv','system.h','registers.json','descriptors.json','ports.json')
    contract['artifact_sha256']={name:digest(artifacts/name) for name in names}
    (artifacts/'manifest.json').write_text(json.dumps(contract,indent=2)+'\n')
    return contract


def build_dispatcher(b, core, am, catalog, groups, n, array_hash):
    """One captured command owns the native channel through its terminal response."""
    b.bound = {'i_event_ready','i_clk','i_rstb','i_test_mode','i_scan_enable'}
    lines = b.code
    lines += ['    logic [1:0] adapter_state;', '    logic [7:0] adapter_kind;',
        '    logic [7:0] adapter_slot;', '    logic [15:0] adapter_owner;',
        '    logic [15:0] adapter_kernel;', '    logic [31:0] adapter_package;',
        '    logic [15:0] adapter_tag;', '    logic [7:0] adapter_epoch;',
        '    logic [1535:0] adapter_payload;', '    logic [7:0] adapter_error;', '    logic adapter_fault;',
        '    logic [1023:0] adapter_result;', '    logic [15:0] expected_payload_bits;',
        '    logic native_ready;', '    logic native_response;', '    logic native_last;',
        '    logic [7:0] native_error;', '    logic native_identity;',
        '    logic [1023:0] native_result;', f'    logic [{n-1}:0] session_end;',
        '    wire adapter_authorized = adapter_slot < '+str(n)+' && (adapter_kind == 0 ||',
        '        (adapter_kind == 6 ? array_o_allocated == 0 :',
        '        array_o_allocated[adapter_slot] &&',
        '        array_o_owner_ids[adapter_slot*16+:16] == adapter_owner &&',
        '        array_o_kernel_ids[adapter_slot*16+:16] == adapter_kernel &&',
        '        array_o_array_package_ids[adapter_slot*32+:32] == adapter_package &&',
        '        array_o_execution_epochs[adapter_slot*8+:8] == adapter_epoch));']
    b.assign(core['i_dispatch_ready'], 'adapter_state == 0')
    b.assign(core['i_dispatch_response_valid'], 'adapter_state == 3')
    b.assign(core['i_dispatch_response_error'], 'adapter_error')
    b.assign(core['i_dispatch_response_fault'], 'adapter_fault')
    b.assign(core['i_dispatch_response_data'], 'adapter_result')
    b.assign(core['i_dispatch_payload_bits'], 'expected_payload_bits')
    def bind(name, value):
        assert name not in b.bound, name
        b.bound.add(name); b.assign(am[name],value)
    def extract(name, local=False):
        width=catalog[name][1]//n if local else catalog[name][1]
        return f'{am[name]}[adapter_slot*{width}+:{width}]' if local else am[name]
    for kind,g in groups.items():
        condition=f'adapter_state == 1 && adapter_kind == 8\'d{kind} && adapter_authorized && !o_fatal'
        bind(g['valid'], f"({condition}) ? ({n}'d1 << adapter_slot) : '0" if g.get('local') else condition)
        for f in g['payload']:
            value=f'adapter_payload[{f["offset"]}+:{f["width"]}]'
            if g.get('local'):
                value=f"({condition}) ? ({catalog[f['name']][1]}'({value}) << (adapter_slot * {f['width']})) : '0"
            bind(f['name'],value)
        if 'response_ready' in g:
            value="adapter_state == 2 && adapter_kind == 8'd"+str(kind)
            if g.get('local'): value=f"({value}) ? ({n}'d1 << adapter_slot) : '0"
            bind(g['response_ready'], value)
    injections = dict(i_runtime_owner_id='adapter_owner',i_runtime_kernel_id='adapter_kernel',
        i_runtime_array_package_id='adapter_package',i_runtime_manifest_hash="256'h"+array_hash,
        i_runtime_tag='adapter_tag',i_cfg_cluster_slot='adapter_slot[0]',
        i_cfg_array_package_id='adapter_package',i_cfg_request_owner_id='adapter_owner',
        i_cfg_request_kernel_id='adapter_kernel',i_cfg_request_tag='adapter_tag')
    for name,value in injections.items(): bind(name,value)
    for suffix,value in [('owner_id','adapter_owner'),('kernel_id','adapter_kernel'),('tag','adapter_tag')]:
        name='i_cluster_package_'+suffix
        width=catalog[name][1]//n
        bind(name,f"{catalog[name][1]}'({value}) << (adapter_slot * {width})")
    if n>1:
        for suffix,value in [('owner_id','adapter_owner'),('kernel_id','adapter_kernel'),('tag','adapter_tag')]:
            bind('i_noc_cfg_'+suffix,value)
    bind('i_cluster_mst_session_end','session_end')
    # The system owns client zero of each native SRAM boundary. Other clients are idle.
    for suffix,value,width in [('valid',"adapter_state == 1 && adapter_kind == 11 && adapter_authorized && !o_fatal",1),
        ('opcode','adapter_payload[1:0]',2),('addr','adapter_payload[33:2]',catalog['i_cluster_memory_req_addr'][1]//(n*3)),
        ('size',"4'd8",4),('wdata','adapter_payload[97:34]',64),('wstrb','adapter_payload[105:98]',8),
        ('owner_id','adapter_owner',16),('kernel_id','adapter_kernel',16),
        ('generation','adapter_payload[121:106]',16),('region_id','adapter_payload[124:122]',3),('tag','adapter_tag',76)]:
        name='i_cluster_memory_req_'+suffix
        bind(name,f"{catalog[name][1]}'({value}) << (adapter_slot * {3*width})")
    # SRAM response ready is private; native completion and rejection sinks are not.
    bind('i_cluster_memory_rsp_ready',f"adapter_state == 2 && adapter_kind == 11 ? ({n*3}'d1 << (adapter_slot * 3)) : '0")
    lines += ['    always_comb begin','        expected_payload_bits = 16\'hffff;',
        '        case (core_o_dispatch_kind)']
    for kind,g in groups.items(): lines.append(f"            8'd{kind}: expected_payload_bits = 16'd{g['payload_bits']};")
    for kind,bits in [(7,160),(8,160),(9,0),(10,8),(11,125),(12,1)]:
        lines.append(f"            8'd{kind}: expected_payload_bits = 16'd{bits};")
    lines += ['            default: begin end','        endcase','    end',
        '    always_comb begin',"        native_ready = 1'b0;","        native_response = 1'b0;",
        "        native_last = 1'b1;","        native_error = 8'd0;",
        "        native_identity = 1'b1;","        native_result = '0;",'        case (adapter_kind)']
    for kind,g in groups.items():
        local=g.get('local',False)
        lines += [f"            8'd{kind}: begin",f"                native_ready = {extract(g['ready'],local)};",
            f"                native_response = {extract(g['response'],local)};",
            f"                native_error = {extract(g['error'],local)};"]
        if kind==5:
            lines += [f"                native_response = {extract('o_cluster_mst_descriptor_accepted',True)} ||",
                f"                    {extract('o_cluster_mst_descriptor_rejected',True)};",
                f"                native_error = {extract('o_cluster_mst_descriptor_rejected',True)} ?",
                f"                    {extract('o_cluster_mst_rejection_code',True)} : 8'd0;"]
        if 'last' in g: lines.append(f"                native_last = {am[g['last']]};")
        if 'tag' in g:
            checks=[f"{extract(g['tag'],local)} === adapter_tag"]
            if kind==0:
                checks += ["array_o_runtime_response_command === adapter_payload[4:0]",
                    f"array_o_runtime_response_cluster_mask === adapter_payload[5+:{n}]"]
            if kind==1:
                epoch=next(f['offset'] for f in g['payload'] if f['name']=='i_cfg_request_epoch')
                checks += ["array_o_cfg_response_command === adapter_payload[4:0]",
                    f"array_o_cfg_response_epoch === adapter_payload[{epoch}+:4]"]
            lines.append('                native_identity = ' + ' && '.join('('+c+')' for c in checks)+';')
        offset=0
        g['response_payload']=[]
        for name in g['outputs']:
            width=catalog[name][1]//n if local else catalog[name][1]
            g['response_payload'].append(dict(name=name,offset=offset,width=width))
            lines.append(f"                native_result[{offset}+:{width}] = {extract(name,local)};")
            offset+=width
        lines.append('            end')
    lines += ["            8'd11: begin",'                native_ready = array_o_cluster_memory_req_ready[adapter_slot*3];',
        '                native_response = array_o_cluster_memory_rsp_valid[adapter_slot*3];',
        '                native_error = array_o_cluster_memory_rsp_error[adapter_slot*3] ?',
        '                    array_o_cluster_memory_rsp_error_code[adapter_slot*24+:8] : 8\'d0;',
        '                native_identity = array_o_cluster_memory_rsp_tag[adapter_slot*228+:76] ===',
        "                    76'(adapter_tag) &&",
        '                    array_o_cluster_memory_rsp_opcode[adapter_slot*6+:2] === adapter_payload[1:0] &&',
        '                    array_o_cluster_memory_rsp_generation[adapter_slot*48+:16] === adapter_payload[121:106] &&',
        '                    array_o_cluster_memory_rsp_region_id[adapter_slot*9+:3] === adapter_payload[124:122];','                native_result[71:64] = native_error;', '                native_result[63:0] =',
        '                    array_o_cluster_memory_rsp_rdata[adapter_slot*192+:64];','            end',
        "            8'd12: begin", "                native_ready = 1'b1;", "                native_response = 1'b1;",'            end',
        '            default: begin end','        endcase','    end',
        '    always @(posedge i_clk) begin',"        if (i_rstb !== 1'b1) begin",
        "            adapter_state <= '0;","            adapter_kind <= '0;","            adapter_slot <= '0;",
        "            adapter_owner <= '0;","            adapter_kernel <= '0;","            adapter_package <= '0;",
        "            adapter_tag <= '0;","            adapter_epoch <= '0;","            adapter_payload <= '0;",
        "            adapter_error <= '0;", "            adapter_fault <= 1'b0;","            adapter_result <= '0;","            session_end <= '0;",
        '        end else begin','            case (adapter_state)',
        "                2'd0: begin",'                    if (core_o_dispatch_valid) begin']
    for suffix in ('kind','slot','owner','kernel','package','tag','epoch','payload'):
        lines.append(f'                        adapter_{suffix} <= core_o_dispatch_{suffix};')
    lines += ["                        adapter_error <= '0;", "                        adapter_fault <= 1'b0;","                        adapter_result <= '0;",
        "                        adapter_state <= 2'd1;",'                    end','                end',
        "                2'd1: begin",'                    if (!adapter_authorized || o_fatal) begin',
        "                        adapter_error <= 8'd2;","                        adapter_state <= 2'd3;",
        '                    end else if (native_ready) begin',
        "                        if (adapter_kind == 12) session_end[adapter_slot] <= adapter_payload[0];",
        "                        adapter_state <= 2'd2;",'                    end','                end',
        "                2'd2: begin",'                    if (native_response) begin',
        "                        if (adapter_kind == 0 && adapter_payload[4:0] == 12 &&",
        "                            native_error === 8'd0 && native_identity) session_end <= '0;",
        '                        adapter_result <= native_result;',
        "                        if (!native_identity) begin", "                            adapter_fault <= 1'b1;",
        "                            adapter_error <= 8'd14;", "                        end",
        "                        else if (^native_error === 1'bx) begin",
        "                            adapter_fault <= 1'b1;", "                            adapter_error <= 8'd14;",
        '                        end else if (native_error != 0) adapter_error <= native_error;',
        "                        if (native_last) adapter_state <= 2'd3;",'                    end','                end',
        "                2'd3: if (core_o_dispatch_response_ready) adapter_state <= 2'd0;",
        '            endcase','        end','    end']


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--descriptor',type=Path,default=HERE/'rtl.toml')
    p.add_argument('--output',type=Path,default=ROOT/'src/rtl/mosaic_blocks/system.sv')
    p.add_argument('--artifacts',type=Path,default=HERE/'generated')
    a=p.parse_args(); generate(a.descriptor,a.output,a.artifacts)

if __name__ == '__main__': main()
