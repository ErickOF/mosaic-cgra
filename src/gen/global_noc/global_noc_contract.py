"""Global NoC v1: shared public layout, topology and configuration encodings."""
from __future__ import annotations

DEFAULTS = {'NOC_X': 2,
 'NOC_Y': 2,
 'NUM_ROUTERS': 4,
 'NUM_ENDPOINTS': 4,
 'NOC_PROFILE': 1,
 'FLIT_DATA_WIDTH': 32,
 'ENDPOINT_DATA_WIDTH': 128,
 'NUM_VCS': 4,
 'INPUT_VC_DEPTH': 4,
 'FLOW_CONTROL': 1,
 'ROUTING_ALGORITHM': 0,
 'ROUTER_OUTPUT_PIPELINE': 1,
 'LINK_PIPELINE_STAGES': 0,
 'CREDIT_RETURN_PIPELINE_STAGES': 0,
 'NUM_TRAFFIC_CLASSES': 8,
 'ENABLE_QOS': 1,
 'HIGH_SERVICE_BURST_LIMIT': 8,
 'MAX_PACKET_FLITS': 16,
 'NUM_TX_CHANNELS_PER_ENDPOINT': 4,
 'NUM_RX_CHANNELS_PER_ENDPOINT': 4,
 'ENDPOINT_TX_QUEUE_DEPTH': 2,
 'ENDPOINT_RX_VC_DEPTH': 4,
 'ENDPOINT_RX_QUEUE_DEPTH': 2,
 'MAX_ACTIVE_FLOWS': 16,
 'FLOW_ID_WIDTH': 16,
 'OWNER_ID_WIDTH': 16,
 'KERNEL_ID_WIDTH': 16,
 'PACKAGE_ID_WIDTH': 32,
 'NODE_ID_WIDTH': 8,
 'ENDPOINT_ID_WIDTH': 8,
 'CONTEXT_ID_WIDTH': 8,
 'MESSAGE_TYPE_WIDTH': 4,
 'PACKET_ID_WIDTH': 16,
 'FRAGMENT_INDEX_WIDTH': 4,
 'USER_METADATA_WIDTH': 64,
 'ERROR_WIDTH': 8,
 'LINK_EPOCH_WIDTH': 4,
 'EXECUTION_EPOCH_WIDTH': 8,
 'ALLOCATION_GENERATION_WIDTH': 16,
 'PACKAGE_SLOT_WIDTH': 8,
 'FLOW_SEQUENCE_WIDTH': 16,
 'FENCE_ID_WIDTH': 8,
 'CONFIG_DATA_WIDTH': 64,
 'CONFIG_VERSION_WIDTH': 16,
 'CONFIG_TAG_WIDTH': 16,
 'CONFIG_CRC_WIDTH': 32,
 'RUNTIME_TAG_WIDTH': 16,
 'DRAIN_TIMEOUT_CYCLES': 65535,
 'ENABLE_LINK_PARITY': 0,
 'BUFFER_PROTECTION': 0,
 'CONTROL_PROTECTION': 0,
 'ENABLE_FAULT_MASKS': 1,
 'ENABLE_COUNTERS': 1,
 'ENABLE_TRACE': 0,
 'ASYNC_ENDPOINT_MASK': 0,
 'ASYNC_RESET': 0}
ALIASES = {'NN': 'NUM_ROUTERS',
 'NE': 'NUM_ENDPOINTS',
 'D': 'FLIT_DATA_WIDTH',
 'TD': 'ENDPOINT_DATA_WIDTH',
 'V': 'NUM_VCS',
 'DEPTH': 'INPUT_VC_DEPTH',
 'TX': 'NUM_TX_CHANNELS_PER_ENDPOINT',
 'RX': 'NUM_RX_CHANNELS_PER_ENDPOINT',
 'MF': 'MAX_ACTIVE_FLOWS',
 'N': 'NODE_ID_WIDTH',
 'EP': 'ENDPOINT_ID_WIDTH',
 'CX': 'CONTEXT_ID_WIDTH',
 'MT': 'MESSAGE_TYPE_WIDTH',
 'PI': 'PACKET_ID_WIDTH',
 'F': 'FRAGMENT_INDEX_WIDTH',
 'U': 'USER_METADATA_WIDTH',
 'ER': 'ERROR_WIDTH',
 'E': 'LINK_EPOCH_WIDTH',
 'RT': 'RUNTIME_TAG_WIDTH'}
