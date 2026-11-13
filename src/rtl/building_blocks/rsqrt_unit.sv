`timescale 1ns / 1ps

// Fixed-point inverse square root with epsilon and three-product Newton refinement.
module rsqrt_unit #(
    parameter INPUT_WIDTH = 16,
    parameter INPUT_FRACTION_WIDTH = 8,
    parameter INTERNAL_WIDTH = 28,
    parameter INTERNAL_FRACTION_WIDTH = 22,
    parameter OUTPUT_WIDTH = 16,
    parameter OUTPUT_FRACTION_WIDTH = 12,
    parameter SEED_MANTISSA_ADDRESS_WIDTH = 6,
    parameter MAX_ITERATIONS = 2,
    parameter EVALUATION_ARCH = 0,
    parameter ZERO_RESULT_MODE = 0,
    parameter SUPPORT_EPSILON = 1,
    parameter OUTPUT_QUEUE_DEPTH = 2,
    parameter CONTEXT_ID_WIDTH = 8,
    parameter REQUEST_TAG_WIDTH = 8,
    parameter SEED_PROTECTION = 0,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((INPUT_WIDTH >= 1 && INPUT_WIDTH < 2147483647) === 1'b1) &&
        ( ((^INPUT_WIDTH == 1'b0) || (^INPUT_WIDTH == 1'b1)) === 1'b1) &&
        ((INPUT_FRACTION_WIDTH >= 1 && INPUT_FRACTION_WIDTH < 2147483647) === 1'b1) &&
        ( ((^INPUT_FRACTION_WIDTH == 1'b0) || (^INPUT_FRACTION_WIDTH == 1'b1)) === 1'b1) &&
        ((INTERNAL_WIDTH >= 1 && INTERNAL_WIDTH < 2147483647) === 1'b1) &&
        ( ((^INTERNAL_WIDTH == 1'b0) || (^INTERNAL_WIDTH == 1'b1)) === 1'b1) &&
        ((INTERNAL_FRACTION_WIDTH >= 1 && INTERNAL_FRACTION_WIDTH < 2147483647) === 1'b1) &&
        ( ((^INTERNAL_FRACTION_WIDTH == 1'b0) || (^INTERNAL_FRACTION_WIDTH == 1'b1)) === 1'b1) &&
        ((OUTPUT_WIDTH >= 1 && OUTPUT_WIDTH < 2147483647) === 1'b1) &&
        ( ((^OUTPUT_WIDTH == 1'b0) || (^OUTPUT_WIDTH == 1'b1)) === 1'b1) &&
        ((OUTPUT_FRACTION_WIDTH >= 1 && OUTPUT_FRACTION_WIDTH < 2147483647) === 1'b1) &&
        ( ((^OUTPUT_FRACTION_WIDTH == 1'b0) || (^OUTPUT_FRACTION_WIDTH == 1'b1)) === 1'b1) &&
        ((SEED_MANTISSA_ADDRESS_WIDTH >= 1 && SEED_MANTISSA_ADDRESS_WIDTH < 2147483647) === 1'b1) &&
        ( ((^SEED_MANTISSA_ADDRESS_WIDTH == 1'b0) || (^SEED_MANTISSA_ADDRESS_WIDTH == 1'b1)) === 1'b1) &&
        ((OUTPUT_QUEUE_DEPTH >= 1 && OUTPUT_QUEUE_DEPTH < 2147483647) === 1'b1) &&
        ( ((^OUTPUT_QUEUE_DEPTH == 1'b0) || (^OUTPUT_QUEUE_DEPTH == 1'b1)) === 1'b1) &&
        ((CONTEXT_ID_WIDTH >= 1 && CONTEXT_ID_WIDTH < 2147483647) === 1'b1) &&
        ( ((^CONTEXT_ID_WIDTH == 1'b0) || (^CONTEXT_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((REQUEST_TAG_WIDTH >= 1 && REQUEST_TAG_WIDTH < 2147483647) === 1'b1) &&
        ( ((^REQUEST_TAG_WIDTH == 1'b0) || (^REQUEST_TAG_WIDTH == 1'b1)) === 1'b1) &&
        ((MAX_ITERATIONS >= 0 && MAX_ITERATIONS < 1073741823) === 1'b1) &&
        ( ((^MAX_ITERATIONS == 1'b0) || (^MAX_ITERATIONS == 1'b1)) === 1'b1) &&
        ((EVALUATION_ARCH === 0) || (EVALUATION_ARCH === 1)) &&
        ((ZERO_RESULT_MODE === 0) || (ZERO_RESULT_MODE === 1)) &&
        ((SEED_PROTECTION === 0) || (SEED_PROTECTION === 1) ||
            (SEED_PROTECTION === 2)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((SUPPORT_EPSILON === 0) || (SUPPORT_EPSILON === 1)) &&
        ((INPUT_FRACTION_WIDTH < INPUT_WIDTH &&
            OUTPUT_FRACTION_WIDTH < OUTPUT_WIDTH &&
            64'(INTERNAL_WIDTH) >= 64'(INTERNAL_FRACTION_WIDTH) + 3 &&
            64'(INTERNAL_FRACTION_WIDTH) >= 64'(SEED_MANTISSA_ADDRESS_WIDTH) + 1 &&
            SEED_MANTISSA_ADDRESS_WIDTH < 30) === 1'b1) &&
        (((64'(INPUT_WIDTH) + 64'(INTERNAL_WIDTH) + 64'(OUTPUT_WIDTH) +
            64'(CONTEXT_ID_WIDTH) + 64'(REQUEST_TAG_WIDTH) + 128) <
            64'd2147483647 / (64'(MAX_ITERATIONS) * 3 +
            64'(OUTPUT_QUEUE_DEPTH) + 8)) === 1'b1) &&
        (((64'd2 << SEED_MANTISSA_ADDRESS_WIDTH) * (64'(INTERNAL_WIDTH) + 64) <
            64'd2147483647) === 1'b1),
    localparam int I = PARAMETERS_VALID ? INPUT_WIDTH : 2,
    localparam int IF = PARAMETERS_VALID ? INPUT_FRACTION_WIDTH : 1,
    localparam int W = PARAMETERS_VALID ? INTERNAL_WIDTH : 4,
    localparam int F = PARAMETERS_VALID ? INTERNAL_FRACTION_WIDTH : 2,
    localparam int O = PARAMETERS_VALID ? OUTPUT_WIDTH : 2,
    localparam int OF = PARAMETERS_VALID ? OUTPUT_FRACTION_WIDTH : 1,
    localparam int A = PARAMETERS_VALID ? SEED_MANTISSA_ADDRESS_WIDTH : 1,
    localparam int SEED_ADDRESS_WIDTH = A + 1,
    localparam int M = PARAMETERS_VALID ? MAX_ITERATIONS : 0,
    localparam int Q = PARAMETERS_VALID ? OUTPUT_QUEUE_DEPTH : 1,
    localparam int C = PARAMETERS_VALID ? CONTEXT_ID_WIDTH : 1,
    localparam int G = PARAMETERS_VALID ? REQUEST_TAG_WIDTH : 1,
    localparam int SEED_DEPTH = 1 << SEED_ADDRESS_WIDTH,
    localparam int ITERATION_WIDTH = M > 0 ? $clog2(M + 1) : 1,
    localparam int EFFECTIVE_MAGNITUDE_WIDTH = I + 1,
    localparam logic [W-1:0] NORMALIZED_ONE = W'(1) << F,
    localparam logic [W-1:0] NORMALIZED_FOUR = W'(1) << (F + 2),
    localparam logic [W-1:0] INTERNAL_THREE = W'(3) << F,
    localparam int INTERNAL_PRODUCT_WIDTH = 2 * W,
    localparam int OUTPUT_QUEUE_OCCUPANCY_WIDTH = $clog2(Q + 1)
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_drain,
    input logic i_flush,
    input logic i_error_clear,
    input logic i_request_valid,
    input logic [I-1:0] i_request_operand,
    input logic i_request_input_signed,
    input logic i_request_output_signed,
    input logic i_request_add_epsilon,
    input logic [I-1:0] i_request_epsilon,
    input logic [ITERATION_WIDTH-1:0] i_request_iterations,
    input logic i_request_round_mode,
    input logic i_request_predicate,
    input logic [C-1:0] i_request_context_id,
    input logic [G-1:0] i_request_tag,
    input logic i_result_ready,
    output logic o_request_ready,
    output logic o_result_valid,
    output logic [O-1:0] o_result_data,
    output logic o_result_output_signed,
    output logic [ITERATION_WIDTH-1:0] o_result_iterations,
    output logic [ITERATION_WIDTH-1:0] o_result_quality_id,
    output logic [C-1:0] o_result_context_id,
    output logic [G-1:0] o_result_tag,
    output logic o_result_epsilon_applied,
    output logic o_result_negative_input,
    output logic o_result_zero_input,
    output logic o_result_overflow,
    output logic o_result_underflow,
    output logic o_result_saturated,
    output logic o_result_rounded,
    output logic o_result_approximate,
    output logic o_result_predicated,
    output logic o_result_error,
    output logic [3:0] o_result_error_code,
    output logic [31:0] o_seed_image_id,
    output logic [31:0] o_seed_checksum,
    output logic [OUTPUT_QUEUE_OCCUPANCY_WIDTH-1:0] o_output_queue_occupancy,
    output logic o_busy,
    output logic o_idle,
    output logic o_quiescent,
    output logic o_drain_done,
    output logic o_flushed,
    output logic o_error,
    output logic [3:0] o_error_code,
    output logic o_fatal_error,
    output logic o_event_request_accept,
    output logic o_event_result_complete,
    output logic o_event_request_stall,
    output logic o_event_result_stall,
    output logic o_event_epsilon,
    output logic o_event_normalize,
    output logic o_event_seed_lookup,
    output logic o_event_iteration,
    output logic o_event_negative_input,
    output logic o_event_zero_input,
    output logic o_event_overflow,
    output logic o_event_underflow,
    output logic o_event_seed_corrected,
    output logic o_event_seed_uncorrectable
);
    import rsqrt_unit_pkg::*;

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        rsqrt_unit_parameters_must_be_valid invalid_parameters ();
    end else begin : g_unit
        localparam bit PROTECTED = SEED_PROTECTION != SEED_PROTECTION_NONE;
        localparam bit UNROLLED =
            EVALUATION_ARCH == rsqrt_unit_pkg::RSQRT_ARCH_UNROLLED;
        localparam int LATENCY = 4 + 3 * M;
        localparam int LANES = UNROLLED ? LATENCY : 1;
        localparam int PHASE = $clog2(LATENCY);

        // These types depend on the configured payload widths and remain local.
        typedef struct packed {
            logic [O-1:0] data;
            logic output_signed;
            logic [ITERATION_WIDTH-1:0] iterations;
            logic [C-1:0] context_id;
            logic [G-1:0] tag;
            logic epsilon_applied;
            logic negative_input;
            logic zero_input;
            logic overflow;
            logic underflow;
            logic saturated;
            logic rounded;
            logic approximate;
            logic predicated;
            logic error;
            logic [3:0] code;
        } result_t;

        typedef struct packed {
            logic [O-1:0] data;
            logic output_signed;
            logic [ITERATION_WIDTH-1:0] iterations;
            logic [C-1:0] context_id;
            logic [G-1:0] tag;
            logic epsilon_applied;
            logic negative_input;
            logic zero_input;
            logic overflow;
            logic underflow;
            logic saturated;
            logic rounded;
            logic approximate;
            logic predicated;
            logic error;
            logic [3:0] code;
            logic [I-1:0] operand;
            logic [I-1:0] epsilon;
            logic add_epsilon;
            logic [I:0] effective;
            logic nearest;
            logic exponent_parity;
            logic signed [31:0] exponent_value;
            logic [W-1:0] normalized;
            logic [W-1:0] estimate;
            logic [W-1:0] correction;
            logic [W-1:0] squared;
        } token_t;

        localparam int TOKEN = $bits(token_t);
        localparam int RESULT = $bits(result_t);
        wire reset_released;

        if (ASYNC_RESET == 1) begin : g_reset_release
            // Unknown reset cannot release ownership. Assertion is immediate;
            // acceptance waits for two clean clocks after asynchronous release.
            reset_synchronizer u_release (
                .i_clk(i_clk),
                .i_async_rstb(i_rstb !== 1'b0),
                .o_rstb(reset_released)
            );
        end else begin : g_sync_reset
            assign reset_released = i_rstb !== 1'b0;
        end

        wire running = i_rstb === 1'b1 && reset_released === 1'b1;
        wire flushing = running && i_flush === 1'b1;
        wire controls_known = ^ {i_rstb, i_flush, i_drain, i_request_valid,
            i_result_ready, i_error_clear} !== 1'bx;
        wire epsilon_used = SUPPORT_EPSILON == 1 && i_request_add_epsilon === 1'b1 &&
            i_request_predicate === 1'b1 && 32'(i_request_iterations) <= M &&
            !(i_request_input_signed === 1'b1 && i_request_operand[I-1] === 1'b1);
        wire request_known = ^ {i_request_operand, i_request_input_signed,
            i_request_output_signed, i_request_add_epsilon, i_request_iterations,
            i_request_round_mode, i_request_predicate, i_request_context_id,
            i_request_tag} !== 1'bx && (!epsilon_used || ^ i_request_epsilon !== 1'bx);
        wire fatal;
        wire [3:0] sticky_code;
        wire [LANES-1:0] lane_valid;
        wire [LANES-1:0] lane_ready;
        wire [LANES-1:0] state_corrupt;
        wire [LANES-1:0] epsilon_access;
        wire [LANES-1:0] normalize_access;
        wire [LANES-1:0] seed_access;
        wire [LANES-1:0] multiply_enable;
        wire [LANES-1:0] iteration_commit;
        wire [LANES-1:0] arithmetic_bad;
        wire [LANES-1:0] seed_bad;
        wire [LANES-1:0] seed_corrected;
        wire [LANES-1:0] identity_bad;
        wire [TOKEN-1:0] packet[LANES];
        wire [TOKEN-1:0] advanced[LANES];
        wire [PHASE-1:0] phase[LANES];
        wire [LANES-1:0] stage_move;
        wire queue_ready;
        wire queue_valid;
        wire queue_corrupt;
        wire [Q-1:0] queue_occupied;
        wire [Q*RESULT-1:0] unused_queue_contents;
        wire [OUTPUT_QUEUE_OCCUPANCY_WIDTH-1:0] occupancy;
        wire [RESULT-1:0] queue_data;
        result_t final_result;
        result_t visible_result;
        token_t request_packet;
        wire error_corrupt;
        wire [LANES-1:0] impossible_state;
        wire raw_corrupt = (|state_corrupt) || (|impossible_state) ||
            error_corrupt || queue_corrupt ||
            ($countones(queue_occupied) != 32'(occupancy));
        wire fatal_now = raw_corrupt || (|arithmetic_bad) || (|seed_bad) ||
            (|identity_bad);
        wire discard = flushing || fatal || fatal_now;
        wire work = (|lane_valid) || queue_valid;
        wire active_clock = running && !flushing && !fatal && !raw_corrupt;
        // Capacity uses the consumer's offered readiness independently of fatal
        // masking. A newly detected fault flushes all queues at this edge and
        // suppresses the public response, without creating a reverse-ready loop.
        wire result_pop = active_clock && (i_result_ready === 1'b1);
        wire [ITERATION_WIDTH-1:0] request_iterations;
        token_t iterative_packet;
        wire finish = stage_move[LANES-1] &&
            (UNROLLED ||
            32'(phase[0]) == 3 + 3 * 32'(request_iterations));
        assign iterative_packet = packet[0];
        assign request_iterations = iterative_packet.iterations;
        wire request_take = o_request_ready && i_request_valid === 1'b1;

        // Known illegal iteration counts use the zero-iteration iterative
        // latency (four cycles), or the fixed unrolled latency.
        always_comb begin : capture_request
            request_packet = '0;
            request_packet.output_signed = i_request_output_signed;
            request_packet.iterations = i_request_iterations;
            request_packet.context_id = i_request_context_id;
            request_packet.tag = i_request_tag;
            request_packet.operand = i_request_operand;
            request_packet.epsilon = epsilon_used ? i_request_epsilon : '0;
            request_packet.add_epsilon = epsilon_used;
            request_packet.nearest = i_request_round_mode;

            if (32'(i_request_iterations) > M) begin
                request_packet.error = 1'b1;
                request_packet.code = RSQRT_ERR_ITERATIONS;
                request_packet.iterations = '0;
            end else if (i_request_add_epsilon && SUPPORT_EPSILON == 0) begin
                request_packet.error = 1'b1;
                request_packet.code = RSQRT_ERR_EPSILON;
                request_packet.iterations = '0;
            end else if (!i_request_predicate)
                request_packet.predicated = 1'b1;
            else if (i_request_input_signed && i_request_operand[I-1]) begin
                request_packet.negative_input = 1'b1;
                request_packet.error = 1'b1;
                request_packet.code = RSQRT_ERR_NEGATIVE;
            end else
                request_packet.approximate = 1'b1;
        end

        for (genvar lane = 0; lane < LANES; lane++) begin : g_stage
            token_t q;
            token_t d;
            wire numeric_active;
            assign q = packet[lane];
            assign impossible_state[lane] = lane_valid[lane] &&
                (( ^ q === 1'bx) || 32'(q.iterations) > M ||
                (!UNROLLED &&
                32'(phase[lane]) > 3 + 3 * 32'(q.iterations)) ||
                (q.approximate && phase[lane] >= 2 &&
                (q.normalized < NORMALIZED_ONE || q.normalized >= NORMALIZED_FOUR ||
                $signed(q.exponent_value) < -(IF + 1) / 2 ||
                $signed(q.exponent_value) > I / 2 ||
                (phase[lane] >= 3 && q.estimate == 0))));
            assign advanced[lane] = d;
            assign numeric_active = stage_move[lane] && q.approximate &&
                !q.error && !q.predicated;
            assign epsilon_access[lane] = numeric_active && phase[lane] == 0 &&
                q.add_epsilon && q.epsilon != 0;
            assign normalize_access[lane] = numeric_active && phase[lane] == 1;
            assign seed_access[lane] = numeric_active && phase[lane] == 2;
            assign multiply_enable[lane] = numeric_active && phase[lane] >= 3 &&
                32'(phase[lane]) < 3 + 3 * 32'(q.iterations);
            wire [1:0] product_phase = 2'((32'(phase[lane]) - 3) % 3);
            assign iteration_commit[lane] = multiply_enable[lane] && product_phase == 2;

            wire [I:0] effective;

            if (!UNROLLED || lane == 0) begin : g_epsilon
                wire [I:0] sum_value;

                scalar_alu #(.DATA_WIDTH(I + 1)) u_add (
                    .i_enable(epsilon_access[lane]),
                    .i_opcode(scalar_alu_pkg::ALU_ADD),
                    .i_operand_a({1'b0, q.operand}),
                    .i_operand_b({1'b0, q.epsilon}),
                    .i_predicate(1'b1),
                    .i_signed(1'b0),
                    .i_saturate(1'b0),
                    .o_result(sum_value),
                    .o_predicate(),
                    .o_zero(),
                    .o_negative(),
                    .o_carry(),
                    .o_borrow(),
                    .o_overflow(),
                    .o_saturated(),
                    .o_illegal_operation()
                );

                assign effective = epsilon_access[lane] ? sum_value : {1'b0, q.operand};
            end else begin : g_no_epsilon
                assign effective = '0;
            end

            wire [W-1:0] normalized;
            wire signed [31:0] exponent_value;
            wire exponent_parity;
            wire normalization_inexact;

            if (!UNROLLED || lane == 1) begin : g_normalize
                rsqrt_unit_normalize #(.INPUT_WIDTH(I), .INTERNAL_WIDTH(W),
                    .INPUT_FRACTION_WIDTH(IF), .INTERNAL_FRACTION_WIDTH(F)) u_normalize (
                    .i_enable(normalize_access[lane]),
                    .i_magnitude(q.effective),
                    .i_nearest(q.nearest),
                    .o_normalized(normalized),
                    .o_half_exponent(exponent_value),
                    .o_parity(exponent_parity),
                    .o_inexact(normalization_inexact)
                );
            end else begin : g_no_normalize
                assign normalized = '0;
                assign exponent_value = '0;
                assign exponent_parity = 1'b0;
                assign normalization_inexact = 1'b0;
            end

            wire [W-1:0] seed;
            wire [W-1:0] mantissa = q.normalized >> q.exponent_parity;
            wire [SEED_ADDRESS_WIDTH-1:0] seed_address =
                {q.exponent_parity, A'((mantissa - NORMALIZED_ONE) >> (F - A))};

            if (!UNROLLED || lane == 2) begin : g_seed
                rsqrt_unit_seed #(.WIDTH(W), .FRACTION(F), .MANTISSA_ADDRESS(A),
                    .PROTECTION(SEED_PROTECTION)) u_seed (
                    .i_enable(seed_access[lane]),
                    .i_address(seed_address),
                    .o_seed(seed),
                    .o_corrected(seed_corrected[lane]),
                    .o_bad(seed_bad[lane]),
                    .o_image_id(o_seed_image_id),
                    .o_checksum(o_seed_checksum)
                );
                assign identity_bad[lane] = running &&
                    (o_seed_image_id !== u_seed.IMAGE_ID ||
                    o_seed_checksum !== u_seed.CHECKSUM);
            end else begin : g_no_seed
                assign seed = '0;
                assign seed_corrected[lane] = 1'b0;
                assign seed_bad[lane] = 1'b0;
                assign identity_bad[lane] = 1'b0;
            end

            wire [W-1:0] newton_value;
            wire newton_inexact;

            if (!UNROLLED ||
                (lane >= 3 && lane < LATENCY - 1)) begin : g_newton
                rsqrt_unit_newton #(.WIDTH(W), .FRACTION(F)) u_newton (
                    .i_enable(multiply_enable[lane]),
                    .i_phase(product_phase),
                    .i_nearest(q.nearest),
                    .i_normalized(q.normalized),
                    .i_estimate(q.estimate),
                    .i_correction(q.correction),
                    .i_squared(q.squared),
                    .o_value(newton_value),
                    .o_inexact(newton_inexact),
                    .o_bad(arithmetic_bad[lane])
                );
            end else begin : g_no_newton
                assign newton_value = '0;
                assign newton_inexact = 1'b0;
                assign arithmetic_bad[lane] = 1'b0;
            end

            wire [O-1:0] scaled;
            wire output_overflow;
            wire output_underflow;
            wire output_inexact;

            if (!UNROLLED || lane == LATENCY - 1) begin : g_scale
                reciprocal_unit_scale #(
                    .INTERNAL_WIDTH(W),
                    .INTERNAL_FRACTION_WIDTH(F),
                    .INPUT_WIDTH(I),
                    .INPUT_FRACTION_WIDTH(IF),
                    .OUTPUT_WIDTH(O),
                    .OUTPUT_FRACTION_WIDTH(OF)
                ) u_scale (
                    .i_enable(numeric_active &&
                        (UNROLLED ||
                        32'(phase[lane]) == 3 + 3 * 32'(q.iterations))),
                    .i_estimate(q.estimate),
                    .i_exponent(q.exponent_value),
                    .i_signed(q.output_signed),
                    .i_negative(1'b0),
                    .i_nearest(q.nearest),
                    .o_data(scaled),
                    .o_overflow(output_overflow),
                    .o_underflow(output_underflow),
                    .o_inexact(output_inexact)
                );
            end else begin : g_no_scale
                assign scaled = '0;
                assign output_overflow = 1'b0;
                assign output_underflow = 1'b0;
                assign output_inexact = 1'b0;
            end

            always_comb begin : advance_packet
                d = q;

                if (numeric_active && phase[lane] == 0) begin
                    d.effective = effective;
                    d.epsilon_applied = epsilon_access[lane];

                    if (effective == 0) begin
                        d.approximate = 1'b0;
                        d.zero_input = 1'b1;
                        d.error = 1'b1;
                        d.code = RSQRT_ERR_ZERO;

                        if (ZERO_RESULT_MODE == RSQRT_ZERO_SATURATE)
                            d.data = q.output_signed ? {1'b0, {(O - 1){1'b1}}} : {O{1'b1}};
                    end
                end

                if (normalize_access[lane]) begin
                    d.normalized = normalized;
                    d.exponent_value = exponent_value;
                    d.exponent_parity = exponent_parity;
                    d.rounded = q.rounded || normalization_inexact;
                end

                if (seed_access[lane])
                    d.estimate = seed;

                if (multiply_enable[lane]) begin
                    d.rounded = q.rounded || newton_inexact;
                    case (product_phase)
                        0: d.squared = newton_value;
                        1: d.correction = newton_value;
                        default: d.estimate = newton_value;
                    endcase
                end

                if (numeric_active &&
                    ((UNROLLED && lane == LATENCY - 1) ||
                    (!UNROLLED &&
                    32'(phase[lane]) == 3 + 3 * 32'(q.iterations)))) begin
                    d.data = scaled;
                    d.overflow = output_overflow;
                    d.saturated = output_overflow;
                    d.underflow = output_underflow;
                    d.rounded = q.rounded || output_inexact;
                end
            end

            if (lane == LANES - 1) begin : g_final_result
                assign final_result = RESULT'(advanced[lane] >> (3 * I + 36 + 4 * W));
            end
        end

        if (!UNROLLED) begin : g_iterative
            wire [TOKEN+PHASE:0] state;
            logic [TOKEN+PHASE:0] next_state;
            assign {lane_valid[0], phase[0], packet[0]} = state;
            assign stage_move[0] = active_clock && lane_valid[0] &&
                (32'(phase[0]) < 3 + 3 * 32'(request_iterations) || queue_ready);
            assign lane_ready[0] = !lane_valid[0] || finish;

            event_barrier_state #(
                .WIDTH(TOKEN + PHASE + 1),
                .PROTECTED(PROTECTED),
                .ASYNC_RESET(ASYNC_RESET != 0)
            ) u_state (
                .i_clk(i_clk),
                .i_rstb(reset_released),
                .i_enable(running || i_rstb === 1'b0),
                .i_data(next_state),
                .o_data(state),
                .o_corrupt(state_corrupt[0])
            );

            always_comb begin
                next_state = state;

                if (stage_move[0])
                    next_state = finish ? '0 :
                        {1'b1, phase[0] + 1'b1, advanced[0]};

                if (request_take)
                    next_state = {1'b1, {PHASE{1'b0}}, request_packet};

                if (discard)
                    next_state = '0;
            end
        end else begin : g_unrolled
            for (genvar lane = 0; lane < LANES; lane++) begin : g_lane
                wire unused_occupancy;
                wire unused_occupied;
                wire [TOKEN-1:0] unused_contents;
                wire upstream_valid;
                wire [TOKEN-1:0] upstream_data;
                wire downstream_ready;
                assign phase[lane] = PHASE'(lane);
                assign upstream_valid = lane == 0 ? request_take : stage_move[lane-1];

                if (lane == 0) begin : g_request
                    assign upstream_data = request_packet;
                end else begin : g_previous
                    assign upstream_data = advanced[lane-1];
                end

                if (lane == LANES - 1) begin : g_output_ready
                    assign downstream_ready = queue_ready;
                end else begin : g_next_ready
                    assign downstream_ready = lane_ready[lane+1];
                end

                assign stage_move[lane] = active_clock && lane_valid[lane] &&
                    downstream_ready;

                event_barrier_queue #(
                    .WIDTH(TOKEN),
                    .DEPTH(1),
                    .PROTECTED(PROTECTED),
                    .ASYNC_RESET(ASYNC_RESET != 0)
                ) u_stage (
                    .i_clk(i_clk),
                    .i_rstb(reset_released),
                    .i_flush(discard),
                    .i_valid(upstream_valid),
                    .o_ready(lane_ready[lane]),
                    .i_data(upstream_data),
                    .o_valid(lane_valid[lane]),
                    .i_ready(active_clock && downstream_ready),
                    .o_data(packet[lane]),
                    .o_occupancy(unused_occupancy),
                    .o_corrupt(state_corrupt[lane]),
                    .o_occupied(unused_occupied),
                    .o_contents(unused_contents)
                );
            end
        end

        event_barrier_queue #(
            .WIDTH(RESULT),
            .DEPTH(Q),
            .PROTECTED(PROTECTED),
            .ASYNC_RESET(ASYNC_RESET != 0)
        ) u_results (
            .i_clk(i_clk),
            .i_rstb(reset_released),
            .i_flush(discard),
            .i_valid(finish),
            .o_ready(queue_ready),
            .i_data(final_result),
            .o_valid(queue_valid),
            .i_ready(result_pop),
            .o_data(queue_data),
            .o_occupancy(occupancy),
            .o_corrupt(queue_corrupt),
            .o_occupied(queue_occupied),
            .o_contents(unused_queue_contents)
        );

        assign o_request_ready = active_clock && i_drain === 1'b0 &&
            !fatal_now && lane_ready[0] &&
            (i_request_valid !== 1'b1 || request_known);
        assign o_result_valid = active_clock && queue_valid && !fatal_now;
        assign visible_result = o_result_valid ? queue_data : '0;
        assign o_result_data = visible_result.data;
        assign o_result_output_signed = visible_result.output_signed;
        assign o_result_iterations = visible_result.iterations;
        assign o_result_quality_id = visible_result.iterations;
        assign o_result_context_id = visible_result.context_id;
        assign o_result_tag = visible_result.tag;
        assign o_result_epsilon_applied = visible_result.epsilon_applied;
        assign o_result_negative_input = visible_result.negative_input;
        assign o_result_zero_input = visible_result.zero_input;
        assign o_result_overflow = visible_result.overflow;
        assign o_result_underflow = visible_result.underflow;
        assign o_result_saturated = visible_result.saturated;
        assign o_result_rounded = visible_result.rounded;
        assign o_result_approximate = visible_result.approximate;
        assign o_result_predicated = visible_result.predicated;
        assign o_result_error = visible_result.error;
        assign o_result_error_code = visible_result.code;
        assign o_output_queue_occupancy = running ? occupancy : '0;
        assign o_busy = running && work;
        assign o_idle = running && !work;
        assign o_quiescent = o_idle && !fatal && i_flush === 1'b0 &&
            i_drain === 1'b0 && i_request_valid === 1'b0 && i_error_clear === 1'b0;
        assign o_drain_done = running && i_drain === 1'b1 && !work;
        assign o_fatal_error = running && fatal;
        assign o_error = running && sticky_code != RSQRT_ERR_NONE;
        assign o_error_code = running ? sticky_code : RSQRT_ERR_NONE;

        logic [3:0] detected;
        logic [3:0] next_sticky;
        wire [14:0] events;
        logic [14:0] next_events;
        wire fault_event = running && fatal_now && (!fatal || error_corrupt);

        always_comb begin : diagnostics
            detected = RSQRT_ERR_NONE;
            next_events = '0;

            if (running && !flushing && !fatal && !raw_corrupt) begin
                next_events[0] = request_take;
                next_events[1] = finish && !fatal_now;
                next_events[2] = i_request_valid === 1'b1 && !o_request_ready;
                next_events[3] = o_result_valid && i_result_ready === 1'b0;
                next_events[4] = |epsilon_access;
                next_events[5] = |normalize_access;
                next_events[6] = |seed_access;
                next_events[7] = |iteration_commit;
                next_events[8] = finish && !fatal_now && final_result.negative_input;
                next_events[9] = finish && !fatal_now && final_result.zero_input;
                next_events[10] = finish && !fatal_now && final_result.overflow;
                next_events[11] = finish && !fatal_now && final_result.underflow;
                next_events[12] = |seed_corrected;
                next_events[13] = |seed_bad;

                if (request_take && request_packet.error)
                    detected = request_packet.code;

                if (stage_move[0] && g_stage[0].q.approximate && phase[0] == 0 &&
                    g_stage[0].effective == 0)
                    detected = RSQRT_ERR_ZERO;

                if (|seed_corrected)
                    detected = RSQRT_ERR_CORRECTED;
            end

            next_events[14] = flushing && work;

            if (!flushing && i_rstb !== 1'b0 && (!controls_known ||
                (i_request_valid === 1'b1 && !request_known)))
                detected = RSQRT_ERR_UNKNOWN;

            if (fault_event) begin
                if (|identity_bad)
                    detected = RSQRT_ERR_IMAGE;
                else if (raw_corrupt)
                    detected = RSQRT_ERR_OWNERSHIP;
                else if (|seed_bad)
                    detected = RSQRT_ERR_SEED;
                else
                    detected = RSQRT_ERR_INTERNAL;
            end

            next_sticky = error_corrupt ? RSQRT_ERR_NONE : sticky_code;

            if ((flushing || (i_error_clear === 1'b1 && !work &&
                i_request_valid === 1'b0 && i_flush === 1'b0 && i_drain === 1'b0)) && !fatal)
                next_sticky = RSQRT_ERR_NONE;

            if (detected != RSQRT_ERR_NONE &&
                next_sticky == RSQRT_ERR_NONE)
                next_sticky = detected;
        end

        event_barrier_state #(
            .WIDTH(5),
            .PROTECTED(PROTECTED),
            .ASYNC_RESET(ASYNC_RESET != 0)
        ) u_errors (
            .i_clk(i_clk),
            .i_rstb(reset_released),
            .i_enable(1'b1),
            .i_data({fatal || fault_event, next_sticky}),
            .o_data({fatal, sticky_code}),
            .o_corrupt(error_corrupt)
        );

        event_barrier_state #(.WIDTH(15), .ASYNC_RESET(ASYNC_RESET != 0)) u_events (
            .i_clk(i_clk),
            .i_rstb(reset_released),
            .i_enable(1'b1),
            .i_data(next_events),
            .o_data(events),
            .o_corrupt()
        );

        assign o_event_request_accept = running && events[0];
        assign o_event_result_complete = running && events[1];
        assign o_event_request_stall = running && events[2];
        assign o_event_result_stall = running && events[3];
        assign o_event_epsilon = running && events[4];
        assign o_event_normalize = running && events[5];
        assign o_event_seed_lookup = running && events[6];
        assign o_event_iteration = running && events[7];
        assign o_event_negative_input = running && events[8];
        assign o_event_zero_input = running && events[9];
        assign o_event_overflow = running && events[10];
        assign o_event_underflow = running && events[11];
        assign o_event_seed_corrected = running && events[12];
        assign o_event_seed_uncorrectable = running && events[13];
        assign o_flushed = running && events[14];
    end
endmodule
