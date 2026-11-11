`timescale 1ns / 1ps

// Default inferred 1RW implementation. Replace this module through the file list
// with an adapter having identical parameters, ports, masks and edge timing.
module sram_wrapper_backend #(
    parameter DATA_WIDTH = 32,
    parameter DEPTH = 1024,
    parameter MASK_GRANULARITY = 8,
    parameter READ_LATENCY = 1,
    localparam bit PARAMETERS_VALID =
        ((DATA_WIDTH >= 1 && DEPTH >= 1 && MASK_GRANULARITY >= 1 && READ_LATENCY >= 1) === 1'b1) &&
        (((^DATA_WIDTH == 1'b0) || (^DATA_WIDTH == 1'b1)) === 1'b1) && (((^DEPTH == 1'b0) || (^DEPTH == 1'b1)) === 1'b1) &&
        (((^MASK_GRANULARITY == 1'b0) || (^MASK_GRANULARITY == 1'b1)) === 1'b1) && (((^READ_LATENCY == 1'b0) || (^READ_LATENCY == 1'b1)) === 1'b1) &&
        ((MASK_GRANULARITY > 0 && DATA_WIDTH % MASK_GRANULARITY == 0) === 1'b1),
    localparam int unsigned DATA_BITS = PARAMETERS_VALID ? DATA_WIDTH : 1,
    localparam int unsigned WORDS = PARAMETERS_VALID ? DEPTH : 1,
    localparam int unsigned GRANULE_BITS = PARAMETERS_VALID ? MASK_GRANULARITY : 1,
    localparam int unsigned LATENCY = PARAMETERS_VALID ? READ_LATENCY : 1,
    localparam int unsigned ADDR_WIDTH = WORDS > 1 ? $clog2(WORDS) : 1,
    localparam int unsigned MASK_WIDTH = DATA_BITS / GRANULE_BITS
) (
    input logic i_clk,
    input logic i_enable,
    input logic i_write,
    input logic [ADDR_WIDTH-1:0] i_addr,
    input logic [DATA_BITS-1:0] i_wdata,
    input logic [MASK_WIDTH-1:0] i_wmask,
    output wire [DATA_BITS-1:0] o_rdata
);
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        sram_wrapper_backend_parameters_must_be_valid invalid_parameters ();
    end else begin : g_inferred
        logic [DATA_BITS-1:0] memory [WORDS];
        logic [DATA_BITS-1:0] read_data [LATENCY+1];
        logic [LATENCY:0] read_valid;
        wire read_enable = i_enable && !i_write;

        // Storage, read data and this unqualified backend activity history have
        // no reset. Only the shell decides which returned reads remain live.
        always_ff @(posedge i_clk) begin
            read_valid <= {read_valid[LATENCY-1:0], read_enable};
            if (i_enable) begin
                if (i_write) begin
                    for (int unsigned granule = 0; granule < MASK_WIDTH; granule++) begin
                        if (i_wmask[granule])
                            memory[i_addr][granule*GRANULE_BITS+:GRANULE_BITS] <=
                                i_wdata[granule*GRANULE_BITS+:GRANULE_BITS];
                    end
                end else begin
                    // Snapshot here, before any later write to this address.
                    read_data[0] <= memory[i_addr];
                end
            end
            for (int unsigned stage = 1; stage <= LATENCY; stage++) begin
                if (read_valid[stage-1]) read_data[stage] <= read_data[stage-1];
            end
        end
        // A request sampled at t reaches this bus after edge t+READ_LATENCY.
        assign o_rdata = read_data[LATENCY];
    end
endmodule
