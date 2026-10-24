`timescale 1ns / 1ps

// Normalize magnitude using the released MSB-priority encoder. All wide shifts
// occur in a zero-extended vector; integer arithmetic is only used for exponents.
module reciprocal_unit_normalize #(
    parameter int INPUT_WIDTH = 16,
    parameter int INTERNAL_WIDTH = 24,
    parameter int INPUT_FRACTION_WIDTH = 8,
    parameter int INTERNAL_FRACTION_WIDTH = 20,
    localparam int MAGNITUDE = INPUT_WIDTH + 1,
    localparam int INDEX = $clog2(MAGNITUDE),
    localparam int WIDE = INPUT_WIDTH + INTERNAL_WIDTH + 2,
    localparam int SHIFT = $clog2(WIDE + 1)
) (
    input logic i_enable,
    input logic [INPUT_WIDTH-1:0] i_operand,
    input logic i_signed,
    input logic i_nearest,
    output wire [INTERNAL_WIDTH-1:0] o_normalized,
    output wire signed [31:0] o_exponent,
    output wire o_negative,
    output wire o_inexact
);
    wire [MAGNITUDE-1:0] extended = {1'b0, i_operand};
    wire negative = i_signed && i_operand[INPUT_WIDTH-1];
    wire [MAGNITUDE-1:0] magnitude = i_enable ?
        (negative ? (~{1'b1, i_operand} + 1'b1) : extended) : '0;
    wire unused_valid;
    wire unused_multiple;
    wire [MAGNITUDE-1:0] unused_onehot;
    wire [INDEX-1:0] leading;

    priority_encoder #(.WIDTH(MAGNITUDE), .LSB_HIGH_PRIORITY(0)) u_leading (
        .i_request(magnitude),
        .o_valid(unused_valid),
        .o_index(leading),
        .o_onehot(unused_onehot),
        .o_multiple(unused_multiple)
    );

    wire signed [31:0] shift_value = INTERNAL_FRACTION_WIDTH - (32'(leading) + 1);
    wire [WIDE-1:0] rounded;
    wire inexact;
    wire [SHIFT-1:0] right_shift = shift_value < 0 ? SHIFT'(-shift_value) : '0;

    // The added sign bit makes the existing signed-magnitude rounder an exact
    // unsigned rounder as well. WIDE accommodates every normalization left shift.
    polynomial_unit_round #(.WIDTH(WIDE), .SHIFT_WIDTH(SHIFT)) u_round (
        .i_value(WIDE'(magnitude)),
        .i_shift(right_shift),
        .i_nearest(i_nearest),
        .o_value(rounded),
        .o_inexact(inexact)
    );

    wire [WIDE-1:0] shifted = shift_value >= 0 ?
        WIDE'(magnitude) << shift_value : rounded;
    localparam logic [INTERNAL_WIDTH-1:0] ONE = INTERNAL_WIDTH'(1) <<
        INTERNAL_FRACTION_WIDTH;
    assign o_normalized = i_enable ? (shifted >= WIDE'(ONE) ?
        ONE - 1'b1 : INTERNAL_WIDTH'(shifted)) : '0;
    assign o_exponent = i_enable ? 32'(leading) + 1 - INPUT_FRACTION_WIDTH : '0;
    assign o_negative = i_enable && negative;
    assign o_inexact = i_enable && (inexact || shifted >= WIDE'(ONE));
endmodule
