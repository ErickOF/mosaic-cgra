`timescale 1ns / 1ps

// Verification-only immediate assertions, instantiated by the DUT's optional
// MOSAIC_ACCUMULATOR_ASSERTIONS hook. A mathematical W+2-bit oracle compares
// pre-edge architectural state with the response and state after NBA updates.
// It intentionally has no dependency on the implementation's arithmetic nets.
module accumulator_assertions #(
    parameter integer ACC_WIDTH = 32,
    parameter integer NUM_LANES = 1,
    parameter integer SUPPORT_SUBTRACT = 1,
    parameter integer SUPPORT_SATURATION = 1,
    parameter integer ASYNC_RESET = 0
) (
    input wire i_clk, i_rstb, i_clock_enable, i_valid,
    input wire [1:0] i_command,
    input wire [NUM_LANES-1:0] i_lane_mask,
    input wire [NUM_LANES*ACC_WIDTH-1:0] i_data,
    input wire i_signed, i_saturate,
    input wire o_valid, o_illegal_operation,
    input wire [NUM_LANES-1:0] o_updated_mask,
    input wire [NUM_LANES*ACC_WIDTH-1:0] o_data,
    input wire [NUM_LANES-1:0] o_state_valid, o_state_signed,
    input wire [NUM_LANES-1:0] o_carry, o_borrow, o_overflow, o_saturated, o_zero, o_negative
);
    localparam integer MATH_WIDTH = ACC_WIDTH + 2;
    localparam integer RESPONSE_WIDTH = 2 + 7 * NUM_LANES;
    localparam logic signed [MATH_WIDTH-1:0] UNSIGNED_MAX = ({{(MATH_WIDTH-1){1'b0}}, 1'b1} << ACC_WIDTH) - 1'b1;
    localparam logic signed [MATH_WIDTH-1:0] SIGNED_MAX = ({{(MATH_WIDTH-1){1'b0}}, 1'b1} << (ACC_WIDTH-1)) - 1'b1;
    localparam logic signed [MATH_WIDTH-1:0] SIGNED_MIN = -( {{(MATH_WIDTH-1){1'b0}}, 1'b1} << (ACC_WIDTH-1));

    task automatic check_transition;
        logic [NUM_LANES*ACC_WIDTH-1:0] data_expected;
        logic [NUM_LANES-1:0] valid_expected, signed_expected;
        logic [NUM_LANES-1:0] updated, carry, borrow, overflow, saturated, zero_flag, negative_flag;
        logic [RESPONSE_WIDTH-1:0] response_expected;
        logic illegal;
        logic signed [MATH_WIDTH-1:0] left_value, right_value, mathematical, final_value;
        logic [ACC_WIDTH-1:0] wrapped;
        begin
            assert ((i_rstb === 1'b0) || (i_rstb === 1'b1))
                else $fatal(1, "Protocol assertion failed: i_rstb");
            assert ((i_clock_enable === 1'b0) || (i_clock_enable === 1'b1))
                else $fatal(1, "Protocol assertion failed: i_clock_enable");
            data_expected = o_data;
            valid_expected = o_state_valid;
            signed_expected = o_state_signed;
            response_expected = {o_valid, o_illegal_operation, o_updated_mask, o_carry,
                o_borrow, o_overflow, o_saturated, o_zero, o_negative};
            updated = '0;
            carry = '0;
            borrow = '0;
            overflow = '0;
            saturated = '0;
            zero_flag = '0;
            negative_flag = '0;
            illegal = 1'b0;
            if (!i_rstb) begin
                data_expected = '0;
                valid_expected = '0;
                signed_expected = '0;
                response_expected = '0;
            end else if (i_clock_enable) begin
                assert ((i_valid === 1'b0) || (i_valid === 1'b1))
                    else $fatal(1, "Protocol assertion failed: i_valid");
                response_expected = '0;
                if (i_valid) begin
                    illegal = (^i_command === 1'bx) || (^i_lane_mask === 1'bx)
                        || ((i_signed !== 1'b0) && (i_signed !== 1'b1))
                        || ((i_saturate !== 1'b0) && (i_saturate !== 1'b1));
                    if (i_command == 2'd3 && SUPPORT_SUBTRACT == 0) illegal = 1'b1;
                    if (i_saturate === 1'b1 && (SUPPORT_SATURATION == 0 || i_command < 2'd2)) illegal = 1'b1;
                    for (integer k = 0; k < NUM_LANES; k++) begin
                        if (i_lane_mask[k] === 1'b1 && i_command >= 2'd2
                                && (o_state_valid[k] !== 1'b1 || o_state_signed[k] !== i_signed)) illegal = 1'b1;
                    end
                    if (!illegal) begin
                        updated = i_lane_mask;
                        for (integer k = 0; k < NUM_LANES; k++) begin
                            if (i_lane_mask[k]) begin
                                if (i_command != 2'd0) begin
                                    assert (^i_data[k*ACC_WIDTH+:ACC_WIDTH] !== 1'bx)
                                        else $fatal(1, "Protocol assertion failed: active_data");
                                end
                                left_value = i_signed ? {{2{o_data[k*ACC_WIDTH+ACC_WIDTH-1]}}, o_data[k*ACC_WIDTH+:ACC_WIDTH]}
                                    : {2'b00, o_data[k*ACC_WIDTH+:ACC_WIDTH]};
                                right_value = i_signed ? {{2{i_data[k*ACC_WIDTH+ACC_WIDTH-1]}}, i_data[k*ACC_WIDTH+:ACC_WIDTH]}
                                    : {2'b00, i_data[k*ACC_WIDTH+:ACC_WIDTH]};
                                mathematical = '0;
                                case (i_command)
                                    2'd0: mathematical = '0;
                                    2'd1: mathematical = right_value;
                                    2'd2: mathematical = left_value + right_value;
                                    2'd3: mathematical = left_value - right_value;
                                endcase
                                wrapped = mathematical[ACC_WIDTH-1:0];
                                final_value = mathematical;
                                if (i_command >= 2'd2) begin
                                    if (i_signed) begin
                                        overflow[k] = mathematical < SIGNED_MIN || mathematical > SIGNED_MAX;
                                        if (i_saturate && mathematical < SIGNED_MIN) final_value = SIGNED_MIN;
                                        if (i_saturate && mathematical > SIGNED_MAX) final_value = SIGNED_MAX;
                                    end else begin
                                        carry[k] = i_command == 2'd2 && mathematical > UNSIGNED_MAX;
                                        borrow[k] = i_command == 2'd3 && mathematical < 0;
                                        if (i_saturate && mathematical < 0) final_value = '0;
                                        if (i_saturate && mathematical > UNSIGNED_MAX) final_value = UNSIGNED_MAX;
                                    end
                                    saturated[k] = i_saturate && final_value[ACC_WIDTH-1:0] != wrapped;
                                end
                                data_expected[k*ACC_WIDTH+:ACC_WIDTH] = final_value[ACC_WIDTH-1:0];
                                valid_expected[k] = 1'b1;
                                signed_expected[k] = i_signed;
                                zero_flag[k] = final_value[ACC_WIDTH-1:0] == '0;
                                negative_flag[k] = i_signed && final_value[ACC_WIDTH-1];
                            end
                        end
                    end
                    response_expected = {1'b1, illegal, updated, carry, borrow, overflow, saturated, zero_flag, negative_flag};
                end
            end
            // The checker samples old state at the actual event, then checks
            // committed outputs one precision tick later without driving RTL.
            #0.001;
            assert (o_data === data_expected && o_state_valid === valid_expected && o_state_signed === signed_expected)
                else $fatal(1, "Accumulator HDL state transition assertion failed");
            assert ({o_valid, o_illegal_operation, o_updated_mask, o_carry, o_borrow,
                o_overflow, o_saturated, o_zero, o_negative} === response_expected)
                else $fatal(1, "Accumulator HDL response transition assertion failed");
        end
    endtask

    if (ASYNC_RESET == 1) begin : g_async
        always @(posedge i_clk or negedge i_rstb) check_transition();
    end else begin : g_sync
        always @(posedge i_clk) check_transition();
    end
endmodule
