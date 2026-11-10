`timescale 1ns / 1ps
`default_nettype none
// Control tile. The actual released shell owns every external protocol.
module cpt #(
    parameter TILE_ID = 0,
    parameter TILE_ID_WIDTH = 16,
    parameter ARCH_VERSION_WIDTH = 16,
    parameter CAPABILITY_ID_WIDTH = 32,
    parameter SHELL_DATA_WIDTH = 64,
    parameter DATA_METADATA_WIDTH = 128,
    parameter DATA_INPUT_PORTS = 2,
    parameter DATA_OUTPUT_PORTS = 1,
    parameter INPUT_BUFFER_DEPTH = 1,
    parameter OUTPUT_BUFFER_DEPTH = 1,
    parameter PREDICATE_WIDTH = 8,
    parameter PREDICATE_METADATA_WIDTH = 64,
    parameter PREDICATE_INPUT_PORTS = 2,
    parameter PREDICATE_OUTPUT_PORTS = 2,
    parameter EVENT_WIDTH = 256,
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
    parameter PREDICATE_LANES = 8,
    parameter PREDICATE_DEPTH = 8,
    parameter EVENT_RECORD_WIDTH = 256,
    parameter CONTROL_WIDTH = 32,
    parameter CONTROL_REGISTER_DEPTH = 8,
    parameter FU_PROFILE = 1,
    // Explicit enables override the legacy profile without coupling peer FUs.
    parameter ENABLE_PREDICATE = 1,
    parameter ENABLE_LOOP_CONTROLLER = 1,
    parameter ENABLE_EVENT_BARRIER = 1,
    parameter ENABLE_ACTIONS = FU_PROFILE >= 1,
    parameter MAX_LOOP_DEPTH = 4,
    parameter INDEX_WIDTH = 32,
    parameter TRIP_COUNT_WIDTH = 32,
    parameter LINEAR_COUNT_WIDTH = 64,
    parameter LOOP_II_WIDTH = 8,
    parameter LOOP_EXPORT_LEVELS = 1,
    parameter NUM_EVENTS = 16,
    parameter EVENT_COUNT_WIDTH = 4,
    parameter NUM_EVENT_NAMESPACES = 1,
    parameter MAX_EVENT_SOURCES = 16,
    parameter EVENT_INPUT_FIFO_DEPTH = 8,
    parameter EVENT_OUTPUT_FIFO_DEPTH = 8,
    parameter NUM_WAIT_SLOTS = 4,
    parameter WAIT_RESULT_QUEUE_DEPTH = 4,
    parameter NUM_BARRIERS = 4,
    parameter MAX_PARTICIPANTS = 16,
    parameter BARRIER_RELEASE_QUEUE_DEPTH = 4,
    parameter BARRIER_GENERATION_WIDTH = 4,
    parameter ACTION_QUEUE_DEPTH = 8,
    parameter ACTION_RESPONSE_DEPTH = 8,
    parameter MAX_OUTSTANDING_ACTIONS = 4,
    parameter ACTION_TAG_WIDTH = 8,
    parameter EVENT_SEQUENCE_WIDTH = 16,
    parameter TIMEOUT_COUNTER_WIDTH = 32,
    parameter MAX_PRIORITY_BURST = 8,
    parameter SUPPORT_CONTEXT_COORDINATION = 1,
    parameter SUPPORT_CLUSTER_LIFECYCLE = 1,
    parameter SUPPORT_TIMEOUT = 1,
    parameter SUPPORT_CHECKPOINT = 0,
    parameter SUPPORT_PREDICATED_TOKEN = 1,
    parameter REQUIRE_CANONICAL_FORMAT = 1,
    parameter PREDICATE_PROTECTION = 0,
    parameter EVENT_PROTECTION = 0,
    parameter CONFIG_WORD_COUNT = (512 + MAX_LOOP_DEPTH *
        (3 * INDEX_WIDTH + TRIP_COUNT_WIDTH + 5) + 63) / 64,
    parameter INPUT_ELASTIC_MASK = 2'b11,
    parameter OUTPUT_ELASTIC_MASK = 1'b1,
    localparam bit CPT_GEOMETRY_VALID =
        ((ENABLE_PREDICATE === 0) || (ENABLE_PREDICATE === 1)) &&
        ((ENABLE_LOOP_CONTROLLER === 0) || (ENABLE_LOOP_CONTROLLER === 1)) &&
        ((ENABLE_EVENT_BARRIER === 0) || (ENABLE_EVENT_BARRIER === 1)) &&
        ((ENABLE_ACTIONS === 0) || (ENABLE_ACTIONS === 1)) &&

        (TILE_ID_WIDTH === 16) && (ARCH_VERSION_WIDTH === 16) &&
        (CAPABILITY_ID_WIDTH === 32) && (RUNTIME_TAG_WIDTH === 8) &&
        (TRACE_WIDTH === 64) && (CONTEXT_CHECKSUM_WIDTH === 32) &&
        (SUPPORT_CONTEXT_CHECKSUM === 1) &&
        ((TILE_ID >= 0 && TILE_ID < MAX_EVENT_SOURCES) === 1'b1) &&
        ((CONFIG_ASYNC === 0) || (CONFIG_ASYNC === 1)) &&
        ((SUPPORT_TRACE === 0) || (SUPPORT_TRACE === 1)) &&
        ((CONFIG_QUEUE_DEPTH >= 2 && CONFIG_QUEUE_DEPTH <= 16) === 1'b1) &&
        (CONFIG_ASYNC == 0 || (CONFIG_QUEUE_DEPTH & (CONFIG_QUEUE_DEPTH - 1)) == 0) &&
        (INPUT_ELASTIC_MASK === 2'b11) && (OUTPUT_ELASTIC_MASK === 1'b1) &&
        ((BARRIER_RELEASE_QUEUE_DEPTH >= 1 && BARRIER_RELEASE_QUEUE_DEPTH <= 16) === 1'b1) &&
        ((WAIT_RESULT_QUEUE_DEPTH >= 1 && WAIT_RESULT_QUEUE_DEPTH <= 16) === 1'b1) &&
        ((EVENT_OUTPUT_FIFO_DEPTH >= 1 && EVENT_OUTPUT_FIFO_DEPTH <= 16) === 1'b1) &&
        ((EVENT_INPUT_FIFO_DEPTH >= 1 && EVENT_INPUT_FIFO_DEPTH <= 16) === 1'b1) &&
        (SHELL_DATA_WIDTH === 64) && (CONTROL_WIDTH === 32) &&
        (DATA_METADATA_WIDTH === 128) && (CONFIG_DATA_WIDTH === 64) &&
        (EVENT_RECORD_WIDTH === 256) && (EVENT_WIDTH === EVENT_RECORD_WIDTH) &&
        (DATA_INPUT_PORTS === 2) && (DATA_OUTPUT_PORTS === 1) &&
        (PREDICATE_WIDTH === PREDICATE_LANES) &&
        ((PREDICATE_LANES >= 1 && PREDICATE_LANES <= 16) === 1'b1) &&
        ((PREDICATE_DEPTH >= 2 && PREDICATE_DEPTH <= 16) === 1'b1) &&
        ((PREDICATE_INPUT_PORTS >= 1 && PREDICATE_INPUT_PORTS <= 2) === 1'b1) &&
        ((PREDICATE_OUTPUT_PORTS >= 1 && PREDICATE_OUTPUT_PORTS <= 4) === 1'b1) &&
        (PREDICATE_METADATA_WIDTH === 64) &&
        (EVENT_INPUT_PORTS === 1) && (EVENT_OUTPUT_PORTS === 1) &&
        (OWNER_ID_WIDTH === 16) && (KERNEL_ID_WIDTH === 16) &&
        (CONTEXT_VERSION_WIDTH === 16) && (STALL_REASON_WIDTH === 8) &&
        (ERROR_CODE_WIDTH === 8) && (ASYNC_RESET === 0) &&
        ((CONTEXT_DEPTH >= 1 && CONTEXT_DEPTH <= 16) === 1'b1) &&
        ((CONTROL_REGISTER_DEPTH >= 4 && CONTROL_REGISTER_DEPTH <= 16) === 1'b1) &&
        ((FU_PROFILE === 0) || (FU_PROFILE === 1)) &&
        (NUM_EVENT_NAMESPACES === 1) && (SUPPORT_CHECKPOINT === 0) &&
        ((MAX_LOOP_DEPTH >= 1 && MAX_LOOP_DEPTH <= 4) === 1'b1) &&
        ((INDEX_WIDTH >= 4 && INDEX_WIDTH <= 32) === 1'b1) &&
        ((TRIP_COUNT_WIDTH >= 2 && TRIP_COUNT_WIDTH <= 32) === 1'b1) &&
        (LINEAR_COUNT_WIDTH === 64) && (LOOP_II_WIDTH === 8) &&
        ((LOOP_EXPORT_LEVELS >= 1 && LOOP_EXPORT_LEVELS <= MAX_LOOP_DEPTH) === 1'b1) &&
        ((NUM_EVENTS >= 1 && NUM_EVENTS <= 16) === 1'b1) &&
        ((EVENT_COUNT_WIDTH >= 1 && EVENT_COUNT_WIDTH <= 8) === 1'b1) &&
        ((MAX_EVENT_SOURCES >= 1 && MAX_EVENT_SOURCES <= 16) === 1'b1) &&
        ((NUM_WAIT_SLOTS >= 1 && NUM_WAIT_SLOTS <= 4) === 1'b1) &&
        ((NUM_BARRIERS >= 1 && NUM_BARRIERS <= 4) === 1'b1) &&
        ((MAX_PARTICIPANTS >= 1 && MAX_PARTICIPANTS <= 16) === 1'b1) &&
        (BARRIER_GENERATION_WIDTH === 4) && (ACTION_TAG_WIDTH === 8) &&
        (EVENT_SEQUENCE_WIDTH === 16) && (TIMEOUT_COUNTER_WIDTH === 32) &&
        ((MAX_OUTSTANDING_ACTIONS >= 1 && MAX_OUTSTANDING_ACTIONS <= 8) === 1'b1) &&
        ((ACTION_QUEUE_DEPTH >= MAX_OUTSTANDING_ACTIONS && ACTION_QUEUE_DEPTH <= 16)
            === 1'b1) &&
        ((ACTION_RESPONSE_DEPTH >= MAX_OUTSTANDING_ACTIONS && ACTION_RESPONSE_DEPTH <= 16)
            === 1'b1) &&
        ((MAX_PRIORITY_BURST >= 1 && MAX_PRIORITY_BURST <= 16) === 1'b1) &&
        (PREDICATE_PROTECTION === 0) &&
        ((EVENT_PROTECTION === 0) || (EVENT_PROTECTION === 1)) &&
        (CONTROL_PROTECTION === 0) &&
        ((CONTEXT_PROTECTION >= 0 && CONTEXT_PROTECTION <= 2) === 1'b1) &&
        ((SUPPORT_CONTEXT_COORDINATION === 0) || (SUPPORT_CONTEXT_COORDINATION === 1)) &&
        ((SUPPORT_CLUSTER_LIFECYCLE === 0) || (SUPPORT_CLUSTER_LIFECYCLE === 1)) &&
        ((SUPPORT_TIMEOUT === 0) || (SUPPORT_TIMEOUT === 1)) &&
        ((SUPPORT_PREDICATED_TOKEN === 0) || (SUPPORT_PREDICATED_TOKEN === 1)) &&
        ((REQUIRE_CANONICAL_FORMAT === 0) || (REQUIRE_CANONICAL_FORMAT === 1)) &&
        (CONFIG_WORD_COUNT === (512 + MAX_LOOP_DEPTH *
            (3 * INDEX_WIDTH + TRIP_COUNT_WIDTH + 5) + 63) / 64) &&
        ((INPUT_BUFFER_DEPTH >= 1 && INPUT_BUFFER_DEPTH <= 4) === 1'b1) &&
        ((OUTPUT_BUFFER_DEPTH >= 1 && OUTPUT_BUFFER_DEPTH <= 4) === 1'b1) &&
        (SUPPORT_RETENTION === 0) && (SUPPORT_POWER_OFF === 0),
    localparam int TI = CPT_GEOMETRY_VALID ? TILE_ID_WIDTH : 1,
    localparam int AV = CPT_GEOMETRY_VALID ? ARCH_VERSION_WIDTH : 1,
    localparam int CP = CPT_GEOMETRY_VALID ? CAPABILITY_ID_WIDTH : 1,
    localparam int D = CPT_GEOMETRY_VALID ? SHELL_DATA_WIDTH : 1,
    localparam int M = CPT_GEOMETRY_VALID ? DATA_METADATA_WIDTH : 1,
    localparam int NI = CPT_GEOMETRY_VALID ? DATA_INPUT_PORTS : 1,
    localparam int NO = CPT_GEOMETRY_VALID ? DATA_OUTPUT_PORTS : 1,
    localparam int BI = CPT_GEOMETRY_VALID ? INPUT_BUFFER_DEPTH : 1,
    localparam int BO = CPT_GEOMETRY_VALID ? OUTPUT_BUFFER_DEPTH : 1,
    localparam int P = CPT_GEOMETRY_VALID ? PREDICATE_WIDTH : 1,
    localparam int PM = CPT_GEOMETRY_VALID ? PREDICATE_METADATA_WIDTH : 1,
    localparam int PI = CPT_GEOMETRY_VALID ? PREDICATE_INPUT_PORTS : 1,
    localparam int PO = CPT_GEOMETRY_VALID ? PREDICATE_OUTPUT_PORTS : 1,
    localparam int E = CPT_GEOMETRY_VALID ? EVENT_WIDTH : 1,
    localparam int EI = CPT_GEOMETRY_VALID ? EVENT_INPUT_PORTS : 1,
    localparam int EO = CPT_GEOMETRY_VALID ? EVENT_OUTPUT_PORTS : 1,
    localparam int C = CPT_GEOMETRY_VALID ? CONTEXT_DEPTH : 1,
    localparam int W = CPT_GEOMETRY_VALID ? CONFIG_DATA_WIDTH : 1,
    localparam int N = CPT_GEOMETRY_VALID ? CONFIG_WORD_COUNT : 1,
    localparam int Q = CPT_GEOMETRY_VALID ? CONFIG_QUEUE_DEPTH : 1,
    localparam int O = CPT_GEOMETRY_VALID ? OWNER_ID_WIDTH : 1,
    localparam int K = CPT_GEOMETRY_VALID ? KERNEL_ID_WIDTH : 1,
    localparam int V = CPT_GEOMETRY_VALID ? CONTEXT_VERSION_WIDTH : 1,
    localparam int T = CPT_GEOMETRY_VALID ? RUNTIME_TAG_WIDTH : 1,
    localparam int S = CPT_GEOMETRY_VALID ? STALL_REASON_WIDTH : 1,
    localparam int ER = CPT_GEOMETRY_VALID ? ERROR_CODE_WIDTH : 1,
    localparam int TR = CPT_GEOMETRY_VALID ? TRACE_WIDTH : 1,
    localparam int CI = C > 1 ? $clog2(C) : 1,
    localparam int WI = N > 1 ? $clog2(N) : 1,
    localparam int BY = W / 8 > 0 ? W / 8 : 1,
    localparam int IM = W * N
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

    if (!CPT_GEOMETRY_VALID) begin : g_invalid_parameters
        cpt_parameters_must_be_valid invalid_parameters ();
    end else begin : g_cpt
        wire body_debug_select = i_debug_request_address[7:5] === 3'b100;
        wire body_debug_valid;
        wire shell_debug_request = i_debug_request_valid &&!body_debug_select &&!body_debug_valid;
        wire shell_debug_ready;
        wire shell_debug_response;
        wire [W-1:0] shell_debug_data;
        wire shell_debug_error;
        wire [31:0] body_counter_data;
        wire body_counter_available;
        wire [W-1:0] body_debug_data;
        wire body_debug_error;
        wire body_debug_accept = i_debug_request_valid === 1'b1
            && body_debug_select &&!body_debug_valid &&!shell_debug_response &&
            body_counter_available &&
            i_rstb === 1'b1;
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
            !shell_debug_response &&
            (body_debug_select ? body_counter_available : shell_debug_ready);
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
            .TILE_CLASS(4),
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

        cpt_body #(
            .TILE_ID(TILE_ID),
            .DATA_METADATA_WIDTH(DATA_METADATA_WIDTH),
            .DATA_INPUT_PORTS(DATA_INPUT_PORTS),
            .DATA_OUTPUT_PORTS(DATA_OUTPUT_PORTS),
            .PREDICATE_WIDTH(PREDICATE_WIDTH),
            .PREDICATE_METADATA_WIDTH(PREDICATE_METADATA_WIDTH),
            .PREDICATE_INPUT_PORTS(PREDICATE_INPUT_PORTS),
            .PREDICATE_OUTPUT_PORTS(PREDICATE_OUTPUT_PORTS),
            .EVENT_WIDTH(EVENT_WIDTH),
            .EVENT_INPUT_PORTS(EVENT_INPUT_PORTS),
            .EVENT_OUTPUT_PORTS(EVENT_OUTPUT_PORTS),
            .CONTEXT_DEPTH(CONTEXT_DEPTH),
            .CONFIG_DATA_WIDTH(CONFIG_DATA_WIDTH),
            .OWNER_ID_WIDTH(OWNER_ID_WIDTH),
            .KERNEL_ID_WIDTH(KERNEL_ID_WIDTH),
            .CONTEXT_VERSION_WIDTH(CONTEXT_VERSION_WIDTH),
            .CONTROL_PROTECTION(CONTROL_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET),
            .PREDICATE_LANES(PREDICATE_LANES),
            .PREDICATE_DEPTH(PREDICATE_DEPTH),
            .EVENT_RECORD_WIDTH(EVENT_RECORD_WIDTH),
            .CONTROL_WIDTH(CONTROL_WIDTH),
            .CONTROL_REGISTER_DEPTH(CONTROL_REGISTER_DEPTH),
            .FU_PROFILE(FU_PROFILE),
            .ENABLE_PREDICATE(ENABLE_PREDICATE),
            .ENABLE_LOOP_CONTROLLER(ENABLE_LOOP_CONTROLLER),
            .ENABLE_EVENT_BARRIER(ENABLE_EVENT_BARRIER),
            .ENABLE_ACTIONS(ENABLE_ACTIONS),
            .MAX_LOOP_DEPTH(MAX_LOOP_DEPTH),
            .INDEX_WIDTH(INDEX_WIDTH),
            .TRIP_COUNT_WIDTH(TRIP_COUNT_WIDTH),
            .LINEAR_COUNT_WIDTH(LINEAR_COUNT_WIDTH),
            .LOOP_II_WIDTH(LOOP_II_WIDTH),
            .LOOP_EXPORT_LEVELS(LOOP_EXPORT_LEVELS),
            .NUM_EVENTS(NUM_EVENTS),
            .EVENT_COUNT_WIDTH(EVENT_COUNT_WIDTH),
            .NUM_EVENT_NAMESPACES(NUM_EVENT_NAMESPACES),
            .MAX_EVENT_SOURCES(MAX_EVENT_SOURCES),
            .EVENT_INPUT_FIFO_DEPTH(EVENT_INPUT_FIFO_DEPTH),
            .EVENT_OUTPUT_FIFO_DEPTH(EVENT_OUTPUT_FIFO_DEPTH),
            .NUM_WAIT_SLOTS(NUM_WAIT_SLOTS),
            .WAIT_RESULT_QUEUE_DEPTH(WAIT_RESULT_QUEUE_DEPTH),
            .NUM_BARRIERS(NUM_BARRIERS),
            .MAX_PARTICIPANTS(MAX_PARTICIPANTS),
            .BARRIER_RELEASE_QUEUE_DEPTH(BARRIER_RELEASE_QUEUE_DEPTH),
            .BARRIER_GENERATION_WIDTH(BARRIER_GENERATION_WIDTH),
            .ACTION_QUEUE_DEPTH(ACTION_QUEUE_DEPTH),
            .ACTION_RESPONSE_DEPTH(ACTION_RESPONSE_DEPTH),
            .MAX_OUTSTANDING_ACTIONS(MAX_OUTSTANDING_ACTIONS),
            .ACTION_TAG_WIDTH(ACTION_TAG_WIDTH),
            .EVENT_SEQUENCE_WIDTH(EVENT_SEQUENCE_WIDTH),
            .TIMEOUT_COUNTER_WIDTH(TIMEOUT_COUNTER_WIDTH),
            .MAX_PRIORITY_BURST(MAX_PRIORITY_BURST),
            .SUPPORT_CONTEXT_COORDINATION(SUPPORT_CONTEXT_COORDINATION),
            .SUPPORT_CLUSTER_LIFECYCLE(SUPPORT_CLUSTER_LIFECYCLE),
            .SUPPORT_TIMEOUT(SUPPORT_TIMEOUT),
            .SUPPORT_CHECKPOINT(SUPPORT_CHECKPOINT),
            .SUPPORT_PREDICATED_TOKEN(SUPPORT_PREDICATED_TOKEN),
            .REQUIRE_CANONICAL_FORMAT(REQUIRE_CANONICAL_FORMAT),
            .PREDICATE_PROTECTION(PREDICATE_PROTECTION),
            .EVENT_PROTECTION(EVENT_PROTECTION),
            .CONFIG_WORD_COUNT(CONFIG_WORD_COUNT),
            .DATA_WIDTH(SHELL_DATA_WIDTH)
        ) u_body (
            .i_loop_delivered(o_data_out_valid[0] === 1'b1 &&
                i_data_out_ready[0] === 1'b1 && o_data_out_metadata[127:124] == 4'hc &&
                o_data_out_metadata[123]),
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
            .o_counter_available(body_counter_available),
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

        // Every released resource/feature parameter participates in tile identity.
        function automatic logic [31:0] body_fingerprint;
            logic [31:0] h;
            h = 32'h43505401;
            h = (h ^ 32'(TILE_ID)) * 32'd16777619;
            h = (h ^ 32'(TILE_ID_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(ARCH_VERSION_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(CAPABILITY_ID_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(SHELL_DATA_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(DATA_METADATA_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(DATA_INPUT_PORTS)) * 32'd16777619;
            h = (h ^ 32'(DATA_OUTPUT_PORTS)) * 32'd16777619;
            h = (h ^ 32'(INPUT_BUFFER_DEPTH)) * 32'd16777619;
            h = (h ^ 32'(OUTPUT_BUFFER_DEPTH)) * 32'd16777619;
            h = (h ^ 32'(PREDICATE_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(PREDICATE_METADATA_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(PREDICATE_INPUT_PORTS)) * 32'd16777619;
            h = (h ^ 32'(PREDICATE_OUTPUT_PORTS)) * 32'd16777619;
            h = (h ^ 32'(EVENT_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(EVENT_INPUT_PORTS)) * 32'd16777619;
            h = (h ^ 32'(EVENT_OUTPUT_PORTS)) * 32'd16777619;
            h = (h ^ 32'(CONTEXT_DEPTH)) * 32'd16777619;
            h = (h ^ 32'(CONFIG_DATA_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(CONTEXT_CHECKSUM_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(SUPPORT_CONTEXT_CHECKSUM)) * 32'd16777619;
            h = (h ^ 32'(CONFIG_ASYNC)) * 32'd16777619;
            h = (h ^ 32'(CONFIG_QUEUE_DEPTH)) * 32'd16777619;
            h = (h ^ 32'(OWNER_ID_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(KERNEL_ID_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(CONTEXT_VERSION_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(RUNTIME_TAG_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(STALL_REASON_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(ERROR_CODE_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(TRACE_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(SUPPORT_TRACE)) * 32'd16777619;
            h = (h ^ 32'(SUPPORT_RETENTION)) * 32'd16777619;
            h = (h ^ 32'(SUPPORT_POWER_OFF)) * 32'd16777619;
            h = (h ^ 32'(CONTEXT_PROTECTION)) * 32'd16777619;
            h = (h ^ 32'(CONTROL_PROTECTION)) * 32'd16777619;
            h = (h ^ 32'(ASYNC_RESET)) * 32'd16777619;
            h = (h ^ 32'(PREDICATE_LANES)) * 32'd16777619;
            h = (h ^ 32'(PREDICATE_DEPTH)) * 32'd16777619;
            h = (h ^ 32'(EVENT_RECORD_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(CONTROL_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(CONTROL_REGISTER_DEPTH)) * 32'd16777619;
            h = (h ^ 32'(FU_PROFILE)) * 32'd16777619;
            if (ENABLE_PREDICATE != (1))
                h = (h ^ (32'(ENABLE_PREDICATE) + 32'd1)) * 32'd16777619;
            if (ENABLE_LOOP_CONTROLLER != (1))
                h = (h ^ (32'(ENABLE_LOOP_CONTROLLER) + 32'd2)) * 32'd16777619;
            if (ENABLE_EVENT_BARRIER != (1))
                h = (h ^ (32'(ENABLE_EVENT_BARRIER) + 32'd3)) * 32'd16777619;
            if (ENABLE_ACTIONS != (FU_PROFILE >= 1))
                h = (h ^ (32'(ENABLE_ACTIONS) + 32'd4)) * 32'd16777619;
            h = (h ^ 32'(MAX_LOOP_DEPTH)) * 32'd16777619;
            h = (h ^ 32'(INDEX_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(TRIP_COUNT_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(LINEAR_COUNT_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(LOOP_II_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(LOOP_EXPORT_LEVELS)) * 32'd16777619;
            h = (h ^ 32'(NUM_EVENTS)) * 32'd16777619;
            h = (h ^ 32'(EVENT_COUNT_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(NUM_EVENT_NAMESPACES)) * 32'd16777619;
            h = (h ^ 32'(MAX_EVENT_SOURCES)) * 32'd16777619;
            h = (h ^ 32'(EVENT_INPUT_FIFO_DEPTH)) * 32'd16777619;
            h = (h ^ 32'(EVENT_OUTPUT_FIFO_DEPTH)) * 32'd16777619;
            h = (h ^ 32'(NUM_WAIT_SLOTS)) * 32'd16777619;
            h = (h ^ 32'(WAIT_RESULT_QUEUE_DEPTH)) * 32'd16777619;
            h = (h ^ 32'(NUM_BARRIERS)) * 32'd16777619;
            h = (h ^ 32'(MAX_PARTICIPANTS)) * 32'd16777619;
            h = (h ^ 32'(BARRIER_RELEASE_QUEUE_DEPTH)) * 32'd16777619;
            h = (h ^ 32'(BARRIER_GENERATION_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(ACTION_QUEUE_DEPTH)) * 32'd16777619;
            h = (h ^ 32'(ACTION_RESPONSE_DEPTH)) * 32'd16777619;
            h = (h ^ 32'(MAX_OUTSTANDING_ACTIONS)) * 32'd16777619;
            h = (h ^ 32'(ACTION_TAG_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(EVENT_SEQUENCE_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(TIMEOUT_COUNTER_WIDTH)) * 32'd16777619;
            h = (h ^ 32'(MAX_PRIORITY_BURST)) * 32'd16777619;
            h = (h ^ 32'(SUPPORT_CONTEXT_COORDINATION)) * 32'd16777619;
            h = (h ^ 32'(SUPPORT_CLUSTER_LIFECYCLE)) * 32'd16777619;
            h = (h ^ 32'(SUPPORT_TIMEOUT)) * 32'd16777619;
            h = (h ^ 32'(SUPPORT_CHECKPOINT)) * 32'd16777619;
            h = (h ^ 32'(SUPPORT_PREDICATED_TOKEN)) * 32'd16777619;
            h = (h ^ 32'(REQUIRE_CANONICAL_FORMAT)) * 32'd16777619;
            h = (h ^ 32'(PREDICATE_PROTECTION)) * 32'd16777619;
            h = (h ^ 32'(EVENT_PROTECTION)) * 32'd16777619;
            h = (h ^ 32'(CONFIG_WORD_COUNT)) * 32'd16777619;
            return h;
        endfunction

        localparam logic [31:0] BODY_CAPABILITY = body_fingerprint();
        assign o_status_capability_id = shell_capability ^ BODY_CAPABILITY;
    end
endmodule
`default_nettype wire
