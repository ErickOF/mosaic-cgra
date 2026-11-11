`timescale 1ns / 1ps

// Persistent, typed integer lanes. Global legality is resolved before any lane
// may write, so a single bad selected lane cancels the entire vector command.
module accumulator #(
    parameter ACC_WIDTH = 32,
    parameter NUM_LANES = 1,
    parameter SUPPORT_SUBTRACT = 1,
    parameter SUPPORT_SATURATION = 1,
    parameter ASYNC_RESET = 0,
    parameter COMMAND_WIDTH = 2,
    localparam bit PARAMETERS_VALID =
        ((ACC_WIDTH >= 1) === 1'b1) &&
        ((NUM_LANES >= 1) === 1'b1) &&
        ((SUPPORT_SUBTRACT === 0) || (SUPPORT_SUBTRACT === 1)) &&
        ((SUPPORT_SATURATION === 0) || (SUPPORT_SATURATION === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) && (COMMAND_WIDTH === 2),
    localparam int unsigned WORD_BITS = PARAMETERS_VALID ? ACC_WIDTH : 1,
    localparam int unsigned LANES = PARAMETERS_VALID ? NUM_LANES : 1,
    localparam int unsigned COMMAND_BITS = 2,
    localparam int unsigned DATA_WIDTH = WORD_BITS * LANES,
    localparam int unsigned RESPONSE_WIDTH = 2 + 7 * LANES
) (
    input  logic                     i_clk,
    input  logic                     i_rstb,
    input  logic                     i_clock_enable,
    input  logic                     i_valid,
    input  logic [COMMAND_BITS-1:0]   i_command,
    input  logic [LANES-1:0]          i_lane_mask,
    input  logic [DATA_WIDTH-1:0]     i_data,
    input  logic                     i_signed,
    input  logic                     i_saturate,
    output logic                     o_valid,
    output logic                     o_illegal_operation,
    output logic [LANES-1:0]          o_updated_mask,
    output logic [DATA_WIDTH-1:0]     o_data,
    output logic [LANES-1:0]          o_state_valid,
    output logic [LANES-1:0]          o_state_signed,
    output logic [LANES-1:0]          o_carry,
    output logic [LANES-1:0]          o_borrow,
    output logic [LANES-1:0]          o_overflow,
    output logic [LANES-1:0]          o_saturated,
    output logic [LANES-1:0]          o_zero,
    output logic [LANES-1:0]          o_negative
);
    import accumulator_pkg::*;

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        accumulator_parameters_must_be_valid invalid_parameters ();
    end else begin : g_bank
        logic is_clear, is_load, is_add, is_sub, known_command;
        wire subtract_illegal, saturation_illegal;
        wire [LANES-1:0] lane_illegal, write_enable, write_isolate;
        wire [LANES-1:0] unused_write_mask;
        wire illegal;
        wire execute_command = (i_rstb === 1'b1) && (i_clock_enable === 1'b1)
            && (i_valid === 1'b1) && !illegal;
        wire [DATA_WIDTH-1:0] state_data;
        wire [LANES-1:0] state_signed;
        wire [LANES-1:0] next_carry, next_borrow, next_overflow;
        wire [LANES-1:0] next_saturated, next_zero, next_negative;
        logic [RESPONSE_WIDTH-1:0] response;

        // Exact decoding preserves X/Z commands as illegal. No wildcard opcode
        // matching or two-state cast is allowed at the acceptance boundary.
        always_comb begin
            is_clear = 1'b0;
            is_load = 1'b0;
            is_add = 1'b0;
            is_sub = 1'b0;
            known_command = 1'b1;
            case (i_command)
                ACC_CLEAR: is_clear = 1'b1;
                ACC_LOAD:  is_load = 1'b1;
                ACC_ADD:   is_add = 1'b1;
                ACC_SUB:   is_sub = 1'b1;
                default: known_command = 1'b0;
            endcase
        end
        if (SUPPORT_SUBTRACT == 1) begin : g_subtract_supported
            assign subtract_illegal = 1'b0;
        end else begin : g_no_subtract
            assign subtract_illegal = is_sub;
        end
        if (SUPPORT_SATURATION == 1) begin : g_saturation_supported
            assign saturation_illegal = ((i_saturate !== 1'b0) && (i_saturate !== 1'b1))
                || (i_saturate && (is_clear || is_load));
        end else begin : g_no_saturation
            assign saturation_illegal = i_saturate !== 1'b0;
        end
        assign illegal = !known_command || subtract_illegal || saturation_illegal
            || ((i_signed !== 1'b0) && (i_signed !== 1'b1))
            || (^i_lane_mask === 1'bx) || (|lane_illegal);

        lane_mask #(.LANES(LANES)) u_write_selection (
            .i_operation_valid(execute_command),
            .i_lane_valid({LANES{1'b1}}),
            .i_lane_mask(i_lane_mask),
            .i_lane_predicate({LANES{1'b1}}),
            .o_lane_active(write_enable),
            .o_lane_isolate(write_isolate),
            .o_lane_write_mask(unused_write_mask)
        );

        // An enabled bubble clears response status. A disabled clock holds the
        // entire response, including valid; users must commit it only once.
        always_comb begin
            response = '0;
            case (i_valid)
                1'b0: begin end
                1'b1: response = {1'b1, illegal, write_enable, next_carry,
                    next_borrow, next_overflow, next_saturated, next_zero, next_negative};
                default: response = {1'bx, 1'b1, {(7*LANES){1'b0}}};
            endcase
        end
        dff #(.WIDTH(RESPONSE_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_response (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(i_clock_enable),
            .i_d(response),
            .o_q({o_valid, o_illegal_operation, o_updated_mask, o_carry,
                o_borrow, o_overflow, o_saturated, o_zero, o_negative})
        );

        for (genvar k = 0; k < LANES; k++) begin : g_lane
            wire [WORD_BITS-1:0] value = state_data[k*WORD_BITS+:WORD_BITS];
            wire [WORD_BITS-1:0] input_value = i_data[k*WORD_BITS+:WORD_BITS];
            wire initialize_lane = write_enable[k] && (is_clear || is_load);
            wire [WORD_BITS-1:0] add_left, add_right, add_result;
            wire [WORD_BITS:0] add_sum;
            wire add_overflow;
            wire [WORD_BITS-1:0] sub_result;
            wire sub_borrow, sub_overflow;
            wire [WORD_BITS-1:0] modular_result;
            wire arithmetic_carry, arithmetic_borrow, arithmetic_overflow;
            wire [WORD_BITS-1:0] final_arithmetic;
            wire saturated;
            logic [WORD_BITS-1:0] result;

            // Invalid/unselected state never contributes a numeric zero to ADD
            // or SUB. Typed initialization is mandatory for each selected lane.
            assign lane_illegal[k] = (i_lane_mask[k] === 1'b1) && (is_add || is_sub)
                && ((o_state_valid[k] !== 1'b1) || (state_signed[k] !== i_signed));

            operand_isolation #(.WIDTH(WORD_BITS)) u_add_left (
                .i_data(value),
                .i_isolate(write_isolate[k] || !is_add),
                .o_data(add_left)
            );

            operand_isolation #(.WIDTH(WORD_BITS)) u_add_right (
                .i_data(input_value),
                .i_isolate(write_isolate[k] || !is_add),
                .o_data(add_right)
            );

            assign add_sum = {1'b0, add_left} + {1'b0, add_right};
            assign add_result = add_sum[WORD_BITS-1:0];
            assign add_overflow = !(add_left[WORD_BITS-1] ^ add_right[WORD_BITS-1])
                && (add_result[WORD_BITS-1] ^ add_left[WORD_BITS-1]);

            if (SUPPORT_SUBTRACT == 1) begin : g_subtract
                wire [WORD_BITS-1:0] sub_left, sub_right;

                operand_isolation #(.WIDTH(WORD_BITS)) u_sub_left (
                    .i_data(value),
                    .i_isolate(write_isolate[k] || !is_sub),
                    .o_data(sub_left)
                );

                operand_isolation #(.WIDTH(WORD_BITS)) u_sub_right (
                    .i_data(input_value),
                    .i_isolate(write_isolate[k] || !is_sub),
                    .o_data(sub_right)
                );

                assign sub_result = sub_left - sub_right;
                assign sub_borrow = sub_left < sub_right;
                assign sub_overflow = (sub_left[WORD_BITS-1] ^ sub_right[WORD_BITS-1])
                    && (sub_result[WORD_BITS-1] ^ sub_left[WORD_BITS-1]);
            end else begin : g_no_subtract
                assign sub_result = '0;
                assign sub_borrow = 1'b0;
                assign sub_overflow = 1'b0;
            end

            assign modular_result = is_sub ? sub_result : add_result;
            assign arithmetic_carry = !i_signed && is_add && add_sum[WORD_BITS];
            assign arithmetic_borrow = !i_signed && is_sub && sub_borrow;
            assign arithmetic_overflow = i_signed && (is_sub ? sub_overflow : add_overflow);

            if (SUPPORT_SATURATION == 1) begin : g_saturation
                localparam logic [WORD_BITS-1:0] SIGNED_MIN = {1'b1, {(WORD_BITS-1){1'b0}}};
                localparam logic [WORD_BITS-1:0] SIGNED_MAX = ~SIGNED_MIN;
                wire range_error = arithmetic_carry || arithmetic_borrow || arithmetic_overflow;
                wire [WORD_BITS-1:0] clamp = i_signed ? (value[WORD_BITS-1] ? SIGNED_MIN : SIGNED_MAX)
                    : (is_sub ? {WORD_BITS{1'b0}} : {WORD_BITS{1'b1}});
                assign final_arithmetic = i_saturate && range_error ? clamp : modular_result;
                assign saturated = i_saturate && range_error && (final_arithmetic != modular_result);
            end else begin : g_no_saturation
                assign final_arithmetic = modular_result;
                assign saturated = 1'b0;
            end

            always_comb begin
                result = '0;
                case (i_command)
                    ACC_CLEAR: result = '0;
                    ACC_LOAD: result = input_value;
                    ACC_ADD, ACC_SUB: result = final_arithmetic;
                    default: begin end
                endcase
            end

            assign next_carry[k] = write_enable[k] && arithmetic_carry;
            assign next_borrow[k] = write_enable[k] && arithmetic_borrow;
            assign next_overflow[k] = write_enable[k] && arithmetic_overflow;
            assign next_saturated[k] = write_enable[k] && (is_add || is_sub) && saturated;
            assign next_zero[k] = write_enable[k] && (result == '0);
            assign next_negative[k] = write_enable[k] && i_signed && result[WORD_BITS-1];

            // Tie data/metadata DFF resets inactive: reset invalidates the lane
            // without driving reset trees through wide payload storage.
            dff #(.WIDTH(WORD_BITS)) u_data (
                .i_clk(i_clk),
                .i_rstb(1'b1),
                .i_enable(write_enable[k]),
                .i_d(result),
                .o_q(state_data[k*WORD_BITS+:WORD_BITS])
            );

            dff #(.WIDTH(1)) u_signed (
                .i_clk(i_clk),
                .i_rstb(1'b1),
                .i_enable(initialize_lane),
                .i_d(i_signed),
                .o_q(state_signed[k])
            );

            dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_valid (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(initialize_lane),
                .i_d(1'b1),
                .o_q(o_state_valid[k])
            );

            operand_isolation #(.WIDTH(WORD_BITS)) u_invalid_data (
                .i_data(value), .i_isolate(!o_state_valid[k]),
                .o_data(o_data[k*WORD_BITS+:WORD_BITS])
            );

            assign o_state_signed[k] = o_state_valid[k] && state_signed[k];
        end

`ifdef MOSAIC_ACCUMULATOR_ASSERTIONS
        // Verification-only, port-based pre-edge/post-edge assertions. Omitted
        // from normal synthesis and available without hierarchy/bind support.
        accumulator_assertions #(.ACC_WIDTH(WORD_BITS), .NUM_LANES(LANES),
            .SUPPORT_SUBTRACT(SUPPORT_SUBTRACT), .SUPPORT_SATURATION(SUPPORT_SATURATION),
            .ASYNC_RESET(ASYNC_RESET)) u_assertions (.*);
`endif
    end
endmodule
