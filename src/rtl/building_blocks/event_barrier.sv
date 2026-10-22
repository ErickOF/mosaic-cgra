`timescale 1ns / 1ps

// Registered event bank and reusable barriers. All count updates share one
// atomic four-client scheduler. Internal arbiters permit candidate withdrawal;
// priorities advance only after the complete transaction commits.
module event_barrier #(
    parameter NUM_EVENTS = 16,
    parameter EVENT_COUNT_WIDTH = 4,
    parameter NUM_WAIT_SLOTS = 4,
    parameter WAIT_RESULT_QUEUE_DEPTH = 4,
    parameter NUM_BARRIERS = 4,
    parameter MAX_PARTICIPANTS = 16,
    parameter BARRIER_RELEASE_QUEUE_DEPTH = 4,
    parameter GENERATION_WIDTH = 4,
    parameter CONTEXT_ID_WIDTH = 8,
    parameter WAITER_TAG_WIDTH = 8,
    parameter BARRIER_TAG_WIDTH = 8,
    parameter SUPPORT_WAIT_CONSUME = 1,
    parameter SUPPORT_WAIT_CANCEL = 1,
    parameter SUPPORT_BARRIER_EVENTS = 1,
    parameter PROTECT_STATE = 0,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((NUM_EVENTS >= 1) === 1'b1) &&
        ( ^ NUM_EVENTS !== 1'bx) &&
        ((EVENT_COUNT_WIDTH >= 1) === 1'b1) &&
        ( ^ EVENT_COUNT_WIDTH !== 1'bx) &&
        ((NUM_WAIT_SLOTS >= 1) === 1'b1) &&
        ( ^ NUM_WAIT_SLOTS !== 1'bx) &&
        ((WAIT_RESULT_QUEUE_DEPTH >= 1) === 1'b1) &&
        ( ^ WAIT_RESULT_QUEUE_DEPTH !== 1'bx) &&
        ((NUM_BARRIERS >= 1) === 1'b1) &&
        ( ^ NUM_BARRIERS !== 1'bx) &&
        ((MAX_PARTICIPANTS >= 1) === 1'b1) &&
        ( ^ MAX_PARTICIPANTS !== 1'bx) &&
        ((BARRIER_RELEASE_QUEUE_DEPTH >= 1) === 1'b1) &&
        ( ^ BARRIER_RELEASE_QUEUE_DEPTH !== 1'bx) &&
        ((GENERATION_WIDTH >= 2) === 1'b1) &&
        ( ^ GENERATION_WIDTH !== 1'bx) &&
        ((CONTEXT_ID_WIDTH >= 1) === 1'b1) &&
        ( ^ CONTEXT_ID_WIDTH !== 1'bx) &&
        ((WAITER_TAG_WIDTH >= 1) === 1'b1) &&
        ( ^ WAITER_TAG_WIDTH !== 1'bx) &&
        ((BARRIER_TAG_WIDTH >= 1) === 1'b1) &&
        ( ^ BARRIER_TAG_WIDTH !== 1'bx) &&
        ((SUPPORT_WAIT_CONSUME === 0) || (SUPPORT_WAIT_CONSUME === 1)) &&
        ((SUPPORT_WAIT_CANCEL === 0) || (SUPPORT_WAIT_CANCEL === 1)) &&
        ((SUPPORT_BARRIER_EVENTS === 0) || (SUPPORT_BARRIER_EVENTS === 1)) &&
        ((PROTECT_STATE === 0) || (PROTECT_STATE === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((64'(NUM_EVENTS) * 64'(EVENT_COUNT_WIDTH) < 64'd2147483647) === 1'b1) &&
        ((64'(NUM_BARRIERS) * 64'(MAX_PARTICIPANTS) < 64'd2147483647) === 1'b1) &&
        ((64'(NUM_BARRIERS) * 64'(GENERATION_WIDTH) < 64'd2147483647) === 1'b1) &&
        ((64'(NUM_WAIT_SLOTS) < 64'd2147483647) === 1'b1) &&
        ((64'(WAIT_RESULT_QUEUE_DEPTH) < 64'd2147483647) === 1'b1) &&
        ((64'(BARRIER_RELEASE_QUEUE_DEPTH) < 64'd2147483647) === 1'b1) &&
        ((2 * 64'(MAX_PARTICIPANTS) + 64'(CONTEXT_ID_WIDTH) + 64'(BARRIER_TAG_WIDTH) +
            64'($clog2(NUM_EVENTS)) + 3 < 64'd2147483647) === 1'b1) &&
        ((64'(NUM_EVENTS) + 64'(CONTEXT_ID_WIDTH) + 64'(WAITER_TAG_WIDTH) + 4 < 64'd2147483647)
            === 1'b1) &&
        (((64'($clog2(NUM_WAIT_SLOTS)) + 2 + 2 * 64'(NUM_EVENTS) + 64'(CONTEXT_ID_WIDTH) +
            64'(WAITER_TAG_WIDTH) + 3) * 64'(WAIT_RESULT_QUEUE_DEPTH) < 64'd2147483647) === 1'b1) &&
        (((64'($clog2(NUM_BARRIERS)) + 64'(GENERATION_WIDTH) + 64'(CONTEXT_ID_WIDTH) +
            64'(BARRIER_TAG_WIDTH) + 64'(MAX_PARTICIPANTS) + 64'($clog2(NUM_EVENTS)) + 4) *
            64'(BARRIER_RELEASE_QUEUE_DEPTH) < 64'd2147483647) === 1'b1),
    localparam int E = PARAMETERS_VALID ? NUM_EVENTS : 1,
    localparam int K = PARAMETERS_VALID ? EVENT_COUNT_WIDTH : 1,
    localparam int W = PARAMETERS_VALID ? NUM_WAIT_SLOTS : 1,
    localparam int B = PARAMETERS_VALID ? NUM_BARRIERS : 1,
    localparam int P = PARAMETERS_VALID ? MAX_PARTICIPANTS : 1,
    localparam int G = PARAMETERS_VALID ? GENERATION_WIDTH : 1,
    localparam int C = PARAMETERS_VALID ? CONTEXT_ID_WIDTH : 1,
    localparam int WT = PARAMETERS_VALID ? WAITER_TAG_WIDTH : 1,
    localparam int BT = PARAMETERS_VALID ? BARRIER_TAG_WIDTH : 1,
    localparam int WD = PARAMETERS_VALID ? WAIT_RESULT_QUEUE_DEPTH : 1,
    localparam int RD = PARAMETERS_VALID ? BARRIER_RELEASE_QUEUE_DEPTH : 1,
    localparam int EI = E > 1 ? $clog2(E) : 1,
    localparam int WI = W > 1 ? $clog2(W) : 1,
    localparam int BI = B > 1 ? $clog2(B) : 1,
    localparam int PI = P > 1 ? $clog2(P) : 1,
    localparam int QW = $clog2(WD + 1),
    localparam int QR = $clog2(RD + 1),
    localparam int MUTATION_CLIENTS = 4
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_flush,
    input logic i_error_clear,
    input logic i_config_valid,
    input logic i_post_valid,
    input logic i_ack_valid,
    input logic i_wait_valid,
    input logic i_wait_cancel_valid,
    input logic i_wait_result_ready,
    input logic i_barrier_config_valid,
    input logic i_barrier_config_enable,
    input logic i_barrier_release_event_enable,
    input logic i_barrier_arrival_valid,
    input logic i_barrier_release_ready,
    input logic i_wait_consume,
    input logic [C-1:0] i_config_context_id,
    input logic [C-1:0] i_post_context_id,
    input logic [C-1:0] i_ack_context_id,
    input logic [C-1:0] i_wait_context_id,
    input logic [C-1:0] i_wait_cancel_context_id,
    input logic [C-1:0] i_barrier_context_id,
    input logic [C-1:0] i_barrier_arrival_context_id,
    input logic [E-1:0] i_config_event_enable,
    input logic [E-1:0] i_wait_event_mask,
    input logic [EI-1:0] i_post_event_id,
    input logic [EI-1:0] i_ack_event_id,
    input logic [EI-1:0] i_barrier_release_event_id,
    input logic [1:0] i_ack_mode,
    input logic [1:0] i_wait_mode,
    input logic [WI-1:0] i_wait_slot,
    input logic [WI-1:0] i_wait_cancel_slot,
    input logic [WT-1:0] i_wait_tag,
    input logic [WT-1:0] i_wait_cancel_tag,
    input logic [BI-1:0] i_barrier_config_id,
    input logic [BI-1:0] i_barrier_arrival_id,
    input logic [P-1:0] i_barrier_expected_mask,
    input logic [BT-1:0] i_barrier_tag,
    input logic [PI-1:0] i_barrier_participant_id,
    input logic [G-1:0] i_barrier_arrival_generation,
    output logic o_config_ready,
    output logic o_config_accepted,
    output logic o_config_rejected,
    output logic o_post_ready,
    output logic o_post_accepted,
    output logic o_post_rejected,
    output logic o_ack_ready,
    output logic o_ack_accepted,
    output logic o_ack_rejected,
    output logic o_wait_ready,
    output logic o_wait_armed,
    output logic o_wait_rejected,
    output logic o_wait_cancel_ready,
    output logic o_wait_canceled,
    output logic o_wait_cancel_not_found,
    output logic o_wait_result_valid,
    output logic o_wait_result_status,
    output logic o_barrier_config_ready,
    output logic o_barrier_configured,
    output logic o_barrier_config_rejected,
    output logic o_barrier_arrival_ready,
    output logic o_barrier_arrival_accepted,
    output logic o_barrier_arrival_rejected,
    output logic o_barrier_release_valid,
    output logic o_barrier_release_event_enable,
    output logic o_policy_valid,
    output logic o_idle,
    output logic o_quiescent,
    output logic o_flushed,
    output logic o_error,
    output logic o_fatal_error,
    output logic o_event_post,
    output logic o_event_ack,
    output logic o_event_wait_complete,
    output logic o_event_barrier_arrival,
    output logic o_event_barrier_release,
    output logic o_event_duplicate_arrival,
    output logic o_event_mutation_stall,
    output logic [C-1:0] o_active_context_id,
    output logic [C-1:0] o_wait_result_context_id,
    output logic [C-1:0] o_barrier_release_context_id,
    output logic [E-1:0] o_event_pending,
    output logic [E-1:0] o_event_saturated,
    output logic [E-1:0] o_wait_result_matched_mask,
    output logic [E-1:0] o_wait_result_consumed_mask,
    output logic [E*K-1:0] o_event_count,
    output logic [W-1:0] o_wait_slot_active,
    output logic [B-1:0] o_barrier_enable,
    output logic [B*P-1:0] o_barrier_arrived,
    output logic [B*G-1:0] o_barrier_generation,
    output logic [QW-1:0] o_wait_result_occupancy,
    output logic [QR-1:0] o_barrier_release_occupancy,
    output logic [WI-1:0] o_wait_result_slot,
    output logic [1:0] o_wait_result_mode,
    output logic [WT-1:0] o_wait_result_tag,
    output logic [BI-1:0] o_barrier_release_id,
    output logic [G-1:0] o_barrier_release_generation,
    output logic [BT-1:0] o_barrier_release_tag,
    output logic [P-1:0] o_barrier_release_participants,
    output logic [EI-1:0] o_barrier_release_event_id,
    output logic [3:0] o_error_code
);
    import event_barrier_pkg::*;

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        event_barrier_parameters_must_be_valid invalid_parameters ();
    end else begin : g_unit
        localparam int WAIT_BITS = 1 + 2 + E + 1 + C + WT;
        localparam int BARRIER_BITS = 1 + 2 * P + C + BT + 1 + EI;
        localparam int RESULT_BITS = WI + 2 + 2 * E + C + WT + 1;
        localparam int RELEASE_BITS = BI + G + C + BT + P + 1 + EI;
        // Keep unknown external reset from corrupting reusable DFF banks.
        // All enables/handshakes still require a known deasserted reset.
        wire state_rstb = i_rstb !== 1'b0;
        wire [E-1:0] event_enable;
        wire [K-1:0] counts[E];
        wire [G-1:0] generations[B];
        wire [E-1:0] count_corrupt;
        wire [W-1:0] wait_corrupt;
        wire [B-1:0] barrier_corrupt;
        wire [B-1:0] generation_corrupt;
        wire policy_corrupt;
        wire result_corrupt;
        wire release_corrupt;
        wire [2:0] arbiter_corrupt;
        wire state_fault = policy_corrupt || (|count_corrupt) || (|wait_corrupt) ||
            (|barrier_corrupt) || (|generation_corrupt) || result_corrupt ||
            release_corrupt || (|arbiter_corrupt);
        wire valids_known = ( ^ {i_config_valid, i_post_valid, i_ack_valid, i_wait_valid,
            i_wait_cancel_valid, i_barrier_config_valid, i_barrier_arrival_valid} !== 1'bx);
        wire controls_known = valids_known && ( ^ {i_flush, i_error_clear,
            i_wait_result_ready, i_barrier_release_ready} !== 1'bx);
        wire healthy = (i_rstb === 1'b1) &&!o_fatal_error &&!state_fault;
        wire run = healthy && controls_known && (i_flush === 1'b0);
        wire flush = healthy && (i_flush === 1'b1);
        wire other_inputs = {i_post_valid, i_ack_valid, i_wait_valid, i_wait_cancel_valid,
            i_barrier_config_valid, i_barrier_arrival_valid} !== 6'b0;
        wire no_arrivals = o_barrier_arrived == '0;
        wire idle_state = o_event_pending == '0 && o_wait_slot_active == '0 && no_arrivals &&
            o_wait_result_occupancy == '0 && o_barrier_release_occupancy == '0;
        assign o_idle = idle_state && (i_flush === 1'b0) &&!other_inputs;
        assign o_quiescent = run && idle_state &&!other_inputs &&!i_config_valid;
        assign o_config_ready = run && idle_state &&!other_inputs;
        wire config_fire = o_config_ready && i_config_valid;
        wire config_legal = ( ^ {i_config_context_id, i_config_event_enable} !== 1'bx);
        wire operate = run &&!config_fire;

        event_barrier_state #(.WIDTH(1 + C + E), .PROTECTED(PROTECT_STATE != 0),
            .ASYNC_RESET(ASYNC_RESET != 0)) u_policy (
            .i_clk(i_clk),
            .i_rstb(state_rstb),
            .i_enable(config_fire && config_legal),
            .i_data({1'b1, i_config_context_id, i_config_event_enable}),
            .o_data({o_policy_valid, o_active_context_id, event_enable}),
            .o_corrupt(policy_corrupt)
        );

        wire [E-1:0] post_select;
        wire [E-1:0] ack_select;
        wire post_id_valid;
        wire ack_id_valid;

        decoder #(.NUM_OUTPUTS(E)) u_post_decode (
            .i_enable(operate && i_post_valid),
            .i_select(i_post_event_id),
            .o_decoded(post_select),
            .o_select_valid(post_id_valid)
        );

        decoder #(.NUM_OUTPUTS(E)) u_ack_decode (
            .i_enable(operate && i_ack_valid),
            .i_select(i_ack_event_id),
            .o_decoded(ack_select),
            .o_select_valid(ack_id_valid)
        );

        logic post_legal;
        logic ack_legal;
        logic post_space;

        always_comb begin
            post_legal = 1'b0;
            ack_legal = 1'b0;
            post_space = 1'b0;

            if (post_id_valid && o_policy_valid &&
                ( ^ i_post_context_id !== 1'bx) && i_post_context_id == o_active_context_id) begin
                post_legal = event_enable[i_post_event_id] === 1'b1;
                post_space = counts[i_post_event_id] != {K{1'b1}};
            end

            if (ack_id_valid && o_policy_valid &&
                ( ^ {i_ack_mode, i_ack_context_id} !== 1'bx) &&
                i_ack_context_id == o_active_context_id &&
                (i_ack_mode == EVENT_ACK_ONE || i_ack_mode == EVENT_CLEAR_ALL))
                ack_legal = event_enable[i_ack_event_id] && counts[i_ack_event_id] != '0;
        end

        wire [W-1:0] wait_active;
        wire [1:0] wait_mode[W];
        wire [E-1:0] wait_mask[W];
        wire wait_consume[W];
        wire [C-1:0] wait_context[W];
        wire [WT-1:0] wait_tag[W];
        wire [W-1:0] satisfied;
        wire [E-1:0] matched[W];
        wire [W-1:0] wait_requests;
        wire [WI-1:0] wait_index;
        wire wait_selected;
        wire wait_complete;
        wire cancel_create;
        logic cancel_match;
        logic wait_addressable;
        logic wait_legal;
        logic cancel_known;
        wire result_space;
        wire result_valid;
        wire [RESULT_BITS-1:0] result_input;
        wire [RESULT_BITS-1:0] result_output;
        wire result_create = wait_complete || cancel_create;
        wire [1:0] result_requests;
        wire result_selected;
        wire result_index;
        wire [E-1:0] consume_mask = wait_complete && wait_consume[wait_index] ?
            matched[wait_index] : '0;

        always_comb begin
            wait_addressable = 1'b1;
            wait_legal = 1'b0;
            cancel_match = 1'b0;
            cancel_known = ( ^ {i_wait_cancel_slot, i_wait_cancel_context_id,
                i_wait_cancel_tag} !== 1'bx);

            if (( ^ i_wait_slot !== 1'bx) && 32'(i_wait_slot) < W) begin
                wait_addressable = !wait_active[i_wait_slot];

                if (( ^ {i_wait_mode, i_wait_event_mask, i_wait_consume,
                    i_wait_context_id, i_wait_tag} !== 1'bx))
                    wait_legal = o_policy_valid && wait_addressable &&
                        i_wait_context_id == o_active_context_id && i_wait_event_mask != '0 &&
                        (i_wait_event_mask & ~ event_enable) == '0 &&
                        (i_wait_mode == EVENT_WAIT_ANY || i_wait_mode == EVENT_WAIT_ALL) &&
                        (!i_wait_consume || SUPPORT_WAIT_CONSUME == 1);
            end

            if (SUPPORT_WAIT_CANCEL == 1 && cancel_known &&
                32'(i_wait_cancel_slot) < W && o_policy_valid)
                cancel_match = wait_active[i_wait_cancel_slot] &&
                    i_wait_cancel_context_id == o_active_context_id &&
                    i_wait_cancel_context_id == wait_context[i_wait_cancel_slot] &&
                    i_wait_cancel_tag == wait_tag[i_wait_cancel_slot];
        end

        assign o_wait_ready = operate && wait_addressable;
        wire arm_fire = i_wait_valid && o_wait_ready;
        assign o_wait_cancel_ready = operate && (!cancel_match || cancel_create);
        wire cancel_miss = i_wait_cancel_valid && o_wait_cancel_ready &&!cancel_match;

        for (genvar w = 0; w < W; w++) begin : g_wait
            wire [E-1:0] pending_mask = wait_active[w] ? wait_mask[w] & o_event_pending : '0;
            wire any_valid;
            wire [EI-1:0] unused_index;
            wire [E-1:0] any_mask;
            wire unused_multiple;

            priority_encoder #(.WIDTH(E)) u_any (
                .i_request(pending_mask),
                .o_valid(any_valid),
                .o_index(unused_index),
                .o_onehot(any_mask),
                .o_multiple(unused_multiple)
            );

            assign matched[w] = wait_mode[w] == EVENT_WAIT_ANY ? any_mask : wait_mask[w];
            assign satisfied[w] = wait_active[w] && (wait_mode[w] == EVENT_WAIT_ANY ?
                any_valid : pending_mask == wait_mask[w]);
            assign wait_requests[w] = operate && result_space && satisfied[w] &&
                !(i_wait_cancel_valid && cancel_match && i_wait_cancel_slot == WI'(w));
            wire arm = arm_fire && wait_legal && i_wait_slot == WI'(w);
            wire remove_wait = (wait_complete && wait_index == WI'(w)) ||
                (cancel_create && i_wait_cancel_slot == WI'(w));
            wire [WAIT_BITS-1:0] next_wait = flush ? '0 : arm ?
                {1'b1, i_wait_mode, i_wait_event_mask,
                    SUPPORT_WAIT_CONSUME == 1 && i_wait_consume,
                    i_wait_context_id, i_wait_tag} :
                {1'b0, wait_mode[w], wait_mask[w], wait_consume[w], wait_context[w], wait_tag[w]};

            event_barrier_state #(
                .WIDTH(WAIT_BITS),
                .PROTECTED(PROTECT_STATE != 0),
                .ASYNC_RESET(ASYNC_RESET != 0)
            ) u_state (
                .i_clk(i_clk),
                .i_rstb(state_rstb),
                .i_enable(flush || arm || remove_wait),
                .i_data(next_wait),
                .o_data({wait_active[w], wait_mode[w], wait_mask[w], wait_consume[w],
                    wait_context[w], wait_tag[w]}),
                .o_corrupt(wait_corrupt[w])
            );
        end

        assign o_wait_slot_active = wait_active;
        assign result_requests[0] = wait_selected;
        assign result_requests[1] = operate && result_space && i_wait_cancel_valid && cancel_match;
        assign cancel_create = result_selected && result_index && operate;

        wire [RD-1:0] release_occupied;
        wire [RD*RELEASE_BITS-1:0] release_contents;
        wire [RELEASE_BITS-1:0] release_input;
        wire [RELEASE_BITS-1:0] release_output;
        wire release_space;
        wire release_valid;
        wire release_create;
        wire [B-1:0] barrier_enabled;
        wire [P-1:0] expected[B];
        wire [P-1:0] arrived[B];
        wire [C-1:0] barrier_context[B];
        wire [BT-1:0] barrier_tag[B];
        wire barrier_event_enable[B];
        wire [EI-1:0] barrier_event[B];
        logic barrier_config_available;
        logic barrier_config_legal;
        logic arrival_legal;
        logic arrival_duplicate;
        logic arrival_stale;
        logic final_arrival;
        logic arrival_event;
        logic arrival_event_space;
        logic [EI-1:0] arrival_event_id;
        logic [P-1:0] next_arrived;
        wire [P-1:0] participant_select;
        wire participant_valid;

        decoder #(.NUM_OUTPUTS(P)) u_participant_decode (
            .i_enable(operate && i_barrier_arrival_valid),
            .i_select(i_barrier_participant_id),
            .o_decoded(participant_select),
            .o_select_valid(participant_valid)
        );

        always_comb begin
            barrier_config_available = 1'b1;
            barrier_config_legal = 1'b0;

            if (( ^ i_barrier_config_id !== 1'bx) && 32'(i_barrier_config_id) < B) begin
                barrier_config_available = arrived[i_barrier_config_id] == '0;

                for (int r = 0; r < RD; r++) begin
                    if (release_occupied[r] &&
                        release_contents[r*RELEASE_BITS+RELEASE_BITS-BI+:BI] ==
                        i_barrier_config_id &&
                        release_contents[r*RELEASE_BITS+RELEASE_BITS-BI-G+:G] ==
                        generations[i_barrier_config_id]) barrier_config_available = 1'b0;
                end

                if (( ^ {i_barrier_config_enable, i_barrier_expected_mask, i_barrier_context_id,
                    i_barrier_tag, i_barrier_release_event_enable,
                    i_barrier_release_event_id} !== 1'bx)) begin
                    barrier_config_legal = o_policy_valid &&
                        i_barrier_context_id == o_active_context_id &&
                        (!i_barrier_config_enable || i_barrier_expected_mask != '0) &&
                        (!i_barrier_release_event_enable || (SUPPORT_BARRIER_EVENTS == 1 &&
                        32'(i_barrier_release_event_id) < E));
                    if (i_barrier_release_event_enable && 32'(i_barrier_release_event_id) < E)
                        barrier_config_legal = barrier_config_legal &&
                            event_enable[i_barrier_release_event_id];
                end
            end
        end

        assign o_barrier_config_ready = operate && barrier_config_available;
        wire barrier_config_fire = i_barrier_config_valid && o_barrier_config_ready;
        wire barrier_config_commit = barrier_config_fire && barrier_config_legal;

        always_comb begin
            arrival_legal = 1'b0;
            arrival_duplicate = 1'b0;
            arrival_stale = 1'b0;
            final_arrival = 1'b0;
            arrival_event = 1'b0;
            arrival_event_id = '0;
            arrival_event_space = 1'b0;
            next_arrived = '0;

            if (( ^ {i_barrier_arrival_id, i_barrier_participant_id,
                i_barrier_arrival_generation, i_barrier_arrival_context_id} !== 1'bx) &&
                operate && i_barrier_arrival_valid &&
                32'(i_barrier_arrival_id) < B && participant_valid) begin
                next_arrived = arrived[i_barrier_arrival_id] | participant_select;
                arrival_duplicate = |(arrived[i_barrier_arrival_id] & participant_select);
                arrival_stale = i_barrier_arrival_generation != generations[i_barrier_arrival_id];
                arrival_legal = o_policy_valid && barrier_enabled[i_barrier_arrival_id] &&
                    i_barrier_arrival_context_id == o_active_context_id &&
                    i_barrier_arrival_context_id == barrier_context[i_barrier_arrival_id] &&
                    |(expected[i_barrier_arrival_id] & participant_select) &&
                    !arrival_duplicate &&!arrival_stale;
                final_arrival = next_arrived == expected[i_barrier_arrival_id];
                arrival_event = barrier_event_enable[i_barrier_arrival_id];
                arrival_event_id = barrier_event[i_barrier_arrival_id];
                if (32'(arrival_event_id) < E)
                    arrival_event_space = counts[arrival_event_id] != {K{1'b1}};
            end
        end
        wire arrival_blocked = barrier_config_fire &&
            i_barrier_config_id == i_barrier_arrival_id;
        wire arrival_candidate = operate && i_barrier_arrival_valid &&!arrival_blocked;
        wire arrival_commit = i_barrier_arrival_valid && o_barrier_arrival_ready && arrival_legal;

        wire [3:0] mutation_requests;
        wire mutation_valid;
        wire [1:0] mutation_index;
        wire mutate = operate && mutation_valid;
        assign mutation_requests[0] = operate && i_post_valid && (!post_legal || post_space);
        assign mutation_requests[1] = operate && i_ack_valid;
        assign mutation_requests[2] = operate && result_selected &&!result_index &&
            wait_consume[wait_index];
        assign mutation_requests[3] = arrival_candidate && arrival_legal && final_arrival &&
            arrival_event && release_space && arrival_event_space;
        assign o_post_ready = operate && mutation_valid && mutation_index == 2'd0;
        assign o_ack_ready = operate && mutation_valid && mutation_index == 2'd1;
        assign wait_complete = operate && result_selected &&!result_index &&
            (!wait_consume[wait_index] || (mutation_valid && mutation_index == 2'd2));
        assign o_barrier_arrival_ready = operate &&!arrival_blocked &&
            (!arrival_legal || !final_arrival || (release_space &&
            (!arrival_event || (mutation_valid && mutation_index == 2'd3))));
        assign release_create = arrival_commit && final_arrival;
        wire post_commit = i_post_valid && o_post_ready && post_legal;
        wire ack_commit = i_ack_valid && o_ack_ready && ack_legal;
        wire release_post = release_create && arrival_event;

        wire [W-1:0] unused_wait_grant_onehot;
        wire unused_wait_grant_lock;
        wire unused_wait_grant_accepted;
        wire unused_wait_contended;
        wire unused_wait_pending;
        wire unused_wait_locked;
        wire [WI-1:0] unused_wait_lock_owner;

        round_robin_arbiter #(
            .NUM_REQUESTERS(W),
            .HAS_LOCK(0),
            .HOLD_PENDING(0),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_wait_arbiter (
            .i_clk(i_clk),
            .i_rstb(state_rstb),
            .i_request(wait_requests),
            .i_eligible('1),
            .i_lock('0),
            .i_accept(wait_complete),
            .i_flush(flush),
            .o_grant_valid(wait_selected),
            .o_grant_index(wait_index),
            .o_protocol_error(arbiter_corrupt[0]),
            .o_grant_onehot(unused_wait_grant_onehot),
            .o_grant_lock(unused_wait_grant_lock),
            .o_grant_accepted(unused_wait_grant_accepted),
            .o_contended(unused_wait_contended),
            .o_pending(unused_wait_pending),
            .o_locked(unused_wait_locked),
            .o_lock_owner(unused_wait_lock_owner)
        );

        wire [1:0] unused_result_grant_onehot;
        wire unused_result_grant_lock;
        wire unused_result_grant_accepted;
        wire unused_result_contended;
        wire unused_result_pending;
        wire unused_result_locked;
        wire unused_result_lock_owner;

        round_robin_arbiter #(
            .NUM_REQUESTERS(2),
            .HAS_LOCK(0),
            .HOLD_PENDING(0),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_result_arbiter (
            .i_clk(i_clk),
            .i_rstb(state_rstb),
            .i_request(result_requests),
            .i_eligible('1),
            .i_lock('0),
            .i_accept(result_create),
            .i_flush(flush),
            .o_grant_valid(result_selected),
            .o_grant_index(result_index),
            .o_protocol_error(arbiter_corrupt[1]),
            .o_grant_onehot(unused_result_grant_onehot),
            .o_grant_lock(unused_result_grant_lock),
            .o_grant_accepted(unused_result_grant_accepted),
            .o_contended(unused_result_contended),
            .o_pending(unused_result_pending),
            .o_locked(unused_result_locked),
            .o_lock_owner(unused_result_lock_owner)
        );

        wire [MUTATION_CLIENTS-1:0] unused_mutation_grant_onehot;
        wire unused_mutation_grant_lock;
        wire unused_mutation_grant_accepted;
        wire unused_mutation_contended;
        wire unused_mutation_pending;
        wire unused_mutation_locked;
        wire [1:0] unused_mutation_lock_owner;

        round_robin_arbiter #(
            .NUM_REQUESTERS(MUTATION_CLIENTS),
            .HAS_LOCK(0),
            .HOLD_PENDING(0),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_mutation_arbiter (
            .i_clk(i_clk),
            .i_rstb(state_rstb),
            .i_request(mutation_requests),
            .i_eligible('1),
            .i_lock('0),
            .i_accept(mutate),
            .i_flush(flush),
            .o_grant_valid(mutation_valid),
            .o_grant_index(mutation_index),
            .o_protocol_error(arbiter_corrupt[2]),
            .o_grant_onehot(unused_mutation_grant_onehot),
            .o_grant_lock(unused_mutation_grant_lock),
            .o_grant_accepted(unused_mutation_grant_accepted),
            .o_contended(unused_mutation_contended),
            .o_pending(unused_mutation_pending),
            .o_locked(unused_mutation_locked),
            .o_lock_owner(unused_mutation_lock_owner)
        );

        for (genvar e = 0; e < E; e++) begin : g_event
            wire increment = (post_commit && post_select[e]) ||
                (release_post && arrival_event_id == EI'(e));
            wire decrement = (ack_commit && ack_select[e]) || consume_mask[e];
            wire clear_count = flush || (ack_commit && ack_select[e] &&
                i_ack_mode == EVENT_CLEAR_ALL);
            wire update_count = clear_count || increment || decrement;
            wire [K-1:0] next_count = clear_count ? '0 :
                increment ? counts[e] + 1'b1 : counts[e] - 1'b1;
            wire unused_overflow;
            wire unused_underflow;
            wire unused_terminal;

            counter #(.WIDTH(K), .ASYNC_RESET(ASYNC_RESET != 0)) u_count (
                .i_clk(i_clk),
                .i_rstb(state_rstb),
                .i_enable(1'b0),
                .i_clear(1'b0),
                .i_load(update_count),
                .i_direction(1'b0),
                .i_load_value(next_count),
                .o_count(counts[e]),
                .o_overflow(unused_overflow),
                .o_underflow(unused_underflow),
                .o_terminal(unused_terminal)
            );

            if (PROTECT_STATE == 1) begin : g_protection
                wire stored_parity;

                dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_parity_bit (
                    .i_clk(i_clk),
                    .i_rstb(state_rstb),
                    .i_enable(update_count),
                    .i_d( ^ next_count),
                    .o_q(stored_parity)
                );

                assign count_corrupt[e] = ( ^ counts[e] === 1'bx) ||
                    ( ^ counts[e] !== stored_parity);
            end else begin : g_unprotected
                assign count_corrupt[e] = ^ counts[e] === 1'bx;
            end
            assign o_event_count[e*K+:K] = counts[e];
            assign o_event_pending[e] = counts[e] != '0;
            assign o_event_saturated[e] = counts[e] == {K{1'b1}};
        end
        for (genvar b = 0; b < B; b++) begin : g_barrier
            wire bank_corrupt;
            wire configure = barrier_config_commit && i_barrier_config_id == BI'(b);
            wire arrive = arrival_commit && i_barrier_arrival_id == BI'(b);
            wire advance = (flush && barrier_enabled[b]) || (arrive && final_arrival);
            wire [G-1:0] next_generation = generations[b] + 1'b1;
            wire [P-1:0] next_mask = flush || (arrive && final_arrival) ? '0 : next_arrived;
            wire [BARRIER_BITS-1:0] next_barrier = configure ?
                {i_barrier_config_enable, i_barrier_expected_mask, {P{1'b0}},
                    i_barrier_context_id, i_barrier_tag,
                    SUPPORT_BARRIER_EVENTS == 1 && i_barrier_release_event_enable,
                    SUPPORT_BARRIER_EVENTS == 1 ? i_barrier_release_event_id : {EI{1'b0}}} :
                {barrier_enabled[b], expected[b], next_mask, barrier_context[b], barrier_tag[b],
                    barrier_event_enable[b], barrier_event[b]};

            event_barrier_state #(
                .WIDTH(BARRIER_BITS),
                .PROTECTED(PROTECT_STATE != 0),
                .ASYNC_RESET(ASYNC_RESET != 0)
            ) u_state (
                .i_clk(i_clk),
                .i_rstb(state_rstb),
                .i_enable(configure || arrive || (flush && arrived[b] != '0)),
                .i_data(next_barrier),
                .o_data({barrier_enabled[b], expected[b], arrived[b], barrier_context[b],
                    barrier_tag[b], barrier_event_enable[b], barrier_event[b]}),
                .o_corrupt(bank_corrupt)
            );

            assign barrier_corrupt[b] = bank_corrupt || ( ^ arrived[b] === 1'bx) ||
                ((arrived[b] & ~ expected[b]) !== {P{1'b0}});
            wire unused_overflow;
            wire unused_underflow;
            wire unused_terminal;

            counter #(.WIDTH(G), .ASYNC_RESET(ASYNC_RESET != 0), .SATURATE(0)) u_generation (
                .i_clk(i_clk),
                .i_rstb(state_rstb),
                .i_enable(1'b0),
                .i_clear(1'b0),
                .i_load(advance),
                .i_direction(1'b0),
                .i_load_value(next_generation),
                .o_count(generations[b]),
                .o_overflow(unused_overflow),
                .o_underflow(unused_underflow),
                .o_terminal(unused_terminal)
            );

            if (PROTECT_STATE == 1) begin : g_protection
                wire stored_parity;

                dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_parity_bit (
                    .i_clk(i_clk),
                    .i_rstb(state_rstb),
                    .i_enable(advance),
                    .i_d( ^ next_generation),
                    .o_q(stored_parity)
                );

                assign generation_corrupt[b] = ( ^ generations[b] === 1'bx) ||
                    ( ^ generations[b] !== stored_parity);
            end else begin : g_unprotected
                assign generation_corrupt[b] = ^ generations[b] === 1'bx;
            end

            assign o_barrier_arrived[b*P+:P] = arrived[b];
            assign o_barrier_generation[b*G+:G] = generations[b];
        end

        assign o_barrier_enable = barrier_enabled;

        assign result_input = cancel_create ?
            {i_wait_cancel_slot, wait_mode[i_wait_cancel_slot], {2*E{1'b0}},
                wait_context[i_wait_cancel_slot], wait_tag[i_wait_cancel_slot],
                EVENT_WAIT_CANCELED} :
            {wait_index, wait_mode[wait_index], matched[wait_index], consume_mask,
                wait_context[wait_index], wait_tag[wait_index], EVENT_WAIT_SATISFIED};
        assign release_input = {i_barrier_arrival_id, generations[i_barrier_arrival_id],
            barrier_context[i_barrier_arrival_id], barrier_tag[i_barrier_arrival_id],
            expected[i_barrier_arrival_id], arrival_event,
            arrival_event ? arrival_event_id : {EI{1'b0}}};
        wire [WD-1:0] unused_result_occupied;
        wire [WD*RESULT_BITS-1:0] unused_result_contents;

        event_barrier_queue #(
            .WIDTH(RESULT_BITS),
            .DEPTH(WD),
            .PROTECTED(PROTECT_STATE != 0),
            .ASYNC_RESET(ASYNC_RESET != 0)
        ) u_results (
            .i_clk(i_clk),
            .i_rstb(state_rstb),
            .i_flush(flush),
            .i_valid(result_create),
            .o_ready(result_space),
            .i_data(result_create ? result_input : {RESULT_BITS{1'b0}}),
            .o_valid(result_valid),
            .i_ready(operate && i_wait_result_ready),
            .o_data(result_output),
            .o_occupancy(o_wait_result_occupancy),
            .o_corrupt(result_corrupt),
            .o_occupied(unused_result_occupied),
            .o_contents(unused_result_contents)
        );

        event_barrier_queue #(
            .WIDTH(RELEASE_BITS),
            .DEPTH(RD),
            .PROTECTED(PROTECT_STATE != 0),
            .ASYNC_RESET(ASYNC_RESET != 0)
        ) u_releases (
            .i_clk(i_clk),
            .i_rstb(state_rstb),
            .i_flush(flush),
            .i_valid(release_create),
            .o_ready(release_space),
            .i_data(release_create ? release_input : {RELEASE_BITS{1'b0}}),
            .o_valid(release_valid),
            .i_ready(operate && i_barrier_release_ready),
            .o_data(release_output),
            .o_occupancy(o_barrier_release_occupancy),
            .o_corrupt(release_corrupt),
            .o_occupied(release_occupied),
            .o_contents(release_contents)
        );

        assign o_wait_result_valid = run && result_valid;
        assign {o_wait_result_slot, o_wait_result_mode, o_wait_result_matched_mask,
            o_wait_result_consumed_mask, o_wait_result_context_id, o_wait_result_tag,
            o_wait_result_status} = o_wait_result_valid ? result_output : '0;
        assign o_barrier_release_valid = run && release_valid;
        assign {o_barrier_release_id, o_barrier_release_generation, o_barrier_release_context_id,
            o_barrier_release_tag, o_barrier_release_participants, o_barrier_release_event_enable,
            o_barrier_release_event_id} = o_barrier_release_valid ? release_output : '0;

        event_barrier_error_t live_error;
        always_comb begin
            live_error = EB_ERR_NONE;
            if (config_fire &&!config_legal) live_error = EB_ERR_POLICY;
            if (i_post_valid && o_post_ready &&!post_legal) live_error = EB_ERR_POST;
            if (i_ack_valid && o_ack_ready &&!ack_legal) live_error = EB_ERR_ACK;
            if (arm_fire &&!wait_legal) live_error = EB_ERR_WAIT;
            if (cancel_miss) live_error = EB_ERR_CANCEL;
            if (barrier_config_fire &&!barrier_config_legal) live_error = EB_ERR_BARRIER_CONFIG;
            if (i_barrier_arrival_valid && o_barrier_arrival_ready &&!arrival_legal) begin
                live_error = EB_ERR_ARRIVAL;
                if (arrival_duplicate) live_error = EB_ERR_DUPLICATE;
                if (arrival_stale) live_error = EB_ERR_STALE;
            end
            if ((i_rstb !== 1'b0) && (!controls_known || i_rstb !== 1'b1))
                live_error = EB_ERR_UNKNOWN;
        end
        // Fatal state faults override the first recoverable class. They freeze
        // every architectural bank immediately and remain sticky until reset.
        logic [5:0] error_next;
        always_comb begin
            error_next = {o_error, o_fatal_error, o_error_code};
            if (state_fault) error_next = {1'b1, 1'b1, EB_ERR_STATE};
            else if (!o_fatal_error) begin
                if (flush || (o_quiescent && i_error_clear)) error_next = '0;
                else if (!o_error && live_error != EB_ERR_NONE)
                    error_next = {1'b1, 1'b0, live_error};
            end
        end

        dff #(.WIDTH(6), .ASYNC_RESET(ASYNC_RESET != 0)) u_errors (
            .i_clk(i_clk),
            .i_rstb(state_rstb),
            .i_enable(1'b1),
            .i_d(error_next),
            .o_q({o_error, o_fatal_error, o_error_code})
        );

        wire [21:0] pulse_next;
        assign pulse_next[0] = config_fire && config_legal;
        assign pulse_next[1] = config_fire &&!config_legal;
        assign pulse_next[2] = post_commit;
        assign pulse_next[3] = i_post_valid && o_post_ready &&!post_legal;
        assign pulse_next[4] = ack_commit;
        assign pulse_next[5] = i_ack_valid && o_ack_ready &&!ack_legal;
        assign pulse_next[6] = arm_fire && wait_legal;
        assign pulse_next[7] = arm_fire &&!wait_legal;
        assign pulse_next[8] = cancel_create;
        assign pulse_next[9] = cancel_miss;
        assign pulse_next[10] = barrier_config_commit;
        assign pulse_next[11] = barrier_config_fire &&!barrier_config_legal;
        assign pulse_next[12] = arrival_commit;
        assign pulse_next[13] = i_barrier_arrival_valid && o_barrier_arrival_ready
            &&!arrival_legal;
        assign pulse_next[14] = flush;
        assign pulse_next[15] = post_commit || release_post;
        assign pulse_next[16] = ack_commit;
        assign pulse_next[17] = wait_complete;
        assign pulse_next[18] = arrival_commit;
        assign pulse_next[19] = release_create;
        assign pulse_next[20] = i_barrier_arrival_valid && o_barrier_arrival_ready
            &&!arrival_legal && arrival_duplicate;
        assign pulse_next[21] = operate && ((i_post_valid &&!o_post_ready) || (i_ack_valid
            &&!o_ack_ready) || (result_selected &&!result_index && wait_consume[wait_index]
            &&!wait_complete) || (arrival_candidate && arrival_legal && final_arrival &&
            arrival_event &&!release_create));

        dff #(.WIDTH(22), .ASYNC_RESET(ASYNC_RESET != 0)) u_pulses (
            .i_clk(i_clk),
            .i_rstb(state_rstb),
            .i_enable(1'b1),
            .i_d(pulse_next),
            .o_q({o_event_mutation_stall, o_event_duplicate_arrival, o_event_barrier_release,
                o_event_barrier_arrival, o_event_wait_complete, o_event_ack, o_event_post,
                o_flushed, o_barrier_arrival_rejected, o_barrier_arrival_accepted,
                o_barrier_config_rejected, o_barrier_configured, o_wait_cancel_not_found,
                o_wait_canceled, o_wait_rejected, o_wait_armed, o_ack_rejected, o_ack_accepted,
                o_post_rejected, o_post_accepted, o_config_rejected, o_config_accepted})
        );
`ifdef MOSAIC_EVENT_BARRIER_ASSERTIONS
        wire [B*P-1:0] checker_expected;
        for (genvar b = 0; b < B; b++) begin : g_checker_masks
            assign checker_expected[b*P+:P] = expected[b];
        end
        event_barrier_assertions #(
            .E(E),
            .K(K),
            .W(W),
            .B(B),
            .P(P),
            .G(G),
            .EI(EI),
            .BI(BI),
            .RESULT_BITS(RESULT_BITS),
            .RELEASE_BITS(RELEASE_BITS),
            .QW(QW),
            .QR(QR)
        ) u_assertions (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_flush(flush),
            .i_fatal(o_fatal_error || state_fault),
            .i_post(post_commit),
            .i_ack(ack_commit),
            .i_ack_mode(i_ack_mode),
            .i_post_id(i_post_event_id),
            .i_ack_id(i_ack_event_id),
            .i_release_post(release_post),
            .i_release_event(arrival_event_id),
            .i_consumed(consume_mask),
            .i_wait_complete(wait_complete),
            .i_wait_consume(wait_consume[wait_index]),
            .i_wait_mode(wait_mode[wait_index]),
            .i_wait_mask(wait_mask[wait_index]),
            .i_matched(matched[wait_index]),
            .i_counts(o_event_count),
            .i_pending(o_event_pending),
            .i_saturated(o_event_saturated),
            .i_wait_active(o_wait_slot_active),
            .i_release(release_create),
            .i_barrier_id(i_barrier_arrival_id),
            .i_barrier_enable(barrier_enabled),
            .i_arrived(o_barrier_arrived),
            .i_expected(checker_expected),
            .i_generations(o_barrier_generation),
            .i_result_valid(o_wait_result_valid),
            .i_result_ready(i_wait_result_ready),
            .i_result(result_output),
            .i_release_valid(o_barrier_release_valid),
            .i_release_ready(i_barrier_release_ready),
            .i_release_payload(release_output),
            .i_result_occupancy(o_wait_result_occupancy),
            .i_release_occupancy(o_barrier_release_occupancy),
            .i_result_create(result_create),
            .i_cancel_create(cancel_create),
            .i_mutation_commits({release_post, |consume_mask, ack_commit, post_commit}),
            .i_event_post(o_event_post),
            .i_event_ack(o_event_ack),
            .i_event_wait(o_event_wait_complete),
            .i_event_release(o_event_barrier_release)
        );
`endif
    end
endmodule