PORTS = {'i_noc_clk': ('Input', '1'),
 'i_noc_rstb': ('Input', '1'),
 'i_run': ('Input', '1'),
 'i_error_clear': ('Input', '1'),
 'i_endpoint_clk': ('Input', 'NE'),
 'i_endpoint_rstb': ('Input', 'NE'),
 'i_drain_valid': ('Input', '1'),
 'o_drain_ready': ('Output', '1'),
 'i_drain_tag': ('Input', 'RT'),
 'i_flush_valid': ('Input', '1'),
 'o_flush_ready': ('Output', '1'),
 'i_flush_tag': ('Input', 'RT'),
 'i_drain_all': ('Input', '1'),
 'i_drain_flow_mask': ('Input', 'MF'),
 'o_lifecycle_valid': ('Output', '1'),
 'i_lifecycle_ready': ('Input', '1'),
 'o_lifecycle_tag': ('Output', 'RT'),
 'o_lifecycle_status': ('Output', '3'),
 'i_cfg_valid': ('Input', '1'),
 'o_cfg_ready': ('Output', '1'),
 'i_cfg_command': ('Input', '3'),
 'i_cfg_owner_id': ('Input', '16'),
 'i_cfg_kernel_id': ('Input', '16'),
 'i_cfg_package_id': ('Input', '32'),
 'i_cfg_expected_version': ('Input', '16'),
 'i_cfg_word_index': ('Input', '16'),
 'i_cfg_write_data': ('Input', '64'),
 'i_cfg_write_strobe': ('Input', '8'),
 'i_cfg_expected_crc': ('Input', '32'),
 'i_cfg_tag': ('Input', '16'),
 'o_cfg_response_valid': ('Output', '1'),
 'i_cfg_response_ready': ('Input', '1'),
 'o_cfg_response_status': ('Output', '4'),
 'o_cfg_response_data': ('Output', '64'),
 'o_cfg_response_version': ('Output', '16'),
 'o_cfg_response_crc': ('Output', '32'),
 'o_cfg_response_tag': ('Output', '16'),
 'i_tile_tx_valid': ('Input', 'NE*TX'),
 'o_tile_tx_ready': ('Output', 'NE*TX'),
 'i_tile_tx_data': ('Input', 'NE*TX*TD'),
 'i_tile_tx_keep': ('Input', 'NE*TX*TB'),
 'i_tile_tx_last': ('Input', 'NE*TX*1'),
 'i_tile_tx_context_id': ('Input', 'NE*TX*CX'),
 'i_tile_tx_message_type': ('Input', 'NE*TX*MT'),
 'i_tile_tx_traffic_class': ('Input', 'NE*TX*TC'),
 'i_tile_tx_packet_id': ('Input', 'NE*TX*PI'),
 'i_tile_tx_user_metadata': ('Input', 'NE*TX*U'),
 'i_tile_tx_error': ('Input', 'NE*TX*ER'),
 'i_tile_tx_destination_node': ('Input', 'NE*TX*N'),
 'i_tile_tx_destination_endpoint': ('Input', 'NE*TX*EP'),
 'o_tile_rx_valid': ('Output', 'NE*RX'),
 'i_tile_rx_ready': ('Input', 'NE*RX'),
 'o_tile_rx_data': ('Output', 'NE*RX*TD'),
 'o_tile_rx_keep': ('Output', 'NE*RX*TB'),
 'o_tile_rx_last': ('Output', 'NE*RX*1'),
 'o_tile_rx_context_id': ('Output', 'NE*RX*CX'),
 'o_tile_rx_message_type': ('Output', 'NE*RX*MT'),
 'o_tile_rx_traffic_class': ('Output', 'NE*RX*TC'),
 'o_tile_rx_packet_id': ('Output', 'NE*RX*PI'),
 'o_tile_rx_user_metadata': ('Output', 'NE*RX*U'),
 'o_tile_rx_error': ('Output', 'NE*RX*ER'),
 'o_tile_rx_source_node': ('Output', 'NE*RX*N'),
 'o_tile_rx_source_endpoint': ('Output', 'NE*RX*EP'),
 'i_response_reserved': ('Input', 'NE*TX'),
 'o_configured': ('Output', '1'),
 'o_running': ('Output', '1'),
 'o_idle': ('Output', '1'),
 'o_quiescent': ('Output', '1'),
 'o_draining': ('Output', '1'),
 'o_flushing': ('Output', '1'),
 'o_router_idle': ('Output', 'NN'),
 'o_endpoint_idle': ('Output', 'NE'),
 'o_link_idle': ('Output', 'NN*5'),
 'o_flow_valid': ('Output', 'MF'),
 'o_flow_outstanding': ('Output', 'MF*16'),
 'o_link_epoch': ('Output', 'NN*5*E'),
 'o_execution_epoch': ('Output', '8'),
 'o_active_version': ('Output', '16'),
 'o_active_package_id': ('Output', '32'),
 'o_router_input_vc_occupancy': ('Output', 'NN*5*V*OCC'),
 'o_router_output_credit_count': ('Output', 'NN*5*V*CW'),
 'o_endpoint_tx_queue_occupancy': ('Output', 'NE*TX*TO'),
 'o_endpoint_rx_vc_occupancy': ('Output', 'NE*V*VO'),
 'o_endpoint_rx_queue_occupancy': ('Output', 'NE*RX*RO'),
 'o_fault_mask': ('Output', 'NN*5'),
 'o_error': ('Output', '1'),
 'o_error_code': ('Output', '8'),
 'o_fatal_error': ('Output', '1'),
 'o_error_flow': ('Output', '16'),
 'o_error_endpoint': ('Output', 'N'),
 'o_accepted_packets': ('Output', '64'),
 'o_delivered_packets': ('Output', '64'),
 'o_discarded_packets': ('Output', '64'),
 'o_class_packets': ('Output', '8*32'),
 'o_flow_packets': ('Output', 'MF*32')}
