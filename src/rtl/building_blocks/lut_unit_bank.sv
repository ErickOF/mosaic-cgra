`timescale 1ns / 1ps

// Inferred unreset codeword storage, one write port and two isolated read ports.
// SECDED stripes reuse the released codec without imposing its 256-bit width cap
// on the architectural table entry. Correction is on read; there is no auto-scrub.
module lut_unit_bank #(
    parameter int ADDRESS = 4,
    parameter int WIDTH = 16,
    parameter int PROTECTION = 0,
    localparam int DEPTH = 1 << ADDRESS,
    localparam int STRIPES = (WIDTH + 255) / 256,
    localparam int LAST = WIDTH - (STRIPES - 1) * 256,
    localparam int CODE = ecc_pkg::code_width(WIDTH, PROTECTION)
) (
    input logic i_clk,
    input logic i_write,
    input logic [ADDRESS-1:0] i_write_address,
    input logic [WIDTH-1:0] i_write_data,
    input logic [1:0] i_read,
    input logic [ADDRESS-1:0] i_lower_address,
    input logic [ADDRESS-1:0] i_upper_address,
    output wire [WIDTH-1:0] o_lower,
    output wire [WIDTH-1:0] o_upper,
    output wire [1:0] o_corrected,
    output wire [1:0] o_bad
);
    logic [CODE-1:0] memory[DEPTH];
    wire [CODE-1:0] encoded;
    wire [CODE-1:0] received[2];
    wire [WIDTH-1:0] decoded[2];
    wire [WIDTH-1:0] write_data = i_write ? i_write_data : '0;
    assign received[0] = i_read[0] ? memory[i_lower_address] : '0;
    assign received[1] = i_read[1] ? memory[i_upper_address] : '0;
    assign o_lower = decoded[0];
    assign o_upper = decoded[1];

    always_ff @(posedge i_clk) begin
        if (i_write)
            memory[i_write_address] <= encoded;
    end

    if (PROTECTION == 2) begin : g_secded
        wire [STRIPES-1:0] corrections[2];
        wire [STRIPES-1:0] errors[2];

        for (genvar port_index = 0; port_index < 2; port_index++) begin : g_port
            for (genvar stripe = 0; stripe < STRIPES; stripe++) begin : g_stripe
                localparam int BITS = stripe == STRIPES - 1 ? LAST : 256;
                localparam int HAMMING = ecc_pkg::hamming_bits(BITS);
                localparam int STORED = BITS + HAMMING + 1;
                wire [STORED-1:0] unused_encoded;
                wire [STORED-1:0] unused_corrected;
                wire unused_no_error;
                wire unused_scrub;
                wire unused_position_valid;
                wire [$clog2(STORED)-1:0] unused_position;
                wire [HAMMING-1:0] unused_syndrome;
                wire unused_overall;
                wire [BITS-1:0] encode_data;

                if (port_index == 0) begin : g_encoder
                    assign encode_data = write_data[stripe*256+:BITS];
                    assign encoded[stripe*266+:STORED] = unused_encoded;
                end else begin : g_no_encoder
                    assign encode_data = '0;
                end

                ecc #(.DATA_WIDTH(BITS)) u_ecc (
                    .i_encode_data(encode_data),
                    .o_encoded_codeword(unused_encoded),
                    .i_decode_codeword(received[port_index][stripe*266+:STORED]),
                    .o_decoded_data(decoded[port_index][stripe*256+:BITS]),
                    .o_corrected_codeword(unused_corrected),
                    .o_no_error(unused_no_error),
                    .o_corrected(corrections[port_index][stripe]),
                    .o_uncorrectable(errors[port_index][stripe]),
                    .o_scrub_required(unused_scrub),
                    .o_error_position_valid(unused_position_valid),
                    .o_error_position(unused_position),
                    .o_syndrome(unused_syndrome),
                    .o_overall_parity_error(unused_overall)
                );
            end

            // Multiple corrected stripes are an uncorrectable whole-entry fault.
            assign o_corrected[port_index] = i_read[port_index] &&!o_bad[port_index] &&
                ((|corrections[port_index]) === 1'b1);
            assign o_bad[port_index] = i_read[port_index] &&
                (((|errors[port_index]) !== 1'b0) ||
                ($countones(corrections[port_index]) > 1) ||
                ( ^ decoded[port_index] === 1'bx));
        end
    end else if (PROTECTION == 1) begin : g_parity
        wire unused_encoded;
        assign encoded = {unused_encoded, write_data};

        for (genvar port_index = 0; port_index < 2; port_index++) begin : g_port
            wire unused_parity_value;
            wire error_bit;
            wire [WIDTH-1:0] unused_checked;
            wire unused_valid;
            wire unused_no_error;
            wire unused_any_error;

            parity #(.DATA_WIDTH(WIDTH), .PARITY_GRANULE_WIDTH(WIDTH)) u_parity (
                .i_generate_data(write_data),
                .o_generated_parity(unused_parity_value),
                .i_check_data(received[port_index][WIDTH-1:0]),
                .i_check_parity(received[port_index][WIDTH]),
                .o_checked_data(unused_checked),
                .o_error_vector(error_bit),
                .o_granule_valid(unused_valid),
                .o_no_error(unused_no_error),
                .o_any_error(unused_any_error)
            );

            if (port_index == 0) begin : g_encoder
                assign unused_encoded = unused_parity_value;
            end

            assign decoded[port_index] = received[port_index][WIDTH-1:0];
            assign o_corrected[port_index] = 1'b0;
            assign o_bad[port_index] = i_read[port_index] && (error_bit !== 1'b0);
        end
    end else begin : g_plain
        assign encoded = write_data;

        for (genvar port_index = 0; port_index < 2; port_index++) begin : g_port
            assign decoded[port_index] = received[port_index];
            assign o_corrected[port_index] = 1'b0;
            assign o_bad[port_index] = i_read[port_index] &&
                ( ^ received[port_index] === 1'bx);
        end
    end
endmodule
