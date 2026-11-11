`timescale 1ns / 1ps
`default_nettype none

// One physical integer lane. Functional units retain their declared latency;
// alignment paths merge their results with equally delayed suppression/legality.
module vector_lane #(
    parameter ELEMENT_WIDTH = 8,
    parameter ACC_WIDTH = 32,
    parameter ENABLE_ALU = 1,
    parameter SUPPORT_MUL = 1,
    parameter SUPPORT_MAC = 1,
    parameter SUPPORT_SATURATION = 1,
    parameter SUPPORT_MINMAX = 1,
    parameter LANE_LATENCY = 1,
    parameter MUL_LATENCY = 1,
    parameter MAC_LATENCY = 1,
    parameter MAX_LANE_LATENCY = 4,
    parameter ASYNC_RESET = 0,
    parameter OPCODE_WIDTH = 5,
    parameter RESULT_FORMAT_WIDTH = 2,
    localparam bit PARAMETERS_VALID =
        ((ELEMENT_WIDTH >= 1) === 1'b1) && ( ((^ELEMENT_WIDTH == 1'b0) || (^ELEMENT_WIDTH == 1'b1)) === 1'b1) &&
        ((ELEMENT_WIDTH <= 32'd268435400) === 1'b1) &&
        ((ACC_WIDTH >= 1) === 1'b1) && ( ((^ACC_WIDTH == 1'b0) || (^ACC_WIDTH == 1'b1)) === 1'b1) &&
        ((ACC_WIDTH <= 32'd536870800) === 1'b1) &&
        ((64'(ACC_WIDTH) >= 2 * 64'(ELEMENT_WIDTH)) === 1'b1) &&
        ((MAX_LANE_LATENCY >= 1) === 1'b1) && ( ((^MAX_LANE_LATENCY == 1'b0) || (^MAX_LANE_LATENCY == 1'b1)) === 1'b1) &&
        ((MAX_LANE_LATENCY <= 32'd2147483646) === 1'b1) &&
        ((LANE_LATENCY >= 0 && LANE_LATENCY <= MAX_LANE_LATENCY) === 1'b1) &&
        ( ((^LANE_LATENCY == 1'b0) || (^LANE_LATENCY == 1'b1)) === 1'b1) &&
        ((ENABLE_ALU === 0) || (ENABLE_ALU === 1)) &&
        ((SUPPORT_MUL === 0) || (SUPPORT_MUL === 1)) &&
        ((SUPPORT_MAC === 0) || (SUPPORT_MAC === 1)) &&
        ((SUPPORT_SATURATION === 0) || (SUPPORT_SATURATION === 1)) &&
        ((SUPPORT_MINMAX === 0) || (SUPPORT_MINMAX === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((SUPPORT_MUL === 0) ||
            ((MUL_LATENCY >= 0 && MUL_LATENCY <= LANE_LATENCY) === 1'b1 &&
                ( ((^MUL_LATENCY == 1'b0) || (^MUL_LATENCY == 1'b1)) === 1'b1))) &&
        ((SUPPORT_MAC === 0) ||
            ((MAC_LATENCY >= 0 && MAC_LATENCY <= LANE_LATENCY) === 1'b1 &&
                ( ((^MAC_LATENCY == 1'b0) || (^MAC_LATENCY == 1'b1)) === 1'b1))) &&
        (OPCODE_WIDTH === 5) && (RESULT_FORMAT_WIDTH === 2) &&
        (((128'(ACC_WIDTH) + 4 * 128'(ELEMENT_WIDTH) + 64) *
            (128'(LANE_LATENCY) + 1) * 8 < 128'd2147483647) === 1'b1),
    localparam int E = PARAMETERS_VALID ? ELEMENT_WIDTH : 1,
    localparam int A = PARAMETERS_VALID ? ACC_WIDTH : 2,
    localparam int L = PARAMETERS_VALID ? LANE_LATENCY : 0,
    localparam int ML = PARAMETERS_VALID && SUPPORT_MUL == 1 ? MUL_LATENCY : 0,
    localparam int MC = PARAMETERS_VALID && SUPPORT_MAC == 1 ? MAC_LATENCY : 0,
    localparam int PRODUCT_WIDTH = 2 * E
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_clock_enable,
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
    output wire o_valid,
    output wire o_write_enable,
    output wire o_suppressed,
    output wire o_illegal_operation,
    output wire [A-1:0] o_result,
    output wire [1:0] o_result_format,
    output wire o_result_signed,
    output wire o_predicate_valid,
    output wire o_predicate,
    output wire o_carry,
    output wire o_borrow,
    output wire o_overflow,
    output wire o_saturated,
    output wire o_zero,
    output wire o_negative
);
    import vector_lane_pkg::*;

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        vector_lane_parameters_must_be_valid invalid_parameters ();
    end else begin : g_lane
        // Width-dependent records remain local; opcode and format enums are shared.
        typedef struct packed {
            logic [A-1:0] result;
            vector_lane_result_format_t format;
            logic result_signed;
            logic predicate_valid;
            logic predicate;
            logic carry;
            logic borrow;
            logic overflow;
            logic saturated;
            logic zero;
            logic negative;
        } result_t;

        localparam int CONTROL_BITS = 11;
        localparam int PAYLOAD = $bits(result_t);
        wire input_active;

        if (L == 0) begin : g_combinational
            assign input_active = 1'b1;
        end else begin : g_registered
            assign input_active = (i_rstb === 1'b1) && (i_clock_enable === 1'b1);
        end

        logic suppressed;
        logic illegal;
        logic execute;
        logic alu_request;
        logic mul_request;
        logic mac_request;

        always_comb begin
            suppressed = 1'b0;
            illegal = 1'b0;
            execute = 1'b0;
            alu_request = 1'b0;
            mul_request = 1'b0;
            mac_request = 1'b0;

            if (input_active && i_valid === 1'b1) begin
                // A known mask wins before any unused predicate/opcode is decoded.
                case (i_lane_enable)
                    1'b0: suppressed = 1'b1;
                    1'b1: begin
                        case (i_predicate_enable)
                            1'b0: execute = 1'b1;
                            1'b1: begin
                                case (i_execute_predicate)
                                    1'b0: suppressed = 1'b1;
                                    1'b1: execute = 1'b1;
                                    default: illegal = 1'b1;
                                endcase
                            end
                            default: illegal = 1'b1;
                        endcase
                    end
                    default: illegal = 1'b1;
                endcase

                if (execute) begin
                    illegal = ( ^ {i_opcode, i_signed, i_saturate} === 1'bx) ||
                        i_opcode > VLANE_MAC ||
                        ((i_opcode == VLANE_MIN || i_opcode == VLANE_MAX) && SUPPORT_MINMAX == 0) ||
                        (i_opcode < VLANE_MUL &&!ENABLE_ALU) ||
                        (i_opcode == VLANE_MUL && SUPPORT_MUL == 0) ||
                        (i_opcode == VLANE_MAC && SUPPORT_MAC == 0) ||
                        (i_opcode == VLANE_SELECT &&
                            !(i_select_predicate === 1'b0 || i_select_predicate === 1'b1)) ||
                        (i_saturate && (SUPPORT_SATURATION == 0 ||
                            !(i_opcode == VLANE_ADD || i_opcode == VLANE_SUB ||
                                i_opcode == VLANE_MAC)));

                    if (!illegal) begin
                        alu_request = i_opcode <= VLANE_MAX;
                        mul_request = i_opcode == VLANE_MUL;
                        mac_request = i_opcode == VLANE_MAC;
                    end
                end
            end else if (input_active && i_valid !== 1'b0) illegal = 1'b1;
        end

        wire [E-1:0] alu_a;
        wire [E-1:0] alu_b;
        operand_isolation #(.WIDTH(2 * E)) u_alu_inputs (
            .i_data({i_operand_b, i_operand_a}),
            .i_isolate(!alu_request),
            .o_data({alu_b, alu_a})
        );

        wire [E-1:0] element_result;
        wire element_predicate;
        wire element_carry;
        wire element_borrow;
        wire element_overflow;
        wire element_saturated;
        wire unused_element_zero;
        wire unused_element_negative;
        wire unused_element_illegal;

        if (ENABLE_ALU) begin : g_alu
            scalar_alu #(.DATA_WIDTH(E), .SUPPORT_SATURATION(SUPPORT_SATURATION),
                .SUPPORT_MINMAX(SUPPORT_MINMAX)) u_alu (
                .i_enable(alu_request),
                .i_opcode(alu_request ? i_opcode : 5'b0),
                .i_operand_a(alu_a),
                .i_operand_b(alu_b),
                .i_predicate(alu_request && i_opcode == vector_lane_pkg::VLANE_SELECT &&
                    i_select_predicate),
                .i_signed(alu_request && i_signed),
                .i_saturate(alu_request && i_saturate),
                .o_result(element_result),
                .o_predicate(element_predicate),
                .o_zero(unused_element_zero),
                .o_negative(unused_element_negative),
                .o_carry(element_carry),
                .o_borrow(element_borrow),
                .o_overflow(element_overflow),
                .o_saturated(element_saturated),
                .o_illegal_operation(unused_element_illegal)
            );
        end else begin : g_no_alu
            assign element_result = '0;
            assign element_predicate = '0;
            assign unused_element_zero = '0;
            assign unused_element_negative = '0;
            assign element_carry = '0;
            assign element_borrow = '0;
            assign element_overflow = '0;
            assign element_saturated = '0;
            assign unused_element_illegal = '0;
        end

        result_t alu_payload;
        always_comb begin
            alu_payload = '0;
            if (alu_request) begin
                alu_payload.predicate_valid = i_opcode >= VLANE_EQ && i_opcode <= VLANE_GE;
                alu_payload.predicate = element_predicate;
                alu_payload.format = alu_payload.predicate_valid ?
                    VLANE_RESULT_BOOLEAN : VLANE_RESULT_ELEMENT;
                alu_payload.result_signed = !alu_payload.predicate_valid && i_signed;
                alu_payload.result = alu_payload.predicate_valid ? A'(element_predicate) :
                    {{(A - E){i_signed && element_result[E-1]}}, element_result};
                alu_payload.carry = !i_signed && element_carry;
                alu_payload.borrow = !i_signed && element_borrow;
                alu_payload.overflow = element_overflow;
                alu_payload.saturated = element_saturated;
                alu_payload.zero = alu_payload.result == 0;
                alu_payload.negative = alu_payload.result_signed && alu_payload.result[A-1];
            end
        end

        wire alu_aligned_valid;
        wire [PAYLOAD-1:0] alu_aligned;

        vector_lane_pipeline #(
            .WIDTH(PAYLOAD),
            .CONTROL_WIDTH(CONTROL_BITS),
            .DEPTH(L),
            .ASYNC_RESET(ASYNC_RESET != 0)
        ) u_alu_alignment (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_clock_enable(i_clock_enable),
            .i_valid(alu_request),
            .i_data(alu_payload),
            .o_valid(alu_aligned_valid),
            .o_data(alu_aligned)
        );

        wire mul_aligned_valid;
        wire [PAYLOAD-1:0] mul_aligned;
        if (SUPPORT_MUL == 1) begin : g_mul
            wire [E-1:0] mul_a;
            wire [E-1:0] mul_b;
            operand_isolation #(.WIDTH(2 * E)) u_inputs (
                .i_data({i_operand_b, i_operand_a}),
                .i_isolate(!mul_request),
                .o_data({mul_b, mul_a})
            );
            wire valid;
            wire [PRODUCT_WIDTH-1:0] product;
            wire product_signed;
            wire product_zero;
            wire product_negative;

            multiplier #(
                .OPERAND_WIDTH(E),
                .LATENCY(ML),
                .MAX_LATENCY(MAX_LANE_LATENCY),
                .ASYNC_RESET(ASYNC_RESET)
            ) u_unit (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_clock_enable(i_clock_enable),
                .i_valid(mul_request),
                .i_operand_a(mul_a),
                .i_operand_b(mul_b),
                .i_signed_a(mul_request && i_signed),
                .i_signed_b(mul_request && i_signed),
                .o_valid(valid),
                .o_product(product),
                .o_product_signed(product_signed),
                .o_zero(product_zero),
                .o_negative(product_negative)
            );

            result_t payload;
            always_comb begin
                payload = '0;

                if (valid) begin
                    payload.result = {{(A - PRODUCT_WIDTH){product_signed &&
                        product[PRODUCT_WIDTH-1]}}, product};

                    payload.format = VLANE_RESULT_PRODUCT;
                    payload.result_signed = product_signed;
                    payload.zero = product_zero;
                    payload.negative = product_negative;
                end
            end

            vector_lane_pipeline #(
                .WIDTH(PAYLOAD),
                .CONTROL_WIDTH(CONTROL_BITS),
                .DEPTH(L - ML),
                .ASYNC_RESET(ASYNC_RESET != 0)
            ) u_alignment (
                .i_clk(i_clk), .i_rstb(i_rstb), .i_clock_enable(i_clock_enable),
                .i_valid(valid), .i_data(payload),
                .o_valid(mul_aligned_valid), .o_data(mul_aligned)
            );
        end else begin : g_no_mul
            wire unused_request = mul_request;
            assign mul_aligned_valid = 1'b0;
            assign mul_aligned = '0;
        end

        wire mac_aligned_valid;
        wire [PAYLOAD-1:0] mac_aligned;

        if (SUPPORT_MAC == 1) begin : g_mac
            wire [E-1:0] mac_a;
            wire [E-1:0] mac_b;
            wire [A-1:0] mac_accumulator;
            operand_isolation #(.WIDTH(2 * E + A)) u_inputs (
                .i_data({i_accumulator, i_operand_b, i_operand_a}),
                .i_isolate(!mac_request),
                .o_data({mac_accumulator, mac_b, mac_a})
            );
            wire valid;
            wire [A-1:0] result;
            wire carry;
            wire overflow;
            wire saturated;
            wire zero;
            wire negative;
            wire unused_illegal;
            wire unused_modes_valid;
            wire result_signed;

            mac #(
                .OPERAND_WIDTH(E),
                .ACC_WIDTH(A),
                .SUPPORT_SATURATION(SUPPORT_SATURATION),
                .LATENCY(MC),
                .MAX_LATENCY(MAX_LANE_LATENCY),
                .ASYNC_RESET(ASYNC_RESET)
            ) u_unit (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_clock_enable(i_clock_enable),
                .i_valid(mac_request),
                .i_operand_a(mac_a),
                .i_operand_b(mac_b),
                .i_accumulator(mac_accumulator),
                .i_signed(mac_request && i_signed),
                .i_saturate(mac_request && i_saturate),
                .o_valid(valid),
                .o_result(result),
                .o_carry(carry),
                .o_overflow(overflow),
                .o_saturated(saturated),
                .o_zero(zero),
                .o_negative(negative),
                .o_illegal_operation(unused_illegal)
            );

            vector_lane_pipeline #(
                .WIDTH(1),
                .CONTROL_WIDTH(1),
                .DEPTH(MC),
                .ASYNC_RESET(ASYNC_RESET != 0)
            ) u_modes (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_clock_enable(i_clock_enable),
                .i_valid(mac_request),
                .i_data(mac_request && i_signed),
                .o_valid(unused_modes_valid),
                .o_data(result_signed)
            );

            result_t payload;
            always_comb begin
                payload = '0;

                if (valid) begin
                    payload.result = result;
                    payload.format = VLANE_RESULT_ACCUMULATOR;
                    payload.result_signed = result_signed;
                    payload.carry = carry;
                    payload.overflow = overflow;
                    payload.saturated = saturated;
                    payload.zero = zero;
                    payload.negative = negative;
                end
            end

            vector_lane_pipeline #(
                .WIDTH(PAYLOAD),
                .CONTROL_WIDTH(CONTROL_BITS),
                .DEPTH(L - MC),
                .ASYNC_RESET(ASYNC_RESET != 0)
            ) u_alignment (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_clock_enable(i_clock_enable),
                .i_valid(valid),
                .i_data(payload),
                .o_valid(mac_aligned_valid),
                .o_data(mac_aligned)
            );
        end else begin : g_no_mac
            wire [A:0] unused_inputs = {mac_request, i_accumulator};
            assign mac_aligned_valid = 1'b0;
            assign mac_aligned = '0;
        end

        wire output_suppressed;
        wire output_illegal;

        vector_lane_pipeline #(
            .WIDTH(2),
            .CONTROL_WIDTH(2),
            .DEPTH(L),
            .ASYNC_RESET(ASYNC_RESET != 0)
        ) u_response (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_clock_enable(i_clock_enable),
            .i_valid(i_valid),
            .i_data({suppressed, illegal}),
            .o_valid(o_valid),
            .o_data({output_suppressed, output_illegal})
        );

        wire unused_write_suppressed;

        write_gate u_write (
            .i_write_enable(o_valid === 1'b1),
            .i_suppress(output_suppressed || output_illegal),
            .o_write_enable(o_write_enable),
            .o_write_suppressed(unused_write_suppressed)
        );

        assign o_suppressed = o_valid && output_suppressed;
        assign o_illegal_operation = o_valid && output_illegal;

        result_t selected;

        always_comb begin
            selected = '0;

            if (o_write_enable) begin
                if (alu_aligned_valid) selected = alu_aligned;
                else if (mul_aligned_valid) selected = mul_aligned;
                else if (mac_aligned_valid) selected = mac_aligned;
            end
        end

        assign {o_result, o_result_format, o_result_signed, o_predicate_valid,
            o_predicate, o_carry, o_borrow, o_overflow, o_saturated, o_zero, o_negative} = selected;

`ifdef MOSAIC_VECTOR_LANE_ASSERTIONS
        vector_lane_assertions #(
            .E(E),
            .A(A),
            .L(L),
            .ASYNC_RESET(ASYNC_RESET),
            .MUL(SUPPORT_MUL),
            .MAC(SUPPORT_MAC),
            .SAT(SUPPORT_SATURATION),
            .MINMAX(SUPPORT_MINMAX)
        ) u_assertions (
            .i_path_valid({mac_aligned_valid, mul_aligned_valid, alu_aligned_valid}), .*
        );
`endif
    end
endmodule
`default_nettype wire
