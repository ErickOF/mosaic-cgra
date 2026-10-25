`timescale 1ns / 1ps

// Parallel exact products feed a zero-padded balanced reduction tree. Latencies
// >= 2 register the products; the remaining stages register the final response.
// No persistent accumulation state or generated clock is introduced.
module dot_product #(
    parameter ELEMENT_WIDTH = 8,
    parameter NUM_TERMS = 4,
    parameter ACC_WIDTH = 32,
    parameter SUPPORT_ACCUMULATE = 1,
    parameter SUPPORT_SATURATION = 1,
    parameter LATENCY = 2,
    parameter MAX_LATENCY = 8,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((ELEMENT_WIDTH >= 1) === 1'b1) && ( ^ ELEMENT_WIDTH !== 1'bx) &&
        ((NUM_TERMS >= 1) === 1'b1) && ( ^ NUM_TERMS !== 1'bx) &&
        ((ACC_WIDTH >= 1) === 1'b1) && ( ^ ACC_WIDTH !== 1'bx) &&
        ((MAX_LATENCY >= 1) === 1'b1) && ( ^ MAX_LATENCY !== 1'bx) &&
        ((LATENCY >= 0) === 1'b1) && ((LATENCY <= MAX_LATENCY) === 1'b1) &&
        ( ^ LATENCY !== 1'bx) &&
        ((SUPPORT_ACCUMULATE === 0) || (SUPPORT_ACCUMULATE === 1)) &&
        ((SUPPORT_SATURATION === 0) || (SUPPORT_SATURATION === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((64'(ACC_WIDTH) >= 2 * 64'(ELEMENT_WIDTH) + 64'($clog2(
        NUM_TERMS
    ))) === 1'b1) && ((64'(NUM_TERMS) * 64'(ELEMENT_WIDTH) < 64'd2147483647) === 1'b1) &&
        ((64'(ACC_WIDTH) * (64'(LATENCY) + 1) < 64'd2147483647) === 1'b1) &&
        ((64'(NUM_TERMS) < 64'd536870912) === 1'b1),
    localparam int E = PARAMETERS_VALID ? ELEMENT_WIDTH : 1,
    localparam int N = PARAMETERS_VALID ? NUM_TERMS : 1,
    localparam int A = PARAMETERS_VALID ? ACC_WIDTH : 2,
    localparam int L = PARAMETERS_VALID ? LATENCY : 0,
    localparam int PACKED_WIDTH = N * E,
    localparam int PRODUCT_WIDTH = 2 * E,
    localparam int SUM_GROWTH = $clog2(N),
    localparam int REDUCTION_WIDTH = PRODUCT_WIDTH + SUM_GROWTH,
    localparam int ACTIVE_COUNT_WIDTH = $clog2(N + 1)
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_clock_enable,
    input logic i_valid,
    input logic [N-1:0] i_term_mask,
    input logic [PACKED_WIDTH-1:0] i_operand_a,
    input logic [PACKED_WIDTH-1:0] i_operand_b,
    input logic i_accumulate,
    input logic [A-1:0] i_accumulator,
    input logic i_signed,
    input logic i_saturate,
    output logic o_valid,
    output logic [A-1:0] o_result,
    output logic [ACTIVE_COUNT_WIDTH-1:0] o_active_count,
    output logic o_carry,
    output logic o_overflow,
    output logic o_saturated,
    output logic o_zero,
    output logic o_negative,
    output logic o_illegal_operation
);
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        dot_product_parameters_must_be_valid invalid_parameters ();
    end else begin : g_datapath
        localparam int LEAVES = 2 ** SUM_GROWTH;
        localparam int PAYLOAD_WIDTH = A + ACTIVE_COUNT_WIDTH + 5;
        localparam int PRODUCT_STAGES = L >= 2 ? 1 : 0;
        localparam int RESPONSE_STAGES = L - PRODUCT_STAGES;
        localparam logic [A-1:0] SIGNED_MIN = {1'b1, {(A - 1) {1'b0}}};
        localparam logic [A-1:0] SIGNED_MAX = ~ SIGNED_MIN;

        wire controls_known = ( ^ {i_term_mask, i_accumulate, i_signed, i_saturate} !== 1'bx);
        wire unsupported = (SUPPORT_ACCUMULATE == 0 && i_accumulate === 1'b1) ||
            (SUPPORT_SATURATION == 0 && i_saturate === 1'b1);
        wire request_illegal = (i_valid === 1'b1) && (!controls_known || unsupported);
        wire request_legal = (i_valid === 1'b1) && controls_known &&!unsupported;
        wire input_fire;
        if (L == 0) begin : g_combinational_enable
            wire [2:0] unused_clock_controls = {i_clk, i_rstb, i_clock_enable};
            assign input_fire = request_legal;
        end else begin : g_registered_enable
            assign input_fire = request_legal && (i_clock_enable === 1'b1) && (i_rstb === 1'b1);
        end

        wire work_valid;
        wire work_illegal;
        wire [N-1:0] work_mask;
        wire work_signed;
        wire work_accumulate;
        wire work_saturate;
        wire [A-1:0] work_accumulator;
        wire work_legal;

        if (PRODUCT_STAGES == 1) begin : g_product_controls
            // Only response controls reset. Stale metadata and product data are
            // hidden by the registered valid/illegal controls and aligned mask.
            dff #(
                .WIDTH(2),
                .ASYNC_RESET(ASYNC_RESET != 0)
            ) u_control (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(i_clock_enable),
                .i_d({i_valid, request_illegal}),
                .o_q({work_valid, work_illegal})
            );

            dff #(
                .WIDTH(N)
            ) u_mask (
                .i_clk(i_clk),
                .i_rstb(1'b1),
                .i_enable(input_fire),
                .i_d(i_term_mask),
                .o_q(work_mask)
            );

            dff #(
                .WIDTH(3)
            ) u_modes (
                .i_clk(i_clk),
                .i_rstb(1'b1),
                .i_enable(input_fire),
                .i_d({i_signed, i_accumulate, i_saturate}),
                .o_q({work_signed, work_accumulate, work_saturate})
            );

            if (SUPPORT_ACCUMULATE == 1) begin : g_accumulator
                dff #(
                    .WIDTH(A)
                ) u_data (
                    .i_clk(i_clk),
                    .i_rstb(1'b1),
                    .i_enable(input_fire && i_accumulate),
                    .i_d(i_accumulator),
                    .o_q(work_accumulator)
                );
            end else begin : g_no_accumulator
                assign work_accumulator = '0;
            end
            assign work_legal = work_valid &&!work_illegal;
        end else begin : g_direct_controls
            assign work_valid = i_valid;
            assign work_illegal = request_illegal;
            assign work_mask = i_term_mask;
            assign work_signed = i_signed;
            assign work_accumulate = i_accumulate;
            assign work_saturate = i_saturate;

            if (SUPPORT_ACCUMULATE == 1) begin : g_accumulator
                assign work_accumulator = i_accumulator;
            end else begin : g_no_accumulator
                assign work_accumulator = '0;
            end
            assign work_legal = input_fire;
        end

        wire signed_mode = work_legal && work_signed;
        wire [PRODUCT_WIDTH-1:0] products[N];

        for (genvar k = 0; k < LEAVES; k ++ ) begin : g_term
            if (k < N) begin : g_active
                wire term_enable = input_fire && i_term_mask[k];
                wire [E-1:0] isolated_a;
                wire [E-1:0] isolated_b;

                operand_isolation #(
                    .WIDTH(E)
                ) u_operand_a (
                    .i_data(i_operand_a[k*E+:E]),
                    .i_isolate(!term_enable),
                    .o_data(isolated_a)
                );

                operand_isolation #(
                    .WIDTH(E)
                ) u_operand_b (
                    .i_data(i_operand_b[k*E+:E]),
                    .i_isolate(!term_enable),
                    .o_data(isolated_b)
                );

                // One shared signed multiplier handles both modes. The extra
                // operand sign bits preserve unsigned magnitudes; the low 2*E
                // bits are the exact specified product in either mode.
                wire signed [E:0] multiply_a = {i_signed && isolated_a[E-1], isolated_a};
                wire signed [E:0] multiply_b = {i_signed && isolated_b[E-1], isolated_b};
                wire signed [PRODUCT_WIDTH+1:0] full_product = multiply_a * multiply_b;
                wire [1:0] unused_product_extension = full_product[PRODUCT_WIDTH+1:PRODUCT_WIDTH];
                wire [PRODUCT_WIDTH-1:0] product;

                if (PRODUCT_STAGES == 1) begin : g_registered
                    wire [PRODUCT_WIDTH-1:0] stored_product;

                    dff #(
                        .WIDTH(PRODUCT_WIDTH)
                    ) u_data (
                        .i_clk(i_clk),
                        .i_rstb(1'b1),
                        .i_enable(term_enable),
                        .i_d(full_product[PRODUCT_WIDTH-1:0]),
                        .o_q(stored_product)
                    );

                    operand_isolation #(
                        .WIDTH(PRODUCT_WIDTH)
                    ) u_output (
                        .i_data(stored_product),
                        .i_isolate(!(work_legal && work_mask[k])),
                        .o_data(product)
                    );
                end else begin : g_direct
                    assign product = full_product[PRODUCT_WIDTH-1:0];
                end
                assign products[k] = product;
            end
        end
        // Separate generated levels make the acyclic topology explicit to lint
        // and synthesis, including the single-leaf and odd-term profiles.
        for (genvar level = 0; level <= SUM_GROWTH; level ++ ) begin : g_level
            localparam int NODE_COUNT = LEAVES >> level;
            wire [REDUCTION_WIDTH-1:0] partial_sum[NODE_COUNT];
            wire [ACTIVE_COUNT_WIDTH-1:0] count[NODE_COUNT];

            for (genvar node = 0; node < NODE_COUNT; node ++ ) begin : g_node
                if (level == 0) begin : g_leaf
                    if (node < N) begin : g_active
                        assign partial_sum[node] = {
                            {SUM_GROWTH{signed_mode && products[node][PRODUCT_WIDTH-1]}},
                            products[node]
                        };
                        assign count[node] = ACTIVE_COUNT_WIDTH'(work_legal && work_mask[node]);
                    end else begin : g_padding
                        assign partial_sum[node] = '0;
                        assign count[node] = '0;
                    end
                end else begin : g_add
                    assign partial_sum[node] = g_level[level-1].partial_sum[2*node] +
                        g_level[level-1].partial_sum[2*node+1];
                    assign count[node] = g_level[level-1].count[2*node] +
                        g_level[level-1].count[2*node+1];
                end
            end
        end

        wire [REDUCTION_WIDTH-1:0] dot_sum = g_level[SUM_GROWTH].partial_sum[0];
        wire [ACTIVE_COUNT_WIDTH-1:0] active_count = g_level[SUM_GROWTH].count[0];
        wire [A-1:0] extended_dot = {
            {(A - REDUCTION_WIDTH) {signed_mode && dot_sum[REDUCTION_WIDTH-1]}}, dot_sum
        };
        wire [A-1:0] modular_result;
        wire carry;
        wire overflow;
        wire mathematical_negative;

        if (SUPPORT_ACCUMULATE == 1) begin : g_accumulation
            wire add_enable = work_legal && work_accumulate;
            wire [A-1:0] isolated_dot;
            wire [A-1:0] isolated_accumulator;

            operand_isolation #(
                .WIDTH(A)
            ) u_dot (
                .i_data(extended_dot),
                .i_isolate(!add_enable),
                .o_data(isolated_dot)
            );

            operand_isolation #(
                .WIDTH(A)
            ) u_accumulator (
                .i_data(work_accumulator),
                .i_isolate(!add_enable),
                .o_data(isolated_accumulator)
            );

            wire [A:0] exact_sum = {signed_mode && isolated_dot[A-1], isolated_dot} +
                {signed_mode && isolated_accumulator[A-1], isolated_accumulator};
            assign modular_result = add_enable ? exact_sum[A-1:0] : extended_dot;
            assign carry = add_enable &&!signed_mode && exact_sum[A];
            assign overflow = add_enable && signed_mode && (exact_sum[A] != exact_sum[A-1]);
            assign mathematical_negative = exact_sum[A];
        end else begin : g_no_accumulation
            wire [2*A:0] unused_accumulator_inputs = {
                i_accumulator, work_accumulator, work_accumulate
            };
            assign modular_result = extended_dot;
            assign carry = 1'b0;
            assign overflow = 1'b0;
            assign mathematical_negative = 1'b0;
        end

        wire [A-1:0] final_result;
        wire saturated;

        if (SUPPORT_SATURATION == 1) begin : g_saturation
            wire select_clamp = work_legal && work_saturate;
            wire clamp_overflow = select_clamp && overflow;
            wire clamp_carry = select_clamp && carry;
            wire negative_clamp = clamp_overflow && mathematical_negative;
            assign final_result = clamp_overflow ? (negative_clamp ? SIGNED_MIN : SIGNED_MAX) :
                clamp_carry ? {A{1'b1}} : modular_result;
            assign saturated = clamp_overflow || clamp_carry;
        end else begin : g_no_saturation
            wire [1:0] unused_saturation_controls = {work_saturate, mathematical_negative};
            assign final_result = modular_result;
            assign saturated = 1'b0;
        end

        wire [PAYLOAD_WIDTH-1:0] payload = {
            final_result,
            active_count,
            carry,
            overflow,
            saturated,
            final_result == 0,
            signed_mode && final_result[A-1]
        };

        wire output_valid;
        wire output_illegal;
        wire [PAYLOAD_WIDTH-1:0] output_payload;

        if (RESPONSE_STAGES == 0) begin : g_combinational_response
            assign output_valid = work_valid;
            assign output_illegal = work_illegal;
            assign output_payload = payload;
        end else begin : g_response_pipeline
            wire [1:0] control[RESPONSE_STAGES+1];
            wire [PAYLOAD_WIDTH-1:0] data[RESPONSE_STAGES+1];
            assign control[0] = {work_valid, work_illegal};
            assign data[0] = payload;

            for (genvar stage = 0; stage < RESPONSE_STAGES; stage ++ ) begin : g_stage
                dff #(
                    .WIDTH(2),
                    .ASYNC_RESET(ASYNC_RESET != 0)
                ) u_control (
                    .i_clk(i_clk),
                    .i_rstb(i_rstb),
                    .i_enable(i_clock_enable),
                    .i_d(control[stage]),
                    .o_q(control[stage+1])
                );

                dff #(
                    .WIDTH(PAYLOAD_WIDTH)
                ) u_data (
                    .i_clk(i_clk),
                    .i_rstb(1'b1),
                    .i_enable(i_clock_enable && i_rstb && control[stage][1] &&!control[stage][0]),
                    .i_d(data[stage]),
                    .o_q(data[stage+1])
                );
            end

            assign {output_valid, output_illegal} = control[RESPONSE_STAGES];
            assign output_payload = data[RESPONSE_STAGES];
        end
        assign o_valid = output_valid;
        assign o_illegal_operation = output_valid && output_illegal;

        operand_isolation #(
            .WIDTH(PAYLOAD_WIDTH)
        ) u_output (
            .i_data(output_payload),
            .i_isolate(!(output_valid &&!output_illegal)),
            .o_data({
                o_result, o_active_count, o_carry, o_overflow, o_saturated, o_zero, o_negative
            })
        );

`ifdef MOSAIC_DOT_PRODUCT_ASSERTIONS
        dot_product_assertions #(
            .E(E),
            .N(N),
            .A(A),
            .L(L),
            .ASYNC_RESET(ASYNC_RESET),
            .SUPPORT_ACCUMULATE(SUPPORT_ACCUMULATE),
            .SUPPORT_SATURATION(SUPPORT_SATURATION)
        ) u_assertions (
            .*
        );
`endif
    end
endmodule
