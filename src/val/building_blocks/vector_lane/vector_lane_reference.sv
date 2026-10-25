`timescale 1ns / 1ps

// Verification-only mathematical oracle. Wider signed integers preserve the
// exact product and sum; narrowing occurs explicitly at the operation boundary.
module vector_lane_reference #(
    parameter int E = 8,
    parameter int A = 32,
    parameter int MUL = 1,
    parameter int MAC = 1,
    parameter int SAT = 1,
    parameter int MINMAX = 1,
    localparam int R = A + 2 * E + 4
) (
    input logic i_valid,
    input logic i_lane_enable,
    input logic i_predicate_enable,
    input logic i_execute_predicate,
    input logic i_select_predicate,
    input logic [4:0] i_opcode,
    input logic [E-1:0] i_operand_a,
    input logic [E-1:0] i_operand_b,
    input logic [A-1:0] i_accumulator,
    input logic i_signed,
    input logic i_saturate,
    output logic [A+14:0] response
);
    function automatic logic [A+14:0] calculate;
        logic signed [R-1:0] left;
        logic signed [R-1:0] right;
        logic signed [R-1:0] accumulator;
        logic signed [R-1:0] raw;
        logic signed [R-1:0] low;
        logic signed [R-1:0] high;
        logic [E-1:0] element;
        logic [A-1:0] result;
        logic [1:0] format_value;
        logic signed_result;
        logic predicate_valid;
        logic predicate;
        logic carry;
        logic borrow;
        logic overflow;
        logic saturated;
        logic illegal;
        if (i_valid !== 1'b1) return '0;
        if (i_lane_enable === 1'b0 || (i_lane_enable === 1'b1 &&
            i_predicate_enable === 1'b1 && i_execute_predicate === 1'b0)) begin
            return {4'b1010, {(A + 11){1'b0}}};
        end
        illegal = i_lane_enable !== 1'b1 ||
            !(i_predicate_enable === 1'b0 || i_predicate_enable === 1'b1) ||
            (i_predicate_enable === 1'b1 &&
                !(i_execute_predicate === 1'b0 || i_execute_predicate === 1'b1)) ||
            ( ^ {i_opcode, i_signed, i_saturate} === 1'bx) || i_opcode > 21 ||
            (!MUL && i_opcode == 20) || (!MAC && i_opcode == 21) ||
            (!MINMAX && (i_opcode == 18 || i_opcode == 19)) ||
            (i_opcode == 15 && ( ^ i_select_predicate === 1'bx)) ||
            (i_saturate && (!SAT || !(i_opcode == 0 || i_opcode == 1 || i_opcode == 21)));
        if (illegal) return {4'b1001, {(A + 11){1'b0}}};
        left = R'(i_operand_a);
        right = R'(i_operand_b);
        accumulator = R'(i_accumulator);
        if (i_signed) begin
            if (i_operand_a[E-1]) left = left - (R'(1) << E);
            if (i_operand_b[E-1]) right = right - (R'(1) << E);
            if (i_accumulator[A-1]) accumulator = accumulator - (R'(1) << A);
        end
        low = i_signed ? -(R'(1) << (E - 1)) : 0;
        high = i_signed ? (R'(1) << (E - 1)) - 1 : (R'(1) << E) - 1;
        raw = '0;
        element = '0;
        result = '0;
        format_value = 2'b01;
        signed_result = i_signed;
        predicate_valid = 1'b0;
        predicate = 1'b0;
        carry = 1'b0;
        borrow = 1'b0;
        overflow = 1'b0;
        saturated = 1'b0;
        case (i_opcode)
            0, 1: begin
                raw = i_opcode == 0 ? left + right : left - right;
                carry = !i_signed && i_opcode == 0 && raw > high;
                borrow = !i_signed && i_opcode == 1 && raw < 0;
                overflow = i_signed && (raw < low || raw > high);
                saturated = i_saturate && (raw < low || raw > high);
                if (i_saturate && raw < low) raw = low;
                if (i_saturate && raw > high) raw = high;
                element = E'(raw);
            end
            2: element = i_operand_a & i_operand_b;
            3: element = i_operand_a | i_operand_b;
            4: element = i_operand_a ^ i_operand_b;
            5: element = ~i_operand_a;
            6: element = i_operand_b >= E ? '0 : i_operand_a << i_operand_b;
            7: element = i_operand_b >= E ? '0 : i_operand_a >> i_operand_b;
            8: begin
                if (i_operand_b >= E) element = {E{i_operand_a[E-1]}};
                else element = $signed(i_operand_a) >>> i_operand_b;
            end
            9: predicate = left == right;
            10: predicate = left != right;
            11: predicate = left < right;
            12: predicate = left <= right;
            13: predicate = left > right;
            14: predicate = left >= right;
            15: element = i_select_predicate ? i_operand_a : i_operand_b;
            16: element = i_operand_a;
            17: element = i_operand_b;
            18: element = E'(left < right ? left : right);
            19: element = E'(left > right ? left : right);
            20, 21: begin
                raw = left * right;
                format_value = 2'b10;
                if (i_opcode == 21) begin
                    raw = raw + accumulator;
                    format_value = 2'b11;
                    low = i_signed ? -(R'(1) << (A - 1)) : 0;
                    high = i_signed ? (R'(1) << (A - 1)) - 1 : (R'(1) << A) - 1;
                    carry = !i_signed && raw > high;
                    overflow = i_signed && (raw < low || raw > high);
                    saturated = i_saturate && (raw < low || raw > high);
                    if (i_saturate && raw < low) raw = low;
                    if (i_saturate && raw > high) raw = high;
                end
                result = A'(raw);
            end
            default: element = '0;
        endcase
        if (i_opcode >= 9 && i_opcode <= 14) begin
            predicate_valid = 1'b1;
            signed_result = 1'b0;
            format_value = 2'b00;
            result = A'(predicate);
        end else if (i_opcode < 20) begin
            result = A'(element);
            if (i_signed && element[E-1]) result = result - (A'(1) << E);
        end
        return {4'b1100, result, format_value, signed_result, predicate_valid, predicate,
            carry, borrow, overflow, saturated, result == 0, signed_result && result[A-1]};
    endfunction
    always_comb response = calculate();
endmodule
