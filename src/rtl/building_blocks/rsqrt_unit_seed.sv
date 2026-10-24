`timescale 1ns / 1ps

// Parameterized two-parity seed image. Constant integer comparisons implement
// correctly rounded sqrt(2**(2*F+A+1-parity) / denominator) at elaboration only.
// The release image is independently generated with pinned MPFR arithmetic.
module rsqrt_unit_seed #(
    parameter int WIDTH = 28,
    parameter int FRACTION = 22,
    parameter int MANTISSA_ADDRESS = 6,
    parameter int PROTECTION = 0,
    localparam int ADDRESS = MANTISSA_ADDRESS + 1,
    localparam int DEPTH = 1 << ADDRESS,
    localparam int WIDE = 2 * WIDTH + MANTISSA_ADDRESS + 5
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
        logic [WIDE-1:0] numerator;
        logic [WIDE-1:0] denominator;
        logic [WIDE-1:0] squared;
        logic [WIDE-1:0] midpoint;
        logic [WIDTH-1:0] root_value;
        logic [WIDTH-1:0] candidate;
        int region;
        int parity_value;
        image_value = '0;

        for (int entry = 0; entry < DEPTH; entry++) begin
            parity_value = entry >> MANTISSA_ADDRESS;
            region = entry & ((1 << MANTISSA_ADDRESS) - 1);
            denominator = (WIDE'(1) << (MANTISSA_ADDRESS + 1)) + 2 * WIDE'(region) + 1;
            numerator = WIDE'(1) << (2 * FRACTION + MANTISSA_ADDRESS + 1 - parity_value);
            root_value = '0;

            for (int position = WIDTH - 1; position >= 0; position--) begin
                candidate = root_value | (WIDTH'(1) << position);
                squared = WIDE'(candidate) * WIDE'(candidate);
                if (squared * denominator <= numerator)
                    root_value = candidate;
            end

            midpoint = 2 * WIDE'(root_value) + 1;
            squared = midpoint * midpoint * denominator;

            if ((4 * numerator > squared) || (4 * numerator == squared && root_value[0]))
                root_value = root_value + 1'b1;
            image_value[entry*WIDTH+:WIDTH] = root_value;
        end

        return image_value;
    endfunction

    // Same byte order and checksum as the reciprocal ROM, with the mantissa
    // address width in metadata and a distinct inverse-square-root image namespace.
    function automatic logic [31:0] image_checksum(
        input logic [DEPTH*WIDTH-1:0] image_value
    );
        logic [31:0] hash_value;
        logic [31:0] metadata_value;
        logic [WIDTH-1:0] value;
        hash_value = 32'h811c9dc5;

        for (int field_index = 0; field_index < 4; field_index++) begin
            case (field_index)
                0: metadata_value = 1;
                1: metadata_value = WIDTH;
                2: metadata_value = FRACTION;
                default: metadata_value = MANTISSA_ADDRESS;
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
    localparam logic [31:0] IMAGE_ID = CHECKSUM ^ 32'h52535101;

    protected_seed_rom #(
        .WIDTH(WIDTH),
        .ADDRESS(ADDRESS),
        .PROTECTION(PROTECTION),
        .IMAGE(IMAGE)
    ) u_rom (
        .i_enable(i_enable),
        .i_address(i_address),
        .o_seed(o_seed),
        .o_corrected(o_corrected),
        .o_bad(o_bad)
    );

    assign o_image_id = IMAGE_ID;
    assign o_checksum = CHECKSUM;
endmodule
