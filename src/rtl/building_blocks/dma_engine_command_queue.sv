`timescale 1ns / 1ps

// Registered common FIFO plus an ID directory and ordered cancel tombstones.
// A canceled command retains its completion-order slot until reaching the head.
// Flush discards entries through normal FIFO pops; it never gates a reset pin.
// Internal helper: dma_engine validates the geometry before instantiation.
module dma_engine_command_queue #(
    parameter int DATA_BITS = 32,
    parameter int DEPTH = 4,
    parameter int ID_BITS = 12,
    parameter int CONTEXT_BITS = 8,
    parameter bit PROTECTED = 0,
    parameter bit ASYNC_RESET = 0,
    localparam int PTR_BITS = DEPTH > 1 ? $clog2(DEPTH) : 1,
    localparam int OCC_BITS = $clog2(DEPTH + 1),
    localparam int STORED_BITS = DATA_BITS + (PROTECTED ? 1 : 0)
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_flush,
    input logic i_valid,
    output logic o_ready,
    input logic [DATA_BITS-1:0] i_data,
    input logic [ID_BITS-1:0] i_id,
    input logic [ID_BITS-1:0] i_query_id,
    input logic [ID_BITS-1:0] i_cancel_id,
    input logic [CONTEXT_BITS-1:0] i_context,
    input logic [CONTEXT_BITS-1:0] i_query_context,
    input logic [CONTEXT_BITS-1:0] i_cancel_context,
    output logic o_duplicate,
    input logic i_cancel,
    output logic o_cancel_match,
    output logic o_valid,
    input logic i_ready,
    output logic [DATA_BITS-1:0] o_data,
    output logic o_canceled,
    output logic o_corrupt,
    output logic [OCC_BITS-1:0] o_occupancy
);
    logic [ID_BITS-1:0] ids[DEPTH];
    logic [CONTEXT_BITS-1:0] contexts[DEPTH];
    logic [DEPTH-1:0] occupied;
    logic [DEPTH-1:0] canceled;
    logic [PTR_BITS-1:0] read_pointer;
    logic [PTR_BITS-1:0] write_pointer;
    wire push = i_valid && o_ready;
    wire pop = o_valid && (i_ready || i_flush);
    wire [STORED_BITS-1:0] stored_input;
    wire [STORED_BITS-1:0] stored_output;
    wire unused_full;
    wire unused_empty;
    wire unused_almost_full;
    wire unused_almost_empty;
    wire [DATA_BITS-1:0] unused_checked;
    wire unused_valid;
    wire unused_no_error;
    wire unused_any_error;
    wire unused_generated_parity;
    wire unused_parity_error;
    logic [DEPTH-1:0] directory_select;
    logic [DEPTH-1:0] directory_write;

    // Share one decode across the command ID and context payload banks. Reset
    // invalidates occupied entries; their payload intentionally remains unreset.
    decoder #(
        .NUM_OUTPUTS(DEPTH),
        .SELECT_WIDTH(PTR_BITS)
    ) u_directory_decoder (
        .i_enable(push),
        .i_select(write_pointer),
        .o_decoded(directory_select),
        .o_select_valid()
    );

    write_gate #(
        .WIDTH(DEPTH)
    ) u_directory_write_gate (
        .i_write_enable(directory_select),
        .i_suppress({DEPTH{i_rstb !== 1'b1}}),
        .o_write_enable(directory_write),
        .o_write_suppressed()
    );

    for (genvar k = 0; k < DEPTH; k++) begin : g_id_entry
        dff #(
            .WIDTH(ID_BITS + CONTEXT_BITS)
        ) u_directory (
            .i_clk(i_clk),
            .i_rstb(1'b1),
            .i_enable(directory_write[k]),
            .i_d({i_context, i_id}),
            .o_q({contexts[k], ids[k]})
        );
    end

    if (PROTECTED) begin : g_parity
        parity #(
            .DATA_WIDTH(DATA_BITS),
            .PARITY_GRANULE_WIDTH(DATA_BITS)
        ) u_parity (
            .i_generate_data(i_data),
            .i_check_data(stored_output[DATA_BITS-1:0]),
            .i_check_parity(stored_output[DATA_BITS]),
            .o_generated_parity(unused_generated_parity),
            .o_checked_data(unused_checked),
            .o_error_vector(unused_parity_error),
            .o_granule_valid(unused_valid),
            .o_no_error(unused_no_error),
            .o_any_error(unused_any_error)
        );
        assign stored_input = {unused_generated_parity, i_data};
        assign o_corrupt = o_valid && (unused_parity_error !== 1'b0);
    end else begin : g_unprotected
        assign stored_input = i_data;
        assign o_corrupt = 1'b0;
        assign unused_generated_parity = 1'b0;
        assign unused_parity_error = 1'b0;
        assign unused_any_error = 1'b0;
        assign unused_checked = '0;
        assign unused_valid = 1'b0;
        assign unused_no_error = 1'b0;
    end

    assign o_data = stored_output[DATA_BITS-1:0];
    assign o_canceled = o_valid && canceled[read_pointer];

    always_comb begin
        o_duplicate = 1'b0;
        o_cancel_match = 1'b0;

        for (int k = 0; k < DEPTH; k ++ ) begin
            if (occupied[k] && ids[k] === i_query_id && contexts[k] === i_query_context)
                o_duplicate = 1'b1;
            if (occupied[k] &&!canceled[k] && ids[k] === i_cancel_id &&
                contexts[k] === i_cancel_context)
                o_cancel_match = 1'b1;
        end
    end

    fifo #(
        .DATA_WIDTH(STORED_BITS),
        .DEPTH(DEPTH),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_fifo (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_valid(i_valid),
        .i_data(stored_input),
        .i_ready(i_ready || i_flush),
        .o_ready(o_ready),
        .o_valid(o_valid),
        .o_data(stored_output),
        .o_full(unused_full),
        .o_empty(unused_empty),
        .o_almost_full(unused_almost_full),
        .o_almost_empty(unused_almost_empty),
        .o_occupancy(o_occupancy)
    );

    // Explicit reset variants keep all state in i_clk's reset domain. The ID
    // payload needs no reset; occupied masks it before any comparison is used.
    task automatic update_directory;
        if (i_cancel)
            for (int k = 0; k < DEPTH; k ++ )
            if (occupied[k] && ids[k] === i_cancel_id && contexts[k] === i_cancel_context)
                canceled[k] <= 1'b1;

        if (pop) begin
            occupied[read_pointer] <= 1'b0;
            canceled[read_pointer] <= 1'b0;
            read_pointer <= read_pointer == PTR_BITS'(DEPTH - 1) ? '0 : read_pointer + 1'b1;
        end

        if (push) begin
            occupied[write_pointer] <= 1'b1;
            canceled[write_pointer] <= 1'b0;
            write_pointer <= write_pointer == PTR_BITS'(DEPTH - 1) ? '0 : write_pointer + 1'b1;
        end
    endtask

    if (ASYNC_RESET == 1) begin : g_async
        always_ff @(posedge i_clk or negedge i_rstb) begin
            if (!i_rstb) begin
                occupied <= '0;
                canceled <= '0;
                read_pointer <= '0;
                write_pointer <= '0;
            end else update_directory();
        end
    end else begin : g_sync
        always_ff @(posedge i_clk) begin
            if (!i_rstb) begin
                occupied <= '0;
                canceled <= '0;
                read_pointer <= '0;
                write_pointer <= '0;
            end else update_directory();
        end
    end
endmodule
