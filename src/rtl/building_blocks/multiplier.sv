`timescale 1ns / 1ps

// Exact scalar multiplication with independently interpreted operands. The
// inferred multiplier is combinational; LATENCY adds enabled response registers,
// not arithmetic segmentation or an unreported narrowing/rounding operation.
module multiplier #(
    parameter OPERAND_WIDTH = 32,
    parameter LATENCY = 1,
    parameter MAX_LATENCY = 4,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((OPERAND_WIDTH >= 1) === 1'b1) &&
        ((MAX_LATENCY >= 1) === 1'b1) &&
        ((LATENCY >= 0) === 1'b1) && ((LATENCY <= MAX_LATENCY) === 1'b1) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        (((2 * 64'(OPERAND_WIDTH) + 3) * (64'(LATENCY) + 1) < 64'd2147483647) === 1'b1),
    localparam int W = PARAMETERS_VALID ? OPERAND_WIDTH : 1,
    localparam int L = PARAMETERS_VALID ? LATENCY : 0,
    localparam int PRODUCT_WIDTH = 2 * W
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_clock_enable,
    input logic i_valid,
    input logic [W-1:0] i_operand_a,
    input logic [W-1:0] i_operand_b,
    input logic i_signed_a,
    input logic i_signed_b,
    output logic o_valid,
    output logic [PRODUCT_WIDTH-1:0] o_product,
    output logic o_product_signed,
    output logic o_zero,
    output logic o_negative
);
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        multiplier_parameters_must_be_valid invalid_parameters ();
    end else begin : g_datapath
        localparam int PAYLOAD_WIDTH = PRODUCT_WIDTH + 3;
        wire input_active;

        if (L == 0) begin : g_combinational_enable
            wire [2:0] unused_clock_controls = {i_clk, i_rstb, i_clock_enable};
            assign input_active = i_valid;
        end else begin : g_registered_enable
            assign input_active = i_valid && i_clock_enable && i_rstb;
        end

        wire [W-1:0] isolated_a;
        wire [W-1:0] isolated_b;

        operand_isolation #(
            .WIDTH(W)
        ) u_operand_a (
            .i_data(i_operand_a),
            .i_isolate(!input_active),
            .o_data(isolated_a)
        );

        operand_isolation #(
            .WIDTH(W)
        ) u_operand_b (
            .i_data(i_operand_b),
            .i_isolate(!input_active),
            .o_data(isolated_b)
        );

        // Each extra operand bit preserves its own signed or unsigned range.
        // The low 2*W bits contain the complete product for all four modes; only
        // redundant sign extension is removed from the wider inferred result.
        wire signed_a = input_active && i_signed_a;
        wire signed_b = input_active && i_signed_b;
        wire signed [W:0] multiply_a = {signed_a && isolated_a[W-1], isolated_a};
        wire signed [W:0] multiply_b = {signed_b && isolated_b[W-1], isolated_b};
        wire signed [PRODUCT_WIDTH+1:0] full_product = multiply_a * multiply_b;
        wire [1:0] unused_product_extension = full_product[PRODUCT_WIDTH+1:PRODUCT_WIDTH];
        wire [PRODUCT_WIDTH-1:0] product = full_product[PRODUCT_WIDTH-1:0];
        wire product_signed = signed_a || signed_b;
        wire [PAYLOAD_WIDTH-1:0] payload = {
            product,
            product_signed,
            product == 0,
            product_signed && product[PRODUCT_WIDTH-1]
        };

        wire output_valid;
        wire [PAYLOAD_WIDTH-1:0] output_payload;

        if (L == 0) begin : g_combinational_response
            assign output_valid = i_valid;
            assign output_payload = payload;
        end else begin : g_pipeline
            wire valid[L+1];
            wire [PAYLOAD_WIDTH-1:0] data[L+1];
            assign valid[0] = i_valid;
            assign data[0] = payload;

            for (genvar stage = 0; stage < L; stage ++ ) begin : g_stage
                // Only validity resets. Unreset product and metadata are held
                // on bubbles and cannot escape the final valid-controlled clamp.
                dff #(
                    .ASYNC_RESET(ASYNC_RESET != 0)
                ) u_valid (
                    .i_clk(i_clk),
                    .i_rstb(i_rstb),
                    .i_enable(i_clock_enable),
                    .i_d(valid[stage]),
                    .o_q(valid[stage+1])
                );

                dff #(
                    .WIDTH(PAYLOAD_WIDTH)
                ) u_data (
                    .i_clk(i_clk),
                    .i_rstb(1'b1),
                    .i_enable(i_clock_enable && i_rstb && valid[stage]),
                    .i_d(data[stage]),
                    .o_q(data[stage+1])
                );
            end

            assign output_valid = valid[L];
            assign output_payload = data[L];
        end

        assign o_valid = output_valid;

        operand_isolation #(
            .WIDTH(PAYLOAD_WIDTH)
        ) u_output (
            .i_data(output_payload),
            .i_isolate(!output_valid),
            .o_data({o_product, o_product_signed, o_zero, o_negative})
        );

`ifdef MOSAIC_MULTIPLIER_ASSERTIONS
        // The verification-only checker uses a separate mathematical oracle and
        // enabled-edge history, and rejects X/Z active inputs before commit.
        multiplier_assertions #(
            .W(W),
            .L(L),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_assertions (
            .*
        );
`endif
    end
endmodule
