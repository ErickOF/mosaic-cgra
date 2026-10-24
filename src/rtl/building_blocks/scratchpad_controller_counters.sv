`timescale 1ns / 1ps
`default_nettype none

// Optional instrumentation for qualified increments. Flatten groups in ascending
// index order: clients (15 each), banks (10 each), client/bank denials, then global
// flush count and duration. Width-wide increments permit byte-weighted events.
// Disable freezes counts, peaks and clear; flush never clears lifetime counters.
module scratchpad_controller_counters #(
    parameter int NUM_CLIENTS = 4,
    parameter int NUM_BANKS = 8,
    parameter int WIDTH = 48,
    parameter bit ASYNC_RESET = 0,
    localparam int COUNT = NUM_CLIENTS * 15 + NUM_BANKS * 10 + NUM_CLIENTS * NUM_BANKS + 2
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_enable,
    input logic i_clear,
    input logic [COUNT*WIDTH-1:0] i_increments,
    input logic [NUM_CLIENTS*WIDTH-1:0] i_occupancy,
    output wire [COUNT*WIDTH-1:0] o_counts,
    output wire [NUM_CLIENTS*WIDTH-1:0] o_maximum_occupancy
);
    if (WIDTH < 1 || NUM_CLIENTS < 1 || NUM_BANKS < 1) begin : g_invalid_parameters
        scratchpad_controller_counter_parameters_must_be_valid invalid_parameters ();
    end else begin : g_counters
        wire reset_b = i_rstb !== 1'b0;
        wire enable = i_rstb === 1'b1 && i_enable === 1'b1;

        for (genvar k = 0; k < COUNT; k++) begin : g_count
            wire [WIDTH-1:0] value;
            wire [WIDTH-1:0] increment = i_increments[k*WIDTH+:WIDTH];
            wire [WIDTH:0] sum = {1'b0, value} + {1'b0, increment};
            wire [WIDTH-1:0] next_value = sum[WIDTH] ? {WIDTH{1'b1}} : sum[WIDTH-1:0];
            assign o_counts[k*WIDTH+:WIDTH] = value;

            counter #(.WIDTH(WIDTH), .ASYNC_RESET(ASYNC_RESET)) u_count (
                .i_clk(i_clk), .i_rstb(reset_b), .i_enable(1'b0),
                .i_clear(enable && i_clear === 1'b1),
                .i_load(enable && increment != '0), .i_direction(1'b0),
                .i_load_value(next_value), .o_count(value), .o_overflow(),
                .o_underflow(), .o_terminal()
            );
        end

        for (genvar c = 0; c < NUM_CLIENTS; c++) begin : g_peak
            wire [WIDTH-1:0] occupancy = i_occupancy[c*WIDTH+:WIDTH];
            wire [WIDTH-1:0] peak;
            assign o_maximum_occupancy[c*WIDTH+:WIDTH] = peak;

            dff #(.WIDTH(WIDTH), .ASYNC_RESET(ASYNC_RESET)) u_peak (
                .i_clk(i_clk), .i_rstb(reset_b),
                .i_enable(enable && (i_clear === 1'b1 || occupancy > peak)),
                .i_d(i_clear === 1'b1 ? {WIDTH{1'b0}} : occupancy), .o_q(peak)
            );
        end
    end
endmodule
`default_nettype wire