FLIT_FIELDS = {'data': 'D',
 'keep': 'K',
 'head': '1',
 'tail': '1',
 'fragment_index': 'F',
 'vc': 'VW',
 'source_node': 'N',
 'source_endpoint': 'EP',
 'destination_node': 'N',
 'destination_endpoint': 'EP',
 'context_id': 'CX',
 'message_type': 'MT',
 'traffic_class': 'TC',
 'packet_id': 'PI',
 'stream_last': '1',
 'user_metadata': 'U',
 'error': 'ER',
 'epoch': 'E',
 'parity': '1'}

CFG_WRITE, CFG_READ, CFG_VALIDATE, CFG_PREPARE, CFG_COMMIT, CFG_ABORT, CFG_STATUS = range(7)
OK, BAD_COMMAND, BAD_INDEX, BAD_IMAGE, BAD_CRC, BAD_VERSION, BUSY, OWNERSHIP = range(8)
PROTOCOL_ID = 0x4E4F430000000001
CLASS_VCS = (0, 0, 1, 2, 3, 3, 0, 0)


def profile(**changes):
    p = DEFAULTS | changes
    p['NUM_ROUTERS'] = changes.get('NUM_ROUTERS', p['NOC_X'] * p['NOC_Y'])
    p['NUM_ENDPOINTS'] = changes.get('NUM_ENDPOINTS', p['NUM_ROUTERS'])
    vw = max(1, (p['NUM_VCS'] - 1).bit_length())
    vcs = CLASS_VCS if p['NOC_PROFILE'] else (0,) * 8
    p['TRAFFIC_CLASS_TO_VC'] = changes.get('TRAFFIC_CLASS_TO_VC',
        sum(v << (c * vw) for c, v in enumerate(vcs)))
    p['TRAFFIC_CLASS_TO_SERVICE'] = changes.get('TRAFFIC_CLASS_TO_SERVICE', 0x30)
    return p


