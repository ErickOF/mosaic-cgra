`timescale 1ns / 1ps

// Scalar full-word storage. Initialization, validity and write-port ownership
// belong to the integrating architecture; this module has no reset or bypass.
module register_file #(
    parameter DATA_WIDTH = 32,
    parameter DEPTH = 32,
    parameter NUM_READ_PORTS = 2,
    parameter NUM_WRITE_PORTS = 1,
    localparam bit PARAMETERS_VALID =
        ((DATA_WIDTH >= 1) === 1'b1) &&
        ((DEPTH >= 1) === 1'b1) &&
        ((NUM_READ_PORTS >= 1) === 1'b1) &&
        ((NUM_WRITE_PORTS >= 1) === 1'b1),
    // Safe dimensions let invalid callers reach the named elaboration guard.
    localparam int unsigned WORD_WIDTH = PARAMETERS_VALID ? DATA_WIDTH : 1,
    localparam int unsigned STORAGE_DEPTH = PARAMETERS_VALID ? DEPTH : 1,
    localparam int unsigned READ_PORTS = PARAMETERS_VALID ? NUM_READ_PORTS : 1,
    localparam int unsigned WRITE_PORTS = PARAMETERS_VALID ? NUM_WRITE_PORTS : 1,
    localparam int unsigned ADDR_WIDTH = STORAGE_DEPTH > 1 ? $clog2(STORAGE_DEPTH) : 1,
    localparam int unsigned READ_ADDR_WIDTH = READ_PORTS * ADDR_WIDTH,
    localparam int unsigned WRITE_ADDR_WIDTH = WRITE_PORTS * ADDR_WIDTH,
    localparam int unsigned READ_DATA_WIDTH = READ_PORTS * WORD_WIDTH,
    localparam int unsigned WRITE_DATA_WIDTH = WRITE_PORTS * WORD_WIDTH
) (
    input  logic                        i_clk,
    input  logic [READ_PORTS-1:0]       i_read_enable,
    input  logic [READ_ADDR_WIDTH-1:0]  i_read_address,
    output logic [READ_DATA_WIDTH-1:0]  o_read_data,
    input  logic [WRITE_PORTS-1:0]      i_write_enable,
    input  logic [WRITE_ADDR_WIDTH-1:0] i_write_address,
    input  logic [WRITE_DATA_WIDTH-1:0] i_write_data
);
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        register_file_parameters_must_be_valid invalid_parameters ();
    end else begin : g_register_file
        logic [WORD_WIDTH-1:0] registers [STORAGE_DEPTH];
        wire [STORAGE_DEPTH-1:0] write_decoded [WRITE_PORTS];

        for (genvar w = 0; w < WRITE_PORTS; w++) begin : g_write_port
            wire unused_address_valid;
            // The shared decoder selects no entry for disabled, unknown or
            // out-of-range accesses. Interface assertions live in validation.
            decoder #(.NUM_OUTPUTS(STORAGE_DEPTH)) u_decoder (
                .i_enable(i_write_enable[w]),
                .i_select(i_write_address[w*ADDR_WIDTH+:ADDR_WIDTH]),
                .o_decoded(write_decoded[w]),
                .o_select_valid(unused_address_valid)
            );
        end

        for (genvar entry = 0; entry < STORAGE_DEPTH; entry++) begin : g_entry
            logic selected, conflict;
            logic [WORD_WIDTH-1:0] next_data;
            always_comb begin
                selected = 1'b0;
                conflict = 1'b0;
                // This value is never clocked without a selected port. A
                // don't-care avoids inferring a redundant constant-data reset.
                next_data = 'x;
                for (int w = 0; w < WRITE_PORTS; w++) begin
                    if (write_decoded[w][entry]) begin
                        conflict = conflict || selected;
                        selected = 1'b1;
                        next_data = i_write_data[w*WORD_WIDTH+:WORD_WIDTH];
                    end
                end
            end
            // A legal access selects exactly one port. An illegal collision
            // has no winner: expose X rather than defining write priority.
            // Only the addressed word updates; payload has no reset or clear.
            always_ff @(posedge i_clk) begin
                if (selected) registers[entry] <= conflict ? 'x : next_data;
            end
        end

        for (genvar r = 0; r < READ_PORTS; r++) begin : g_read_port
            // Clamp inactive mux addresses to suppress disabled-port activity.
            wire [ADDR_WIDTH-1:0] address = i_read_enable[r] ?
                i_read_address[r*ADDR_WIDTH+:ADDR_WIDTH] : '0;
            always_comb begin
                o_read_data[r*WORD_WIDTH+:WORD_WIDTH] = '0;
                case (i_read_enable[r])
                    1'b0: begin end
                    1'b1: begin
                        if (^address === 1'bx)
                            o_read_data[r*WORD_WIDTH+:WORD_WIDTH] = 'x;
                        else if ({1'b0, address} < (ADDR_WIDTH+1)'(STORAGE_DEPTH))
                            o_read_data[r*WORD_WIDTH+:WORD_WIDTH] = registers[address];
                    end
                    default: o_read_data[r*WORD_WIDTH+:WORD_WIDTH] = 'x;
                endcase
            end
        end
    end
endmodule
