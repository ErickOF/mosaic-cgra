`timescale 1ns / 1ps

// A ring of common one-entry FIFOs provides synchronous, parallel flush without
// gating reset or resetting payload RAM. All lanes pop together on flush; normal
// traffic reads/writes only the selected lane. Metadata and occupied payloads are
// parity checked when enabled. The parent validates the geometry.
module event_barrier_queue #(
    parameter int WIDTH = 32,
    parameter int DEPTH = 4,
    parameter bit PROTECTED = 0,
    parameter bit ASYNC_RESET = 0,
    localparam int PTR = DEPTH > 1 ? $clog2(DEPTH) : 1,
    localparam int OCC = $clog2(DEPTH + 1),
    localparam int STORED = WIDTH + int'(PROTECTED)
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_flush,
    input logic i_valid,
    output wire o_ready,
    input logic [WIDTH-1:0] i_data,
    output wire o_valid,
    input logic i_ready,
    output wire [WIDTH-1:0] o_data,
    output wire [OCC-1:0] o_occupancy,
    output wire o_corrupt,
    output wire [DEPTH-1:0] o_occupied,
    output wire [DEPTH*WIDTH-1:0] o_contents
);
    wire [PTR-1:0] read_pointer;
    wire [PTR-1:0] write_pointer;
    wire push = i_valid && o_ready;
    wire pop = o_valid && i_ready;
    wire [PTR-1:0] read_next = read_pointer == PTR'(DEPTH - 1) ? '0 : read_pointer + 1'b1;
    wire [PTR-1:0] write_next = write_pointer == PTR'(DEPTH - 1) ? '0 : write_pointer + 1'b1;
    wire [OCC-1:0] occupancy_next = push ? o_occupancy + 1'b1 : o_occupancy - 1'b1;
    wire metadata_corrupt;
    wire [DEPTH-1:0] payload_corrupt;
    wire [STORED-1:0] stored_input;
    wire [STORED-1:0] stored_output[DEPTH];
    assign o_valid = o_occupancy != '0;
    assign o_ready = o_occupancy < OCC'(DEPTH) || pop;
    assign o_data = o_valid ? stored_output[read_pointer][WIDTH-1:0] : '0;
    assign o_corrupt = metadata_corrupt || (|payload_corrupt);

    event_barrier_state #(.WIDTH(2 * PTR + OCC), .PROTECTED(PROTECTED),
        .ASYNC_RESET(ASYNC_RESET)) u_metadata (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(i_flush || push || pop),
        .i_data(i_flush ? '0 : {push ? write_next : write_pointer,
            pop ? read_next : read_pointer, push != pop ? occupancy_next : o_occupancy}),
        .o_data({write_pointer, read_pointer, o_occupancy}),
        .o_corrupt(metadata_corrupt)
    );

    if (PROTECTED) begin : g_input_parity
        assign stored_input = { ^ i_data, i_data};
    end else begin : g_plain_input
        assign stored_input = i_data;
    end

    for (genvar lane = 0; lane < DEPTH; lane++) begin : g_lane
        wire unused_ready;
        wire unused_full;
        wire unused_empty;
        wire unused_almost_full;
        wire unused_almost_empty;
        wire unused_occupancy;

        fifo #(.DATA_WIDTH(STORED), .DEPTH(1), .ASYNC_RESET(ASYNC_RESET)) u_fifo (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_valid(push && write_pointer == PTR'(lane) &&!i_flush),
            .o_ready(unused_ready),
            .i_data(stored_input),
            .o_valid(o_occupied[lane]),
            .i_ready(i_flush || (pop && read_pointer == PTR'(lane))),
            .o_data(stored_output[lane]),
            .o_full(unused_full),
            .o_empty(unused_empty),
            .o_almost_full(unused_almost_full),
            .o_almost_empty(unused_almost_empty),
            .o_occupancy(unused_occupancy)
        );

        assign o_contents[lane*WIDTH+:WIDTH] = stored_output[lane][WIDTH-1:0];

        if (PROTECTED) begin : g_check
            assign payload_corrupt[lane] = o_occupied[lane] &&
                ( ^ stored_output[lane] !== 1'b0);
        end else begin : g_no_check
            assign payload_corrupt[lane] = 1'b0;
        end
    end
endmodule
