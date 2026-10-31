`timescale 1ns / 1ps

// Stripe a complete record through the released SECDED codec. A separate masked
// ownership copy distinguishes payload-only double faults from unsafe ownership
// faults. Two corrected stripes count as a whole-record uncorrectable error.
module noc_router_codec #(
    parameter int WIDTH = 32,
    parameter int PROTECTION = 0,
    parameter logic [WIDTH-1:0] OWNERSHIP_MASK = '1,
    localparam int STRIPES = (WIDTH + 255) / 256,
    localparam int LAST = WIDTH - (STRIPES - 1) * 256,
    localparam int MAIN = (STRIPES - 1) * 266 + LAST + ecc_pkg::hamming_bits(LAST) + 1,
    localparam int CODE = PROTECTION == 2 ? MAIN + WIDTH + 1 : WIDTH + PROTECTION
) (
    input logic [WIDTH-1:0] i_encode,
    output wire [CODE-1:0] o_encoded,
    input logic [CODE-1:0] i_decode,
    output wire [WIDTH-1:0] o_decoded,
    output wire o_corrected,
    output wire o_uncorrectable,
    output wire o_ownership_error
);
    if (PROTECTION == 2) begin : g_ecc
        wire [STRIPES-1:0] corrected;
        wire [STRIPES-1:0] bad;
        wire [WIDTH-1:0] shadow = i_decode[MAIN+:WIDTH];
        wire shadow_parity = i_decode[MAIN+WIDTH];
        assign o_encoded[MAIN+:WIDTH] = i_encode & OWNERSHIP_MASK;
        assign o_encoded[MAIN+WIDTH] = ^ (i_encode & OWNERSHIP_MASK);
        assign o_uncorrectable = (|bad) || $countones(corrected) > 1;
        assign o_corrected = (|corrected) && !o_uncorrectable;
        assign o_ownership_error = ( ^ {shadow_parity, shadow} !== 1'b0) ||
            (((o_decoded ^ shadow) & OWNERSHIP_MASK) !== {WIDTH{1'b0}});

        for (genvar stripe = 0; stripe < STRIPES; stripe++) begin : g_stripe
            localparam int BITS = stripe == STRIPES - 1 ? LAST : 256;
            localparam int H = ecc_pkg::hamming_bits(BITS);
            localparam int C = BITS + H + 1;
            wire [C-1:0] unused_codeword;
            wire [BITS-1:0] corrected_data;
            wire [BITS-1:0] raw_data;

            // The released ECC decoder clamps uncorrectable data. Recover only
            // the raw record bits for ownership-copy comparison and error-marked
            // payload forwarding; never treat those bits as a successful decode.
            for (genvar position = 1; position < C; position++) begin : g_raw
                if ((position & (position - 1)) != 0) begin : g_data
                    localparam int INDEX = ecc_pkg::data_index(position);
                    assign raw_data[INDEX] = i_decode[stripe*266+position-1];
                end
            end

            assign o_decoded[stripe*256+:BITS] = bad[stripe] ? raw_data : corrected_data;
            wire unused_no_error;
            wire unused_scrub;
            wire unused_position_valid;
            wire [$clog2(C)-1:0] unused_position;
            wire [H-1:0] unused_syndrome;
            wire unused_overall;

            ecc #(.DATA_WIDTH(BITS)) u_ecc (
                .i_encode_data(i_encode[stripe*256+:BITS]),
                .o_encoded_codeword(o_encoded[stripe*266+:C]),
                .i_decode_codeword(i_decode[stripe*266+:C]),
                .o_decoded_data(corrected_data),
                .o_corrected_codeword(unused_codeword),
                .o_no_error(unused_no_error),
                .o_corrected(corrected[stripe]),
                .o_uncorrectable(bad[stripe]),
                .o_scrub_required(unused_scrub),
                .o_error_position_valid(unused_position_valid),
                .o_error_position(unused_position),
                .o_syndrome(unused_syndrome),
                .o_overall_parity_error(unused_overall)
            );
        end
    end else if (PROTECTION == 1) begin : g_parity
        wire generated;
        wire error_bit;
        wire unused_valid;
        wire unused_no_error;
        wire unused_any_error;
        assign o_encoded = {generated, i_encode};
        assign o_corrected = 1'b0;
        assign o_uncorrectable = error_bit !== 1'b0;
        assign o_ownership_error = o_uncorrectable;

        parity #(.DATA_WIDTH(WIDTH), .PARITY_GRANULE_WIDTH(WIDTH)) u_parity (
            .i_generate_data(i_encode),
            .o_generated_parity(generated),
            .i_check_data(i_decode[WIDTH-1:0]),
            .i_check_parity(i_decode[WIDTH]),
            .o_checked_data(o_decoded),
            .o_error_vector(error_bit),
            .o_granule_valid(unused_valid),
            .o_no_error(unused_no_error),
            .o_any_error(unused_any_error)
        );
    end else begin : g_plain
        assign o_encoded = i_encode;
        assign o_decoded = i_decode;
        assign o_corrected = 1'b0;
        assign o_uncorrectable = 1'b0;
        assign o_ownership_error = 1'b0;
    end
endmodule
