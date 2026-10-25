`timescale 1ns / 1ps

// One multiply-rescale operation. Iterative mode shares this instance between
// n*y and y*u; unrolled mode instantiates one at each multiplication position.
module reciprocal_unit_newton #(
    parameter int WIDTH = 24,
    parameter int FRACTION = 20,
    localparam int PRODUCT = 2 * WIDTH,
    localparam int ROUND_WIDTH = PRODUCT + 1,
    localparam int SHIFT = $clog2(ROUND_WIDTH + 1)
) (
    input logic i_enable,
    input logic i_second,
    input logic i_nearest,
    input logic [WIDTH-1:0] i_normalized,
    input logic [WIDTH-1:0] i_estimate,
    input logic [WIDTH-1:0] i_correction,
    output wire [WIDTH-1:0] o_value,
    output wire o_inexact,
    output wire o_bad
);
    wire unused_valid;
    wire unused_signed;
    wire unused_zero;
    wire unused_negative;
    wire [PRODUCT-1:0] product;

    multiplier #(.OPERAND_WIDTH(WIDTH), .LATENCY(0)) u_multiply (
        .i_clk(1'b0),
        .i_rstb(1'b1),
        .i_clock_enable(1'b1),
        .i_valid(i_enable),
        .i_operand_a(i_second ? i_estimate : i_normalized),
        .i_operand_b(i_second ? i_correction : i_estimate),
        .i_signed_a(1'b0),
        .i_signed_b(1'b0),
        .o_valid(unused_valid),
        .o_product(product),
        .o_product_signed(unused_signed),
        .o_zero(unused_zero),
        .o_negative(unused_negative)
    );

    wire [ROUND_WIDTH-1:0] rounded;
    polynomial_unit_round #(.WIDTH(ROUND_WIDTH), .SHIFT_WIDTH(SHIFT)) u_round (
        .i_value({1'b0, product}),
        .i_shift(SHIFT'(FRACTION)),
        .i_nearest(i_nearest),
        .o_value(rounded),
        .o_inexact(o_inexact)
    );

    wire [WIDTH:0] difference;
    wire borrow;
    wire unused_predicate;
    wire unused_alu_zero;
    wire unused_alu_negative;
    wire unused_carry;
    wire unused_overflow;
    wire unused_saturated;
    wire unused_illegal;
    localparam logic [WIDTH:0] TWO = (WIDTH + 1)'(1) << (FRACTION + 1);

    scalar_alu #(.DATA_WIDTH(WIDTH + 1)) u_subtract (
        .i_enable(i_enable && !i_second),
        .i_opcode(scalar_alu_pkg::ALU_SUB),
        .i_operand_a(TWO),
        .i_operand_b((WIDTH + 1)'(rounded)),
        .i_predicate(1'b1),
        .i_signed(1'b0),
        .i_saturate(1'b0),
        .o_result(difference),
        .o_predicate(unused_predicate),
        .o_zero(unused_alu_zero),
        .o_negative(unused_alu_negative),
        .o_carry(unused_carry),
        .o_borrow(borrow),
        .o_overflow(unused_overflow),
        .o_saturated(unused_saturated),
        .o_illegal_operation(unused_illegal)
    );

    wire too_large = (|rounded[ROUND_WIDTH-1:WIDTH]) !== 1'b0;
    wire bad_correction = borrow || difference[WIDTH];
    assign o_bad = i_enable && (too_large || (!i_second && bad_correction));
    assign o_value = !i_enable ? '0 : o_bad ? {WIDTH{1'b1}} :
        i_second ? rounded[WIDTH-1:0] : difference[WIDTH-1:0];
endmodule
