`timescale 1ns / 1ps

// Flushable ring built from released one-entry FIFOs. Payload RAM is unreset;
// protected pointers/count and an independent occupied-lane census guard control.
module noc_router_buffer #(
    parameter int WIDTH = 32,
    parameter int DEPTH = 2,
    parameter int PROTECTION = 0,
    parameter bit ASYNC_RESET = 0,
    parameter logic [WIDTH-1:0] OWNERSHIP_MASK = '1,
    localparam int PTR = DEPTH > 1 ? $clog2(DEPTH) : 1,
    localparam int OCC = $clog2(DEPTH + 1),
    localparam int STRIPES = (WIDTH + 255) / 256,
    localparam int LAST = WIDTH - (STRIPES - 1) * 256,
    localparam int CODE = PROTECTION == 2 ? (STRIPES - 1) * 266 + LAST +
        hamming_bits(LAST) + 1 + WIDTH + 1 : WIDTH + PROTECTION
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
    output wire o_corrected,
    output wire o_uncorrectable,
    output wire o_ownership_error
);
    function automatic int hamming_bits(input int width);
        int count;
        count = 1;
        while ((64'd1 << count) < 64'(width) + 64'(count) + 1) count++;
        return count;
    endfunction

    wire [PTR-1:0] read_pointer;
    wire [PTR-1:0] write_pointer;
    wire metadata_bad;
    wire [DEPTH-1:0] occupied;
    wire [DEPTH-1:0] write_select;
    wire [DEPTH-1:0] read_select;
    wire unused_write_valid;
    wire unused_read_valid;
    wire [CODE-1:0] encoded;
    wire [CODE-1:0] received;
    wire [DEPTH-1:0][CODE-1:0] contents;
    wire selected_valid;
    wire code_ownership_bad;
    wire push = i_valid && o_ready && !i_flush;
    wire pop = o_valid && i_ready && !i_flush;
    wire [PTR-1:0] read_next = read_pointer == PTR'(DEPTH - 1) ? '0 : read_pointer + 1'b1;
    wire [PTR-1:0] write_next = write_pointer == PTR'(DEPTH - 1) ? '0 : write_pointer + 1'b1;
    wire [OCC-1:0] count_next = push ? o_occupancy + 1'b1 : o_occupancy - 1'b1;
    assign o_valid = o_occupancy != 0;
    // Stored-head replacement sustains one flit per cycle even at depth one.
    // Mesh integration inserts registered reverse-flow boundaries between routers.
    assign o_ready = o_occupancy < OCC'(DEPTH) || pop;
    assign o_ownership_error = metadata_bad ||
        (32'(read_pointer) >= DEPTH) || (32'(write_pointer) >= DEPTH) ||
        ($countones(occupied) != 32'(o_occupancy)) ||
        (o_valid && (!selected_valid || !occupied[read_pointer] || code_ownership_bad));

    event_barrier_state #(.WIDTH(2 * PTR + OCC), .PROTECTED(PROTECTION != 0),
        .ASYNC_RESET(ASYNC_RESET)) u_metadata (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(i_flush || push || pop),
        .i_data(i_flush ? '0 : {push ? write_next : write_pointer,
            pop ? read_next : read_pointer, push != pop ? count_next : o_occupancy}),
        .o_data({write_pointer, read_pointer, o_occupancy}),
        .o_corrupt(metadata_bad)
    );

    decoder #(.NUM_OUTPUTS(DEPTH), .SELECT_WIDTH(PTR)) u_write_decode (
        .i_enable(push),
        .i_select(write_pointer),
        .o_decoded(write_select),
        .o_select_valid(unused_write_valid)
    );

    decoder #(.NUM_OUTPUTS(DEPTH), .SELECT_WIDTH(PTR)) u_read_decode (
        .i_enable(pop),
        .i_select(read_pointer),
        .o_decoded(read_select),
        .o_select_valid(unused_read_valid)
    );

    mux #(.NUM_INPUTS(DEPTH), .DATA_WIDTH(CODE)) u_read_mux (
        .i_data(contents),
        .i_select(read_pointer),
        .o_data(received),
        .o_select_valid(selected_valid)
    );

    noc_router_codec #(.WIDTH(WIDTH), .PROTECTION(PROTECTION),
        .OWNERSHIP_MASK(OWNERSHIP_MASK)) u_codec (
        .i_encode(push ? i_data : '0),
        .o_encoded(encoded),
        .i_decode(o_valid ? received : '0),
        .o_decoded(o_data),
        .o_corrected(o_corrected),
        .o_uncorrectable(o_uncorrectable),
        .o_ownership_error(code_ownership_bad)
    );

    for (genvar lane = 0; lane < DEPTH; lane++) begin : g_lane
        wire unused_ready;
        wire unused_full;
        wire unused_empty;
        wire unused_almost_full;
        wire unused_almost_empty;
        wire unused_occupancy;

        fifo #(.DATA_WIDTH(CODE), .DEPTH(1), .ASYNC_RESET(ASYNC_RESET)) u_fifo (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_valid(write_select[lane]),
            .o_ready(unused_ready),
            .i_data(encoded),
            .o_valid(occupied[lane]),
            .i_ready(i_flush || read_select[lane]),
            .o_data(contents[lane]),
            .o_full(unused_full),
            .o_empty(unused_empty),
            .o_almost_full(unused_almost_full),
            .o_almost_empty(unused_almost_empty),
            .o_occupancy(unused_occupancy)
        );
    end
endmodule
