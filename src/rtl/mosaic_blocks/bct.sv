`timescale 1ns / 1ps
`default_nettype none

// Scalar tile: the released shell owns every external protocol and power boundary.
module bct #(
    parameter TILE_ID = 0,
    parameter TILE_ID_WIDTH = 16,
    parameter ARCH_VERSION_WIDTH = 16,
    parameter CAPABILITY_ID_WIDTH = 32,
    parameter DATA_WIDTH = 32,
    parameter DATA_METADATA_WIDTH = 32,
    parameter DATA_INPUT_PORTS = 4,
    parameter DATA_OUTPUT_PORTS = 4,
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
    parameter CONFIG_WORD_COUNT = 8,
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
    parameter FU_PROFILE = 1,
    // Explicit enables override the legacy profile without coupling peer FUs.
    parameter ENABLE_ALU = 1,
    parameter ENABLE_MULTIPLIER = FU_PROFILE >= 1,
    parameter ENABLE_MAC = FU_PROFILE == 2,
    parameter MULTIPLY_OPERAND_WIDTH = 16,
    parameter ALU_LATENCY = 1,
    parameter MULTIPLY_LATENCY = 1,
    parameter MAC_LATENCY = 1,
    parameter RF_DEPTH = 8,
    parameter RF_READ_PORTS = 2,
    parameter RF_WRITE_PORTS = 1,
    parameter PREDICATE_DEPTH = 2,
    parameter IMMEDIATE_COUNT = 1,
    parameter ACCUMULATOR_COUNT = 1,
    parameter BYPASS_PROFILE = 1,
    parameter REGISTER_BYPASS = 0,
    parameter SYNC_PROFILE = 1,
    parameter RDU_TOTAL_DELAY_ENTRIES = 8,
    parameter INPUT_FIFO_DEPTH = 2,
    parameter RESULT_QUEUE_DEPTH = 2,
    parameter SUPPORT_SPATIAL_TEMPORAL = 1,
    parameter SUPPORT_PREDICATED_TOKEN = 1,
    parameter SUPPORT_SATURATION = 1,
    parameter SUPPORT_MINMAX = 1,
    parameter REQUIRE_CANONICAL_NARROW = 1,
    parameter RF_PROTECTION = 0,
    localparam bit BCT_GEOMETRY_VALID =
        ((ENABLE_ALU === 0) || (ENABLE_ALU === 1)) &&
        ((ENABLE_MULTIPLIER === 0) || (ENABLE_MULTIPLIER === 1)) &&
        ((ENABLE_MAC === 0) || (ENABLE_MAC === 1)) &&

        ((DATA_WIDTH >= 1 && DATA_WIDTH <= 65536) === 1'b1) &&
        ((DATA_INPUT_PORTS >= 1 && DATA_INPUT_PORTS <= 65536) === 1'b1) &&
        ((DATA_OUTPUT_PORTS >= 1 && DATA_OUTPUT_PORTS <= 65536) === 1'b1) &&
        ((CONTEXT_DEPTH >= 1 && CONTEXT_DEPTH <= 65536) === 1'b1) &&
        ((RF_DEPTH >= 1 && RF_DEPTH <= 65536) === 1'b1) &&
        ((PREDICATE_DEPTH >= 1 && PREDICATE_DEPTH <= 65536) === 1'b1) &&
        ((IMMEDIATE_COUNT >= 1 && IMMEDIATE_COUNT <= 65536) === 1'b1) &&
        ((RF_READ_PORTS >= 1 && RF_READ_PORTS <= 65536) === 1'b1) &&
        ((RF_WRITE_PORTS >= 1 && RF_WRITE_PORTS <= 65536) === 1'b1) &&
        ((RESULT_QUEUE_DEPTH >= 1 && RESULT_QUEUE_DEPTH <= 65536) === 1'b1) &&
        ((MULTIPLY_OPERAND_WIDTH >= 1 && MULTIPLY_OPERAND_WIDTH <= 65536) === 1'b1) &&
        ((REGISTER_BYPASS === 0) || (REGISTER_BYPASS === 1)) &&
        ((SUPPORT_SPATIAL_TEMPORAL === 0) || (SUPPORT_SPATIAL_TEMPORAL === 1)) &&
        ((SUPPORT_PREDICATED_TOKEN === 0) || (SUPPORT_PREDICATED_TOKEN === 1)) &&
        ((SUPPORT_SATURATION === 0) || (SUPPORT_SATURATION === 1)) &&
        ((SUPPORT_MINMAX === 0) || (SUPPORT_MINMAX === 1)) &&
        ((REQUIRE_CANONICAL_NARROW === 0) || (REQUIRE_CANONICAL_NARROW === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((128'(DATA_WIDTH) * (128'(RF_DEPTH) + RF_READ_PORTS + RF_WRITE_PORTS +
            IMMEDIATE_COUNT + ACCUMULATOR_COUNT + 3) +
            128'(RDU_TOTAL_DELAY_ENTRIES) * (128'(DATA_WIDTH) + DATA_METADATA_WIDTH) +
            128'(RESULT_QUEUE_DEPTH) * (128'(DATA_WIDTH) + DATA_METADATA_WIDTH +
                DATA_OUTPUT_PORTS + 256) < 128'd2147483647) === 1'b1) &&
        ((DATA_WIDTH >= 2) === 1'b1) &&
        ((2 * MULTIPLY_OPERAND_WIDTH <= DATA_WIDTH) === 1'b1) &&
        ((FU_PROFILE >= 0 && FU_PROFILE <= 2) === 1'b1) &&
        ((BYPASS_PROFILE >= 0 && BYPASS_PROFILE <= 2) === 1'b1) &&
        ((SYNC_PROFILE >= 0 && SYNC_PROFILE <= 2) === 1'b1) &&
        ((RF_PROTECTION >= 0 && RF_PROTECTION <= 2) === 1'b1) &&
        ((CONTROL_PROTECTION >= 0 && CONTROL_PROTECTION <= 2) === 1'b1) &&
        ((ALU_LATENCY == 0 || ALU_LATENCY == 1) === 1'b1) &&
        ((MULTIPLY_LATENCY >= 0 && MULTIPLY_LATENCY <= 4) === 1'b1) &&
        ((MAC_LATENCY >= 0 && MAC_LATENCY <= 4) === 1'b1) &&
        ((RF_READ_PORTS >= 2 && RF_WRITE_PORTS >= 1) === 1'b1) &&
        ((ACCUMULATOR_COUNT >= 0 && ACCUMULATOR_COUNT <= 32) === 1'b1) &&
        ((ENABLE_MAC != 1 || ACCUMULATOR_COUNT >= 1) === 1'b1) &&
        ((RDU_TOTAL_DELAY_ENTRIES >= 0 && RDU_TOTAL_DELAY_ENTRIES <= 1024) === 1'b1) &&
        ((SYNC_PROFILE != 1 || RDU_TOTAL_DELAY_ENTRIES >= 1) === 1'b1) &&
        ((INPUT_FIFO_DEPTH >= 0 && INPUT_FIFO_DEPTH <= 65536) === 1'b1) &&
        ((SYNC_PROFILE != 2 || INPUT_FIFO_DEPTH >= 1) === 1'b1),
    localparam int TI = BCT_GEOMETRY_VALID ? TILE_ID_WIDTH : 1,
    localparam int AV = BCT_GEOMETRY_VALID ? ARCH_VERSION_WIDTH : 1,
    localparam int CP = BCT_GEOMETRY_VALID ? CAPABILITY_ID_WIDTH : 1,
    localparam int D = BCT_GEOMETRY_VALID ? DATA_WIDTH : 1,
    localparam int M = BCT_GEOMETRY_VALID ? DATA_METADATA_WIDTH : 1,
    localparam int NI = BCT_GEOMETRY_VALID ? DATA_INPUT_PORTS : 1,
    localparam int NO = BCT_GEOMETRY_VALID ? DATA_OUTPUT_PORTS : 1,
    localparam int BI = BCT_GEOMETRY_VALID ? INPUT_BUFFER_DEPTH : 1,
    localparam int BO = BCT_GEOMETRY_VALID ? OUTPUT_BUFFER_DEPTH : 1,
    localparam int P = BCT_GEOMETRY_VALID ? PREDICATE_WIDTH : 1,
    localparam int PM = BCT_GEOMETRY_VALID ? PREDICATE_METADATA_WIDTH : 1,
    localparam int PI = BCT_GEOMETRY_VALID ? PREDICATE_INPUT_PORTS : 1,
    localparam int PO = BCT_GEOMETRY_VALID ? PREDICATE_OUTPUT_PORTS : 1,
    localparam int E = BCT_GEOMETRY_VALID ? EVENT_WIDTH : 1,
    localparam int EI = BCT_GEOMETRY_VALID ? EVENT_INPUT_PORTS : 1,
    localparam int EO = BCT_GEOMETRY_VALID ? EVENT_OUTPUT_PORTS : 1,
    localparam int C = BCT_GEOMETRY_VALID ? CONTEXT_DEPTH : 1,
    localparam int W = BCT_GEOMETRY_VALID ? CONFIG_DATA_WIDTH : 1,
    localparam int N = BCT_GEOMETRY_VALID ? CONFIG_WORD_COUNT : 1,
    localparam int Q = BCT_GEOMETRY_VALID ? CONFIG_QUEUE_DEPTH : 1,
    localparam int O = BCT_GEOMETRY_VALID ? OWNER_ID_WIDTH : 1,
    localparam int K = BCT_GEOMETRY_VALID ? KERNEL_ID_WIDTH : 1,
    localparam int V = BCT_GEOMETRY_VALID ? CONTEXT_VERSION_WIDTH : 1,
    localparam int T = BCT_GEOMETRY_VALID ? RUNTIME_TAG_WIDTH : 1,
    localparam int S = BCT_GEOMETRY_VALID ? STALL_REASON_WIDTH : 1,
    localparam int ER = BCT_GEOMETRY_VALID ? ERROR_CODE_WIDTH : 1,
    localparam int TR = BCT_GEOMETRY_VALID ? TRACE_WIDTH : 1,
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

    if (!BCT_GEOMETRY_VALID || PREDICATE_WIDTH != 1 || PREDICATE_INPUT_PORTS != 1 ||
        PREDICATE_OUTPUT_PORTS != 1 || EVENT_INPUT_PORTS != 1 || EVENT_OUTPUT_PORTS != 1 ||
        EVENT_WIDTH != 32 || STALL_REASON_WIDTH != 8 || ERROR_CODE_WIDTH != 8 ||
        DATA_METADATA_WIDTH < CI + CONTEXT_VERSION_WIDTH + 1) begin : g_invalid_parameters
        bct_parameters_must_be_valid invalid_parameters ();
    end else begin : g_bct

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

    dff #(.WIDTH(W + 2), .ASYNC_RESET(ASYNC_RESET)) u_debug_response (
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
        .DATA_WIDTH(DATA_WIDTH),
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
        .TILE_CLASS(0),
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

    bct_body #(
        .FU_PROFILE(FU_PROFILE),
        .ENABLE_ALU(ENABLE_ALU),
        .ENABLE_MULTIPLIER(ENABLE_MULTIPLIER),
        .ENABLE_MAC(ENABLE_MAC),
        .MULTIPLY_OPERAND_WIDTH(MULTIPLY_OPERAND_WIDTH),
        .ALU_LATENCY(ALU_LATENCY),
        .MULTIPLY_LATENCY(MULTIPLY_LATENCY),
        .MAC_LATENCY(MAC_LATENCY),
        .RF_DEPTH(RF_DEPTH),
        .RF_READ_PORTS(RF_READ_PORTS),
        .RF_WRITE_PORTS(RF_WRITE_PORTS),
        .PREDICATE_DEPTH(PREDICATE_DEPTH),
        .IMMEDIATE_COUNT(IMMEDIATE_COUNT),
        .ACCUMULATOR_COUNT(ACCUMULATOR_COUNT),
        .BYPASS_PROFILE(BYPASS_PROFILE),
        .REGISTER_BYPASS(REGISTER_BYPASS),
        .SYNC_PROFILE(SYNC_PROFILE),
        .RDU_TOTAL_DELAY_ENTRIES(RDU_TOTAL_DELAY_ENTRIES),
        .INPUT_FIFO_DEPTH(INPUT_FIFO_DEPTH),
        .RESULT_QUEUE_DEPTH(RESULT_QUEUE_DEPTH),
        .SUPPORT_SPATIAL_TEMPORAL(SUPPORT_SPATIAL_TEMPORAL),
        .SUPPORT_PREDICATED_TOKEN(SUPPORT_PREDICATED_TOKEN),
        .SUPPORT_SATURATION(SUPPORT_SATURATION),
        .SUPPORT_MINMAX(SUPPORT_MINMAX),
        .REQUIRE_CANONICAL_NARROW(REQUIRE_CANONICAL_NARROW),
        .RF_PROTECTION(RF_PROTECTION),
        .CONTROL_PROTECTION(CONTROL_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET),
        .DATA_WIDTH(DATA_WIDTH),
        .DATA_METADATA_WIDTH(DATA_METADATA_WIDTH),
        .DATA_INPUT_PORTS(DATA_INPUT_PORTS),
        .DATA_OUTPUT_PORTS(DATA_OUTPUT_PORTS),
        .CONTEXT_DEPTH(CONTEXT_DEPTH),
        .CONFIG_DATA_WIDTH(CONFIG_DATA_WIDTH),
        .CONFIG_WORD_COUNT(CONFIG_WORD_COUNT),
        .CONTEXT_VERSION_WIDTH(CONTEXT_VERSION_WIDTH),
        .PREDICATE_METADATA_WIDTH(PREDICATE_METADATA_WIDTH),
        .OWNER_ID_WIDTH(OWNER_ID_WIDTH),
        .KERNEL_ID_WIDTH(KERNEL_ID_WIDTH)
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

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(FU_PROFILE) >> (8 * b)) & 255)) * 32'd16777619;
        if (ENABLE_ALU != (1))
            h = (h ^ (32'(ENABLE_ALU) + 32'd1)) * 32'd16777619;
        if (ENABLE_MULTIPLIER != (FU_PROFILE >= 1))
            h = (h ^ (32'(ENABLE_MULTIPLIER) + 32'd2)) * 32'd16777619;
        if (ENABLE_MAC != (FU_PROFILE == 2))
            h = (h ^ (32'(ENABLE_MAC) + 32'd3)) * 32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(MULTIPLY_OPERAND_WIDTH) >> (8 * b)) & 255)) *
            32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(ALU_LATENCY) >> (8 * b)) & 255)) * 32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(MULTIPLY_LATENCY) >> (8 * b)) & 255)) *
            32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(MAC_LATENCY) >> (8 * b)) & 255)) * 32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(RF_DEPTH) >> (8 * b)) & 255)) * 32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(RF_READ_PORTS) >> (8 * b)) & 255)) *
            32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(RF_WRITE_PORTS) >> (8 * b)) & 255)) *
            32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(PREDICATE_DEPTH) >> (8 * b)) & 255)) *
            32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(IMMEDIATE_COUNT) >> (8 * b)) & 255)) *
            32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(ACCUMULATOR_COUNT) >> (8 * b)) & 255)) *
            32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(BYPASS_PROFILE) >> (8 * b)) & 255)) *
            32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(REGISTER_BYPASS) >> (8 * b)) & 255)) *
            32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(SYNC_PROFILE) >> (8 * b)) & 255)) * 32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(RDU_TOTAL_DELAY_ENTRIES) >> (8 * b)) & 255))
            * 32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(INPUT_FIFO_DEPTH) >> (8 * b)) & 255)) *
            32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(RESULT_QUEUE_DEPTH) >> (8 * b)) & 255)) *
            32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(SUPPORT_SPATIAL_TEMPORAL) >> (8 * b)) & 255))
            * 32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(SUPPORT_PREDICATED_TOKEN) >> (8 * b)) & 255))
            * 32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(SUPPORT_SATURATION) >> (8 * b)) & 255)) *
            32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(SUPPORT_MINMAX) >> (8 * b)) & 255)) *
            32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(REQUIRE_CANONICAL_NARROW) >> (8 * b)) & 255))
            * 32'd16777619;

        for (int b = 0; b < 4; b++) h = (h ^ ((32'(RF_PROTECTION) >> (8 * b)) & 255)) *
            32'd16777619;

        return h;
    endfunction

    localparam logic [31:0] BODY_CAPABILITY = body_fingerprint();

    assign o_status_capability_id = shell_capability ^ CP'(BODY_CAPABILITY);

    end
endmodule
`default_nettype wire
