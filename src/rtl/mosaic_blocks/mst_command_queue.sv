`timescale 1ns / 1ps
// Reuse the common ordered command directory and FIFO with an outer striped
// command code. Cancellation keeps a tombstone in acceptance order.
module mst_command_queue #(
    parameter int WIDTH = 512,
    parameter int KEY_WIDTH = 48,
    parameter int DEPTH = 4,
    parameter int PROTECTION = 0,
    parameter int ASYNC_RESET = 0,
    localparam int CODE = ecc_pkg::code_width(WIDTH, PROTECTION),
    localparam int OC = $clog2(DEPTH + 1)
) (
    input wire i_clk,
    input wire i_rstb,
    input wire i_valid,
    output wire o_ready,
    input wire [WIDTH-1:0] i_data,
    input wire [KEY_WIDTH-1:0] i_key,
    input wire i_cancelable,
    input wire [KEY_WIDTH-1:0] i_query_key,
    output wire o_duplicate,
    input wire i_cancel,
    input wire [KEY_WIDTH-1:0] i_cancel_key,
    output wire o_cancel_match,
    output wire o_valid,
    input wire i_ready,
    output wire [WIDTH-1:0] o_data,
    output wire o_canceled,
    output wire o_bad,
    output wire [OC-1:0] o_count
);
    wire [CODE-1:0] encoded;
    wire [CODE-1:0] stored;
    wire bad;
    wire queue_bad;
    wire raw_valid;
    localparam int PTR = DEPTH > 1 ? $clog2(DEPTH) : 1;

    typedef struct packed {
        logic valid;
        logic cancelable;
        logic canceled;
        logic [KEY_WIDTH-1:0] key;
    } directory_t;

    localparam int DIRECTORY = $bits(directory_t);
    wire [DIRECTORY-1:0] records [DEPTH];
    logic [DIRECTORY-1:0] next_records [DEPTH];
    wire [DEPTH-1:0] directory_bad;
    wire [2*PTR-1:0] pointers;
    logic [2*PTR-1:0] next_pointers;
    wire pointer_bad;
    wire [PTR-1:0] head = pointers[0+:PTR];
    wire [PTR-1:0] tail = pointers[PTR+:PTR];
    directory_t first;
    assign first = records[head];
    wire [KEY_WIDTH-1:0] stored_key;
    wire stored_cancelable;
    wire raw_canceled;
    logic duplicate;
    logic cancel_match;
    assign o_duplicate = duplicate;
    assign o_cancel_match = cancel_match;
    wire push = i_valid && o_ready;
    wire pop = o_valid && i_ready;

    always @* begin
        duplicate = 1'b0;
        cancel_match = 1'b0;

        for (int k = 0; k < DEPTH; k++) begin
            directory_t entry;
            entry = records[k];

            if (entry.valid && entry.key === i_query_key) duplicate = 1'b1;

            if (entry.valid &&!entry.canceled && entry.cancelable &&
                entry.key === i_cancel_key) cancel_match = 1'b1;
        end
    end

    always @* begin
        next_pointers = pointers;

        for (int k = 0; k < DEPTH; k++) begin
            directory_t entry;
            entry = records[k];

            if (i_cancel && cancel_match && entry.valid && entry.key === i_cancel_key)
                entry.canceled = 1'b1;

            if (pop && head == PTR'(k)) entry = '0;

            if (push && tail == PTR'(k)) begin
                entry.valid = 1'b1;
                entry.cancelable = i_cancelable;
                entry.canceled = 1'b0;
                entry.key = i_key;
            end

            next_records[k] = entry;
        end

        if (pop) next_pointers[0+:PTR] = head == PTR'(DEPTH - 1) ? '0 : head + 1'b1;

        if (push) next_pointers[PTR+:PTR] = tail == PTR'(DEPTH - 1) ? '0 : tail + 1'b1;
    end

    banked_scratchpad_state #(
        .WIDTH(2 * PTR),
        .PROTECTION(PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_pointers (
        .i_clk(i_clk),
        .i_reset_n(i_rstb),
        .i_data(next_pointers),
        .o_data(pointers),
        .o_bad(pointer_bad)
    );

    for (genvar k = 0; k < DEPTH; k++) begin : g_directory
        banked_scratchpad_state #(
            .WIDTH(DIRECTORY),
            .PROTECTION(PROTECTION),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_entry (
            .i_clk(i_clk),
            .i_reset_n(i_rstb),
            .i_data(next_records[k]),
            .o_data(records[k]),
            .o_bad(directory_bad[k])
        );
    end

    tile_shell_codec #(.WIDTH(WIDTH), .PROTECTION(PROTECTION)) u_codec (
        .i_data(i_data),
        .o_code(encoded),
        .i_code(stored),
        .o_data(o_data),
        .o_corrected(),
        .o_bad(bad)
    );

    dma_engine_command_queue #(
        .DATA_BITS(CODE + KEY_WIDTH + 1),
        .DEPTH(DEPTH),
        .ID_BITS(KEY_WIDTH),
        .CONTEXT_BITS(1),
        .PROTECTED(PROTECTION == 1),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_queue (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_flush(1'b0),
        .i_valid(i_valid),
        .o_ready(o_ready),
        .i_data({i_cancelable, i_key, encoded}),
        .i_id(i_key),
        .i_query_id(i_query_key),
        .i_cancel_id(i_cancel_key),
        .i_context(1'b0),
        .i_query_context(1'b0),
        .i_cancel_context(1'b0),
        .o_duplicate(),
        .i_cancel(i_cancel && cancel_match),
        .o_cancel_match(),
        .o_valid(raw_valid),
        .i_ready(i_ready &&!o_bad),
        .o_data({stored_cancelable, stored_key, stored}),
        .o_canceled(raw_canceled),
        .o_corrupt(queue_bad),
        .o_occupancy(o_count)
    );

    assign o_bad = queue_bad || pointer_bad || (|directory_bad) ||
        (raw_valid && (bad ||!first.valid || first.key !== stored_key ||
            first.cancelable !== stored_cancelable || first.canceled !== raw_canceled));
    assign o_canceled = raw_canceled;
    assign o_valid = raw_valid &&!o_bad;
endmodule
