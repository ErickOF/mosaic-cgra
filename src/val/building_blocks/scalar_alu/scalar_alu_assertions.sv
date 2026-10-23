`timescale 1ns / 1ps

// Verification-only oracle uses widened mathematical arithmetic and constructs
// shifted bits individually. It does not read any DUT decode or arithmetic cone.
// FORMAL removes observation delays and proves the same complete output record.
module scalar_alu_assertions #(
    parameter int W = 32,
    parameter int SAT = 1,
    parameter int MINMAX = 1,
    localparam int R = W + 2,
    localparam int RESPONSE = W + 8
) (
    input logic i_enable,
    input logic [4:0] i_opcode,
    input logic [W-1:0] i_operand_a,
    input logic [W-1:0] i_operand_b,
    input logic i_predicate,
    input logic i_signed,
    input logic i_saturate,
    input logic [W-1:0] o_result,
    input logic o_predicate,
    input logic o_zero,
    input logic o_negative,
    input logic o_carry,
    input logic o_borrow,
    input logic o_overflow,
    input logic o_saturated,
    input logic o_illegal_operation
);
    wire [RESPONSE-1:0] actual = {o_result, o_predicate, o_zero, o_negative,
        o_carry, o_borrow, o_overflow, o_saturated, o_illegal_operation};

    function automatic logic [RESPONSE-1:0] reference_response(
        input logic enable,
        input logic [4:0] opcode,
        input logic [W-1:0] operand_a,
        input logic [W-1:0] operand_b,
        input logic predicate_input,
        input logic signed_mode,
        input logic saturate
    );
        logic illegal;
        logic need_signed;
        logic signed [R-1:0] a;
        logic signed [R-1:0] b;
        logic signed [R-1:0] numerical;
        logic signed [R-1:0] low_limit;
        logic signed [R-1:0] high_limit;
        logic [W-1:0] result;
        logic predicate;
        logic carry;
        logic borrow;
        logic overflow;
        logic saturated;
        logic [R-1:0] unsigned_sum;
        need_signed = (opcode <= 5'd1) ||
            (opcode >= 5'd11 && opcode <= 5'd14) ||
            (opcode >= 5'd18 && opcode <= 5'd19);
        illegal = ( ^ opcode === 1'bx) || opcode > 5'd19 ||
            ((opcode == 5'd18 || opcode == 5'd19) && MINMAX == 0) ||
            !(saturate === 1'b0 || (saturate === 1'b1 && opcode <= 5'd1 && SAT == 1)) ||
            (need_signed && !(signed_mode === 1'b0 || signed_mode === 1'b1)) ||
            (opcode == 5'd15 && !(predicate_input === 1'b0 || predicate_input === 1'b1));
        if (enable === 1'b0) return '0;
        if (enable !== 1'b1 || illegal) return {{(RESPONSE - 1){1'b0}}, 1'b1};
        a = R'(operand_a);
        b = R'(operand_b);
        if (signed_mode && need_signed && operand_a[W-1]) a = a - (R'(1) << W);
        if (signed_mode && need_signed && operand_b[W-1]) b = b - (R'(1) << W);
        low_limit = -(R'(1) << (W - 1));
        high_limit = (R'(1) << (W - 1)) - 1'b1;
        numerical = '0;
        result = '0;
        predicate = 1'b0;
        carry = 1'b0;
        borrow = 1'b0;
        overflow = 1'b0;
        saturated = 1'b0;
        unsigned_sum = R'(operand_a) + R'(operand_b);
        case (opcode)
            5'd0, 5'd1: begin
                numerical = opcode == 0 ? a + b : a - b;
                carry = opcode == 0 && unsigned_sum >= (R'(1) << W);
                borrow = opcode == 1 && operand_a < operand_b;
                overflow = signed_mode && (numerical < low_limit || numerical > high_limit);
                if (SAT == 1 && saturate) begin
                    if (signed_mode) begin
                        if (numerical < low_limit) begin
                            numerical = low_limit;
                            saturated = 1'b1;
                        end else if (numerical > high_limit) begin
                            numerical = high_limit;
                            saturated = 1'b1;
                        end
                    end else if (numerical < 0) begin
                        numerical = '0;
                        saturated = 1'b1;
                    end else if (numerical >= (R'(1) << W)) begin
                        numerical = (R'(1) << W) - 1'b1;
                        saturated = 1'b1;
                    end
                end
                result = numerical[W-1:0];
            end
            5'd2: result = operand_a & operand_b;
            5'd3: result = operand_a | operand_b;
            5'd4: result = operand_a ^ operand_b;
            5'd5: result = ~operand_a;
            5'd6, 5'd7, 5'd8: begin
                for (int bit_index = 0; bit_index < W; bit_index++) begin
                    if (opcode == 5'd6) begin
                        result[bit_index] = {1'b0, operand_b} <= (W + 1)'(bit_index) ?
                            operand_a[bit_index-int'(operand_b)] : 1'b0;
                    end else begin
                        result[bit_index] = {1'b0, operand_b} < (W + 1)'(W - bit_index) ?
                            operand_a[bit_index+int'(operand_b)] :
                            (opcode == 5'd8 && operand_a[W-1]);
                    end
                end
            end
            5'd9: predicate = a == b;
            5'd10: predicate = a != b;
            5'd11: predicate = a < b;
            5'd12: predicate = a <= b;
            5'd13: predicate = a > b;
            5'd14: predicate = a >= b;
            5'd15: result = predicate_input ? operand_a : operand_b;
            5'd16: result = operand_a;
            5'd17: result = operand_b;
            5'd18: result = a <= b ? operand_a : operand_b;
            5'd19: result = a >= b ? operand_a : operand_b;
            default: begin end
        endcase
        if (opcode >= 5'd9 && opcode <= 5'd14)
            result = {{(W - 1){1'b0}}, predicate};
        return {result, predicate, result == 0, result[W-1], carry, borrow,
            overflow, saturated, 1'b0};
    endfunction

    wire [RESPONSE-1:0] expected = reference_response(
        i_enable, i_opcode, i_operand_a, i_operand_b, i_predicate, i_signed, i_saturate);
`ifdef FORMAL
    always_comb assert (actual == expected);
`else
    // Active unknown operands are integration violations, even if masking happens
    // to produce a known result. Ignored operands and illegal requests are exempt.
    always @(*) begin
        #1ps;
        if (i_enable === 1'b1 && expected[0] === 1'b0) begin
            if (i_opcode != 5'd17 && (i_opcode != 5'd15 || i_predicate === 1'b1)) begin
                assert ( ^ i_operand_a !== 1'bx)
                else $fatal(1, "SCALAR_ALU_PROTOCOL: i_operand_a");
            end
            if (i_opcode != 5'd5 && i_opcode != 5'd16 &&
                (i_opcode != 5'd15 || i_predicate === 1'b0)) begin
                assert ( ^ i_operand_b !== 1'bx)
                else $fatal(1, "SCALAR_ALU_PROTOCOL: i_operand_b");
            end
        end
        assert (actual === expected)
        else $fatal(1, "SCALAR_ALU_HDL: result/predicate/flags/legality");
    end
`endif
endmodule
