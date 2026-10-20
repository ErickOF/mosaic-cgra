`timescale 1ns / 1ps

// Sparse, independently selected forwarding paths. Only declared edges read
// source data. Registered payload is unreset; validity owns reset and flush.
module bypass_network #(
    parameter int unsigned DATA_WIDTH = 32,
    parameter int unsigned NUM_SOURCES = 8,
    parameter int unsigned NUM_DESTINATIONS = 4,
    // Untyped flags retain X/Z and oversized caller values for the guard.
    parameter REGISTER_OUTPUTS = 0,
    parameter ASYNC_RESET = 0,
    localparam int unsigned SELECT_WIDTH = NUM_SOURCES > 1 ? $clog2(NUM_SOURCES) : 1,
    localparam int unsigned SOURCE_DATA_WIDTH = NUM_SOURCES * DATA_WIDTH,
    localparam int unsigned DESTINATION_DATA_WIDTH = NUM_DESTINATIONS * DATA_WIDTH,
    localparam int unsigned SELECT_BUS_WIDTH = NUM_DESTINATIONS * SELECT_WIDTH,
    localparam int unsigned CONNECTIVITY_WIDTH = NUM_DESTINATIONS * NUM_SOURCES,
    parameter logic [CONNECTIVITY_WIDTH-1:0] CONNECTIVITY_MASK = '1
) (
    input  logic                              i_clk,
    input  logic                              i_rstb,
    input  logic [SOURCE_DATA_WIDTH-1:0]      i_source_data,
    input  logic [NUM_SOURCES-1:0]            i_source_valid,
    input  logic [NUM_DESTINATIONS-1:0]       i_destination_enable,
    input  logic [SELECT_BUS_WIDTH-1:0]       i_select,
    input  logic [NUM_DESTINATIONS-1:0]       i_capture_enable,
    input  logic                              i_flush,
    output logic [DESTINATION_DATA_WIDTH-1:0] o_destination_data,
    output logic [NUM_DESTINATIONS-1:0]       o_destination_valid,
    output logic [NUM_DESTINATIONS-1:0]       o_selection_error
);
    if (DATA_WIDTH < 1 || NUM_SOURCES < 1 || NUM_DESTINATIONS < 1 ||
        (REGISTER_OUTPUTS !== 0 && REGISTER_OUTPUTS !== 1) ||
        (ASYNC_RESET !== 0 && ASYNC_RESET !== 1)) begin : g_invalid_parameters
        // Preserve illegal caller values, including X/Z, until this guard can
        // reject them instead of silently selecting a static implementation.
        bypass_network_invalid_parameters invalid_parameters ();
    end
    if (^CONNECTIVITY_MASK === 1'bx) begin : g_unknown_connectivity
        bypass_network_connectivity_must_be_known invalid_connectivity ();
    end

    logic [DESTINATION_DATA_WIDTH-1:0] registered_data;
    logic [NUM_DESTINATIONS-1:0] registered_valid;

    function automatic bit source_connected_f(input int source);
        source_connected_f = 1'b0;
        for (int d = 0; d < NUM_DESTINATIONS; d++) begin
            source_connected_f |= CONNECTIVITY_MASK[d*NUM_SOURCES+source];
        end
    endfunction

    // A stable interface may include sources unused by this particular graph.
    // No output or state depends on those ports; synthesis removes this net.
    for (genvar s = 0; s < NUM_SOURCES; s++) begin : g_source
        if (!source_connected_f(s)) begin : g_unconnected
            wire unused_source = ^{i_source_data[s*DATA_WIDTH+:DATA_WIDTH], i_source_valid[s]};
        end
    end

    for (genvar d = 0; d < NUM_DESTINATIONS; d++) begin : g_destination
        if (CONNECTIVITY_MASK[d*NUM_SOURCES+:NUM_SOURCES] == '0) begin : g_empty_row
            bypass_network_destination_requires_an_edge invalid_row ();
        end
        wire consumed = i_destination_enable[d] &
                        (REGISTER_OUTPUTS != 0 ? i_capture_enable[d] : 1'b1);
        wire [SELECT_WIDTH-1:0] selected = i_select[d*SELECT_WIDTH+:SELECT_WIDTH];
        logic [SOURCE_DATA_WIDTH-1:0] data_terms;
        logic [NUM_SOURCES-1:0] valid_terms;
        logic [NUM_SOURCES-1:0] selected_terms;
        logic [DATA_WIDTH-1:0] routed_data;
        logic routed_valid;
        logic selection_error;

        for (genvar s = 0; s < NUM_SOURCES; s++) begin : g_edge
            if (CONNECTIVITY_MASK[d*NUM_SOURCES+s]) begin : g_connected
                assign selected_terms[s] = consumed & (selected == SELECT_WIDTH'(s));
                assign valid_terms[s] = selected_terms[s] & i_source_valid[s];
                assign data_terms[s*DATA_WIDTH +: DATA_WIDTH] =
                    valid_terms[s] ? i_source_data[s*DATA_WIDTH +: DATA_WIDTH] : '0;
            end else begin : g_disconnected
                assign selected_terms[s] = 1'b0;
                assign valid_terms[s] = 1'b0;
                assign data_terms[s*DATA_WIDTH+:DATA_WIDTH] = '0;
            end
        end

        always_comb begin
            routed_data = '0;
            routed_valid = |valid_terms;
            selection_error = consumed & !(|selected_terms);
            for (int s = 0; s < NUM_SOURCES; s++) begin
                routed_data |= data_terms[s*DATA_WIDTH+:DATA_WIDTH];
            end
            // X/Z select encodings have no hardware meaning. Simulation must
            // expose them, including when every candidate payload equals zero.
            case (^selected)
                1'b0, 1'b1: begin
                end
                default:
                if (consumed) begin
                    routed_data = 'x;
                    routed_valid = 1'bx;
                    selection_error = 1'bx;
                end
            endcase
        end
        assign o_selection_error[d] = selection_error;

        if (REGISTER_OUTPUTS != 0) begin : g_registered
            wire capture_data = i_rstb & !i_flush & consumed & (|selected_terms) & routed_valid;
            // Constant inactive reset removes reset logic from payload banks.
            dff #(
                .WIDTH(DATA_WIDTH),
                .HAS_ENABLE(1'b1)
            ) u_data (
                .i_clk(i_clk),
                .i_rstb(1'b1),
                .i_enable(capture_data),
                .i_d(routed_data),
                .o_q(registered_data[d*DATA_WIDTH+:DATA_WIDTH])
            );

            dff #(
                .WIDTH(1),
                .ASYNC_RESET(ASYNC_RESET != 0),
                .HAS_ENABLE(1'b1)
            ) u_valid (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(i_flush | consumed),
                .i_d(i_flush ? 1'b0 : routed_valid),
                .o_q(registered_valid[d])
            );
            assign o_destination_valid[d] = i_destination_enable[d] & registered_valid[d];
            assign o_destination_data[d*DATA_WIDTH +: DATA_WIDTH] =
                o_destination_valid[d] ? registered_data[d*DATA_WIDTH +: DATA_WIDTH] : '0;
        end else begin : g_combinational
            assign registered_data[d*DATA_WIDTH+:DATA_WIDTH] = '0;
            assign registered_valid[d] = 1'b0;
            assign o_destination_data[d*DATA_WIDTH+:DATA_WIDTH] = routed_data;
            assign o_destination_valid[d] = routed_valid;
            // Stable interface controls intentionally have no functional role.
            wire unused_controls = ^{i_clk, i_rstb, i_capture_enable[d], i_flush,
                                     registered_valid[d],
                                     registered_data[d*DATA_WIDTH +: DATA_WIDTH]};
        end
    end
endmodule
