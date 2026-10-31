`timescale 1ns / 1ps
`default_nettype none
// Flit storage is independent of adjacent branches. A skid cuts reverse ready.
module configuration_network_link #(
    parameter int WIDTH = 128,
    parameter int DEPTH = 2,
    parameter int PROTECTION = 1,
    parameter int ASYNC_RESET = 0
) (
    input wire i_clk,
    input wire i_reset_n,
    input wire i_flush,
    input wire i_run,
    input wire i_valid,
    output wire o_ready,
    input wire [WIDTH-1:0] i_data,
    output wire o_valid,
    input wire i_ready,
    output wire [WIDTH-1:0] o_data,
    output wire o_idle,
    output wire o_bad
);
    wire valid;
    wire ready;
    wire [WIDTH-1:0] data;
    wire [31:0] count;
    wire queue_bad;
    wire link_bad;
    wire link_idle;
    wire run = i_reset_n === 1'b1 && i_run &&!i_flush &&!o_bad;
    static_mesh_queue #(
        .WIDTH(WIDTH),
        .DEPTH(DEPTH),
        .PROTECTION(PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_queue (
        .i_clk(i_clk),
        .i_reset_n(i_reset_n),
        .i_flush(i_flush),
        .i_valid(run && i_valid === 1'b1),
        .o_ready(o_ready),
        .i_data(i_data),
        .o_valid(valid),
        .i_ready(ready),
        .o_data(data),
        .o_count(count),
        .o_bad(queue_bad)
    );
    static_mesh_link #(
        .WIDTH(WIDTH),
        .PARITY(0),
        .PROTECTION(PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_skid (
        .i_clk(i_clk),
        .i_reset_n(i_reset_n),
        .i_flush(i_flush),
        .i_run(run),
        .i_fault(1'b0),
        .i_valid(valid),
        .o_ready(ready),
        .i_data(data),
        .o_valid(o_valid),
        .i_ready(i_ready === 1'b1),
        .o_data(o_data),
        .o_idle(link_idle),
        .o_transfer(),
        .o_parity_bad(),
        .o_bad(link_bad),
        .o_observed_data()
    );
    assign o_idle = count == 0 && link_idle;
    assign o_bad = queue_bad || link_bad;
endmodule
`default_nettype wire
