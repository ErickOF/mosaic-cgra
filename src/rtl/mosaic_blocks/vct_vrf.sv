`timescale 1ns / 1ps
`default_nettype none

// Encode each independently writable slice before the released vector RF.
// Payload codewords have no reset. The parent owns protected slice validity.
module vct_vrf #(
    parameter int LANES = 4,
    parameter int WIDTH = 32,
    parameter int SLICE = 8,
    parameter int DEPTH = 8,
    parameter int READ_PORTS = 2,
    parameter int WRITE_PORTS = 1,
    parameter int PROTECTION = 0,
    localparam int SLICES = WIDTH / SLICE,
    localparam int MASK = LANES * SLICES,
    localparam int ADDRESS = DEPTH > 1 ? $clog2(DEPTH) : 1,
    localparam int CODE = PROTECTION == 2 ? SLICE + ecc_pkg::hamming_bits(SLICE) + 1 :
        SLICE + PROTECTION,
    localparam int PHYSICAL = MASK * CODE
) (
    input logic i_clk,
    input logic [2*MASK-1:0] i_read_mask,
    input logic [2*ADDRESS-1:0] i_read_address,
    output wire [2*LANES*WIDTH-1:0] o_read_data,
    output wire [1:0] o_bad,
    output wire [1:0] o_corrected,
    input logic i_write,
    input logic [MASK-1:0] i_write_mask,
    input logic [ADDRESS-1:0] i_write_address,
    input logic [LANES*WIDTH-1:0] i_write_data
);
    wire [PHYSICAL-1:0] encoded;
    wire [READ_PORTS*PHYSICAL-1:0] codes;
    wire [2*MASK-1:0] bad;
    wire [2*MASK-1:0] corrected;

    // Model every slice as a physical RF lane, so inactive slices do not read.
    vector_register_file #(
        .LANE_WIDTH(CODE), .NUM_LANES(MASK), .WRITE_SLICE_WIDTH(CODE),
        .DEPTH(DEPTH), .NUM_READ_PORTS(READ_PORTS), .NUM_WRITE_PORTS(WRITE_PORTS),
        .HAS_BROADCAST(0)
    ) u_storage (
        .i_clk(i_clk),
        .i_read_enable(READ_PORTS'({|i_read_mask[MASK+:MASK], |i_read_mask[0+:MASK]})),
        .i_read_lane_enable((READ_PORTS * MASK)'(i_read_mask)),
        .i_read_address((READ_PORTS * ADDRESS)'(i_read_address)),
        .o_read_data(codes),
        .i_write_enable(WRITE_PORTS'(i_write)),
        .i_write_mask((WRITE_PORTS * MASK)'(i_write_mask)),
        .i_write_broadcast({WRITE_PORTS{1'b0}}),
        .i_write_address((WRITE_PORTS * ADDRESS)'(i_write_address)),
        .i_write_data((WRITE_PORTS * PHYSICAL)'(encoded))
    );

    for (genvar s = 0; s < MASK; s++) begin : g_slice
        tile_shell_codec #(.WIDTH(SLICE), .PROTECTION(PROTECTION)) u_encode (
            .i_data(i_write_data[s*SLICE+:SLICE]),
            .o_code(encoded[s*CODE+:CODE]),
            .i_code({CODE{1'b0}}),
            .o_data(),
            .o_bad(),
            .o_corrected()
        );

        for (genvar r = 0; r < 2; r++) begin : g_read
            wire [SLICE-1:0] decoded;
            wire b;
            wire c;

            tile_shell_codec #(.WIDTH(SLICE), .PROTECTION(PROTECTION)) u_decode (
                .i_data({SLICE{1'b0}}),
                .o_code(),
                .i_code(codes[r*PHYSICAL+s*CODE+:CODE]),
                .o_data(decoded),
                .o_bad(b),
                .o_corrected(c)
            );

            assign o_read_data[r*LANES*WIDTH+s*SLICE+:SLICE] =
                i_read_mask[r*MASK+s] ? decoded : '0;
            assign bad[r*MASK+s] = i_read_mask[r*MASK+s] && b;
            assign corrected[r*MASK+s] = i_read_mask[r*MASK+s] && c;
        end
    end

    assign o_bad = {|bad[MASK+:MASK], |bad[0+:MASK]};
    assign o_corrected = {|corrected[MASK+:MASK], |corrected[0+:MASK]};
endmodule
`default_nettype wire
