`timescale 1ns / 1ps
`default_nettype none

// Simulation-only controls exercise enable, clear, saturation and disabled copies.
module scratchpad_controller_instrumentation #(
    parameter int C = 4,
    parameter int B = 8,
    parameter bit ASYNC_RESET = 0,
    localparam int COUNT = C * 15 + B * 10 + C * B + 2
) (
    input logic i_clk,
    input logic i_rstb,
    input logic [COUNT*8-1:0] i_increments,
    input logic [C*8-1:0] i_occupancy
);
    logic test_enable = 1'b1;
    logic test_clear = 1'b0;
    wire [COUNT*8-1:0] counts;
    wire [C*8-1:0] peaks;
    wire [COUNT*8-1:0] disabled_counts;
    wire [C*8-1:0] disabled_peaks;
    scratchpad_controller_counters #(.NUM_CLIENTS(C), .NUM_BANKS(B), .WIDTH(8),
        .ASYNC_RESET(ASYNC_RESET)) u_enabled (
        .i_clk(i_clk), .i_rstb(i_rstb), .i_enable(test_enable), .i_clear(test_clear),
        .i_increments(i_increments), .i_occupancy(i_occupancy),
        .o_counts(counts), .o_maximum_occupancy(peaks)
    );
    scratchpad_controller_counters #(.NUM_CLIENTS(C), .NUM_BANKS(B), .WIDTH(8),
        .ASYNC_RESET(ASYNC_RESET)) u_disabled (
        .i_clk(i_clk), .i_rstb(i_rstb), .i_enable(1'b0), .i_clear(1'b1),
        .i_increments(i_increments), .i_occupancy(i_occupancy),
        .o_counts(disabled_counts), .o_maximum_occupancy(disabled_peaks)
    );
endmodule
`default_nettype wire
