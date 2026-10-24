`timescale 1ns / 1ps

// One exact multiply, magnitude rescale, coefficient addition, then saturation.
module polynomial_unit_horner #(
    parameter int INPUT_WIDTH = 16,
    parameter int COEFFICIENT_WIDTH = 18,
    parameter int ACCUMULATOR_WIDTH = 32,
    parameter int FRACTION_WIDTH = 12,
    localparam int M = ACCUMULATOR_WIDTH > INPUT_WIDTH ? ACCUMULATOR_WIDTH : INPUT_WIDTH,
    localparam int W = 2 * M + 2
) (
    input logic i_enable,
    input logic [INPUT_WIDTH-1:0] i_x,
    input logic [ACCUMULATOR_WIDTH-1:0] i_accumulator,
    input logic [COEFFICIENT_WIDTH-1:0] i_coefficient,
    input logic i_nearest,
    output logic [ACCUMULATOR_WIDTH-1:0] o_accumulator,
    output logic o_inexact,
    output logic o_saturated
);
    wire [2*M-1:0] product;
    wire signed [W-1:0] rounded;
    wire signed [W-1:0] sum_value = rounded +
        (i_enable ? W'($signed(i_coefficient)) : W'(0));
    localparam logic signed [W-1:0] MAXIMUM = (W'(1) << (ACCUMULATOR_WIDTH - 1)) - 1'b1;
    localparam logic signed [W-1:0] MINIMUM = -(W'(1) << (ACCUMULATOR_WIDTH - 1));

    multiplier #(.OPERAND_WIDTH(M), .LATENCY(0)) u_multiplier (
        .i_clk(1'b0),
        .i_rstb(1'b1),
        .i_clock_enable(1'b1),
        .i_valid(i_enable),
        .i_operand_a(M'($signed(i_accumulator))),
        .i_operand_b(M'($signed(i_x))),
        .i_signed_a(1'b1),
        .i_signed_b(1'b1),
        .o_product(product),
        .o_valid(),
        .o_product_signed(),
        .o_zero(),
        .o_negative()
    );

    polynomial_unit_round #(.WIDTH(W), .SHIFT_WIDTH($clog2(W + 1))) u_round (
        .i_value(W'($signed(product))),
        .i_shift($clog2(W + 1)'(FRACTION_WIDTH)),
        .i_nearest(i_nearest),
        .o_value(rounded),
        .o_inexact(o_inexact)
    );

    assign o_saturated = i_enable && (sum_value > MAXIMUM || sum_value < MINIMUM);
    assign o_accumulator = sum_value > MAXIMUM ? ACCUMULATOR_WIDTH'(MAXIMUM) :
        sum_value < MINIMUM ? ACCUMULATOR_WIDTH'(MINIMUM) :
        ACCUMULATOR_WIDTH'(sum_value);
endmodule
