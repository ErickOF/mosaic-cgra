`timescale 1ns / 1ps
// Reuse the common parity and shortened Hamming codecs, striped at 256 data
// bits. Geometry is validated by the parent. More than one corrected stripe is
// a whole-record integrity failure, rather than an unreported multi-bit repair.
module tile_shell_codec #(
    parameter int WIDTH = 32,
    parameter int PROTECTION = 0,
    localparam int STRIPES = (WIDTH + 255) / 256,
    localparam int LAST = WIDTH - (STRIPES - 1) * 256,
    localparam int CODE = ecc_pkg::code_width(WIDTH, PROTECTION)
) (
    input logic [WIDTH-1:0] i_data,
    output wire [CODE-1:0] o_code,
    input logic [CODE-1:0] i_code,
    output wire [WIDTH-1:0] o_data,
    output wire o_corrected,
    output wire o_bad
);
    if (PROTECTION == 2) begin : g_secded
        wire [STRIPES-1:0] corrected;
        wire [STRIPES-1:0] bad;

        for (genvar s = 0; s < STRIPES; s++) begin : g_stripe
            localparam int BITS = s == STRIPES - 1 ? LAST : 256;
            localparam int STORED = BITS + ecc_pkg::hamming_bits(BITS) + 1;

            ecc #(.DATA_WIDTH(BITS)) u_ecc (
                .i_encode_data(i_data[s*256+:BITS]),
                .o_encoded_codeword(o_code[s*266+:STORED]),
                .i_decode_codeword(i_code[s*266+:STORED]),
                .o_decoded_data(o_data[s*256+:BITS]),
                .o_corrected(corrected[s]),
                .o_uncorrectable(bad[s]),
                .o_corrected_codeword(),
                .o_no_error(),
                .o_scrub_required(),
                .o_error_position_valid(),
                .o_error_position(),
                .o_syndrome(),
                .o_overall_parity_error()
            );
        end

        assign o_bad = ((|bad) !== 1'b0) || $countones(corrected) > 1 || (^ o_data === 1'bx);
        assign o_corrected = !o_bad && (|corrected);
    end else if (PROTECTION == 1) begin : g_parity
        wire generated;
        wire error_bit;

        parity #(.DATA_WIDTH(WIDTH), .PARITY_GRANULE_WIDTH(WIDTH)) u_parity (
            .i_generate_data(i_data),
            .o_generated_parity(generated),
            .i_check_data(i_code[WIDTH-1:0]),
            .i_check_parity(i_code[WIDTH]),
            .o_error_vector(error_bit),
            .o_checked_data(),
            .o_granule_valid(),
            .o_no_error(),
            .o_any_error()
        );

        assign o_code = {generated, i_data};
        assign o_data = i_code[WIDTH-1:0];
        assign o_corrected = 1'b0;
        assign o_bad = error_bit !== 1'b0;
    end else begin : g_plain
        assign o_code = i_data;
        assign o_data = i_code;
        assign o_corrected = 1'b0;
        assign o_bad = ^ i_code === 1'bx;
    end
endmodule
