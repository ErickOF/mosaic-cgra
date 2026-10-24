`timescale 1ns / 1ps

// Normalize the widened effective magnitude into [1,4). Arithmetic right shift
// implements floor(exponent/2), including negative odd exponents.
module rsqrt_unit_normalize #(
    parameter int INPUT_WIDTH = 16,
    parameter int INPUT_FRACTION_WIDTH = 8,
    parameter int INTERNAL_WIDTH = 28,
    parameter int INTERNAL_FRACTION_WIDTH = 22,
    localparam int MAGNITUDE = INPUT_WIDTH + 1,
    localparam int INDEX = $clog2(MAGNITUDE),
    localparam int WIDE = INPUT_WIDTH + INTERNAL_WIDTH + 3,
    localparam int SHIFT = $clog2(WIDE + 1)
) (
    input logic i_enable,
    input logic [MAGNITUDE-1:0] i_magnitude,
    input logic i_nearest,
    output wire [INTERNAL_WIDTH-1:0] o_normalized,
    output wire signed [31:0] o_half_exponent,
    output wire o_parity,
    output wire o_inexact
);
    wire [MAGNITUDE-1:0] magnitude = i_enable ? i_magnitude : '0;
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

    wire signed [31:0] exponent_value = 32'(leading) - INPUT_FRACTION_WIDTH;
    wire signed [31:0] shift_value = INTERNAL_FRACTION_WIDTH - 32'(leading);
    wire [SHIFT-1:0] right_shift = shift_value < 0 ? SHIFT'(-shift_value) : '0;
    wire [WIDE-1:0] rounded;
    wire inexact;

    polynomial_unit_round #(.WIDTH(WIDE), .SHIFT_WIDTH(SHIFT)) u_round (
        .i_value(WIDE'(magnitude)),
        .i_shift(right_shift),
        .i_nearest(i_nearest),
        .o_value(rounded),
        .o_inexact(inexact)
    );

    localparam logic [INTERNAL_WIDTH-1:0] TWO = INTERNAL_WIDTH'(1) <<
        (INTERNAL_FRACTION_WIDTH + 1);
    wire [WIDE-1:0] shifted = shift_value >= 0 ?
        WIDE'(magnitude) << shift_value : rounded;
    wire [INTERNAL_WIDTH-1:0] mantissa = shifted >= WIDE'(TWO) ?
        TWO - 1'b1 : INTERNAL_WIDTH'(shifted);
    assign o_normalized = i_enable ? mantissa << exponent_value[0] : '0;
    wire signed [31:0] half_exponent = exponent_value >>> 1;
    assign o_half_exponent = i_enable ? half_exponent : 32'sd0;
    assign o_parity = i_enable && exponent_value[0];
    assign o_inexact = i_enable && (inexact || shifted >= WIDE'(TWO));
endmodule
