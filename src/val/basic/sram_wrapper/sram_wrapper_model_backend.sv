`timescale 1ns / 1ps

// Verification-only replacement: granule planes and a timestamped return
// calendar provide a structurally different oracle for the same backend pins.
// This is not a vendor macro model or evidence of physical SRAM compatibility.
module sram_wrapper_backend #(
    parameter DATA_WIDTH=32, DEPTH=1024, MASK_GRANULARITY=8, READ_LATENCY=1,
    localparam ADDR_WIDTH=DEPTH>1?$clog2(DEPTH):1,
    localparam MASK_WIDTH=DATA_WIDTH/MASK_GRANULARITY
) (
    input logic i_clk,i_enable,i_write,
    input logic [ADDR_WIDTH-1:0] i_addr,
    input logic [DATA_WIDTH-1:0] i_wdata,
    input logic [MASK_WIDTH-1:0] i_wmask,
    output logic [DATA_WIDTH-1:0] o_rdata
);
    if (1) begin : g_reference
        logic [MASK_GRANULARITY-1:0] planes [MASK_WIDTH][DEPTH];
        wire [DATA_WIDTH-1:0] memory [DEPTH];
        logic [DATA_WIDTH-1:0] calendar [READ_LATENCY+1];
        integer due [READ_LATENCY+1];
        integer epoch=0;
        initial begin
            for (integer slot=0;slot<=READ_LATENCY;slot++) due[slot]=-1;
        end
        for (genvar word=0;word<DEPTH;word++) begin : g_word
            for (genvar granule=0;granule<MASK_WIDTH;granule++) begin : g_plane
                assign memory[word][granule*MASK_GRANULARITY+:MASK_GRANULARITY]=planes[granule][word];
            end
        end
        always @(posedge i_clk) begin
            for (integer slot=0;slot<=READ_LATENCY;slot++) begin
                if (due[slot]==epoch) o_rdata<=calendar[slot];
            end
            if (i_enable) begin
                if (i_write) begin
                    for (integer granule=0;granule<MASK_WIDTH;granule++) begin
                        if (i_wmask[granule]) planes[granule][i_addr]<=i_wdata[granule*MASK_GRANULARITY+:MASK_GRANULARITY];
                    end
                end else begin
                    calendar[epoch%(READ_LATENCY+1)]<=memory[i_addr];
                    due[epoch%(READ_LATENCY+1)]<=epoch+READ_LATENCY;
                end
            end
            epoch<=epoch+1;
        end
    end
endmodule
