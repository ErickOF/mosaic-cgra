`timescale 1ns / 1ps

// Immutable coefficient images with bit-identical iterative and elastic Horner datapaths.
module polynomial_unit #(
    parameter INPUT_WIDTH = 16,
    parameter COEFFICIENT_WIDTH = 18,
    parameter ACCUMULATOR_WIDTH = 32,
    parameter OUTPUT_WIDTH = 16,
    parameter FRACTION_WIDTH = 12,
    parameter MAX_DEGREE = 4,
    parameter NUM_BANKS = 4,
    parameter EVALUATION_ARCH = 0,
    parameter OUTPUT_QUEUE_DEPTH = 2,
    parameter PROGRAM_RESPONSE_DEPTH = 2,
    parameter TRACK_COEFFICIENT_COVERAGE = 1,
    parameter RESULT_SHIFT_WIDTH = 6,
    parameter BANK_VERSION_WIDTH = 8,
    parameter POLYNOMIAL_ID_WIDTH = 16,
    parameter QUALITY_ID_WIDTH = 4,
    parameter CONTEXT_ID_WIDTH = 8,
    parameter REQUEST_TAG_WIDTH = 8,
    parameter COEFFICIENT_PROTECTION = 0,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((INPUT_WIDTH >= 1 && INPUT_WIDTH < 2147483647) === 1'b1) &&
        ( ((^INPUT_WIDTH == 1'b0) || (^INPUT_WIDTH == 1'b1)) === 1'b1) &&
        ((COEFFICIENT_WIDTH >= 1 && COEFFICIENT_WIDTH < 2147483647) === 1'b1) &&
        ( ((^COEFFICIENT_WIDTH == 1'b0) || (^COEFFICIENT_WIDTH == 1'b1)) === 1'b1) &&
        ((ACCUMULATOR_WIDTH >= 1 && ACCUMULATOR_WIDTH < 2147483647) === 1'b1) &&
        ( ((^ACCUMULATOR_WIDTH == 1'b0) || (^ACCUMULATOR_WIDTH == 1'b1)) === 1'b1) &&
        ((OUTPUT_WIDTH >= 1 && OUTPUT_WIDTH < 2147483647) === 1'b1) &&
        ( ((^OUTPUT_WIDTH == 1'b0) || (^OUTPUT_WIDTH == 1'b1)) === 1'b1) &&
        ((FRACTION_WIDTH >= 1 && FRACTION_WIDTH < 2147483647) === 1'b1) &&
        ( ((^FRACTION_WIDTH == 1'b0) || (^FRACTION_WIDTH == 1'b1)) === 1'b1) &&
        ((MAX_DEGREE >= 1 && MAX_DEGREE < 2147483647) === 1'b1) &&
        ( ((^MAX_DEGREE == 1'b0) || (^MAX_DEGREE == 1'b1)) === 1'b1) &&
        ((NUM_BANKS >= 1 && NUM_BANKS < 2147483647) === 1'b1) &&
        ( ((^NUM_BANKS == 1'b0) || (^NUM_BANKS == 1'b1)) === 1'b1) &&
        ((EVALUATION_ARCH === 0) || (EVALUATION_ARCH === 1)) &&
        ((OUTPUT_QUEUE_DEPTH >= 1 && OUTPUT_QUEUE_DEPTH < 2147483647) === 1'b1) &&
        ( ((^OUTPUT_QUEUE_DEPTH == 1'b0) || (^OUTPUT_QUEUE_DEPTH == 1'b1)) === 1'b1) &&
        ((PROGRAM_RESPONSE_DEPTH >= 1 && PROGRAM_RESPONSE_DEPTH < 2147483647) === 1'b1) &&
        ( ((^PROGRAM_RESPONSE_DEPTH == 1'b0) || (^PROGRAM_RESPONSE_DEPTH == 1'b1)) === 1'b1) &&
        ((TRACK_COEFFICIENT_COVERAGE === 0) || (TRACK_COEFFICIENT_COVERAGE === 1)) &&
        ((RESULT_SHIFT_WIDTH >= 1 && RESULT_SHIFT_WIDTH < 2147483647) === 1'b1) &&
        ( ((^RESULT_SHIFT_WIDTH == 1'b0) || (^RESULT_SHIFT_WIDTH == 1'b1)) === 1'b1) &&
        ((BANK_VERSION_WIDTH >= 2 && BANK_VERSION_WIDTH < 2147483647) === 1'b1) &&
        ( ((^BANK_VERSION_WIDTH == 1'b0) || (^BANK_VERSION_WIDTH == 1'b1)) === 1'b1) &&
        ((POLYNOMIAL_ID_WIDTH >= 1 && POLYNOMIAL_ID_WIDTH < 2147483647) === 1'b1) &&
        ( ((^POLYNOMIAL_ID_WIDTH == 1'b0) || (^POLYNOMIAL_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((QUALITY_ID_WIDTH >= 1 && QUALITY_ID_WIDTH < 2147483647) === 1'b1) &&
        ( ((^QUALITY_ID_WIDTH == 1'b0) || (^QUALITY_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((CONTEXT_ID_WIDTH >= 1 && CONTEXT_ID_WIDTH < 2147483647) === 1'b1) &&
        ( ((^CONTEXT_ID_WIDTH == 1'b0) || (^CONTEXT_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((REQUEST_TAG_WIDTH >= 1 && REQUEST_TAG_WIDTH < 2147483647) === 1'b1) &&
        ( ((^REQUEST_TAG_WIDTH == 1'b0) || (^REQUEST_TAG_WIDTH == 1'b1)) === 1'b1) &&
        ((COEFFICIENT_PROTECTION === 0) || (COEFFICIENT_PROTECTION === 1) ||
            (COEFFICIENT_PROTECTION === 2)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((FRACTION_WIDTH < INPUT_WIDTH && FRACTION_WIDTH < COEFFICIENT_WIDTH &&
            FRACTION_WIDTH < ACCUMULATOR_WIDTH && ACCUMULATOR_WIDTH >= COEFFICIENT_WIDTH &&
            RESULT_SHIFT_WIDTH >= $clog2(ACCUMULATOR_WIDTH) + 1) === 1'b1) &&
        ((64'(NUM_BANKS) <= 64'd2147483647 / (64'(MAX_DEGREE) + 1) /
            (64'(MAX_DEGREE) + 1) / (64'(COEFFICIENT_WIDTH) + 32)) === 1'b1) &&
        (((64'(MAX_DEGREE) + 64'(OUTPUT_QUEUE_DEPTH) +
            64'(PROGRAM_RESPONSE_DEPTH) + 64'(NUM_BANKS) + 16) *
            (64'(ACCUMULATOR_WIDTH) * 8 + 64'(INPUT_WIDTH) * 8 +
            64'(RESULT_SHIFT_WIDTH) + 64'(BANK_VERSION_WIDTH) +
            64'(POLYNOMIAL_ID_WIDTH) + 64'(QUALITY_ID_WIDTH) +
            64'(CONTEXT_ID_WIDTH) + 64'(REQUEST_TAG_WIDTH) + 256) <
            64'd2147483647) === 1'b1),
    localparam int I = PARAMETERS_VALID ? INPUT_WIDTH : 1,
    localparam int K = PARAMETERS_VALID ? COEFFICIENT_WIDTH : 1,
    localparam int A = PARAMETERS_VALID ? ACCUMULATOR_WIDTH : 1,
    localparam int O = PARAMETERS_VALID ? OUTPUT_WIDTH : 1,
    localparam int F = PARAMETERS_VALID ? FRACTION_WIDTH : 1,
    localparam int D = PARAMETERS_VALID ? MAX_DEGREE : 1,
    localparam int B = PARAMETERS_VALID ? NUM_BANKS : 1,
    localparam int OQ = PARAMETERS_VALID ? OUTPUT_QUEUE_DEPTH : 1,
    localparam int PQ = PARAMETERS_VALID ? PROGRAM_RESPONSE_DEPTH : 1,
    localparam int S = PARAMETERS_VALID ? RESULT_SHIFT_WIDTH : 1,
    localparam int V = PARAMETERS_VALID ? BANK_VERSION_WIDTH : 2,
    localparam int ID = PARAMETERS_VALID ? POLYNOMIAL_ID_WIDTH : 1,
    localparam int Q = PARAMETERS_VALID ? QUALITY_ID_WIDTH : 1,
    localparam int C = PARAMETERS_VALID ? CONTEXT_ID_WIDTH : 1,
    localparam int G = PARAMETERS_VALID ? REQUEST_TAG_WIDTH : 1,
    localparam int COEFFICIENT_COUNT = D + 1,
    localparam int COEFFICIENT_INDEX_WIDTH = D > 1 ? $clog2(D + 1) : 1,
    localparam int DEGREE_WIDTH = COEFFICIENT_INDEX_WIDTH,
    localparam int BANK_WIDTH = B > 1 ? $clog2(B) : 1,
    localparam int PRODUCT_WIDTH = A + I,
    localparam int OUTPUT_QUEUE_OCCUPANCY_WIDTH = $clog2(OQ + 1),
    localparam int PROGRAM_QUEUE_OCCUPANCY_WIDTH = $clog2(PQ + 1)
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_drain,
    input logic i_flush,
    input logic i_error_clear,
    input logic i_request_valid,
    output logic o_request_ready,
    input logic [I-1:0] i_request_x,
    input logic [BANK_WIDTH-1:0] i_request_bank,
    input logic i_request_predicate,
    input logic [C-1:0] i_request_context_id,
    input logic [G-1:0] i_request_tag,
    output logic o_result_valid,
    input logic i_result_ready,
    output logic [O-1:0] o_result_data,
    output logic [BANK_WIDTH-1:0] o_result_bank,
    output logic [V-1:0] o_result_bank_version,
    output logic [ID-1:0] o_result_polynomial_id,
    output logic [Q-1:0] o_result_quality_id,
    output logic [C-1:0] o_result_context_id,
    output logic [G-1:0] o_result_tag,
    output logic o_result_clipped_low,
    output logic o_result_clipped_high,
    output logic o_result_internal_saturated,
    output logic o_result_output_saturated,
    output logic o_result_inexact,
    output logic o_result_predicated,
    output logic o_result_error,
    output logic [4:0] o_result_error_code,
    input logic i_program_valid,
    output logic o_program_ready,
    input logic [1:0] i_program_command,
    input logic [BANK_WIDTH-1:0] i_program_bank,
    input logic [COEFFICIENT_INDEX_WIDTH-1:0] i_program_coefficient_index,
    input logic [K-1:0] i_program_coefficient_data,
    input logic [DEGREE_WIDTH-1:0] i_program_degree,
    input logic [I-1:0] i_program_x_min,
    input logic [I-1:0] i_program_x_max,
    input logic i_program_range_policy,
    input logic i_program_round_mode,
    input logic [S-1:0] i_program_result_shift,
    input logic [ID-1:0] i_program_polynomial_id,
    input logic [Q-1:0] i_program_quality_id,
    output logic o_program_response_valid,
    input logic i_program_response_ready,
    output logic [1:0] o_program_response_command,
    output logic [BANK_WIDTH-1:0] o_program_response_bank,
    output logic [COEFFICIENT_INDEX_WIDTH-1:0] o_program_response_coefficient_index,
    output logic [K-1:0] o_program_response_coefficient_data,
    output logic [DEGREE_WIDTH-1:0] o_program_response_degree,
    output logic [I-1:0] o_program_response_x_min,
    output logic [I-1:0] o_program_response_x_max,
    output logic o_program_response_range_policy,
    output logic o_program_response_round_mode,
    output logic [S-1:0] o_program_response_result_shift,
    output logic [V-1:0] o_program_response_version,
    output logic [ID-1:0] o_program_response_polynomial_id,
    output logic [Q-1:0] o_program_response_quality_id,
    output logic o_program_response_bank_valid,
    output logic o_program_response_error,
    output logic [4:0] o_program_response_error_code,
    output logic [B-1:0] o_bank_valid,
    output logic [B*V-1:0] o_bank_version,
    output logic [B*ID-1:0] o_bank_polynomial_id,
    output logic [B*Q-1:0] o_bank_quality_id,
    output logic [B-1:0] o_bank_program_complete,
    output logic [OUTPUT_QUEUE_OCCUPANCY_WIDTH-1:0] o_output_queue_occupancy,
    output logic [PROGRAM_QUEUE_OCCUPANCY_WIDTH-1:0] o_program_queue_occupancy,
    output logic o_busy,
    output logic o_idle,
    output logic o_quiescent,
    output logic o_drain_done,
    output logic o_flushed,
    output logic o_error,
    output logic [4:0] o_error_code,
    output logic o_fatal_error,
    output logic o_event_request_accept,
    output logic o_event_result_complete,
    output logic o_event_request_stall,
    output logic o_event_result_stall,
    output logic o_event_horner_stage,
    output logic o_event_clip_low,
    output logic o_event_clip_high,
    output logic o_event_internal_saturation,
    output logic o_event_output_saturation,
    output logic o_event_program_write,
    output logic o_event_program_read,
    output logic o_event_program_commit,
    output logic o_event_program_invalidate,
    output logic o_event_coefficient_corrected,
    output logic o_event_coefficient_uncorrectable
);
    import polynomial_unit_pkg::*;

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        polynomial_unit_parameters_must_be_valid invalid_parameters ();
    end else begin : g_unit
        // Parameter-dependent records remain local to this module.
        localparam int STAGES = EVALUATION_ARCH == POLY_ARCH_UNROLLED ? D + 1 : 1;
        localparam int READ_PORTS = STAGES;
        localparam int REFERENCES = $clog2(STAGES + OQ + 1);
        localparam bit PROTECTED = COEFFICIENT_PROTECTION != 0;

        typedef struct packed {
            logic [O-1:0] data;
            logic [BANK_WIDTH-1:0] bank;
            logic [V-1:0] version;
            logic [ID-1:0] polynomial_id;
            logic [Q-1:0] quality_id;
            logic [C-1:0] context_id;
            logic [G-1:0] tag;
            logic low_clip;
            logic high_clip;
            logic internal_saturated;
            logic output_saturated;
            logic inexact;
            logic predicated;
            logic error;
            logic [ERROR_WIDTH-1:0] code;
            logic tracked;
        } result_t;

        typedef struct packed {
            logic [O-1:0] data;
            logic [BANK_WIDTH-1:0] bank;
            logic [V-1:0] version;
            logic [ID-1:0] polynomial_id;
            logic [Q-1:0] quality_id;
            logic [C-1:0] context_id;
            logic [G-1:0] tag;
            logic low_clip;
            logic high_clip;
            logic internal_saturated;
            logic output_saturated;
            logic inexact;
            logic predicated;
            logic error;
            logic [ERROR_WIDTH-1:0] code;
            logic tracked;

            logic [I-1:0] x;
            logic [A-1:0] accumulator;
            logic [DEGREE_WIDTH-1:0] degree;
            logic [S-1:0] shift;
            logic nearest;
        } token_t;

        typedef struct packed {
            logic valid_bank;
            logic [V-1:0] version;
            logic [ID-1:0] polynomial_id;
            logic [Q-1:0] quality_id;
            logic [COEFFICIENT_COUNT-1:0] coverage;
            logic [REFERENCES-1:0] references;
            logic [DEGREE_WIDTH-1:0] degree;
            logic [I-1:0] x_min;
            logic [I-1:0] x_max;
            logic range_policy;
            logic nearest;
            logic [S-1:0] shift;
            logic fault;
        } bank_t;

        typedef struct packed {
            logic [1:0] command;
            logic [BANK_WIDTH-1:0] bank;
            logic [COEFFICIENT_INDEX_WIDTH-1:0] index;
            logic [K-1:0] data;
            logic valid_bank;
            logic [V-1:0] version;
            logic [ID-1:0] polynomial_id;
            logic [Q-1:0] quality_id;
            logic [COEFFICIENT_COUNT-1:0] coverage;
            logic [REFERENCES-1:0] references;
            logic [DEGREE_WIDTH-1:0] degree;
            logic [I-1:0] x_min;
            logic [I-1:0] x_max;
            logic range_policy;
            logic nearest;
            logic [S-1:0] shift;
            logic fault;
            logic error;
            logic [ERROR_WIDTH-1:0] code;
        } program_t;

        token_t request_packet;
        token_t final_packet;
        result_t completed_packet;
        result_t result_head;
        program_t program_packet;
        program_t program_head;
        bank_t request_bank;
        bank_t program_bank;
        wire [COEFFICIENT_COUNT-1:0] program_coverage = program_bank.coverage;
        wire [$bits(bank_t)-1:0] bank_records[B];
        wire [B-1:0] bank_corrupt;
        wire [B-1:0] bank_fault;
        wire [B-1:0] ownership_bad;
        logic [B-1:0] coefficient_fault;
        wire [B-1:0] write_select;
        wire [B-1:0] program_corrected;
        wire [B-1:0] program_bad;
        wire [K-1:0] program_data[B];
        logic [READ_PORTS-1:0] read_enable;
        logic [BANK_WIDTH-1:0] read_bank[READ_PORTS];
        logic [COEFFICIENT_INDEX_WIDTH-1:0] read_index[READ_PORTS];
        wire [B-1:0] read_select[READ_PORTS];
        wire [B-1:0][K+1:0] read_values[READ_PORTS];
        wire [K-1:0] coefficient[READ_PORTS];
        wire [READ_PORTS-1:0] read_corrected;
        wire [READ_PORTS-1:0] read_bad;
        wire [STAGES-1:0] pipe_valid;
        wire [STAGES-1:0] pipe_corrupt;
        wire [$bits(token_t)-1:0] pipe_data[STAGES];
        wire [STAGES-1:0] stage_commit;
        wire [STAGES-1:0] stage_saturated;
        wire [OQ*$bits(result_t)-1:0] all_results;
        wire [OQ-1:0] result_occupied;
        wire result_valid;
        wire result_ready;
        wire result_corrupt;
        wire program_valid;
        wire program_ready;
        wire program_corrupt;
        wire [PQ-1:0] unused_program_occupied;
        wire [PQ*$bits(program_t)-1:0] unused_program_contents;
        logic finish;
        logic accept_capacity;
        logic request_known;
        logic program_known;
        logic request_access;
        logic conflict;
        polynomial_error_t program_error;
        logic [ERROR_WIDTH-1:0] detected;
        wire hard_fatal;
        wire flushed;
        wire [ERROR_WIDTH-1:0] sticky_error;
        wire [14:0] events;
        logic [14:0] next_events;
        wire reset_b = i_rstb !== 1'b0;
        wire clock_enabled = i_rstb === 1'b1;
        wire controls_known = ( ^ {i_flush, i_drain, i_error_clear, i_request_valid,
            i_result_ready, i_program_valid, i_program_response_ready} !== 1'bx);
        wire running = clock_enabled && controls_known && (i_flush === 1'b0);
        wire flushing = clock_enabled && (i_flush === 1'b1);
        wire raw_corrupt = (|bank_corrupt) || (|ownership_bad) || (|pipe_corrupt) ||
            result_corrupt || program_corrupt;
        wire healthy = !hard_fatal && !raw_corrupt;
        wire fatal = hard_fatal || (|bank_fault);
        wire evaluation_empty = !(|pipe_valid) && o_output_queue_occupancy == 0;
        wire idle = evaluation_empty && o_program_queue_occupancy == 0;
        wire clear_allowed = running && idle && (i_drain === 1'b0) &&
            (i_request_valid === 1'b0) && (i_program_valid === 1'b0);
        wire request_take = o_request_ready && (i_request_valid === 1'b1);
        wire program_take = o_program_ready && (i_program_valid === 1'b1);
        wire result_pop = o_result_valid && (i_result_ready === 1'b1);
        wire program_pop = o_program_response_valid && (i_program_response_ready === 1'b1);
        wire legal_write = program_take && program_error == POLY_ERR_NONE &&
            i_program_command == POLY_PROGRAM_WRITE;
        wire legal_read = program_take && program_error == POLY_ERR_NONE &&
            i_program_command == POLY_PROGRAM_READ;
        wire legal_commit = program_take && program_error == POLY_ERR_NONE &&
            i_program_command == POLY_PROGRAM_COMMIT;
        wire legal_invalidate = program_take && program_error == POLY_ERR_NONE &&
            i_program_command == POLY_PROGRAM_INVALIDATE;
        wire program_candidate = running && healthy && program_ready && program_known &&
            ((i_drain === 1'b0) || evaluation_empty);
        wire request_bank_known = ( ^ i_request_bank !== 1'bx) &&
            (32'(i_request_bank) < B);
        wire program_bank_known = ( ^ i_program_bank !== 1'bx) &&
            (32'(i_program_bank) < B);

        // Global diagnostics do not reset or rewrite coefficient payloads.
        wire [ERROR_WIDTH-1:0] retained_error = hard_fatal || raw_corrupt ?
            ERROR_WIDTH'(POLY_ERR_INTERNAL) : (|bank_fault) ?
            ERROR_WIDTH'(POLY_ERR_COEFFICIENT) : ERROR_WIDTH'(POLY_ERR_NONE);
        wire error_enable = (i_rstb !== 1'b0) && (flushing ||
            (clear_allowed && (i_error_clear === 1'b1)) ||
            ((sticky_error == POLY_ERR_NONE) && (detected != POLY_ERR_NONE)));
        wire [ERROR_WIDTH-1:0] next_error = flushing ||
            (clear_allowed && (i_error_clear === 1'b1)) ? retained_error : detected;

        dff #(.WIDTH(ERROR_WIDTH), .ASYNC_RESET(1'(ASYNC_RESET))) u_error (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(error_enable),
            .i_d(next_error),
            .o_q(sticky_error)
        );

        dff #(.ASYNC_RESET(1'(ASYNC_RESET))) u_fatal (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(clock_enabled && raw_corrupt),
            .i_d(1'b1),
            .o_q(hard_fatal)
        );

        dff #(.WIDTH(15), .ASYNC_RESET(1'(ASYNC_RESET))) u_events (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(clock_enabled),
            .i_d(next_events),
            .o_q(events)
        );

        dff #(.ASYNC_RESET(1'(ASYNC_RESET))) u_flushed (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(clock_enabled),
            .i_d(flushing && !evaluation_empty),
            .o_q(flushed)
        );

        // Parallel, synchronous queue flush preserves bank and program state.
        event_barrier_queue #(
            .WIDTH($bits(result_t)),
            .DEPTH(OQ),
            .PROTECTED(PROTECTED),
            .ASYNC_RESET(1'(ASYNC_RESET))
        ) u_results (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_flush(flushing),
            .i_valid(finish),
            .o_ready(result_ready),
            .i_data(completed_packet),
            .o_valid(result_valid),
            .i_ready(result_pop),
            .o_data(result_head),
            .o_occupancy(o_output_queue_occupancy),
            .o_corrupt(result_corrupt),
            .o_occupied(result_occupied),
            .o_contents(all_results)
        );

        event_barrier_queue #(
            .WIDTH($bits(program_t)),
            .DEPTH(PQ),
            .PROTECTED(PROTECTED),
            .ASYNC_RESET(1'(ASYNC_RESET))
        ) u_program_results (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_flush(1'b0),
            .i_valid(program_take),
            .o_ready(program_ready),
            .i_data(program_packet),
            .o_valid(program_valid),
            .i_ready(program_pop),
            .o_data(program_head),
            .o_occupancy(o_program_queue_occupancy),
            .o_corrupt(program_corrupt),
            .o_occupied(unused_program_occupied),
            .o_contents(unused_program_contents)
        );

        decoder #(.NUM_OUTPUTS(B), .SELECT_WIDTH(BANK_WIDTH)) u_write_decode (
            .i_enable(legal_write),
            .i_select(i_program_bank),
            .o_decoded(write_select),
            .o_select_valid()
        );

        for (genvar port_index = 0; port_index < READ_PORTS; port_index++) begin : g_read
            decoder #(.NUM_OUTPUTS(B), .SELECT_WIDTH(BANK_WIDTH)) u_decode (
                .i_enable(read_enable[port_index]),
                .i_select(read_bank[port_index]),
                .o_decoded(read_select[port_index]),
                .o_select_valid()
            );

            mux #(.NUM_INPUTS(B), .DATA_WIDTH(K + 2)) u_mux (
                .i_data(read_values[port_index]),
                .i_select(read_bank[port_index]),
                .o_data({read_bad[port_index], read_corrected[port_index],
                    coefficient[port_index]}),
                .o_select_valid()
            );
        end

        // Unrolled mode replicates storage per read position. All copies share
        // the same legal write; only the coefficient used by a committing stage
        // is read. Iterative mode has one copy and one shared multiplier.
        for (genvar bank = 0; bank < B; bank++) begin : g_bank
            bank_t metadata;
            bank_t next_metadata;
            logic [REFERENCES-1:0] actual_references;
            wire add_reference = request_take && request_packet.tracked &&
                i_request_bank == BANK_WIDTH'(bank);
            wire retire_reference = result_pop && result_head.tracked &&
                result_head.bank == BANK_WIDTH'(bank);
            assign bank_records[bank] = metadata;
            assign bank_fault[bank] = metadata.fault;
            assign o_bank_valid[bank] = clock_enabled && !bank_corrupt[bank] && metadata.valid_bank;
            assign o_bank_version[bank*V+:V] = clock_enabled ? metadata.version : '0;
            assign o_bank_polynomial_id[bank*ID+:ID] = clock_enabled ? metadata.polynomial_id : '0;
            assign o_bank_quality_id[bank*Q+:Q] = clock_enabled ? metadata.quality_id : '0;
            assign o_bank_program_complete[bank] = clock_enabled &&
                (!TRACK_COEFFICIENT_COVERAGE || (&metadata.coverage));

            event_barrier_state #(
                .WIDTH($bits(bank_t)),
                .PROTECTED(PROTECTED),
                .ASYNC_RESET(1'(ASYNC_RESET))
            ) u_metadata (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_enable(clock_enabled && (flushing || (healthy && next_metadata !== metadata))),
                .i_data(next_metadata),
                .o_data(metadata),
                .o_corrupt(bank_corrupt[bank])
            );

            always_comb begin : reference_census
                token_t token;
                result_t result;
                actual_references = '0;
                token = '0;
                result = '0;

                for (int stage = 0; stage < STAGES; stage++) begin
                    token = pipe_data[stage];

                    if (pipe_valid[stage] && token.tracked &&
                        token.bank == BANK_WIDTH'(bank))
                        actual_references = actual_references + REFERENCES'(1);
                end

                for (int slot = 0; slot < OQ; slot++) begin
                    result = all_results[slot*$bits(result_t)+:$bits(result_t)];

                    if (result_occupied[slot] && result.tracked &&
                        result.bank == BANK_WIDTH'(bank))
                        actual_references = actual_references + REFERENCES'(1);
                end
            end

            assign ownership_bad[bank] = metadata.references !== actual_references;

            always_comb begin
                next_metadata = metadata;

                if (add_reference != retire_reference)
                    next_metadata.references = add_reference ? metadata.references + 1'b1 :
                        metadata.references - 1'b1;

                if (coefficient_fault[bank])
                    next_metadata.fault = 1'b1;

                if (legal_write && i_program_bank == BANK_WIDTH'(bank))
                    next_metadata.coverage = metadata.coverage |
                        (COEFFICIENT_COUNT'(1) << i_program_coefficient_index);

                if (legal_commit && i_program_bank == BANK_WIDTH'(bank)) begin
                    next_metadata.valid_bank = 1'b1;
                    next_metadata.version = metadata.version + 1'b1;
                    next_metadata.degree = i_program_degree;
                    next_metadata.x_min = i_program_x_min;
                    next_metadata.x_max = i_program_x_max;
                    next_metadata.range_policy = i_program_range_policy;
                    next_metadata.nearest = i_program_round_mode;
                    next_metadata.shift = i_program_result_shift;
                    next_metadata.polynomial_id = i_program_polynomial_id;
                    next_metadata.quality_id = i_program_quality_id;
                end

                if (legal_invalidate && i_program_bank == BANK_WIDTH'(bank)) begin
                    next_metadata = '0;
                    next_metadata.version = metadata.version;
                end

                if (flushing)
                    next_metadata.references = '0;
            end

            for (genvar copy = 0; copy < READ_PORTS; copy++) begin : g_copy
                localparam int READ_COPY = copy;
                wire [K-1:0] lower;
                wire [K-1:0] upper;
                wire [1:0] corrected;
                wire [1:0] bad;

                lut_unit_bank #(
                    .ADDRESS(COEFFICIENT_INDEX_WIDTH),
                    .WIDTH(K),
                    .PROTECTION(COEFFICIENT_PROTECTION)
                ) u_coefficients (
                    .i_clk(i_clk),
                    .i_write(write_select[bank]),
                    .i_write_address(i_program_coefficient_index),
                    .i_write_data(i_program_coefficient_data),
                    .i_read({read_select[READ_COPY][bank],
                        legal_read && i_program_bank == BANK_WIDTH'(bank) && READ_COPY == 0}),
                    .i_lower_address(i_program_coefficient_index),
                    .i_upper_address(read_index[READ_COPY]),
                    .o_lower(lower),
                    .o_upper(upper),
                    .o_corrected(corrected),
                    .o_bad(bad)
                );

                assign read_values[READ_COPY][bank] = {bad[1], corrected[1], upper};

                if (READ_COPY == 0) begin : g_program_read
                    assign program_data[bank] = lower;
                    assign program_corrected[bank] = corrected[0];
                    assign program_bad[bank] = bad[0];
                end
            end
        end

        // Datapath and programming policy are defined below.
        if (EVALUATION_ARCH == POLY_ARCH_UNROLLED) begin : g_unrolled
            wire [STAGES-1:0] ready;
            assign accept_capacity = ready[0];
            assign read_enable[0] = request_take && request_access;
            assign read_bank[0] = i_request_bank;
            assign read_index[0] = request_bank.degree;
            assign finish = running && healthy && pipe_valid[STAGES-1] && result_ready;
            assign final_packet = pipe_data[STAGES-1];

            for (genvar stage = 0; stage < STAGES; stage++) begin : g_stage
                token_t input_packet;
                wire input_valid;
                wire output_ready;
                wire unused_occupancy;
                wire unused_occupied;
                wire [$bits(token_t)-1:0] unused_contents;

                if (stage == 0) begin : g_initial
                    assign input_valid = request_take;
                    assign input_packet = request_packet;
                    assign stage_commit[stage] = 1'b0;
                    assign stage_saturated[stage] = 1'b0;
                end else begin : g_horner
                    token_t source;
                    wire [A-1:0] accumulator;
                    wire inexact;
                    wire saturated;
                    wire active_stage = running && healthy && pipe_valid[stage-1] &&
                        ready[stage] && !source.error && !source.predicated &&
                        32'(source.degree) >= stage;
                    assign source = pipe_data[stage-1];
                    assign input_valid = running && healthy && pipe_valid[stage-1];
                    assign read_enable[stage] = active_stage && !bank_fault[source.bank];
                    assign read_bank[stage] = source.bank;
                    assign read_index[stage] = source.degree - DEGREE_WIDTH'(stage);
                    assign stage_commit[stage] = read_enable[stage] && !read_bad[stage];
                    assign stage_saturated[stage] = stage_commit[stage] && saturated;

                    polynomial_unit_horner #(
                        .INPUT_WIDTH(I),
                        .COEFFICIENT_WIDTH(K),
                        .ACCUMULATOR_WIDTH(A),
                        .FRACTION_WIDTH(F)
                    ) u_horner (
                        .i_enable(stage_commit[stage]),
                        .i_x(source.x),
                        .i_accumulator(source.accumulator),
                        .i_coefficient(coefficient[stage]),
                        .i_nearest(source.nearest),
                        .o_accumulator(accumulator),
                        .o_inexact(inexact),
                        .o_saturated(saturated)
                    );

                    always_comb begin
                        input_packet = source;

                        if (active_stage) begin
                            if (read_bad[stage] || bank_fault[source.bank]) begin
                                input_packet.error = 1'b1;
                                input_packet.code = POLY_ERR_COEFFICIENT;
                                input_packet.accumulator = '0;
                            end else begin
                                input_packet.accumulator = accumulator;
                                input_packet.inexact = source.inexact || inexact;
                                input_packet.internal_saturated =
                                    source.internal_saturated || saturated;
                            end
                        end
                    end
                end

                if (stage == STAGES - 1) begin : g_last
                    assign output_ready = running && healthy && result_ready;
                end else begin : g_earlier
                    assign output_ready = running && healthy && ready[stage+1];
                end

                event_barrier_queue #(
                    .WIDTH($bits(token_t)),
                    .DEPTH(1),
                    .PROTECTED(PROTECTED),
                    .ASYNC_RESET(1'(ASYNC_RESET))
                ) u_stage (
                    .i_clk(i_clk),
                    .i_rstb(reset_b),
                    .i_flush(flushing),
                    .i_valid(input_valid),
                    .o_ready(ready[stage]),
                    .i_data(input_packet),
                    .o_valid(pipe_valid[stage]),
                    .i_ready(output_ready),
                    .o_data(pipe_data[stage]),
                    .o_occupancy(unused_occupancy),
                    .o_corrupt(pipe_corrupt[stage]),
                    .o_occupied(unused_occupied),
                    .o_contents(unused_contents)
                );
            end
        end else begin : g_iterative
            typedef struct packed {
                logic valid;
                logic [DEGREE_WIDTH-1:0] remaining;
                logic [O-1:0] data;
                logic [BANK_WIDTH-1:0] bank;
                logic [V-1:0] version;
                logic [ID-1:0] polynomial_id;
                logic [Q-1:0] quality_id;
                logic [C-1:0] context_id;
                logic [G-1:0] tag;
                logic low_clip;
                logic high_clip;
                logic internal_saturated;
                logic output_saturated;
                logic inexact;
                logic predicated;
                logic error;
                logic [ERROR_WIDTH-1:0] code;
                logic tracked;

                logic [I-1:0] x;
                logic [A-1:0] accumulator;
                logic [DEGREE_WIDTH-1:0] degree;
                logic [S-1:0] shift;
                logic nearest;

            } evaluation_t;

            evaluation_t q;
            evaluation_t d;
            token_t current;
            assign current = $bits(token_t)'(q);
            wire state_bad;
            wire [A-1:0] accumulator;
            wire inexact;
            wire saturated;
            wire active_stage = running && healthy && q.valid && q.remaining != 0 &&
                !current.error && !current.predicated;
            assign pipe_valid[0] = q.valid;
            assign pipe_data[0] = $bits(token_t)'(q);
            assign pipe_corrupt[0] = state_bad ||
                (q.valid && q.remaining > current.degree);
            assign finish = running && healthy && q.valid && q.remaining == 0 && result_ready;
            assign accept_capacity = result_ready && (!q.valid || finish);
            assign final_packet = $bits(token_t)'(q);
            assign read_enable[0] = (request_take && request_access) ||
                (active_stage && !bank_fault[current.bank]);
            assign read_bank[0] = request_take ? i_request_bank : current.bank;
            assign read_index[0] = request_take ? request_bank.degree : q.remaining - 1'b1;
            assign stage_commit[0] = active_stage && read_enable[0] && !read_bad[0];
            assign stage_saturated[0] = stage_commit[0] && saturated;

            polynomial_unit_horner #(
                .INPUT_WIDTH(I),
                .COEFFICIENT_WIDTH(K),
                .ACCUMULATOR_WIDTH(A),
                .FRACTION_WIDTH(F)
            ) u_horner (
                .i_enable(stage_commit[0]),
                .i_x(current.x),
                .i_accumulator(current.accumulator),
                .i_coefficient(coefficient[0]),
                .i_nearest(current.nearest),
                .o_accumulator(accumulator),
                .o_inexact(inexact),
                .o_saturated(saturated)
            );

            event_barrier_state #(
                .WIDTH($bits(evaluation_t)),
                .PROTECTED(PROTECTED),
                .ASYNC_RESET(1'(ASYNC_RESET))
            ) u_evaluation (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_enable(clock_enabled && (flushing || (healthy && running && d !== q))),
                .i_data(d),
                .o_data(q),
                .o_corrupt(state_bad)
            );

            always_comb begin
                d = q;

                if (active_stage) begin
                    if (read_bad[0] || bank_fault[current.bank]) begin
                        d.error = 1'b1;
                        d.code = POLY_ERR_COEFFICIENT;
                        d.accumulator = '0;
                        d.remaining = '0;
                    end else begin
                        d.accumulator = accumulator;
                        d.inexact = current.inexact || inexact;
                        d.internal_saturated =
                            current.internal_saturated || saturated;
                        d.remaining = q.remaining - 1'b1;
                    end
                end

                if (finish)
                    d.valid = 1'b0;

                if (request_take) begin
                    d.valid = 1'b1;
                    d.data = request_packet.data;
                    d.bank = request_packet.bank;
                    d.version = request_packet.version;
                    d.polynomial_id = request_packet.polynomial_id;
                    d.quality_id = request_packet.quality_id;
                    d.context_id = request_packet.context_id;
                    d.tag = request_packet.tag;
                    d.low_clip = request_packet.low_clip;
                    d.high_clip = request_packet.high_clip;
                    d.internal_saturated = request_packet.internal_saturated;
                    d.output_saturated = request_packet.output_saturated;
                    d.inexact = request_packet.inexact;
                    d.predicated = request_packet.predicated;
                    d.error = request_packet.error;
                    d.code = request_packet.code;
                    d.tracked = request_packet.tracked;
                    d.x = request_packet.x;
                    d.accumulator = request_packet.accumulator;
                    d.degree = request_packet.degree;
                    d.shift = request_packet.shift;
                    d.nearest = request_packet.nearest;
                    d.remaining = request_packet.error || request_packet.predicated ?
                        '0 : request_packet.degree;
                end

                if (flushing)
                    d = '0;
            end
        end

        wire [O-1:0] scaled;
        wire output_inexact;
        wire output_saturated;

        polynomial_unit_scale #(
            .ACCUMULATOR_WIDTH(A),
            .OUTPUT_WIDTH(O),
            .SHIFT_WIDTH(S)
        ) u_scale (
            .i_enable(finish && !final_packet.error && !final_packet.predicated),
            .i_accumulator(final_packet.accumulator),
            .i_shift(final_packet.shift),
            .i_nearest(final_packet.nearest),
            .o_data(scaled),
            .o_inexact(output_inexact),
            .o_saturated(output_saturated)
        );

        always_comb begin
            completed_packet = $bits(result_t)'(final_packet >> (I + A + DEGREE_WIDTH + S + 1));
            completed_packet.data = scaled;
            completed_packet.inexact = final_packet.inexact || output_inexact;
            completed_packet.output_saturated = output_saturated;
        end

        always_comb begin : request_policy
            request_known = ( ^ {i_request_x, i_request_bank, i_request_predicate,
                i_request_context_id, i_request_tag} !== 1'bx);
            request_bank = request_bank_known ? bank_records[i_request_bank] : '0;
            request_packet = '0;
            request_packet.bank = i_request_bank;
            request_packet.context_id = i_request_context_id;
            request_packet.tag = i_request_tag;
            request_access = 1'b0;

            if (!request_bank_known) begin
                request_packet.error = 1'b1;
                request_packet.code = POLY_ERR_BANK;
            end else if (!request_bank.valid_bank) begin
                request_packet.error = 1'b1;
                request_packet.code = POLY_ERR_UNCOMMITTED;
            end else begin
                request_packet.tracked = 1'b1;
                request_packet.version = request_bank.version;
                request_packet.polynomial_id = request_bank.polynomial_id;
                request_packet.quality_id = request_bank.quality_id;
                request_packet.degree = request_bank.degree;
                request_packet.shift = request_bank.shift;
                request_packet.nearest = request_bank.nearest;
                request_packet.x = i_request_x;

                if (!i_request_predicate)
                    request_packet.predicated = 1'b1;
                else if (request_bank.range_policy == POLY_RANGE_ERROR &&
                    ($signed(i_request_x) < $signed(request_bank.x_min) ||
                    $signed(i_request_x) > $signed(request_bank.x_max))) begin
                    request_packet.error = 1'b1;
                    request_packet.code = POLY_ERR_RANGE;
                end else begin
                    if ($signed(i_request_x) < $signed(request_bank.x_min)) begin
                        request_packet.x = request_bank.x_min;
                        request_packet.low_clip = 1'b1;
                    end else if ($signed(i_request_x) > $signed(request_bank.x_max)) begin
                        request_packet.x = request_bank.x_max;
                        request_packet.high_clip = 1'b1;
                    end

                    request_access = 1'b1;

                    if (read_bad[0]) begin
                        request_packet.error = 1'b1;
                        request_packet.code = POLY_ERR_COEFFICIENT;
                    end else
                        request_packet.accumulator = A'($signed(coefficient[0]));
                end
            end
        end

        always_comb begin : program_policy
            logic covered;
            program_known = ( ^ {i_program_command, i_program_bank,
                i_program_coefficient_index, i_program_coefficient_data, i_program_degree,
                i_program_x_min, i_program_x_max, i_program_range_policy, i_program_round_mode,
                i_program_result_shift, i_program_polynomial_id, i_program_quality_id} !== 1'bx);
            program_bank = program_bank_known ? bank_records[i_program_bank] : '0;
            covered = 1'b1;

            for (int index = 0; index < COEFFICIENT_COUNT; index++)
                if (index <= 32'(i_program_degree) && !program_coverage[index])
                    covered = 1'b0;

            program_error = POLY_ERR_NONE;

            if (!program_bank_known)
                program_error = POLY_ERR_BANK;
            else begin
                case (i_program_command)
                    POLY_PROGRAM_WRITE: begin
                        if (program_bank.valid_bank)
                            program_error = POLY_ERR_COMMITTED;
                        else if (32'(i_program_coefficient_index) > D)
                            program_error = POLY_ERR_INDEX;
                    end
                    POLY_PROGRAM_READ: begin
                        if (32'(i_program_coefficient_index) > D)
                            program_error = POLY_ERR_INDEX;
                    end
                    POLY_PROGRAM_COMMIT: begin
                        if (fatal)
                            program_error = POLY_ERR_INTERNAL;
                        else if (program_bank.valid_bank)
                            program_error = POLY_ERR_COMMITTED;
                        else if (program_bank.references != 0)
                            program_error = POLY_ERR_BUSY;
                        else if (32'(i_program_degree) > D)
                            program_error = POLY_ERR_DEGREE;
                        else if ($signed(i_program_x_min) > $signed(i_program_x_max))
                            program_error = POLY_ERR_DOMAIN;
                        else if ($signed(i_program_result_shift) > (A - 1) ||
                            $signed(i_program_result_shift) < -(A - 1))
                            program_error = POLY_ERR_SHIFT;
                        else if (TRACK_COEFFICIENT_COVERAGE && !covered)
                            program_error = POLY_ERR_INCOMPLETE;
                    end
                    POLY_PROGRAM_INVALIDATE: begin
                        if (program_bank.references != 0)
                            program_error = POLY_ERR_BUSY;
                    end
                    default: program_error = POLY_ERR_UNKNOWN;
                endcase
            end

            conflict = program_candidate && (i_program_valid === 1'b1) &&
                (i_program_command == POLY_PROGRAM_COMMIT ||
                 i_program_command == POLY_PROGRAM_INVALIDATE) &&
                i_program_bank == i_request_bank;
        end

        always_comb begin : program_response
            program_packet = '0;
            program_packet.command = i_program_command;
            program_packet.bank = i_program_bank;
            program_packet.index = i_program_coefficient_index;
            program_packet.valid_bank = program_bank.valid_bank;
            program_packet.version = program_bank.version;
            program_packet.polynomial_id = program_bank.polynomial_id;
            program_packet.quality_id = program_bank.quality_id;
            program_packet.coverage = program_bank.coverage;
            program_packet.references = program_bank.references;
            program_packet.degree = program_bank.degree;
            program_packet.x_min = program_bank.x_min;
            program_packet.x_max = program_bank.x_max;
            program_packet.range_policy = program_bank.range_policy;
            program_packet.nearest = program_bank.nearest;
            program_packet.shift = program_bank.shift;
            program_packet.fault = program_bank.fault;
            program_packet.error = program_error != POLY_ERR_NONE;
            program_packet.code = program_error;

            if (legal_read) begin
                if (program_bad[i_program_bank]) begin
                    program_packet.error = 1'b1;
                    program_packet.code = POLY_ERR_COEFFICIENT;
                end else
                    program_packet.data = program_data[i_program_bank];
            end

            if (legal_commit) begin
                program_packet.valid_bank = 1'b1;
                program_packet.version = program_bank.version + 1'b1;
                program_packet.degree = i_program_degree;
                program_packet.x_min = i_program_x_min;
                program_packet.x_max = i_program_x_max;
                program_packet.range_policy = i_program_range_policy;
                program_packet.nearest = i_program_round_mode;
                program_packet.shift = i_program_result_shift;
                program_packet.polynomial_id = i_program_polynomial_id;
                program_packet.quality_id = i_program_quality_id;
            end

            if (legal_invalidate) begin
                program_packet.valid_bank = '0;
                program_packet.version = '0;
                program_packet.polynomial_id = '0;
                program_packet.quality_id = '0;
                program_packet.coverage = '0;
                program_packet.references = '0;
                program_packet.degree = '0;
                program_packet.x_min = '0;
                program_packet.x_max = '0;
                program_packet.range_policy = '0;
                program_packet.nearest = '0;
                program_packet.shift = '0;
                program_packet.fault = '0;
                program_packet.version = program_bank.version;
            end
        end

        always_comb begin : faults_and_events
            coefficient_fault = '0;
            next_events = '0;
            detected = POLY_ERR_NONE;

            if (running && healthy) begin
                next_events[0] = request_take;
                next_events[1] = finish;
                next_events[2] = (i_request_valid === 1'b1) && !o_request_ready;
                next_events[3] = result_valid && (i_result_ready === 1'b0);
                next_events[4] = |stage_commit;
                next_events[5] = request_take && request_packet.low_clip;
                next_events[6] = request_take && request_packet.high_clip;
                next_events[7] = |stage_saturated;
                next_events[8] = finish && output_saturated;
                next_events[9] = legal_write;
                next_events[10] = legal_read;
                next_events[11] = legal_commit;
                next_events[12] = legal_invalidate;

                for (int port_index = 0; port_index < READ_PORTS; port_index++) begin
                    if (read_enable[port_index]) begin
                        next_events[13] = next_events[13] || read_corrected[port_index];
                        next_events[14] = next_events[14] || read_bad[port_index];
                        if (read_bad[port_index])
                            coefficient_fault[read_bank[port_index]] = 1'b1;
                    end
                end

                if (legal_read) begin
                    next_events[13] = next_events[13] || program_corrected[i_program_bank];
                    next_events[14] = next_events[14] || program_bad[i_program_bank];
                    if (program_bad[i_program_bank] && program_bank.valid_bank)
                        coefficient_fault[i_program_bank] = 1'b1;
                end

                if (request_take && request_packet.error)
                    detected = request_packet.code;

                if (program_take && program_packet.error)
                    detected = program_packet.code;

                if (next_events[13] && detected == POLY_ERR_NONE)
                    detected = POLY_ERR_CORRECTED;

                if (next_events[14])
                    detected = POLY_ERR_COEFFICIENT;
            end

            if ( ^ {i_rstb, i_flush, i_drain, i_error_clear, i_request_valid, i_result_ready,
                i_program_valid, i_program_response_ready} === 1'bx ||
                ((i_request_valid === 1'b1) && !request_known) ||
                ((i_program_valid === 1'b1) && !program_known))
                detected = POLY_ERR_UNKNOWN;

            if (raw_corrupt)
                detected = POLY_ERR_INTERNAL;
        end

        assign o_request_ready = running && healthy && !fatal && (i_drain === 1'b0) &&
            request_known && !conflict && accept_capacity;
        assign o_program_ready = program_candidate;
        assign o_result_valid = running && healthy && result_valid;
        assign o_program_response_valid = running && healthy && program_valid;
        assign o_busy = clock_enabled && (|pipe_valid);
        assign o_idle = running && healthy && idle;
        assign o_quiescent = o_idle && (i_drain === 1'b0) &&
            (i_request_valid === 1'b0) && (i_program_valid === 1'b0) &&
            (i_error_clear === 1'b0);
        assign o_drain_done = running && healthy && (i_drain === 1'b1) && evaluation_empty;
        assign o_flushed = clock_enabled && flushed;
        assign o_error = clock_enabled && sticky_error != POLY_ERR_NONE;
        assign o_error_code = clock_enabled ? sticky_error : ERROR_WIDTH'(POLY_ERR_NONE);
        assign o_fatal_error = clock_enabled && fatal;
        assign o_result_data = o_result_valid ? result_head.data : '0;
        assign o_result_bank = o_result_valid ? result_head.bank : '0;
        assign o_result_bank_version = o_result_valid ? result_head.version : '0;
        assign o_result_polynomial_id = o_result_valid ? result_head.polynomial_id : '0;
        assign o_result_quality_id = o_result_valid ? result_head.quality_id : '0;
        assign o_result_context_id = o_result_valid ? result_head.context_id : '0;
        assign o_result_tag = o_result_valid ? result_head.tag : '0;
        assign o_result_clipped_low = o_result_valid ? result_head.low_clip : '0;
        assign o_result_clipped_high = o_result_valid ? result_head.high_clip : '0;
        assign o_result_internal_saturated = o_result_valid ? result_head.internal_saturated : '0;
        assign o_result_output_saturated = o_result_valid ? result_head.output_saturated : '0;
        assign o_result_inexact = o_result_valid ? result_head.inexact : '0;
        assign o_result_predicated = o_result_valid ? result_head.predicated : '0;
        assign o_result_error = o_result_valid ? result_head.error : '0;
        assign o_result_error_code = o_result_valid ? result_head.code : '0;
        assign o_program_response_command = o_program_response_valid ?
            program_head.command : '0;
        assign o_program_response_bank = o_program_response_valid ?
            program_head.bank : '0;
        assign o_program_response_coefficient_index = o_program_response_valid ?
            program_head.index : '0;
        assign o_program_response_coefficient_data = o_program_response_valid ?
            program_head.data : '0;
        assign o_program_response_degree = o_program_response_valid ?
            program_head.degree : '0;
        assign o_program_response_x_min = o_program_response_valid ?
            program_head.x_min : '0;
        assign o_program_response_x_max = o_program_response_valid ?
            program_head.x_max : '0;
        assign o_program_response_range_policy = o_program_response_valid ?
            program_head.range_policy : '0;
        assign o_program_response_round_mode = o_program_response_valid ?
            program_head.nearest : '0;
        assign o_program_response_result_shift = o_program_response_valid ?
            program_head.shift : '0;
        assign o_program_response_version = o_program_response_valid ?
            program_head.version : '0;
        assign o_program_response_polynomial_id = o_program_response_valid ?
            program_head.polynomial_id : '0;
        assign o_program_response_quality_id = o_program_response_valid ?
            program_head.quality_id : '0;
        assign o_program_response_bank_valid = o_program_response_valid ?
            program_head.valid_bank : '0;
        assign o_program_response_error = o_program_response_valid ?
            program_head.error : '0;
        assign o_program_response_error_code = o_program_response_valid ?
            program_head.code : '0;
        assign o_event_request_accept = clock_enabled && events[0];
        assign o_event_result_complete = clock_enabled && events[1];
        assign o_event_request_stall = clock_enabled && events[2];
        assign o_event_result_stall = clock_enabled && events[3];
        assign o_event_horner_stage = clock_enabled && events[4];
        assign o_event_clip_low = clock_enabled && events[5];
        assign o_event_clip_high = clock_enabled && events[6];
        assign o_event_internal_saturation = clock_enabled && events[7];
        assign o_event_output_saturation = clock_enabled && events[8];
        assign o_event_program_write = clock_enabled && events[9];
        assign o_event_program_read = clock_enabled && events[10];
        assign o_event_program_commit = clock_enabled && events[11];
        assign o_event_program_invalidate = clock_enabled && events[12];
        assign o_event_coefficient_corrected = clock_enabled && events[13];
        assign o_event_coefficient_uncorrectable = clock_enabled && events[14];
    end
endmodule
