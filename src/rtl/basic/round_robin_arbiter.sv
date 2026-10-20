`timescale 1ns / 1ps

// Zero-cycle arbitration with registered ownership under backpressure. Requester
// meanings, payload buffering, bounded lock use and cancellation are external.
module round_robin_arbiter #(
    parameter NUM_REQUESTERS = 4,
    parameter INITIAL_PRIORITY = 0,
    parameter HAS_LOCK = 1,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((NUM_REQUESTERS >= 1) === 1'b1) && (^NUM_REQUESTERS !== 1'bx) &&
        ((INITIAL_PRIORITY >= 0 && INITIAL_PRIORITY < NUM_REQUESTERS) === 1'b1) &&
        (^INITIAL_PRIORITY !== 1'bx) &&
        ((HAS_LOCK === 0) || (HAS_LOCK === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)),
    localparam int unsigned REQUESTERS = PARAMETERS_VALID ? NUM_REQUESTERS : 1,
    localparam int unsigned INDEX_WIDTH = REQUESTERS > 1 ? $clog2(REQUESTERS) : 1
) (
    input  logic                       i_clk,
    input  logic                       i_rstb,
    input  logic [REQUESTERS-1:0]      i_request,
    input  logic [REQUESTERS-1:0]      i_eligible,
    input  logic [REQUESTERS-1:0]      i_lock,
    input  logic                       i_accept,
    input  logic                       i_flush,
    output logic                       o_grant_valid,
    output logic [REQUESTERS-1:0]      o_grant_onehot,
    output logic [INDEX_WIDTH-1:0]     o_grant_index,
    output logic                       o_grant_lock,
    output logic                       o_grant_accepted,
    output logic                       o_contended,
    output logic                       o_pending,
    output logic                       o_locked,
    output logic [INDEX_WIDTH-1:0]     o_lock_owner,
    output logic                       o_protocol_error
);
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        round_robin_arbiter_parameters_must_be_valid invalid_parameters ();
    end else begin : g_arbiter
        logic [INDEX_WIDTH-1:0] pointer, pending_index;
        logic pending_valid, protocol_error;
        wire locked, pending_lock;
        wire [INDEX_WIDTH-1:0] lock_owner;
        logic [REQUESTERS-1:0] rotated_request;
        wire [REQUESTERS-1:0] active_request = i_request & i_eligible;
        wire [INDEX_WIDTH-1:0] encoded_index;
        wire encoded_valid, raw_contended;
        wire unused_multiple, unused_raw_valid;
        wire [INDEX_WIDTH-1:0] unused_raw_index;
        wire [REQUESTERS-1:0] unused_onehot, unused_raw_onehot;
        logic selected_valid, selected_lock, live_fault;
        logic [INDEX_WIDTH-1:0] selected_index;
        logic pointer_enable, pending_enable, index_enable, error_enable;
        logic pending_next, error_next;
        logic [INDEX_WIDTH-1:0] pointer_next;
        wire clear_state = i_flush;
        wire capture = o_grant_valid && !i_accept && !pending_valid;
        wire accepted = o_grant_accepted;

        // Suppress the rotating cone once ownership or an error fixes selection.
        always_comb begin
            int unsigned requester;
            requester = 0;
            rotated_request = '0;
            if (i_rstb && !i_flush && !protocol_error && !pending_valid && !locked) begin
                for (int unsigned offset = 0; offset < REQUESTERS; offset++) begin
                    requester = 32'(pointer) + offset;
                    if (requester >= REQUESTERS) requester -= REQUESTERS;
                    rotated_request[offset] = active_request[requester];
                end
            end
        end

        priority_encoder #(.WIDTH(REQUESTERS)) u_candidate (
            .i_request(rotated_request),
            .o_valid(encoded_valid),
            .o_index(encoded_index),
            .o_onehot(unused_onehot),
            .o_multiple(unused_multiple)
        );

        // Raw contention remains observable even during a pending or locked beat.
        // Unused winner logic in this instance is removed during synthesis.
        priority_encoder #(.WIDTH(REQUESTERS)) u_contention (
            .i_request(active_request),
            .o_valid(unused_raw_valid),
            .o_index(unused_raw_index),
            .o_onehot(unused_raw_onehot),
            .o_multiple(raw_contended)
        );

        always_comb begin
            int unsigned requester;
            requester = 0;
            selected_valid = 1'b0;
            selected_index = '0;
            selected_lock = 1'b0;
            live_fault = 1'b0;
            if (pending_valid) begin
                selected_index = pending_index;
                selected_lock = pending_lock;
                selected_valid = i_request[pending_index] && i_eligible[pending_index];
                if (HAS_LOCK == 1) begin
                    selected_valid = selected_valid && (i_lock[pending_index] == pending_lock);
                    if ((i_lock[pending_index] != pending_lock) === 1'b1) live_fault = 1'b1;
                end
                if (i_request[pending_index] === 1'b0 || i_eligible[pending_index] === 1'b0)
                    live_fault = 1'b1;
            end else if (locked) begin
                selected_index = lock_owner;
                selected_valid = active_request[lock_owner];
                selected_lock = i_lock[lock_owner];
            end else begin
                requester = 32'(pointer) + 32'(encoded_index);
                if (requester >= REQUESTERS) requester -= REQUESTERS;
                selected_index = INDEX_WIDTH'(requester);
                // A possible earlier X/Z must not be skipped for a known loser.
                selected_valid = ((^encoded_index === 1'bx) && encoded_valid !== 1'b0) ? 1'bx : encoded_valid;
                if (HAS_LOCK == 1) selected_lock = i_lock[selected_index];
            end
            if (HAS_LOCK == 1) begin
                if (locked && i_eligible[lock_owner] === 1'b0) live_fault = 1'b1;
                // An owner gap may not be used to abandon an atomic sequence.
                if (locked && i_request[lock_owner] === 1'b0 && i_lock[lock_owner] === 1'b0)
                    live_fault = 1'b1;
            end else begin
                selected_lock = 1'b0;
                if ((|i_lock) === 1'b1) live_fault = 1'b1;
            end
        end

        always_comb begin
            o_grant_valid = 1'b0;
            o_grant_onehot = '0;
            o_grant_index = '0;
            o_grant_lock = 1'b0;
            o_contended = 1'b0;
            o_pending = 1'b0;
            o_locked = 1'b0;
            o_lock_owner = '0;
            if (i_rstb && !i_flush) begin
                o_contended = raw_contended;
                o_pending = pending_valid;
                o_locked = locked;
                o_lock_owner = locked ? lock_owner : '0;
                if (!protocol_error && !live_fault) begin
                    case (selected_valid)
                        1'b0: begin end
                        1'b1: begin
                            o_grant_valid = 1'b1;
                            o_grant_index = selected_index;
                            o_grant_onehot = REQUESTERS'(1'b1) << selected_index;
                            o_grant_lock = selected_lock;
                        end
                        default: begin
                            o_grant_valid = 1'bx;
                            o_grant_index = 'x;
                            o_grant_onehot = 'x;
                            o_grant_lock = HAS_LOCK == 1 ? 1'bx : 1'b0;
                        end
                    endcase
                end
            end
        end
        assign o_grant_accepted = o_grant_valid && i_accept && !i_flush && i_rstb;
        assign o_protocol_error = protocol_error;

        always_comb begin
            pointer_enable = clear_state || (accepted && !locked);
            pointer_next = selected_index == INDEX_WIDTH'(REQUESTERS-1) ? '0 : selected_index + 1'b1;
            if (clear_state) pointer_next = INDEX_WIDTH'(INITIAL_PRIORITY);
            pending_enable = clear_state || (!protocol_error && !live_fault && (capture || accepted));
            pending_next = clear_state ? 1'b0 : (capture ? 1'b1 : 1'b0);
            index_enable = clear_state || (!protocol_error && !live_fault && capture);
            error_enable = clear_state || (!protocol_error &&
                (live_fault || (i_accept === 1'b1 && o_grant_valid === 1'b0)));
            error_next = !clear_state;
        end

        dff #(.WIDTH(INDEX_WIDTH), .RESET_VALUE(INDEX_WIDTH'(INITIAL_PRIORITY)), .ASYNC_RESET(ASYNC_RESET != 0)) u_pointer (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(pointer_enable),
            .i_d(pointer_next),
            .o_q(pointer)
        );

        dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_pending (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(pending_enable),
            .i_d(pending_next),
            .o_q(pending_valid)
        );

        dff #(.WIDTH(INDEX_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_pending_index (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(index_enable),
            .i_d(clear_state ? {INDEX_WIDTH{1'b0}} : selected_index),
            .o_q(pending_index)
        );

        dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_error (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(error_enable),
            .i_d(error_next),
            .o_q(protocol_error)
        );

        if (HAS_LOCK == 1) begin : g_lock
            wire lock_enable = clear_state || accepted;
            wire owner_enable = clear_state || (accepted && (!locked || !selected_lock));

            dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_locked (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(lock_enable),
                .i_d(clear_state ? 1'b0 : selected_lock),
                .o_q(locked)
            );

            dff #(.WIDTH(INDEX_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_owner (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(owner_enable),
                .i_d(clear_state || !selected_lock ? {INDEX_WIDTH{1'b0}} : selected_index),
                .o_q(lock_owner)
            );

            dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET != 0)) u_pending_lock (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(index_enable),
                .i_d(clear_state ? 1'b0 : selected_lock),
                .o_q(pending_lock)
            );
        end else begin : g_no_lock
            assign locked = 1'b0;
            assign lock_owner = '0;
            assign pending_lock = 1'b0;
        end
    end
endmodule
