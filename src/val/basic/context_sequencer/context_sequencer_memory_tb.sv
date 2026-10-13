`timescale 1ns / 1ps

// Single-clock selection of committed contexts. Execution acceptance and safe
// points are supplied by the tile; this controller neither executes nor drains it.
module context_sequencer_memory_tb #(
    // Untyped parameters retain negative, oversized, and X/Z caller values.
    parameter CONTEXT_DEPTH = 4,
    parameter LOOP_COUNT_WIDTH = 16,
    parameter HAS_LOOP = 1,
    parameter HAS_SUSPEND = 1,
    parameter HAS_EXTERNAL_SWITCH = 1,
    parameter ASYNC_RESET = 0,
    localparam int unsigned STORAGE_DEPTH = CONTEXT_DEPTH >= 1 && (^CONTEXT_DEPTH !== 1'bx) ? CONTEXT_DEPTH : 1,
    localparam int unsigned COUNT_WIDTH = LOOP_COUNT_WIDTH >= 1 && (^LOOP_COUNT_WIDTH !== 1'bx) ? LOOP_COUNT_WIDTH : 1,
    localparam int unsigned ADDR_WIDTH = STORAGE_DEPTH > 1 ? $clog2(STORAGE_DEPTH) : 1,
    localparam int unsigned TRANSITION_MODE_WIDTH = context_sequencer_pkg::TRANSITION_MODE_WIDTH,
    localparam int unsigned ERROR_CODE_WIDTH = context_sequencer_pkg::ERROR_CODE_WIDTH,
    localparam int unsigned INTERFACE_VERSION = context_sequencer_pkg::INTERFACE_VERSION
) (
    input  logic i_clk,
    input  logic i_rstb,
    input  logic i_start_enable,
    input  logic [ADDR_WIDTH-1:0] i_start_context,
    input  logic i_stop_request,
    input  logic i_suspend_request,
    input  logic i_resume_request,
    input  logic i_switch_request,
    input  logic [ADDR_WIDTH-1:0] i_switch_context,
    input  logic i_error_clear,
    input  logic i_step_accepted,
    input  logic i_safe_point,
    input  logic [TRANSITION_MODE_WIDTH-1:0] i_transition_mode,
    input  logic [ADDR_WIDTH-1:0] i_transition_target,
    input  logic [COUNT_WIDTH-1:0] i_loop_count,
    output logic o_active_read_enable,
    output logic [ADDR_WIDTH-1:0] o_active_context,
    output logic o_candidate_read_enable,
    output logic [ADDR_WIDTH-1:0] o_candidate_context,
    output logic o_context_enable,
    output logic o_quiesce_request,
    output logic o_idle,
    output logic o_active,
    output logic o_context_wait,
    output logic o_stop_pending,
    output logic o_suspend_pending,
    output logic o_suspended,
    output logic o_switch_pending,
    output logic o_completed,
    output logic o_error,
    output logic [ERROR_CODE_WIDTH-1:0] o_error_code,
    output logic o_context_activated,
    output logic o_context_changed,
    output logic o_sequence_completed,
    output logic o_loop_active,
    output logic [ADDR_WIDTH-1:0] o_loop_owner,
    output logic [COUNT_WIDTH-1:0] o_loop_remaining,
    input logic i_memory_write_enable,
    input logic [1:0] i_memory_write_mask,
    input logic [ADDR_WIDTH-1:0] i_memory_write_address,
    input logic [7:0] i_memory_write_data,
    input logic i_memory_commit_enable,
    input logic [ADDR_WIDTH-1:0] i_memory_commit_address,
    input logic i_memory_invalidate_enable,
    input logic [ADDR_WIDTH-1:0] i_memory_invalidate_address,
    output logic [7:0] o_memory_active_data,
    output logic [7:0] o_memory_candidate_data
);
    // Two execution ports share real committed storage; raw access is disabled.
    wire i_active_context_valid, i_candidate_context_valid;
    wire [1:0] memory_valid;
    wire [15:0] memory_data;
    if (INTERFACE_VERSION != 1) begin : g_interface_version
        context_sequencer_memory_interface_must_be_v1 invalid_interface ();
    end
    assign i_active_context_valid = memory_valid[0];
    assign i_candidate_context_valid = memory_valid[1];
    assign o_memory_active_data = memory_data[7:0];
    assign o_memory_candidate_data = memory_data[15:8];
    context_memory #(.CONTEXT_WIDTH(8), .CONTEXT_DEPTH(CONTEXT_DEPTH),
                     .WRITE_SLICE_WIDTH(4), .NUM_READ_PORTS(2),
                     .HAS_RAW_READBACK(0), .ASYNC_RESET(ASYNC_RESET)) memory (
        .i_clk(i_clk), .i_rstb(i_rstb),
        .i_read_enable({o_candidate_read_enable, o_active_read_enable}),
        .i_read_raw(2'b00), .i_read_address({o_candidate_context, o_active_context}),
        .o_read_data(memory_data), .o_read_valid(memory_valid),
        .i_write_enable(i_memory_write_enable), .i_write_mask(i_memory_write_mask),
        .i_write_address(i_memory_write_address), .i_write_data(i_memory_write_data),
        .i_commit_enable(i_memory_commit_enable), .i_commit_address(i_memory_commit_address),
        .i_invalidate_enable(i_memory_invalidate_enable), .i_invalidate_address(i_memory_invalidate_address)
    );
    context_sequencer #(
        .CONTEXT_DEPTH(CONTEXT_DEPTH), .LOOP_COUNT_WIDTH(LOOP_COUNT_WIDTH),
        .HAS_LOOP(HAS_LOOP), .HAS_SUSPEND(HAS_SUSPEND),
        .HAS_EXTERNAL_SWITCH(HAS_EXTERNAL_SWITCH), .ASYNC_RESET(ASYNC_RESET)
    ) dut (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_start_enable(i_start_enable),
        .i_stop_request(i_stop_request),
        .i_suspend_request(i_suspend_request),
        .i_resume_request(i_resume_request),
        .i_switch_request(i_switch_request),
        .i_error_clear(i_error_clear),
        .i_start_context(i_start_context),
        .i_switch_context(i_switch_context),
        .i_step_accepted(i_step_accepted),
        .i_safe_point(i_safe_point),
        .i_transition_mode(i_transition_mode),
        .i_transition_target(i_transition_target),
        .i_loop_count(i_loop_count),
        .i_active_context_valid(i_active_context_valid),
        .i_candidate_context_valid(i_candidate_context_valid),
        .o_active_read_enable(o_active_read_enable),
        .o_active_context(o_active_context),
        .o_candidate_read_enable(o_candidate_read_enable),
        .o_candidate_context(o_candidate_context),
        .o_context_enable(o_context_enable),
        .o_quiesce_request(o_quiesce_request),
        .o_idle(o_idle),
        .o_active(o_active),
        .o_context_wait(o_context_wait),
        .o_stop_pending(o_stop_pending),
        .o_suspend_pending(o_suspend_pending),
        .o_suspended(o_suspended),
        .o_switch_pending(o_switch_pending),
        .o_completed(o_completed),
        .o_error(o_error),
        .o_error_code(o_error_code),
        .o_context_activated(o_context_activated),
        .o_context_changed(o_context_changed),
        .o_sequence_completed(o_sequence_completed),
        .o_loop_active(o_loop_active),
        .o_loop_owner(o_loop_owner),
        .o_loop_remaining(o_loop_remaining)
    );
endmodule
