`timescale 1ns / 1ps
`default_nettype none

// Canonical framing and lane-local byte clamping with an optional elastic entry.
// All runtime row boundaries use a wrapping counter, never divide or modulo.
module stream_formatter #(
    parameter DATA_WIDTH = 128,
    parameter NUM_LANES = 4,
    parameter COUNT_WIDTH = 16,
    parameter DATATYPE_WIDTH = 6,
    parameter CHANNEL_ID_WIDTH = 4,
    parameter CONTEXT_ID_WIDTH = 8,
    parameter REGISTER_OUTPUTS = 1,
    parameter ASYNC_RESET = 0,
    parameter MODE_WIDTH = 1,
    localparam bit PARAMETERS_VALID =
        ((DATA_WIDTH >= 8) === 1'b1) && (^DATA_WIDTH !== 1'bx) &&
        ((NUM_LANES >= 1) === 1'b1) && (^NUM_LANES !== 1'bx) &&
        ((DATA_WIDTH % 8 == 0) === 1'b1) &&
        ((DATA_WIDTH % (NUM_LANES > 0 ? NUM_LANES : 1) == 0) === 1'b1) &&
        (((DATA_WIDTH / (NUM_LANES > 0 ? NUM_LANES : 1)) % 8 == 0) === 1'b1) &&
        ((COUNT_WIDTH >= 1) === 1'b1) && (^COUNT_WIDTH !== 1'bx) &&
        ((DATATYPE_WIDTH >= 1) === 1'b1) && (^DATATYPE_WIDTH !== 1'bx) &&
        ((CHANNEL_ID_WIDTH >= 1) === 1'b1) && (^CHANNEL_ID_WIDTH !== 1'bx) &&
        ((CONTEXT_ID_WIDTH >= 1) === 1'b1) && (^CONTEXT_ID_WIDTH !== 1'bx) &&
        ((REGISTER_OUTPUTS === 0) || (REGISTER_OUTPUTS === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) && (MODE_WIDTH === 1) &&
        ((128'(DATA_WIDTH) + 128'(DATA_WIDTH) / 8 + 128'(NUM_LANES) +
            2 * 128'(COUNT_WIDTH) + 128'(DATATYPE_WIDTH) + 128'(CHANNEL_ID_WIDTH) +
            128'(CONTEXT_ID_WIDTH) + 64 < 128'd2147483647) === 1'b1),
    localparam int D = PARAMETERS_VALID ? DATA_WIDTH : 8,
    localparam int L = PARAMETERS_VALID ? NUM_LANES : 1,
    localparam int C = PARAMETERS_VALID ? COUNT_WIDTH : 1,
    localparam int F = PARAMETERS_VALID ? DATATYPE_WIDTH : 1,
    localparam int H = PARAMETERS_VALID ? CHANNEL_ID_WIDTH : 1,
    localparam int T = PARAMETERS_VALID ? CONTEXT_ID_WIDTH : 1,
    localparam int DATA_BYTES = D / 8,
    localparam int LANE_WIDTH = D / L,
    localparam int LANE_BYTES = LANE_WIDTH / 8,
    localparam int INDEX_WIDTH = C
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_flush,
    input logic i_error_clear,
    input logic i_config_valid,
    output logic o_config_ready,
    input logic i_mode,
    input logic [C-1:0] i_frame_beats,
    input logic [C-1:0] i_row_beats,
    input logic [L-1:0] i_lane_enable,
    input logic [F-1:0] i_datatype,
    input logic [H-1:0] i_channel_id,
    input logic [T-1:0] i_context_id,
    input logic i_emit_end_of_stream,
    input logic i_valid,
    output logic o_ready,
    input logic [D-1:0] i_data,
    input logic [DATA_BYTES-1:0] i_keep,
    input logic [L-1:0] i_lane_mask,
    input logic i_first,
    input logic i_last,
    input logic i_row_first,
    input logic i_row_last,
    input logic i_end_of_stream,
    input logic [F-1:0] i_stream_datatype,
    input logic [H-1:0] i_stream_channel_id,
    input logic [T-1:0] i_stream_context_id,
    input logic i_error,
    output logic o_valid,
    input logic i_ready,
    output logic [D-1:0] o_data,
    output logic [DATA_BYTES-1:0] o_keep,
    output logic [L-1:0] o_lane_mask,
    output logic o_first,
    output logic o_last,
    output logic o_row_first,
    output logic o_row_last,
    output logic o_end_of_stream,
    output logic [F-1:0] o_datatype,
    output logic [H-1:0] o_channel_id,
    output logic [T-1:0] o_context_id,
    output logic o_stream_error,
    output logic [stream_formatter_pkg::FORMAT_ERROR_WIDTH-1:0] o_format_error_code,
    output logic o_idle,
    output logic o_busy,
    output logic o_frame_started,
    output logic o_input_accepted,
    output logic o_output_accepted,
    output logic o_frame_completed,
    output logic o_completed_with_error,
    output logic o_frame_aborted,
    output logic [C-1:0] o_beats_accepted,
    output logic [C-1:0] o_beats_emitted,
    output logic o_format_error_seen,
    output logic o_input_error_seen,
    output logic o_error,
    output logic [stream_formatter_pkg::CONFIG_ERROR_WIDTH-1:0] o_config_error_code
);
    import stream_formatter_pkg::*;

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        stream_formatter_parameters_must_be_valid invalid_parameters ();
    end else begin : g_formatter
        // These structures depend on public geometry and therefore remain local.
        typedef struct packed {
            logic mode;
            logic [C-1:0] frame_beats;
            logic [C-1:0] row_beats;
            logic [L-1:0] lanes;
            logic [F-1:0] datatype;
            logic [H-1:0] channel;
            logic [T-1:0] context_id;
            logic eos;
        } configuration_t;

        typedef struct packed {
            logic [D-1:0] data;
            logic [DATA_BYTES-1:0] keep;
            logic [L-1:0] lanes;
            logic first;
            logic last;
            logic row_first;
            logic row_last;
            logic eos;
            logic [F-1:0] datatype;
            logic [H-1:0] channel;
            logic [T-1:0] context_id;
            logic error;
            logic [FORMAT_ERROR_WIDTH-1:0] code;
        } beat_t;

        localparam int CLAIM_BITS = 5 + F + H + T;
        wire run = i_rstb === 1'b1;
        wire reset_b = i_rstb !== 1'b0;
        wire normal = run && i_flush === 1'b0;
        wire flushing = run && i_flush === 1'b1;
        wire active;
        wire buffered;
        wire room;
        wire [C-1:0] row_index;
        wire [8:0] unused_counter_status;
        wire [5:0] events;
        configuration_t configuration;
        configuration_t new_configuration;
        beat_t direct_beat;
        beat_t selected_beat;
        wire config_accept = o_config_ready && i_config_valid === 1'b1;
        config_error_t config_error;
        wire start;
        wire reject;
        wire accepting = normal && active && o_beats_accepted < configuration.frame_beats;
        wire presented = accepting && i_valid === 1'b1;
        wire validate = presented && configuration.mode == FORMAT_VALIDATE;
        wire input_accept = o_ready && i_valid === 1'b1;
        wire output_accept = o_valid && i_ready === 1'b1;
        wire finish = output_accept && o_last;
        wire abort_frame = flushing && (active || buffered);
        wire clear_error = normal && !o_busy && i_error_clear === 1'b1 && !reject;
        wire [L-1:0] effective_lanes;
        wire [DATA_BYTES-1:0] effective_keep;
        wire [D-1:0] clamped_data;
        wire [L-1:0] unused_lane_isolate;
        wire [L-1:0] unused_lane_write;
        logic [L-1:0] known_lanes;
        logic [DATA_BYTES-1:0] known_keep;
        wire [CLAIM_BITS-1:0] claims;
        wire [CLAIM_BITS-1:0] expected_claims;
        logic [FORMAT_CLASSES-1:0] detected;
        logic [FORMAT_ERROR_WIDTH-1:0] format_code;
        // Bindable, independent per-class events preserve every simultaneous fault.
        wire [FORMAT_CLASSES-1:0] format_error_events = detected & {FORMAT_CLASSES{input_accept}};

        assign o_busy = active || buffered;
        assign o_idle = !o_busy && !o_error;
        assign o_error = o_config_error_code != CONFIG_ERR_NONE;
        assign o_config_ready = normal && !o_busy && !o_error;
        assign {o_frame_started, o_input_accepted, o_output_accepted, o_frame_completed,
            o_completed_with_error, o_frame_aborted} = run ? events : '0;
        assign new_configuration = {i_mode, i_frame_beats, i_row_beats, i_lane_enable,
            i_datatype, i_channel_id, i_context_id, i_emit_end_of_stream};

        // All known datatype identifiers are supported opaque labels in this
        // repository-local profile; no numerical conversion is performed.
        always_comb begin
            config_error = CONFIG_ERR_NONE;

            if (config_accept) begin
                if (^{i_mode, i_frame_beats, i_row_beats, i_lane_enable, i_datatype,
                    i_channel_id, i_context_id, i_emit_end_of_stream} === 1'bx)
                    config_error = CONFIG_ERR_UNKNOWN;
                else if (i_frame_beats == '0) config_error = CONFIG_ERR_FRAME_ZERO;
                else if (i_row_beats == '0) config_error = CONFIG_ERR_ROW_ZERO;
                else if (i_row_beats > i_frame_beats) config_error = CONFIG_ERR_ROW_RANGE;
                else if (i_lane_enable == '0) config_error = CONFIG_ERR_LANES_EMPTY;
            end
        end

        write_gate u_configuration_write (
            .i_write_enable(config_accept),
            .i_suppress(config_error != stream_formatter_pkg::CONFIG_ERR_NONE),
            .o_write_enable(start),
            .o_write_suppressed(reject)
        );

        dff #(.WIDTH($bits(configuration_t))) u_configuration (
            .i_clk(i_clk),
            .i_rstb(1'b1),
            .i_enable(start),
            .i_d(new_configuration),
            .o_q(configuration)
        );

        dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_active (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(flushing || start || finish),
            .i_d(start && !flushing),
            .o_q(active)
        );

        dff #(.WIDTH(CONFIG_ERROR_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_error (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(clear_error || (reject && !o_error)),
            .i_d(clear_error ? stream_formatter_pkg::CONFIG_ERR_NONE : config_error),
            .o_q(o_config_error_code)
        );

        counter #(.WIDTH(C), .ASYNC_RESET(ASYNC_RESET != 0)) u_accepted (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(input_accept),
            .i_clear(flushing || start),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value({C{1'b0}}),
            .o_count(o_beats_accepted),
            .o_overflow(unused_counter_status[0]),
            .o_underflow(unused_counter_status[1]),
            .o_terminal(unused_counter_status[2])
        );

        counter #(.WIDTH(C), .ASYNC_RESET(ASYNC_RESET != 0)) u_emitted (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(output_accept),
            .i_clear(flushing || start),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value({C{1'b0}}),
            .o_count(o_beats_emitted),
            .o_overflow(unused_counter_status[3]),
            .o_underflow(unused_counter_status[4]),
            .o_terminal(unused_counter_status[5])
        );

        counter #(.WIDTH(C), .ASYNC_RESET(ASYNC_RESET != 0)) u_row (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(input_accept),
            .i_clear(flushing || start || (input_accept && direct_beat.row_last)),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value({C{1'b0}}),
            .o_count(row_index),
            .o_overflow(unused_counter_status[6]),
            .o_underflow(unused_counter_status[7]),
            .o_terminal(unused_counter_status[8])
        );

        // Unknown mask bits are rejected and conservatively disable their bytes.
        // Known bits remain usable, so malformed controls still produce one beat.
        always_comb begin
            for (int k = 0; k < L; k++) known_lanes[k] = i_lane_mask[k] === 1'b1;
            for (int b = 0; b < DATA_BYTES; b++) known_keep[b] = i_keep[b] === 1'b1;
        end

        lane_mask #(.LANES(L)) u_lanes (
            .i_operation_valid(presented),
            .i_lane_valid(known_lanes),
            .i_lane_mask(configuration.lanes),
            .i_lane_predicate({L{1'b1}}),
            .o_lane_active(effective_lanes),
            .o_lane_isolate(unused_lane_isolate),
            .o_lane_write_mask(unused_lane_write)
        );

        for (genvar b = 0; b < DATA_BYTES; b++) begin : g_byte
            assign effective_keep[b] = known_keep[b] && effective_lanes[b / LANE_BYTES];

            operand_isolation #(.WIDTH(8)) u_clamp (
                .i_data(i_data[b*8+:8]),
                .i_isolate(!effective_keep[b]),
                .o_data(clamped_data[b*8+:8])
            );
        end

        assign direct_beat.data = clamped_data;
        assign direct_beat.keep = effective_keep;
        assign direct_beat.lanes = effective_lanes;
        assign direct_beat.first = o_beats_accepted == '0;
        assign direct_beat.last = o_beats_accepted == configuration.frame_beats - 1'b1;
        assign direct_beat.row_first = row_index == '0;
        assign direct_beat.row_last = row_index == configuration.row_beats - 1'b1 ||
            direct_beat.last;
        assign direct_beat.eos = configuration.eos && direct_beat.last;
        assign direct_beat.datatype = configuration.datatype;
        assign direct_beat.channel = configuration.channel;
        assign direct_beat.context_id = configuration.context_id;
        assign direct_beat.code = format_code;
        assign direct_beat.error = (i_error !== 1'b0) || |detected;

        // Isolate both operands so generate mode ignores arbitrary incoming claims.
        operand_isolation #(.WIDTH(CLAIM_BITS)) u_claims (
            .i_data({i_first, i_last, i_row_first, i_row_last, i_end_of_stream,
                i_stream_datatype, i_stream_channel_id, i_stream_context_id}),
            .i_isolate(!validate),
            .o_data(claims)
        );

        operand_isolation #(.WIDTH(CLAIM_BITS)) u_expected_claims (
            .i_data({direct_beat.first, direct_beat.last, direct_beat.row_first,
                direct_beat.row_last, direct_beat.eos, configuration.datatype,
                configuration.channel, configuration.context_id}),
            .i_isolate(!validate),
            .o_data(expected_claims)
        );

        always_comb begin
            detected = '0;
            format_code = FORMAT_ERR_NONE;

            if (presented) begin
                detected[FORMAT_ERR_UNKNOWN_CONTROL-1] =
                    (^{i_lane_mask, i_keep, i_error} === 1'bx) || (^claims === 1'bx);
                detected[FORMAT_ERR_EMPTY_BEAT-1] = known_lanes == '0;

                for (int k = 0; k < L; k++) begin
                    if (known_lanes[k] != (|known_keep[k*LANE_BYTES+:LANE_BYTES]))
                        detected[FORMAT_ERR_LANE_KEEP-1] = 1'b1;
                end

                // Framing and identity slices are constants after elaboration.
                detected[FORMAT_ERR_FIRST-1] = claims[CLAIM_BITS-1] !==
                    expected_claims[CLAIM_BITS-1];
                detected[FORMAT_ERR_LAST-1] = claims[CLAIM_BITS-2] !==
                    expected_claims[CLAIM_BITS-2];
                detected[FORMAT_ERR_ROW_FIRST-1] = claims[CLAIM_BITS-3] !==
                    expected_claims[CLAIM_BITS-3];
                detected[FORMAT_ERR_ROW_LAST-1] = claims[CLAIM_BITS-4] !==
                    expected_claims[CLAIM_BITS-4];
                detected[FORMAT_ERR_END_OF_STREAM-1] = claims[CLAIM_BITS-5] !==
                    expected_claims[CLAIM_BITS-5];
                detected[FORMAT_ERR_DATATYPE-1] = claims[T+H+:F] !== expected_claims[T+H+:F];
                detected[FORMAT_ERR_CHANNEL-1] = claims[T+:H] !== expected_claims[T+:H];
                detected[FORMAT_ERR_CONTEXT-1] = claims[T-1:0] !== expected_claims[T-1:0];

                // Lowest nonzero code wins while the complete bitmap is retained.
                for (int k = FORMAT_CLASSES - 1; k >= 0; k--)
                    if (detected[k]) format_code = FORMAT_ERROR_WIDTH'(k + 1);
            end
        end

        if (REGISTER_OUTPUTS == 1) begin : g_registered
            wire stored_valid;
            wire [$bits(beat_t)-1:0] stored_beat;

            // Flush clears only slice validity, synchronously, through its ready
            // path. It never creates an asynchronous reset for payload storage.
            register_slice #(
                .DATA_WIDTH($bits(beat_t)),
                .ASYNC_RESET(ASYNC_RESET)
            ) u_slice (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_valid(presented),
                .o_ready(room),
                .i_data(direct_beat),
                .o_valid(stored_valid),
                .i_ready(flushing || (normal && i_ready === 1'b1)),
                .o_data(stored_beat)
            );

            assign buffered = stored_valid;
            assign o_ready = accepting && room;
            assign o_valid = normal && stored_valid;
            assign selected_beat = stored_beat;
        end else begin : g_combinational
            assign buffered = 1'b0;
            assign room = i_ready === 1'b1;
            assign o_ready = accepting && room;
            assign o_valid = presented;
            assign selected_beat = direct_beat;
        end

        operand_isolation #(.WIDTH($bits(beat_t))) u_output (
            .i_data(selected_beat),
            .i_isolate(!o_valid),
            .o_data({o_data, o_keep, o_lane_mask, o_first, o_last, o_row_first,
                o_row_last, o_end_of_stream, o_datatype, o_channel_id, o_context_id,
                o_stream_error, o_format_error_code})
        );

        dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_format_error (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(flushing || start || input_accept),
            .i_d(!flushing && !start && (o_format_error_seen || |detected)),
            .o_q(o_format_error_seen)
        );

        dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_input_error (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(flushing || start || input_accept),
            .i_d(!flushing && !start && (o_input_error_seen || i_error === 1'b1)),
            .o_q(o_input_error_seen)
        );

        dff #(.WIDTH(6), .ASYNC_RESET(ASYNC_RESET != 0)) u_events (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run),
            .i_d({start, input_accept, output_accept, finish,
                finish && (o_format_error_seen || o_input_error_seen || o_stream_error),
                abort_frame}),
            .o_q(events)
        );
    end
endmodule
`default_nettype wire