def aliases(p):
    a = {k: p[v] for k, v in ALIASES.items()}
    a.update(TB=p['ENDPOINT_DATA_WIDTH']//8,K=p['FLIT_DATA_WIDTH']//8,
        VW=max(1,(p['NUM_VCS']-1).bit_length()),TC=3,
        OCC=p['INPUT_VC_DEPTH'].bit_length(),CW=p['INPUT_VC_DEPTH'].bit_length(),
        TO=p['ENDPOINT_TX_QUEUE_DEPTH'].bit_length(),VO=p['ENDPOINT_RX_VC_DEPTH'].bit_length(),
        RO=p['ENDPOINT_RX_QUEUE_DEPTH'].bit_length())
    return a


def signature(p):
    # A compiled layout identity, paired with SHA256 provenance in generated manifests.
    keys = ('NOC_X',
     'NOC_Y',
     'NUM_ROUTERS',
     'NUM_ENDPOINTS',
     'NOC_PROFILE',
     'FLIT_DATA_WIDTH',
     'ENDPOINT_DATA_WIDTH',
     'NUM_VCS',
     'INPUT_VC_DEPTH',
     'FLOW_CONTROL',
     'ROUTING_ALGORITHM',
     'ROUTER_OUTPUT_PIPELINE',
     'LINK_PIPELINE_STAGES',
     'CREDIT_RETURN_PIPELINE_STAGES',
     'NUM_TRAFFIC_CLASSES',
     'ENABLE_QOS',
     'HIGH_SERVICE_BURST_LIMIT',
     'MAX_PACKET_FLITS',
     'NUM_TX_CHANNELS_PER_ENDPOINT',
     'NUM_RX_CHANNELS_PER_ENDPOINT',
     'ENDPOINT_TX_QUEUE_DEPTH',
     'ENDPOINT_RX_VC_DEPTH',
     'ENDPOINT_RX_QUEUE_DEPTH',
     'MAX_ACTIVE_FLOWS',
     'FLOW_ID_WIDTH',
     'OWNER_ID_WIDTH',
     'KERNEL_ID_WIDTH',
     'PACKAGE_ID_WIDTH',
     'NODE_ID_WIDTH',
     'ENDPOINT_ID_WIDTH',
     'CONTEXT_ID_WIDTH',
     'MESSAGE_TYPE_WIDTH',
     'PACKET_ID_WIDTH',
     'FRAGMENT_INDEX_WIDTH',
     'USER_METADATA_WIDTH',
     'ERROR_WIDTH',
     'LINK_EPOCH_WIDTH',
     'EXECUTION_EPOCH_WIDTH',
     'ALLOCATION_GENERATION_WIDTH',
     'PACKAGE_SLOT_WIDTH',
     'FLOW_SEQUENCE_WIDTH',
     'FENCE_ID_WIDTH',
     'CONFIG_DATA_WIDTH',
     'CONFIG_VERSION_WIDTH',
     'CONFIG_TAG_WIDTH',
     'CONFIG_CRC_WIDTH',
     'RUNTIME_TAG_WIDTH',
     'DRAIN_TIMEOUT_CYCLES',
     'ENABLE_LINK_PARITY',
     'BUFFER_PROTECTION',
     'CONTROL_PROTECTION',
     'ENABLE_FAULT_MASKS',
     'ENABLE_COUNTERS',
     'ENABLE_TRACE',
     'ASYNC_ENDPOINT_MASK',
     'ASYNC_RESET',
     'TRAFFIC_CLASS_TO_VC',
     'TRAFFIC_CLASS_TO_SERVICE')
    value = 0x474E4F4300000001
    for key in keys:
        value = ((value << 7) | (value >> 57)) & ((1 << 64) - 1)
        value ^= p[key]
    return value


