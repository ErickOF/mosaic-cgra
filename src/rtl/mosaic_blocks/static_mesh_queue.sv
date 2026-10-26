`timescale 1ns / 1ps
`default_nettype none
// Boundary storage has no fall-through unless depth zero is explicitly selected
// by a scheduled-flow profile. Keep admission independent of delivery for drain.
module static_mesh_queue #(
    parameter int WIDTH = 97,
    parameter int DEPTH = 1,
    parameter int PROTECTION = 0,
    parameter int ASYNC_RESET = 0
) (
    input wire i_clk,
    input wire i_reset_n,
    input wire i_flush,
    input wire i_valid,
    output wire o_ready,
    input wire [WIDTH-1:0] i_data,
    output wire o_valid,
    input wire i_ready,
    output wire [WIDTH-1:0] o_data,
    output wire [31:0] o_count,
    output wire o_bad
);
    if (DEPTH == 0) begin : g_wire
        assign o_valid = i_reset_n === 1'b1 &&!i_flush && i_valid;
        assign o_ready = i_reset_n === 1'b1 &&!i_flush && i_ready;
        assign o_data = o_valid ? i_data : '0;
        assign o_count = '0;
        assign o_bad = 1'b0;
    end else begin : g_queue
        wire [$clog2(DEPTH+1)-1:0] count;
        wire raw_valid;
        wire raw_ready;

        event_barrier_queue #(
            .WIDTH(WIDTH),
            .DEPTH(DEPTH),
            .PROTECTED(PROTECTION != 0),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_queue (
            .i_clk(i_clk),
            .i_rstb(i_reset_n),
            .i_flush(i_flush),
            .i_valid(i_valid && !i_flush && !o_bad),
            .o_ready(raw_ready),
            .i_data(i_data),
            .o_valid(raw_valid),
            .i_ready(i_ready && !i_flush && !o_bad),
            .o_data(o_data),
            .o_occupancy(count),
            .o_corrupt(o_bad),
            .o_occupied(),
            .o_contents()
        );

        assign o_valid = i_reset_n === 1'b1 &&!i_flush &&!o_bad && raw_valid;
        assign o_ready = i_reset_n === 1'b1 &&!i_flush &&!o_bad && raw_ready;
        assign o_count = 32'(count);
    end
endmodule
`default_nettype wire
