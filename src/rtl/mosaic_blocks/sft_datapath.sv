`timescale 1ns / 1ps
`default_nettype none
// Exact integer, full-product and reduction paths. Narrowing is an explicit op.
module sft_datapath #(
    parameter D = 64,
    parameter I = 16,
    parameter OW = 16,
    parameter EW = 16,
    parameter NL = 4,
    parameter RA = 48,
    parameter GENERAL_MULTIPLY = 1,
    parameter SUPPORT_SATURATION = 1
) (
    input wire i_enable,
    input wire [7:0] i_operation,
    input wire [4:0] i_opcode,
    input wire [D-1:0] i_a,
    input wire [D-1:0] i_b,
    input wire i_signed,
    input wire i_saturate,
    input wire i_round,
    input wire i_select,
    input wire [7:0] i_shift,
    input wire [NL-1:0] i_mask,
    input wire [2:0] i_reduction,
    output logic [D-1:0] o_data,
    output logic [15:0] o_flags,
    output wire [15:0] o_count
);
    import sft_pkg::*;
    wire [D-1:0] alu_data;
    wire alu_predicate;
    wire alu_overflow;
    wire alu_saturated;
    wire alu_illegal;
    wire abs_negative = i_opcode == 20 && i_signed && i_a[D-1];

    scalar_alu #(
        .DATA_WIDTH(D),
        .SUPPORT_SATURATION(SUPPORT_SATURATION)
    ) u_alu (
        .i_enable(i_enable && i_operation == SFT_ALU),
        .i_opcode(i_opcode == 20 ? (abs_negative ? 5'd1 : 5'd16) : i_opcode),
        .i_operand_a(abs_negative ? {D{1'b0}} : i_a),
        .i_operand_b(abs_negative ? i_a : i_b),
        .i_predicate(i_select),
        .i_signed(i_signed),
        .i_saturate(i_saturate && (i_opcode != 20 || abs_negative)),
        .o_result(alu_data),
        .o_predicate(alu_predicate),
        .o_overflow(alu_overflow),
        .o_saturated(alu_saturated),
        .o_illegal_operation(alu_illegal),
        .o_zero(),
        .o_negative(),
        .o_carry(),
        .o_borrow()
    );

    wire [2*I-1:0] product;

    if (GENERAL_MULTIPLY == 1) begin : g_multiply
        multiplier #(
            .OPERAND_WIDTH(I),
            .LATENCY(0)
        ) u_multiply (
            .i_clk(1'b0),
            .i_rstb(1'b1),
            .i_clock_enable(1'b1),
            .i_valid(i_enable && i_operation == SFT_MULTIPLY),
            .i_operand_a(i_a[0+:I]),
            .i_operand_b(i_b[0+:I]),
            .i_signed_a(i_signed),
            .i_signed_b(i_signed),
            .o_product(product),
            .o_valid(),
            .o_product_signed(),
            .o_zero(),
            .o_negative()
        );
    end else begin : g_no_multiply
        assign product = '0;
    end

    wire [NL*2*EW-1:0] squares;

    for (genvar lane = 0; lane < NL; lane++) begin : g_sumsq
        multiplier #(
            .OPERAND_WIDTH(EW),
            .LATENCY(0)
        ) u_square (
            .i_clk(1'b0),
            .i_rstb(1'b1),
            .i_clock_enable(1'b1),
            .i_valid(i_enable && i_operation == SFT_REDUCE && i_reduction == REDUCE_SUMSQ &&
                i_mask[lane]),
            .i_operand_a(i_a[lane*EW+:EW]),
            .i_operand_b(i_a[lane*EW+:EW]),
            .i_signed_a(i_signed),
            .i_signed_b(i_signed),
            .o_product(squares[lane*2*EW+:2*EW]),
            .o_valid(),
            .o_product_signed(),
            .o_zero(),
            .o_negative()
        );
    end

    wire [RA-1:0] reduced;
    wire [RA-1:0] squared_sum;
    wire [$clog2(NL+1)-1:0] count;

    vector_reduction #(
        .ELEMENT_WIDTH(EW),
        .NUM_ELEMENTS(NL),
        .ACC_WIDTH(RA),
        .LATENCY(0)
    ) u_reduction (
        .i_clk(1'b0),
        .i_rstb(1'b1),
        .i_clock_enable(1'b1),
        .i_valid(i_enable && i_operation == SFT_REDUCE),
        .i_opcode(i_reduction == REDUCE_MIN ? 3'd1 : i_reduction == REDUCE_MAX ? 3'd2 : 3'd0),
        .i_element_mask(i_mask),
        .i_data(i_a[NL*EW-1:0]),
        .i_signed(i_signed),
        .o_result(reduced),
        .o_active_count(count),
        .o_valid(),
        .o_result_format(),
        .o_result_signed(),
        .o_zero(),
        .o_negative(),
        .o_illegal_operation()
    );

    vector_reduction #(
        .ELEMENT_WIDTH(2 * EW),
        .NUM_ELEMENTS(NL),
        .ACC_WIDTH(RA),
        .LATENCY(0)
    ) u_square_sum (
        .i_clk(1'b0),
        .i_rstb(1'b1),
        .i_clock_enable(1'b1),
        .i_valid(i_enable && i_operation == SFT_REDUCE && i_reduction == REDUCE_SUMSQ),
        .i_opcode(3'd0),
        .i_element_mask(i_mask),
        .i_data(squares),
        .i_signed(1'b0),
        .o_result(squared_sum),
        .o_active_count(),
        .o_valid(),
        .o_result_format(),
        .o_result_signed(),
        .o_zero(),
        .o_negative(),
        .o_illegal_operation()
    );

    wire signed [D:0] rounded;
    wire inexact;

    polynomial_unit_round #(
        .WIDTH(D + 1),
        .SHIFT_WIDTH(8)
    ) u_round (
        .i_value({i_signed && i_a[D-1], i_a}),
        .i_shift(i_shift),
        .i_nearest(i_round),
        .o_value(rounded),
        .o_inexact(inexact)
    );

    wire [OW-1:0] formatted;
    wire overflow;
    wire saturated;

    packer #(
        .NUM_ELEMENTS(1),
        .SRC_ELEMENT_WIDTH(D + 1),
        .DST_ELEMENT_WIDTH(OW),
        .SUPPORT_SATURATION(SUPPORT_SATURATION)
    ) u_format (
        .i_clk(1'b0),
        .i_rstb(1'b1),
        .i_flush(1'b0),
        .i_valid(i_enable && i_operation == SFT_FORMAT),
        .o_ready(),
        .i_data(rounded),
        .i_lane_valid(1'b1),
        .i_signed(i_signed),
        .i_saturate(i_saturate),
        .i_reverse(1'b0),
        .i_last(1'b1),
        .i_user(1'b0),
        .o_valid(),
        .i_ready(1'b1),
        .o_data(formatted),
        .o_lane_valid(),
        .o_overflow(),
        .o_saturated(),
        .o_any_overflow(overflow),
        .o_any_saturated(saturated),
        .o_last(),
        .o_user(),
        .o_config_error(),
        .o_busy()
    );

    assign o_count = 16'(count);

    always @* begin
        o_data = '0;
        o_flags = '0;

        case (i_operation)
            SFT_ALU: begin
                o_data = alu_data;
                o_flags[0] = alu_illegal;
                o_flags[1] = alu_overflow;
                o_flags[3] = alu_saturated;
            end
            SFT_MULTIPLY: o_data = i_signed ? D'($signed(product)) : D'(product);
            SFT_REDUCE: begin
                if (i_reduction == REDUCE_SUMSQ) o_data = D'(squared_sum);
                else o_data = i_signed ? D'($signed(reduced)) : D'(reduced);
                o_flags[8] = count == 0;
            end
            SFT_FORMAT: begin
                o_data = i_signed ? D'($signed(formatted[OW-1:0])) : D'(formatted[OW-1:0]);
                o_flags[1] = overflow;
                o_flags[3] = saturated;
                o_flags[4] = inexact;
            end
            default: begin end
        endcase
    end
endmodule
`default_nettype wire
