`timescale 1ns / 1ps
`default_nettype none
// Lossless event fan-in on the ungated cluster clock. Critical records precede
// tile arbitration; the released arbiter advances only on an accepted tile beat.
module cluster_events #(
    parameter NUM_TILES = 4,
    parameter EVENT_DEPTH = NUM_TILES + 8,
    parameter PROTECT_EVENTS = 1,
    localparam bit GEOMETRY_VALID = ((NUM_TILES >= 1 && NUM_TILES <= 64) === 1'b1) &&
        (^NUM_TILES !== 1'bx),
    localparam int N = GEOMETRY_VALID ? NUM_TILES : 1,
    parameter logic [N*8-1:0] TILE_ID_TABLE = default_tile_ids(),
    localparam int INDEX = N > 1 ? $clog2(N) : 1,
    localparam int EW = 377
) (
    input wire i_clk,
    input wire i_rstb,
    input wire i_clear_completion,
    input wire [N-1:0] i_tile_valid,
    output logic [N-1:0] o_tile_ready,
    input wire [N*256-1:0] i_tile_payload,
    input wire i_memory_valid,
    output wire o_memory_ready,
    input wire [255:0] i_memory_payload,
    input wire i_terminal_valid,
    output wire o_terminal_ready,
    input wire i_fault_valid,
    output wire o_fault_ready,
    input wire [7:0] i_fault_code,
    input wire [7:0] i_fault_source,
    input wire [15:0] i_owner_id,
    input wire [15:0] i_kernel_id,
    input wire [7:0] i_context_id,
    input wire [31:0] i_package_id,
    input wire [3:0] i_epoch,
    output wire o_event_valid,
    input wire i_event_ready,
    output wire [2:0] o_event_type,
    output wire [7:0] o_event_source_id,
    output wire [15:0] o_event_owner_id,
    output wire [15:0] o_event_kernel_id,
    output wire [7:0] o_event_context_id,
    output wire [31:0] o_event_package_id,
    output wire [3:0] o_event_epoch,
    output wire [255:0] o_event_payload,
    output wire [1:0] o_event_severity,
    output wire [31:0] o_event_sequence,
    output wire o_empty,
    output wire [N-1:0] o_completion_mask,
    output wire o_duplicate_completion,
    output wire o_error
);
    import cluster_pkg::*;

    function automatic logic [N*8-1:0] default_tile_ids();
        for (int t = 0; t < N; t++) default_tile_ids[t*8+:8] = 8'(t);
    endfunction

    function automatic bit identities_valid();
        identities_valid = ^TILE_ID_TABLE !== 1'bx;

        for (int t = 0; t < N; t++) begin
            if (TILE_ID_TABLE[t*8+:8] >= 240) identities_valid = 0;

            for (int other = 0; other < t; other++) begin
                if (TILE_ID_TABLE[t*8+:8] == TILE_ID_TABLE[other*8+:8]) identities_valid = 0;
            end
        end
    endfunction

    localparam bit PARAMETERS_VALID = GEOMETRY_VALID &&
        ((EVENT_DEPTH >= 1 && EVENT_DEPTH <= 128) === 1'b1) && (^EVENT_DEPTH !== 1'bx) &&
        (PROTECT_EVENTS === 0 || PROTECT_EVENTS === 1) && identities_valid();

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        cluster_events_parameters_must_be_valid invalid_parameters ();
    end else begin : g_events
        wire [N-1:0] completed;
        logic [N-1:0] completed_d;
        wire duplicate;
        logic duplicate_d;
        wire completion_bad;
        wire [31:0] sequence_id;
        wire sequence_max;
        wire sequence_exhausted;
        wire failed;
        wire queue_failed;
        wire queue_bad;
        wire queue_valid;
        wire queue_ready;
        wire [EW-1:0] outgoing;
        wire [N-1:0] requests;
        wire [N-1:0] grant;
        wire grant_valid;
        wire [INDEX-1:0] selected;
        wire arbiter_bad;
        logic [EW-1:0] incoming;
        logic [2:0] kind;
        logic [7:0] source;
        logic [255:0] payload;
        logic [1:0] severity;
        wire candidate = grant_valid || i_fault_valid === 1'b1 ||
            i_terminal_valid === 1'b1 || i_memory_valid === 1'b1;
        wire known_controls = ^{i_tile_valid, i_fault_valid, i_terminal_valid,
            i_memory_valid, i_clear_completion} !== 1'bx;
        wire input_bad = !known_controls || (candidate && ^incoming === 1'bx) ||
            (^sequence_id === 1'bx);
        wire live_failure = input_bad || queue_bad || completion_bad || arbiter_bad ||
            sequence_exhausted;
        wire run = i_rstb === 1'b1 && !failed && !live_failure;
        wire push = run && candidate;
        wire admitted = push && queue_ready;
        wire tile_selected = !i_fault_valid && !i_terminal_valid && !i_memory_valid &&
            grant_valid;
        wire tile_admitted = admitted && tile_selected;
        // Ingress/namespace failure does not invalidate previously accepted
        // records. A corrupt queue is a failed transport and needs global reset.
        wire deliver = i_rstb === 1'b1 && !queue_failed && !queue_bad;

        for (genvar t = 0; t < N; t++) begin : g_request
            assign requests[t] = i_tile_valid[t] === 1'b1;
        end

        round_robin_arbiter #(
            .NUM_REQUESTERS(N),
            .HAS_LOCK(0),
            .HOLD_PENDING(1)
        ) u_tile_arbiter (
            .i_clk(i_clk),
            .i_rstb(i_rstb === 1'b1),
            .i_request(requests),
            .i_eligible({N{1'b1}}),
            .i_lock({N{1'b0}}),
            .i_accept(tile_admitted),
            .i_flush(1'b0),
            .o_grant_valid(grant_valid),
            .o_grant_onehot(grant),
            .o_grant_index(selected),
            .o_grant_lock(),
            .o_grant_accepted(),
            .o_contended(),
            .o_pending(),
            .o_locked(),
            .o_lock_owner(),
            .o_protocol_error(arbiter_bad)
        );

        always @* begin
            kind = CLUSTER_EVENT_TILE;
            source = TILE_ID_TABLE[selected*8+:8];
            payload = i_tile_payload[selected*256+:256];
            severity = 0;

            if (i_fault_valid === 1'b1) begin
                kind = CLUSTER_EVENT_FAULT;
                source = i_fault_source;
                payload = {248'd0, i_fault_code};
                severity = 3;
            end else if (i_terminal_valid === 1'b1) begin
                kind = CLUSTER_EVENT_COMPLETE;
                source = 8'hff;
                payload = {{(256-N){1'b0}}, completed};
            end else if (i_memory_valid === 1'b1) begin
                kind = CLUSTER_EVENT_MEMORY;
                source = 8'hfe;
                payload = i_memory_payload;
            end

            // Capture full identity at admission, never from later allocations.
            incoming = {sequence_id, severity, payload, i_epoch, i_package_id,
                i_context_id, i_kernel_id, i_owner_id, source, kind};
            o_tile_ready = run && queue_ready && tile_selected ? grant : '0;
        end

        assign o_fault_ready = run && queue_ready;
        assign o_terminal_ready = run && queue_ready && !i_fault_valid;
        assign o_memory_ready = run && queue_ready && !i_fault_valid && !i_terminal_valid;
        assign o_event_valid = deliver && queue_valid;
        assign {o_event_sequence, o_event_severity, o_event_payload, o_event_epoch,
            o_event_package_id, o_event_context_id, o_event_kernel_id, o_event_owner_id,
            o_event_source_id, o_event_type} = o_event_valid ? outgoing : '0;
        assign o_completion_mask = completion_bad ? '0 : completed;
        assign o_duplicate_completion = duplicate;
        assign o_error = i_rstb === 1'b1 && (failed || live_failure);
        // A failed collector cannot authorize release merely because RAM is empty.
        assign o_empty = !queue_valid && !o_error;

        event_barrier_queue #(
            .WIDTH(EW),
            .DEPTH(EVENT_DEPTH),
            .PROTECTED(PROTECT_EVENTS != 0)
        ) u_queue (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_flush(1'b0),
            .i_valid(push),
            .o_ready(queue_ready),
            .i_data(incoming),
            .o_valid(queue_valid),
            .i_ready(deliver && i_event_ready === 1'b1),
            .o_data(outgoing),
            .o_occupancy(),
            .o_corrupt(queue_bad),
            .o_occupied(),
            .o_contents()
        );

        tile_shell_state #(
            .WIDTH(N + 1),
            .PROTECTION(PROTECT_EVENTS)
        ) u_completion (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(run && (i_clear_completion || tile_admitted)),
            .i_data({duplicate_d, completed_d}),
            .o_data({duplicate, completed}),
            .o_bad(completion_bad),
            .o_corrected()
        );

        always @* begin
            completed_d = i_clear_completion ? '0 : completed;
            duplicate_d = duplicate;

            if (tile_admitted && payload[2:0] == tile_shell_pkg::EVENT_COMPLETE) begin
                if (completed[selected] && !i_clear_completion) duplicate_d = 1;

                completed_d[selected] = 1;
            end
        end

        counter #(
            .WIDTH(32),
            .SATURATE(1)
        ) u_sequence (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(admitted),
            .i_clear(1'b0),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value(32'b0),
            .o_count(sequence_id),
            .o_overflow(),
            .o_underflow(),
            .o_terminal(sequence_max)
        );

        dff u_exhausted (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(admitted && sequence_max),
            .i_d(1'b1),
            .o_q(sequence_exhausted)
        );

        dff u_failed (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(live_failure),
            .i_d(1'b1),
            .o_q(failed)
        );

        dff u_queue_failed (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(queue_bad),
            .i_d(1'b1),
            .o_q(queue_failed)
        );
    end
endmodule
`default_nettype wire
