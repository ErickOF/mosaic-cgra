`timescale 1ns / 1ps

// Real requester payload mux and registered consumer: ID and payload must refer
// to the same accepted pre-edge grant, including pending and atomic service.
module round_robin_arbiter_payload_tb #(
    parameter NUM_REQUESTERS = 4,
    parameter INITIAL_PRIORITY = 0,
    parameter HAS_LOCK = 1,
    parameter ASYNC_RESET = 0,
    localparam INDEX_WIDTH = NUM_REQUESTERS > 1 ? $clog2(NUM_REQUESTERS) : 1
) (
    input logic i_clk, i_rstb, i_accept, i_flush,
    input logic [NUM_REQUESTERS-1:0] i_request, i_eligible, i_lock,
    input logic [NUM_REQUESTERS*32-1:0] i_payload,
    output wire o_grant_valid, o_grant_lock, o_grant_accepted, o_contended,
    output wire o_pending, o_locked, o_protocol_error,
    output wire [NUM_REQUESTERS-1:0] o_grant_onehot,
    output wire [INDEX_WIDTH-1:0] o_grant_index, o_lock_owner,
    output wire [31:0] o_payload,
    output wire o_received_valid,
    output wire [INDEX_WIDTH-1:0] o_received_index,
    output wire [31:0] o_received_payload
);
    wire [31:0] selected_payload;
    wire unused_select_valid, unused_receiver_ready;
    round_robin_arbiter #(
        .NUM_REQUESTERS(NUM_REQUESTERS), .INITIAL_PRIORITY(INITIAL_PRIORITY),
        .HAS_LOCK(HAS_LOCK), .ASYNC_RESET(ASYNC_RESET)
    ) u_arbiter (.*);
    mux #(.NUM_INPUTS(NUM_REQUESTERS), .DATA_WIDTH(32)) u_payload (
        .i_data(i_payload), .i_select(o_grant_index), .o_data(selected_payload), .o_select_valid(unused_select_valid)
    );
    assign o_payload = o_grant_valid ? selected_payload : 32'b0;
    register_slice #(.DATA_WIDTH(32+INDEX_WIDTH), .ASYNC_RESET(ASYNC_RESET)) u_receiver (
        .i_clk(i_clk), .i_rstb(i_rstb), .i_valid(o_grant_accepted),
        .o_ready(unused_receiver_ready), .i_data({o_grant_index, o_payload}),
        .o_valid(o_received_valid), .i_ready(1'b1), .o_data({o_received_index, o_received_payload})
    );
endmodule