def crc32c(words):
    crc = 0xFFFFFFFF
    for word in words:
        for byte in word.to_bytes(8, 'little'):
            crc ^= byte
            for _ in range(8):
                crc = (crc >> 1) ^ (0x82F63B78 if crc & 1 else 0)
    return crc ^ 0xFFFFFFFF


def route(source, destination, p):
    x, y = source % p['NOC_X'], source // p['NOC_X']
    dx, dy = destination % p['NOC_X'], destination // p['NOC_X']
    edges = []
    for axis in ((0,1) if p['ROUTING_ALGORITHM']==0 else (1,0)):
        while (x if axis==0 else y) != (dx if axis==0 else dy):
            node=y*p['NOC_X']+x
            if axis==0:
                port=2 if x<dx else 4
                x += 1 if x<dx else -1
            else:
                port=3 if y<dy else 1
                y += 1 if y<dy else -1
            edges.append((node,port,y*p['NOC_X']+x))
    return edges


def flow_words(*, flow_id, source, destination, tx=0, rx=0, classes=1, messages=0xFFFF,
               owner=1, kernel=1, package=1, generation=1, epoch=0, slot=0,
               context=0, budget=8, sequence=0, reply=0, valid=True):
    return [int(valid) | flow_id<<1 | generation<<17 | epoch<<33 | slot<<41 | context<<49,
        owner | kernel<<16 | package<<32,
        source | tx<<8 | destination<<16 | rx<<24 | classes<<32 | messages<<40 | budget<<56,
        reply | sequence<<16]


def metadata(flow, sequence, epoch=None):
    w0=flow[0]
    return ((w0>>1)&0xFFFF) | ((w0>>17)&0xFFFF)<<16 | (
        ((w0>>33)&255) if epoch is None else epoch)<<32 | ((w0>>41)&255)<<40 | sequence<<48


