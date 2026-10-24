`timescale 1ns / 1ps

// Generated constant ROM. Elaboration evaluates integer rational midpoints;
// there are no real numbers, runtime dividers, initialization files or writes.
// Each SECDED stripe reuses the repository codec. The ROM identity is hardwired.
module reciprocal_unit_seed #(
    parameter int WIDTH = 24,
    parameter int FRACTION = 20,
    parameter int ADDRESS = 6,
    parameter int PROTECTION = 0,
    localparam int DEPTH = 1 << ADDRESS,
    localparam int STRIPES = (WIDTH + 255) / 256,
    localparam int LAST = WIDTH - (STRIPES - 1) * 256,
    localparam int CODE = PROTECTION == 2 ?
        (STRIPES - 1) * 266 + LAST + parity_bits(LAST) + 1 : WIDTH + PROTECTION,
    localparam int RATIONAL = FRACTION + ADDRESS + 4
) (
    input logic i_enable,
    input logic [ADDRESS-1:0] i_address,
    output wire [WIDTH-1:0] o_seed,
    output wire o_corrected,
    output wire o_bad,
    output wire [31:0] o_image_id,
    output wire [31:0] o_checksum
);
    function automatic int parity_bits(input int width);
        int count;
        count = 1;

        while ((64'd1 << count) < 64'(width) + 64'(count) + 1)
            count++;

        return count;
    endfunction

    function automatic logic [WIDTH-1:0] seed_value(input int address_value);
        logic [RATIONAL-1:0] numerator;
        logic [RATIONAL-1:0] denominator;
        logic [RATIONAL-1:0] quotient;
        logic [RATIONAL-1:0] remainder_value;
        numerator = RATIONAL'(1) << (FRACTION + ADDRESS + 2);
        denominator = (RATIONAL'(1) << (ADDRESS + 1)) +
            2 * RATIONAL'(address_value) + 1;
        quotient = numerator / denominator;
        remainder_value = numerator % denominator;

        if ((2 * remainder_value > denominator) ||
            (2 * remainder_value == denominator && quotient[0]))
            quotient = quotient + 1'b1;

        return WIDTH'(quotient);
    endfunction

    // FNV-1a over little-endian u32 generator version, W, F, A, followed by
    // little-endian seed words of ceil(W/8) bytes. Python independently regenerates it.
    function automatic logic [31:0] image_checksum(input int unused);
        logic [31:0] hash_value;
        logic [31:0] metadata_value;
        logic [WIDTH-1:0] value;
        logic [RATIONAL-1:0] denominator;
        logic [RATIONAL-1:0] quotient;
        logic [RATIONAL-1:0] remainder_value;
        hash_value = 32'h811c9dc5;

        for (int field_index = 0; field_index < 4; field_index++) begin
            case (field_index)
                0: metadata_value = 1;
                1: metadata_value = WIDTH;
                2: metadata_value = FRACTION;
                default: metadata_value = ADDRESS;
            endcase

            for (int byte_index = 0; byte_index < 4; byte_index++)
                hash_value = (hash_value ^
                    ((metadata_value >> (8 * byte_index)) & 32'hff)) * 32'h01000193;
        end

        for (int entry = 0; entry < DEPTH; entry++) begin
            denominator = (RATIONAL'(1) << (ADDRESS + 1)) + 2 * RATIONAL'(entry) + 1;
            quotient = (RATIONAL'(1) << (FRACTION + ADDRESS + 2)) / denominator;
            remainder_value = (RATIONAL'(1) << (FRACTION + ADDRESS + 2)) % denominator;

            if (2 * remainder_value > denominator ||
                (2 * remainder_value == denominator && quotient[0]))
                quotient = quotient + 1'b1;

            value = WIDTH'(quotient);

            for (int byte_index = 0; byte_index < (WIDTH + 7) / 8; byte_index++)
                hash_value = (hash_value ^
                    (32'(value >> (8 * byte_index)) & 32'hff)) * 32'h01000193;
        end

        return hash_value;
    endfunction

    function automatic logic [CODE-1:0] encode(input logic [WIDTH-1:0] value);
        logic [CODE-1:0] result;
        logic parity_value;
        int bits_count;
        int checks;
        int stored;
        int data_index;
        int offset;
        result = '0;

        if (PROTECTION == 2) begin
            for (int stripe = 0; stripe < STRIPES; stripe++) begin
                bits_count = stripe == STRIPES - 1 ? LAST : 256;
                checks = parity_bits(bits_count);
                stored = bits_count + checks;
                offset = stripe * 266;
                data_index = stripe * 256;

                for (int position = 1; position <= stored; position++) begin
                    if ((position & (position - 1)) != 0) begin
                        result[offset+position-1] = value[data_index];
                        data_index++;
                    end
                end

                for (int check = 0; check < checks; check++) begin
                    parity_value = 1'b0;

                    for (int position = 1; position <= stored; position++)
                        if ((position & (1 << check)) != 0)
                            parity_value = parity_value ^ result[offset+position-1];

                    result[offset+(1<<check)-1] = parity_value;
                end

                parity_value = 1'b0;

                for (int position = 0; position < stored; position++)
                    parity_value = parity_value ^ result[offset+position];

                result[offset+stored] = parity_value;
            end
        end else begin
            result[WIDTH-1:0] = value;

            if (PROTECTION == 1)
                result[CODE-1] = ^ value;
        end
        return result;
    endfunction

    localparam logic [31:0] CHECKSUM = image_checksum(0);
    localparam logic [31:0] IMAGE_ID = CHECKSUM ^ 32'h52435001;
    wire [DEPTH-1:0][CODE-1:0] table_data;

    for (genvar entry = 0; entry < DEPTH; entry++) begin : g_word
        wire [CODE-1:0] codeword = encode(seed_value(entry));
        assign table_data[entry] = codeword;
    end

    wire [CODE-1:0] received;
    wire select_valid;
    mux #(.NUM_INPUTS(DEPTH), .DATA_WIDTH(CODE), .SEL_WIDTH(ADDRESS)) u_select (
        .i_data(table_data),
        .i_select(i_enable ? i_address : '0),
        .o_data(received),
        .o_select_valid(select_valid)
    );

    wire [WIDTH-1:0] decoded;
    wire bad;
    wire corrected;

    if (PROTECTION == 2) begin : g_secded
        wire [STRIPES-1:0] corrections;
        wire [STRIPES-1:0] errors;

        for (genvar stripe = 0; stripe < STRIPES; stripe++) begin : g_stripe
            localparam int BITS = stripe == STRIPES - 1 ? LAST : 256;
            localparam int HAMMING = parity_bits(BITS);
            localparam int STORED = BITS + HAMMING + 1;
            wire [STORED-1:0] unused_encoded;
            wire [STORED-1:0] unused_corrected;
            wire unused_no_error;
            wire unused_scrub;
            wire unused_position_valid;
            wire [$clog2(STORED)-1:0] unused_position;
            wire [HAMMING-1:0] unused_syndrome;
            wire unused_overall;

            ecc #(.DATA_WIDTH(BITS)) u_ecc (
                .i_encode_data('0),
                .o_encoded_codeword(unused_encoded),
                .i_decode_codeword(received[stripe*266+:STORED]),
                .o_decoded_data(decoded[stripe*256+:BITS]),
                .o_corrected_codeword(unused_corrected),
                .o_no_error(unused_no_error),
                .o_corrected(corrections[stripe]),
                .o_uncorrectable(errors[stripe]),
                .o_scrub_required(unused_scrub),
                .o_error_position_valid(unused_position_valid),
                .o_error_position(unused_position),
                .o_syndrome(unused_syndrome),
                .o_overall_parity_error(unused_overall)
            );
        end

        assign bad = (|errors) !== 1'b0 || $countones(corrections) > 1;
        assign corrected = !bad && (|corrections);
    end else if (PROTECTION == 1) begin : g_parity
        wire unused_generated;
        wire unused_valid;
        wire unused_no_error;
        wire unused_any_error;
        wire error_bit;

        parity #(.DATA_WIDTH(WIDTH), .PARITY_GRANULE_WIDTH(WIDTH)) u_check (
            .i_generate_data('0),
            .o_generated_parity(unused_generated),
            .i_check_data(received[WIDTH-1:0]),
            .i_check_parity(received[WIDTH]),
            .o_checked_data(decoded),
            .o_error_vector(error_bit),
            .o_granule_valid(unused_valid),
            .o_no_error(unused_no_error),
            .o_any_error(unused_any_error)
        );

        assign bad = error_bit !== 1'b0;
        assign corrected = 1'b0;
    end else begin : g_plain
        assign decoded = received;
        assign bad = ^ received === 1'bx;
        assign corrected = 1'b0;
    end

    assign o_seed = i_enable && !o_bad ? decoded : '0;
    assign o_bad = i_enable && (bad || !select_valid || ^ decoded === 1'bx);
    assign o_corrected = i_enable && !o_bad && corrected;
    assign o_image_id = IMAGE_ID;
    assign o_checksum = CHECKSUM;
endmodule
