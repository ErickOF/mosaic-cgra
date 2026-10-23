`timescale 1ns / 1ps

// Combinational scalar execution. Legality is decoded before operand isolation;
// flags describe the final result, while arithmetic flags retain modular status.
module scalar_alu #(
    parameter DATA_WIDTH = 32,
    parameter SUPPORT_SATURATION = 1,
    parameter SUPPORT_MINMAX = 1,
    parameter OPCODE_WIDTH = 5,
    localparam bit PARAMETERS_VALID =
        ((DATA_WIDTH >= 1) === 1'b1) && ( ^ DATA_WIDTH !== 1'bx) &&
        ((DATA_WIDTH <= 32'd536870903) === 1'b1) &&
        ((SUPPORT_SATURATION === 0) || (SUPPORT_SATURATION === 1)) &&
        ((SUPPORT_MINMAX === 0) || (SUPPORT_MINMAX === 1)) &&
        (OPCODE_WIDTH === 5),
    localparam int W = PARAMETERS_VALID ? DATA_WIDTH : 1,
    localparam int O = PARAMETERS_VALID ? OPCODE_WIDTH : 5,
    localparam int SHIFT_WIDTH = W > 1 ? $clog2(W) : 1
) (
    input logic i_enable,
    input logic [O-1:0] i_opcode,
    input logic [W-1:0] i_operand_a,
    input logic [W-1:0] i_operand_b,
    input logic i_predicate,
    input logic i_signed,
    input logic i_saturate,
    output logic [W-1:0] o_result,
    output logic o_predicate,
    output logic o_zero,
    output logic o_negative,
    output logic o_carry,
    output logic o_borrow,
    output logic o_overflow,
    output logic o_saturated,
    output logic o_illegal_operation
);
    import scalar_alu_pkg::*;

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        scalar_alu_parameters_must_be_valid invalid_parameters ();
    end else begin : g_datapath
        logic opcode_legal;
        logic uses_signed;
        logic uses_predicate;
        logic arithmetic;
        logic comparison;
        logic controls_legal;
        logic active;
        logic uses_a;
        logic uses_b;

        // Plain case preserves all five opcode bits and rejects X/Z encodings.
        always_comb begin
            opcode_legal = 1'b1;
            uses_signed = 1'b0;
            uses_predicate = 1'b0;
            arithmetic = 1'b0;
            comparison = 1'b0;

            case (i_opcode)
                ALU_ADD, ALU_SUB: begin
                    arithmetic = 1'b1;
                    uses_signed = 1'b1;
                end
                ALU_AND, ALU_OR, ALU_XOR, ALU_NOT, ALU_SLL, ALU_SRL, ALU_SRA,
                ALU_PASS_A, ALU_PASS_B: begin end
                ALU_EQ, ALU_NE: comparison = 1'b1;
                ALU_LT, ALU_LE, ALU_GT, ALU_GE: begin
                    comparison = 1'b1;
                    uses_signed = 1'b1;
                end
                ALU_SELECT: uses_predicate = 1'b1;
                ALU_MIN, ALU_MAX: begin
                    opcode_legal = SUPPORT_MINMAX == 1;
                    uses_signed = 1'b1;
                end
                default: opcode_legal = 1'b0;
            endcase

            controls_legal = opcode_legal &&
                ((i_saturate === 1'b0) || (i_saturate === 1'b1 &&
                    arithmetic && SUPPORT_SATURATION == 1)) &&
                (!uses_signed || i_signed === 1'b0 || i_signed === 1'b1) &&
                (!uses_predicate || i_predicate === 1'b0 || i_predicate === 1'b1);
            active = (i_enable === 1'b1) && controls_legal;
            o_illegal_operation = (i_enable !== 1'b0) && !active;
            uses_a = active && i_opcode != ALU_PASS_B &&
                (i_opcode != ALU_SELECT || i_predicate === 1'b1);
            uses_b = active && i_opcode != ALU_NOT && i_opcode != ALU_PASS_A &&
                (i_opcode != ALU_SELECT || i_predicate === 1'b0);
        end

        wire [W-1:0] isolated_a;
        wire [W-1:0] isolated_b;

        operand_isolation #(.WIDTH(W)) u_operand_a (
            .i_data(i_operand_a),
            .i_isolate(!uses_a),
            .o_data(isolated_a)
        );

        operand_isolation #(.WIDTH(W)) u_operand_b (
            .i_data(i_operand_b),
            .i_isolate(!uses_b),
            .o_data(isolated_b)
        );

        wire [W-1:0] math_a;
        wire [W-1:0] math_b;

        operand_isolation #(.WIDTH(2 * W)) u_arithmetic_inputs (
            .i_data({isolated_b, isolated_a}),
            .i_isolate(!(active && arithmetic)),
            .o_data({math_b, math_a})
        );

        // One W+1-bit adder implements add/sub without losing the raw carry.
        // For subtraction its carry is no-borrow, converted at the output below.
        wire subtract = active && i_opcode == ALU_SUB;
        wire [W-1:0] complemented_b = math_b ^ {W{subtract}};
        wire [W:0] extended_sum = {1'b0, math_a} + {1'b0, complemented_b} +
            (W + 1)'(subtract);
        wire [W-1:0] modular_result = extended_sum[W-1:0];
        wire raw_carry = extended_sum[W];
        wire raw_borrow = !extended_sum[W];
        wire raw_overflow = (math_a[W-1] ^ modular_result[W-1]) &&
            (subtract ? math_a[W-1] ^ math_b[W-1] : !(math_a[W-1] ^ math_b[W-1]));
        wire [W-1:0] arithmetic_result;
        wire saturated;

        if (SUPPORT_SATURATION == 1) begin : g_saturation
            localparam logic [W-1:0] SIGNED_MIN = {1'b1, {(W - 1){1'b0}}};
            localparam logic [W-1:0] SIGNED_MAX = ~SIGNED_MIN;
            wire clamp = active && arithmetic && i_saturate &&
                (i_signed ? raw_overflow : subtract ? raw_borrow : raw_carry);
            wire [W-1:0] limit_value = i_signed ?
                (math_a[W-1] ? SIGNED_MIN : SIGNED_MAX) : (subtract ? {W{1'b0}} : {W{1'b1}});
            assign arithmetic_result = clamp ? limit_value : modular_result;
            assign saturated = clamp;
        end else begin : g_no_saturation
            assign arithmetic_result = modular_result;
            assign saturated = 1'b0;
        end

        // Sign-bit ordering avoids mixed signed/unsigned expression coercion.
        wire signed_order = active && uses_signed && i_signed;
        wire equal_operands = isolated_a == isolated_b;
        wire less = signed_order && (isolated_a[W-1] != isolated_b[W-1]) ?
            isolated_a[W-1] : isolated_a < isolated_b;
        wire [W-1:0] selected_result;
        wire unused_select_valid;

        mux #(.NUM_INPUTS(2), .DATA_WIDTH(W)) u_select (
            .i_data({isolated_a, isolated_b}),
            .i_select(i_predicate),
            .o_data(selected_result),
            .o_select_valid(unused_select_valid)
        );

        wire [W-1:0] minmax_result;
        if (SUPPORT_MINMAX == 1) begin : g_minmax
            wire choose_b = i_opcode == ALU_MIN ? !(less || equal_operands) : less;
            wire unused_valid;

            mux #(.NUM_INPUTS(2), .DATA_WIDTH(W)) u_minmax (
                .i_data({isolated_b, isolated_a}),
                .i_select(choose_b),
                .o_data(minmax_result),
                .o_select_valid(unused_valid)
            );
        end else begin : g_no_minmax
            assign minmax_result = '0;
        end

        // Test the complete B operand before narrowing the barrel-shifter input.
        // This also handles width one and non-power-of-two data widths.
        wire oversized_shift = {1'b0, isolated_b} >= (W + 1)'(W);
        wire [SHIFT_WIDTH-1:0] amount = isolated_b[SHIFT_WIDTH-1:0];
        wire signed [W-1:0] arithmetic_right = $signed(isolated_a) >>> amount;
        logic [W-1:0] result;
        logic predicate;
        always_comb begin
            result = '0;
            predicate = 1'b0;

            case (i_opcode)
                ALU_ADD, ALU_SUB: result = arithmetic_result;
                ALU_AND: result = isolated_a & isolated_b;
                ALU_OR: result = isolated_a | isolated_b;
                ALU_XOR: result = isolated_a ^ isolated_b;
                ALU_NOT: result = ~isolated_a;
                ALU_SLL: result = oversized_shift ? '0 : isolated_a << amount;
                ALU_SRL: result = oversized_shift ? '0 : isolated_a >> amount;
                ALU_SRA: result = oversized_shift ? {W{isolated_a[W-1]}} :
                    arithmetic_right;
                ALU_EQ: predicate = equal_operands;
                ALU_NE: predicate = !equal_operands;
                ALU_LT: predicate = less;
                ALU_LE: predicate = less || equal_operands;
                ALU_GT: predicate = !(less || equal_operands);
                ALU_GE: predicate = !less;
                ALU_SELECT: result = selected_result;
                ALU_PASS_A: result = isolated_a;
                ALU_PASS_B: result = isolated_b;
                ALU_MIN, ALU_MAX: result = minmax_result;
                default: begin end
            endcase

            if (comparison) result = {{(W - 1){1'b0}}, predicate};
            o_result = active ? result : '0;
            o_predicate = active && comparison && predicate;
            o_zero = active && (result == 0);
            o_negative = active && result[W-1];
            o_carry = active && i_opcode == ALU_ADD && raw_carry;
            o_borrow = active && i_opcode == ALU_SUB && raw_borrow;
            o_overflow = active && arithmetic && i_signed && raw_overflow;
            o_saturated = saturated;
        end

`ifdef MOSAIC_SCALAR_ALU_ASSERTIONS
        scalar_alu_assertions #(.W(W), .SAT(SUPPORT_SATURATION), .MINMAX(SUPPORT_MINMAX))
            u_assertions (.*);
`endif
    end
endmodule
