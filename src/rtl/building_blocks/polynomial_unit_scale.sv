`timescale 1ns / 1ps

// Wide left scaling retains every bit before the final signed clamp.
module polynomial_unit_scale #(
    parameter int ACCUMULATOR_WIDTH = 32,
    parameter int OUTPUT_WIDTH = 16,
    parameter int SHIFT_WIDTH = 6,
    localparam int W = 2 * ACCUMULATOR_WIDTH + OUTPUT_WIDTH + 1
) (
    input logic i_enable,
    input logic [ACCUMULATOR_WIDTH-1:0] i_accumulator,
    input logic signed [SHIFT_WIDTH-1:0] i_shift,
    input logic i_nearest,
    output logic [OUTPUT_WIDTH-1:0] o_data,
    output logic o_inexact,
    output logic o_saturated
);
    wire signed [W-1:0] value = i_enable ? W'($signed(i_accumulator)) : '0;
    wire signed [W-1:0] rounded;
    wire signed [W-1:0] scaled = i_shift < 0 ? value <<< (-i_shift) : rounded;
    wire discarded;
    localparam logic signed [W-1:0] MAXIMUM = (W'(1) << (OUTPUT_WIDTH - 1)) - 1'b1;
    localparam logic signed [W-1:0] MINIMUM = -(W'(1) << (OUTPUT_WIDTH - 1));

    polynomial_unit_round #(.WIDTH(W), .SHIFT_WIDTH(SHIFT_WIDTH)) u_round (
        .i_value(value),
        .i_shift(i_shift < 0 ? SHIFT_WIDTH'(0) : i_shift),
        .i_nearest(i_nearest),
        .o_value(rounded),
        .o_inexact(discarded)
    );

    assign o_inexact = i_enable && discarded;
    assign o_saturated = i_enable && (scaled > MAXIMUM || scaled < MINIMUM);
    assign o_data = scaled > MAXIMUM ? OUTPUT_WIDTH'(MAXIMUM) :
        scaled < MINIMUM ? OUTPUT_WIDTH'(MINIMUM) : OUTPUT_WIDTH'(scaled);
endmodule
