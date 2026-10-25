`timescale 1ns / 1ps
// Read-only lifetime instrumentation. Reset is the sole clear; snapshots and
// privileged software transport belong to the integrating runtime adapter.
module banked_scratchpad_counters #(
    parameter int COUNT = 1,
    parameter int PEAKS = 1,
    parameter int ASYNC_RESET = 0
) (
    input logic i_clk,
    input logic i_reset_n,
    input logic [COUNT*32-1:0] i_increments,
    input logic [PEAKS*32-1:0] i_occupancy,
    output wire [COUNT*32-1:0] o_counts,
    output wire [PEAKS*32-1:0] o_peaks
);
    for (genvar k = 0; k < COUNT; k++) begin : g_count
        wire [31:0] value;
        wire [31:0] increment = i_increments[k*32+:32];
        wire [32:0] sum = {1'b0, value} + {1'b0, increment};

        counter #(.WIDTH(32), .ASYNC_RESET(ASYNC_RESET)) u_counter (
            .i_clk(i_clk),
            .i_rstb(i_reset_n),
            .i_enable(1'b0),
            .i_clear(1'b0),
            .i_load(i_reset_n === 1'b1 && increment != 0),
            .i_direction(1'b0),
            .i_load_value(sum[32] ? 32'hffffffff : sum[31:0]),
            .o_count(value),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );

        assign o_counts[k*32+:32] = value;
    end

    for (genvar p = 0; p < PEAKS; p++) begin : g_peak
        wire [31:0] occupancy = i_occupancy[p*32+:32];
        wire [31:0] peak;

        dff #(.WIDTH(32), .ASYNC_RESET(ASYNC_RESET)) u_peak (
            .i_clk(i_clk),
            .i_rstb(i_reset_n),
            .i_enable(i_reset_n === 1'b1 && occupancy > peak),
            .i_d(occupancy),
            .o_q(peak)
        );

        assign o_peaks[p*32+:32] = peak;
    end
endmodule
