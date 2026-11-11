`timescale 1ns / 1ps
`default_nettype none
// Always-on ownership, context and protocol boundary around a tile-specific body.
module tile_shell #(
    parameter TILE_ID = 0,
    parameter TILE_ID_WIDTH = 16,
    parameter TILE_CLASS = 0,
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
    // Optional synchronous body request, accepted only at an empty safe boundary.
    parameter BODY_CONTEXT_ADVANCE = 0,
    // Memory tiles can finish accepted effects after runtime termination. Keep
    // their owned terminal events deliverable while returning to READY.
    parameter BODY_DRAIN_EVENTS = 0,
    localparam bit GEOMETRY_VALID =
        ((BODY_CONTEXT_ADVANCE === 0) || (BODY_CONTEXT_ADVANCE === 1)) &&
        ((BODY_DRAIN_EVENTS === 0) || (BODY_DRAIN_EVENTS === 1)) &&
        ((TILE_ID_WIDTH >= 1) === 1'b1) &&
        ((ARCH_VERSION_WIDTH >= 1) === 1'b1) &&
        ((CAPABILITY_ID_WIDTH >= 1) === 1'b1) &&
        ((DATA_WIDTH >= 1) === 1'b1) &&
        ((DATA_METADATA_WIDTH >= 1) === 1'b1) &&
        ((DATA_INPUT_PORTS >= 1) === 1'b1) &&
        ((DATA_OUTPUT_PORTS >= 1) === 1'b1) &&
        ((PREDICATE_WIDTH >= 1) === 1'b1) &&
        ((PREDICATE_METADATA_WIDTH >= 1) === 1'b1) &&
        ((PREDICATE_INPUT_PORTS >= 1) === 1'b1) &&
        ((PREDICATE_OUTPUT_PORTS >= 1) === 1'b1) &&
        ((EVENT_WIDTH >= 1) === 1'b1) &&
        ((EVENT_INPUT_PORTS >= 1) === 1'b1) &&
        ((EVENT_OUTPUT_PORTS >= 1) === 1'b1) &&
        ((CONTEXT_DEPTH >= 1) === 1'b1) &&
        ((CONFIG_DATA_WIDTH >= 1) === 1'b1) &&
        ((CONFIG_WORD_COUNT >= 1) === 1'b1) &&
        ((CONTEXT_CHECKSUM_WIDTH >= 1) === 1'b1) &&
        ((CONFIG_QUEUE_DEPTH >= 1) === 1'b1) &&
        ((OWNER_ID_WIDTH >= 1) === 1'b1) &&
        ((KERNEL_ID_WIDTH >= 1) === 1'b1) &&
        ((CONTEXT_VERSION_WIDTH >= 1) === 1'b1) &&
        ((RUNTIME_TAG_WIDTH >= 1) === 1'b1) &&
        ((STALL_REASON_WIDTH >= 1) === 1'b1) &&
        ((ERROR_CODE_WIDTH >= 1) === 1'b1) &&
        ((TRACE_WIDTH >= 1) === 1'b1) &&
        ((SUPPORT_CONTEXT_CHECKSUM === 0) || (SUPPORT_CONTEXT_CHECKSUM === 1)) &&
        ((CONFIG_ASYNC === 0) || (CONFIG_ASYNC === 1)) &&
        ((SUPPORT_TRACE === 0) || (SUPPORT_TRACE === 1)) &&
        ((SUPPORT_RETENTION === 0) || (SUPPORT_RETENTION === 1)) &&
        ((SUPPORT_POWER_OFF === 0) || (SUPPORT_POWER_OFF === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((TILE_ID >= 0) === 1'b1) &&
        ((INPUT_BUFFER_DEPTH >= 0) === 1'b1) &&
        ((OUTPUT_BUFFER_DEPTH >= 0) === 1'b1) &&
        ((TILE_CLASS >= 0 && TILE_CLASS <= 4) === 1'b1) &&
        ((CONTEXT_PROTECTION >= 0 && CONTEXT_PROTECTION <= 2) === 1'b1) &&
        ((CONTROL_PROTECTION >= 0 && CONTROL_PROTECTION <= 2) === 1'b1) &&
        ((CONFIG_DATA_WIDTH % 8 == 0) === 1'b1) &&
        (CONTEXT_CHECKSUM_WIDTH === 32) &&
        ((STALL_REASON_WIDTH >= 4) === 1'b1) &&
        ((ERROR_CODE_WIDTH >= 8) === 1'b1) &&
        ((CONFIG_ASYNC == 0 || CONFIG_QUEUE_DEPTH >= 2) === 1'b1) &&
        ((128'(TILE_ID) >> TILE_ID_WIDTH) === 128'b0) &&
        ((DATA_METADATA_WIDTH >= CONTEXT_VERSION_WIDTH + (CONTEXT_DEPTH > 1 ?
            $clog2(CONTEXT_DEPTH) : 1)) === 1'b1) &&
        ((PREDICATE_METADATA_WIDTH >= (CONTEXT_DEPTH > 1 ? $clog2(CONTEXT_DEPTH) : 1)) === 1'b1) &&
        ((EVENT_WIDTH >= KERNEL_ID_WIDTH + (CONTEXT_DEPTH > 1 ? $clog2(CONTEXT_DEPTH) : 1) + 3)
            === 1'b1) &&
        ((SUPPORT_TRACE == 0 || TRACE_WIDTH >= TILE_ID_WIDTH + OWNER_ID_WIDTH +
            KERNEL_ID_WIDTH + (CONTEXT_DEPTH > 1 ? $clog2(CONTEXT_DEPTH) : 1) + 5) === 1'b1) &&
        ((128'(CONFIG_DATA_WIDTH) * CONFIG_WORD_COUNT * CONTEXT_DEPTH +
            128'(DATA_WIDTH + DATA_METADATA_WIDTH) * (DATA_INPUT_PORTS + DATA_OUTPUT_PORTS) *
            (128'(INPUT_BUFFER_DEPTH) + OUTPUT_BUFFER_DEPTH + 1) < 128'd2147483647) === 1'b1) &&
        ((TILE_ID_WIDTH < 32'd1048576) === 1'b1) &&
        ((ARCH_VERSION_WIDTH < 32'd1048576) === 1'b1) &&
        ((CAPABILITY_ID_WIDTH < 32'd1048576) === 1'b1) &&
        ((DATA_WIDTH < 32'd1048576) === 1'b1) &&
        ((DATA_METADATA_WIDTH < 32'd1048576) === 1'b1) &&
        ((DATA_INPUT_PORTS < 32'd1048576) === 1'b1) &&
        ((DATA_OUTPUT_PORTS < 32'd1048576) === 1'b1) &&
        ((PREDICATE_WIDTH < 32'd1048576) === 1'b1) &&
        ((PREDICATE_METADATA_WIDTH < 32'd1048576) === 1'b1) &&
        ((PREDICATE_INPUT_PORTS < 32'd1048576) === 1'b1) &&
        ((PREDICATE_OUTPUT_PORTS < 32'd1048576) === 1'b1) &&
        ((EVENT_WIDTH < 32'd1048576) === 1'b1) &&
        ((EVENT_INPUT_PORTS < 32'd1048576) === 1'b1) &&
        ((EVENT_OUTPUT_PORTS < 32'd1048576) === 1'b1) &&
        ((CONTEXT_DEPTH < 32'd1048576) === 1'b1) &&
        ((CONFIG_DATA_WIDTH < 32'd1048576) === 1'b1) &&
        ((CONFIG_WORD_COUNT < 32'd1048576) === 1'b1) &&
        ((CONTEXT_CHECKSUM_WIDTH < 32'd1048576) === 1'b1) &&
        ((CONFIG_QUEUE_DEPTH < 32'd1048576) === 1'b1) &&
        ((OWNER_ID_WIDTH < 32'd1048576) === 1'b1) &&
        ((KERNEL_ID_WIDTH < 32'd1048576) === 1'b1) &&
        ((CONTEXT_VERSION_WIDTH < 32'd1048576) === 1'b1) &&
        ((RUNTIME_TAG_WIDTH < 32'd1048576) === 1'b1) &&
        ((STALL_REASON_WIDTH < 32'd1048576) === 1'b1) &&
        ((ERROR_CODE_WIDTH < 32'd1048576) === 1'b1) &&
        ((TRACE_WIDTH < 32'd1048576) === 1'b1) &&
        ((INPUT_BUFFER_DEPTH < 32'd1048576) === 1'b1) &&
        ((OUTPUT_BUFFER_DEPTH < 32'd1048576) === 1'b1),
    localparam int TI = GEOMETRY_VALID ? TILE_ID_WIDTH : 1,
    localparam int AV = GEOMETRY_VALID ? ARCH_VERSION_WIDTH : 1,
    localparam int CP = GEOMETRY_VALID ? CAPABILITY_ID_WIDTH : 1,
    localparam int D = GEOMETRY_VALID ? DATA_WIDTH : 1,
    localparam int M = GEOMETRY_VALID ? DATA_METADATA_WIDTH : 1,
    localparam int NI = GEOMETRY_VALID ? DATA_INPUT_PORTS : 1,
    localparam int NO = GEOMETRY_VALID ? DATA_OUTPUT_PORTS : 1,
    localparam int BI = GEOMETRY_VALID ? INPUT_BUFFER_DEPTH : 1,
    localparam int BO = GEOMETRY_VALID ? OUTPUT_BUFFER_DEPTH : 1,
    localparam int P = GEOMETRY_VALID ? PREDICATE_WIDTH : 1,
    localparam int PM = GEOMETRY_VALID ? PREDICATE_METADATA_WIDTH : 1,
    localparam int PI = GEOMETRY_VALID ? PREDICATE_INPUT_PORTS : 1,
    localparam int PO = GEOMETRY_VALID ? PREDICATE_OUTPUT_PORTS : 1,
    localparam int E = GEOMETRY_VALID ? EVENT_WIDTH : 1,
    localparam int EI = GEOMETRY_VALID ? EVENT_INPUT_PORTS : 1,
    localparam int EO = GEOMETRY_VALID ? EVENT_OUTPUT_PORTS : 1,
    localparam int C = GEOMETRY_VALID ? CONTEXT_DEPTH : 1,
    localparam int W = GEOMETRY_VALID ? CONFIG_DATA_WIDTH : 1,
    localparam int N = GEOMETRY_VALID ? CONFIG_WORD_COUNT : 1,
    localparam int Q = GEOMETRY_VALID ? CONFIG_QUEUE_DEPTH : 1,
    localparam int O = GEOMETRY_VALID ? OWNER_ID_WIDTH : 1,
    localparam int K = GEOMETRY_VALID ? KERNEL_ID_WIDTH : 1,
    localparam int V = GEOMETRY_VALID ? CONTEXT_VERSION_WIDTH : 1,
    localparam int T = GEOMETRY_VALID ? RUNTIME_TAG_WIDTH : 1,
    localparam int S = GEOMETRY_VALID ? STALL_REASON_WIDTH : 1,
    localparam int ER = GEOMETRY_VALID ? ERROR_CODE_WIDTH : 1,
    localparam int TR = GEOMETRY_VALID ? TRACE_WIDTH : 1,
    localparam int CI = C > 1 ? $clog2(C) : 1,
    localparam int WI = N > 1 ? $clog2(N) : 1,
    localparam int BY = W / 8 > 0 ? W / 8 : 1,
    localparam int IM = W * N,
    parameter INPUT_ELASTIC_MASK = {NI{1'b1}},
    parameter OUTPUT_ELASTIC_MASK = {NO{1'b1}},
    localparam bit PARAMETERS_VALID = GEOMETRY_VALID &&
        ($bits(INPUT_ELASTIC_MASK) == NI) && ($bits(OUTPUT_ELASTIC_MASK) == NO) &&
        (((^INPUT_ELASTIC_MASK == 1'b0) || (^INPUT_ELASTIC_MASK == 1'b1)) === 1'b1) &&
        (((^OUTPUT_ELASTIC_MASK == 1'b0) || (^OUTPUT_ELASTIC_MASK == 1'b1)) === 1'b1)
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_cfg_clk,
    input logic i_cfg_rstb,
    input logic i_test_enable,
    input logic i_scan_enable,
    input logic i_body_context_advance,
    input logic [CI-1:0] i_body_next_context,
    output wire o_body_context_advance_ready,
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
    input logic [3-1:0] i_cfg_request_command,
    input logic [TI-1:0] i_cfg_request_tile_id,
    input logic [O-1:0] i_cfg_request_owner_id,
    input logic [CI-1:0] i_cfg_request_context_id,
    input logic [WI-1:0] i_cfg_request_word_index,
    input logic [W-1:0] i_cfg_request_write_data,
    input logic [BY-1:0] i_cfg_request_write_strobe,
    input logic [32-1:0] i_cfg_request_expected_crc,
    input logic [T-1:0] i_cfg_request_tag,
    output wire o_cfg_response_valid,
    input logic i_cfg_response_ready,
    output wire [3-1:0] o_cfg_response_command,
    output wire [CI-1:0] o_cfg_response_context_id,
    output wire [W-1:0] o_cfg_response_read_data,
    output wire [V-1:0] o_cfg_response_context_version,
    output wire [32-1:0] o_cfg_response_crc,
    output wire o_cfg_response_error,
    output wire [ER-1:0] o_cfg_response_error_code,
    output wire [T-1:0] o_cfg_response_tag,
    input logic i_runtime_request_valid,
    output wire o_runtime_request_ready,
    input logic [3-1:0] i_runtime_request_command,
    input logic [O-1:0] i_runtime_request_owner_id,
    input logic [K-1:0] i_runtime_request_kernel_id,
    input logic [CI-1:0] i_runtime_request_context_id,
    input logic [T-1:0] i_runtime_request_tag,
    output wire o_runtime_response_valid,
    input logic i_runtime_response_ready,
    output wire [3-1:0] o_runtime_response_command,
    output wire [4-1:0] o_runtime_response_state,
    output wire o_runtime_response_error,
    output wire [ER-1:0] o_runtime_response_error_code,
    output wire [T-1:0] o_runtime_response_tag,
    output wire [CI-1:0] o_body_context_id,
    output wire [V-1:0] o_body_context_version,
    output wire [IM-1:0] o_body_context_image,
    output wire [N-1:0] o_body_context_word_valid,
    output wire o_body_context_active,
    output wire o_body_validate_valid,
    input logic i_body_validate_ready,
    output wire [CI-1:0] o_body_validate_context_id,
    output wire [V-1:0] o_body_validate_context_version,
    output wire [IM-1:0] o_body_validate_context_image,
    output wire [N-1:0] o_body_validate_word_valid,
    input logic i_body_validate_result_valid,
    output wire o_body_validate_result_ready,
    input logic [CI-1:0] i_body_validate_context_id,
    input logic [V-1:0] i_body_validate_context_version,
    input logic i_body_validate_legal,
    input logic [ER-1:0] i_body_validate_error_code,
    output wire o_body_start,
    output wire o_body_suspend_request,
    output wire o_body_resume,
    output wire o_body_drain_request,
    output wire o_body_flush,
    output wire [NI-1:0] o_body_data_in_valid,
    input logic [NI-1:0] i_body_data_in_ready,
    output wire [NI*D-1:0] o_body_data_in_payload,
    output wire [NI*M-1:0] o_body_data_in_metadata,
    output wire [PI-1:0] o_body_predicate_in_valid,
    input logic [PI-1:0] i_body_predicate_in_ready,
    output wire [PI*P-1:0] o_body_predicate_in_payload,
    output wire [PI*PM-1:0] o_body_predicate_in_metadata,
    output wire [EI-1:0] o_body_event_in_valid,
    input logic [EI-1:0] i_body_event_in_ready,
    output wire [E*EI-1:0] o_body_event_in_payload,
    input logic [NO-1:0] i_body_data_out_valid,
    output wire [NO-1:0] o_body_data_out_ready,
    input logic [NO*D-1:0] i_body_data_out_payload,
    input logic [NO*M-1:0] i_body_data_out_metadata,
    input logic [PO-1:0] i_body_predicate_out_valid,
    output wire [PO-1:0] o_body_predicate_out_ready,
    input logic [PO*P-1:0] i_body_predicate_out_payload,
    input logic [PO*PM-1:0] i_body_predicate_out_metadata,
    input logic [EO-1:0] i_body_event_out_valid,
    output wire [EO-1:0] o_body_event_out_ready,
    input logic [E*EO-1:0] i_body_event_out_payload,
    input logic i_body_busy,
    input logic i_body_idle,
    input logic i_body_safe_point,
    input logic i_body_drain_done,
    input logic i_body_completed,
    input logic [S-1:0] i_body_stall_reasons,
    input logic i_body_error,
    input logic i_body_fatal_error,
    input logic [ER-1:0] i_body_error_code,
    input logic i_body_wakeup_required,
    input logic i_power_request_valid,
    output wire o_power_request_ready,
    input logic [3-1:0] i_power_request_state,
    output wire o_power_response_valid,
    input logic i_power_response_ready,
    output wire [3-1:0] o_power_response_state,
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
    output wire [3-1:0] o_status_tile_class,
    output wire [AV-1:0] o_status_arch_version,
    output wire [CP-1:0] o_status_capability_id,
    output wire [4-1:0] o_status_execution_state,
    output wire [3-1:0] o_status_power_state,
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
    input logic [8-1:0] i_debug_request_address,
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
    import tile_shell_pkg::*;

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        tile_shell_parameters_must_be_valid invalid_parameters ();
    end else begin : g_shell
        // Packed next-state records use complete @* processes. This avoids
        // Icarus retriggering always_comb on intermediate aggregate assignments;
        // every branch below supplies defaults, with no inferred latches.
        // Either reset starts a new command epoch. Both CDC directions reset
        // together and release independently; stale responses cannot survive.
        wire reset_input = (i_rstb !== 1'b0) &&
            (CONFIG_ASYNC == 0 || i_cfg_rstb !== 1'b0);
        wire reset_known = (^i_rstb !== 1'bx) &&
            (CONFIG_ASYNC == 0 || (^i_cfg_rstb !== 1'bx));
        wire reset_b;
        wire cfg_reset_b;
        wire interface_up = reset_b && reset_known;

        if (ASYNC_RESET == 1 || CONFIG_ASYNC == 1) begin : g_reset
            reset_synchronizer u_core_release (
                .i_clk(i_clk),
                .i_async_rstb(reset_input),
                .o_rstb(reset_b)
            );
        end else begin : g_sync_reset
            assign reset_b = reset_input;
        end

        if (CONFIG_ASYNC == 1) begin : g_cfg_reset
            reset_synchronizer u_cfg_release (
                .i_clk(i_cfg_clk),
                .i_async_rstb(reset_input),
                .o_rstb(cfg_reset_b)
            );
        end else begin : g_cfg_sync_reset
            assign cfg_reset_b = reset_b;
        end

        typedef struct packed {
            logic [2:0] command;
            logic [TI-1:0] tile_id;
            logic [O-1:0] owner;
            logic [CI-1:0] context_id;
            logic [WI-1:0] word_index;
            logic [W-1:0] data;
            logic [BY-1:0] strobe;
            logic [31:0] crc;
            logic [T-1:0] tag;
        } cfg_request_t;

        typedef struct packed {
            logic [2:0] command;
            logic [CI-1:0] context_id;
            logic [W-1:0] data;
            logic [V-1:0] version;
            logic [31:0] crc;
            logic error;
            logic [ER-1:0] code;
            logic [T-1:0] tag;
        } cfg_response_t;

        typedef struct packed {
            logic allocated;
            logic [O-1:0] owner;
            logic [K-1:0] kernel;
            logic active;
            logic [3:0] state;
            logic completion;
            logic completion_event;
            logic body_completed;
            logic monitor;
        } control_t;

        typedef struct packed {
            logic [V-1:0] version;
            logic [N-1:0] written;
            logic validated;
        } context_t;

        typedef struct packed {
            logic valid;
            logic sent;
            logic cancelled;
            logic [CI-1:0] context_id;
            logic [V-1:0] version;
            logic [IM-1:0] image;
            logic [N-1:0] written;
            logic [31:0] crc;
            logic [T-1:0] tag;
        } validation_t;

        typedef struct packed {
            logic valid;
            logic fatal;
            logic [ER-1:0] code;
            logic [2:0] source;
            logic [O-1:0] owner;
            logic [K-1:0] kernel;
            logic [CI-1:0] context_id;
            logic [3:0] state;
            logic [T-1:0] tag;
        } error_t;

        typedef struct packed {
            logic [2:0] command;
            logic [3:0] state;
            logic error;
            logic [ER-1:0] code;
            logic [T-1:0] tag;
        } runtime_response_t;

        control_t control;
        control_t control_next;
        wire [V-1:0] versions[C];
        wire [N-1:0] written[C];
        wire [C-1:0] validated;
        logic [V-1:0] next_versions[C];
        logic [N-1:0] next_written[C];
        logic [C-1:0] next_validated;
        validation_t validation;
        validation_t validation_next;
        error_t first_error;
        error_t error_next;
        cfg_request_t cfg;
        wire [$bits(cfg_request_t)-1:0] external_cfg = {i_cfg_request_command,
            i_cfg_request_tile_id, i_cfg_request_owner_id, i_cfg_request_context_id,
            i_cfg_request_word_index, i_cfg_request_write_data, i_cfg_request_write_strobe,
            i_cfg_request_expected_crc, i_cfg_request_tag};
        wire external_cfg_known = ^external_cfg !== 1'bx;
        wire cfg_unknown;
        cfg_response_t cfg_response;
        cfg_response_t cfg_response_next;
        runtime_response_t runtime_response;
        runtime_response_t runtime_response_next;
        wire control_bad;
        wire control_corrected;
        wire validation_bad;
        wire validation_corrected;
        wire error_bad;
        wire error_corrected;
        wire [C-1:0] context_bad;
        wire [C-1:0] context_corrected;
        wire [C-1:0] image_bad;
        wire [C-1:0] image_corrected;
        wire [C-1:0] committed;
        wire [C-1:0] version_exhausted;
        wire [C*IM-1:0] images;
        wire [CI-1:0] selected_context;
        wire seq_idle;
        wire seq_error;
        wire seq_activate;
        wire seq_stop;
        wire cfg_valid;
        wire cfg_ready;
        wire cfg_response_ready;
        wire response_valid;
        logic response_next;
        logic runtime_valid;
        logic runtime_valid_next;
        logic runtime_pending;
        logic runtime_pending_next;
        logic [2:0] pending_command;
        logic [2:0] pending_command_next;
        logic [T-1:0] pending_tag;
        logic [T-1:0] pending_tag_next;
        wire queues_empty;
        wire outputs_empty;
        wire queue_fault;
        wire response_bad;
        wire response_corrected;
        wire runtime_response_bad;
        wire runtime_response_corrected;
        wire queue_corrected;
        wire protocol_fault;
        wire metadata_fault;
        wire schedule_fault;
        wire power_fatal;
        wire power_error;
        wire power_transition;
        wire power_clock;
        wire power_accept;
        wire power_drain;
        wire power_isolate;
        wire power_switch;
        wire power_reset;
        wire [3:0] physical_power;
        wire [2:0] architectural_power;
        wire power_policy_valid;
        wire power_command_ready;
        wire power_command_done;
        wire power_command_rejected;
        wire healthy;
        wire debug_fire;
        wire debug_write_ok;
        wire trace_drop;
        logic error_event_valid;
        wire [E-1:0] error_event_payload;
        wire safe_boundary = i_body_idle === 1'b1 && i_body_safe_point === 1'b1 && queues_empty;
        wire safe_mutation = safe_boundary &&!validation.valid &&!runtime_pending &&
            control.state != tile_shell_pkg::TILE_ACTIVE && control.state !=
                tile_shell_pkg::TILE_SUSPENDING &&
            control.state != tile_shell_pkg::TILE_DRAINING &&!power_transition;
        wire body_advance_index_ok = (^i_body_next_context !== 1'bx) &&
            {1'b0, i_body_next_context} < (CI + 1)'(C);
        wire body_advance_requested = BODY_CONTEXT_ADVANCE == 1 &&
            i_body_context_advance === 1'b1;
        wire body_advance_fault = body_advance_requested && (!body_advance_index_ok ||
            validated[i_body_next_context] !== 1'b1);
        assign o_body_context_advance_ready = BODY_CONTEXT_ADVANCE == 1 && healthy &&
            safe_boundary &&!validation.valid &&!runtime_pending &&!runtime_valid &&
            !cfg_valid &&!response_valid &&!power_transition &&
            control.state == tile_shell_pkg::TILE_ACTIVE &&!body_advance_fault;
        wire body_advance_fire = body_advance_requested && o_body_context_advance_ready;
        wire [CI-1:0] sequencer_target = body_advance_fire ?
            i_body_next_context : cfg.context_id;
        wire completion_fault = i_body_completed === 1'b1 &&!control.body_completed &&
            (control.completion || control.completion_event ||
            control.state == tile_shell_pkg::TILE_COMPLETED);
        wire selected_address_valid = (^selected_context !== 1'bx) &&
            {1'b0, selected_context} < (CI + 1)'(C);
        wire active_context_fault = control.active && (!selected_address_valid ||
            validated[selected_context] !== 1'b1 || committed[selected_context] !== 1'b1);
        wire fatal_live = body_advance_fault || active_context_fault || completion_fault ||
            control_bad ||
            validation_bad || error_bad ||
            (|context_bad) ||
            (|image_bad) || queue_fault || response_bad || runtime_response_bad || seq_error ||
                power_fatal ||
            i_body_fatal_error === 1'b1 ||
            (reset_b && i_body_power_good === 1'b0 && i_body_isolation_ack !== 1'b1);
        wire operational_controls_known = ^{i_test_enable, i_scan_enable, i_body_power_good,
            i_body_isolation_ack, i_body_save_done, i_body_restore_done} !== 1'bx;
        assign healthy = interface_up && operational_controls_known &&
            !first_error.fatal &&!fatal_live;
        wire cfg_fire = cfg_valid && cfg_ready;
        wire runtime_known = ^{i_runtime_request_command, i_runtime_request_owner_id,
            i_runtime_request_kernel_id, i_runtime_request_context_id,
            i_runtime_request_tag} !== 1'bx;
        wire execution_wake = i_runtime_request_valid === 1'b1 && runtime_known &&
            control.allocated && control.active &&
            i_runtime_request_owner_id == control.owner &&
            i_runtime_request_kernel_id == control.kernel &&
            ((i_runtime_request_command == tile_shell_pkg::RUNTIME_START &&
            (control.state == tile_shell_pkg::TILE_READY ||
            control.state == tile_shell_pkg::TILE_COMPLETED)) ||
            (i_runtime_request_command == tile_shell_pkg::RUNTIME_RESUME &&
            control.state == tile_shell_pkg::TILE_SUSPENDED));
        wire runtime_fire = i_runtime_request_valid === 1'b1 && o_runtime_request_ready;
        wire terminate_now = runtime_fire && i_runtime_request_command ==
            tile_shell_pkg::RUNTIME_TERMINATE &&
            control.allocated && i_runtime_request_owner_id == control.owner &&
            i_runtime_request_kernel_id == control.kernel;
        wire flush = reset_b && (terminate_now || first_error.fatal || fatal_live);
        wire running = healthy &&!flush && control.state == tile_shell_pkg::TILE_ACTIVE &&
            (architectural_power == tile_shell_pkg::POWER_ACTIVE ||
            architectural_power == tile_shell_pkg::POWER_STALLED) && power_accept &&!power_reset;
        wire retiring = healthy &&!flush && (control.state == tile_shell_pkg::TILE_ACTIVE ||
            control.state == tile_shell_pkg::TILE_SUSPENDING || control.state ==
                tile_shell_pkg::TILE_DRAINING);
        wire wake_pending;
        wire body_usable = healthy &&!power_reset && o_body_clock_enable &&
            i_body_power_good === 1'b1 && i_body_isolation_ack === 1'b0;
        wire terminal_event_retiring = retiring || (BODY_DRAIN_EVENTS == 1 && healthy &&
            !flush && control.active && control.state == tile_shell_pkg::TILE_READY &&
            i_body_busy === 1'b1);
        wire power_needs_wake = physical_power != tile_power_controller_pkg::PWR_ACTIVE &&
            physical_power != tile_power_controller_pkg::PWR_STALLED;
        wire [BY-1:0] cfg_strobe = cfg.strobe;
        wire [W-1:0] cfg_write_data = cfg.data;
        wire config_known = ^cfg !== 1'bx;
        wire cfg_capacity = !response_valid || cfg_response_ready;
        wire runtime_capacity = !runtime_valid || i_runtime_response_ready === 1'b1;
        wire context_index_ok = {1'b0, cfg.context_id} < (CI + 1)'(C);
        wire word_index_ok = {1'b0, cfg.word_index} < (WI + 1)'(N);
        wire [CI-1:0] cfg_index = context_index_ok ? cfg.context_id : '0;
        wire [WI-1:0] word_index = word_index_ok ? cfg.word_index : '0;
        wire [IM-1:0] cfg_image = images[cfg_index*IM+:IM];
        logic write_context;
        logic commit_context;
        logic invalidate_context;
        logic release_contexts;
        logic [CI-1:0] commit_index;
        logic [IM-1:0] merged_image;
        logic [ER-1:0] cfg_error;
        logic [ER-1:0] runtime_error;
        logic [ER-1:0] detected_error;
        logic detected_fatal;
        shell_error_source_t detected_source;
        logic clear_error;
        logic [T-1:0] error_tag;
        logic body_start;
        logic body_resume;
        logic [15:0] events;
        wire cfg_activate_ok = cfg_fire && cfg.command == tile_shell_pkg::CFG_ACTIVATE &&
            cfg_error == 0;
        assign seq_activate = cfg_activate_ok;
        assign seq_stop = release_contexts &&!seq_idle;

        // Configuration owns a request/response bridge pair. Logical capacity
        // can be non-power-of-two; physical Gray FIFOs round storage upward.
        if (CONFIG_ASYNC == 1) begin : g_bridge
            localparam int DEPTH = 1 << $clog2(Q);
            logic source_unknown;
            (* ASYNC_REG = "TRUE" *) wire [1:0] unknown_sync;

            always_ff @(posedge i_cfg_clk or negedge cfg_reset_b) begin
                if (!cfg_reset_b) source_unknown <= 1'b0;
                else source_unknown <= i_cfg_request_valid !== 1'b0 &&
                    (i_cfg_request_valid !== 1'b1 ||!external_cfg_known);
            end

            dff #(.WIDTH(2), .ASYNC_RESET(1)) u_unknown_sync (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_enable(1'b1),
                .i_d({unknown_sync[0], source_unknown}),
                .o_q(unknown_sync)
            );

            assign cfg_unknown = unknown_sync[1];
            wire [$clog2(DEPTH+1)-1:0] request_level;
            wire [$clog2(DEPTH+1)-1:0] response_level;
            wire request_ready;
            wire response_ready;
            wire response_out;
            wire [$bits(cfg_response_t)-1:0] response_data;

            async_fifo #(.DATA_WIDTH($bits(cfg_request_t)), .DEPTH(DEPTH)) u_requests (
                .i_w_clk(i_cfg_clk),
                .i_w_rstb(cfg_reset_b),
                .i_w_valid(reset_known && i_cfg_request_valid === 1'b1 && external_cfg_known &&
                    request_level < Q),
                .o_w_ready(request_ready),
                .i_w_data({i_cfg_request_command, i_cfg_request_tile_id, i_cfg_request_owner_id,
                    i_cfg_request_context_id, i_cfg_request_word_index, i_cfg_request_write_data,
                    i_cfg_request_write_strobe, i_cfg_request_expected_crc, i_cfg_request_tag}),
                .i_r_clk(i_clk),
                .i_r_rstb(reset_b),
                .o_r_valid(cfg_valid),
                .i_r_ready(cfg_ready),
                .o_r_data(cfg),
                .o_w_level(request_level),
                .o_w_full(),
                .o_w_almost_full(),
                .o_w_init_done(),
                .o_r_empty(),
                .o_r_almost_empty(),
                .o_r_level(),
                .o_r_init_done()
            );

            assign o_cfg_request_ready = reset_known && request_ready && external_cfg_known &&
                request_level < Q;

            async_fifo #(.DATA_WIDTH($bits(cfg_response_t)), .DEPTH(DEPTH)) u_responses (
                .i_w_clk(i_clk),
                .i_w_rstb(reset_b),
                .i_w_valid(interface_up && response_valid && response_level < Q),
                .o_w_ready(response_ready),
                .i_w_data(cfg_response),
                .i_r_clk(i_cfg_clk),
                .i_r_rstb(cfg_reset_b),
                .o_r_valid(response_out),
                .i_r_ready(reset_known && i_cfg_response_ready === 1'b1),
                .o_r_data(response_data),
                .o_w_level(response_level),
                .o_w_full(),
                .o_w_almost_full(),
                .o_w_init_done(),
                .o_r_empty(),
                .o_r_almost_empty(),
                .o_r_level(),
                .o_r_init_done()
            );

            assign cfg_response_ready = interface_up && response_ready && response_level < Q;
            assign o_cfg_response_valid = reset_known && cfg_reset_b && response_out;
            assign {o_cfg_response_command, o_cfg_response_context_id, o_cfg_response_read_data,
                o_cfg_response_context_version, o_cfg_response_crc, o_cfg_response_error,
                o_cfg_response_error_code, o_cfg_response_tag} = o_cfg_response_valid ?
                response_data : '0;
        end else begin : g_direct_config
            assign cfg_unknown = i_cfg_request_valid !== 1'b0 &&
                (i_cfg_request_valid !== 1'b1 ||!external_cfg_known);
            assign cfg_valid = i_cfg_request_valid === 1'b1;
            assign cfg = {i_cfg_request_command, i_cfg_request_tile_id, i_cfg_request_owner_id,
                i_cfg_request_context_id, i_cfg_request_word_index, i_cfg_request_write_data,
                i_cfg_request_write_strobe, i_cfg_request_expected_crc, i_cfg_request_tag};
            assign o_cfg_request_ready = cfg_ready;
            assign cfg_response_ready = interface_up && i_cfg_response_ready === 1'b1;
            assign o_cfg_response_valid = interface_up && response_valid;
            assign {o_cfg_response_command, o_cfg_response_context_id, o_cfg_response_read_data,
                o_cfg_response_context_version, o_cfg_response_crc, o_cfg_response_error,
                o_cfg_response_error_code, o_cfg_response_tag} = o_cfg_response_valid ?
                    cfg_response : '0;
        end

        // Validation results get response priority. Writes may proceed while a
        // candidate is outstanding, making stale-response handling observable.
        assign cfg_ready = interface_up && cfg_capacity && config_known &&
            !(validation.valid && (i_body_validate_result_valid === 1'b1 ||
                validation.cancelled || flush)) &&
            !(validation.valid && cfg.command == tile_shell_pkg::CFG_VALIDATE) &&!runtime_fire;
        assign o_runtime_request_ready = interface_up && runtime_capacity &&!runtime_pending &&
            runtime_known &&!cfg_valid &&
            (!execution_wake || architectural_power == tile_shell_pkg::POWER_ACTIVE);

        function automatic logic [31:0] crc32c(input logic [IM-1:0] image);
            logic [31:0] crc;
            crc = '1;

            for (int b = 0; b < IM / 8; b++) begin
                crc = crc_pkg::crc32c_byte(crc, image[b*8+:8]);
            end

            return ~crc;
        endfunction

        // Context-memory holds protected raw words; validation is separately
        // committed. Byte merges use corrected read data and initialize unwritten
        // bytes to zero. No executable word or immutable snapshot is overwritten.
        localparam int CODE = ecc_pkg::code_width(W, CONTEXT_PROTECTION);
        wire [C*N*CODE-1:0] raw_images;
        wire [N*CODE-1:0] write_image;
        wire [C*CI-1:0] read_addresses;
        wire [N-1:0] write_mask = N'(1) << word_index;

        for (genvar c = 0; c < C; c++) begin : g_context
            assign read_addresses[c*CI+:CI] = CI'(c);
            assign version_exhausted[c] = &versions[c];

            tile_shell_state #(.WIDTH($bits(context_t)), .PROTECTION(CONTROL_PROTECTION)) u_state (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_enable(reset_known && ({next_versions[c], next_written[c], next_validated[c]} !=
                    {versions[c], written[c], validated[c]})),
                .i_data({next_versions[c], next_written[c], next_validated[c]}),
                .o_data({versions[c], written[c], validated[c]}),
                .o_bad(context_bad[c]),
                .o_corrected(context_corrected[c])
            );

            wire [N-1:0] bad;
            wire [N-1:0] corrected;

            for (genvar w = 0; w < N; w++) begin : g_word
                wire [W-1:0] decoded;

                tile_shell_codec #(.WIDTH(W), .PROTECTION(CONTEXT_PROTECTION)) u_codec (
                    .i_data(merged_image[w*W+:W]),
                    .o_code(),
                    .i_code(raw_images[(c*N+w)*CODE+:CODE]),
                    .o_data(decoded),
                    .o_bad(bad[w]),
                    .o_corrected(corrected[w])
                );

                assign images[(c*N+w)*W+:W] = written[c][w] ? decoded : '0;
            end

            assign image_bad[c] = |(bad & written[c]);
            assign image_corrected[c] = |(corrected & written[c]);
        end

        for (genvar w = 0; w < N; w++) begin : g_write_codec
            tile_shell_codec #(.WIDTH(W), .PROTECTION(CONTEXT_PROTECTION)) u_codec (
                .i_data(merged_image[w*W+:W]),
                .o_code(write_image[w*CODE+:CODE]),
                .i_code({CODE{1'b0}}),
                .o_data(),
                .o_bad(),
                .o_corrected()
            );
        end

        context_memory #(
            .CONTEXT_WIDTH(N * CODE),
            .CONTEXT_DEPTH(C),
            .WRITE_SLICE_WIDTH(CODE),
            .NUM_READ_PORTS(C)
        ) u_context_memory (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_read_enable({C{1'b1}}),
            .i_read_raw({C{1'b1}}),
            .i_read_address(read_addresses),
            .o_read_data(raw_images),
            .o_read_valid(committed),
            .i_write_enable(write_context),
            .i_write_mask(write_mask),
            .i_write_address(cfg.context_id),
            .i_write_data(write_image),
            .i_commit_enable(commit_context),
            .i_commit_address(commit_index),
            .i_invalidate_enable(invalidate_context),
            .i_invalidate_address(cfg.context_id)
        );

        context_sequencer #(.CONTEXT_DEPTH(C), .HAS_LOOP(0)) u_sequencer (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_start_enable(seq_activate && seq_idle),
            .i_start_context(sequencer_target),
            .i_stop_request(seq_stop),
            .i_suspend_request(1'b0),
            .i_resume_request(1'b0),
            .i_switch_request((seq_activate &&!seq_idle) || body_advance_fire),
            .i_switch_context(sequencer_target),
            .i_error_clear(1'b0),
            .i_step_accepted(1'b0),
            .i_safe_point(safe_boundary),
            .i_transition_mode(context_sequencer_pkg::CONTEXT_HOLD),
            .i_transition_target({CI{1'b0}}),
            .i_loop_count(16'b0),
            .i_active_context_valid(!control.active || validated[selected_context]),
            .i_candidate_context_valid(body_advance_fire ? validated[i_body_next_context] :
                context_index_ok && validated[cfg_index]),
            .o_active_context(selected_context),
            .o_idle(seq_idle),
            .o_error(seq_error),
            .o_active_read_enable(),
            .o_candidate_read_enable(),
            .o_candidate_context(),
            .o_context_enable(),
            .o_quiesce_request(),
            .o_active(),
            .o_context_wait(),
            .o_stop_pending(),
            .o_suspend_pending(),
            .o_suspended(),
            .o_switch_pending(),
            .o_completed(),
            .o_error_code(),
            .o_context_activated(),
            .o_context_changed(),
            .o_sequence_completed(),
            .o_loop_active(),
            .o_loop_owner(),
            .o_loop_remaining()
        );

        // Port zero occupies the least-significant packed slice. Each record
        // stores payload and metadata atomically; invalid outputs are isolated.
        wire [NI-1:0] data_in_bad;
        wire [NI-1:0] data_in_corrected;
        wire [NI-1:0] data_in_metadata_bad;
        wire [NI-1:0] data_in_schedule_bad;
        wire [31:0] data_in_count[NI];
        wire [NI-1:0] data_in_source_fire;
        wire [NI-1:0] data_in_sink_fire;

        for (genvar port_index = 0; port_index < NI; port_index++) begin : g_data_in
            wire [M-1:0] metadata = i_data_in_metadata[port_index*M+:M];
            wire metadata_matches = (^ metadata !== 1'bx) && control.active &&
                metadata[CI-1:0] == selected_context &&
                metadata[CI+:V] == versions[selected_context];
            wire source_valid = i_data_in_valid[port_index] === 1'b1;
            wire admission = running;
            assign data_in_metadata_bad[port_index] = reset_b && admission &&
                source_valid &&!metadata_matches;
            assign data_in_schedule_bad[port_index] = running && (!INPUT_ELASTIC_MASK[port_index])
                &&
                ((source_valid &&!o_data_in_ready[port_index]) ||
                (i_body_data_in_ready[port_index] === 1'b1 &&!source_valid));

            tile_shell_queue #(
                .WIDTH(D + M),
                .DEPTH(BI),
                .PROTECTION(CONTROL_PROTECTION)
            ) u_channel (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_flush(flush),
                .i_admit(admission && metadata_matches),
                .i_deliver(retiring && body_usable),
                .i_valid(source_valid),
                .o_ready(o_data_in_ready[port_index]),
                .i_data({i_data_in_metadata[port_index*M+:M],
                    i_data_in_payload[port_index*D+:D]}),
                .o_valid(o_body_data_in_valid[port_index]),
                .i_ready(i_body_data_in_ready[port_index] === 1'b1),
                .o_data({o_body_data_in_metadata[port_index*M+:M],
                    o_body_data_in_payload[port_index*D+:D]}),
                .o_count(data_in_count[port_index]),
                .o_bad(data_in_bad[port_index]),
                .o_corrected(data_in_corrected[port_index])
            );

            assign data_in_source_fire[port_index] = source_valid && o_data_in_ready[port_index];
            assign data_in_sink_fire[port_index] = o_body_data_in_valid[port_index] &&
                i_body_data_in_ready[port_index] === 1'b1;
        end

        wire [NO-1:0] data_out_bad;
        wire [NO-1:0] data_out_corrected;
        wire [NO-1:0] data_out_metadata_bad;
        wire [NO-1:0] data_out_schedule_bad;
        wire [31:0] data_out_count[NO];
        wire [NO-1:0] data_out_source_fire;
        wire [NO-1:0] data_out_sink_fire;

        for (genvar port_index = 0; port_index < NO; port_index++) begin : g_data_out
            wire [M-1:0] metadata = i_body_data_out_metadata[port_index*M+:M];
            wire metadata_matches = (^ metadata !== 1'bx) && control.active &&
                metadata[CI-1:0] == selected_context &&
                metadata[CI+:V] == versions[selected_context];
            wire source_valid = i_body_data_out_valid[port_index] === 1'b1;
            wire admission = retiring && body_usable;
            assign data_out_metadata_bad[port_index] = reset_b && admission &&
                source_valid &&!metadata_matches;
            assign data_out_schedule_bad[port_index] = running &&
                (!OUTPUT_ELASTIC_MASK[port_index]) &&
                source_valid &&!o_body_data_out_ready[port_index];

            tile_shell_queue #(
                .WIDTH(D + M),
                .DEPTH(BO),
                .PROTECTION(CONTROL_PROTECTION)
            ) u_channel (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_flush(flush),
                .i_admit(admission && metadata_matches),
                .i_deliver(healthy && control.state != tile_shell_pkg::TILE_SUSPENDED),
                .i_valid(source_valid),
                .o_ready(o_body_data_out_ready[port_index]),
                .i_data({i_body_data_out_metadata[port_index*M+:M],
                    i_body_data_out_payload[port_index*D+:D]}),
                .o_valid(o_data_out_valid[port_index]),
                .i_ready(i_data_out_ready[port_index] === 1'b1),
                .o_data({o_data_out_metadata[port_index*M+:M],
                    o_data_out_payload[port_index*D+:D]}),
                .o_count(data_out_count[port_index]),
                .o_bad(data_out_bad[port_index]),
                .o_corrected(data_out_corrected[port_index])
            );

            assign data_out_source_fire[port_index] = source_valid &&
                o_body_data_out_ready[port_index];
            assign data_out_sink_fire[port_index] = o_data_out_valid[port_index] &&
                i_data_out_ready[port_index] === 1'b1;
        end

        wire [PI-1:0] predicate_in_bad;
        wire [PI-1:0] predicate_in_corrected;
        wire [PI-1:0] predicate_in_metadata_bad;
        wire [PI-1:0] predicate_in_schedule_bad;
        wire [31:0] predicate_in_count[PI];
        wire [PI-1:0] predicate_in_source_fire;
        wire [PI-1:0] predicate_in_sink_fire;

        for (genvar port_index = 0; port_index < PI; port_index++) begin : g_predicate_in
            wire [PM-1:0] metadata = i_predicate_in_metadata[port_index*PM+:PM];
            wire metadata_matches = (^ metadata !== 1'bx) && control.active &&
                metadata[CI-1:0] == selected_context;
            wire source_valid = i_predicate_in_valid[port_index] === 1'b1;
            wire admission = running;
            assign predicate_in_metadata_bad[port_index] = reset_b && admission &&
                source_valid &&!metadata_matches;
            assign predicate_in_schedule_bad[port_index] = 1'b0;

            tile_shell_queue #(
                .WIDTH(P + PM),
                .DEPTH(BI),
                .PROTECTION(CONTROL_PROTECTION)
            ) u_channel (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_flush(flush),
                .i_admit(admission && metadata_matches),
                .i_deliver(retiring && body_usable),
                .i_valid(source_valid),
                .o_ready(o_predicate_in_ready[port_index]),
                .i_data({i_predicate_in_metadata[port_index*PM+:PM],
                    i_predicate_in_payload[port_index*P+:P]}),
                .o_valid(o_body_predicate_in_valid[port_index]),
                .i_ready(i_body_predicate_in_ready[port_index] === 1'b1),
                .o_data({o_body_predicate_in_metadata[port_index*PM+:PM],
                    o_body_predicate_in_payload[port_index*P+:P]}),
                .o_count(predicate_in_count[port_index]),
                .o_bad(predicate_in_bad[port_index]),
                .o_corrected(predicate_in_corrected[port_index])
            );

            assign predicate_in_source_fire[port_index] = source_valid &&
                o_predicate_in_ready[port_index];
            assign predicate_in_sink_fire[port_index] = o_body_predicate_in_valid[port_index] &&
                i_body_predicate_in_ready[port_index] === 1'b1;
        end

        wire [PO-1:0] predicate_out_bad;
        wire [PO-1:0] predicate_out_corrected;
        wire [PO-1:0] predicate_out_metadata_bad;
        wire [PO-1:0] predicate_out_schedule_bad;
        wire [31:0] predicate_out_count[PO];
        wire [PO-1:0] predicate_out_source_fire;
        wire [PO-1:0] predicate_out_sink_fire;

        for (genvar port_index = 0; port_index < PO; port_index++) begin : g_predicate_out
            wire [PM-1:0] metadata = i_body_predicate_out_metadata[port_index*PM+:PM];
            wire metadata_matches = (^ metadata !== 1'bx) && control.active &&
                metadata[CI-1:0] == selected_context;
            wire source_valid = i_body_predicate_out_valid[port_index] === 1'b1;
            wire admission = retiring && body_usable;
            assign predicate_out_metadata_bad[port_index] = reset_b && admission &&
                source_valid &&!metadata_matches;
            assign predicate_out_schedule_bad[port_index] = 1'b0;

            tile_shell_queue #(
                .WIDTH(P + PM),
                .DEPTH(BO),
                .PROTECTION(CONTROL_PROTECTION)
            ) u_channel (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_flush(flush),
                .i_admit(admission && metadata_matches),
                .i_deliver(healthy && control.state != tile_shell_pkg::TILE_SUSPENDED),
                .i_valid(source_valid),
                .o_ready(o_body_predicate_out_ready[port_index]),
                .i_data({i_body_predicate_out_metadata[port_index*PM+:PM],
                    i_body_predicate_out_payload[port_index*P+:P]}),
                .o_valid(o_predicate_out_valid[port_index]),
                .i_ready(i_predicate_out_ready[port_index] === 1'b1),
                .o_data({o_predicate_out_metadata[port_index*PM+:PM],
                    o_predicate_out_payload[port_index*P+:P]}),
                .o_count(predicate_out_count[port_index]),
                .o_bad(predicate_out_bad[port_index]),
                .o_corrected(predicate_out_corrected[port_index])
            );

            assign predicate_out_source_fire[port_index] = source_valid &&
                o_body_predicate_out_ready[port_index];
            assign predicate_out_sink_fire[port_index] = o_predicate_out_valid[port_index] &&
                i_predicate_out_ready[port_index] === 1'b1;
        end

        wire [EI-1:0] event_in_bad;
        wire [EI-1:0] event_in_corrected;
        wire [EI-1:0] event_in_metadata_bad;
        wire [EI-1:0] event_in_schedule_bad;
        wire [31:0] event_in_count[EI];
        wire [EI-1:0] event_in_source_fire;
        wire [EI-1:0] event_in_sink_fire;

        for (genvar port_index = 0; port_index < EI; port_index++) begin : g_event_in
            wire [E-1:0] payload = i_event_in_payload[port_index*E+:E];
            wire metadata_matches = (^ payload !== 1'bx) && control.active &&
                payload[3+:CI] == selected_context && payload[3+CI+:K] == control.kernel;
            wire source_valid = i_event_in_valid[port_index] === 1'b1;
            wire admission = healthy && control.active && (running ||
                payload[2:0] == tile_shell_pkg::EVENT_WAKEUP || payload[2:0] ==
                    tile_shell_pkg::EVENT_ERROR ||
                payload[2:0] == tile_shell_pkg::EVENT_FATAL);
            assign event_in_metadata_bad[port_index] = reset_b && admission &&
                source_valid &&!metadata_matches;
            assign event_in_schedule_bad[port_index] = 1'b0;

            tile_shell_queue #(
                .WIDTH(E),
                .DEPTH(BI > 0 ? BI : 1),
                .PROTECTION(CONTROL_PROTECTION)
            ) u_channel (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_flush(flush),
                .i_admit(admission && metadata_matches),
                .i_deliver(healthy && control.state != tile_shell_pkg::TILE_SUSPENDED &&
                    o_body_clock_enable &&!power_reset),
                .i_valid(source_valid),
                .o_ready(o_event_in_ready[port_index]),
                .i_data(payload),
                .o_valid(o_body_event_in_valid[port_index]),
                .i_ready(i_body_event_in_ready[port_index] === 1'b1),
                .o_data(o_body_event_in_payload[port_index*E+:E]),
                .o_count(event_in_count[port_index]),
                .o_bad(event_in_bad[port_index]),
                .o_corrected(event_in_corrected[port_index])
            );

            assign event_in_source_fire[port_index] = source_valid && o_event_in_ready[port_index];
            assign event_in_sink_fire[port_index] = o_body_event_in_valid[port_index] &&
                i_body_event_in_ready[port_index] === 1'b1;
        end

        wire [EO-1:0] event_out_bad;
        wire [EO-1:0] event_out_corrected;
        wire [EO-1:0] event_out_metadata_bad;
        wire [EO-1:0] event_out_schedule_bad;
        wire [31:0] event_out_count[EO];
        wire [EO-1:0] event_out_source_fire;
        wire [EO-1:0] event_out_sink_fire;
        wire [EO-1:0] event_out_valid;
        wire [EO*E-1:0] event_out_payload;

        for (genvar event_port = 0; event_port < EO; event_port++) begin : g_event_out
            wire [E-1:0] payload = i_body_event_out_payload[event_port*E+:E];
            wire metadata_matches = (^ payload !== 1'bx) && control.active &&
                payload[3+:CI] == selected_context && payload[3+CI+:K] == control.kernel;
            wire source_valid = i_body_event_out_valid[event_port] === 1'b1;
            wire admission = terminal_event_retiring && body_usable;
            wire deliver;

            if (event_port == 0) begin : g_completion_priority
                assign deliver = healthy && control.state != tile_shell_pkg::TILE_SUSPENDED &&
                    !control.completion_event &&!error_event_valid;
            end else begin : g_body_event
                assign deliver = healthy && control.state != tile_shell_pkg::TILE_SUSPENDED;
            end

            assign event_out_metadata_bad[event_port] = reset_b && admission &&
                source_valid &&!metadata_matches;
            assign event_out_schedule_bad[event_port] = 1'b0;

            tile_shell_queue #(
                .WIDTH(E),
                .DEPTH(BO > 0 ? BO : 1),
                .PROTECTION(CONTROL_PROTECTION)
            ) u_channel (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_flush(flush && BODY_DRAIN_EVENTS == 0),
                .i_admit(admission && metadata_matches),
                .i_deliver(deliver),
                .i_valid(source_valid),
                .o_ready(o_body_event_out_ready[event_port]),
                .i_data(payload),
                .o_valid(event_out_valid[event_port]),
                .i_ready(i_event_out_ready[event_port] === 1'b1),
                .o_data(event_out_payload[event_port*E+:E]),
                .o_count(event_out_count[event_port]),
                .o_bad(event_out_bad[event_port]),
                .o_corrected(event_out_corrected[event_port])
            );

            assign event_out_source_fire[event_port] = source_valid &&
                o_body_event_out_ready[event_port];
            assign event_out_sink_fire[event_port] = event_out_valid[event_port] &&
                i_event_out_ready[event_port] === 1'b1;
        end

        logic [31:0] input_count;
        logic [31:0] output_count;

        always @* begin
            input_count = '0;
            output_count = '0;

            for (int p = 0; p < NI; p++)
                input_count = input_count + data_in_count[p];
            for (int p = 0; p < NO; p++)
                output_count = output_count + data_out_count[p];
            for (int p = 0; p < PI; p++)
                input_count = input_count + predicate_in_count[p];
            for (int p = 0; p < PO; p++)
                output_count = output_count + predicate_out_count[p];
            for (int p = 0; p < EI; p++)
                input_count = input_count + event_in_count[p];
            for (int p = 0; p < EO; p++)
                output_count = output_count + event_out_count[p];
        end

        assign queues_empty = input_count == 0 && output_count == 0;
        assign outputs_empty = output_count == 0 && i_body_data_out_valid === '0 &&
            i_body_predicate_out_valid === '0 && i_body_event_out_valid === '0;
        assign queue_fault = (|data_in_bad) ||
            (|data_out_bad) ||
            (|predicate_in_bad) ||
            (|predicate_out_bad) ||
            (|event_in_bad) ||
            (|event_out_bad);
        assign queue_corrected = (|data_in_corrected) ||
            (|data_out_corrected) ||
            (|predicate_in_corrected) ||
            (|predicate_out_corrected) ||
            (|event_in_corrected) ||
            (|event_out_corrected);
        assign metadata_fault = (|data_in_metadata_bad) ||
            (|data_out_metadata_bad) ||
            (|predicate_in_metadata_bad) ||
            (|predicate_out_metadata_bad) ||
            (|event_in_metadata_bad) ||
            (|event_out_metadata_bad);
        assign schedule_fault = (|data_in_schedule_bad) ||
            (|data_out_schedule_bad) ||
            (|predicate_in_schedule_bad) ||
            (|predicate_out_schedule_bad) ||
            (|event_in_schedule_bad) ||
            (|event_out_schedule_bad);
        assign protocol_fault = reset_b && (!reset_known || (^ {i_test_enable, i_scan_enable,
            i_runtime_request_valid, i_runtime_response_ready, i_debug_request_valid,
            i_debug_response_ready, i_power_request_valid, i_power_response_ready,
            i_data_in_valid, i_data_out_ready, i_body_data_in_ready, i_body_data_out_valid,
            i_predicate_in_valid, i_predicate_out_ready, i_body_predicate_in_ready,
            i_body_predicate_out_valid, i_event_in_valid, i_event_out_ready,
            i_body_event_in_ready, i_body_event_out_valid, i_body_safe_point,
            i_body_idle, i_body_busy, i_body_completed, i_body_drain_done,
            i_body_stall_reasons, i_body_error, i_body_fatal_error, i_body_wakeup_required,
            i_body_power_good, i_body_isolation_ack, i_body_save_done, i_body_restore_done} ===
                1'bx));

        logic event_buffer_pending;
        always @* begin
            event_buffer_pending = 1'b0;

            for (int e = 0; e < EI; e++)
                event_buffer_pending = event_buffer_pending || event_in_count[e] != 0;
        end

        assign wake_pending = event_buffer_pending || |i_event_in_valid ||
            i_body_wakeup_required === 1'b1;
        wire [E-1:0] completion_payload = (E'(control.kernel) << (CI + 3)) |
            (E'(selected_context) << 3) | E'(tile_shell_pkg::EVENT_COMPLETE);
        assign o_event_out_valid = error_event_valid && interface_up ?
            event_out_valid | {{(EO - 1){1'b0}}, 1'b1} :
            control.completion_event && healthy ?
            event_out_valid | {{(EO - 1){1'b0}}, 1'b1} : event_out_valid;

        for (genvar e = 0; e < EO; e++) begin : g_event_mux
            assign o_event_out_payload[e*E+:E] = e == 0 && error_event_valid && interface_up ?
                error_event_payload : e == 0 && control.completion_event && healthy ?
                completion_payload : event_out_payload[e*E+:E];
        end

        wire validation_result_known = ^{i_body_validate_context_id,
            i_body_validate_context_version, i_body_validate_legal,
            i_body_validate_error_code} !== 1'bx;
        wire validation_result_fire = i_body_validate_result_valid === 1'b1 &&
            o_body_validate_result_ready;
        assign o_body_validate_valid = healthy && validation.valid &&!validation.sent &&
            o_body_clock_enable &&!power_reset;
        assign o_body_validate_result_ready = interface_up && validation.valid && validation.sent &&
            cfg_capacity && validation_result_known &&!validation.cancelled &&!flush;
        assign o_body_validate_context_id = reset_b && validation.valid ? validation.context_id :
            '0;
        assign o_body_validate_context_version = reset_b && validation.valid ? validation.version
            : '0;
        assign o_body_validate_context_image = reset_b && validation.valid ? validation.image : '0;
        assign o_body_validate_word_valid = reset_b && validation.valid ? validation.written : '0;
        assign o_body_context_active = healthy && control.active &&
            validated[selected_context] && committed[selected_context];
        assign o_body_context_id = o_body_context_active ? selected_context : '0;
        assign o_body_context_version = o_body_context_active ?
            versions[selected_context] : '0;
        assign o_body_context_image = o_body_context_active ? images[selected_context*IM+:IM] : '0;
        assign o_body_context_word_valid = o_body_context_active ?
            written[selected_context] : '0;
        assign o_body_suspend_request = healthy && control.state == tile_shell_pkg::TILE_SUSPENDING;
        assign o_body_drain_request = healthy && (control.state == tile_shell_pkg::TILE_DRAINING
            || power_drain);
        assign o_body_flush = flush || (reset_b && power_reset);
        assign o_body_start = interface_up && body_start &&!first_error.fatal;
        assign o_body_resume = interface_up && body_resume &&!first_error.fatal;
        assign o_runtime_response_valid = interface_up && runtime_valid;
        assign {o_runtime_response_command, o_runtime_response_state,
            o_runtime_response_error, o_runtime_response_error_code,
            o_runtime_response_tag} = o_runtime_response_valid ? runtime_response : '0;
        always @* begin
            cfg_error = tile_shell_pkg::SHELL_OK;

            if (cfg.tile_id != TI'(TILE_ID)) cfg_error = tile_shell_pkg::SHELL_ERR_TILE;
            else if (control.allocated && cfg.owner != control.owner) cfg_error =
                tile_shell_pkg::SHELL_ERR_OWNER;
            else if (!context_index_ok) cfg_error = tile_shell_pkg::SHELL_ERR_CONTEXT;
            else if (cfg.command > tile_shell_pkg::CFG_QUERY) cfg_error =
                tile_shell_pkg::SHELL_ERR_COMMAND;
            else if ((cfg.command == tile_shell_pkg::CFG_WRITE || cfg.command ==
                tile_shell_pkg::CFG_READ) &&!word_index_ok)
                cfg_error = tile_shell_pkg::SHELL_ERR_WORD;
            else if (cfg.command != tile_shell_pkg::CFG_READ && cfg.command !=
                tile_shell_pkg::CFG_QUERY &&!healthy)
                cfg_error = tile_shell_pkg::SHELL_ERR_STATE;
            else case (cfg.command)
                tile_shell_pkg::CFG_WRITE, tile_shell_pkg::CFG_INVALIDATE: begin
                    if (control.active && cfg.context_id == selected_context)
                        cfg_error = tile_shell_pkg::SHELL_ERR_ACTIVE;
                    else if (cfg.command == tile_shell_pkg::CFG_WRITE && (&versions[cfg_index]))
                        cfg_error = tile_shell_pkg::SHELL_ERR_VERSION;
                end
                tile_shell_pkg::CFG_VALIDATE: begin
                    if (!(&written[cfg_index])) cfg_error = tile_shell_pkg::SHELL_ERR_INCOMPLETE;
                    else if (SUPPORT_CONTEXT_CHECKSUM == 1 && crc32c(cfg_image) != cfg.crc)
                        cfg_error = tile_shell_pkg::SHELL_ERR_CRC;
                end
                tile_shell_pkg::CFG_ACTIVATE: begin
                    if (!control.allocated) cfg_error = tile_shell_pkg::SHELL_ERR_OWNER;
                    else if (!validated[cfg_index]) cfg_error = tile_shell_pkg::SHELL_ERR_CONTEXT;
                    else if (!safe_mutation || runtime_valid || control.completion_event)
                        cfg_error = tile_shell_pkg::SHELL_ERR_STATE;
                end
                default: begin end
            endcase
        end

        always @* begin
            runtime_error = tile_shell_pkg::SHELL_OK;

            if (i_runtime_request_command == tile_shell_pkg::RUNTIME_ALLOCATE) begin
                if (control.allocated ||!safe_mutation || response_valid)
                    runtime_error = tile_shell_pkg::SHELL_ERR_STATE;
            end else if (!control.allocated || i_runtime_request_owner_id != control.owner ||
                i_runtime_request_kernel_id != control.kernel) runtime_error =
                    tile_shell_pkg::SHELL_ERR_OWNER;
            else case (i_runtime_request_command)
                tile_shell_pkg::RUNTIME_START: begin
                    if (!healthy || i_body_power_good !== 1'b1 ||
                        i_body_isolation_ack !== 1'b0 || i_body_error !== 1'b0 ||
                        first_error.valid ||!control.active ||
                        !o_body_context_active || i_runtime_request_context_id != selected_context
                            ||
                        !(control.state == tile_shell_pkg::TILE_READY || control.state ==
                            tile_shell_pkg::TILE_COMPLETED) ||
                        !safe_boundary || architectural_power != tile_shell_pkg::POWER_ACTIVE)
                        runtime_error = tile_shell_pkg::SHELL_ERR_STATE;
                end
                tile_shell_pkg::RUNTIME_SUSPEND: begin
                    if (!healthy || control.state != tile_shell_pkg::TILE_ACTIVE) runtime_error =
                        tile_shell_pkg::SHELL_ERR_STATE;
                end
                tile_shell_pkg::RUNTIME_RESUME: begin
                    if (!healthy || i_body_power_good !== 1'b1 || i_body_isolation_ack !== 1'b0 ||
                        control.state != tile_shell_pkg::TILE_SUSPENDED ||
                        i_body_safe_point !== 1'b1 || architectural_power !=
                            tile_shell_pkg::POWER_ACTIVE)
                        runtime_error = tile_shell_pkg::SHELL_ERR_STATE;
                end
                tile_shell_pkg::RUNTIME_DRAIN: begin
                    if (!healthy ||!(control.state == tile_shell_pkg::TILE_ACTIVE ||
                        control.state == tile_shell_pkg::TILE_SUSPENDED)) runtime_error =
                            tile_shell_pkg::SHELL_ERR_STATE;
                end
                tile_shell_pkg::RUNTIME_TERMINATE: begin end
                tile_shell_pkg::RUNTIME_RELEASE: begin
                    if (|version_exhausted) runtime_error = tile_shell_pkg::SHELL_ERR_VERSION;
                    if (!safe_mutation ||!(control.state == tile_shell_pkg::TILE_READY ||
                        control.state == tile_shell_pkg::TILE_COMPLETED || control.state ==
                            tile_shell_pkg::TILE_CONFIGURING ||
                        control.state == tile_shell_pkg::TILE_ERROR) || control.completion_event)
                        runtime_error = tile_shell_pkg::SHELL_ERR_STATE;
                end
                tile_shell_pkg::RUNTIME_CLEAR_ERROR: begin
                    if (!safe_mutation || first_error.fatal) runtime_error =
                        tile_shell_pkg::SHELL_ERR_STATE;
                end
                default: runtime_error = tile_shell_pkg::SHELL_ERR_COMMAND;
            endcase
        end

        always @* begin
            control_next = control;
            validation_next = validation;
            cfg_response_next = cfg_response;
            response_next = response_valid &&!cfg_response_ready;
            runtime_response_next = runtime_response;
            runtime_valid_next = runtime_valid && i_runtime_response_ready !== 1'b1;
            runtime_pending_next = runtime_pending;
            pending_command_next = pending_command;
            pending_tag_next = pending_tag;
            write_context = 1'b0;
            commit_context = 1'b0;
            invalidate_context = 1'b0;
            release_contexts = 1'b0;
            commit_index = validation.context_id;
            merged_image = cfg_image;
            clear_error = 1'b0;
            events = '0;
            events[0] = |data_in_source_fire;
            events[1] = |data_out_sink_fire;
            events[2] = |predicate_in_source_fire;
            events[3] = |predicate_out_sink_fire;
            events[4] = |event_in_source_fire;
            events[5] = |(o_event_out_valid & i_event_out_ready);
            events[6] = running && (|o_status_stall_reasons);

            for (int c = 0; c < C; c++) begin
                next_versions[c] = versions[c];
                next_written[c] = written[c];
                next_validated[c] = validated[c];
            end

            control_next.body_completed = i_body_completed === 1'b1;

            if (debug_fire && debug_write_ok && i_debug_request_write &&
                i_debug_request_address == 8'h21)
                control_next.monitor = i_debug_request_write_data[0];

            if (o_body_validate_valid && i_body_validate_ready === 1'b1)
                validation_next.sent = 1'b1;

            if (validation_result_fire) begin
                response_next = 1'b1;
                cfg_response_next = '0;
                cfg_response_next.command = tile_shell_pkg::CFG_VALIDATE;
                cfg_response_next.context_id = validation.context_id;
                cfg_response_next.version = validation.version;
                cfg_response_next.crc = validation.crc;
                cfg_response_next.tag = validation.tag;
                validation_next.valid = 1'b0;

                if (!healthy || i_body_validate_context_id != validation.context_id ||
                    i_body_validate_context_version != validation.version ||
                    versions[validation.context_id] != validation.version) begin
                    cfg_response_next.error = 1'b1;
                    cfg_response_next.code = tile_shell_pkg::SHELL_ERR_STALE;
                end else if (i_body_validate_legal !== 1'b1) begin
                    cfg_response_next.error = 1'b1;
                    cfg_response_next.code = i_body_validate_error_code != 0 ?
                        i_body_validate_error_code : ER'(tile_shell_pkg::SHELL_ERR_BODY);
                end else begin
                    next_validated[validation.context_id] = 1'b1;
                    commit_context = 1'b1;
                end
                events[8] = !cfg_response_next.error;
            end

            if (validation.valid && flush) validation_next.cancelled = 1'b1;

            if (validation.valid && (validation.cancelled || flush) && cfg_capacity) begin
                validation_next.valid = 1'b0;
                cfg_response_next = '0;
                cfg_response_next.command = tile_shell_pkg::CFG_VALIDATE;
                cfg_response_next.context_id = validation.context_id;
                cfg_response_next.version = validation.version;
                cfg_response_next.crc = validation.crc;
                cfg_response_next.tag = validation.tag;
                cfg_response_next.error = 1'b1;
                cfg_response_next.code = first_error.fatal || fatal_live ?
                    ER'(tile_shell_pkg::SHELL_ERR_INTEGRITY) : ER'(tile_shell_pkg::SHELL_ERR_STATE);
                response_next = 1'b1;
                commit_context = 1'b0;
                next_validated[validation.context_id] = validated[validation.context_id];
            end

            if (cfg_fire) begin
                cfg_response_next = '0;
                cfg_response_next.command = cfg.command;
                cfg_response_next.context_id = cfg.context_id;
                cfg_response_next.version = versions[cfg_index];
                cfg_response_next.tag = cfg.tag;
                cfg_response_next.error = cfg_error != 0;
                cfg_response_next.code = cfg_error;
                response_next = 1'b1;

                if (cfg_error == 0) case (cfg.command)
                    tile_shell_pkg::CFG_WRITE: begin
                        for (int b = 0; b < BY; b++)
                            if (cfg_strobe[b])
                                merged_image[word_index*W+b*8+:8] = cfg_write_data[b*8+:8];

                        write_context = 1'b1;
                        next_written[cfg_index][word_index] = 1'b1;
                        next_versions[cfg_index] = versions[cfg_index] + 1'b1;
                        next_validated[cfg_index] = 1'b0;
                        cfg_response_next.version = versions[cfg_index] + 1'b1;
                        events[7] = 1'b1;
                    end
                    tile_shell_pkg::CFG_READ: cfg_response_next.data = cfg_image[word_index*W+:W];
                    tile_shell_pkg::CFG_QUERY: begin
                        cfg_response_next.data = W'(written[cfg_index]) |
                            (W'(validated[cfg_index]) << N);
                        cfg_response_next.crc = crc32c(cfg_image);
                    end
                    tile_shell_pkg::CFG_VALIDATE: begin
                        response_next = 1'b0;
                        validation_next.valid = 1'b1;
                        validation_next.sent = 1'b0;
                        validation_next.cancelled = 1'b0;
                        validation_next.context_id = cfg.context_id;
                        validation_next.version = versions[cfg_index];
                        validation_next.image = cfg_image;
                        validation_next.written = written[cfg_index];
                        validation_next.crc = crc32c(cfg_image);
                        validation_next.tag = cfg.tag;
                    end
                    tile_shell_pkg::CFG_ACTIVATE: begin
                        control_next.active = 1'b1;
                        if (control.state != tile_shell_pkg::TILE_SUSPENDED) control_next.state =
                            tile_shell_pkg::TILE_READY;
                        events[9] = 1'b1;
                    end
                    tile_shell_pkg::CFG_INVALIDATE: begin
                        next_validated[cfg_index] = 1'b0;
                        invalidate_context = 1'b1;
                    end
                    default: begin end
                endcase
            end

            if (body_advance_fire) events[9] = 1'b1;

            if (runtime_fire) begin
                runtime_response_next = '0;
                runtime_response_next.command = i_runtime_request_command;
                runtime_response_next.tag = i_runtime_request_tag;
                runtime_response_next.error = runtime_error != 0;
                runtime_response_next.code = runtime_error;
                runtime_valid_next = 1'b1;

                if (runtime_error == 0) begin
                    events[10] = 1'b1;

                    case (i_runtime_request_command)
                        tile_shell_pkg::RUNTIME_ALLOCATE: begin
                            control_next.allocated = 1'b1;
                            control_next.owner = i_runtime_request_owner_id;
                            control_next.kernel = i_runtime_request_kernel_id;
                            control_next.state = tile_shell_pkg::TILE_CONFIGURING;
                            control_next.monitor = 1'b1;
                        end
                        tile_shell_pkg::RUNTIME_START, tile_shell_pkg::RUNTIME_RESUME: begin
                            control_next.state = tile_shell_pkg::TILE_ACTIVE;
                            control_next.completion = 1'b0;
                            control_next.completion_event = 1'b0;
                        end
                        tile_shell_pkg::RUNTIME_SUSPEND, tile_shell_pkg::RUNTIME_DRAIN: begin
                            control_next.state = i_runtime_request_command ==
                                tile_shell_pkg::RUNTIME_SUSPEND ?
                                tile_shell_pkg::TILE_SUSPENDING : tile_shell_pkg::TILE_DRAINING;
                            runtime_pending_next = 1'b1;
                            pending_command_next = i_runtime_request_command;
                            pending_tag_next = i_runtime_request_tag;
                            runtime_valid_next = 1'b0;
                        end
                        tile_shell_pkg::RUNTIME_TERMINATE: begin
                            control_next.state = control.active ? tile_shell_pkg::TILE_READY :
                                tile_shell_pkg::TILE_CONFIGURING;
                            control_next.completion = 1'b0;
                            control_next.completion_event = 1'b0;
                            runtime_pending_next = 1'b0;
                        end
                        tile_shell_pkg::RUNTIME_RELEASE: begin
                            control_next = '0;
                            release_contexts = 1'b1;
                            for (int c = 0; c < C; c++) begin
                                next_validated[c] = 1'b0;
                                next_versions[c] = versions[c] + 1'b1;
                            end
                        end
                        tile_shell_pkg::RUNTIME_CLEAR_ERROR: begin
                            clear_error = 1'b1;
                            if (control.state == tile_shell_pkg::TILE_ERROR)
                                control_next.state = control.active ? tile_shell_pkg::TILE_READY :
                                    tile_shell_pkg::TILE_CONFIGURING;
                        end
                        default: begin end
                    endcase
                end
                runtime_response_next.state = control_next.state;
            end

            if (retiring && i_body_completed === 1'b1 &&!control.body_completed)
                control_next.completion = 1'b1;

            if (control.completion &&!control.completion_event && healthy &&
                safe_boundary && (control.state != tile_shell_pkg::TILE_DRAINING ||
                i_body_drain_done === 1'b1) && outputs_empty &&!validation.valid &&!response_valid
                    &&!error_event_valid) begin
                control_next.completion_event = 1'b1;
            end

            if (control.completion_event &&!error_event_valid && healthy && i_event_out_ready[0]
                === 1'b1) begin
                control_next.completion_event = 1'b0;
                control_next.completion = 1'b0;
                control_next.state = tile_shell_pkg::TILE_COMPLETED;

                if (runtime_pending && pending_command == tile_shell_pkg::RUNTIME_DRAIN &&
                    runtime_capacity) begin
                    runtime_valid_next = 1'b1;
                    runtime_pending_next = 1'b0;
                    runtime_response_next = '0;
                    runtime_response_next.command = pending_command;
                    runtime_response_next.tag = pending_tag;
                    runtime_response_next.state = tile_shell_pkg::TILE_COMPLETED;
                end
                events[11] = 1'b1;
            end

            if (interface_up && runtime_pending && runtime_capacity) begin
                if ((pending_command == tile_shell_pkg::RUNTIME_SUSPEND && i_body_safe_point ===
                    1'b1) ||
                    (pending_command == tile_shell_pkg::RUNTIME_DRAIN && safe_boundary &&
                    i_body_drain_done === 1'b1 &&!validation.valid &&!response_valid &&
                    !control.completion &&!control.completion_event)) begin
                    runtime_valid_next = 1'b1;
                    runtime_pending_next = 1'b0;
                    runtime_response_next = '0;
                    runtime_response_next.command = pending_command;
                    runtime_response_next.tag = pending_tag;
                    control_next.state = pending_command == tile_shell_pkg::RUNTIME_SUSPEND ?
                        tile_shell_pkg::TILE_SUSPENDED : tile_shell_pkg::TILE_READY;
                    runtime_response_next.state = control_next.state;
                end
            end

            if (fatal_live || first_error.fatal || i_body_error === 1'b1) begin
                control_next.state = tile_shell_pkg::TILE_ERROR;
                control_next.completion_event = 1'b0;
                control_next.completion = 1'b0;
            end
        end

        tile_shell_state #(.WIDTH($bits(control_t)), .PROTECTION(CONTROL_PROTECTION)) u_control (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(reset_known && control_next != control),
            .i_data(control_next),
            .o_data(control),
            .o_bad(control_bad),
            .o_corrected(control_corrected)
        );

        tile_shell_state #(
            .WIDTH($bits(validation_t)),
            .PROTECTION(CONTROL_PROTECTION)
        ) u_validation (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(reset_known && validation_next != validation),
            .i_data(validation_next),
            .o_data(validation),
            .o_bad(validation_bad),
            .o_corrected(validation_corrected)
        );

        tile_shell_state #(
            .WIDTH($bits(cfg_response_t) + 1),
            .PROTECTION(CONTROL_PROTECTION)
        ) u_cfg_response (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(reset_known),
            .i_data({response_next, cfg_response_next}),
            .o_data({response_valid, cfg_response}),
            .o_bad(response_bad),
            .o_corrected(response_corrected)
        );

        tile_shell_state #(
            .WIDTH($bits(runtime_response_t) + T + 5),
            .PROTECTION(CONTROL_PROTECTION)
        ) u_runtime_response (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(reset_known),
            .i_data({runtime_valid_next, runtime_pending_next, pending_command_next,
                pending_tag_next, runtime_response_next}),
            .o_data({runtime_valid, runtime_pending, pending_command, pending_tag,
                runtime_response}),
            .o_bad(runtime_response_bad),
            .o_corrected(runtime_response_corrected)
        );

        dff #(.WIDTH(2)) u_body_pulses (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(reset_known),
            .i_d({runtime_fire && runtime_error == 0 && i_runtime_request_command ==
                tile_shell_pkg::RUNTIME_START,
                runtime_fire && runtime_error == 0 && i_runtime_request_command ==
                    tile_shell_pkg::RUNTIME_RESUME}),
            .o_q({body_start, body_resume})
        );

        // The physical controller retains its existing command/state encodings;
        // this adapter publishes the architectural shell power states.
        wire [2:0] power_command = i_power_request_state == tile_shell_pkg::POWER_IDLE ?
            tile_power_controller_pkg::POWER_IDLE :
            i_power_request_state == tile_shell_pkg::POWER_RETENTION ?
                tile_power_controller_pkg::POWER_RETENTION :
            i_power_request_state == tile_shell_pkg::POWER_OFF ?
                tile_power_controller_pkg::POWER_OFF :
            tile_power_controller_pkg::POWER_RUN;
        logic power_pending;
        logic power_response_valid;
        logic power_response_error;
        logic [ER-1:0] power_response_code;
        logic [2:0] power_response_state;
        wire power_known = ^i_power_request_state !== 1'bx;
        wire power_legal = healthy && power_known && i_power_request_state <=
            tile_shell_pkg::POWER_OFF &&
            (i_power_request_state != tile_shell_pkg::POWER_STALLED || (|o_status_stall_reasons)) &&
            (i_power_request_state != tile_shell_pkg::POWER_RETENTION || SUPPORT_RETENTION == 1) &&
            (i_power_request_state != tile_shell_pkg::POWER_OFF || SUPPORT_POWER_OFF == 1) &&
            (i_power_request_state < tile_shell_pkg::POWER_IDLE || (safe_mutation &&
                (!control.allocated || control.state != tile_shell_pkg::TILE_ACTIVE))) &&
            (i_power_request_state != tile_shell_pkg::POWER_OFF || control.state !=
                tile_shell_pkg::TILE_SUSPENDED ||
                SUPPORT_RETENTION == 1);
        wire power_fire = i_power_request_valid === 1'b1 && o_power_request_ready;
        assign o_power_request_ready = interface_up &&!power_pending && power_known &&
            (!power_response_valid || i_power_response_ready === 1'b1) && power_command_ready &&
            !runtime_fire &&!cfg_valid;

        tile_power_controller #(
            .NUM_CLOCK_GROUPS(1),
            .NUM_WAKE_SOURCES(1),
            .NUM_STALL_REASONS(S),
            .CONTEXT_ID_WIDTH(CI),
            .IDLE_ENTRY_CYCLES(2),
            .MIN_IDLE_RESIDENCY_CYCLES(1),
            .WAKEUP_STABILIZE_CYCLES(1),
            .ISOLATION_SETUP_CYCLES(2),
            .POWER_STABLE_CYCLES(2),
            .RESET_HOLD_CYCLES(2),
            .DRAIN_TIMEOUT_CYCLES(64),
            .ACK_TIMEOUT_CYCLES(32),
            .POWER_TIMEOUT_CYCLES(64),
            .SUPPORT_RETENTION(SUPPORT_RETENTION),
            .SUPPORT_POWER_GATING(SUPPORT_RETENTION || SUPPORT_POWER_OFF)
        ) u_power (
            .i_aon_clk(i_clk),
            .i_aon_rstb(reset_b),
            .i_error_clear(clear_error),
            .i_test_mode(1'b0),
            .i_test_clock_enable(1'b0),
            .i_config_valid(!power_policy_valid),
            .o_config_ready(),
            .i_config_auto_idle_enable(1'b1),
            .i_config_wake_enable(1'b1),
            .i_config_context_check(1'b0),
            .i_config_context_id({CI{1'b0}}),
            .o_config_accepted(),
            .o_config_rejected(),
            .i_command_valid(power_fire && power_legal),
            .o_command_ready(power_command_ready),
            .i_command(power_command),
            .i_command_context_id({CI{1'b0}}),
            .o_command_accepted(),
            .o_command_rejected(power_command_rejected),
            .o_command_done(power_command_done),
            .i_tile_busy(control.state == tile_shell_pkg::TILE_ACTIVE ||
                control.state == tile_shell_pkg::TILE_SUSPENDING ||
                control.state == tile_shell_pkg::TILE_DRAINING || runtime_pending || i_body_busy
                    === 1'b1 ||
                !queues_empty || validation.valid),
            .i_tile_quiescent(safe_boundary &&!validation.valid),
            .i_drain_done(safe_boundary && i_body_drain_done === 1'b1),
            .i_stall_reason(o_status_stall_reasons),
            .i_clock_group_request(control.state == tile_shell_pkg::TILE_ACTIVE || wake_pending ||
                validation.valid),
            .i_wakeup_event(((wake_pending || validation.valid || execution_wake) &&
                power_needs_wake) ||
                (runtime_fire && runtime_error == 0 &&
                (i_runtime_request_command == tile_shell_pkg::RUNTIME_START ||
                i_runtime_request_command == tile_shell_pkg::RUNTIME_RESUME))),
            .i_power_good_async(i_body_power_good),
            .i_retention_save_ack(i_body_save_done),
            .i_retention_restore_ack(i_body_restore_done),
            .o_tile_accept_enable(power_accept),
            .o_drain_request(power_drain),
            .o_tile_clock_enable(power_clock),
            .o_clock_group_enable(),
            .o_operand_isolation_enable(),
            .o_write_disable(),
            .o_tile_reset_request(power_reset),
            .o_isolation_enable(power_isolate),
            .o_retention_save(o_body_save),
            .o_retention_restore(o_body_restore),
            .o_power_switch_enable(power_switch),
            .o_power_state(physical_power),
            .o_target_state(),
            .o_previous_stable_state(),
            .o_transition_active(power_transition),
            .o_power_good_sync(),
            .o_wakeup_pending(),
            .o_policy_valid(power_policy_valid),
            .o_active_context_id(),
            .o_idle_count(),
            .o_state_residency(),
            .o_idle(),
            .o_quiescent(),
            .o_error(power_error),
            .o_fatal_error(power_fatal),
            .o_error_code(),
            .o_event_state_change(),
            .o_event_idle_entry(),
            .o_event_wakeup(),
            .o_event_stall_entry(),
            .o_event_retention_entry(),
            .o_event_off_entry(),
            .o_event_timeout()
        );

        assign architectural_power = first_error.fatal ? tile_shell_pkg::POWER_SAFE :
            physical_power == tile_power_controller_pkg::PWR_ACTIVE ? tile_shell_pkg::POWER_ACTIVE :
            physical_power == tile_power_controller_pkg::PWR_STALLED ?
                tile_shell_pkg::POWER_STALLED :
            physical_power == tile_power_controller_pkg::PWR_IDLE ? tile_shell_pkg::POWER_IDLE :
            physical_power == tile_power_controller_pkg::PWR_RETENTION ?
                tile_shell_pkg::POWER_RETENTION :
            physical_power == tile_power_controller_pkg::PWR_OFF ? tile_shell_pkg::POWER_OFF :
            physical_power == tile_power_controller_pkg::PWR_ERROR ? tile_shell_pkg::POWER_SAFE :
                tile_shell_pkg::POWER_WAKEUP;

        // The existing controller uses an isolation setup interval. The shell
        // additionally requires the physical acknowledgement before supply loss.
        assign o_body_power_enable = power_switch || (power_isolate &&
            i_body_isolation_ack !== 1'b1);
        assign o_body_isolate = !interface_up || power_isolate || first_error.fatal || fatal_live;
        wire activity_needed = i_body_stall_reasons === '0 || input_count != 0 ||
            i_data_in_valid !== '0 || i_predicate_in_valid !== '0 ||
            i_body_data_out_valid !== '0 || i_body_predicate_out_valid !== '0 ||
            (i_body_stall_reasons[1] && i_data_out_ready !== '0);
        assign o_body_clock_enable = interface_up && (i_test_enable === 1'b1 ||
            i_scan_enable === 1'b1 || (healthy && power_clock &&
            ((control.state == tile_shell_pkg::TILE_ACTIVE && activity_needed) ||
            control.state == tile_shell_pkg::TILE_SUSPENDING ||
            control.state == tile_shell_pkg::TILE_DRAINING || wake_pending || validation.valid ||
            o_body_start || o_body_resume || o_body_save || o_body_restore ||
            (BODY_DRAIN_EVENTS == 1 && control.state == tile_shell_pkg::TILE_READY &&
                i_body_busy === 1'b1))));
        assign o_monitor_clock_enable = reset_b && control.monitor;
        assign o_power_response_valid = interface_up && power_response_valid;
        assign o_power_response_state = o_power_response_valid ? power_response_state : '0;
        assign o_power_response_error = o_power_response_valid && power_response_error;
        assign o_power_response_error_code = o_power_response_valid ? power_response_code : '0;

        always_ff @(posedge i_clk) begin
            if (!reset_b) begin
                power_pending <= 1'b0;
                power_response_valid <= 1'b0;
                power_response_error <= 1'b0;
                power_response_code <= '0;
                power_response_state <= '0;
            end else if (reset_known) begin
                if (power_response_valid && i_power_response_ready === 1'b1)
                    power_response_valid <= 1'b0;

                if (power_fire) begin
                    if (!power_legal) begin
                        power_response_valid <= 1'b1;
                        power_response_error <= 1'b1;
                        power_response_code <= ER'(tile_shell_pkg::SHELL_ERR_POWER);
                        power_response_state <= architectural_power;
                    end else power_pending <= 1'b1;
                end

                if (power_pending && (power_command_done || power_command_rejected ||
                    power_fatal)) begin
                    power_pending <= 1'b0;
                    power_response_valid <= 1'b1;
                    power_response_error <= power_command_rejected || power_error;
                    power_response_code <= power_command_rejected || power_error ?
                        ER'(tile_shell_pkg::SHELL_ERR_POWER) : '0;
                    power_response_state <= architectural_power;
                end
            end
        end

        // Debug is a separate single-response channel. Status reads remain
        // available during containment. Writes cannot bypass context validation.
        logic debug_valid;
        logic [W-1:0] debug_data;
        logic debug_error;
        logic [W-1:0] debug_read;
        wire debug_known = ^{i_debug_request_write, i_debug_request_owner_id,
            i_debug_request_privileged, i_debug_request_address,
            i_debug_request_write_data, i_debug_request_write_strobe} !== 1'bx;
        assign debug_fire = i_debug_request_valid === 1'b1 && o_debug_request_ready;
        wire debug_authorized = i_debug_request_privileged === 1'b1 ||
            (control.allocated && i_debug_request_owner_id == control.owner);
        assign debug_write_ok = debug_authorized && safe_mutation &&!first_error.fatal &&
            (i_debug_request_address == 8'h20 || i_debug_request_address == 8'h21) &&
            i_debug_request_write_strobe[0] &&!runtime_fire &&!cfg_valid;
        wire debug_bad = debug_fire && (i_debug_request_write &&!debug_write_ok ||
            !i_debug_request_write &&!(i_debug_request_address <= 8'h0c ||
                (i_debug_request_address >= 8'h40 && i_debug_request_address < 8'h50)));
        wire debug_clear = debug_fire && i_debug_request_address == 8'h20 &&
            i_debug_request_write && debug_write_ok &&
            i_debug_request_write_data[0];
        wire counter_clear = release_contexts || (debug_fire && i_debug_request_write &&
            debug_write_ok && i_debug_request_address == 8'h20 && i_debug_request_write_data[1]);
        wire [W-1:0] counter_read;
        wire [15:0] counter_events = events | (16'(detected_error != 0) << 12) |
            (16'(wake_pending) << 13) | (16'(power_transition) << 14) |
            (16'(trace_drop) << 15);
        wire [63:0] event_select;

        for (genvar e = 0; e < 16; e++) begin : g_event_select
            assign event_select[e*4+:4] = 4'(e);
        end

        // Weighted events preserve simultaneous per-port transfer counts.
        localparam int DATA_PORTS = NI > NO ? NI : NO;
        localparam int PREDICATE_PORTS = PI > PO ? PI : PO;
        localparam int EVENT_PORTS = EI > EO ? EI : EO;
        localparam int STREAM_PORTS = DATA_PORTS > PREDICATE_PORTS ? DATA_PORTS : PREDICATE_PORTS;
        localparam int MAX_PORTS = STREAM_PORTS > EVENT_PORTS ? STREAM_PORTS : EVENT_PORTS;
        localparam int INCREMENT = $clog2(MAX_PORTS + 1);
        logic [16*INCREMENT-1:0] increments;

        always @* begin
            increments = '0;

            for (int e = 6; e < 16; e++) increments[e*INCREMENT+:INCREMENT] = INCREMENT'(1);
            for (int p = 0; p < NI; p++)
                increments[0*INCREMENT+:INCREMENT] = increments[0*INCREMENT+:INCREMENT] +
                    INCREMENT'(data_in_source_fire[p]);
            for (int p = 0; p < NO; p++)
                increments[1*INCREMENT+:INCREMENT] = increments[1*INCREMENT+:INCREMENT] +
                    INCREMENT'(data_out_sink_fire[p]);
            for (int p = 0; p < PI; p++)
                increments[2*INCREMENT+:INCREMENT] = increments[2*INCREMENT+:INCREMENT] +
                    INCREMENT'(predicate_in_source_fire[p]);
            for (int p = 0; p < PO; p++)
                increments[3*INCREMENT+:INCREMENT] = increments[3*INCREMENT+:INCREMENT] +
                    INCREMENT'(predicate_out_sink_fire[p]);
            for (int p = 0; p < EI; p++)
                increments[4*INCREMENT+:INCREMENT] = increments[4*INCREMENT+:INCREMENT] +
                    INCREMENT'(event_in_source_fire[p]);
            for (int p = 0; p < EO; p++)
                increments[5*INCREMENT+:INCREMENT] = increments[5*INCREMENT+:INCREMENT] +
                    INCREMENT'(o_event_out_valid[p] && i_event_out_ready[p]);
        end

        performance_counters #(
            .COUNTER_WIDTH(W),
            .NUM_COUNTERS(16),
            .NUM_EVENTS(16),
            .INCREMENT_WIDTH(INCREMENT),
            .HAS_SNAPSHOT(0),
            .HAS_THRESHOLD(0)
        ) u_counters (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_global_enable(control.monitor),
            .i_freeze(1'b0),
            .i_counter_enable(16'hffff),
            .i_clear({16{counter_clear}}),
            .i_event_select(event_select),
            .i_event_valid(counter_events),
            .i_event_increment(increments),
            .i_threshold_enable(16'b0),
            .i_threshold_value({16*W{1'b0}}),
            .i_snapshot(1'b0),
            .i_read_enable(i_debug_request_valid === 1'b1),
            .i_read_snapshot(1'b0),
            .i_read_index(i_debug_request_address[3:0]),
            .o_read_data(counter_read),
            .o_read_overflow(),
            .o_read_valid(),
            .o_counter_overflow(),
            .o_threshold_event(),
            .o_config_error(),
            .o_snapshot_valid()
        );

        always @* begin
            debug_read = '0;

            case (i_debug_request_address)
                8'h00: debug_read = W'(o_status_execution_state);
                8'h01: debug_read = W'(control.owner);
                8'h02: debug_read = W'(control.kernel);
                8'h03: debug_read = W'(selected_context);
                8'h04: debug_read = W'(first_error.code);
                8'h05: debug_read = W'(first_error.owner);
                8'h06: debug_read = W'(first_error.kernel);
                8'h07: debug_read = W'(first_error.context_id);
                8'h08: debug_read = W'(first_error.state);
                8'h09: debug_read = W'(first_error.tag);
                8'h0a: debug_read = W'(input_count);
                8'h0b: debug_read = W'(output_count);
                8'h0c: debug_read = W'(first_error.source);
                default: if (i_debug_request_address >= 8'h40 &&
                    i_debug_request_address < 8'h50) debug_read = counter_read;
            endcase
        end

        assign o_debug_request_ready = interface_up && debug_known &&
            (!debug_valid || i_debug_response_ready === 1'b1);
        assign o_debug_response_valid = interface_up && debug_valid;
        assign o_debug_response_read_data = o_debug_response_valid ? debug_data : '0;
        assign o_debug_response_error = o_debug_response_valid && debug_error;

        always_ff @(posedge i_clk) begin
            if (!reset_b) begin
                debug_valid <= 1'b0;
                debug_data <= '0;
                debug_error <= 1'b0;
            end else if (reset_known) begin
                if (i_debug_response_ready === 1'b1) debug_valid <= 1'b0;
                if (debug_fire) begin
                    debug_valid <= 1'b1;
                    debug_data <= !i_debug_request_write &&!debug_bad ? debug_read : '0;
                    debug_error <= debug_bad;
                end
            end
        end

        assign error_event_payload = (E'(first_error.code) << (CI + K + 3)) |
            (E'(first_error.kernel) << (CI + 3)) |
            (E'(first_error.context_id) << 3) |
            (first_error.fatal ? E'(tile_shell_pkg::EVENT_FATAL) : E'(tile_shell_pkg::EVENT_ERROR));

        always_ff @(posedge i_clk) begin
            if (!reset_b) error_event_valid <= 1'b0;
            else begin
                if (interface_up && error_event_valid && i_event_out_ready[0] === 1'b1)
                    error_event_valid <= 1'b0;
                if (!first_error.valid && error_next.valid) error_event_valid <= 1'b1;
            end
        end

        if (SUPPORT_TRACE == 1) begin : g_trace
            localparam int SEQUENCE = TR - TI - O - K - CI - 4;
            wire [SEQUENCE-1:0] sequence_number;
            wire trace_event = |counter_events[14:0];

            counter #(.WIDTH(SEQUENCE)) u_sequence (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_enable(control.monitor && trace_event && reset_known),
                .i_clear(release_contexts),
                .i_load(1'b0),
                .i_direction(1'b0),
                .i_load_value({SEQUENCE{1'b0}}),
                .o_count(sequence_number),
                .o_overflow(),
                .o_underflow(),
                .o_terminal()
            );

            wire queue_ready;
            wire queue_valid;
            wire [TR-1:0] trace_data;
            wire [3:0] event_class = detected_error != 0 ? 4'd12 : runtime_fire ? 4'd10 :
                cfg_fire ? 4'd7 : wake_pending ? 4'd13 : 4'd0;
            wire [TR-1:0] trace_record = TR'({sequence_number, TILE_ID_WIDTH'(TILE_ID),
                control.owner,
                control.kernel, selected_context, event_class});

            tile_shell_queue #(.WIDTH(TR), .DEPTH(1), .PROTECTION(CONTROL_PROTECTION)) u_trace (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_flush(release_contexts),
                .i_admit(interface_up),
                .i_deliver(interface_up),
                .i_valid(trace_event && control.monitor && reset_known),
                .o_ready(queue_ready),
                .i_data(trace_record),
                .o_valid(queue_valid),
                .i_ready(i_trace_ready === 1'b1),
                .o_data(trace_data),
                .o_count(),
                .o_bad(),
                .o_corrected()
            );

            assign o_trace_valid = interface_up && queue_valid;
            assign o_trace_data = o_trace_valid ? trace_data : '0;
            assign trace_drop = trace_event && control.monitor &&!queue_ready;
        end else begin : g_no_trace
            assign o_trace_valid = 1'b0;
            assign o_trace_data = '0;
            assign trace_drop = 1'b0;
        end

        always @* begin
            detected_error = '0;
            detected_fatal = 1'b0;
            detected_source = tile_shell_pkg::ERROR_SOURCE_CONFIGURATION;
            error_tag = '0;

            if (cfg_fire && cfg_error != 0) begin
                detected_error = cfg_error;
                error_tag = cfg.tag;
                detected_fatal = cfg_error == tile_shell_pkg::SHELL_ERR_VERSION;
            end

            if (validation_result_fire && cfg_response_next.error) begin
                detected_error = cfg_response_next.code;
                error_tag = validation.tag;
            end

            if (runtime_fire && runtime_error != 0) begin
                detected_error = runtime_error;
                detected_fatal = runtime_error == tile_shell_pkg::SHELL_ERR_VERSION;
                detected_source = tile_shell_pkg::ERROR_SOURCE_RUNTIME;
                error_tag = i_runtime_request_tag;
            end

            if (metadata_fault) detected_error = ER'(tile_shell_pkg::SHELL_ERR_METADATA);

            if (schedule_fault) detected_error = ER'(tile_shell_pkg::SHELL_ERR_SCHEDULE);

            if (response_corrected || runtime_response_corrected ||
                queue_corrected || control_corrected || validation_corrected ||
                error_corrected || (|context_corrected) || (|image_corrected))
                detected_error = ER'(tile_shell_pkg::SHELL_ERR_CORRECTED);

            if (debug_bad) detected_source = tile_shell_pkg::ERROR_SOURCE_DEBUG;

            if (debug_bad) detected_error = ER'(tile_shell_pkg::SHELL_ERR_DEBUG);

            if ((i_power_request_valid === 1'b1 &&!power_known) ||
                protocol_fault || cfg_unknown || (cfg_valid &&!config_known) ||
                (i_runtime_request_valid === 1'b1 &&!runtime_known) ||
                (i_body_validate_result_valid === 1'b1 &&!validation_result_known))
                detected_error = ER'(tile_shell_pkg::SHELL_ERR_UNKNOWN);

            if (i_body_error === 1'b1) detected_source = tile_shell_pkg::ERROR_SOURCE_BODY;

            if (i_body_error === 1'b1) detected_error = i_body_error_code != 0 ?
                i_body_error_code : ER'(tile_shell_pkg::SHELL_ERR_BODY);

            if (i_body_completed === 1'b1 &&!control.body_completed &&
                (control.completion || control.completion_event || control.state ==
                    tile_shell_pkg::TILE_COMPLETED)) begin
                detected_error = ER'(tile_shell_pkg::SHELL_ERR_COMPLETION);
                detected_fatal = 1'b1;
            end

            if (fatal_live) begin
                detected_source = tile_shell_pkg::ERROR_SOURCE_INTEGRITY;
                detected_error = ER'(tile_shell_pkg::SHELL_ERR_INTEGRITY);
                detected_fatal = 1'b1;

                if (completion_fault) detected_error = ER'(tile_shell_pkg::SHELL_ERR_COMPLETION);

                if (power_fatal) detected_error = ER'(tile_shell_pkg::SHELL_ERR_POWER);

                if (i_body_fatal_error === 1'b1) detected_error = i_body_error_code != 0 ?
                    i_body_error_code : ER'(tile_shell_pkg::SHELL_ERR_BODY);

                if (i_body_power_good === 1'b0 && i_body_isolation_ack !== 1'b1)
                    detected_error = ER'(tile_shell_pkg::SHELL_ERR_POWER_LOSS);
            end

            // Source attribution follows the same priority as the diagnostic.
            if (validation_result_fire && cfg_response_next.error)
                detected_source = tile_shell_pkg::ERROR_SOURCE_BODY;

            if (metadata_fault || schedule_fault || protocol_fault || cfg_unknown)
                detected_source = tile_shell_pkg::ERROR_SOURCE_PROTOCOL;

            if (debug_bad) detected_source = tile_shell_pkg::ERROR_SOURCE_DEBUG;

            if (i_body_error === 1'b1 || i_body_fatal_error === 1'b1)
                detected_source = tile_shell_pkg::ERROR_SOURCE_BODY;

            if (power_fatal || (i_body_power_good === 1'b0 &&
                i_body_isolation_ack !== 1'b1))
                detected_source = tile_shell_pkg::ERROR_SOURCE_POWER;

            error_next = first_error;

            if ((clear_error || debug_clear) &&!first_error.fatal) error_next = '0;
            else if (detected_error != 0) begin
                error_next.fatal = first_error.fatal || detected_fatal;

                if (!first_error.valid) begin
                    error_next.valid = 1'b1;
                    error_next.code = detected_error;
                    error_next.source = detected_source;
                    error_next.owner = control.owner;
                    error_next.kernel = control.kernel;
                    error_next.context_id = selected_context;
                    error_next.state = control.state;
                    error_next.tag = error_tag;
                end
            end
        end

        tile_shell_state #(.WIDTH($bits(error_t)), .PROTECTION(CONTROL_PROTECTION)) u_error (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(error_next != first_error),
            .i_data(error_next),
            .o_data(first_error),
            .o_bad(error_bad),
            .o_corrected(error_corrected)
        );

        assign o_status_tile_id = TI'(TILE_ID);
        assign o_status_tile_class = 3'(TILE_CLASS);
        assign o_status_arch_version = AV'(1);

        function automatic logic [31:0] capability_fingerprint;
            localparam int INPUT_BITS = 32 * ((NI + 31) / 32);
            localparam int OUTPUT_BITS = 32 * ((NO + 31) / 32);
            localparam int BITS = 32 * 37 + INPUT_BITS + OUTPUT_BITS;
            logic [BITS-1:0] descriptor;
            logic [31:0] digest;
            descriptor = {OUTPUT_BITS'(OUTPUT_ELASTIC_MASK), INPUT_BITS'(INPUT_ELASTIC_MASK),
                32'(ASYNC_RESET),
                32'(CONTROL_PROTECTION),
                32'(CONTEXT_PROTECTION),
                32'(SUPPORT_POWER_OFF),
                32'(SUPPORT_RETENTION),
                32'(SUPPORT_TRACE),
                32'(TRACE_WIDTH),
                32'(ERROR_CODE_WIDTH),
                32'(STALL_REASON_WIDTH),
                32'(RUNTIME_TAG_WIDTH),
                32'(CONTEXT_VERSION_WIDTH),
                32'(KERNEL_ID_WIDTH),
                32'(OWNER_ID_WIDTH),
                32'(CONFIG_QUEUE_DEPTH),
                32'(CONFIG_ASYNC),
                32'(SUPPORT_CONTEXT_CHECKSUM),
                32'(CONTEXT_CHECKSUM_WIDTH),
                32'(CONFIG_WORD_COUNT),
                32'(CONFIG_DATA_WIDTH),
                32'(CONTEXT_DEPTH),
                32'(EVENT_OUTPUT_PORTS),
                32'(EVENT_INPUT_PORTS),
                32'(EVENT_WIDTH),
                32'(PREDICATE_OUTPUT_PORTS),
                32'(PREDICATE_INPUT_PORTS),
                32'(PREDICATE_METADATA_WIDTH),
                32'(PREDICATE_WIDTH),
                32'(OUTPUT_BUFFER_DEPTH),
                32'(INPUT_BUFFER_DEPTH),
                32'(DATA_OUTPUT_PORTS),
                32'(DATA_INPUT_PORTS),
                32'(DATA_METADATA_WIDTH),
                32'(DATA_WIDTH),
                32'(CAPABILITY_ID_WIDTH),
                32'(ARCH_VERSION_WIDTH),
                32'(TILE_CLASS),
                32'(TILE_ID_WIDTH)};
            digest = 32'd2166136261;

            for (int b = 0; b < BITS / 8; b++)
                digest = (digest ^ {24'b0, descriptor[b*8+:8]}) * 32'd16777619;

            return digest;
        endfunction

        localparam logic [31:0] CAPABILITY = capability_fingerprint();
        assign o_status_capability_id = CP'(CAPABILITY);

        // Elastic ready indicates capacity, not a demand for an operand. Only
        // scheduled ready is a reservation; elastic input stalls come from the
        // body's explicit requirement bitmap. Stall decoding never depends on
        // the physical ACTIVE/STALLED state, preventing power-state oscillation.
        wire reserved_missing = |(~INPUT_ELASTIC_MASK & i_body_data_in_ready &
            ~(i_data_in_valid | o_body_data_in_valid));
        wire output_blocked = |(o_data_out_valid & ~i_data_out_ready) ||
            |(o_predicate_out_valid & ~i_predicate_out_ready) ||
            |(o_event_out_valid & ~i_event_out_ready) ||
            (BO == 0 && (|(i_body_data_out_valid & ~i_data_out_ready)));
        wire [S-1:0] shell_stalls = S'(reserved_missing) | (S'(output_blocked) << 1);
        assign o_status_stall_reasons = control.state == tile_shell_pkg::TILE_ACTIVE ?
            i_body_stall_reasons | shell_stalls : '0;
        assign o_status_execution_state = !reset_b ? tile_shell_pkg::TILE_UNALLOCATED :
            first_error.fatal || fatal_live ?
            tile_shell_pkg::TILE_ERROR :
            power_transition && reset_b ? tile_shell_pkg::TILE_POWER_TRANSITION :
            control.state == tile_shell_pkg::TILE_ACTIVE && o_status_stall_reasons[1] ?
                tile_shell_pkg::TILE_OUTPUT_STALL :
            control.state == tile_shell_pkg::TILE_ACTIVE && o_status_stall_reasons[2] ?
                tile_shell_pkg::TILE_MEMORY_STALL :
            control.state == tile_shell_pkg::TILE_ACTIVE && o_status_stall_reasons[3] ?
                tile_shell_pkg::TILE_SYNC_STALL :
            control.state == tile_shell_pkg::TILE_ACTIVE && o_status_stall_reasons[0] ?
                tile_shell_pkg::TILE_INPUT_STALL :
            control.state;
        assign o_status_power_state = reset_b ? architectural_power : tile_shell_pkg::POWER_SAFE;
        assign o_status_active_context = reset_b && control.active ? selected_context : '0;
        assign o_status_context_version = reset_b && control.active ? versions[selected_context] :
            '0;
        assign o_status_owner_id = reset_b && control.allocated ? control.owner : '0;
        assign o_status_kernel_id = reset_b && control.allocated ? control.kernel : '0;

        for (genvar c = 0; c < C; c++) begin : g_valid_status
            assign o_status_context_valid[c] = reset_b && validated[c] && committed[c];
        end

        assign o_status_error = reset_b && (first_error.valid || fatal_live);
        assign o_status_fatal_error = reset_b && (first_error.fatal || fatal_live);
        assign o_status_error_code = !reset_b ? '0 : first_error.valid ? first_error.code :
            reset_b && fatal_live ? detected_error : '0;
        assign o_status_busy = reset_b && (!safe_boundary || validation.valid || runtime_pending ||
            response_valid || runtime_valid || power_pending || power_response_valid ||
            debug_valid || o_trace_valid || power_transition || control.completion ||
            control.completion_event || control.state == tile_shell_pkg::TILE_ACTIVE ||
            control.state == tile_shell_pkg::TILE_SUSPENDING || control.state ==
                tile_shell_pkg::TILE_DRAINING);
        assign o_status_idle = reset_b &&!o_status_busy;
        assign o_status_quiescent = o_status_idle && i_body_safe_point === 1'b1 &&
            i_data_in_valid === '0 && i_body_data_out_valid === '0 &&
            i_predicate_in_valid === '0 && i_body_predicate_out_valid === '0 &&
            i_event_in_valid === '0 && i_body_event_out_valid === '0 &&
            i_runtime_request_valid === 1'b0 &&!cfg_valid && i_debug_request_valid === 1'b0 &&
            i_power_request_valid === 1'b0 &&!queue_corrected &&!control_corrected;
    end
endmodule
`default_nettype wire
