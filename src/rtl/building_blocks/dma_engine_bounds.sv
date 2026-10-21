`timescale 1ns / 1ps

// Mathematical affine rectangle bounds, including the final element's bytes.
// Isolating validation inputs keeps the multiply/compare cone quiet otherwise.
// Internal helper: dma_engine validates the geometry before instantiation.
module dma_engine_bounds #(
    parameter int W = 40,
    parameter int C = 16,
    parameter int SIZE_WIDTH = 5,
    parameter int MAX_ELEMENT_LOG2 = 4,
    localparam int P = W + C + 3
) (
    input logic i_enable,
    input logic [1:0] i_mode,
    input logic [W-1:0] i_base,
    input logic [W-1:0] i_inner_stride,
    input logic [W-1:0] i_outer_stride,
    input logic [C-1:0] i_inner_count,
    input logic [C-1:0] i_outer_count,
    input logic [SIZE_WIDTH-1:0] i_size,
    output logic o_legal,
    output logic [4:0] o_error,
    output logic [W:0] o_lowest,
    output logic [W:0] o_limit
);
    import dma_engine_pkg::*;

    logic signed [P-1:0] base;
    logic signed [P-1:0] inner_step;
    logic signed [P-1:0] outer_step;
    logic signed [P-1:0] inner_delta;
    logic signed [P-1:0] outer_delta;
    logic signed [P-1:0] lowest;
    logic signed [P-1:0] highest;
    logic signed [P-1:0] element;
    logic [W-1:0] alignment;

    wire unsupported_size;
    if (MAX_ELEMENT_LOG2 == 2 ** SIZE_WIDTH - 1) begin : g_all_sizes
        assign unsupported_size = 1'b0;
    end else begin : g_limit_size
        assign unsupported_size = 32'(i_size) > MAX_ELEMENT_LOG2;
    end
    always_comb begin
        base = '0;
        inner_step = '0;
        outer_step = '0;
        inner_delta = '0;
        outer_delta = '0;
        lowest = '0;
        highest = '0;
        element = '0;
        alignment = '0;
        o_legal = 1'b0;
        o_error = DMA_ERR_NONE;
        o_lowest = '0;
        o_limit = '0;

        if (i_enable) begin
            if (( ^ {i_mode, i_base, i_inner_count, i_outer_count, i_size} === 1'bx) ||
                ((i_mode != 0) && ( ^ i_inner_stride === 1'bx)) ||
                ((i_mode == 2) && ( ^ i_outer_stride === 1'bx)))
                o_error = DMA_ERR_UNKNOWN;
            else if (i_mode == 3 || i_inner_count == 0 || i_outer_count == 0 ||
                     (i_mode != 2 && i_outer_count != 1) || unsupported_size)
                o_error = DMA_ERR_COMMAND;
            else begin
                base = $signed({{(P - W) {1'b0}}, i_base});
                element = P'(1) << i_size;
                alignment = W'(element - 1'b1);
                inner_step = i_mode == 0 ? element : P'($signed(i_inner_stride));
                outer_step = i_mode == 2 ? P'($signed(i_outer_stride)) : P'(0);
                inner_delta = ($signed({{(P - C) {1'b0}}, i_inner_count}) - P'(1)) * inner_step;
                outer_delta = ($signed({{(P - C) {1'b0}}, i_outer_count}) - P'(1)) * outer_step;
                lowest = base + (inner_delta < 0 ? inner_delta : P'(0)) +
                    (outer_delta < 0 ? outer_delta : P'(0));
                highest = base + (inner_delta > 0 ? inner_delta : P'(0)) +
                    (outer_delta > 0 ? outer_delta : P'(0)) + element - 1'b1;

                if (( | (i_base & alignment)) || ((i_mode != 0) && ( | (i_inner_stride &
                    alignment))) ||
                    ((i_mode == 2) && ( | (i_outer_stride & alignment)))) begin
                    o_error = DMA_ERR_ALIGNMENT;
                end else if (lowest < 0 || highest < lowest || highest > ($signed(
                        P'(1) << W
                    ) - 1'b1)) begin
                    o_error = DMA_ERR_BOUNDS;
                end else begin
                    o_legal = 1'b1;
                    o_lowest = (W + 1)'(lowest);
                    o_limit = (W + 1)'(highest + 1'b1);
                end
            end
        end
    end
endmodule
