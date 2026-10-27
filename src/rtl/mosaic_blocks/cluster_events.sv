`timescale 1ns / 1ps
`default_nettype none
// Lossless fan-in. Native payloads are retained in full; headers capture the
// allocation identity at admission rather than following later runtime inputs.
module cluster_events #(
    parameter NUM_TILES = 4,
    parameter TILE_ID_TABLE = 32'h03020100,
    parameter EVENT_DEPTH = NUM_TILES + 8,
    localparam int N = NUM_TILES,
    localparam int EW = 3 + 8 + 16 + 16 + 8 + 32 + 4 + 256 + 2 + 32
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
    output wire o_duplicate_completion
);
    import cluster_pkg::*;
    logic [N-1:0] completed;
    logic duplicate;
    logic [31:0] sequence_id;
    integer cursor;
    integer selected;
    logic found;
    logic push;
    wire ready;
    logic [EW-1:0] incoming;
    wire [EW-1:0] outgoing;
    logic [2:0] kind;
    logic [7:0] source;
    logic [255:0] payload;
    logic [1:0] severity;

    // Strict one-source selection plus a rotating tile cursor bounds arbitration.
    always @* begin
        selected = 0;
        found = 1'b0;

        for (int k = 0; k < N; k++) begin
            if (!found && i_tile_valid[(cursor + k) % N] === 1'b1) begin
                selected = (cursor + k) % N;
                found = 1'b1;
            end
        end

        kind = CLUSTER_EVENT_TILE;
        source = TILE_ID_TABLE[selected*8+:8];
        payload = i_tile_payload[selected*256+:256];
        severity = 2'd0;

        if (i_fault_valid) begin
            kind = CLUSTER_EVENT_FAULT;
            source = i_fault_source;
            payload = {248'd0, i_fault_code};
            severity = 2'd3;
        end else if (i_terminal_valid) begin
            kind = CLUSTER_EVENT_COMPLETE;
            source = 8'hff;
            payload = {{(256-N){1'b0}}, completed};
        end else if (i_memory_valid) begin
            kind = CLUSTER_EVENT_MEMORY;
            source = 8'hfe;
            payload = i_memory_payload;
        end

        push = i_rstb === 1'b1 && (i_fault_valid || i_terminal_valid ||
            i_memory_valid || found);
        incoming = {sequence_id, severity, payload, i_epoch, i_package_id,
            i_context_id, i_kernel_id, i_owner_id, source, kind};
        o_tile_ready = '0;

        if (!i_fault_valid &&!i_terminal_valid &&!i_memory_valid && found && ready)
            o_tile_ready[selected] = 1'b1;
    end

    assign o_fault_ready = ready && i_rstb === 1'b1;
    assign o_terminal_ready = ready &&!i_fault_valid && i_rstb === 1'b1;
    assign o_memory_ready = ready &&!i_fault_valid &&!i_terminal_valid && i_rstb === 1'b1;

    fifo #(.DATA_WIDTH(EW), .DEPTH(EVENT_DEPTH)) u_queue (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_valid(push),
        .o_ready(ready),
        .i_data(incoming),
        .o_valid(o_event_valid),
        .i_ready(i_event_ready === 1'b1),
        .o_data(outgoing),
        .o_full(),
        .o_empty(o_empty),
        .o_almost_full(),
        .o_almost_empty(),
        .o_occupancy()
    );

    assign {o_event_sequence, o_event_severity, o_event_payload, o_event_epoch,
        o_event_package_id, o_event_context_id, o_event_kernel_id, o_event_owner_id,
        o_event_source_id, o_event_type} = o_event_valid ? outgoing : '0;
    assign o_completion_mask = completed;
    assign o_duplicate_completion = duplicate;

    always_ff @(posedge i_clk) begin
        if (!i_rstb) begin
            completed <= '0;
            duplicate <= 1'b0;
            sequence_id <= '0;
            cursor <= 0;
        end else begin
            if (i_clear_completion) completed <= '0;

            if (push && ready) sequence_id <= sequence_id + 1'b1;

            for (int t = 0; t < N; t++) begin
                if (o_tile_ready[t] && i_tile_valid[t]) begin
                    cursor <= (t + 1) % N;

                    if (i_tile_payload[t*256+:3] == tile_shell_pkg::EVENT_COMPLETE) begin
                        if (completed[t] &&!i_clear_completion) duplicate <= 1'b1;

                        completed[t] <= 1'b1;
                    end
                end
            end
        end
    end
endmodule
`default_nettype wire
