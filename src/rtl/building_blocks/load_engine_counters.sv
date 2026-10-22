`timescale 1ns / 1ps

// Optional/bindable instrumentation; absent from the functional engine instance.
// Event indices: start, complete, fail, request, response, stream, request-stall,
// head-wait, stream-stall, full, memory-error, protocol-error, stream-bytes.
module load_engine_counters #(
    parameter int WIDTH = 32,
    parameter bit ASYNC_RESET = 0
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_enable,
    input logic i_clear,
    input logic [12:0] i_events,
    input logic [WIDTH-1:0] i_stream_bytes,
    input logic [WIDTH-1:0] i_occupancy,
    output wire [13*WIDTH-1:0] o_counts,
    output wire [WIDTH-1:0] o_maximum_occupancy
);
    import load_engine_pkg::*;
    if (WIDTH < 1) begin : g_invalid_parameters
        load_engine_counter_width_must_be_positive invalid_parameters ();
    end else begin : g_counters
        wire reset_b = i_rstb !== 1'b0;
        wire enable = (i_rstb === 1'b1) && (i_enable === 1'b1);
        for (genvar n = 0; n < 13; n++) begin : g_count
            wire [2:0] unused_status;
            wire enabled_event = enable && i_events[n];
            wire byte_write = enabled_event && (n == LOAD_COUNT_STREAM_BYTES);
            wire [WIDTH-1:0] current_count;
            assign o_counts[n*WIDTH+:WIDTH] = current_count;
            wire [WIDTH:0] sum = {1'b0, current_count} + {1'b0, i_stream_bytes};
            wire [WIDTH-1:0] next_bytes = sum[WIDTH] ? {WIDTH{1'b1}} : sum[WIDTH-1:0];

            counter #(.WIDTH(WIDTH), .ASYNC_RESET(ASYNC_RESET)) u_count (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_clear(enable && i_clear),
                .i_enable(enabled_event),
                .i_load(byte_write),
                .i_direction(1'b0),
                .i_load_value(next_bytes),
                .o_count(current_count),
                .o_overflow(unused_status[0]),
                .o_underflow(unused_status[1]),
                .o_terminal(unused_status[2])
            );
        end

        dff #(.WIDTH(WIDTH), .ASYNC_RESET(ASYNC_RESET)) u_maximum (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(enable && (i_clear || (i_occupancy > o_maximum_occupancy))),
            .i_d(i_clear ? {WIDTH{1'b0}} : i_occupancy),
            .o_q(o_maximum_occupancy)
        );
    end
endmodule
