`timescale 1ns / 1ps
`default_nettype none
// Common fork plus an independent protected pending-destination witness.
module configuration_network_fork #(
    parameter int WIDTH = 128,
    parameter int OUTPUTS = 4,
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
    input wire [OUTPUTS-1:0] i_destination,
    output wire [OUTPUTS-1:0] o_valid,
    input wire [OUTPUTS-1:0] i_ready,
    output wire [OUTPUTS*WIDTH-1:0] o_data,
    output wire o_idle,
    output wire o_bad
);
    wire raw_ready;
    wire [OUTPUTS-1:0] valid;
    wire [OUTPUTS-1:0] ready;
    wire [OUTPUTS*WIDTH-1:0] raw_data;
    logic [OUTPUTS*WIDTH-1:0] data;
    always @* data = raw_data;
    wire [OUTPUTS-1:0] witness;
    wire witness_bad;
    wire run = i_reset_n === 1'b1 && i_run &&!i_flush &&!o_bad;
    wire accept = i_valid === 1'b1 && o_ready;
    wire [OUTPUTS-1:0] next_witness = i_flush ? '0 : accept ?
        i_destination : witness & ~ready;
    for (genvar k = 0; k < OUTPUTS; k++) begin : g_ready
        assign ready[k] = i_flush || (run && i_ready[k] === 1'b1);
        assign o_valid[k] = run && valid[k];
        assign o_data[k*WIDTH+:WIDTH] = o_valid[k] ? data[k*WIDTH+:WIDTH] : '0;
    end
    stream_fork #(
        .NUM_OUTPUTS(OUTPUTS),
        .DATA_WIDTH(WIDTH),
        .HAS_DESTINATION_MASK(1),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_fork (
        .i_clk(i_clk),
        .i_rstb(i_reset_n),
        .i_valid(run && i_valid === 1'b1),
        .o_ready(raw_ready),
        .i_data(i_data),
        .i_destination(i_destination),
        .o_valid(valid),
        .i_ready(ready),
        .o_data(raw_data)
    );
    banked_scratchpad_state #(
        .WIDTH(OUTPUTS),
        .PROTECTION(PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_witness (
        .i_clk(i_clk),
        .i_reset_n(i_reset_n),
        .i_data(next_witness),
        .o_data(witness),
        .o_bad(witness_bad)
    );
    assign o_ready = run && raw_ready;
    assign o_idle = witness == 0;
    assign o_bad = witness_bad || (i_reset_n === 1'b1 && valid !== witness);
endmodule
`default_nettype wire
