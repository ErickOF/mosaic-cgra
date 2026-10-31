`timescale 1ns / 1ps

// Immutable generated endpoints. Static SECDED encoding is constant-folded;
// the released common ECC decoder corrects each independently selected endpoint.
module exp_unit_rom #(
    parameter int WIDTH = 24,
    parameter int FRACTION = 20,
    parameter int ADDRESS = 6,
    parameter int PROTECTION = 0,
    localparam int DEPTH = (1 << ADDRESS) + 1,
    localparam int HAMMING = ecc_pkg::hamming_bits(WIDTH),
    localparam int CODE = WIDTH + (PROTECTION == 2 ? HAMMING + 1 : PROTECTION)
) (
    input logic i_enable,
    input logic i_upper_enable,
    input logic [ADDRESS-1:0] i_address,
    output wire [WIDTH-1:0] o_lower,
    output wire [WIDTH-1:0] o_upper,
    output wire o_corrected,
    output wire o_uncorrectable
);

    function automatic logic [CODE-1:0] encode_word(input logic [WIDTH-1:0] data);
        logic [CODE-1:0] codeword;
        int index;
        codeword = '0;
        index = 0;

        if (PROTECTION == 2) begin
            for (int position = 1; position < CODE; position++) begin
                if ((position & (position - 1)) != 0) begin
                    codeword[position-1] = data[index];
                    index++;
                end
            end

            for (int parity_bit = 0; parity_bit < HAMMING; parity_bit++)
                for (int position = 1; position < CODE; position++)
                    if ((position & (1 << parity_bit)) != 0)
                        codeword[(1<<parity_bit)-1] =
                            codeword[(1<<parity_bit)-1] ^ codeword[position-1];
            codeword[CODE-1] = ^ codeword[CODE-2:0];
        end else if (PROTECTION == 1) codeword = CODE'({ ^ data, data});
        else codeword = CODE'(data);

        return codeword;
    endfunction

    wire [CODE-1:0] table_words[DEPTH];

    for (genvar index = 0; index < DEPTH; index++) begin : g_word
        localparam logic [129:0] GENERATED =
            exp_unit_tables_pkg::table_value(index, ADDRESS, FRACTION);
        localparam logic [WIDTH-1:0] VALUE = WIDTH'(GENERATED);
        wire [CODE-1:0] stored_codeword = encode_word(VALUE);
        assign table_words[index] = stored_codeword;
    end

    wire [CODE-1:0] received[2];
    wire [WIDTH-1:0] checked[2];
    wire [1:0] corrected;
    wire [1:0] bad;
    assign received[0] = i_enable ? table_words[{1'b0, i_address}] : '0;
    assign received[1] = i_enable && i_upper_enable ?
        table_words[{1'b0, i_address} + 1'b1] : '0;

    for (genvar port_index = 0; port_index < 2; port_index++) begin : g_read
        if (PROTECTION == 2) begin : g_ecc
            wire [CODE-1:0] unused_encoded;
            wire [CODE-1:0] unused_corrected_codeword;
            wire unused_no_error;
            wire unused_scrub;
            wire unused_position_valid;
            wire [$clog2(CODE)-1:0] unused_position;
            wire [HAMMING-1:0] unused_syndrome;
            wire unused_overall;

            ecc #(.DATA_WIDTH(WIDTH)) u_decode (
                .i_encode_data({WIDTH{1'b0}}),
                .o_encoded_codeword(unused_encoded),
                .i_decode_codeword(received[port_index]),
                .o_decoded_data(checked[port_index]),
                .o_corrected_codeword(unused_corrected_codeword),
                .o_no_error(unused_no_error),
                .o_corrected(corrected[port_index]),
                .o_uncorrectable(bad[port_index]),
                .o_scrub_required(unused_scrub),
                .o_error_position_valid(unused_position_valid),
                .o_error_position(unused_position),
                .o_syndrome(unused_syndrome),
                .o_overall_parity_error(unused_overall)
            );
        end else if (PROTECTION == 1) begin : g_parity
            wire unused_generated;
            wire [WIDTH-1:0] unused_checked;
            wire unused_valid;
            wire unused_no_error;
            wire unused_any_error;

            parity #(.DATA_WIDTH(WIDTH), .PARITY_GRANULE_WIDTH(WIDTH)) u_check (
                .i_generate_data({WIDTH{1'b0}}),
                .i_check_data(received[port_index][WIDTH-1:0]),
                .i_check_parity(received[port_index][WIDTH]),
                .o_generated_parity(unused_generated),
                .o_checked_data(unused_checked),
                .o_error_vector(bad[port_index]),
                .o_granule_valid(unused_valid),
                .o_no_error(unused_no_error),
                .o_any_error(unused_any_error)
            );

            assign checked[port_index] = received[port_index][WIDTH-1:0];
            assign corrected[port_index] = 1'b0;
        end else begin : g_unprotected
            assign checked[port_index] = received[port_index];
            assign corrected[port_index] = 1'b0;
            assign bad[port_index] = 1'b0;
        end
    end

    assign o_lower = checked[0];
    assign o_upper = checked[1];
    assign o_corrected = i_enable && ((corrected[0] === 1'b1) ||
        (i_upper_enable && corrected[1] === 1'b1));
    assign o_uncorrectable = i_enable && ((bad[0] !== 1'b0) ||
        ( ^ checked[0] === 1'bx) || (i_upper_enable &&
        ((bad[1] !== 1'b0) || ( ^ checked[1] === 1'bx))));
endmodule
