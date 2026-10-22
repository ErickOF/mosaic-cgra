`timescale 1ns / 1ps

// Elastic token/control FIFO plus a separately enabled, unreset arithmetic bank.
// CONTROL's most-significant bit is active. Inactive tokens preserve latency
// and metadata while arithmetic storage holds. Parent validates all geometry.
module exp_unit_stage #(
    parameter int CONTROL = 16,
    parameter int DATA = 32,
    parameter bit PROTECTED = 0,
    parameter bit ASYNC_RESET = 0,
    localparam int C_BITS = CONTROL + int'(PROTECTED),
    localparam int D_BITS = DATA + int'(PROTECTED)
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_flush,
    input logic i_enable,
    input logic i_valid,
    output wire o_ready,
    input logic [CONTROL-1:0] i_control,
    input logic [DATA-1:0] i_data,
    output wire o_valid,
    input logic i_ready,
    output wire [CONTROL-1:0] o_control,
    output wire [DATA-1:0] o_data,
    output wire o_corrupt
);
    wire [C_BITS-1:0] control_input;
    wire [C_BITS-1:0] control_output;
    wire [D_BITS-1:0] data_input;
    wire [D_BITS-1:0] stored_data;
    wire capture = i_enable && i_valid && o_ready &&!i_flush;
    wire unused_full;
    wire unused_empty;
    wire unused_almost_full;
    wire unused_almost_empty;
    wire unused_occupancy;

    if (PROTECTED) begin : g_protection
        assign control_input = { ^ i_control, i_control};
        assign data_input = { ^ i_data, i_data};
        assign o_corrupt = o_valid && (( ^ control_output !== 1'b0) ||
            (o_control[CONTROL-1] && ( ^ stored_data !== 1'b0)));
    end else begin : g_unprotected
        assign control_input = i_control;
        assign data_input = i_data;
        assign o_corrupt = 1'b0;
    end

    fifo #(.DATA_WIDTH(C_BITS), .DEPTH(1), .ASYNC_RESET(ASYNC_RESET)) u_control (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_valid(i_enable && i_valid &&!i_flush),
        .o_ready(o_ready),
        .i_data(control_input),
        .o_valid(o_valid),
        .i_ready(i_flush || (i_enable && i_ready)),
        .o_data(control_output),
        .o_full(unused_full),
        .o_empty(unused_empty),
        .o_almost_full(unused_almost_full),
        .o_almost_empty(unused_almost_empty),
        .o_occupancy(unused_occupancy)
    );

    dff #(.WIDTH(D_BITS)) u_arithmetic (
        .i_clk(i_clk),
        .i_rstb(1'b1),
        .i_enable(i_rstb && capture && i_control[CONTROL-1]),
        .i_d(data_input),
        .o_q(stored_data)
    );

    assign o_control = control_output[CONTROL-1:0];
    assign o_data = o_valid && o_control[CONTROL-1] ? stored_data[DATA-1:0] : '0;
endmodule
