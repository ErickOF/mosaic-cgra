`timescale 1ns / 1ps

// Opaque resident contexts with slice writes and separately committed validity.
// The configuration validator and execution safe-point policy live outside here.
module context_memory #(
    // Preserve illegal caller values until the elaboration guard checks them.
    parameter CONTEXT_WIDTH = 256,
    parameter CONTEXT_DEPTH = 4,
    parameter WRITE_SLICE_WIDTH = 32,
    parameter NUM_READ_PORTS = 2,
    parameter HAS_RAW_READBACK = 1,
    parameter ASYNC_RESET = 0,
    localparam int unsigned WORD_WIDTH = CONTEXT_WIDTH >= 1 && (^CONTEXT_WIDTH !== 1'bx) ? CONTEXT_WIDTH : 1,
    localparam int unsigned STORAGE_DEPTH = CONTEXT_DEPTH >= 1 && (^CONTEXT_DEPTH !== 1'bx) ? CONTEXT_DEPTH : 1,
    localparam int unsigned READ_PORTS = NUM_READ_PORTS >= 1 && (^NUM_READ_PORTS !== 1'bx) ? NUM_READ_PORTS : 1,
    localparam int unsigned NUM_WRITE_SLICES = WRITE_SLICE_WIDTH >= 1 && (^WRITE_SLICE_WIDTH !== 1'bx) &&
        WORD_WIDTH >= WRITE_SLICE_WIDTH ? WORD_WIDTH / WRITE_SLICE_WIDTH : 1,
    localparam int unsigned ADDR_WIDTH = STORAGE_DEPTH > 1 ? $clog2(STORAGE_DEPTH) : 1,
    localparam int unsigned READ_ADDR_WIDTH = READ_PORTS * ADDR_WIDTH,
    localparam int unsigned READ_DATA_WIDTH = READ_PORTS * WORD_WIDTH
) (
    input  logic i_clk,
    input  logic i_rstb,
    input  logic [READ_PORTS-1:0] i_read_enable,
    input  logic [READ_PORTS-1:0] i_read_raw,
    input  logic [READ_ADDR_WIDTH-1:0] i_read_address,
    output logic [READ_DATA_WIDTH-1:0] o_read_data,
    output logic [READ_PORTS-1:0] o_read_valid,
    input  logic i_write_enable,
    input  logic [NUM_WRITE_SLICES-1:0] i_write_mask,
    input  logic [ADDR_WIDTH-1:0] i_write_address,
    input  logic [WORD_WIDTH-1:0] i_write_data,
    input  logic i_commit_enable,
    input  logic [ADDR_WIDTH-1:0] i_commit_address,
    input  logic i_invalidate_enable,
    input  logic [ADDR_WIDTH-1:0] i_invalidate_address
);
    localparam bit PARAMETERS_VALID =
        (^CONTEXT_WIDTH !== 1'bx) && CONTEXT_WIDTH >= 1 &&
        (^CONTEXT_DEPTH !== 1'bx) && CONTEXT_DEPTH >= 1 &&
        (^WRITE_SLICE_WIDTH !== 1'bx) && WRITE_SLICE_WIDTH >= 1 &&
        (^NUM_READ_PORTS !== 1'bx) && NUM_READ_PORTS >= 1 &&
        (WRITE_SLICE_WIDTH > 0 && CONTEXT_WIDTH % WRITE_SLICE_WIDTH == 0) &&
        (HAS_RAW_READBACK === 0 || HAS_RAW_READBACK === 1) &&
        (ASYNC_RESET === 0 || ASYNC_RESET === 1);

    // Safe declaration dimensions allow malformed profiles to reach this guard
    // without division by zero or invalid part-selects in the implementation.
    logic [WORD_WIDTH-1:0] context_data[STORAGE_DEPTH];
    logic [STORAGE_DEPTH-1:0] context_valid;

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        context_memory_parameters_must_be_valid invalid_parameters ();
    end else begin : g_memory
        logic [STORAGE_DEPTH-1:0] next_valid;
        wire [STORAGE_DEPTH-1:0] write_decoded, commit_decoded, invalidate_decoded;
        wire write_address_valid;
        wire [1:0] unused_command_address_valid;

        // Common decoders reject unknown/out-of-range addresses without
        // selecting a legal entry, including non-power-of-two storage depths.
        decoder #(.NUM_OUTPUTS(STORAGE_DEPTH)) u_write_decoder (
            .i_enable(i_write_enable),
            .i_select(i_write_address),
            .o_decoded(write_decoded),
            .o_select_valid(write_address_valid)
        );

        decoder #(.NUM_OUTPUTS(STORAGE_DEPTH)) u_commit_decoder (
            .i_enable(i_commit_enable),
            .i_select(i_commit_address),
            .o_decoded(commit_decoded),
            .o_select_valid(unused_command_address_valid[0])
        );

        decoder #(.NUM_OUTPUTS(STORAGE_DEPTH)) u_invalidate_decoder (
            .i_enable(i_invalidate_enable),
            .i_select(i_invalidate_address),
            .o_decoded(invalidate_decoded),
            .o_select_valid(unused_command_address_valid[1])
        );

        wire data_write = i_rstb === 1'b1 && write_address_valid;

        // This clocked storage port has no reset. Asserted reset suppresses
        // configuration writes, and each unmasked slice retains its old bits.
        always_ff @(posedge i_clk) begin
            if (data_write) begin
                for (int slice = 0; slice < NUM_WRITE_SLICES; slice++) begin
                    if (i_write_mask[slice] === 1'b1) begin
                        context_data[i_write_address][slice*WRITE_SLICE_WIDTH+:WRITE_SLICE_WIDTH] <=
                            i_write_data[slice*WRITE_SLICE_WIDTH+:WRITE_SLICE_WIDTH];
                    end
                end
            end
        end

        // Commit may finalize a masked write atomically. Commit/invalidate of
        // the same entry is illegal; X exposes the violation without a priority.
        always_comb begin
            next_valid = context_valid;
            for (int entry = 0; entry < CONTEXT_DEPTH; entry++) begin
                if ((write_decoded[entry] && (|i_write_mask) === 1'b1) || invalidate_decoded[entry]) begin
                    next_valid[entry] = 1'b0;
                end
                if (commit_decoded[entry]) begin
                    next_valid[entry] = invalidate_decoded[entry] ? 1'bx : 1'b1;
                end
            end
        end

        // Keep reset on validity only. The common DFF samples X/Z reset inside
        // its sequential process, preserving four-state reset behavior without
        // an external data-input guard racing asynchronous reset assertion.
        dff #(.WIDTH(STORAGE_DEPTH), .RESET_VALUE('0), .ASYNC_RESET(ASYNC_RESET != 0)) u_valid (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(1'b1),
            .i_d(next_valid),
            .o_q(context_valid)
        );

        for (genvar port_index = 0; port_index < NUM_READ_PORTS; port_index++) begin : g_read
            wire [ADDR_WIDTH-1:0] address = i_read_address[port_index*ADDR_WIDTH+:ADDR_WIDTH];
            always_comb begin
                o_read_data[port_index*CONTEXT_WIDTH+:CONTEXT_WIDTH] = '0;
                o_read_valid[port_index] = 1'b0;
                if (i_read_enable[port_index] === 1'b1) begin
                    if (^address === 1'bx) begin
                        o_read_data[port_index*CONTEXT_WIDTH+:CONTEXT_WIDTH] = 'x;
                        o_read_valid[port_index] = 1'bx;
                    end else if (int'(address) < CONTEXT_DEPTH) begin
                        if (i_rstb === 1'b0) begin
                            // Even synchronous validity reset cannot expose an
                            // executable context while reset is asserted.
                            if (HAS_RAW_READBACK == 1 && i_read_raw[port_index] === 1'b1)
                                o_read_data[port_index*CONTEXT_WIDTH+:CONTEXT_WIDTH] = context_data[address];
                        end else if (i_rstb === 1'b1) begin
                            case (context_valid[address])
                                1'b1: begin
                                    o_read_data[port_index*CONTEXT_WIDTH+:CONTEXT_WIDTH] = context_data[address];
                                    o_read_valid[port_index] = 1'b1;
                                end
                                1'b0: begin
                                    if (HAS_RAW_READBACK == 1 && i_read_raw[port_index] === 1'b1)
                                        o_read_data[port_index*CONTEXT_WIDTH+:CONTEXT_WIDTH] = context_data[address];
                                end
                                default: begin
                                    o_read_data[port_index*CONTEXT_WIDTH+:CONTEXT_WIDTH] = 'x;
                                    o_read_valid[port_index] = 1'bx;
                                end
                            endcase
                        end else begin
                            o_read_data[port_index*CONTEXT_WIDTH+:CONTEXT_WIDTH] = 'x;
                            o_read_valid[port_index] = 1'bx;
                        end
                    end
                end else if (i_read_enable[port_index] !== 1'b0) begin
                    o_read_data[port_index*CONTEXT_WIDTH+:CONTEXT_WIDTH] = 'x;
                    o_read_valid[port_index] = 1'bx;
                end
            end
        end
    end
endmodule
