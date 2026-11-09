"""Repository-local SFT v1 parameter, context and connectivity contract."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tile_units import UNIT_DEFAULTS, resolve_units, unit_defaults

DEFAULTS = {'TILE_ID': 0,
 'TILE_ID_WIDTH': 16,
 'ARCH_VERSION_WIDTH': 16,
 'CAPABILITY_ID_WIDTH': 32,
 'SHELL_DATA_WIDTH': 64,
 'DATA_METADATA_WIDTH': 256,
 'DATA_INPUT_PORTS': 2,
 'DATA_OUTPUT_PORTS': 2,
 'INPUT_BUFFER_DEPTH': 1,
 'OUTPUT_BUFFER_DEPTH': 1,
 'PREDICATE_WIDTH': 1,
 'PREDICATE_METADATA_WIDTH': 16,
 'PREDICATE_INPUT_PORTS': 1,
 'PREDICATE_OUTPUT_PORTS': 1,
 'EVENT_WIDTH': 32,
 'EVENT_INPUT_PORTS': 1,
 'EVENT_OUTPUT_PORTS': 1,
 'CONTEXT_DEPTH': 4,
 'CONFIG_DATA_WIDTH': 64,
 'CONTEXT_CHECKSUM_WIDTH': 32,
 'SUPPORT_CONTEXT_CHECKSUM': 1,
 'CONFIG_ASYNC': 0,
 'CONFIG_QUEUE_DEPTH': 4,
 'OWNER_ID_WIDTH': 16,
 'KERNEL_ID_WIDTH': 16,
 'CONTEXT_VERSION_WIDTH': 16,
 'RUNTIME_TAG_WIDTH': 8,
 'STALL_REASON_WIDTH': 8,
 'ERROR_CODE_WIDTH': 8,
 'TRACE_WIDTH': 64,
 'SUPPORT_TRACE': 0,
 'SUPPORT_RETENTION': 0,
 'SUPPORT_POWER_OFF': 0,
 'CONTEXT_PROTECTION': 0,
 'CONTROL_PROTECTION': 0,
 'ASYNC_RESET': 0,
 'INPUT_WIDTH': 16,
 'INPUT_FRAC_BITS': 8,
 'OUTPUT_WIDTH': 16,
 'OUTPUT_FRAC_BITS': 12,
 'INTERNAL_WIDTH': 32,
 'INTERNAL_FRAC_BITS': 20,
 'LUT_ADDRESS_WIDTH': 8,
 'LUT_INDEX_FRACTION_WIDTH': 8,
 'LUT_BANKS': 4,
 'LUT_PIPELINE_DEPTH': 2,
 'POLY_COEFFICIENT_WIDTH': 18,
 'POLY_MAX_DEGREE': 4,
 'POLY_BANKS': 4,
 'POLY_EVALUATION_ARCH': 0,
 'RECIP_INTERNAL_WIDTH': 24,
 'RECIP_INTERNAL_FRAC_BITS': 20,
 'RECIP_SEED_ADDRESS_WIDTH': 6,
 'RECIP_MAX_ITERATIONS': 2,
 'RSQRT_INTERNAL_WIDTH': 28,
 'RSQRT_INTERNAL_FRAC_BITS': 22,
 'RSQRT_SEED_ADDRESS_WIDTH': 6,
 'RSQRT_MAX_ITERATIONS': 2,
 'EXP_RANGE_WIDTH': 40,
 'EXP_TABLE_ADDRESS_WIDTH': 6,
 'EXP_PIPELINE_DEPTH': 5,
 'REDUCTION_LANES': 4,
 'REDUCTION_ELEMENT_WIDTH': 16,
 'REDUCTION_ACC_WIDTH': 48,
 'MAX_REDUCTION_ELEMENTS': 1024,
 'FU_PROFILE': 1,
 'LOCAL_RF_DEPTH': 8,
 'LOCAL_RF_READ_PORTS': 2,
 'LOCAL_RF_WRITE_PORTS': 1,
 'REDUCTION_STATE_DEPTH': 2,
 'INPUT_FIFO_DEPTH': 4,
 'RESULT_QUEUE_DEPTH': 8,
 'MAX_INFLIGHT': 8,
 'BYPASS_PROFILE': 1,
 'SYNC_PROFILE': 2,
 'SUPPORT_SPATIAL_TEMPORAL': 1,
 'SUPPORT_INTERPOLATION': 1,
 'SUPPORT_SATURATION': 1,
 'SUPPORT_PREDICATED_TOKEN': 1,
 'SUPPORT_LOCAL_CHAINING': 1,
 'SUPPORT_FP16': 0,
 'SUPPORT_BF16': 0,
 'REQUIRE_CANONICAL_FORMAT': 1,
 'TABLE_PROTECTION': 0,
 'COEFFICIENT_PROTECTION': 0,
 'CONFIG_WORD_COUNT': 74}
PORTS = {'i_clk': ('Input', '1'),
 'i_rstb': ('Input', '1'),
 'i_cfg_clk': ('Input', '1'),
 'i_cfg_rstb': ('Input', '1'),
 'i_test_enable': ('Input', '1'),
 'i_scan_enable': ('Input', '1'),
 'o_body_clock_enable': ('Output', '1'),
 'o_monitor_clock_enable': ('Output', '1'),
 'i_data_in_valid': ('Input', 'NI'),
 'o_data_in_ready': ('Output', 'NI'),
 'i_data_in_payload': ('Input', 'NI*D'),
 'i_data_in_metadata': ('Input', 'NI*M'),
 'o_data_out_valid': ('Output', 'NO'),
 'i_data_out_ready': ('Input', 'NO'),
 'o_data_out_payload': ('Output', 'NO*D'),
 'o_data_out_metadata': ('Output', 'NO*M'),
 'i_predicate_in_valid': ('Input', 'PI'),
 'o_predicate_in_ready': ('Output', 'PI'),
 'i_predicate_in_payload': ('Input', 'PI*P'),
 'i_predicate_in_metadata': ('Input', 'PI*PM'),
 'o_predicate_out_valid': ('Output', 'PO'),
 'i_predicate_out_ready': ('Input', 'PO'),
 'o_predicate_out_payload': ('Output', 'PO*P'),
 'o_predicate_out_metadata': ('Output', 'PO*PM'),
 'i_event_in_valid': ('Input', 'EI'),
 'o_event_in_ready': ('Output', 'EI'),
 'i_event_in_payload': ('Input', 'E*EI'),
 'o_event_out_valid': ('Output', 'EO'),
 'i_event_out_ready': ('Input', 'EO'),
 'o_event_out_payload': ('Output', 'E*EO'),
 'i_cfg_request_valid': ('Input', '1'),
 'o_cfg_request_ready': ('Output', '1'),
 'i_cfg_request_command': ('Input', '3'),
 'i_cfg_request_tile_id': ('Input', 'TI'),
 'i_cfg_request_owner_id': ('Input', 'O'),
 'i_cfg_request_context_id': ('Input', 'CI'),
 'i_cfg_request_word_index': ('Input', 'WI'),
 'i_cfg_request_write_data': ('Input', 'W'),
 'i_cfg_request_write_strobe': ('Input', 'BY'),
 'i_cfg_request_expected_crc': ('Input', '32'),
 'i_cfg_request_tag': ('Input', 'T'),
 'o_cfg_response_valid': ('Output', '1'),
 'i_cfg_response_ready': ('Input', '1'),
 'o_cfg_response_command': ('Output', '3'),
 'o_cfg_response_context_id': ('Output', 'CI'),
 'o_cfg_response_read_data': ('Output', 'W'),
 'o_cfg_response_context_version': ('Output', 'V'),
 'o_cfg_response_crc': ('Output', '32'),
 'o_cfg_response_error': ('Output', '1'),
 'o_cfg_response_error_code': ('Output', 'ER'),
 'o_cfg_response_tag': ('Output', 'T'),
 'i_runtime_request_valid': ('Input', '1'),
 'o_runtime_request_ready': ('Output', '1'),
 'i_runtime_request_command': ('Input', '3'),
 'i_runtime_request_owner_id': ('Input', 'O'),
 'i_runtime_request_kernel_id': ('Input', 'K'),
 'i_runtime_request_context_id': ('Input', 'CI'),
 'i_runtime_request_tag': ('Input', 'T'),
 'o_runtime_response_valid': ('Output', '1'),
 'i_runtime_response_ready': ('Input', '1'),
 'o_runtime_response_command': ('Output', '3'),
 'o_runtime_response_state': ('Output', '4'),
 'o_runtime_response_error': ('Output', '1'),
 'o_runtime_response_error_code': ('Output', 'ER'),
 'o_runtime_response_tag': ('Output', 'T'),
 'i_power_request_valid': ('Input', '1'),
 'o_power_request_ready': ('Output', '1'),
 'i_power_request_state': ('Input', '3'),
 'o_power_response_valid': ('Output', '1'),
 'i_power_response_ready': ('Input', '1'),
 'o_power_response_state': ('Output', '3'),
 'o_power_response_error': ('Output', '1'),
 'o_power_response_error_code': ('Output', 'ER'),
 'o_body_save': ('Output', '1'),
 'i_body_save_done': ('Input', '1'),
 'o_body_restore': ('Output', '1'),
 'i_body_restore_done': ('Input', '1'),
 'o_body_isolate': ('Output', '1'),
 'i_body_isolation_ack': ('Input', '1'),
 'o_body_power_enable': ('Output', '1'),
 'i_body_power_good': ('Input', '1'),
 'o_status_tile_id': ('Output', 'TI'),
 'o_status_tile_class': ('Output', '3'),
 'o_status_arch_version': ('Output', 'AV'),
 'o_status_capability_id': ('Output', 'CP'),
 'o_status_execution_state': ('Output', '4'),
 'o_status_power_state': ('Output', '3'),
 'o_status_stall_reasons': ('Output', 'S'),
 'o_status_active_context': ('Output', 'CI'),
 'o_status_context_version': ('Output', 'V'),
 'o_status_owner_id': ('Output', 'O'),
 'o_status_kernel_id': ('Output', 'K'),
 'o_status_context_valid': ('Output', 'C'),
 'o_status_busy': ('Output', '1'),
 'o_status_idle': ('Output', '1'),
 'o_status_quiescent': ('Output', '1'),
 'o_status_error': ('Output', '1'),
 'o_status_fatal_error': ('Output', '1'),
 'o_status_error_code': ('Output', 'ER'),
 'i_debug_request_valid': ('Input', '1'),
 'o_debug_request_ready': ('Output', '1'),
 'i_debug_request_write': ('Input', '1'),
 'i_debug_request_owner_id': ('Input', 'O'),
 'i_debug_request_privileged': ('Input', '1'),
 'i_debug_request_address': ('Input', '8'),
 'i_debug_request_write_data': ('Input', 'W'),
 'i_debug_request_write_strobe': ('Input', 'BY'),
 'o_debug_response_valid': ('Output', '1'),
 'i_debug_response_ready': ('Input', '1'),
 'o_debug_response_read_data': ('Output', 'W'),
 'o_debug_response_error': ('Output', '1'),
 'o_trace_valid': ('Output', '1'),
 'i_trace_ready': ('Input', '1'),
 'o_trace_data': ('Output', 'TR')}
FIELDS = {'schema': (0, 8),
 'operation': (8, 8),
 'datatype': (16, 2),
 'signed_data': (18, 1),
 'rounding': (19, 1),
 'saturate': (20, 1),
 'interpolate': (21, 1),
 'base': (22, 1),
 'false_token': (23, 1),
 'predicate_mode': (24, 2),
 'source_a': (26, 3),
 'source_b': (29, 3),
 'rf_a': (32, 8),
 'rf_b': (40, 8),
 'rf_write': (48, 8),
 'write_rf': (56, 1),
 'write_acc': (57, 1),
 'phase': (58, 3),
 'reduction': (61, 3),
 'state_id': (64, 8),
 'bank': (72, 8),
 'quality': (80, 2),
 'range_error': (82, 1),
 'empty_policy': (83, 2),
 'terminal': (85, 1),
 'advance_context': (86, 1),
 'invalidate': (87, 1),
 'steps': (88, 16),
 'next_context': (104, 8),
 'mask': (112, 16),
 'iterations': (128, 8),
 'degree': (136, 8),
 'shift': (144, 8),
 'model': (152, 32),
 'immediate': (192, 64),
 'x_min': (256, 32),
 'x_max': (288, 32),
 'epsilon': (320, 32),
 'table_id': (352, 16),
 'polynomial_id': (368, 16),
 'source_format': (384, 8),
 'result_format': (392, 8),
 'output_mask': (400, 8),
 'opcode': (408, 5),
 'dynamic_phase': (413, 1),
 'monitor': (414, 1),
 'select_condition': (415, 1)}

def package_words(p):
    return (512 + (1 << p['LUT_ADDRESS_WIDTH']) * p['OUTPUT_WIDTH'] +
            ((p['POLY_MAX_DEGREE'] + 1) * p['POLY_COEFFICIENT_WIDTH'] if p['ENABLE_POLYNOMIAL'] else 0) + 63) // 64


DEFAULTS.update(unit_defaults("SFT"))

def profile(**changes):
    p = resolve_units("SFT", DEFAULTS | changes, changes)
    if 'CONFIG_WORD_COUNT' not in changes:
        p['CONFIG_WORD_COUNT'] = package_words(p)
    p.setdefault('INPUT_ELASTIC_MASK', (1 << p['DATA_INPUT_PORTS']) - 1)
    p.setdefault('OUTPUT_ELASTIC_MASK', (1 << p['DATA_OUTPUT_PORTS']) - 1)
    return p


def validate(p):
    for name in UNIT_DEFAULTS["SFT"]:
        if p[name] not in (0, 1):
            raise ValueError(f"{name} must be Boolean")
    if any(not isinstance(value, int) for value in p.values()):
        raise ValueError('Parameters must be known integers')
    ranges = {'FU_PROFILE': (0, 3), 'LUT_ADDRESS_WIDTH': (1, 8), 'LUT_BANKS': (1, 4),
              'POLY_BANKS': (1, 4), 'POLY_MAX_DEGREE': (1, 4), 'INPUT_WIDTH': (4, 16),
              'OUTPUT_WIDTH': (8, 32), 'CONTEXT_DEPTH': (1, 16), 'LOCAL_RF_DEPTH': (2, 32),
              'REDUCTION_LANES': (1, 16), 'REDUCTION_ELEMENT_WIDTH': (2, 16),
              'MAX_INFLIGHT': (1, 32), 'RESULT_QUEUE_DEPTH': (1, 32)}
    for key,(lo,hi) in ranges.items():
        if not lo <= p[key] <= hi: raise ValueError(f'Unsupported {key}')
    for key in ('SUPPORT_SPATIAL_TEMPORAL', 'SUPPORT_INTERPOLATION', 'SUPPORT_SATURATION',
                'SUPPORT_PREDICATED_TOKEN', 'SUPPORT_LOCAL_CHAINING', 'REQUIRE_CANONICAL_FORMAT'):
        if p[key] not in (0, 1): raise ValueError(f'Invalid boolean {key}')
    if p['ASYNC_RESET'] != 0:
        raise ValueError('The body requires synchronous reset')
    if not 1 <= p['OUTPUT_BUFFER_DEPTH'] <= 4:
        raise ValueError('Elastic outputs require a registered shell buffer')
    for key in ('OWNER_ID_WIDTH', 'KERNEL_ID_WIDTH'):
        if not 1 <= p[key] <= 32: raise ValueError('Ownership width exceeds the profile')
    if not 2 <= p['CONTEXT_VERSION_WIDTH'] <= 16:
        raise ValueError('Unsupported context version width')
    if p['SUPPORT_FP16'] or p['SUPPORT_BF16'] or p['SYNC_PROFILE'] not in (0, 2):
        raise ValueError('FP and static RDU profiles are not characterized')
    if p['RESULT_QUEUE_DEPTH'] < p['MAX_INFLIGHT']:
        raise ValueError('Retirement credits must cover every accepted operation')
    if p['REDUCTION_LANES'] * p['REDUCTION_ELEMENT_WIDTH'] > p['SHELL_DATA_WIDTH']:
        raise ValueError('Packed reduction payload is too wide')
    growth = (p['MAX_REDUCTION_ELEMENTS']).bit_length()
    if not 2 * p['REDUCTION_ELEMENT_WIDTH'] + growth <= p['REDUCTION_ACC_WIDTH'] <= p['SHELL_DATA_WIDTH']:
        raise ValueError('Exact SUMSQ growth is not representable')
    if p['CONFIG_WORD_COUNT'] < package_words(p):
        raise ValueError('Incomplete context/function-bank image')
    return p


def connectivity(p):
    sources = ['input_a', 'input_b', 'rf_a', 'rf_b', 'accumulator', 'previous', 'immediate', 'zero']
    enabled = [0, 1, 6, 7]
    if p['SUPPORT_LOCAL_CHAINING']:
        enabled.append(4)
        if p['BYPASS_PROFILE'] >= 1: enabled += [2, 3]
        if p['BYPASS_PROFILE'] == 2: enabled.append(5)
    return {name: [sources[i] for i in sorted(enabled)] for name in ('operand_a', 'operand_b')}
