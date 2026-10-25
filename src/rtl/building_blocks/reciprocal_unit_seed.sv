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
    function automatic logic [DEPTH*WIDTH-1:0] generate_image(input int unused);
        logic [DEPTH*WIDTH-1:0] image_value;
        logic [RATIONAL-1:0] denominator;
        logic [RATIONAL-1:0] quotient;
        logic [RATIONAL-1:0] remainder_value;
        image_value = '0;

        for (int entry = 0; entry < DEPTH; entry++) begin
            denominator = (RATIONAL'(1) << (ADDRESS + 1)) + 2 * RATIONAL'(entry) + 1;
            quotient = (RATIONAL'(1) << (FRACTION + ADDRESS + 2)) / denominator;
            remainder_value = (RATIONAL'(1) << (FRACTION + ADDRESS + 2)) % denominator;

            if (2 * remainder_value > denominator ||
                (2 * remainder_value == denominator && quotient[0]))
                quotient = quotient + 1'b1;

            image_value[entry*WIDTH+:WIDTH] = WIDTH'(quotient);
        end

        return image_value;
    endfunction

    function automatic logic [31:0] image_checksum(input logic [DEPTH*WIDTH-1:0] image_value);
        logic [31:0] hash_value;
        logic [31:0] metadata_value;
        logic [WIDTH-1:0] value;
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
            value = image_value[entry*WIDTH+:WIDTH];

            for (int byte_index = 0; byte_index < (WIDTH + 7) / 8; byte_index++)
                hash_value = (hash_value ^
                    (32'(value >> (8 * byte_index)) & 32'hff)) * 32'h01000193;
        end

        return hash_value;
    endfunction

    localparam logic [DEPTH*WIDTH-1:0] IMAGE = generate_image(0);
    localparam logic [31:0] CHECKSUM = image_checksum(IMAGE);
    localparam logic [31:0] IMAGE_ID = CHECKSUM ^ 32'h52435001;

    protected_seed_rom #(.WIDTH(WIDTH), .ADDRESS(ADDRESS), .PROTECTION(PROTECTION),
        .IMAGE(IMAGE)) u_rom (
        .i_enable(i_enable),
        .i_address(i_address),
        .o_seed(o_seed),
        .o_corrected(o_corrected),
        .o_bad(o_bad)
    );

    assign o_image_id = IMAGE_ID;
    assign o_checksum = CHECKSUM;
endmodule
