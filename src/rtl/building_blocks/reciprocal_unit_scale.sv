`timescale 1ns / 1ps

// Restore the binary exponent in magnitude space, clamp to the independently
// selected signed/unsigned output range, then restore the original sign.
module reciprocal_unit_scale #(
    parameter int INTERNAL_WIDTH = 24,
    parameter int INTERNAL_FRACTION_WIDTH = 20,
    parameter int INPUT_WIDTH = 16,
    parameter int INPUT_FRACTION_WIDTH = 8,
    parameter int OUTPUT_WIDTH = 16,
    parameter int OUTPUT_FRACTION_WIDTH = 12,
    localparam int WIDE = INTERNAL_WIDTH + INPUT_WIDTH + OUTPUT_WIDTH + 4,
    localparam int SHIFT = $clog2(WIDE + 1)
) (
    input logic i_enable,
    input logic [INTERNAL_WIDTH-1:0] i_estimate,
    input logic signed [31:0] i_exponent,
    input logic i_signed,
    input logic i_negative,
    input logic i_nearest,
    output wire [OUTPUT_WIDTH-1:0] o_data,
    output wire o_overflow,
    output wire o_underflow,
    output wire o_inexact
);
    wire signed [31:0] shift_value = OUTPUT_FRACTION_WIDTH -
        INTERNAL_FRACTION_WIDTH - i_exponent;
    wire [WIDE-1:0] rounded;
    wire inexact;
    // A right shift beyond the entire estimate is below half and rounds to zero.
    wire [SHIFT-1:0] right_shift = shift_value < 0 ?
        ( -shift_value >= WIDE ? SHIFT'(WIDE - 1) : SHIFT'(-shift_value)) : '0;

    polynomial_unit_round #(.WIDTH(WIDE), .SHIFT_WIDTH(SHIFT)) u_round (
        .i_value(i_enable ? WIDE'(i_estimate) : '0),
        .i_shift(right_shift),
        .i_nearest(i_nearest),
        .o_value(rounded),
        .o_inexact(inexact)
    );

    wire [WIDE-1:0] magnitude = shift_value >= 0 ?
        WIDE'(i_estimate) << shift_value : rounded;
    wire [WIDE-1:0] sign_limit = WIDE'(1) << (OUTPUT_WIDTH - 1);
    wire [WIDE-1:0] limit_value = i_signed ?
        (i_negative ? sign_limit : sign_limit - 1'b1) :
        (WIDE'(1) << OUTPUT_WIDTH) - 1'b1;
    wire [OUTPUT_WIDTH-1:0] clamped = magnitude > limit_value ?
        OUTPUT_WIDTH'(limit_value) : OUTPUT_WIDTH'(magnitude);
    assign o_data = !i_enable ? '0 : i_negative ? -clamped : clamped;
    assign o_overflow = i_enable && magnitude > limit_value;
    assign o_underflow = i_enable && magnitude == 0;
    assign o_inexact = i_enable && inexact;
endmodule
