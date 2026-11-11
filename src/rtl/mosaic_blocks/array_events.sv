`timescale 1ns / 1ps
`default_nettype none
// Critical events use a dedicated, ungated control network, independent of data VCs.
module array_events #(
    parameter NUM_CLUSTERS = 2,
    parameter EVENT_DEPTH = 8,
    localparam bit GEOMETRY_VALID = ((NUM_CLUSTERS >= 1 && NUM_CLUSTERS <= 4) === 1'b1),
    localparam int N = GEOMETRY_VALID ? NUM_CLUSTERS : 1,
    localparam bit DEPTH_VALID = ((EVENT_DEPTH >= 1 && EVENT_DEPTH <= 128) === 1'b1),
    localparam int DEPTH = DEPTH_VALID ? EVENT_DEPTH : 1,
    localparam int INDEX = $clog2(2 * N),
    localparam int WIDTH = 389 + N,
    parameter logic [N*8-1:0] CLUSTER_IDS = 16'h0100
) (
    input wire i_clk,
    input wire i_rstb,
    input wire [N-1:0] i_valid,
    output wire [N-1:0] o_ready,
    input wire [N*377-1:0] i_records,
    input wire [N-1:0] i_terminal_valid,
    output wire [N-1:0] o_terminal_ready,
    input wire [N-1:0] i_allocated,
    input wire [N*N-1:0] i_group_masks,
    input wire [N*16-1:0] i_owner_ids,
    input wire [N*16-1:0] i_kernel_ids,
    input wire [N*32-1:0] i_package_ids,
    input wire [N*32-1:0] i_local_package_ids,
    input wire [N*8-1:0] i_execution_epochs,
    input wire [N*8-1:0] i_context_ids,
    output wire [N-1:0] o_completion,
    output wire o_event_valid,
    input wire i_event_ready,
    output wire [2:0] o_event_type,
    output wire [15:0] o_event_source_id,
    output wire [N-1:0] o_event_cluster_mask,
    output wire [15:0] o_event_owner_id,
    output wire [15:0] o_event_kernel_id,
    output wire [7:0] o_event_context_id,
    output wire [31:0] o_event_package_id,
    output wire [7:0] o_event_epoch,
    output wire [255:0] o_event_payload,
    output wire [1:0] o_event_severity,
    output wire [31:0] o_event_sequence,
    output wire o_empty,
    output wire o_error
);
    function automatic bit ids_valid();
        ids_valid = ((^CLUSTER_IDS == 1'b0) || (^CLUSTER_IDS == 1'b1)) === 1'b1;

        for (int c = 0; c < N; c++) begin
            if (CLUSTER_IDS[c*8+:8] >= 240) ids_valid = 1'b0;

            for (int k = 0; k < c; k++)
                if (CLUSTER_IDS[c*8+:8] == CLUSTER_IDS[k*8+:8]) ids_valid = 1'b0;
        end
    endfunction

    if (!GEOMETRY_VALID || !DEPTH_VALID || !ids_valid()) begin : g_invalid
        array_events_parameters_must_be_valid invalid_parameters ();
    end

    wire [N*32-1:0] expected_sequences;
    wire [2*N-1:0] requests = {i_terminal_valid, i_valid};
    wire [2*N-1:0] grant;
    wire grant_valid;
    wire [INDEX-1:0] selected;
    wire arbiter_bad;
    wire queue_ready;
    wire queue_valid;
    wire queue_bad;
    wire [WIDTH-1:0] outgoing;
    wire [31:0] sequence_id;
    logic exhausted;
    logic failed;
    logic [WIDTH-1:0] incoming;
    logic identity_bad;
    logic [376:0] record;
    integer cluster_slot;
    wire push = grant_valid && !o_error && i_rstb === 1'b1;
    wire admitted = push && queue_ready;
    wire terminal = selected >= N;
    assign o_error = failed || exhausted || arbiter_bad || queue_bad || identity_bad;
    assign o_ready = admitted && !terminal ? grant[N-1:0] : '0;
    assign o_terminal_ready = admitted && terminal ? grant[N+:N] : '0;
    assign o_completion = admitted && !terminal && record[2:0] == 2 ? grant[N-1:0] : '0;
    assign o_event_valid = i_rstb === 1'b1 && queue_valid && !queue_bad;
    assign {o_event_sequence, o_event_severity, o_event_payload, o_event_epoch,
        o_event_package_id, o_event_context_id, o_event_kernel_id, o_event_owner_id,
        o_event_cluster_mask, o_event_source_id, o_event_type} =
        o_event_valid ? outgoing : '0;
    assign o_empty = !queue_valid && requests == 0 && !o_error;

    round_robin_arbiter #(.NUM_REQUESTERS(2 * N), .HAS_LOCK(0), .HOLD_PENDING(1)) u_arbiter (
        .i_clk(i_clk),
        .i_rstb(i_rstb === 1'b1),
        .i_request(requests),
        .i_eligible({2*N{1'b1}}),
        .i_lock({2*N{1'b0}}),
        .i_accept(admitted),
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

    counter #(.WIDTH(32)) u_sequence (
        .i_clk(i_clk),
        .i_rstb(i_rstb === 1'b1),
        .i_enable(admitted),
        .i_clear(1'b0),
        .i_load(1'b0),
        .i_direction(1'b0),
        .i_load_value(32'd0),
        .o_count(sequence_id),
        .o_overflow(),
        .o_underflow(),
        .o_terminal()
    );

    event_barrier_queue #(.WIDTH(WIDTH), .DEPTH(DEPTH), .PROTECTED(1)) u_queue (
        .i_clk(i_clk),
        .i_rstb(i_rstb === 1'b1),
        .i_flush(1'b0),
        .i_valid(push),
        .o_ready(queue_ready),
        .i_data(incoming),
        .o_valid(queue_valid),
        .i_ready(i_event_ready === 1'b1 && o_event_valid),
        .o_data(outgoing),
        .o_occupancy(),
        .o_corrupt(queue_bad),
        .o_occupied(),
        .o_contents()
    );

    for (genvar c = 0; c < N; c++) begin : g_sequence
        counter #(.WIDTH(32)) u_expected (
            .i_clk(i_clk),
            .i_rstb(i_rstb === 1'b1),
            .i_enable(o_ready[c]),
            .i_clear(1'b0),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value(32'd0),
            .o_count(expected_sequences[c*32+:32]),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );
    end

    always @* begin
        cluster_slot = int'(selected) % N;
        record = i_records[cluster_slot*377+:377];
        identity_bad = grant_valid && !terminal && (^{record} === 1'bx ||
            record[345+:32] != expected_sequences[cluster_slot*32+:32] ||
            (record[2:0] == 2 && (!i_allocated[cluster_slot] ||
            record[11+:16] != i_owner_ids[cluster_slot*16+:16] ||
            record[27+:16] != i_kernel_ids[cluster_slot*16+:16] ||
            record[51+:32] != i_local_package_ids[cluster_slot*32+:32] ||
            record[83+:4] != i_execution_epochs[cluster_slot*8+:4] ||
            record[43+:8] != i_context_ids[cluster_slot*8+:8])));
        incoming = {sequence_id, record[343+:2], record[87+:256],
            i_execution_epochs[cluster_slot*8+:8], i_package_ids[cluster_slot*32+:32],
            record[43+:8], record[27+:16], record[11+:16], N'(1 << cluster_slot),
            CLUSTER_IDS[cluster_slot*8+:8], record[3+:8],
            record[2:0] == 2 ? 3'd6 : record[2:0]};

        if (terminal) incoming = {sequence_id, 2'd0, 256'd0,
            i_execution_epochs[cluster_slot*8+:8], i_package_ids[cluster_slot*32+:32],
            8'd0, i_kernel_ids[cluster_slot*16+:16], i_owner_ids[cluster_slot*16+:16],
            i_group_masks[cluster_slot*N+:N], 16'hffff, 3'd2};
    end

    always @(posedge i_clk) begin
        if (i_rstb !== 1'b1) begin
            failed <= 1'b0;
            exhausted <= 1'b0;
        end else begin
            if (o_error) failed <= 1'b1;

            if (admitted && &sequence_id) exhausted <= 1'b1;
        end
    end
endmodule
`default_nettype wire
