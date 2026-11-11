`timescale 1ns / 1ps

// Programmable immutable image banks and a fixed-depth elastic lookup pipeline.
module lut_unit #(
    parameter ADDRESS_WIDTH = 8,
    parameter OUTPUT_WIDTH = 16,
    parameter INDEX_FRACTION_WIDTH = 8,
    parameter NUM_BANKS = 4,
    parameter SUPPORT_INTERPOLATION = 1,
    parameter LOOKUP_PIPELINE_DEPTH = 2,
    parameter LOOKUP_RESPONSE_DEPTH = 2,
    parameter PROGRAM_RESPONSE_DEPTH = 2,
    parameter TRACK_PROGRAM_COVERAGE = 1,
    parameter TABLE_VERSION_WIDTH = 8,
    parameter TABLE_ID_WIDTH = 16,
    parameter QUALITY_ID_WIDTH = 4,
    parameter CONTEXT_ID_WIDTH = 8,
    parameter LOOKUP_TAG_WIDTH = 8,
    parameter BUFFER_PROTECTION = 0,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((ADDRESS_WIDTH >= 1) === 1'b1) && ( ((^ADDRESS_WIDTH == 1'b0) || (^ADDRESS_WIDTH == 1'b1)) === 1'b1) &&
        ((OUTPUT_WIDTH >= 1) === 1'b1) && ( ((^OUTPUT_WIDTH == 1'b0) || (^OUTPUT_WIDTH == 1'b1)) === 1'b1) &&
        ((INDEX_FRACTION_WIDTH >= 1) === 1'b1) && ( ((^INDEX_FRACTION_WIDTH == 1'b0) || (^INDEX_FRACTION_WIDTH == 1'b1)) === 1'b1) &&
        ((NUM_BANKS >= 1) === 1'b1) && ( ((^NUM_BANKS == 1'b0) || (^NUM_BANKS == 1'b1)) === 1'b1) &&
        ((SUPPORT_INTERPOLATION === 0) || (SUPPORT_INTERPOLATION === 1)) &&
        ((LOOKUP_PIPELINE_DEPTH >= 1) === 1'b1) && ( ((^LOOKUP_PIPELINE_DEPTH == 1'b0) || (^LOOKUP_PIPELINE_DEPTH == 1'b1)) === 1'b1) &&
        ((LOOKUP_RESPONSE_DEPTH >= 1) === 1'b1) && ( ((^LOOKUP_RESPONSE_DEPTH == 1'b0) || (^LOOKUP_RESPONSE_DEPTH == 1'b1)) === 1'b1) &&
        ((PROGRAM_RESPONSE_DEPTH >= 1) === 1'b1) && ( ((^PROGRAM_RESPONSE_DEPTH == 1'b0) || (^PROGRAM_RESPONSE_DEPTH == 1'b1)) === 1'b1) &&
        ((TRACK_PROGRAM_COVERAGE === 0) || (TRACK_PROGRAM_COVERAGE === 1)) &&
        ((TABLE_VERSION_WIDTH >= 2) === 1'b1) && ( ((^TABLE_VERSION_WIDTH == 1'b0) || (^TABLE_VERSION_WIDTH == 1'b1)) === 1'b1) &&
        ((TABLE_ID_WIDTH >= 1) === 1'b1) && ( ((^TABLE_ID_WIDTH == 1'b0) || (^TABLE_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((QUALITY_ID_WIDTH >= 1) === 1'b1) && ( ((^QUALITY_ID_WIDTH == 1'b0) || (^QUALITY_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((CONTEXT_ID_WIDTH >= 1) === 1'b1) && ( ((^CONTEXT_ID_WIDTH == 1'b0) || (^CONTEXT_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((LOOKUP_TAG_WIDTH >= 1) === 1'b1) && ( ((^LOOKUP_TAG_WIDTH == 1'b0) || (^LOOKUP_TAG_WIDTH == 1'b1)) === 1'b1) &&
        ((BUFFER_PROTECTION >= 0 && BUFFER_PROTECTION <= 2) === 1'b1) &&
        ( ((^BUFFER_PROTECTION == 1'b0) || (^BUFFER_PROTECTION == 1'b1)) === 1'b1) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((ADDRESS_WIDTH < 31) === 1'b1) &&
        ((64'(NUM_BANKS) * (64'd1 << ADDRESS_WIDTH) * (64'(OUTPUT_WIDTH) * 2 + 4) +
            (64'(LOOKUP_PIPELINE_DEPTH) + 64'(LOOKUP_RESPONSE_DEPTH) +
            64'(PROGRAM_RESPONSE_DEPTH) + 64'(NUM_BANKS)) *
            (64'(OUTPUT_WIDTH) * 4 + 64'(TABLE_VERSION_WIDTH) * 4 +
            64'(TABLE_ID_WIDTH) * 4 + 64'(QUALITY_ID_WIDTH) * 4 +
            64'(CONTEXT_ID_WIDTH) * 4 + 64'(LOOKUP_TAG_WIDTH) * 4 + 256) +
            64'(INDEX_FRACTION_WIDTH) * 4 < 64'd2147483647) === 1'b1),
    localparam int A = PARAMETERS_VALID ? ADDRESS_WIDTH : 1,
    localparam int W = PARAMETERS_VALID ? OUTPUT_WIDTH : 1,
    localparam int F = PARAMETERS_VALID ? INDEX_FRACTION_WIDTH : 1,
    localparam int B = PARAMETERS_VALID ? NUM_BANKS : 1,
    localparam int P = PARAMETERS_VALID ? LOOKUP_PIPELINE_DEPTH : 1,
    localparam int LQ = PARAMETERS_VALID ? LOOKUP_RESPONSE_DEPTH : 1,
    localparam int PQ = PARAMETERS_VALID ? PROGRAM_RESPONSE_DEPTH : 1,
    localparam int V = PARAMETERS_VALID ? TABLE_VERSION_WIDTH : 2,
    localparam int T = PARAMETERS_VALID ? TABLE_ID_WIDTH : 1,
    localparam int Q = PARAMETERS_VALID ? QUALITY_ID_WIDTH : 1,
    localparam int C = PARAMETERS_VALID ? CONTEXT_ID_WIDTH : 1,
    localparam int G = PARAMETERS_VALID ? LOOKUP_TAG_WIDTH : 1,
    localparam int TABLE_DEPTH = 1 << A,
    localparam int BANK_WIDTH = B > 1 ? $clog2(B) : 1,
    localparam int INDEX_WIDTH = 1 + A + F,
    localparam int LOOKUP_QUEUE_OCCUPANCY_WIDTH = $clog2(LQ + 1),
    localparam int PROGRAM_QUEUE_OCCUPANCY_WIDTH = $clog2(PQ + 1)
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_drain,
    input logic i_flush,
    input logic i_error_clear,
    input logic i_lookup_valid,
    output logic o_lookup_ready,
    input logic [INDEX_WIDTH-1:0] i_lookup_coordinate,
    input logic [BANK_WIDTH-1:0] i_lookup_bank,
    input logic i_lookup_index_signed,
    input logic i_lookup_output_signed,
    input logic i_lookup_interpolate,
    input logic i_lookup_round_mode,
    input logic i_lookup_predicate,
    input logic [C-1:0] i_lookup_context_id,
    input logic [G-1:0] i_lookup_tag,
    output logic o_result_valid,
    input logic i_result_ready,
    output logic [W-1:0] o_result_data,
    output logic [BANK_WIDTH-1:0] o_result_bank,
    output logic [V-1:0] o_result_table_version,
    output logic [T-1:0] o_result_table_id,
    output logic [Q-1:0] o_result_quality_id,
    output logic [C-1:0] o_result_context_id,
    output logic [G-1:0] o_result_tag,
    output logic o_result_clipped_low,
    output logic o_result_clipped_high,
    output logic o_result_interpolated,
    output logic o_result_predicated,
    output logic o_result_error,
    output logic [lut_unit_pkg::ERROR_WIDTH-1:0] o_result_error_code,
    input logic i_program_valid,
    output logic o_program_ready,
    input logic [2-1:0] i_program_command,
    input logic [BANK_WIDTH-1:0] i_program_bank,
    input logic [A-1:0] i_program_address,
    input logic [W-1:0] i_program_write_data,
    input logic [T-1:0] i_program_table_id,
    input logic [Q-1:0] i_program_quality_id,
    output logic o_program_response_valid,
    input logic i_program_response_ready,
    output logic [2-1:0] o_program_response_command,
    output logic [BANK_WIDTH-1:0] o_program_response_bank,
    output logic [A-1:0] o_program_response_address,
    output logic [W-1:0] o_program_response_read_data,
    output logic [V-1:0] o_program_response_version,
    output logic [T-1:0] o_program_response_table_id,
    output logic [Q-1:0] o_program_response_quality_id,
    output logic o_program_response_bank_valid,
    output logic o_program_response_error,
    output logic [lut_unit_pkg::ERROR_WIDTH-1:0] o_program_response_error_code,
    output logic [B-1:0] o_bank_valid,
    output logic [B*V-1:0] o_bank_version,
    output logic [B*T-1:0] o_bank_table_id,
    output logic [B*Q-1:0] o_bank_quality_id,
    output logic [B-1:0] o_bank_program_complete,
    output logic [LOOKUP_QUEUE_OCCUPANCY_WIDTH-1:0] o_lookup_queue_occupancy,
    output logic [PROGRAM_QUEUE_OCCUPANCY_WIDTH-1:0] o_program_queue_occupancy,
    output logic o_idle,
    output logic o_quiescent,
    output logic o_drain_done,
    output logic o_flushed,
    output logic o_error,
    output logic [lut_unit_pkg::ERROR_WIDTH-1:0] o_error_code,
    output logic o_fatal_error,
    output logic o_event_lookup_accept,
    output logic o_event_lookup_complete,
    output logic o_event_lookup_stall,
    output logic o_event_result_stall,
    output logic o_event_clip_low,
    output logic o_event_clip_high,
    output logic o_event_interpolate,
    output logic o_event_program_write,
    output logic o_event_program_read,
    output logic o_event_program_commit,
    output logic o_event_program_invalidate,
    output logic o_event_table_corrected,
    output logic o_event_table_uncorrectable
);
    import lut_unit_pkg::*;

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        lut_unit_parameters_must_be_valid invalid_parameters ();
    end else begin : g_unit
        localparam int REFERENCES = $clog2(P + LQ + 1);
        localparam int PRODUCT = W + 1 + F;
        localparam bit PROTECTED = BUFFER_PROTECTION != 0;
        localparam logic [INDEX_WIDTH-1:0] INDEX_MAX =
            {1'b0, {A{1'b1}}, {F{1'b0}}};

        // These packed records depend on module parameters and stay local.
        typedef struct packed {
            logic [W-1:0] data;
            logic [BANK_WIDTH-1:0] bank;
            logic [V-1:0] version;
            logic [T-1:0] table_id;
            logic [Q-1:0] quality_id;
            logic [C-1:0] context_id;
            logic [G-1:0] tag;
            logic low_clip;
            logic high_clip;
            logic interpolated;
            logic predicated;
            logic error;
            logic [ERROR_WIDTH-1:0] code;
        } result_t;

        typedef struct packed {
            logic [1:0] command;
            logic [BANK_WIDTH-1:0] bank;
            logic [A-1:0] address;
            logic [W-1:0] data;
            logic [V-1:0] version;
            logic [T-1:0] table_id;
            logic [Q-1:0] quality_id;
            logic valid_bank;
            logic error;
            logic [ERROR_WIDTH-1:0] code;
        } response_t;

        typedef struct packed {
            logic valid_bank;
            logic [V-1:0] version;
            logic [T-1:0] table_id;
            logic [Q-1:0] quality_id;
            logic [TABLE_DEPTH-1:0] coverage;
            logic [REFERENCES-1:0] references;
            logic fault;
        } bank_t;

        localparam int RESULT_BANK_LOW = $bits(result_t) - W - BANK_WIDTH;

        result_t lookup_packet;
        result_t lookup_identity;
        result_t result_head;
        response_t program_packet;
        response_t program_head;
        logic [A-1:0] lower_address;
        logic [A-1:0] upper_address;
        logic [F-1:0] fraction;
        logic lower_enable;
        logic upper_enable;
        logic lookup_known;
        logic program_known;
        logic command_exclusion;
        logic read_conflict;
        logic lookup_fault;
        logic lookup_corrected;
        logic program_fault;
        logic program_corrected;
        logic [13:0] events_next;
        lut_error_t lookup_error;
        lut_error_t program_error;
        lut_error_t detected;
        wire [13:0] events;
        wire [ERROR_WIDTH-1:0] sticky_error;
        wire hard_fatal;
        wire [B-1:0] bank_valid;
        wire [B-1:0] bank_complete;
        wire [B-1:0] bank_fault;
        wire [B-1:0] bank_corrupt;
        wire [B-1:0] ownership_bad;
        logic queue_bad;
        wire [B*V-1:0] bank_versions;
        wire [B*T-1:0] bank_ids;
        wire [B*Q-1:0] bank_qualities;
        wire [REFERENCES-1:0] references[B];
        wire [W-1:0] bank_lower[B];
        wire [W-1:0] bank_upper[B];
        wire [1:0] bank_corrected[B];
        wire [1:0] bank_bad[B];
        wire [P-1:0] pipe_valid;
        wire [P-1:0] pipe_ready;
        wire [P-1:0] pipe_corrupt;
        wire [$bits(result_t)-1:0] pipe_data[P];
        wire result_valid;
        wire result_ready;
        wire result_corrupt;
        wire program_valid;
        wire program_ready;
        wire program_corrupt;
        wire [LOOKUP_QUEUE_OCCUPANCY_WIDTH-1:0] result_occupancy;
        wire [PROGRAM_QUEUE_OCCUPANCY_WIDTH-1:0] program_occupancy;
        wire [LQ-1:0] unused_result_occupied;
        wire [LQ*$bits(result_t)-1:0] unused_result_contents;
        wire [PQ-1:0] unused_program_occupied;
        wire [PQ*$bits(response_t)-1:0] unused_program_contents;

        wire reset_b = i_rstb !== 1'b0;
        wire clock_enabled = i_rstb === 1'b1;
        wire running = clock_enabled && (i_flush === 1'b0);
        wire flushing = clock_enabled && (i_flush === 1'b1);
        wire raw_corrupt = (|bank_corrupt) || (|ownership_bad) || queue_bad ||
            (|pipe_corrupt) ||
            result_corrupt || program_corrupt;
        wire healthy = !hard_fatal&&!raw_corrupt;
        wire fatal = hard_fatal || (|bank_fault);
        wire lookup_empty = !(|pipe_valid) && (result_occupancy == 0);
        wire idle = lookup_empty && (program_occupancy == 0);
        wire clear_allowed = running && idle && (i_drain === 1'b0) &&
            (i_lookup_valid === 1'b0) && (i_program_valid === 1'b0);
        wire lookup_take = o_lookup_ready && (i_lookup_valid === 1'b1);
        wire program_take = o_program_ready && (i_program_valid === 1'b1);
        wire result_pop = o_result_valid && (i_result_ready === 1'b1);
        wire program_pop = o_program_response_valid && (i_program_response_ready === 1'b1);
        wire lookup_finish = running && healthy && pipe_valid[P-1] && result_ready;
        wire program_candidate = running && healthy && program_ready && program_known &&
            ((i_drain === 1'b0) || ((i_drain === 1'b1) && lookup_empty));
        wire legal_write = program_take && (program_error == LUT_ERR_NONE) &&
            (i_program_command == LUT_PROGRAM_WRITE);
        wire legal_read = program_take && (program_error == LUT_ERR_NONE) &&
            (i_program_command == LUT_PROGRAM_READ);
        wire legal_commit = program_take && (program_error == LUT_ERR_NONE) &&
            (i_program_command == LUT_PROGRAM_COMMIT);
        wire legal_invalidate = program_take && (program_error == LUT_ERR_NONE) &&
            (i_program_command == LUT_PROGRAM_INVALIDATE);
        wire error_enable = clock_enabled && (flushing ||
            (running && ((clear_allowed && (i_error_clear === 1'b1)) ||
            ((sticky_error == LUT_ERR_NONE) && (detected != LUT_ERR_NONE)))));
        // Clearing a recoverable first error cannot hide an outstanding fatal
        // cause. Invalidation clears an entry fault; ownership faults need reset.
        wire [ERROR_WIDTH-1:0] retained_error = hard_fatal || raw_corrupt ?
            ERROR_WIDTH'(LUT_ERR_INTERNAL) : (|bank_fault) ?
            ERROR_WIDTH'(LUT_ERR_UNCORRECTABLE) : ERROR_WIDTH'(LUT_ERR_NONE);
        wire [ERROR_WIDTH-1:0] error_next =
            flushing || (clear_allowed && (i_error_clear === 1'b1)) ? retained_error : detected;

        // References include error and predicated tokens. A retired result owns
        // its bank through the retiring edge; lifecycle changes use the next edge.
        for (genvar bank = 0; bank < B; bank++) begin : g_bank
            bank_t metadata;
            bank_t next_metadata;
            logic [TABLE_DEPTH-1:0] next_coverage;
            logic [REFERENCES-1:0] actual_references;
            wire lookup_reference = lookup_take && (i_lookup_bank == BANK_WIDTH'(bank));
            wire retire_reference = result_pop && (result_head.bank == BANK_WIDTH'(bank));
            wire targeted = i_program_bank == BANK_WIDTH'(bank);
            wire selected = i_lookup_bank == BANK_WIDTH'(bank);
            wire writing = legal_write && targeted;
            wire reading = legal_read && targeted;
            wire [1:0] read_enable =
                {upper_enable && selected, (lower_enable && selected) || reading};
            wire [A-1:0] first_address = reading ? i_program_address : lower_address;
            wire detected_fault = metadata.valid_bank &&
                ((lookup_take && selected && lookup_fault) || (reading && program_fault));
            wire metadata_enable = running && healthy && (next_metadata !== metadata);
            assign bank_valid[bank] = metadata.valid_bank;
            assign bank_versions[bank*V+:V] = metadata.version;
            assign bank_ids[bank*T+:T] = metadata.table_id;
            assign bank_qualities[bank*Q+:Q] = metadata.quality_id;
            assign references[bank] = metadata.references;
            assign bank_fault[bank] = metadata.fault;

            if (TRACK_PROGRAM_COVERAGE == 1) begin : g_coverage
                assign bank_complete[bank] = &metadata.coverage;
            end else begin : g_no_coverage
                assign bank_complete[bank] = 1'b1;
            end

            event_barrier_state #(
                .WIDTH($bits(bank_t)),
                .PROTECTED(PROTECTED),
                .ASYNC_RESET(1'(ASYNC_RESET))
            ) u_metadata (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_enable(flushing || metadata_enable),
                .i_data(next_metadata),
                .o_data(metadata),
                .o_corrupt(bank_corrupt[bank])
            );

            lut_unit_bank #(.ADDRESS(A), .WIDTH(W), .PROTECTION(BUFFER_PROTECTION)) u_table (
                .i_clk(i_clk),
                .i_write(writing),
                .i_write_address(i_program_address),
                .i_write_data(i_program_write_data),
                .i_read(read_enable),
                .i_lower_address(first_address),
                .i_upper_address(upper_address),
                .o_lower(bank_lower[bank]),
                .o_upper(bank_upper[bank]),
                .o_corrected(bank_corrected[bank]),
                .o_bad(bank_bad[bank])
            );

            // Count actual owned tokens independently of the increment/decrement
            // ledger. This also catches unprotected impossible reference counts.
            always_comb begin
                actual_references = '0;
                for (int stage_index = 0; stage_index < P; stage_index++) begin
                    if (pipe_valid[stage_index] &&
                        (pipe_data[stage_index][RESULT_BANK_LOW+:BANK_WIDTH] == BANK_WIDTH'(bank)))
                        actual_references = actual_references + REFERENCES'(1);
                end
                for (int lane = 0; lane < LQ; lane++) begin
                    if (unused_result_occupied[lane] &&
                        (unused_result_contents[lane*$bits(result_t)+RESULT_BANK_LOW+:BANK_WIDTH] ==
                        BANK_WIDTH'(bank)))
                        actual_references = actual_references + REFERENCES'(1);
                end
            end
            assign ownership_bad[bank] = metadata.references !== actual_references;

            always_comb begin
                next_metadata = metadata;
                next_coverage = metadata.coverage;

                if (lookup_reference != retire_reference)
                    next_metadata.references = lookup_reference ?
                        metadata.references + REFERENCES'(1) : metadata.references - REFERENCES'(1);
                if (writing && (TRACK_PROGRAM_COVERAGE == 1)) begin
                    next_coverage[i_program_address] = 1'b1;
                    next_metadata.coverage = next_coverage;
                end
                if (legal_commit && targeted) begin
                    next_metadata.valid_bank = 1'b1;
                    next_metadata.version = metadata.version + V'(1);
                    next_metadata.table_id = i_program_table_id;
                    next_metadata.quality_id = i_program_quality_id;
                end
                if (detected_fault)
                    next_metadata.fault = 1'b1;
                if (legal_invalidate && targeted) begin
                    next_metadata.valid_bank = 1'b0;
                    next_metadata.table_id = '0;
                    next_metadata.quality_id = '0;
                    next_metadata.coverage = '0;
                    next_metadata.fault = 1'b0;
                end
                if (flushing)
                    next_metadata.references = '0;
            end
        end

        always_comb begin : queue_invariants
            int result_count;
            int program_count;
            result_count = 0;
            program_count = 0;
            for (int lane = 0; lane < LQ; lane++)
                result_count += int'(unused_result_occupied[lane]);
            for (int lane = 0; lane < PQ; lane++)
                program_count += int'(unused_program_occupied[lane]);
            queue_bad = (int'(result_occupancy) !== result_count) ||
                (int'(program_occupancy) !== program_count);
        end

        // One protected elastic slot per stage, followed by a protected response
        // queue. Payload RAM is unreset; reset/flush remove ownership in parallel.
        for (genvar stage = 0; stage < P; stage++) begin : g_stage
            wire input_valid;
            wire [$bits(result_t)-1:0] input_data;
            wire output_ready;
            wire unused_occupancy;
            wire unused_occupied;
            wire [$bits(result_t)-1:0] unused_contents;

            if (stage == 0) begin : g_first
                assign input_valid = lookup_take;
                assign input_data = lookup_packet;
            end else begin : g_later
                assign input_valid = running && healthy && pipe_valid[stage-1];
                assign input_data = pipe_data[stage-1];
            end

            if (stage == P - 1) begin : g_last
                assign output_ready = running && healthy && result_ready;
            end else begin : g_earlier
                assign output_ready = running && healthy && pipe_ready[stage+1];
            end

            event_barrier_queue #(
                .WIDTH($bits(result_t)),
                .DEPTH(1),
                .PROTECTED(PROTECTED),
                .ASYNC_RESET(1'(ASYNC_RESET))
            ) u_pipeline (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_flush(flushing),
                .i_valid(input_valid),
                .o_ready(pipe_ready[stage]),
                .i_data(input_data),
                .o_valid(pipe_valid[stage]),
                .i_ready(output_ready),
                .o_data(pipe_data[stage]),
                .o_occupancy(unused_occupancy),
                .o_corrupt(pipe_corrupt[stage]),
                .o_occupied(unused_occupied),
                .o_contents(unused_contents)
            );
        end

        event_barrier_queue #(
            .WIDTH($bits(result_t)),
            .DEPTH(LQ),
            .PROTECTED(PROTECTED),
            .ASYNC_RESET(1'(ASYNC_RESET))
        ) u_results (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_flush(flushing),
            .i_valid(lookup_finish),
            .o_ready(result_ready),
            .i_data(pipe_data[P-1]),
            .o_valid(result_valid),
            .i_ready(result_pop),
            .o_data(result_head),
            .o_occupancy(result_occupancy),
            .o_corrupt(result_corrupt),
            .o_occupied(unused_result_occupied),
            .o_contents(unused_result_contents)
        );

        event_barrier_queue #(
            .WIDTH($bits(response_t)),
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
            .o_occupancy(program_occupancy),
            .o_corrupt(program_corrupt),
            .o_occupied(unused_program_occupied),
            .o_contents(unused_program_contents)
        );

        dff #(.WIDTH(1), .ASYNC_RESET(1'(ASYNC_RESET))) u_fatal (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(running && raw_corrupt),
            .i_d(1'b1),
            .o_q(hard_fatal)
        );

        dff #(.WIDTH(ERROR_WIDTH), .ASYNC_RESET(1'(ASYNC_RESET))) u_error (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(error_enable),
            .i_d(error_next),
            .o_q(sticky_error)
        );

        dff #(.WIDTH(14), .ASYNC_RESET(1'(ASYNC_RESET))) u_events (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(clock_enabled && (running || flushing)),
            .i_d(events_next),
            .o_q(events)
        );

        always_comb begin : request_fields
            lookup_known = (i_lookup_valid !== 1'b1) ||
                (( ^ {i_lookup_coordinate, i_lookup_bank, i_lookup_index_signed,
                i_lookup_output_signed, i_lookup_interpolate, i_lookup_predicate,
                i_lookup_context_id, i_lookup_tag} !== 1'bx) &&
                ((i_lookup_interpolate === 1'b0) || ( ^ i_lookup_round_mode !== 1'bx)));
            program_known = (i_program_valid !== 1'b1) ||
                ( ^ {i_program_command, i_program_bank, i_program_address,
                    i_program_write_data, i_program_table_id, i_program_quality_id} !== 1'bx);
        end

        // Lifecycle and write commands have priority over same-bank lookups.
        assign command_exclusion = program_candidate && (i_program_valid === 1'b1) &&
            (i_program_command != LUT_PROGRAM_READ) && (i_program_bank == i_lookup_bank);
        assign o_lookup_ready = running && healthy&&!fatal && (i_drain === 1'b0) &&
            lookup_known && pipe_ready[0]&&!command_exclusion;
        assign read_conflict = lookup_take && lower_enable &&
            (i_program_command == LUT_PROGRAM_READ) && (i_program_bank == i_lookup_bank);
        assign o_program_ready = program_candidate&&!read_conflict;

        // Coordinate classification does not depend on memory outputs or ready.
        // Separate cones keep ready arbitration free of interpolation feedback.
        always_comb begin : classify_lookup
            lookup_error = LUT_ERR_NONE;
            lower_address = '0;
            upper_address = '0;
            fraction = '0;
            lower_enable = 1'b0;
            upper_enable = 1'b0;
            lookup_identity = '0;
            lookup_identity.bank = i_lookup_bank;
            lookup_identity.context_id = i_lookup_context_id;
            lookup_identity.tag = i_lookup_tag;

            if (lookup_known && (int'(i_lookup_bank) < B)) begin
                lookup_identity.version = bank_versions[int'(i_lookup_bank)*V+:V];
                lookup_identity.table_id = bank_ids[int'(i_lookup_bank)*T+:T];
                lookup_identity.quality_id = bank_qualities[int'(i_lookup_bank)*Q+:Q];

                if (!bank_valid[i_lookup_bank])
                    lookup_error = LUT_ERR_INVALID_BANK;
                else if ((i_lookup_interpolate === 1'b1) && (SUPPORT_INTERPOLATION == 0))
                    lookup_error = LUT_ERR_INTERPOLATION;
                else if (i_lookup_predicate === 1'b0)
                    lookup_identity.predicated = 1'b1;
                else begin
                    if (i_lookup_index_signed && i_lookup_coordinate[INDEX_WIDTH-1])
                        lookup_identity.low_clip = 1'b1;
                    else if (i_lookup_coordinate > INDEX_MAX) begin
                        lower_address = {A{1'b1}};
                        lookup_identity.high_clip = 1'b1;
                    end else begin
                        lower_address = i_lookup_coordinate[F+:A];
                        fraction = i_lookup_coordinate[F-1:0];
                    end

                    upper_address = lower_address;
                    if ((SUPPORT_INTERPOLATION == 1) && i_lookup_interpolate &&
                        (fraction != 0) && (lower_address != {A{1'b1}})) begin
                        upper_address = lower_address + A'(1);
                        lookup_identity.interpolated = 1'b1;
                    end

                    lower_enable = lookup_take;
                    upper_enable = lookup_take && lookup_identity.interpolated;
                end
            end else
                lookup_error = LUT_ERR_BANK;
        end

        always_comb begin : numerical_result
            logic signed [W:0] y0;
            logic signed [W:0] y1;
            logic signed [W:0] delta;
            logic signed [PRODUCT-1:0] product_value;
            logic [PRODUCT-1:0] magnitude;
            logic [PRODUCT-1:0] quotient;
            logic [F-1:0] remainder_value;
            logic [F-1:0] half_value;
            logic signed [W+1:0] scaled;
            logic signed [W+1:0] value;
            lookup_packet = lookup_identity;
            lookup_fault = 1'b0;
            lookup_corrected = 1'b0;
            y0 = '0;
            y1 = '0;
            delta = '0;
            product_value = '0;
            magnitude = '0;
            quotient = '0;
            remainder_value = '0;
            half_value = {1'b1, {(F-1){1'b0}}};
            scaled = '0;
            value = '0;

            if (lower_enable) begin
                lookup_fault = (bank_bad[i_lookup_bank][0] !== 1'b0) ||
                    (upper_enable && (bank_bad[i_lookup_bank][1] !== 1'b0));
                lookup_corrected = bank_corrected[i_lookup_bank][0] ||
                    (upper_enable && bank_corrected[i_lookup_bank][1]);

                if (!lookup_fault) begin
                    y0 = i_lookup_output_signed ?
                        $signed({bank_lower[i_lookup_bank][W-1], bank_lower[i_lookup_bank]}) :
                        $signed({1'b0, bank_lower[i_lookup_bank]});
                    value = (W + 2)'(y0);

                    if ((SUPPORT_INTERPOLATION == 1) && upper_enable) begin
                        y1 = i_lookup_output_signed ?
                            $signed({bank_upper[i_lookup_bank][W-1], bank_upper[i_lookup_bank]}) :
                            $signed({1'b0, bank_upper[i_lookup_bank]});
                        delta = y1 - y0;
                        product_value = PRODUCT'(delta) * PRODUCT'($signed({1'b0, fraction}));
                        magnitude = product_value < 0 ? $unsigned(-product_value) :
                            $unsigned(product_value);
                        quotient = magnitude >> F;
                        remainder_value = magnitude[F-1:0];

                        if (i_lookup_round_mode && ((remainder_value > half_value) ||
                            ((remainder_value == half_value) && quotient[0])))
                            quotient = quotient + PRODUCT'(1);

                        scaled = (W + 2)'(quotient);
                        if (product_value < 0)
                            scaled = -scaled;

                        value = (W + 2)'(y0) + scaled;
                        if (value < (y0 < y1 ? (W + 2)'(y0) : (W + 2)'(y1)))
                            value = y0 < y1 ? (W + 2)'(y0) : (W + 2)'(y1);

                        if (value > (y0 > y1 ? (W + 2)'(y0) : (W + 2)'(y1)))
                            value = y0 > y1 ? (W + 2)'(y0) : (W + 2)'(y1);
                    end

                    lookup_packet.data = value[W-1:0];
                end
            end

            lookup_packet.code = lookup_error;
            if (lookup_fault)
                lookup_packet.code = LUT_ERR_UNCORRECTABLE;

            lookup_packet.error = lookup_packet.code != LUT_ERR_NONE;
        end

        always_comb begin : program_legality
            program_error = LUT_ERR_NONE;

            if (int'(i_program_bank) >= B)
                program_error = LUT_ERR_BANK;
            else begin
                case (i_program_command)
                    LUT_PROGRAM_WRITE: begin
                        if (bank_valid[i_program_bank])
                            program_error = LUT_ERR_WRITE_COMMITTED;
                    end
                    LUT_PROGRAM_READ: begin end
                    LUT_PROGRAM_COMMIT: begin
                        if (fatal)
                            program_error = LUT_ERR_UNCORRECTABLE;
                        else if (bank_valid[i_program_bank])
                            program_error = LUT_ERR_LIFECYCLE;
                        else if (references[i_program_bank] != 0)
                            program_error = LUT_ERR_BUSY;
                        else if (!bank_complete[i_program_bank])
                            program_error = LUT_ERR_COVERAGE;
                    end
                    LUT_PROGRAM_INVALIDATE: begin
                        if (!bank_valid[i_program_bank])
                            program_error = LUT_ERR_LIFECYCLE;
                        else if (references[i_program_bank] != 0)
                            program_error = LUT_ERR_BUSY;
                    end
                    default: program_error = LUT_ERR_UNKNOWN;
                endcase
            end
        end

        always_comb begin : program_response
            program_packet = '0;
            program_packet.command = i_program_command;
            program_packet.bank = i_program_bank;
            program_packet.address = i_program_address;
            program_packet.code = program_error;
            program_fault = 1'b0;
            program_corrected = 1'b0;

            if (program_known && (int'(i_program_bank) < B)) begin
                program_packet.version = bank_versions[int'(i_program_bank)*V+:V];
                program_packet.table_id = bank_ids[int'(i_program_bank)*T+:T];
                program_packet.quality_id = bank_qualities[int'(i_program_bank)*Q+:Q];
                program_packet.valid_bank = bank_valid[i_program_bank];

                if (legal_commit) begin
                    program_packet.version = program_packet.version + V'(1);
                    program_packet.table_id = i_program_table_id;
                    program_packet.quality_id = i_program_quality_id;
                    program_packet.valid_bank = 1'b1;
                end

                if (legal_invalidate) begin
                    program_packet.table_id = '0;
                    program_packet.quality_id = '0;
                    program_packet.valid_bank = 1'b0;
                end

                if (legal_read) begin
                    program_fault = bank_bad[i_program_bank][0] !== 1'b0;
                    program_corrected = bank_corrected[i_program_bank][0];
                    if (program_fault)
                        program_packet.code = LUT_ERR_UNCORRECTABLE;
                    else
                        program_packet.data = bank_lower[i_program_bank];
                end
            end

            program_packet.error = program_packet.code != LUT_ERR_NONE;
        end

        always_comb begin : event_and_error_update
            events_next = '0;
            detected = LUT_ERR_NONE;

            if (running) begin
                events_next[0] = lookup_take;
                events_next[1] = lookup_finish;
                events_next[2] = (i_lookup_valid === 1'b1) &&!o_lookup_ready;
                events_next[3] = o_result_valid && (i_result_ready === 1'b0);
                events_next[4] = lookup_take && lookup_packet.low_clip;
                events_next[5] = lookup_take && lookup_packet.high_clip;
                events_next[6] = lookup_take && lookup_packet.interpolated;
                events_next[7] = legal_write;
                events_next[8] = legal_read;
                events_next[9] = legal_commit;
                events_next[10] = legal_invalidate;
                events_next[11] = lookup_corrected || program_corrected;
                events_next[12] = lookup_fault || program_fault;

                if (lookup_take && lookup_packet.error)
                    detected = lookup_error;

                if (program_take && program_packet.error)
                    detected = program_error;

                if (lookup_corrected || program_corrected)
                    detected = LUT_ERR_CORRECTED;

                if (lookup_fault || program_fault)
                    detected = LUT_ERR_UNCORRECTABLE;

                if ( ^ {i_rstb, i_flush, i_drain, i_lookup_valid, i_result_ready,
                    i_program_valid, i_program_response_ready, i_error_clear} === 1'bx ||
                    !lookup_known ||!program_known)
                    detected = LUT_ERR_UNKNOWN;

                if (raw_corrupt)
                    detected = LUT_ERR_INTERNAL;
            end

            if (flushing)
                events_next[13] = !lookup_empty;
        end

        always_comb begin : public_outputs
            o_result_valid = running && healthy && result_valid;
            o_result_data = o_result_valid ? result_head.data : '0;
            o_result_bank = o_result_valid ? result_head.bank : '0;
            o_result_table_version = o_result_valid ? result_head.version : '0;
            o_result_table_id = o_result_valid ? result_head.table_id : '0;
            o_result_quality_id = o_result_valid ? result_head.quality_id : '0;
            o_result_context_id = o_result_valid ? result_head.context_id : '0;
            o_result_tag = o_result_valid ? result_head.tag : '0;
            o_result_clipped_low = o_result_valid && result_head.low_clip;
            o_result_clipped_high = o_result_valid && result_head.high_clip;
            o_result_interpolated = o_result_valid && result_head.interpolated;
            o_result_predicated = o_result_valid && result_head.predicated;
            o_result_error = o_result_valid && result_head.error;
            o_result_error_code = o_result_valid ? result_head.code : '0;
            // Flush masks handshakes; completed program records remain in their queue.
            o_program_response_valid = running && healthy && program_valid;
            o_program_response_command = o_program_response_valid ? program_head.command : '0;
            o_program_response_bank = o_program_response_valid ? program_head.bank : '0;
            o_program_response_address = o_program_response_valid ? program_head.address : '0;
            o_program_response_read_data = o_program_response_valid ? program_head.data : '0;
            o_program_response_version = o_program_response_valid ? program_head.version : '0;
            o_program_response_table_id = o_program_response_valid ? program_head.table_id : '0;
            o_program_response_quality_id = o_program_response_valid ? program_head.quality_id : '0;
            o_program_response_bank_valid = o_program_response_valid && program_head.valid_bank;
            o_program_response_error = o_program_response_valid && program_head.error;
            o_program_response_error_code = o_program_response_valid ? program_head.code : '0;
            o_bank_valid = clock_enabled && healthy ? bank_valid : '0;
            o_bank_version = clock_enabled && healthy ? bank_versions : '0;
            o_bank_table_id = clock_enabled && healthy ? bank_ids : '0;
            o_bank_quality_id = clock_enabled && healthy ? bank_qualities : '0;
            o_bank_program_complete = clock_enabled && healthy ? bank_complete : '0;
            o_lookup_queue_occupancy = clock_enabled && healthy ? result_occupancy : '0;
            o_program_queue_occupancy = clock_enabled && healthy ? program_occupancy : '0;
            o_idle = running && healthy && idle;
            o_quiescent = o_idle && clear_allowed && (i_error_clear === 1'b0);
            o_drain_done = running && healthy && (i_drain === 1'b1) && lookup_empty;
            o_flushed = clock_enabled && events[13];
            o_error = clock_enabled && (sticky_error != LUT_ERR_NONE);
            o_error_code = clock_enabled ? sticky_error : ERROR_WIDTH'(LUT_ERR_NONE);
            o_fatal_error = clock_enabled && fatal;
            o_event_lookup_accept = clock_enabled && events[0];
            o_event_lookup_complete = clock_enabled && events[1];
            o_event_lookup_stall = clock_enabled && events[2];
            o_event_result_stall = clock_enabled && events[3];
            o_event_clip_low = clock_enabled && events[4];
            o_event_clip_high = clock_enabled && events[5];
            o_event_interpolate = clock_enabled && events[6];
            o_event_program_write = clock_enabled && events[7];
            o_event_program_read = clock_enabled && events[8];
            o_event_program_commit = clock_enabled && events[9];
            o_event_program_invalidate = clock_enabled && events[10];
            o_event_table_corrected = clock_enabled && events[11];
            o_event_table_uncorrectable = clock_enabled && events[12];
        end
`ifdef MOSAIC_LUT_UNIT_ASSERTIONS
        wire [11:0] assertion_controls = {o_lookup_ready, o_result_valid, o_program_ready,
            o_program_response_valid, o_idle, o_quiescent, o_drain_done, o_flushed,
            o_error, o_fatal_error, o_event_table_corrected, o_event_table_uncorrectable};
        lut_unit_assertions #(
            .RESULT_BITS($bits(result_t)),
            .PROGRAM_BITS($bits(response_t)),
            .PRODUCT_BITS(PRODUCT),
            .LOOKUP_DEPTH(LQ),
            .PROGRAM_DEPTH(PQ),
            .LOOKUP_OCC(LOOKUP_QUEUE_OCCUPANCY_WIDTH),
            .PROGRAM_OCC(PROGRAM_QUEUE_OCCUPANCY_WIDTH)
        ) u_assertions (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_flush(i_flush),
            .i_fault(raw_corrupt || hard_fatal),
            .i_fatal(fatal),
            .i_lookup_fire(lookup_take),
            .i_commit(legal_commit),
            .i_read(lower_enable),
            .i_predicate(i_lookup_predicate),
            .i_bank_valid(bank_valid[i_lookup_bank]),
            .i_interpolating(upper_enable),
            .i_product(numerical_result.product_value),
            .i_result_valid(o_result_valid),
            .i_result_ready(i_result_ready),
            .i_result(result_head),
            .i_program_valid(o_program_response_valid),
            .i_program_ready(i_program_response_ready),
            .i_program(program_head),
            .i_lookup_occupancy(result_occupancy),
            .i_program_occupancy(program_occupancy),
            .i_finish(lookup_finish),
            .i_accept_event(o_event_lookup_accept),
            .i_complete_event(o_event_lookup_complete),
            .i_controls(assertion_controls)
        );
`endif
    end
endmodule
