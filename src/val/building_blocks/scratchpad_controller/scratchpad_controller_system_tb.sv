`timescale 1ns / 1ps
`default_nettype none

// Verification-only subsystem: the released controller and independently
// parameterized real banks. Gates model interface backpressure, never clocks.
module scratchpad_controller_system_tb #(
    parameter PROTECTION_MODE = 0,
    parameter DATA_WIDTH = 128,
    parameter NUM_BANKS = 8,
    parameter BANK_DEPTH_WORDS = 1024,
    parameter NUM_CLIENTS = 4,
    parameter CLIENT_TAG_WIDTH = 8,
    parameter MAX_OUTSTANDING_PER_CLIENT = 8,
    parameter INTERLEAVE_BYTES = 16,
    parameter MAP_MODE = 0,
    parameter ENFORCE_PERMISSIONS = 1,
    parameter DEFAULT_ALLOW = 0,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((DATA_WIDTH >= 8) === 1'b1) && (^DATA_WIDTH !== 1'bx) &&
        ((DATA_WIDTH % 8 == 0) === 1'b1) &&
        ((((DATA_WIDTH / 8) & ((DATA_WIDTH / 8) - 1)) == 0) === 1'b1) &&
        ((NUM_BANKS > 0) === 1'b1) && (^NUM_BANKS !== 1'bx) &&
        ((BANK_DEPTH_WORDS > 0) === 1'b1) && (^BANK_DEPTH_WORDS !== 1'bx) &&
        ((NUM_CLIENTS > 0) === 1'b1) && (^NUM_CLIENTS !== 1'bx) &&
        ((CLIENT_TAG_WIDTH > 0) === 1'b1) && (^CLIENT_TAG_WIDTH !== 1'bx) &&
        ((MAX_OUTSTANDING_PER_CLIENT > 0) === 1'b1) &&
        (^MAX_OUTSTANDING_PER_CLIENT !== 1'bx) &&
        ((INTERLEAVE_BYTES > 0) === 1'b1) && (^INTERLEAVE_BYTES !== 1'bx) &&
        (((INTERLEAVE_BYTES & (INTERLEAVE_BYTES - 1)) == 0) === 1'b1) &&
        ((INTERLEAVE_BYTES >= DATA_WIDTH / 8) === 1'b1) &&
        ((128'(INTERLEAVE_BYTES) <= 128'(BANK_DEPTH_WORDS) * 128'(DATA_WIDTH / 8))
            === 1'b1) &&
        ((128'(BANK_DEPTH_WORDS) * 128'(DATA_WIDTH / 8) %
            128'(INTERLEAVE_BYTES > 0 ? INTERLEAVE_BYTES : 1) == 0) === 1'b1) &&
        ((MAP_MODE === 0) || (MAP_MODE === 1)) &&
        ((MAP_MODE == 0 || (NUM_BANKS & (NUM_BANKS - 1)) == 0) === 1'b1) &&
        ((ENFORCE_PERMISSIONS === 0) || (ENFORCE_PERMISSIONS === 1)) &&
        ((DEFAULT_ALLOW === 0) || (DEFAULT_ALLOW === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((128'(NUM_BANKS) * 128'(BANK_DEPTH_WORDS) * 128'(DATA_WIDTH) <
            128'd2147483647) === 1'b1) &&
        ((128'(NUM_CLIENTS) * 128'(MAX_OUTSTANDING_PER_CLIENT) *
            (128'(DATA_WIDTH) + 128'(CLIENT_TAG_WIDTH) + 128'(NUM_BANKS) + 128) <
            128'd2147483647) === 1'b1) &&
        ((128'(NUM_CLIENTS) * 128'(NUM_BANKS) * 128'(DATA_WIDTH) <
            128'd2147483647) === 1'b1),
    localparam int D = PARAMETERS_VALID ? DATA_WIDTH : 8,
    localparam int B = PARAMETERS_VALID ? NUM_BANKS : 1,
    localparam int C = PARAMETERS_VALID ? NUM_CLIENTS : 1,
    localparam int N = PARAMETERS_VALID ? MAX_OUTSTANDING_PER_CLIENT : 1,
    localparam int T = PARAMETERS_VALID ? CLIENT_TAG_WIDTH : 1,
    localparam int WORDS = PARAMETERS_VALID ? BANK_DEPTH_WORDS : 1,
    localparam int STRIPE = PARAMETERS_VALID ? INTERLEAVE_BYTES : 1,
    localparam int DATA_BYTES = D / 8,
    localparam logic [63:0] BANK_CAPACITY_BYTES = 64'(WORDS) * 64'(DATA_BYTES),
    localparam logic [63:0] TOTAL_CAPACITY_BYTES = 64'(B) * BANK_CAPACITY_BYTES,
    localparam int GLOBAL_ADDR_WIDTH = TOTAL_CAPACITY_BYTES > 1 ?
        $clog2(TOTAL_CAPACITY_BYTES) : 1,
    localparam int BANK_ADDR_WIDTH = BANK_CAPACITY_BYTES > 1 ? $clog2(BANK_CAPACITY_BYTES) : 1,
    localparam int SIZE_WIDTH = DATA_BYTES > 1 ? $clog2($clog2(DATA_BYTES) + 1) : 1,
    localparam int CLIENT_INDEX_WIDTH = C > 1 ? $clog2(C) : 1,
    localparam int BANK_INDEX_WIDTH = B > 1 ? $clog2(B) : 1,
    localparam int CLIENT_SLOT_WIDTH = N > 1 ? $clog2(N) : 1,
    localparam int BANK_TAG_WIDTH = CLIENT_INDEX_WIDTH + CLIENT_SLOT_WIDTH,
    localparam int CLIENT_OCCUPANCY_WIDTH = $clog2(64'(N) + 1),
    localparam int PERMISSION_WIDTH = C * B
) (
    input logic  i_clk,
    input logic  i_rstb,
    input logic  i_flush,
    input logic  i_error_clear,
    input logic  i_perm_valid,
    output logic  o_perm_ready,
    input logic [PERMISSION_WIDTH-1:0] i_read_permission,
    input logic [PERMISSION_WIDTH-1:0] i_write_permission,
    output logic  o_permission_updated,
    input logic [C-1:0] i_client_req_valid,
    input logic [C-1:0] i_client_req_write,
    input logic [C*GLOBAL_ADDR_WIDTH-1:0] i_client_req_address,
    input logic [C*SIZE_WIDTH-1:0] i_client_req_size_log2,
    input logic [C*D-1:0] i_client_req_wdata,
    input logic [C*DATA_BYTES-1:0] i_client_req_wstrobe,
    input logic [C*T-1:0] i_client_req_tag,
    output logic [C-1:0] o_client_req_ready,
    output logic [C-1:0] o_client_rsp_valid,
    output logic [C-1:0] o_client_rsp_write,
    output logic [C*D-1:0] o_client_rsp_rdata,
    output logic [C*T-1:0] o_client_rsp_tag,
    output logic [C-1:0] o_client_rsp_error,
    output logic [C*scratchpad_controller_pkg::MEM_ERROR_WIDTH-1:0] o_client_rsp_error_code,
    output logic [C-1:0] o_client_rsp_corrected,
    output logic [C-1:0] o_client_rsp_uncorrectable,
    input logic [C-1:0] i_client_rsp_ready,
    output logic  o_idle,
    output logic  o_busy,
    output logic  o_flushing,
    output logic  o_flush_completed,
    output logic [C*CLIENT_OCCUPANCY_WIDTH-1:0] o_client_outstanding,
    output logic [C-1:0] o_request_accepted,
    output logic [C-1:0] o_response_accepted,
    output logic [C-1:0] o_permission_denied,
    output logic  o_error,
    output logic [scratchpad_controller_pkg::CTRL_ERROR_WIDTH-1:0] o_error_code,
    input logic [B-1:0] i_bank_request_enable,
    input logic [B-1:0] i_bank_response_enable
);
    wire [B-1:0] o_bank_req_valid;
    wire [B-1:0] o_bank_req_write;
    wire [B*BANK_ADDR_WIDTH-1:0] o_bank_req_address;
    wire [B*SIZE_WIDTH-1:0] o_bank_req_size_log2;
    wire [B*D-1:0] o_bank_req_wdata;
    wire [B*DATA_BYTES-1:0] o_bank_req_wstrobe;
    wire [B*BANK_TAG_WIDTH-1:0] o_bank_req_tag;
    wire [B-1:0] i_bank_req_ready;
    wire [B-1:0] i_bank_rsp_valid;
    wire [B-1:0] i_bank_rsp_write;
    wire [B*D-1:0] i_bank_rsp_rdata;
    wire [B*BANK_TAG_WIDTH-1:0] i_bank_rsp_tag;
    wire [B-1:0] i_bank_rsp_error;
    wire [B*scratchpad_bank_pkg::BANK_ERROR_WIDTH-1:0] i_bank_rsp_error_code;
    wire [B-1:0] i_bank_rsp_corrected;
    wire [B-1:0] i_bank_rsp_uncorrectable;
    wire [B-1:0] o_bank_rsp_ready;
    wire [B-1:0] o_bank_flush;
    wire [B-1:0] i_bank_flush_completed;
    wire [B-1:0] i_bank_idle;
    wire [B-1:0] o_bank_conflict;
    wire [B-1:0] physical_request_ready;
    wire [B-1:0] physical_response_valid;
    assign i_bank_req_ready = physical_request_ready & i_bank_request_enable;
    assign i_bank_rsp_valid = physical_response_valid & i_bank_response_enable;
    scratchpad_controller #(
        .DATA_WIDTH(DATA_WIDTH),
        .NUM_BANKS(NUM_BANKS),
        .BANK_DEPTH_WORDS(BANK_DEPTH_WORDS),
        .NUM_CLIENTS(NUM_CLIENTS),
        .CLIENT_TAG_WIDTH(CLIENT_TAG_WIDTH),
        .MAX_OUTSTANDING_PER_CLIENT(MAX_OUTSTANDING_PER_CLIENT),
        .INTERLEAVE_BYTES(INTERLEAVE_BYTES),
        .MAP_MODE(MAP_MODE),
        .ENFORCE_PERMISSIONS(ENFORCE_PERMISSIONS),
        .DEFAULT_ALLOW(DEFAULT_ALLOW),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_controller (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_flush(i_flush),
        .i_error_clear(i_error_clear),
        .i_perm_valid(i_perm_valid),
        .o_perm_ready(o_perm_ready),
        .i_read_permission(i_read_permission),
        .i_write_permission(i_write_permission),
        .o_permission_updated(o_permission_updated),
        .i_client_req_valid(i_client_req_valid),
        .i_client_req_write(i_client_req_write),
        .i_client_req_address(i_client_req_address),
        .i_client_req_size_log2(i_client_req_size_log2),
        .i_client_req_wdata(i_client_req_wdata),
        .i_client_req_wstrobe(i_client_req_wstrobe),
        .i_client_req_tag(i_client_req_tag),
        .o_client_req_ready(o_client_req_ready),
        .o_client_rsp_valid(o_client_rsp_valid),
        .o_client_rsp_write(o_client_rsp_write),
        .o_client_rsp_rdata(o_client_rsp_rdata),
        .o_client_rsp_tag(o_client_rsp_tag),
        .o_client_rsp_error(o_client_rsp_error),
        .o_client_rsp_error_code(o_client_rsp_error_code),
        .o_client_rsp_corrected(o_client_rsp_corrected),
        .o_client_rsp_uncorrectable(o_client_rsp_uncorrectable),
        .i_client_rsp_ready(i_client_rsp_ready),
        .o_bank_req_valid(o_bank_req_valid),
        .o_bank_req_write(o_bank_req_write),
        .o_bank_req_address(o_bank_req_address),
        .o_bank_req_size_log2(o_bank_req_size_log2),
        .o_bank_req_wdata(o_bank_req_wdata),
        .o_bank_req_wstrobe(o_bank_req_wstrobe),
        .o_bank_req_tag(o_bank_req_tag),
        .i_bank_req_ready(i_bank_req_ready),
        .i_bank_rsp_valid(i_bank_rsp_valid),
        .i_bank_rsp_write(i_bank_rsp_write),
        .i_bank_rsp_rdata(i_bank_rsp_rdata),
        .i_bank_rsp_tag(i_bank_rsp_tag),
        .i_bank_rsp_error(i_bank_rsp_error),
        .i_bank_rsp_error_code(i_bank_rsp_error_code),
        .i_bank_rsp_corrected(i_bank_rsp_corrected),
        .i_bank_rsp_uncorrectable(i_bank_rsp_uncorrectable),
        .o_bank_rsp_ready(o_bank_rsp_ready),
        .o_bank_flush(o_bank_flush),
        .i_bank_flush_completed(i_bank_flush_completed),
        .i_bank_idle(i_bank_idle),
        .o_idle(o_idle),
        .o_busy(o_busy),
        .o_flushing(o_flushing),
        .o_flush_completed(o_flush_completed),
        .o_client_outstanding(o_client_outstanding),
        .o_bank_conflict(o_bank_conflict),
        .o_request_accepted(o_request_accepted),
        .o_response_accepted(o_response_accepted),
        .o_permission_denied(o_permission_denied),
        .o_error(o_error),
        .o_error_code(o_error_code)
    );
    for (genvar b = 0; b < B; b++) begin : g_bank
        scratchpad_bank #(.DATA_WIDTH(D), .DEPTH_WORDS(WORDS), .TAG_WIDTH(BANK_TAG_WIDTH),
            .MAX_OUTSTANDING(3), .BACKEND_READ_LATENCY(2), .PROTECTION_MODE(PROTECTION_MODE),
            .ASYNC_RESET(ASYNC_RESET)) u_bank (
            .i_clk(i_clk), .i_rstb(i_rstb), .i_flush(o_bank_flush[b]),
            .i_error_clear(i_error_clear),
            .i_req_valid(o_bank_req_valid[b] && i_bank_request_enable[b]),
            .o_req_ready(physical_request_ready[b]),
            .i_req_write(o_bank_req_write[b]),
            .i_req_address(o_bank_req_address[b*BANK_ADDR_WIDTH+:BANK_ADDR_WIDTH]),
            .i_req_size_log2(o_bank_req_size_log2[b*SIZE_WIDTH+:SIZE_WIDTH]),
            .i_req_wdata(o_bank_req_wdata[b*D+:D]),
            .i_req_wstrobe(o_bank_req_wstrobe[b*DATA_BYTES+:DATA_BYTES]),
            .i_req_tag(o_bank_req_tag[b*BANK_TAG_WIDTH+:BANK_TAG_WIDTH]),
            .o_rsp_valid(physical_response_valid[b]),
            .i_rsp_ready(o_bank_rsp_ready[b] && i_bank_response_enable[b]),
            .o_rsp_write(i_bank_rsp_write[b]), .o_rsp_rdata(i_bank_rsp_rdata[b*D+:D]),
            .o_rsp_tag(i_bank_rsp_tag[b*BANK_TAG_WIDTH+:BANK_TAG_WIDTH]),
            .o_rsp_error(i_bank_rsp_error[b]),
            .o_rsp_error_code(i_bank_rsp_error_code[b*4+:4]),
            .o_rsp_corrected(i_bank_rsp_corrected[b]),
            .o_rsp_uncorrectable(i_bank_rsp_uncorrectable[b]), .o_idle(i_bank_idle[b]),
            .o_flush_completed(i_bank_flush_completed[b]), .o_busy(), .o_outstanding(),
            .o_request_accepted(), .o_read_accepted(), .o_write_accepted(),
            .o_response_accepted(), .o_corrected_event(), .o_uncorrectable_event(),
            .o_scrub_completed(), .o_error(), .o_error_code()
        );
    end
endmodule
`default_nettype wire
