`timescale 1ns / 1ps

// Combinational interpolation between protected endpoints. Unequal unsigned
// operands are zero-extended before multiplication; rounding sees every product
// bit. The parent supplies validated geometry and registers the elastic result.
module exp_unit_interpolate #(
    parameter int WIDTH = 24,
    parameter int REMAINDER_WIDTH = 14,
    localparam int MULTIPLY_WIDTH = WIDTH > REMAINDER_WIDTH ? WIDTH : REMAINDER_WIDTH,
    localparam int PRODUCT_WIDTH = WIDTH + REMAINDER_WIDTH,
    localparam int ROUND_WIDTH = PRODUCT_WIDTH + 1,
    localparam int SHIFT_WIDTH = $clog2(ROUND_WIDTH + 1)
) (
    input logic i_enable,
    input logic i_nearest,
    input logic [WIDTH-1:0] i_lower,
    input logic [WIDTH-1:0] i_upper,
    input logic [REMAINDER_WIDTH-1:0] i_remainder,
    output wire [WIDTH-1:0] o_mantissa,
    output wire o_inexact,
    output wire o_bad
);
    wire [WIDTH:0] difference;
    wire borrow;

    scalar_alu #(.DATA_WIDTH(WIDTH + 1)) u_difference (
        .i_enable(i_enable),
        .i_opcode(scalar_alu_pkg::ALU_SUB),
        .i_operand_a({1'b0, i_upper}),
        .i_operand_b({1'b0, i_lower}),
        .i_predicate(1'b1),
        .i_signed(1'b0),
        .i_saturate(1'b0),
        .o_result(difference),
        .o_borrow(borrow),
        .o_predicate(),
        .o_zero(),
        .o_negative(),
        .o_carry(),
        .o_overflow(),
        .o_saturated(),
        .o_illegal_operation()
    );

    wire [2*MULTIPLY_WIDTH-1:0] full_product;
    multiplier #(.OPERAND_WIDTH(MULTIPLY_WIDTH), .LATENCY(0)) u_multiply (
        .i_clk(1'b0),
        .i_rstb(1'b1),
        .i_clock_enable(1'b1),
        .i_valid(i_enable),
        .i_operand_a(MULTIPLY_WIDTH'(difference[WIDTH-1:0])),
        .i_operand_b(MULTIPLY_WIDTH'(i_remainder)),
        .i_signed_a(1'b0),
        .i_signed_b(1'b0),
        .o_product(full_product),
        .o_valid(),
        .o_product_signed(),
        .o_zero(),
        .o_negative()
    );

    wire [ROUND_WIDTH-1:0] rounded;
    polynomial_unit_round #(.WIDTH(ROUND_WIDTH), .SHIFT_WIDTH(SHIFT_WIDTH)) u_round (
        .i_value({1'b0, full_product[PRODUCT_WIDTH-1:0]}),
        .i_shift(SHIFT_WIDTH'(REMAINDER_WIDTH)),
        .i_nearest(i_nearest),
        .o_value(rounded),
        .o_inexact(o_inexact)
    );

    wire [WIDTH:0] interpolated;
    scalar_alu #(.DATA_WIDTH(WIDTH + 1)) u_sum (
        .i_enable(i_enable),
        .i_opcode(scalar_alu_pkg::ALU_ADD),
        .i_operand_a({1'b0, i_lower}),
        .i_operand_b((WIDTH + 1)'(rounded)),
        .i_predicate(1'b1),
        .i_signed(1'b0),
        .i_saturate(1'b0),
        .o_result(interpolated),
        .o_predicate(),
        .o_zero(),
        .o_negative(),
        .o_carry(),
        .o_borrow(),
        .o_overflow(),
        .o_saturated(),
        .o_illegal_operation()
    );

    assign o_mantissa = i_enable ? interpolated[WIDTH-1:0] : i_lower;
    assign o_bad = i_enable && (borrow || (|rounded[ROUND_WIDTH-1:WIDTH]) ||
        interpolated > {1'b0, i_upper} || interpolated < {1'b0, i_lower});
endmodule
