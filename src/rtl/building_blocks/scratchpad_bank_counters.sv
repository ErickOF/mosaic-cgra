`timescale 1ns / 1ps
`default_nettype none

// Optional, bindable lifetime counters. The bank supplies qualified event bits;
// read/write byte counts are weighted. Disable suppresses clear as well as events.
module scratchpad_bank_counters #(
    parameter int WIDTH = 48,
    parameter bit ASYNC_RESET = 0
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_enable,
    input logic i_clear,
    input logic [22:0] i_events,
    input logic [WIDTH-1:0] i_read_bytes,
    input logic [WIDTH-1:0] i_write_bytes,
    input logic [WIDTH-1:0] i_occupancy,
    output wire [23*WIDTH-1:0] o_counts,
    output wire [WIDTH-1:0] o_maximum_occupancy
);
    if (WIDTH < 1) begin : g_invalid_width
        scratchpad_bank_counter_width_must_be_positive invalid_width ();
    end else begin : g_counters
        wire reset_b = i_rstb !== 1'b0;
        wire enable = i_rstb === 1'b1 && i_enable === 1'b1;

        for (genvar k = 0; k < 23; k++) begin : g_count
            wire [WIDTH-1:0] value;
            wire [2:0] unused_status;
            wire weighted = k == scratchpad_bank_pkg::BANK_COUNT_READ_BYTES ||
                k == scratchpad_bank_pkg::BANK_COUNT_WRITE_BYTES;
            wire [WIDTH-1:0] increment = k == scratchpad_bank_pkg::BANK_COUNT_READ_BYTES ?
                i_read_bytes : i_write_bytes;
            wire [WIDTH:0] sum = {1'b0, value} + {1'b0, increment};
            wire [WIDTH-1:0] next_value = sum[WIDTH] ? {WIDTH{1'b1}} : sum[WIDTH-1:0];
            assign o_counts[k*WIDTH+:WIDTH] = value;

            counter #(.WIDTH(WIDTH), .ASYNC_RESET(ASYNC_RESET)) u_count (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_enable(enable && i_events[k]),
                .i_clear(enable && i_clear),
                .i_load(enable && i_events[k] && weighted),
                .i_direction(1'b0),
                .i_load_value(next_value),
                .o_count(value),
                .o_overflow(unused_status[0]),
                .o_underflow(unused_status[1]),
                .o_terminal(unused_status[2])
            );
        end

        dff #(.WIDTH(WIDTH), .ASYNC_RESET(ASYNC_RESET)) u_peak (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(enable && (i_clear || i_occupancy > o_maximum_occupancy)),
            .i_d(i_clear ? {WIDTH{1'b0}} : i_occupancy),
            .o_q(o_maximum_occupancy)
        );
    end
endmodule
`default_nettype wire
