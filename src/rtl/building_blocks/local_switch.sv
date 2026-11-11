`timescale 1ns / 1ps

// Static routes over physically sparse muxes, with one elastic item per input.
// Independent output acknowledgements consume separate copies of that item.
module local_switch #(
    parameter NUM_INPUTS = 4,
    parameter NUM_OUTPUTS = 4,
    parameter DATA_WIDTH = 128,
    parameter METADATA_WIDTH = 32,
    parameter CONTEXT_ID_WIDTH = 8,
    localparam int DEFAULT_MASK_BITS =
        ((NUM_INPUTS >= 1 && NUM_OUTPUTS >= 1 &&
            64'(NUM_INPUTS) * 64'(NUM_OUTPUTS) < 64'd2147483647) === 1'b1)
        ? NUM_INPUTS * NUM_OUTPUTS : 1,
    parameter CONNECTIVITY_MASK = {DEFAULT_MASK_BITS{1'b1}},
    parameter SUPPORT_MULTICAST = 1,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((NUM_INPUTS >= 1) === 1'b1) && ( ((^NUM_INPUTS == 1'b0) || (^NUM_INPUTS == 1'b1)) === 1'b1) &&
        ((NUM_OUTPUTS >= 1) === 1'b1) && ( ((^NUM_OUTPUTS == 1'b0) || (^NUM_OUTPUTS == 1'b1)) === 1'b1) &&
        ((DATA_WIDTH >= 1) === 1'b1) && ( ((^DATA_WIDTH == 1'b0) || (^DATA_WIDTH == 1'b1)) === 1'b1) &&
        ((METADATA_WIDTH >= 1) === 1'b1) && ( ((^METADATA_WIDTH == 1'b0) || (^METADATA_WIDTH == 1'b1)) === 1'b1) &&
        ((CONTEXT_ID_WIDTH >= 1) === 1'b1) && ( ((^CONTEXT_ID_WIDTH == 1'b0) || (^CONTEXT_ID_WIDTH == 1'b1)) === 1'b1) &&
        ($bits(CONNECTIVITY_MASK) == DEFAULT_MASK_BITS) && ( ((^CONNECTIVITY_MASK == 1'b0) || (^CONNECTIVITY_MASK == 1'b1)) === 1'b1) &&
        ((SUPPORT_MULTICAST === 0) || (SUPPORT_MULTICAST === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((64'(NUM_INPUTS) * 64'(NUM_OUTPUTS) < 64'd2147483647) === 1'b1) &&
        ((64'(NUM_INPUTS) * (64'(DATA_WIDTH) + 64'(METADATA_WIDTH)) <
            64'd2147483647) === 1'b1) &&
        ((64'(NUM_OUTPUTS) * (64'(DATA_WIDTH) + 64'(METADATA_WIDTH)) <
            64'd2147483647) === 1'b1) &&
        ((64'(NUM_OUTPUTS) * (64'(CONTEXT_ID_WIDTH) + 64'($clog2(NUM_INPUTS)) + 8) +
            8 * 64'(NUM_INPUTS) < 64'd2147483647) === 1'b1) && rows_connected(),
    localparam int I = PARAMETERS_VALID ? NUM_INPUTS : 1,
    localparam int O = PARAMETERS_VALID ? NUM_OUTPUTS : 1,
    localparam int D = PARAMETERS_VALID ? DATA_WIDTH : 1,
    localparam int M = PARAMETERS_VALID ? METADATA_WIDTH : 1,
    localparam int C = PARAMETERS_VALID ? CONTEXT_ID_WIDTH : 1,
    localparam int INPUT_SELECT_WIDTH = I > 1 ? $clog2(I) : 1,
    localparam int INPUT_DATA_WIDTH = I * D,
    localparam int INPUT_METADATA_WIDTH = I * M,
    localparam int OUTPUT_DATA_WIDTH = O * D,
    localparam int OUTPUT_METADATA_WIDTH = O * M,
    localparam int OUTPUT_SELECT_WIDTH = O * INPUT_SELECT_WIDTH,
    localparam int PENDING_WIDTH = I * O
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_flush,
    input logic i_error_clear,
    input logic i_config_valid,
    output logic o_config_ready,
    input logic [O-1:0] i_config_output_enable,
    input logic [OUTPUT_SELECT_WIDTH-1:0] i_config_output_select,
    input logic [C-1:0] i_config_context_id,
    output logic o_config_accepted,
    output logic o_config_rejected,
    input logic [I-1:0] i_input_valid,
    output logic [I-1:0] o_input_ready,
    input logic [INPUT_DATA_WIDTH-1:0] i_input_data,
    input logic [INPUT_METADATA_WIDTH-1:0] i_input_metadata,
    output logic [O-1:0] o_output_valid,
    input logic [O-1:0] i_output_ready,
    output logic [OUTPUT_DATA_WIDTH-1:0] o_output_data,
    output logic [OUTPUT_METADATA_WIDTH-1:0] o_output_metadata,
    output logic [O-1:0] o_active_output_enable,
    output logic [OUTPUT_SELECT_WIDTH-1:0] o_active_output_select,
    output logic [C-1:0] o_active_context_id,
    output logic [I-1:0] o_input_buffered,
    output logic [PENDING_WIDTH-1:0] o_pending_delivery,
    output logic o_idle,
    output logic o_quiescent,
    output logic o_error,
    output logic [local_switch_pkg::ERROR_CODE_WIDTH-1:0] o_error_code,
    output logic o_flushed,
    output logic [I-1:0] o_event_input_accept,
    output logic [O-1:0] o_event_output_transfer,
    output logic [I-1:0] o_event_input_stall,
    output logic [O-1:0] o_event_output_stall,
    output logic [I-1:0] o_event_multicast_accept,
    output logic [I-1:0] o_event_item_complete
);
    import local_switch_pkg::*;

    // No variable-width slice is evaluated for invalid dimensions. The mask is
    // deliberately untyped so an incorrectly sized override cannot be truncated.
    function automatic bit rows_connected();
        bit connected;
        rows_connected = 1'b1;

        if ((NUM_INPUTS >= 1 && NUM_OUTPUTS >= 1 &&
            64'(NUM_INPUTS) * 64'(NUM_OUTPUTS) < 64'd2147483647) !== 1'b1)
            rows_connected = 1'b0;
        else begin
            for (int o = 0; o < NUM_OUTPUTS; o++) begin
                connected = 1'b0;

                for (int i = 0; i < NUM_INPUTS; i++)
                    connected |= CONNECTIVITY_MASK[o*NUM_INPUTS+i] === 1'b1;
                rows_connected &= connected;
            end
        end
    endfunction

    function automatic int edge_count(input int output_index);
        edge_count = 0;
        for (int i = 0; i < I; i++) edge_count += int'(CONNECTIVITY_MASK[output_index*I+i]);
    endfunction

    function automatic int edge_rank(input int output_index, input int source);
        edge_rank = 0;

        for (int i = 0; i < source; i++)
            edge_rank += int'(CONNECTIVITY_MASK[output_index*I+i]);
    endfunction

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        local_switch_parameters_must_be_valid invalid_parameters ();
    end else begin : g_switch
        localparam int P = D + M;
        localparam int ROUTE_BITS = O + OUTPUT_SELECT_WIDTH + C;
        localparam int EVENT_BITS = 4 * I + 2 * O + 3;
        wire run = i_rstb === 1'b1;
        wire reset_b = i_rstb !== 1'b0;
        wire flush = run && (i_flush === 1'b1);
        wire global_known = ( ^ {i_flush, i_error_clear, i_config_valid}) !== 1'bx;
        wire unknown_control = !global_known || ( ^ {i_input_valid, i_output_ready} === 1'bx);
        wire [I-1:0] buffered;
        // Physically isolated inputs leave their payload lanes intentionally unused.
        wire [I*P-1:0] unused_payload;
        wire [PENDING_WIDTH-1:0] pending;
        wire [PENDING_WIDTH-1:0] destinations;
        wire [I-1:0] input_accept;
        wire [O-1:0] output_transfer;
        wire [I-1:0] item_complete;
        wire [I-1:0] multicast_accept;
        wire [I-1:0] input_stall;
        wire [O-1:0] output_stall;
        wire [2:0] state_errors [I];
        logic [2:0] state_error;
        logic [2:0] config_error;
        wire [EVENT_BITS-1:0] events;
        wire operation_allowed = run && (i_flush === 1'b0) && global_known &&
            (state_error == SWITCH_ERR_NONE);
        wire config_window = operation_allowed && o_idle && (i_config_valid === 1'b1);
        wire traffic = operation_allowed&&!config_window;
        wire config_accept = o_config_ready && (i_config_valid === 1'b1);
        wire config_good = config_accept && (config_error == SWITCH_ERR_NONE);
        wire config_bad = config_accept && (config_error != SWITCH_ERR_NONE);
        wire [2:0] detected_error = state_error != SWITCH_ERR_NONE ? state_error :
            unknown_control ? SWITCH_ERR_UNKNOWN : config_bad ? config_error : SWITCH_ERR_NONE;
        wire clear_error = o_quiescent&&!config_accept && (i_error_clear === 1'b1) &&
            (detected_error == SWITCH_ERR_NONE);
        wire [2:0] next_error = clear_error ? SWITCH_ERR_NONE : detected_error;
        wire error_enable = run && (clear_error ||
            (!o_error && (detected_error != SWITCH_ERR_NONE)));
        wire [EVENT_BITS-1:0] next_events = {config_good, config_bad,
            flush&&!o_idle, input_accept, output_transfer, input_stall, output_stall,
            multicast_accept, item_complete};

        assign o_idle = (buffered === '0) && (pending === '0);
        assign o_quiescent = operation_allowed && o_idle && !( | input_accept) &&
            !( | output_transfer);
        assign o_config_ready = o_quiescent;
        assign o_error = o_error_code != SWITCH_ERR_NONE;
        assign {o_config_accepted, o_config_rejected, o_flushed, o_event_input_accept,
            o_event_output_transfer, o_event_input_stall, o_event_output_stall,
            o_event_multicast_accept, o_event_item_complete} = run ? events : '0;

        // Input control unknowns are diagnosed, not coerced into transfers. Each
        // known output acknowledgement remains independent of unrelated X/Z ready.
        for (genvar o = 0; o < O; o++) begin : g_output
            localparam int K = edge_count(o);
            localparam int SELECT_BITS = K > 1 ? $clog2(K) : 1;
            wire [K-1:0][P+1:0] mux_inputs;
            wire [P+1:0] selected_payload;
            wire [I-1:0] source_onehot;
            wire unused_mux_valid;
            logic [SELECT_BITS-1:0] compact_select;
            logic selected_exists;

            // Share one decoded route between destination capture and sparse
            // mux selection. Disabled outputs keep the select cone inactive.
            decoder #(.NUM_OUTPUTS(I)) u_source_decode (
                .i_enable(o_active_output_enable[o]),
                .i_select(o_active_output_select[o*INPUT_SELECT_WIDTH+:INPUT_SELECT_WIDTH]),
                .o_decoded(source_onehot),
                .o_select_valid()
            );

            // Only physically connected sources enter this common mux. Sparse
            // profiles have fewer mux lanes, rather than a rejected full crossbar.
            for (genvar i = 0; i < I; i++) begin : g_edge
                if (CONNECTIVITY_MASK[o*I+i]) begin : g_connected
                    localparam int RANK = edge_rank(o, i);
                    assign mux_inputs[RANK] = {buffered[i], pending[i*O+o], unused_payload[i*P+:P]};
                    assign destinations[i*O+o] = source_onehot[i];
                end else begin : g_absent
                    assign destinations[i*O+o] = 1'b0;
                end
            end

            always_comb begin
                compact_select = '0;
                selected_exists = 1'b0;

                for (int i = 0; i < I; i++) begin
                    if (CONNECTIVITY_MASK[o*I+i] && source_onehot[i]) begin
                        compact_select = SELECT_BITS'(edge_rank(o, i));
                        selected_exists = 1'b1;
                    end
                end
            end

            mux #(.NUM_INPUTS(K), .DATA_WIDTH(P + 2)) u_source (
                .i_data(mux_inputs),
                .i_select(compact_select),
                .o_data(selected_payload),
                .o_select_valid(unused_mux_valid)
            );

            assign o_output_valid[o] = traffic && (o_active_output_enable[o] === 1'b1) &&
                selected_exists && (selected_payload[P+1] === 1'b1) &&
                (selected_payload[P] === 1'b1);
            assign output_transfer[o] = o_output_valid[o] && (i_output_ready[o] === 1'b1);
            assign output_stall[o] = o_output_valid[o] && (i_output_ready[o] === 1'b0);

            operand_isolation #(.WIDTH(P)) u_output (
                .i_data(selected_payload[P-1:0]),
                .i_isolate(!o_output_valid[o]),
                .o_data({o_output_data[o*D+:D], o_output_metadata[o*M+:M]})
            );
        end

        for (genvar i = 0; i < I; i++) begin : g_input
            wire [O-1:0] saved = pending[i*O+:O];
            wire [O-1:0] capture = destinations[i*O+:O];
            wire [O-1:0] delivered = saved & output_transfer;
            wire [O-1:0] remaining = saved & ~output_transfer;
            wire slice_ready;
            wire slice_pop = flush || item_complete[i];
            wire pending_enable = flush || input_accept[i] || ( | delivered);
            wire [O-1:0] next_pending = flush ? {O{1'b0}} :
                input_accept[i] ? capture : remaining;

            assign item_complete[i] = traffic && (buffered[i] === 1'b1) &&
                (saved != '0) && (remaining == '0);
            assign o_input_ready[i] = traffic && ( | capture) && slice_ready;
            assign input_accept[i] = o_input_ready[i] && (i_input_valid[i] === 1'b1);
            assign input_stall[i] = traffic && (i_input_valid[i] === 1'b1)&&!o_input_ready[i];
            assign multicast_accept[i] = input_accept[i] && ($countones(capture) > 1);
            assign o_input_buffered[i] = buffered[i] === 1'b1;

            for (genvar o = 0; o < O; o++) begin : g_status
                assign o_pending_delivery[i*O+o] = saved[o] === 1'b1;
            end

            // Diagnose inconsistent ownership before exposing any delivery.
            assign state_errors[i] = ( ^ {buffered[i], saved} === 1'bx) ?
                SWITCH_ERR_BUFFER_STATE : buffered[i] && (saved == '0) ?
                SWITCH_ERR_EMPTY_PENDING : !buffered[i] && (saved != '0) ?
                SWITCH_ERR_BUFFER_STATE : ( | (saved & ~capture)) ?
                SWITCH_ERR_PENDING_ROUTE : SWITCH_ERR_NONE;

            register_slice #(.DATA_WIDTH(P), .ASYNC_RESET(ASYNC_RESET)) u_buffer (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_valid(input_accept[i]),
                .o_ready(slice_ready),
                .i_data({i_input_data[i*D+:D], i_input_metadata[i*M+:M]}),
                .o_valid(buffered[i]),
                .i_ready(slice_pop),
                .o_data(unused_payload[i*P+:P])
            );

            // Flush is a synchronous pop/clear command, never an asynchronous reset.
            dff #(.WIDTH(O), .ASYNC_RESET(ASYNC_RESET != 0)) u_pending (
                .i_clk(i_clk),
                .i_rstb(reset_b),
                .i_enable(pending_enable),
                .i_d(next_pending),
                .o_q(pending[i*O+:O])
            );
        end

        always_comb begin
            state_error = SWITCH_ERR_NONE;

            for (int i = 0; i < I; i++)
                if (state_error == SWITCH_ERR_NONE) state_error = state_errors[i];

        end

        always_comb begin

            config_error = SWITCH_ERR_NONE;

            if (config_accept) begin
                if ( ^ {i_config_output_enable, i_config_output_select,
                    i_config_context_id} === 1'bx)
                    config_error = SWITCH_ERR_UNKNOWN;
                else begin
                    for (int o = 0; o < O; o++) begin
                        if (i_config_output_enable[o] && (config_error == SWITCH_ERR_NONE)) begin
                            if (32'(i_config_output_select[o*INPUT_SELECT_WIDTH+:
                                INPUT_SELECT_WIDTH]) >= I) config_error = SWITCH_ERR_SOURCE;
                            else if (!CONNECTIVITY_MASK[o*I+32'(i_config_output_select[
                                o*INPUT_SELECT_WIDTH+:INPUT_SELECT_WIDTH])])
                                config_error = SWITCH_ERR_CONNECTIVITY;
                            else if (SUPPORT_MULTICAST == 0) begin
                                for (int p = 0; p < o; p++)
                                    if (i_config_output_enable[p] &&
                                        (i_config_output_select[p*INPUT_SELECT_WIDTH+:
                                            INPUT_SELECT_WIDTH] == i_config_output_select[
                                            o*INPUT_SELECT_WIDTH+:INPUT_SELECT_WIDTH]))
                                        config_error = SWITCH_ERR_MULTICAST;
                            end
                        end
                    end
                end
            end
        end

        dff #(.WIDTH(ROUTE_BITS), .ASYNC_RESET(ASYNC_RESET != 0)) u_routes (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(config_good),
            .i_d({i_config_output_enable, i_config_output_select, i_config_context_id}),
            .o_q({o_active_output_enable, o_active_output_select, o_active_context_id})
        );

        dff #(.WIDTH(local_switch_pkg::ERROR_CODE_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0))
            u_error (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(error_enable),
            .i_d(next_error),
            .o_q(o_error_code)
        );

        dff #(.WIDTH(EVENT_BITS), .ASYNC_RESET(ASYNC_RESET != 0)) u_events (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(run && ( | {next_events, events})),
            .i_d(next_events),
            .o_q(events)
        );

`ifdef MOSAIC_LOCAL_SWITCH_ASSERTIONS
        local_switch_assertions #(
            .I(I),
            .O(O),
            .D(D),
            .M(M),
            .C(C),
            .S(INPUT_SELECT_WIDTH),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_assertions (.*);
`endif
    end
endmodule
