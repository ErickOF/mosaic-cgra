`timescale 1ns / 1ps

// Parallel element representation conversion; beat count and lane count hold.
module packer #(
    // Untyped arguments preserve illegal negative/X/Z values for the guard.
    parameter NUM_ELEMENTS = 4,
    parameter SRC_ELEMENT_WIDTH = 8,
    parameter DST_ELEMENT_WIDTH = 16,
    parameter USER_WIDTH = 1,
    parameter SUPPORT_SIGNED = 1,
    parameter SUPPORT_SATURATION = 1,
    parameter SUPPORT_REVERSE = 1,
    parameter REGISTER_OUTPUTS = 0,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((NUM_ELEMENTS >= 1) === 1'b1) && (^NUM_ELEMENTS !== 1'bx) &&
        ((SRC_ELEMENT_WIDTH >= 1) === 1'b1) && (^SRC_ELEMENT_WIDTH !== 1'bx) &&
        ((DST_ELEMENT_WIDTH >= 1) === 1'b1) && (^DST_ELEMENT_WIDTH !== 1'bx) &&
        ((USER_WIDTH >= 1) === 1'b1) && (^USER_WIDTH !== 1'bx) &&
        (SUPPORT_SIGNED === 0 || SUPPORT_SIGNED === 1) &&
        (SUPPORT_SATURATION === 0 || SUPPORT_SATURATION === 1) &&
        (SUPPORT_REVERSE === 0 || SUPPORT_REVERSE === 1) &&
        (REGISTER_OUTPUTS === 0 || REGISTER_OUTPUTS === 1) &&
        (ASYNC_RESET === 0 || ASYNC_RESET === 1),
    localparam int unsigned ELEMENTS = PARAMETERS_VALID ? NUM_ELEMENTS : 1,
    localparam int unsigned SRC_BITS = PARAMETERS_VALID ? SRC_ELEMENT_WIDTH : 1,
    localparam int unsigned DST_BITS = PARAMETERS_VALID ? DST_ELEMENT_WIDTH : 1,
    localparam int unsigned USER_BITS = PARAMETERS_VALID ? USER_WIDTH : 1,
    localparam int unsigned IN_DATA_WIDTH = ELEMENTS * SRC_BITS,
    localparam int unsigned OUT_DATA_WIDTH = ELEMENTS * DST_BITS
) (
    input  logic                      i_clk,
    input  logic                      i_rstb,
    input  logic                      i_flush,
    input  logic                      i_valid,
    output logic                      o_ready,
    input  logic [IN_DATA_WIDTH-1:0]  i_data,
    input  logic [ELEMENTS-1:0]       i_lane_valid,
    input  logic                      i_signed,
    input  logic                      i_saturate,
    input  logic                      i_reverse,
    input  logic                      i_last,
    input  logic [USER_BITS-1:0]      i_user,
    output logic                      o_valid,
    input  logic                      i_ready,
    output logic [OUT_DATA_WIDTH-1:0] o_data,
    output logic [ELEMENTS-1:0]       o_lane_valid,
    output logic [ELEMENTS-1:0]       o_overflow,
    output logic [ELEMENTS-1:0]       o_saturated,
    output logic                      o_any_overflow,
    output logic                      o_any_saturated,
    output logic                      o_last,
    output logic [USER_BITS-1:0]      o_user,
    output logic                      o_config_error,
    output logic                      o_busy
);
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        packer_parameters_must_be_valid invalid_parameters ();
    end else begin : g_packer
        localparam int unsigned RESULT_WIDTH = OUT_DATA_WIDTH + 3 * ELEMENTS + 1 + USER_BITS;
        wire [IN_DATA_WIDTH-1:0] isolated_data;
        wire [OUT_DATA_WIDTH-1:0] direct_data, mapped_data;
        wire [ELEMENTS-1:0] direct_overflow, direct_saturated;
        wire [ELEMENTS-1:0] mapped_valid, mapped_overflow, mapped_saturated;
        wire signed_ok, saturation_ok, reverse_ok;

        for (genvar lane = 0; lane < ELEMENTS; lane++) begin : g_lane
            wire [SRC_BITS-1:0] source_element = isolated_data[lane*SRC_BITS+:SRC_BITS];
            wire [DST_BITS-1:0] converted;
            wire overflow, saturated;
            // Invalid/idle source elements cannot toggle conversion comparators.
            operand_isolation #(.WIDTH(SRC_BITS)) u_input_isolation (
                .i_data(i_data[lane*SRC_BITS+:SRC_BITS]),
                .i_isolate(!(i_valid & i_lane_valid[lane])),
                .o_data(isolated_data[lane*SRC_BITS+:SRC_BITS])
            );

            if (SRC_BITS < DST_BITS) begin : g_widen
                if (SUPPORT_SIGNED == 1) begin : g_signed
                    assign converted = i_signed ?
                        {{(DST_BITS-SRC_BITS){source_element[SRC_BITS-1]}}, source_element} :
                        {{(DST_BITS-SRC_BITS){1'b0}}, source_element};
                end else begin : g_unsigned
                    assign converted = {{(DST_BITS-SRC_BITS){1'b0}}, source_element};
                end
                assign overflow = 1'b0;
                assign saturated = 1'b0;
            end else if (SRC_BITS == DST_BITS) begin : g_equal
                assign converted = source_element;
                assign overflow = 1'b0;
                assign saturated = 1'b0;
            end else begin : g_narrow
                wire unsigned_overflow = |source_element[SRC_BITS-1:DST_BITS];
                if (SUPPORT_SIGNED == 1) begin : g_signed
                    // Compare discarded bits to the retained sign bit, while
                    // the ORIGINAL sign selects the direction of saturation.
                    wire signed_overflow = |(source_element[SRC_BITS-1:DST_BITS] ^
                        {(SRC_BITS-DST_BITS){source_element[DST_BITS-1]}});
                    assign overflow = i_signed ? signed_overflow : unsigned_overflow;
                end else begin : g_unsigned
                    assign overflow = unsigned_overflow;
                end
                if (SUPPORT_SATURATION == 1) begin : g_saturation
                    wire [DST_BITS-1:0] saturation_limit;
                    if (SUPPORT_SIGNED == 1) begin : g_signed_limit
                        assign saturation_limit = i_signed ?
                            (source_element[SRC_BITS-1] ? {1'b1, {(DST_BITS-1){1'b0}}} :
                                                         {1'b0, {(DST_BITS-1){1'b1}}}) : {DST_BITS{1'b1}};
                    end else begin : g_unsigned_limit
                        assign saturation_limit = {DST_BITS{1'b1}};
                    end
                    assign saturated = i_saturate & overflow;
                    assign converted = saturated ? saturation_limit : source_element[DST_BITS-1:0];
                end else begin : g_truncation
                    assign saturated = 1'b0;
                    assign converted = source_element[DST_BITS-1:0];
                end
            end
            assign direct_data[lane*DST_BITS+:DST_BITS] = converted;
            assign direct_overflow[lane] = overflow;
            assign direct_saturated[lane] = saturated;
            if (SUPPORT_REVERSE == 1) begin : g_reverse
                assign mapped_data[lane*DST_BITS+:DST_BITS] = i_reverse ?
                    direct_data[(ELEMENTS-1-lane)*DST_BITS+:DST_BITS] : direct_data[lane*DST_BITS+:DST_BITS];
                assign mapped_valid[lane] = i_reverse ? i_lane_valid[ELEMENTS-1-lane] : i_lane_valid[lane];
                assign mapped_overflow[lane] = i_reverse ? direct_overflow[ELEMENTS-1-lane] : direct_overflow[lane];
                assign mapped_saturated[lane] = i_reverse ? direct_saturated[ELEMENTS-1-lane] : direct_saturated[lane];
            end else begin : g_direct
                assign mapped_data[lane*DST_BITS+:DST_BITS] = direct_data[lane*DST_BITS+:DST_BITS];
                assign mapped_valid[lane] = i_lane_valid[lane];
                assign mapped_overflow[lane] = direct_overflow[lane];
                assign mapped_saturated[lane] = direct_saturated[lane];
            end
        end

        // Do not silently turn unknown active modes into supported requests.
        if (SUPPORT_SIGNED == 1) begin : g_signed_mode
            assign signed_ok = i_signed | !i_signed;
        end else begin : g_unsigned_mode
            assign signed_ok = !i_signed;
        end
        if (SUPPORT_SATURATION == 1 && SRC_BITS > DST_BITS) begin : g_saturation_mode
            assign saturation_ok = i_saturate | !i_saturate;
        end else begin : g_truncation_mode
            assign saturation_ok = !i_saturate;
        end
        if (SUPPORT_REVERSE == 1) begin : g_reverse_mode
            assign reverse_ok = i_reverse | !i_reverse;
        end else begin : g_direct_mode
            assign reverse_ok = !i_reverse;
        end
        wire running = i_rstb & !i_flush;
        wire configuration_ok = signed_ok & saturation_ok & reverse_ok;
        // Runtime controls are qualified by input valid; errors block new input
        // without reinterpreting an already captured registered result.
        assign o_config_error = running & i_valid & !configuration_ok;
        wire permitted = running & !o_config_error;
        wire [RESULT_WIDTH-1:0] result = {mapped_data, mapped_valid, mapped_overflow, mapped_saturated, i_last, i_user};
        wire [RESULT_WIDTH-1:0] selected_result, visible_result;

        if (REGISTER_OUTPUTS == 1) begin : g_registered
            wire stored_valid;
            wire [RESULT_WIDTH-1:0] stored_result;
            wire room = !stored_valid | i_ready;
            wire accept = permitted & i_valid & room;

            dff #(.WIDTH(RESULT_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_result (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(accept),
                .i_d(result),
                .o_q(stored_result)
            );

            dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_valid (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(i_flush | (running & room)),
                .i_d(!i_flush & i_valid & !o_config_error),
                .o_q(stored_valid)
            );

            assign o_ready = permitted & room;
            assign o_valid = running & stored_valid;
            assign o_busy = stored_valid;
            assign selected_result = stored_result;
        end else begin : g_combinational
            wire unused_clock = i_clk;
            assign o_ready = permitted & i_ready;
            assign o_valid = permitted & i_valid;
            assign o_busy = 1'b0;
            assign selected_result = result;
        end

        operand_isolation #(.WIDTH(RESULT_WIDTH)) u_output_clamp (
            .i_data(selected_result),
            .i_isolate(!o_valid),
            .o_data(visible_result)
        );

        assign {o_data, o_lane_valid, o_overflow, o_saturated, o_last, o_user} = visible_result;
        assign o_any_overflow = |o_overflow;
        assign o_any_saturated = |o_saturated;
    end
endmodule
