`timescale 1ns / 1ps

// Vector storage composed from scalar register-file banks, one per writable
// slice. All banks share entry addresses; only selected slices clock new data.
module vector_register_file #(
    parameter LANE_WIDTH = 32,
    parameter NUM_LANES = 4,
    parameter WRITE_SLICE_WIDTH = 8,
    parameter DEPTH = 16,
    parameter NUM_READ_PORTS = 2,
    parameter NUM_WRITE_PORTS = 1,
    parameter HAS_BROADCAST = 1,
    localparam bit PARAMETERS_VALID =
        ((LANE_WIDTH >= 1) === 1'b1) && (^LANE_WIDTH !== 1'bx) &&
        ((NUM_LANES >= 1) === 1'b1) && (^NUM_LANES !== 1'bx) &&
        ((WRITE_SLICE_WIDTH >= 1) === 1'b1) && (^WRITE_SLICE_WIDTH !== 1'bx) &&
        (((LANE_WIDTH % WRITE_SLICE_WIDTH) == 0) === 1'b1) &&
        ((DEPTH >= 1) === 1'b1) && (^DEPTH !== 1'bx) &&
        ((NUM_READ_PORTS >= 1) === 1'b1) && (^NUM_READ_PORTS !== 1'bx) &&
        ((NUM_WRITE_PORTS >= 1) === 1'b1) && (^NUM_WRITE_PORTS !== 1'bx) &&
        ((HAS_BROADCAST === 0) || (HAS_BROADCAST === 1)),
    localparam int unsigned LANE_BITS = PARAMETERS_VALID ? LANE_WIDTH : 1,
    localparam int unsigned LANES = PARAMETERS_VALID ? NUM_LANES : 1,
    localparam int unsigned SLICE_BITS = PARAMETERS_VALID ? WRITE_SLICE_WIDTH : 1,
    localparam int unsigned STORAGE_DEPTH = PARAMETERS_VALID ? DEPTH : 1,
    localparam int unsigned READ_PORTS = PARAMETERS_VALID ? NUM_READ_PORTS : 1,
    localparam int unsigned WRITE_PORTS = PARAMETERS_VALID ? NUM_WRITE_PORTS : 1,
    localparam int unsigned VECTOR_WIDTH = LANES * LANE_BITS,
    localparam int unsigned SLICES_PER_LANE = LANE_BITS / SLICE_BITS,
    localparam int unsigned MASK_WIDTH = LANES * SLICES_PER_LANE,
    localparam int unsigned ADDR_WIDTH = STORAGE_DEPTH > 1 ? $clog2(STORAGE_DEPTH) : 1,
    localparam int unsigned READ_ADDR_WIDTH = READ_PORTS * ADDR_WIDTH,
    localparam int unsigned WRITE_ADDR_WIDTH = WRITE_PORTS * ADDR_WIDTH,
    localparam int unsigned READ_DATA_WIDTH = READ_PORTS * VECTOR_WIDTH,
    localparam int unsigned WRITE_DATA_WIDTH = WRITE_PORTS * VECTOR_WIDTH,
    localparam int unsigned READ_LANE_ENABLE_WIDTH = READ_PORTS * LANES,
    localparam int unsigned WRITE_MASK_WIDTH = WRITE_PORTS * MASK_WIDTH
) (
    input  logic                              i_clk,
    input  logic [READ_PORTS-1:0]             i_read_enable,
    input  logic [READ_LANE_ENABLE_WIDTH-1:0] i_read_lane_enable,
    input  logic [READ_ADDR_WIDTH-1:0]        i_read_address,
    output logic [READ_DATA_WIDTH-1:0]        o_read_data,
    input  logic [WRITE_PORTS-1:0]            i_write_enable,
    input  logic [WRITE_MASK_WIDTH-1:0]       i_write_mask,
    input  logic [WRITE_PORTS-1:0]            i_write_broadcast,
    input  logic [WRITE_ADDR_WIDTH-1:0]       i_write_address,
    input  logic [WRITE_DATA_WIDTH-1:0]       i_write_data
);
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        vector_register_file_parameters_must_be_valid invalid_parameters ();
    end else begin : g_vector_file
        wire [WRITE_DATA_WIDTH-1:0] effective_data;

        if (HAS_BROADCAST == 1) begin : g_broadcast
            for (genvar w = 0; w < WRITE_PORTS; w++) begin : g_write
                for (genvar l = 0; l < LANES; l++) begin : g_lane
                    assign effective_data[w*VECTOR_WIDTH+l*LANE_BITS+:LANE_BITS] =
                        i_write_broadcast[w] ? i_write_data[w*VECTOR_WIDTH+:LANE_BITS] :
                        i_write_data[w*VECTOR_WIDTH+l*LANE_BITS+:LANE_BITS];
                end
            end
        end else begin : g_normal_only
            wire unused_broadcast = ^i_write_broadcast;
            assign effective_data = i_write_data;
        end

        for (genvar l = 0; l < LANES; l++) begin : g_lane
            wire [READ_PORTS-1:0] read_active;
            for (genvar r = 0; r < READ_PORTS; r++) begin : g_read_enable
                assign read_active[r] = i_read_enable[r] & i_read_lane_enable[r*LANES+l];
            end
            for (genvar s = 0; s < SLICES_PER_LANE; s++) begin : g_slice
                wire [WRITE_PORTS-1:0] write_active;
                wire [WRITE_PORTS*SLICE_BITS-1:0] write_data;
                wire [READ_PORTS*SLICE_BITS-1:0] read_data;
                for (genvar w = 0; w < WRITE_PORTS; w++) begin : g_write
                    assign write_active[w] = i_write_enable[w] & i_write_mask[w*MASK_WIDTH+l*SLICES_PER_LANE+s];
                    assign write_data[w*SLICE_BITS+:SLICE_BITS] = effective_data[w*VECTOR_WIDTH+l*LANE_BITS+s*SLICE_BITS+:SLICE_BITS];
                end

                // Scalar banks already suppress disabled/illegal addresses,
                // preserve unreset storage and poison overlapping writes rather
                // than imposing a winning port. Disjoint slice banks merge.
                register_file #(
                    .DATA_WIDTH(SLICE_BITS),
                    .DEPTH(STORAGE_DEPTH),
                    .NUM_READ_PORTS(READ_PORTS),
                    .NUM_WRITE_PORTS(WRITE_PORTS)
                ) u_bank (
                    .i_clk(i_clk),
                    .i_read_enable(read_active),
                    .i_read_address(i_read_address),
                    .o_read_data(read_data),
                    .i_write_enable(write_active),
                    .i_write_address(i_write_address),
                    .i_write_data(write_data)
                );

                for (genvar r = 0; r < READ_PORTS; r++) begin : g_read
                    assign o_read_data[r*VECTOR_WIDTH+l*LANE_BITS+s*SLICE_BITS+:SLICE_BITS] = read_data[r*SLICE_BITS+:SLICE_BITS];
                end
            end
        end
    end
endmodule
