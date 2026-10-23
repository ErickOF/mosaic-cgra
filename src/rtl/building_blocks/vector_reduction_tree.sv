`timescale 1ns / 1ps
`default_nettype none

// Compile-time operation tree. All SUM nodes retain the complete SUM_WIDTH.
// Extrema carry selection validity, so neither padding nor masked data can win.
module vector_reduction_tree #(
    parameter int ELEMENT_WIDTH = 8,
    parameter int NUM_ELEMENTS = 4,
    parameter int OPERATION = 0,
    localparam int GROWTH = $clog2(NUM_ELEMENTS),
    localparam int LEAVES = 2 ** GROWTH,
    localparam int WIDTH = OPERATION == 0 ? ELEMENT_WIDTH + GROWTH : ELEMENT_WIDTH,
    localparam int E = ELEMENT_WIDTH,
    localparam int N = NUM_ELEMENTS
) (
    input logic i_enable,
    input logic [N-1:0] i_mask,
    input logic [N*E-1:0] i_data,
    input logic i_signed,
    output wire [WIDTH-1:0] o_result
);
    if (N == 1) begin : g_single_element
        // A single selected value needs no signed comparison or SUM extension.
        wire unused_signed = i_signed;
    end
    for (genvar level = 0; level <= GROWTH; level++) begin : g_level
        localparam int NODES = LEAVES >> level;
        wire [WIDTH-1:0] value[NODES];

        if (OPERATION == 1 || OPERATION == 2) begin : g_selection
            wire selected[NODES];

            for (genvar k = 0; k < NODES; k++) begin : g_node
                if (level == 0) begin : g_leaf
                    if (k < N) begin : g_element
                        assign selected[k] = i_enable && i_mask[k];
                    end else begin : g_padding
                        assign selected[k] = 1'b0;
                    end
                end else begin : g_branch
                    wire left_valid = g_level[level-1].g_selection.selected[2*k];
                    wire right_valid = g_level[level-1].g_selection.selected[2*k+1];
                    wire [E-1:0] left_value = g_level[level-1].value[2*k];
                    wire [E-1:0] right_value = g_level[level-1].value[2*k+1];
                    wire less = i_signed && (left_value[E-1] != right_value[E-1]) ?
                        left_value[E-1] : left_value < right_value;
                    wire choose_right = OPERATION == 2 ? less : !less;
                    assign selected[k] = left_valid || right_valid;
                    assign value[k] = !left_valid ? right_value : !right_valid ? left_value :
                        choose_right ? right_value : left_value;
                end
            end
            wire unused_root_valid = selected[0];
        end else begin : g_associative
            wire unused_signed = i_signed;

            if (level > 0) begin : g_branch
                for (genvar k = 0; k < NODES; k++) begin : g_node
                    if (OPERATION == 0) begin : g_sum
                        assign value[k] = g_level[level-1].value[2*k] +
                            g_level[level-1].value[2*k+1];
                    end else if (OPERATION == 3) begin : g_and
                        assign value[k] = g_level[level-1].value[2*k] &
                            g_level[level-1].value[2*k+1];
                    end else begin : g_or
                        assign value[k] = g_level[level-1].value[2*k] |
                            g_level[level-1].value[2*k+1];
                    end
                end
            end
        end

        if (level == 0) begin : g_leaves
            for (genvar k = 0; k < LEAVES; k++) begin : g_leaf
                if (k < N) begin : g_element
                    wire [E-1:0] isolated;
                    operand_isolation #(.WIDTH(E),
                        .CLAMP_VALUE(OPERATION == 3 ? '1 : '0)) u_input (
                        .i_data(i_data[k*E+:E]),
                        .i_isolate(!(i_enable && i_mask[k])),
                        .o_data(isolated)
                    );
                    assign value[k] = {{(WIDTH - E){i_signed && isolated[E-1]}}, isolated};
                end else begin : g_padding
                    assign value[k] = OPERATION == 3 ? '1 : '0;
                end
            end
        end
    end

    assign o_result = g_level[GROWTH].value[0];
endmodule
`default_nettype wire
