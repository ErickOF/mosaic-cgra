`timescale 1ns / 1ps

// Flat, verification-only mathematical oracle, independent of the DUT's trees.
// Subtractive two's-complement interpretation takes place before SUM or ordering.
module vector_reduction_reference #(
    parameter int E = 8,
    parameter int N = 4,
    parameter int A = 32,
    parameter int SUM = 1,
    parameter int MINMAX = 1,
    parameter int LOGICAL = 1,
    localparam int C = $clog2(N + 1),
    localparam int B = A + C + 7,
    localparam int R = E + $clog2(N) + 2
) (
    input logic i_valid,
    input logic [2:0] i_opcode,
    input logic [N-1:0] i_element_mask,
    input logic [N*E-1:0] i_data,
    input logic i_signed,
    output logic [B-1:0] response
);
    function automatic logic [B-1:0] calculate;
        logic signed [R-1:0] element;
        logic signed [R-1:0] value;
        logic [E-1:0] logical_value;
        logic [A-1:0] result;
        logic [1:0] format_value;
        int count;
        if (i_valid !== 1'b1) return '0;
        if (( ^ {i_opcode, i_element_mask, i_signed} === 1'bx) || i_opcode > 4 ||
            (i_opcode == 0 && !SUM) || ((i_opcode == 1 || i_opcode == 2) && !MINMAX) ||
            ((i_opcode == 3 || i_opcode == 4) && !LOGICAL) ||
            ((i_opcode == 1 || i_opcode == 2) && i_element_mask == 0)) begin
            return {1'b1, {(B - 2){1'b0}}, 1'b1};
        end
        count = 0;
        value = '0;
        logical_value = i_opcode == 3 ? '1 : '0;
        for (int k = 0; k < N; k++) begin
            if (i_element_mask[k]) begin
                element = R'(i_data[k*E+:E]);
                if (i_signed && i_data[k*E+E-1]) element = element - (R'(1) << E);
                case (i_opcode)
                    0: value = value + element;
                    1: if (count == 0 || element < value) value = element;
                    2: if (count == 0 || element > value) value = element;
                    3: logical_value = logical_value & i_data[k*E+:E];
                    4: logical_value = logical_value | i_data[k*E+:E];
                    default: value = '0;
                endcase
                count++;
            end
        end
        if (i_opcode == 3 || i_opcode == 4) begin
            value = R'(logical_value);
            if (i_signed && logical_value[E-1]) value = value - (R'(1) << E);
        end
        result = A'(value);
        format_value = i_opcode == 0 ? 2'b11 : 2'b01;
        return {1'b1, result, format_value, i_signed, C'(count), result == 0,
            i_signed && result[A-1], 1'b0};
    endfunction
    always_comb response = calculate();
endmodule
