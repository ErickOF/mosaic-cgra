`timescale 1ns / 1ps
`default_nettype none
// Nonlinear tile composition. The released shell owns all external protocols.
module sft #(
    parameter TILE_ID = 0,
    parameter TILE_ID_WIDTH = 16,
    parameter ARCH_VERSION_WIDTH = 16,
    parameter CAPABILITY_ID_WIDTH = 32,
    parameter SHELL_DATA_WIDTH = 64,
    parameter DATA_METADATA_WIDTH = 256,
    parameter DATA_INPUT_PORTS = 2,
    parameter DATA_OUTPUT_PORTS = 2,
    parameter INPUT_BUFFER_DEPTH = 1,
    parameter OUTPUT_BUFFER_DEPTH = 1,
    parameter PREDICATE_WIDTH = 1,
    parameter PREDICATE_METADATA_WIDTH = 16,
    parameter PREDICATE_INPUT_PORTS = 1,
    parameter PREDICATE_OUTPUT_PORTS = 1,
    parameter EVENT_WIDTH = 32,
    parameter EVENT_INPUT_PORTS = 1,
    parameter EVENT_OUTPUT_PORTS = 1,
    parameter CONTEXT_DEPTH = 4,
    parameter CONFIG_DATA_WIDTH = 64,
    parameter CONTEXT_CHECKSUM_WIDTH = 32,
    parameter SUPPORT_CONTEXT_CHECKSUM = 1,
    parameter CONFIG_ASYNC = 0,
    parameter CONFIG_QUEUE_DEPTH = 4,
    parameter OWNER_ID_WIDTH = 16,
    parameter KERNEL_ID_WIDTH = 16,
    parameter CONTEXT_VERSION_WIDTH = 16,
    parameter RUNTIME_TAG_WIDTH = 8,
    parameter STALL_REASON_WIDTH = 8,
    parameter ERROR_CODE_WIDTH = 8,
    parameter TRACE_WIDTH = 64,
    parameter SUPPORT_TRACE = 0,
    parameter SUPPORT_RETENTION = 0,
    parameter SUPPORT_POWER_OFF = 0,
    parameter CONTEXT_PROTECTION = 0,
    parameter CONTROL_PROTECTION = 0,
    parameter ASYNC_RESET = 0,
    parameter INPUT_WIDTH = 16,
    parameter INPUT_FRAC_BITS = 8,
    parameter OUTPUT_WIDTH = 16,
    parameter OUTPUT_FRAC_BITS = 12,
    parameter INTERNAL_WIDTH = 32,
    parameter INTERNAL_FRAC_BITS = 20,
    parameter LUT_ADDRESS_WIDTH = 8,
    parameter LUT_INDEX_FRACTION_WIDTH = 8,
    parameter LUT_BANKS = 4,
    parameter LUT_PIPELINE_DEPTH = 2,
    parameter POLY_COEFFICIENT_WIDTH = 18,
    parameter POLY_MAX_DEGREE = 4,
    parameter POLY_BANKS = 4,
    parameter POLY_EVALUATION_ARCH = 0,
    parameter RECIP_INTERNAL_WIDTH = 24,
    parameter RECIP_INTERNAL_FRAC_BITS = 20,
    parameter RECIP_SEED_ADDRESS_WIDTH = 6,
    parameter RECIP_MAX_ITERATIONS = 2,
    parameter RSQRT_INTERNAL_WIDTH = 28,
    parameter RSQRT_INTERNAL_FRAC_BITS = 22,
    parameter RSQRT_SEED_ADDRESS_WIDTH = 6,
    parameter RSQRT_MAX_ITERATIONS = 2,
    parameter EXP_RANGE_WIDTH = 40,
    parameter EXP_TABLE_ADDRESS_WIDTH = 6,
    parameter EXP_PIPELINE_DEPTH = 5,
    parameter REDUCTION_LANES = 4,
    parameter REDUCTION_ELEMENT_WIDTH = 16,
    parameter REDUCTION_ACC_WIDTH = 48,
    parameter MAX_REDUCTION_ELEMENTS = 1024,
    parameter FU_PROFILE = 1,
    // Explicit enables override the legacy profile without coupling peer FUs.
    parameter ENABLE_ALU = 1,
    parameter ENABLE_MULTIPLIER = FU_PROFILE >= 1,
    parameter ENABLE_LUT = 1,
    parameter ENABLE_POLYNOMIAL = FU_PROFILE >= 1,
    parameter ENABLE_RECIPROCAL = FU_PROFILE >= 2,
    parameter ENABLE_RSQRT = FU_PROFILE >= 2,
    parameter ENABLE_EXPONENTIAL = FU_PROFILE == 3,
    parameter ENABLE_REDUCTION = 1,
    parameter ENABLE_FORMATTER = 1,
    parameter ENABLE_ACCUMULATOR = 1,
    parameter LOCAL_RF_DEPTH = 8,
    parameter LOCAL_RF_READ_PORTS = 2,
    parameter LOCAL_RF_WRITE_PORTS = 1,
    parameter REDUCTION_STATE_DEPTH = 2,
    parameter INPUT_FIFO_DEPTH = 4,
    parameter RESULT_QUEUE_DEPTH = 8,
    parameter MAX_INFLIGHT = 8,
    parameter BYPASS_PROFILE = 1,
    parameter SYNC_PROFILE = 2,
    parameter SUPPORT_SPATIAL_TEMPORAL = 1,
    parameter SUPPORT_INTERPOLATION = 1,
    parameter SUPPORT_SATURATION = 1,
    parameter SUPPORT_PREDICATED_TOKEN = 1,
    parameter SUPPORT_LOCAL_CHAINING = 1,
    parameter SUPPORT_FP16 = 0,
    parameter SUPPORT_BF16 = 0,
    parameter REQUIRE_CANONICAL_FORMAT = 1,
    parameter TABLE_PROTECTION = 0,
    parameter COEFFICIENT_PROTECTION = 0,
    // Complete inactive packages contain a header and selected function-bank images.
    parameter CONFIG_WORD_COUNT = (512 + (1 << LUT_ADDRESS_WIDTH) *
        OUTPUT_WIDTH + (ENABLE_POLYNOMIAL ? (POLY_MAX_DEGREE + 1) *
        POLY_COEFFICIENT_WIDTH : 0) + CONFIG_DATA_WIDTH - 1) / CONFIG_DATA_WIDTH,
    localparam bit SFT_GEOMETRY_VALID =
        ((ENABLE_ALU === 0) || (ENABLE_ALU === 1)) &&
        ((ENABLE_MULTIPLIER === 0) || (ENABLE_MULTIPLIER === 1)) &&
        ((ENABLE_LUT === 0) || (ENABLE_LUT === 1)) &&
        ((ENABLE_POLYNOMIAL === 0) || (ENABLE_POLYNOMIAL === 1)) &&
        ((ENABLE_RECIPROCAL === 0) || (ENABLE_RECIPROCAL === 1)) &&
        ((ENABLE_RSQRT === 0) || (ENABLE_RSQRT === 1)) &&
        ((ENABLE_EXPONENTIAL === 0) || (ENABLE_EXPONENTIAL === 1)) &&
        ((ENABLE_REDUCTION === 0) || (ENABLE_REDUCTION === 1)) &&
        ((ENABLE_FORMATTER === 0) || (ENABLE_FORMATTER === 1)) &&
        ((ENABLE_ACCUMULATOR === 0) || (ENABLE_ACCUMULATOR === 1)) &&

        ((DATA_METADATA_WIDTH >= 160 && DATA_METADATA_WIDTH <= 512) === 1'b1) &&
        ((OWNER_ID_WIDTH >= 1 && OWNER_ID_WIDTH <= 32) === 1'b1) &&
        ((KERNEL_ID_WIDTH >= 1 && KERNEL_ID_WIDTH <= 32) === 1'b1) &&
        ((CONTEXT_VERSION_WIDTH >= 2 && CONTEXT_VERSION_WIDTH <= 16) === 1'b1) &&
        ((CONFIG_WORD_COUNT >= 8 && CONFIG_WORD_COUNT <= 2048) === 1'b1) &&
        ((INPUT_BUFFER_DEPTH >= 0 && INPUT_BUFFER_DEPTH <= 4) === 1'b1) &&
        ((OUTPUT_BUFFER_DEPTH >= 1 && OUTPUT_BUFFER_DEPTH <= 4) === 1'b1) &&
        (PREDICATE_WIDTH === 1) && (PREDICATE_INPUT_PORTS === 1) &&
        (PREDICATE_OUTPUT_PORTS === 1) && (EVENT_WIDTH === 32) &&
        (EVENT_INPUT_PORTS === 1) && (EVENT_OUTPUT_PORTS === 1) &&
        ((SUPPORT_SPATIAL_TEMPORAL === 0) || (SUPPORT_SPATIAL_TEMPORAL === 1)) &&
        ((SUPPORT_INTERPOLATION === 0) || (SUPPORT_INTERPOLATION === 1)) &&
        ((SUPPORT_SATURATION === 0) || (SUPPORT_SATURATION === 1)) &&
        ((SUPPORT_PREDICATED_TOKEN === 0) || (SUPPORT_PREDICATED_TOKEN === 1)) &&
        ((SUPPORT_LOCAL_CHAINING === 0) || (SUPPORT_LOCAL_CHAINING === 1)) &&
        ((REQUIRE_CANONICAL_FORMAT === 0) || (REQUIRE_CANONICAL_FORMAT === 1)) &&
        ((TABLE_PROTECTION >= 0 && TABLE_PROTECTION <= 2) === 1'b1) &&
        ((COEFFICIENT_PROTECTION >= 0 && COEFFICIENT_PROTECTION <= 2) === 1'b1) &&
        ((CONTROL_PROTECTION >= 0 && CONTROL_PROTECTION <= 2) === 1'b1) &&
        (ASYNC_RESET === 0) &&
        ((RECIP_MAX_ITERATIONS === 2) && (RSQRT_MAX_ITERATIONS === 2)) &&
        ((RECIP_INTERNAL_WIDTH >= 16 && RECIP_INTERNAL_WIDTH <= 64) === 1'b1) &&
        ((RECIP_INTERNAL_FRAC_BITS >= 8 &&
            RECIP_INTERNAL_FRAC_BITS + 2 <= RECIP_INTERNAL_WIDTH) === 1'b1) &&
        ((RECIP_SEED_ADDRESS_WIDTH >= 1 && RECIP_SEED_ADDRESS_WIDTH <= 6 &&
            RECIP_SEED_ADDRESS_WIDTH + 2 <= RECIP_INTERNAL_FRAC_BITS) === 1'b1) &&
        ((RSQRT_INTERNAL_WIDTH >= 16 && RSQRT_INTERNAL_WIDTH <= 64) === 1'b1) &&
        ((RSQRT_INTERNAL_FRAC_BITS >= 8 &&
            RSQRT_INTERNAL_FRAC_BITS + 3 <= RSQRT_INTERNAL_WIDTH) === 1'b1) &&
        ((RSQRT_SEED_ADDRESS_WIDTH >= 1 && RSQRT_SEED_ADDRESS_WIDTH <= 6 &&
            RSQRT_SEED_ADDRESS_WIDTH + 2 <= RSQRT_INTERNAL_FRAC_BITS) === 1'b1) &&
        ((EXP_RANGE_WIDTH >= 40 && EXP_RANGE_WIDTH <= 64) === 1'b1) &&
        ((EXP_TABLE_ADDRESS_WIDTH >= 1 && EXP_TABLE_ADDRESS_WIDTH <= 6) === 1'b1) &&
        ((EXP_PIPELINE_DEPTH >= 5 && EXP_PIPELINE_DEPTH <= 8) === 1'b1) &&
        ((SHELL_DATA_WIDTH >= 48 && SHELL_DATA_WIDTH <= 128) === 1'b1) &&
        ((INPUT_WIDTH >= 4 && INPUT_WIDTH <= 16) === 1'b1) &&
        ((OUTPUT_WIDTH >= 8 && OUTPUT_WIDTH <= 32) === 1'b1) &&
        ((INPUT_FRAC_BITS >= 1 && INPUT_FRAC_BITS < INPUT_WIDTH) === 1'b1) &&
        ((OUTPUT_FRAC_BITS >= 1 && OUTPUT_FRAC_BITS < OUTPUT_WIDTH) === 1'b1) &&
        ((INTERNAL_WIDTH >= 24 && INTERNAL_WIDTH <= 64) === 1'b1) &&
        ((INTERNAL_FRAC_BITS > 0 && INTERNAL_FRAC_BITS < INTERNAL_WIDTH) === 1'b1) &&
        ((LUT_ADDRESS_WIDTH >= 1 && LUT_ADDRESS_WIDTH <= 8) === 1'b1) &&
        ((LUT_INDEX_FRACTION_WIDTH >= 1 && LUT_INDEX_FRACTION_WIDTH <= 8) === 1'b1) &&
        ((LUT_BANKS >= 1 && LUT_BANKS <= 4) === 1'b1) &&
        ((POLY_BANKS >= 1 && POLY_BANKS <= 4) === 1'b1) &&
        ((POLY_MAX_DEGREE >= 1 && POLY_MAX_DEGREE <= 4) === 1'b1) &&
        ((POLY_COEFFICIENT_WIDTH > INPUT_FRAC_BITS &&
            POLY_COEFFICIENT_WIDTH <= INTERNAL_WIDTH) === 1'b1) &&
        ((POLY_EVALUATION_ARCH === 0) || (POLY_EVALUATION_ARCH === 1)) &&
        ((LUT_PIPELINE_DEPTH >= 1 && LUT_PIPELINE_DEPTH <= 4) === 1'b1) &&
        ((FU_PROFILE >= 0 && FU_PROFILE <= 3) === 1'b1) &&
        ((REDUCTION_LANES >= 1 && REDUCTION_LANES <= 16) === 1'b1) &&
        ((REDUCTION_ELEMENT_WIDTH >= 2 && REDUCTION_ELEMENT_WIDTH <= 16) === 1'b1) &&
        ((REDUCTION_LANES * REDUCTION_ELEMENT_WIDTH <= SHELL_DATA_WIDTH) === 1'b1) &&
        ((MAX_REDUCTION_ELEMENTS >= 1 && MAX_REDUCTION_ELEMENTS <= 65535) === 1'b1) &&
        ((REDUCTION_ACC_WIDTH >= 2 * REDUCTION_ELEMENT_WIDTH +
            $clog2(MAX_REDUCTION_ELEMENTS + 1) &&
            REDUCTION_ACC_WIDTH <= SHELL_DATA_WIDTH) === 1'b1) &&
        ((CONTEXT_DEPTH >= 1 && CONTEXT_DEPTH <= 16) === 1'b1) &&
        ((LOCAL_RF_DEPTH >= 2 && LOCAL_RF_DEPTH <= 32) === 1'b1) &&
        (LOCAL_RF_READ_PORTS === 2) && (LOCAL_RF_WRITE_PORTS === 1) &&
        ((REDUCTION_STATE_DEPTH >= 1 && REDUCTION_STATE_DEPTH <= 8) === 1'b1) &&
        ((INPUT_FIFO_DEPTH >= 1 && INPUT_FIFO_DEPTH <= 16) === 1'b1) &&
        ((MAX_INFLIGHT >= 1 && MAX_INFLIGHT <= 32) === 1'b1) &&
        ((RESULT_QUEUE_DEPTH >= MAX_INFLIGHT && RESULT_QUEUE_DEPTH <= 32) === 1'b1) &&
        ((BYPASS_PROFILE >= 0 && BYPASS_PROFILE <= 2) === 1'b1) &&
        ((SYNC_PROFILE === 0) || (SYNC_PROFILE === 2)) &&
        (SUPPORT_FP16 === 0) && (SUPPORT_BF16 === 0) &&
        ((CONFIG_WORD_COUNT * CONFIG_DATA_WIDTH >= 512 +
            (1 << LUT_ADDRESS_WIDTH) * OUTPUT_WIDTH + (ENABLE_POLYNOMIAL ?
            (POLY_MAX_DEGREE + 1) * POLY_COEFFICIENT_WIDTH : 0)) === 1'b1) &&
        (CONFIG_DATA_WIDTH === 64) && (DATA_INPUT_PORTS === 2) &&
        ((DATA_OUTPUT_PORTS >= 1 && DATA_OUTPUT_PORTS <= 4) === 1'b1),
    localparam int TI = SFT_GEOMETRY_VALID ? TILE_ID_WIDTH : 1,
    localparam int AV = SFT_GEOMETRY_VALID ? ARCH_VERSION_WIDTH : 1,
    localparam int CP = SFT_GEOMETRY_VALID ? CAPABILITY_ID_WIDTH : 1,
    localparam int D = SFT_GEOMETRY_VALID ? SHELL_DATA_WIDTH : 1,
    localparam int M = SFT_GEOMETRY_VALID ? DATA_METADATA_WIDTH : 1,
    localparam int NI = SFT_GEOMETRY_VALID ? DATA_INPUT_PORTS : 1,
    localparam int NO = SFT_GEOMETRY_VALID ? DATA_OUTPUT_PORTS : 1,
    localparam int BI = SFT_GEOMETRY_VALID ? INPUT_BUFFER_DEPTH : 1,
    localparam int BO = SFT_GEOMETRY_VALID ? OUTPUT_BUFFER_DEPTH : 1,
    localparam int P = SFT_GEOMETRY_VALID ? PREDICATE_WIDTH : 1,
    localparam int PM = SFT_GEOMETRY_VALID ? PREDICATE_METADATA_WIDTH : 1,
    localparam int PI = SFT_GEOMETRY_VALID ? PREDICATE_INPUT_PORTS : 1,
    localparam int PO = SFT_GEOMETRY_VALID ? PREDICATE_OUTPUT_PORTS : 1,
    localparam int E = SFT_GEOMETRY_VALID ? EVENT_WIDTH : 1,
    localparam int EI = SFT_GEOMETRY_VALID ? EVENT_INPUT_PORTS : 1,
    localparam int EO = SFT_GEOMETRY_VALID ? EVENT_OUTPUT_PORTS : 1,
    localparam int C = SFT_GEOMETRY_VALID ? CONTEXT_DEPTH : 1,
    localparam int W = SFT_GEOMETRY_VALID ? CONFIG_DATA_WIDTH : 1,
    localparam int N = SFT_GEOMETRY_VALID ? CONFIG_WORD_COUNT : 1,
    localparam int Q = SFT_GEOMETRY_VALID ? CONFIG_QUEUE_DEPTH : 1,
    localparam int O = SFT_GEOMETRY_VALID ? OWNER_ID_WIDTH : 1,
    localparam int K = SFT_GEOMETRY_VALID ? KERNEL_ID_WIDTH : 1,
    localparam int V = SFT_GEOMETRY_VALID ? CONTEXT_VERSION_WIDTH : 1,
    localparam int T = SFT_GEOMETRY_VALID ? RUNTIME_TAG_WIDTH : 1,
    localparam int S = SFT_GEOMETRY_VALID ? STALL_REASON_WIDTH : 1,
    localparam int ER = SFT_GEOMETRY_VALID ? ERROR_CODE_WIDTH : 1,
    localparam int TR = SFT_GEOMETRY_VALID ? TRACE_WIDTH : 1,
    localparam int CI = C > 1 ? $clog2(C) : 1,
    localparam int WI = N > 1 ? $clog2(N) : 1,
    localparam int BY = W / 8 > 0 ? W / 8 : 1,
    localparam int IM = W * N,
    parameter INPUT_ELASTIC_MASK = {NI{1'b1}},
    parameter OUTPUT_ELASTIC_MASK = {NO{1'b1}}
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_cfg_clk,
    input logic i_cfg_rstb,
    input logic i_test_enable,
    input logic i_scan_enable,
    output wire o_body_clock_enable,
    output wire o_monitor_clock_enable,
    input logic [NI-1:0] i_data_in_valid,
    output wire [NI-1:0] o_data_in_ready,
    input logic [NI*D-1:0] i_data_in_payload,
    input logic [NI*M-1:0] i_data_in_metadata,
    output wire [NO-1:0] o_data_out_valid,
    input logic [NO-1:0] i_data_out_ready,
    output wire [NO*D-1:0] o_data_out_payload,
    output wire [NO*M-1:0] o_data_out_metadata,
    input logic [PI-1:0] i_predicate_in_valid,
    output wire [PI-1:0] o_predicate_in_ready,
    input logic [PI*P-1:0] i_predicate_in_payload,
    input logic [PI*PM-1:0] i_predicate_in_metadata,
    output wire [PO-1:0] o_predicate_out_valid,
    input logic [PO-1:0] i_predicate_out_ready,
    output wire [PO*P-1:0] o_predicate_out_payload,
    output wire [PO*PM-1:0] o_predicate_out_metadata,
    input logic [EI-1:0] i_event_in_valid,
    output wire [EI-1:0] o_event_in_ready,
    input logic [E*EI-1:0] i_event_in_payload,
    output wire [EO-1:0] o_event_out_valid,
    input logic [EO-1:0] i_event_out_ready,
    output wire [E*EO-1:0] o_event_out_payload,
    input logic i_cfg_request_valid,
    output wire o_cfg_request_ready,
    input logic [2:0] i_cfg_request_command,
    input logic [TI-1:0] i_cfg_request_tile_id,
    input logic [O-1:0] i_cfg_request_owner_id,
    input logic [CI-1:0] i_cfg_request_context_id,
    input logic [WI-1:0] i_cfg_request_word_index,
    input logic [W-1:0] i_cfg_request_write_data,
    input logic [BY-1:0] i_cfg_request_write_strobe,
    input logic [31:0] i_cfg_request_expected_crc,
    input logic [T-1:0] i_cfg_request_tag,
    output wire o_cfg_response_valid,
    input logic i_cfg_response_ready,
    output wire [2:0] o_cfg_response_command,
    output wire [CI-1:0] o_cfg_response_context_id,
    output wire [W-1:0] o_cfg_response_read_data,
    output wire [V-1:0] o_cfg_response_context_version,
    output wire [31:0] o_cfg_response_crc,
    output wire o_cfg_response_error,
    output wire [ER-1:0] o_cfg_response_error_code,
    output wire [T-1:0] o_cfg_response_tag,
    input logic i_runtime_request_valid,
    output wire o_runtime_request_ready,
    input logic [2:0] i_runtime_request_command,
    input logic [O-1:0] i_runtime_request_owner_id,
    input logic [K-1:0] i_runtime_request_kernel_id,
    input logic [CI-1:0] i_runtime_request_context_id,
    input logic [T-1:0] i_runtime_request_tag,
    output wire o_runtime_response_valid,
    input logic i_runtime_response_ready,
    output wire [2:0] o_runtime_response_command,
    output wire [3:0] o_runtime_response_state,
    output wire o_runtime_response_error,
    output wire [ER-1:0] o_runtime_response_error_code,
    output wire [T-1:0] o_runtime_response_tag,
    input logic i_power_request_valid,
    output wire o_power_request_ready,
    input logic [2:0] i_power_request_state,
    output wire o_power_response_valid,
    input logic i_power_response_ready,
    output wire [2:0] o_power_response_state,
    output wire o_power_response_error,
    output wire [ER-1:0] o_power_response_error_code,
    output wire o_body_save,
    input logic i_body_save_done,
    output wire o_body_restore,
    input logic i_body_restore_done,
    output wire o_body_isolate,
    input logic i_body_isolation_ack,
    output wire o_body_power_enable,
    input logic i_body_power_good,
    output wire [TI-1:0] o_status_tile_id,
    output wire [2:0] o_status_tile_class,
    output wire [AV-1:0] o_status_arch_version,
    output wire [CP-1:0] o_status_capability_id,
    output wire [3:0] o_status_execution_state,
    output wire [2:0] o_status_power_state,
    output wire [S-1:0] o_status_stall_reasons,
    output wire [CI-1:0] o_status_active_context,
    output wire [V-1:0] o_status_context_version,
    output wire [O-1:0] o_status_owner_id,
    output wire [K-1:0] o_status_kernel_id,
    output wire [C-1:0] o_status_context_valid,
    output wire o_status_busy,
    output wire o_status_idle,
    output wire o_status_quiescent,
    output wire o_status_error,
    output wire o_status_fatal_error,
    output wire [ER-1:0] o_status_error_code,
    input logic i_debug_request_valid,
    output wire o_debug_request_ready,
    input logic i_debug_request_write,
    input logic [O-1:0] i_debug_request_owner_id,
    input logic i_debug_request_privileged,
    input logic [7:0] i_debug_request_address,
    input logic [W-1:0] i_debug_request_write_data,
    input logic [BY-1:0] i_debug_request_write_strobe,
    output wire o_debug_response_valid,
    input logic i_debug_response_ready,
    output wire [W-1:0] o_debug_response_read_data,
    output wire o_debug_response_error,
    output wire o_trace_valid,
    input logic i_trace_ready,
    output wire [TR-1:0] o_trace_data
);
    wire [CI-1:0] o_body_context_id;
    wire [V-1:0] o_body_context_version;
    wire [IM-1:0] o_body_context_image;
    wire [N-1:0] o_body_context_word_valid;
    wire o_body_context_active;
    wire o_body_validate_valid;
    wire i_body_validate_ready;
    wire [CI-1:0] o_body_validate_context_id;
    wire [V-1:0] o_body_validate_context_version;
    wire [IM-1:0] o_body_validate_context_image;
    wire [N-1:0] o_body_validate_word_valid;
    wire i_body_validate_result_valid;
    wire o_body_validate_result_ready;
    wire [CI-1:0] i_body_validate_context_id;
    wire [V-1:0] i_body_validate_context_version;
    wire i_body_validate_legal;
    wire [ER-1:0] i_body_validate_error_code;
    wire o_body_start;
    wire o_body_suspend_request;
    wire o_body_resume;
    wire o_body_drain_request;
    wire o_body_flush;
    wire [NI-1:0] o_body_data_in_valid;
    wire [NI-1:0] i_body_data_in_ready;
    wire [NI*D-1:0] o_body_data_in_payload;
    wire [NI*M-1:0] o_body_data_in_metadata;
    wire [PI-1:0] o_body_predicate_in_valid;
    wire [PI-1:0] i_body_predicate_in_ready;
    wire [PI*P-1:0] o_body_predicate_in_payload;
    wire [PI*PM-1:0] o_body_predicate_in_metadata;
    wire [EI-1:0] o_body_event_in_valid;
    wire [EI-1:0] i_body_event_in_ready;
    wire [E*EI-1:0] o_body_event_in_payload;
    wire [NO-1:0] i_body_data_out_valid;
    wire [NO-1:0] o_body_data_out_ready;
    wire [NO*D-1:0] i_body_data_out_payload;
    wire [NO*M-1:0] i_body_data_out_metadata;
    wire [PO-1:0] i_body_predicate_out_valid;
    wire [PO-1:0] o_body_predicate_out_ready;
    wire [PO*P-1:0] i_body_predicate_out_payload;
    wire [PO*PM-1:0] i_body_predicate_out_metadata;
    wire [EO-1:0] i_body_event_out_valid;
    wire [EO-1:0] o_body_event_out_ready;
    wire [E*EO-1:0] i_body_event_out_payload;
    wire i_body_busy;
    wire i_body_idle;
    wire i_body_safe_point;
    wire i_body_drain_done;
    wire i_body_completed;
    wire [S-1:0] i_body_stall_reasons;
    wire i_body_error;
    wire i_body_fatal_error;
    wire [ER-1:0] i_body_error_code;
    wire i_body_wakeup_required;
    wire [CP-1:0] shell_capability;
    wire advance_valid;
    wire advance_ready;
    wire [CI-1:0] advance_context;

    if (!SFT_GEOMETRY_VALID || PREDICATE_WIDTH != 1 || PREDICATE_INPUT_PORTS != 1 ||
        PREDICATE_OUTPUT_PORTS != 1 || EVENT_INPUT_PORTS != 1 || EVENT_OUTPUT_PORTS != 1 ||
        EVENT_WIDTH != 32 || STALL_REASON_WIDTH != 8 || ERROR_CODE_WIDTH != 8 ||
        DATA_METADATA_WIDTH < 160) begin : g_invalid_parameters
        sft_parameters_must_be_valid invalid_parameters ();
    end else begin : g_sft
        wire body_debug_select = i_debug_request_address[7:5] === 3'b100;
        wire body_debug_valid;
        wire shell_debug_request = i_debug_request_valid &&!body_debug_select &&!body_debug_valid;
        wire shell_debug_ready;
        wire shell_debug_response;
        wire [W-1:0] shell_debug_data;
        wire shell_debug_error;
        wire [31:0] body_counter_data;
        wire [W-1:0] body_debug_data;
        wire body_debug_error;
        wire body_debug_accept = i_debug_request_valid === 1'b1 && body_debug_select &&
            !body_debug_valid &&!shell_debug_response && i_rstb === 1'b1;
        wire body_debug_authorized = (^ {i_debug_request_owner_id, i_debug_request_privileged,
            i_debug_request_write} !== 1'bx) && i_debug_request_write === 1'b0 &&
            (i_debug_request_privileged === 1'b1 ||
            i_debug_request_owner_id == o_status_owner_id);
        wire body_debug_consume = i_rstb === 1'b1 && body_debug_valid &&
            i_debug_response_ready === 1'b1;
        wire next_debug_valid = body_debug_accept || (body_debug_valid &&!body_debug_consume);

        dff #(
            .WIDTH(W + 2),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_debug_response (
            .i_clk(i_clk),
            .i_rstb(i_rstb !== 1'b0),
            .i_enable(body_debug_accept || body_debug_consume),
            .i_d({next_debug_valid, !body_debug_authorized,
                body_debug_authorized ? W'(body_counter_data) : {W{1'b0}}}),
            .o_q({body_debug_valid, body_debug_error, body_debug_data})
        );

        assign o_debug_request_ready = i_rstb === 1'b1 &&!body_debug_valid &&
            !shell_debug_response && (body_debug_select || shell_debug_ready);
        assign o_debug_response_valid = i_rstb === 1'b1 &&
            (body_debug_valid || shell_debug_response);
        assign o_debug_response_read_data = !o_debug_response_valid ? '0 :
            body_debug_valid ? body_debug_data : shell_debug_data;
        assign o_debug_response_error = o_debug_response_valid &&
            (body_debug_valid ? body_debug_error : shell_debug_error);

        tile_shell #(
            .TILE_ID(TILE_ID),
            .TILE_ID_WIDTH(TILE_ID_WIDTH),
            .ARCH_VERSION_WIDTH(ARCH_VERSION_WIDTH),
            .CAPABILITY_ID_WIDTH(CAPABILITY_ID_WIDTH),
            .DATA_WIDTH(SHELL_DATA_WIDTH),
            .DATA_METADATA_WIDTH(DATA_METADATA_WIDTH),
            .DATA_INPUT_PORTS(DATA_INPUT_PORTS),
            .DATA_OUTPUT_PORTS(DATA_OUTPUT_PORTS),
            .INPUT_BUFFER_DEPTH(INPUT_BUFFER_DEPTH),
            .OUTPUT_BUFFER_DEPTH(OUTPUT_BUFFER_DEPTH),
            .PREDICATE_WIDTH(PREDICATE_WIDTH),
            .PREDICATE_METADATA_WIDTH(PREDICATE_METADATA_WIDTH),
            .PREDICATE_INPUT_PORTS(PREDICATE_INPUT_PORTS),
            .PREDICATE_OUTPUT_PORTS(PREDICATE_OUTPUT_PORTS),
            .EVENT_WIDTH(EVENT_WIDTH),
            .EVENT_INPUT_PORTS(EVENT_INPUT_PORTS),
            .EVENT_OUTPUT_PORTS(EVENT_OUTPUT_PORTS),
            .CONTEXT_DEPTH(CONTEXT_DEPTH),
            .CONFIG_DATA_WIDTH(CONFIG_DATA_WIDTH),
            .CONFIG_WORD_COUNT(CONFIG_WORD_COUNT),
            .CONTEXT_CHECKSUM_WIDTH(CONTEXT_CHECKSUM_WIDTH),
            .SUPPORT_CONTEXT_CHECKSUM(SUPPORT_CONTEXT_CHECKSUM),
            .CONFIG_ASYNC(CONFIG_ASYNC),
            .CONFIG_QUEUE_DEPTH(CONFIG_QUEUE_DEPTH),
            .OWNER_ID_WIDTH(OWNER_ID_WIDTH),
            .KERNEL_ID_WIDTH(KERNEL_ID_WIDTH),
            .CONTEXT_VERSION_WIDTH(CONTEXT_VERSION_WIDTH),
            .RUNTIME_TAG_WIDTH(RUNTIME_TAG_WIDTH),
            .STALL_REASON_WIDTH(STALL_REASON_WIDTH),
            .ERROR_CODE_WIDTH(ERROR_CODE_WIDTH),
            .TRACE_WIDTH(TRACE_WIDTH),
            .SUPPORT_TRACE(SUPPORT_TRACE),
            .SUPPORT_RETENTION(SUPPORT_RETENTION),
            .SUPPORT_POWER_OFF(SUPPORT_POWER_OFF),
            .CONTEXT_PROTECTION(CONTEXT_PROTECTION),
            .CONTROL_PROTECTION(CONTROL_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET),
            .TILE_CLASS(2),
            .BODY_CONTEXT_ADVANCE(1),
            .INPUT_ELASTIC_MASK(INPUT_ELASTIC_MASK),
            .OUTPUT_ELASTIC_MASK(OUTPUT_ELASTIC_MASK)
        ) u_shell (
            .i_body_context_advance(advance_valid),
            .i_body_next_context(advance_context),
            .o_body_context_advance_ready(advance_ready),
            .o_status_capability_id(shell_capability),
            .i_debug_request_valid(shell_debug_request),
            .o_debug_request_ready(shell_debug_ready),
            .o_debug_response_valid(shell_debug_response),
            .i_debug_response_ready(i_debug_response_ready &&!body_debug_valid),
            .o_debug_response_read_data(shell_debug_data),
            .o_debug_response_error(shell_debug_error),
            .*
        );

        sft_body #(
            .INPUT_WIDTH(INPUT_WIDTH),
            .INPUT_FRAC_BITS(INPUT_FRAC_BITS),
            .OUTPUT_WIDTH(OUTPUT_WIDTH),
            .OUTPUT_FRAC_BITS(OUTPUT_FRAC_BITS),
            .INTERNAL_WIDTH(INTERNAL_WIDTH),
            .INTERNAL_FRAC_BITS(INTERNAL_FRAC_BITS),
            .LUT_ADDRESS_WIDTH(LUT_ADDRESS_WIDTH),
            .LUT_INDEX_FRACTION_WIDTH(LUT_INDEX_FRACTION_WIDTH),
            .LUT_BANKS(LUT_BANKS),
            .LUT_PIPELINE_DEPTH(LUT_PIPELINE_DEPTH),
            .POLY_COEFFICIENT_WIDTH(POLY_COEFFICIENT_WIDTH),
            .POLY_MAX_DEGREE(POLY_MAX_DEGREE),
            .POLY_BANKS(POLY_BANKS),
            .POLY_EVALUATION_ARCH(POLY_EVALUATION_ARCH),
            .RECIP_INTERNAL_WIDTH(RECIP_INTERNAL_WIDTH),
            .RECIP_INTERNAL_FRAC_BITS(RECIP_INTERNAL_FRAC_BITS),
            .RECIP_SEED_ADDRESS_WIDTH(RECIP_SEED_ADDRESS_WIDTH),
            .RECIP_MAX_ITERATIONS(RECIP_MAX_ITERATIONS),
            .RSQRT_INTERNAL_WIDTH(RSQRT_INTERNAL_WIDTH),
            .RSQRT_INTERNAL_FRAC_BITS(RSQRT_INTERNAL_FRAC_BITS),
            .RSQRT_SEED_ADDRESS_WIDTH(RSQRT_SEED_ADDRESS_WIDTH),
            .RSQRT_MAX_ITERATIONS(RSQRT_MAX_ITERATIONS),
            .EXP_RANGE_WIDTH(EXP_RANGE_WIDTH),
            .EXP_TABLE_ADDRESS_WIDTH(EXP_TABLE_ADDRESS_WIDTH),
            .EXP_PIPELINE_DEPTH(EXP_PIPELINE_DEPTH),
            .REDUCTION_LANES(REDUCTION_LANES),
            .REDUCTION_ELEMENT_WIDTH(REDUCTION_ELEMENT_WIDTH),
            .REDUCTION_ACC_WIDTH(REDUCTION_ACC_WIDTH),
            .MAX_REDUCTION_ELEMENTS(MAX_REDUCTION_ELEMENTS),
            .FU_PROFILE(FU_PROFILE),
            .ENABLE_ALU(ENABLE_ALU),
            .ENABLE_MULTIPLIER(ENABLE_MULTIPLIER),
            .ENABLE_LUT(ENABLE_LUT),
            .ENABLE_POLYNOMIAL(ENABLE_POLYNOMIAL),
            .ENABLE_RECIPROCAL(ENABLE_RECIPROCAL),
            .ENABLE_RSQRT(ENABLE_RSQRT),
            .ENABLE_EXPONENTIAL(ENABLE_EXPONENTIAL),
            .ENABLE_REDUCTION(ENABLE_REDUCTION),
            .ENABLE_FORMATTER(ENABLE_FORMATTER),
            .ENABLE_ACCUMULATOR(ENABLE_ACCUMULATOR),
            .LOCAL_RF_DEPTH(LOCAL_RF_DEPTH),
            .LOCAL_RF_READ_PORTS(LOCAL_RF_READ_PORTS),
            .LOCAL_RF_WRITE_PORTS(LOCAL_RF_WRITE_PORTS),
            .REDUCTION_STATE_DEPTH(REDUCTION_STATE_DEPTH),
            .INPUT_FIFO_DEPTH(INPUT_FIFO_DEPTH),
            .RESULT_QUEUE_DEPTH(RESULT_QUEUE_DEPTH),
            .MAX_INFLIGHT(MAX_INFLIGHT),
            .BYPASS_PROFILE(BYPASS_PROFILE),
            .SYNC_PROFILE(SYNC_PROFILE),
            .SUPPORT_SPATIAL_TEMPORAL(SUPPORT_SPATIAL_TEMPORAL),
            .SUPPORT_INTERPOLATION(SUPPORT_INTERPOLATION),
            .SUPPORT_SATURATION(SUPPORT_SATURATION),
            .SUPPORT_PREDICATED_TOKEN(SUPPORT_PREDICATED_TOKEN),
            .SUPPORT_LOCAL_CHAINING(SUPPORT_LOCAL_CHAINING),
            .SUPPORT_FP16(SUPPORT_FP16),
            .SUPPORT_BF16(SUPPORT_BF16),
            .REQUIRE_CANONICAL_FORMAT(REQUIRE_CANONICAL_FORMAT),
            .TABLE_PROTECTION(TABLE_PROTECTION),
            .COEFFICIENT_PROTECTION(COEFFICIENT_PROTECTION),
            .CONTROL_PROTECTION(CONTROL_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET),
            .DATA_METADATA_WIDTH(DATA_METADATA_WIDTH),
            .DATA_INPUT_PORTS(DATA_INPUT_PORTS),
            .DATA_OUTPUT_PORTS(DATA_OUTPUT_PORTS),
            .CONTEXT_DEPTH(CONTEXT_DEPTH),
            .CONFIG_DATA_WIDTH(CONFIG_DATA_WIDTH),
            .CONFIG_WORD_COUNT(CONFIG_WORD_COUNT),
            .CONTEXT_VERSION_WIDTH(CONTEXT_VERSION_WIDTH),
            .PREDICATE_METADATA_WIDTH(PREDICATE_METADATA_WIDTH),
            .OWNER_ID_WIDTH(OWNER_ID_WIDTH),
            .KERNEL_ID_WIDTH(KERNEL_ID_WIDTH),
            .DATA_WIDTH(SHELL_DATA_WIDTH)
        ) u_body (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_clock_enable(o_body_clock_enable),
            .i_execution_state(o_status_execution_state),
            .i_owner(o_status_owner_id),
            .i_kernel(o_status_kernel_id),
            .i_isolate(o_body_isolate),
            .i_monitor_enable(o_monitor_clock_enable),
            .i_power_state(o_status_power_state),
            .i_counter_index(i_debug_request_address[4:0]),
            .o_counter_data(body_counter_data),
            .o_advance_valid(advance_valid),
            .i_advance_ready(advance_ready),
            .o_advance_context(advance_context),
            .o_body_context_id(o_body_context_id),
            .o_body_context_version(o_body_context_version),
            .o_body_context_image(o_body_context_image),
            .o_body_context_word_valid(o_body_context_word_valid),
            .o_body_context_active(o_body_context_active),
            .o_body_validate_valid(o_body_validate_valid),
            .i_body_validate_ready(i_body_validate_ready),
            .o_body_validate_context_id(o_body_validate_context_id),
            .o_body_validate_context_version(o_body_validate_context_version),
            .o_body_validate_context_image(o_body_validate_context_image),
            .o_body_validate_word_valid(o_body_validate_word_valid),
            .i_body_validate_result_valid(i_body_validate_result_valid),
            .o_body_validate_result_ready(o_body_validate_result_ready),
            .i_body_validate_context_id(i_body_validate_context_id),
            .i_body_validate_context_version(i_body_validate_context_version),
            .i_body_validate_legal(i_body_validate_legal),
            .i_body_validate_error_code(i_body_validate_error_code),
            .o_body_start(o_body_start),
            .o_body_suspend_request(o_body_suspend_request),
            .o_body_resume(o_body_resume),
            .o_body_drain_request(o_body_drain_request),
            .o_body_flush(o_body_flush),
            .o_body_data_in_valid(o_body_data_in_valid),
            .i_body_data_in_ready(i_body_data_in_ready),
            .o_body_data_in_payload(o_body_data_in_payload),
            .o_body_data_in_metadata(o_body_data_in_metadata),
            .o_body_predicate_in_valid(o_body_predicate_in_valid),
            .i_body_predicate_in_ready(i_body_predicate_in_ready),
            .o_body_predicate_in_payload(o_body_predicate_in_payload),
            .o_body_predicate_in_metadata(o_body_predicate_in_metadata),
            .o_body_event_in_valid(o_body_event_in_valid),
            .i_body_event_in_ready(i_body_event_in_ready),
            .o_body_event_in_payload(o_body_event_in_payload),
            .i_body_data_out_valid(i_body_data_out_valid),
            .o_body_data_out_ready(o_body_data_out_ready),
            .i_body_data_out_payload(i_body_data_out_payload),
            .i_body_data_out_metadata(i_body_data_out_metadata),
            .i_body_predicate_out_valid(i_body_predicate_out_valid),
            .o_body_predicate_out_ready(o_body_predicate_out_ready),
            .i_body_predicate_out_payload(i_body_predicate_out_payload),
            .i_body_predicate_out_metadata(i_body_predicate_out_metadata),
            .i_body_event_out_valid(i_body_event_out_valid),
            .o_body_event_out_ready(o_body_event_out_ready),
            .i_body_event_out_payload(i_body_event_out_payload),
            .i_body_busy(i_body_busy),
            .i_body_idle(i_body_idle),
            .i_body_safe_point(i_body_safe_point),
            .i_body_drain_done(i_body_drain_done),
            .i_body_completed(i_body_completed),
            .i_body_stall_reasons(i_body_stall_reasons),
            .i_body_error(i_body_error),
            .i_body_fatal_error(i_body_fatal_error),
            .i_body_error_code(i_body_error_code),
            .i_body_wakeup_required(i_body_wakeup_required)
        );

        function automatic logic [31:0] body_fingerprint;
            logic [31:0] h;
            h = 32'd2166136261;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(SHELL_DATA_WIDTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(INPUT_WIDTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(INPUT_FRAC_BITS) >> (8 * b)) & 255)) * 32'd16777619;
            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(OUTPUT_WIDTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(OUTPUT_FRAC_BITS) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(INTERNAL_WIDTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(INTERNAL_FRAC_BITS) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(LUT_ADDRESS_WIDTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(LUT_INDEX_FRACTION_WIDTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(LUT_BANKS) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(LUT_PIPELINE_DEPTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(POLY_COEFFICIENT_WIDTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(POLY_MAX_DEGREE) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(POLY_BANKS) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(POLY_EVALUATION_ARCH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(RECIP_INTERNAL_WIDTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(RECIP_INTERNAL_FRAC_BITS) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(RECIP_SEED_ADDRESS_WIDTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(RECIP_MAX_ITERATIONS) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(RSQRT_INTERNAL_WIDTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(RSQRT_INTERNAL_FRAC_BITS) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(RSQRT_SEED_ADDRESS_WIDTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(RSQRT_MAX_ITERATIONS) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(EXP_RANGE_WIDTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(EXP_TABLE_ADDRESS_WIDTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(EXP_PIPELINE_DEPTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(REDUCTION_LANES) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(REDUCTION_ELEMENT_WIDTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(REDUCTION_ACC_WIDTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(MAX_REDUCTION_ELEMENTS) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(FU_PROFILE) >> (8 * b)) & 255)) * 32'd16777619;
            if (ENABLE_ALU != (1))
                h = (h ^ (32'(ENABLE_ALU) + 32'd1)) * 32'd16777619;
            if (ENABLE_MULTIPLIER != (FU_PROFILE >= 1))
                h = (h ^ (32'(ENABLE_MULTIPLIER) + 32'd2)) * 32'd16777619;
            if (ENABLE_LUT != (1))
                h = (h ^ (32'(ENABLE_LUT) + 32'd3)) * 32'd16777619;
            if (ENABLE_POLYNOMIAL != (FU_PROFILE >= 1))
                h = (h ^ (32'(ENABLE_POLYNOMIAL) + 32'd4)) * 32'd16777619;
            if (ENABLE_RECIPROCAL != (FU_PROFILE >= 2))
                h = (h ^ (32'(ENABLE_RECIPROCAL) + 32'd5)) * 32'd16777619;
            if (ENABLE_RSQRT != (FU_PROFILE >= 2))
                h = (h ^ (32'(ENABLE_RSQRT) + 32'd6)) * 32'd16777619;
            if (ENABLE_EXPONENTIAL != (FU_PROFILE == 3))
                h = (h ^ (32'(ENABLE_EXPONENTIAL) + 32'd7)) * 32'd16777619;
            if (ENABLE_REDUCTION != (1))
                h = (h ^ (32'(ENABLE_REDUCTION) + 32'd8)) * 32'd16777619;
            if (ENABLE_FORMATTER != (1))
                h = (h ^ (32'(ENABLE_FORMATTER) + 32'd9)) * 32'd16777619;
            if (ENABLE_ACCUMULATOR != (1))
                h = (h ^ (32'(ENABLE_ACCUMULATOR) + 32'd10)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(LOCAL_RF_DEPTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(LOCAL_RF_READ_PORTS) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(LOCAL_RF_WRITE_PORTS) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(REDUCTION_STATE_DEPTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(INPUT_FIFO_DEPTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(RESULT_QUEUE_DEPTH) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(MAX_INFLIGHT) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(BYPASS_PROFILE) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(SYNC_PROFILE) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(SUPPORT_SPATIAL_TEMPORAL) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(SUPPORT_INTERPOLATION) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(SUPPORT_SATURATION) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(SUPPORT_PREDICATED_TOKEN) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(SUPPORT_LOCAL_CHAINING) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(SUPPORT_FP16) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(SUPPORT_BF16) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(REQUIRE_CANONICAL_FORMAT) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(TABLE_PROTECTION) >> (8 * b)) & 255)) * 32'd16777619;

            for (int b = 0; b < 4; b++)
                h = (h ^ ((32'(COEFFICIENT_PROTECTION) >> (8 * b)) & 255)) * 32'd16777619;

            return h;
        endfunction

        localparam logic [31:0] BODY_CAPABILITY = body_fingerprint();
        assign o_status_capability_id = shell_capability ^ CP'(BODY_CAPABILITY);
    end
endmodule
`default_nettype wire
