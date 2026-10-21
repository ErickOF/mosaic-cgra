`timescale 1ns / 1ps

// Handshake-qualified channel assertions for zero-delay native RTL. The Python
// scoreboard independently checks the command schema, protection and every byte.
module dma_engine_assertions #(
    parameter int C = 3,
    parameter int DESC_BITS = 32,
    parameter int STORE_BITS = 32,
    parameter int TILE_BITS = 32,
    parameter int OCC_BITS = 2,
    parameter int DEPTH = 2,
    parameter int ASYNC_RESET = 0,
    parameter int CANCEL_BITS = 5
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_discard,
    input logic i_abort,
    input logic i_start,
    input logic i_retire,
    input logic [2:0] i_phase,
    input logic [1:0] i_mode,
    input logic [1:0] i_status,
    input logic [2*C-1:0] i_elements,
    input logic [2*C-1:0] i_source_count,
    input logic [2*C-1:0] i_destination_count,
    input logic i_source_take,
    input logic i_sink_take,
    input logic i_load_armed,
    input logic i_store_armed,
    input logic i_load_finished,
    input logic i_store_finished,
    input logic i_load_valid,
    input logic i_load_ready,
    input logic i_store_valid,
    input logic i_store_ready,
    input logic [DESC_BITS-1:0] i_load_descriptor,
    input logic [DESC_BITS-1:0] i_store_descriptor,
    input logic i_store_data_valid,
    input logic i_store_data_ready,
    input logic i_tile_valid,
    input logic i_tile_ready,
    input logic [STORE_BITS-1:0] i_store_data,
    input logic [TILE_BITS-1:0] i_tile_data,
    input logic i_fifo_push,
    input logic i_fifo_pop,
    input logic [OCC_BITS-1:0] i_occupancy,
    input logic [CANCEL_BITS-1:0] i_cancel_timer
);
    import dma_engine_pkg::*;
    logic seen = 0;
    logic previous_load_stall;
    logic previous_store_stall;
    logic previous_store_data_stall;
    logic previous_tile_stall;
    logic [DESC_BITS-1:0] previous_load;
    logic [DESC_BITS-1:0] previous_store;
    logic [STORE_BITS-1:0] previous_store_data;
    logic [TILE_BITS-1:0] previous_tile_data;
    logic [2*C-1:0] expected_source;
    logic [2*C-1:0] expected_destination;
    logic [OCC_BITS:0] expected_occupancy;
    logic previous_fatal;
    logic [CANCEL_BITS-1:0] previous_cancel_timer;

    task automatic check_edge;
        if (i_rstb === 1'b0) begin
            seen = 1;
            previous_load_stall = 0;
            previous_store_stall = 0;
            previous_store_data_stall = 0;
            previous_tile_stall = 0;
            previous_fatal = 0;
            #1ps;
            assert (i_source_count == '0 && i_destination_count == '0 && i_occupancy == '0 &&
                    i_phase == 0)
            else $fatal(1, "DMA HDL assertion: reset state");
        end else if (seen && i_rstb === 1'b1) begin
            assert (( ^ {i_load_valid, i_store_valid, i_store_data_valid, i_tile_valid, i_phase} !==
                     1'bx))
            else $fatal(1, "DMA HDL assertion: known output controls");
            if (previous_fatal && i_phase == DMA_FATAL)
                assert (i_cancel_timer === previous_cancel_timer)
                else $fatal(1, "DMA HDL assertion: fatal cancel timer hold");
            previous_fatal = i_phase == DMA_FATAL;
            previous_cancel_timer = i_cancel_timer;
            if (!i_discard &&!i_abort) begin
                if (previous_load_stall)
                    assert (i_load_valid && i_load_descriptor === previous_load)
                    else $fatal(1, "DMA HDL assertion: load descriptor stability");
                if (previous_store_stall)
                    assert (i_store_valid && i_store_descriptor === previous_store)
                    else $fatal(1, "DMA HDL assertion: store descriptor stability");
                if (previous_store_data_stall)
                    assert (i_store_data_valid && i_store_data === previous_store_data)
                    else $fatal(1, "DMA HDL assertion: store data stability");
                if (previous_tile_stall)
                    assert (i_tile_valid && i_tile_data === previous_tile_data)
                    else $fatal(1, "DMA HDL assertion: tile data stability");
                if (i_mode == 0 && i_load_valid)
                    assert (i_store_armed)
                    else $fatal(1, "DMA HDL assertion: destination-first arming");
                if (i_source_take)
                    assert (i_source_count < i_elements &&
                            (i_mode == 2 ? i_store_armed : i_load_armed))
                    else $fatal(1, "DMA HDL assertion: legal source acceptance");
                if (i_sink_take)
                    assert (i_destination_count < i_elements && (i_mode == 1 || i_store_armed))
                    else $fatal(1, "DMA HDL assertion: legal destination acceptance");
                if (i_retire && i_status == 0) begin
                    assert (i_source_count == i_elements && i_destination_count == i_elements &&
                            (i_mode == 2 || i_load_finished) && (i_mode == 1 || i_store_finished))
                    else $fatal(1, "DMA HDL assertion: successful completion boundary");
                end
            end
            previous_load_stall = i_load_valid &&!i_load_ready &&!i_discard &&!i_abort;
            previous_store_stall = i_store_valid &&!i_store_ready &&!i_discard &&!i_abort;
            previous_store_data_stall = i_store_data_valid &&!i_store_data_ready &&!i_discard &&
                !i_abort;
            previous_tile_stall = i_tile_valid &&!i_tile_ready &&!i_discard &&!i_abort;
            previous_load = i_load_descriptor;
            previous_store = i_store_descriptor;
            previous_store_data = i_store_data;
            previous_tile_data = i_tile_data;
            expected_source = i_start ? '0 : i_source_count + (2 * C)'(i_source_take);
            expected_destination = i_start ? '0 : i_destination_count + (2 * C)'(i_sink_take);
            expected_occupancy = {1'b0, i_occupancy} + (OCC_BITS + 1)'(i_fifo_push) -
                (OCC_BITS + 1)'(i_fifo_pop);
            assert (expected_occupancy <= (OCC_BITS + 1)'(DEPTH))
            else $fatal(1, "DMA HDL assertion: FIFO capacity");
            #1ps;
            assert (i_source_count === expected_source &&
                    i_destination_count === expected_destination)
            else $fatal(1, "DMA HDL assertion: accepted-only counters");
            assert ({1'b0, i_occupancy} === expected_occupancy)
            else $fatal(1, "DMA HDL assertion: FIFO handshake occupancy");
        end
    endtask
    if (ASYNC_RESET == 1) begin : g_async
        always @(posedge i_clk or negedge i_rstb) check_edge();
    end else begin : g_sync
        always @(posedge i_clk) check_edge();
    end
endmodule
