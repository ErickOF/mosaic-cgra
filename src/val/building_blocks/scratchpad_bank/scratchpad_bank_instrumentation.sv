`timescale 1ns / 1ps

// Verification-only small counters make saturation and disabled holds observable
// within Python simulation. No instrumented logic is required in the baseline.
module scratchpad_bank_instrumentation #(
    parameter int O = 4,
    parameter int ASYNC_RESET = 0
) (
    input logic i_clk,
    input logic i_rstb,
    input logic [22:0] i_events,
    input logic [7:0] i_read_bytes,
    input logic [7:0] i_write_bytes,
    input logic [O-1:0] i_occupancy
);
    wire [183:0] counts;
    wire [183:0] disabled_counts;
    wire [7:0] peak;
    wire [7:0] disabled_peak;
    scratchpad_bank_counters #(.WIDTH(8), .ASYNC_RESET(ASYNC_RESET != 0)) u_enabled (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(1'b1),
        .i_clear(1'b0),
        .i_events(i_events),
        .i_read_bytes(i_read_bytes),
        .i_write_bytes(i_write_bytes),
        .i_occupancy(8'(i_occupancy)),
        .o_counts(counts),
        .o_maximum_occupancy(peak)
    );
    scratchpad_bank_counters #(.WIDTH(8), .ASYNC_RESET(ASYNC_RESET != 0)) u_disabled (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(1'b0),
        .i_clear(1'b1),
        .i_events(i_events),
        .i_read_bytes(i_read_bytes),
        .i_write_bytes(i_write_bytes),
        .i_occupancy(8'(i_occupancy)),
        .o_counts(disabled_counts),
        .o_maximum_occupancy(disabled_peak)
    );
endmodule
