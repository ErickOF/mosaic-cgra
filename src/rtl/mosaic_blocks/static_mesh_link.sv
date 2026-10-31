`timescale 1ns / 1ps
`default_nettype none
// A forward-bypassing skid slot cuts ready between adjacent node switches.
// Flush drains the slot synchronously; it never gates or synthesizes a reset.
module static_mesh_link #(
    parameter int WIDTH = 96,
    parameter int PARITY = 0,
    parameter int PROTECTION = 0,
    parameter int ASYNC_RESET = 0
) (
    input wire i_clk,
    input wire i_reset_n,
    input wire i_flush,
    input wire i_run,
    input wire i_fault,
    input wire i_valid,
    output wire o_ready,
    input wire [WIDTH-1:0] i_data,
    output wire o_valid,
    input wire i_ready,
    output wire [WIDTH-1:0] o_data,
    output wire o_idle,
    output wire o_transfer,
    output wire o_parity_bad,
    output wire o_bad,
    output wire [WIDTH-1:0] o_observed_data
);
    wire raw_ready;
    wire raw_valid;
    wire [WIDTH:0] received_packet;
    wire parity_bad = PARITY && raw_valid && (^received_packet !== 1'b0);
    wire admit = i_run &&!i_fault &&!i_flush;
    wire deliver = i_flush || (admit && i_ready &&!parity_bad);
    wire full;
    wire witness_bad;
    wire next_full = !i_flush && (full ? !deliver :
        (admit && i_valid &&!deliver));
    assign o_ready = admit && raw_ready;
    assign o_valid = admit && raw_valid &&!parity_bad;
    // Observation does not acknowledge or release a quarantined beat.
    assign o_observed_data = received_packet[0+:WIDTH];
    assign o_data = o_valid ? received_packet[0+:WIDTH] : '0;
    assign o_transfer = i_valid && o_ready;
    assign o_idle = raw_ready === 1'b1;
    assign o_parity_bad = i_reset_n === 1'b1 &&!i_flush && parity_bad;
    assign o_bad = witness_bad || (raw_ready !== !full);

    skid_buffer #(.DATA_WIDTH(WIDTH + 1), .ASYNC_RESET(ASYNC_RESET)) u_skid (
        .i_clk(i_clk),
        .i_rstb(i_reset_n),
        .i_valid(admit && i_valid),
        .o_ready(raw_ready),
        .i_data({PARITY ? ^i_data : 1'b0, i_data}),
        .o_valid(raw_valid),
        .i_ready(deliver),
        .o_data(received_packet)
    );

    banked_scratchpad_state #(
        .WIDTH(1),
        .PROTECTION(PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_witness (
        .i_clk(i_clk),
        .i_reset_n(i_reset_n),
        .i_data(next_full),
        .o_data(full),
        .o_bad(witness_bad)
    );
endmodule
`default_nettype wire