def validate(p):
    """Reject unsupported generated profiles before publishing a manifest."""
    p=profile(**p)
    if any(type(value) is not int for value in p.values()):
        raise ValueError('Parameters must be known integers')
    positive=('NOC_X','NOC_Y','FLIT_DATA_WIDTH','ENDPOINT_DATA_WIDTH','NUM_VCS',
        'INPUT_VC_DEPTH','NUM_TX_CHANNELS_PER_ENDPOINT','NUM_RX_CHANNELS_PER_ENDPOINT',
        'ENDPOINT_TX_QUEUE_DEPTH','ENDPOINT_RX_VC_DEPTH','ENDPOINT_RX_QUEUE_DEPTH',
        'MAX_ACTIVE_FLOWS','MAX_PACKET_FLITS','FRAGMENT_INDEX_WIDTH','LINK_EPOCH_WIDTH',
        'DRAIN_TIMEOUT_CYCLES','HIGH_SERVICE_BURST_LIMIT')
    if any(p[key]<=0 for key in positive):raise ValueError('Nonpositive geometry')
    if not (p['NOC_X']<=8 and p['NOC_Y']<=8 and p['NUM_VCS']<=4 and
        p['NUM_ROUTERS']==p['NOC_X']*p['NOC_Y'] and p['NUM_ENDPOINTS']==p['NUM_ROUTERS'] and
        p['MAX_ACTIVE_FLOWS']<=64 and p['NUM_TX_CHANNELS_PER_ENDPOINT']<=16 and
        p['NUM_RX_CHANNELS_PER_ENDPOINT']<=16):raise ValueError('Unsupported mesh/endpoint size')
    for key in ('FLOW_CONTROL','ROUTING_ALGORITHM','ENABLE_QOS','ENABLE_LINK_PARITY',
                'ENABLE_FAULT_MASKS','ENABLE_COUNTERS'):
        if p[key] not in (0,1):raise ValueError(f'Unsupported {key}')
    for key in ('LINK_PIPELINE_STAGES','CREDIT_RETURN_PIPELINE_STAGES'):
        if not 0<=p[key]<=4:raise ValueError(f'Unsupported {key}')
    if p['NOC_PROFILE'] not in (0,1,2) or p['BUFFER_PROTECTION'] not in (0,1,2):
        raise ValueError('Unsupported network/protection profile')
    if any(p[key]!=0 for key in ('ASYNC_ENDPOINT_MASK','ASYNC_RESET','CONTROL_PROTECTION','ENABLE_TRACE')):
        raise ValueError('Unsupported clock/reset/protection/trace setting')
    variable_widths={'FLIT_DATA_WIDTH','ENDPOINT_DATA_WIDTH','FRAGMENT_INDEX_WIDTH','LINK_EPOCH_WIDTH'}
    if any(p[k]!=v for k,v in DEFAULTS.items() if k.endswith('_WIDTH') and k not in variable_widths):
        raise ValueError('Fixed v1 identity/configuration layout')
    fragments=(p['ENDPOINT_DATA_WIDTH']+p['FLIT_DATA_WIDTH']-1)//p['FLIT_DATA_WIDTH']
    if (p['FLIT_DATA_WIDTH']%8 or p['ENDPOINT_DATA_WIDTH']%8 or
        p['ENDPOINT_RX_VC_DEPTH']!=p['INPUT_VC_DEPTH'] or p['ROUTER_OUTPUT_PIPELINE']!=1 or
        p['FRAGMENT_INDEX_WIDTH']>16 or fragments>p['MAX_PACKET_FLITS'] or
        p['MAX_PACKET_FLITS']>1<<p['FRAGMENT_INDEX_WIDTH']):
        raise ValueError('Unsupported packet/credit geometry')
    if p['DRAIN_TIMEOUT_CYCLES']>0xFFFFFFFF:raise ValueError('Drain timeout exceeds 32 bits')
    if p['FLOW_CONTROL'] and (p['INPUT_VC_DEPTH']<fragments or p['LINK_EPOCH_WIDTH']<2):
        raise ValueError('Credit mode requires complete packet capacity and epoch bits')
    if p['NUM_TRAFFIC_CLASSES']!=8:raise ValueError('The v1 layout has eight classes')
    if p['NOC_PROFILE'] and min(p['NUM_TX_CHANNELS_PER_ENDPOINT'],p['NUM_RX_CHANNELS_PER_ENDPOINT'])<2:
        raise ValueError('Balanced/protected require separate data and critical channels')
    if p['NOC_PROFILE']==0:
        if p['NUM_VCS']>2 or p['FLOW_CONTROL']!=0 or p['ENABLE_QOS']!=0:
            raise ValueError('Lite requires one/two ready-valid VCs without QoS')
    elif p['NUM_VCS']<4 or p['FLOW_CONTROL']!=1:
        raise ValueError('Balanced/protected require four credit VCs')
    if p['NOC_PROFILE']==2 and (not p['ENABLE_LINK_PARITY'] or not p['BUFFER_PROTECTION']):
        raise ValueError('Protected requires link and buffer protection')
    vw=max(1,(p['NUM_VCS']-1).bit_length())
    if (not 0<=p['TRAFFIC_CLASS_TO_VC']<1<<(8*vw) or
        not 0<=p['TRAFFIC_CLASS_TO_SERVICE']<256 or
        any((p['TRAFFIC_CLASS_TO_VC']>>(c*vw)&((1<<vw)-1))>=p['NUM_VCS'] for c in range(8))):
        raise ValueError('Illegal class/service map')
    if p['NOC_PROFILE'] and (p['TRAFFIC_CLASS_TO_SERVICE']!=0x30 or
        p['TRAFFIC_CLASS_TO_VC']!=sum(v<<(c*vw) for c,v in enumerate(CLASS_VCS))):
        raise ValueError('Balanced dependency map must be canonical')
    return p
