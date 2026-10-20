`timescale 1ns / 1ps

// Single-clock ready/valid FIFO with registered occupancy and no fall-through.
module fifo #(
    parameter DATA_WIDTH = 32,
    parameter DEPTH = 4,
    parameter ASYNC_RESET = 0,
    parameter ALMOST_FULL_LEVEL = DEPTH > 1 ? DEPTH - 1 : 1,
    parameter ALMOST_EMPTY_LEVEL = DEPTH > 1 ? 1 : 0,
    // These are implementation results, not independently configurable knobs.
    localparam bit PARAMETERS_VALID =
        ((DATA_WIDTH >= 1) === 1'b1) && ((DEPTH >= 1) === 1'b1) &&
        ((^DATA_WIDTH) !== 1'bx) && ((^DEPTH) !== 1'bx) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((ALMOST_FULL_LEVEL >= 1 && ALMOST_FULL_LEVEL <= DEPTH) === 1'b1) &&
        ((ALMOST_EMPTY_LEVEL >= 0 && ALMOST_EMPTY_LEVEL < DEPTH) === 1'b1),
    localparam int unsigned DATA_BITS = PARAMETERS_VALID ? DATA_WIDTH : 1,
    localparam int unsigned STORAGE_DEPTH = PARAMETERS_VALID ? DEPTH : 1,
    localparam int unsigned PTR_WIDTH = STORAGE_DEPTH > 1 ? $clog2(STORAGE_DEPTH) : 1,
    localparam int unsigned OCC_WIDTH = $clog2(64'(STORAGE_DEPTH) + 1)
) (
    input  logic                 i_clk,
    input  logic                 i_rstb,
    input  logic                 i_valid,
    output logic                 o_ready,
    input  logic [DATA_BITS-1:0] i_data,
    output logic                 o_valid,
    input  logic                 i_ready,
    output logic [DATA_BITS-1:0] o_data,
    output logic                 o_full,
    output logic                 o_empty,
    output logic                 o_almost_full,
    output logic                 o_almost_empty,
    output logic [OCC_WIDTH-1:0] o_occupancy
);
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        fifo_parameters_must_be_valid invalid_parameters ();
    end else begin : g_fifo
        logic [DATA_BITS-1:0] memory [STORAGE_DEPTH];
        logic [PTR_WIDTH-1:0] read_pointer, write_pointer;
        logic [PTR_WIDTH-1:0] read_next, write_next;
        logic [OCC_WIDTH-1:0] occupancy_next;
        logic push, pop, storage_write_enable;

        assign o_empty = o_occupancy == '0;
        assign o_full = o_occupancy == OCC_WIDTH'(DEPTH);
        assign o_almost_empty = o_occupancy <= OCC_WIDTH'(ALMOST_EMPTY_LEVEL);
        assign o_almost_full = o_occupancy >= OCC_WIDTH'(ALMOST_FULL_LEVEL);
        assign o_valid = !o_empty;
        // At full capacity the outgoing item frees its slot on the same edge.
        assign o_ready = !o_full || (o_valid && i_ready);
        assign push = i_valid && o_ready;
        assign pop = o_valid && i_ready;
        assign storage_write_enable = i_rstb && push;

        // Explicit terminal comparison also handles depth one and odd depths.
        assign read_next = read_pointer == PTR_WIDTH'(DEPTH - 1) ? '0 : read_pointer + 1'b1;
        assign write_next = write_pointer == PTR_WIDTH'(DEPTH - 1) ? '0 : write_pointer + 1'b1;
        assign occupancy_next = pop ? o_occupancy - 1'b1 : o_occupancy + 1'b1;

        dff #(.WIDTH(PTR_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_read_pointer (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(pop),
            .i_d(read_next),
            .o_q(read_pointer)
        );

        dff #(.WIDTH(PTR_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_write_pointer (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(push),
            .i_d(write_next),
            .o_q(write_pointer)
        );

        dff #(.WIDTH(OCC_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_occupancy (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(push ^ pop),
            .i_d(occupancy_next),
            .o_q(o_occupancy)
        );

        // Do not reset the data array: only accepted writes may change it.
        // The consumer observes the old head before a same-address NBA write,
        // including consume-and-replace in a one-entry FIFO.
        always_ff @(posedge i_clk) begin
            if (storage_write_enable) memory[write_pointer] <= i_data;
        end

        operand_isolation #(.WIDTH(DATA_BITS)) u_empty_output (
            .i_data(memory[read_pointer]),
            .i_isolate(o_empty),
            .o_data(o_data)
        );
    end
endmodule
