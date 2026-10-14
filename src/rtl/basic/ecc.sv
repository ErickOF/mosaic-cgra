`timescale 1ns / 1ps

// Shortened extended Hamming SECDED. Conceptual position u occupies bit u-1;
// the overall even-parity bit is above the Hamming field. Both cones are independent.
module ecc #(
    // The implementation cap bounds elaboration and validated XOR-tree sizes.
    // Preserve negative, oversized and X/Z arguments until the guard rejects them.
    parameter DATA_WIDTH = 32,
    localparam int unsigned MAX_DATA_WIDTH = 256,
    localparam int unsigned DATA_BITS = (^DATA_WIDTH !== 1'bx) && DATA_WIDTH >= 1 && DATA_WIDTH <= MAX_DATA_WIDTH ? DATA_WIDTH : 1,
    localparam int unsigned HAMMING_PARITY_BITS = parity_bits(DATA_BITS),
    localparam int unsigned HAMMING_WIDTH = DATA_BITS + HAMMING_PARITY_BITS,
    localparam int unsigned CODE_WIDTH = HAMMING_WIDTH + 1,
    localparam int unsigned POSITION_WIDTH = CODE_WIDTH > 1 ? $clog2(CODE_WIDTH) : 1
) (
    input  logic [DATA_BITS-1:0] i_encode_data,
    output logic [CODE_WIDTH-1:0] o_encoded_codeword,
    input  logic [CODE_WIDTH-1:0] i_decode_codeword,
    output logic [DATA_BITS-1:0] o_decoded_data,
    output logic [CODE_WIDTH-1:0] o_corrected_codeword,
    output logic o_no_error,
    output logic o_corrected,
    output logic o_uncorrectable,
    output logic o_scrub_required,
    output logic o_error_position_valid,
    output logic [POSITION_WIDTH-1:0] o_error_position,
    output logic [HAMMING_PARITY_BITS-1:0] o_syndrome,
    output logic o_overall_parity_error
);
    // Wide intermediate powers cannot overflow a host-sized 32-bit integer.
    function automatic int unsigned parity_bits(input int unsigned data_width);
        logic [63:0] capacity;
        int unsigned count;
        capacity = 64'd2;
        count = 1;
        while (capacity < 64'(data_width) + 64'(count) + 64'd1) begin
            capacity = capacity << 1;
            count++;
        end
        parity_bits = count;
    endfunction

    function automatic bit is_parity(input int unsigned position);
        is_parity = (position & (position - 32'd1)) == 0;
    endfunction

    function automatic int unsigned data_index(input int unsigned position);
        int unsigned index;
        index = 0;
        for (int unsigned lower = 1; lower < position; lower++) begin
            if ((lower & (lower - 32'd1)) != 0) index++;
        end
        data_index = index;
    endfunction

    function automatic logic [HAMMING_WIDTH-1:0] coverage_mask(input int unsigned parity);
        logic [HAMMING_WIDTH-1:0] mask;
        mask = '0;
        for (int unsigned position = 1; position <= HAMMING_WIDTH; position++) begin
            mask[position-1] = (position & (32'd1 << parity)) != 0;
        end
        coverage_mask = mask;
    endfunction

    if ((^DATA_WIDTH === 1'bx) || DATA_WIDTH < 1 || DATA_WIDTH > MAX_DATA_WIDTH) begin : g_invalid_parameters
        ecc_data_width_must_be_between_1_and_256 invalid_parameters ();
    end else begin : g_codec
        wire [HAMMING_WIDTH-1:0] placed_data;
        wire [HAMMING_WIDTH-1:0] encoded_hamming;
        for (genvar position = 1; position <= HAMMING_WIDTH; position++) begin : g_position
            if (is_parity(position)) begin : g_parity
                assign placed_data[position-1] = 1'b0;
            end else begin : g_data
                localparam int unsigned INDEX = data_index(position);
                assign placed_data[position-1] = i_encode_data[INDEX];
                assign encoded_hamming[position-1] = placed_data[position-1];
                assign o_decoded_data[INDEX] = o_corrected_codeword[position-1];
            end
        end
        for (genvar parity = 0; parity < HAMMING_PARITY_BITS; parity++) begin : g_check
            localparam logic [HAMMING_WIDTH-1:0] MASK = coverage_mask(parity);
            // Static reduction sets permit balanced XOR trees. Received parity
            // participates in syndrome checks; encode parity positions start at zero.
            assign encoded_hamming[(32'd1 << parity)-1] = ^(placed_data & MASK);
            assign o_syndrome[parity] = ^(i_decode_codeword[HAMMING_WIDTH-1:0] & MASK);
        end
        assign o_encoded_codeword = {^encoded_hamming, encoded_hamming};
        assign o_overall_parity_error = ^i_decode_codeword;

        wire syndrome_zero = !(|o_syndrome);
        wire syndrome_in_range = {1'b0, o_syndrome} <= (HAMMING_PARITY_BITS + 1)'(HAMMING_WIDTH);
        // Four-state Boolean expressions preserve ambiguity. No wildcard case
        // or known-value default can turn an unknown received bit into success.
        assign o_no_error = syndrome_zero & !o_overall_parity_error;
        assign o_corrected = o_overall_parity_error & syndrome_in_range;
        assign o_uncorrectable = !syndrome_zero & (!o_overall_parity_error | !syndrome_in_range);
        assign o_scrub_required = o_corrected;
        assign o_error_position_valid = o_corrected;
        wire [POSITION_WIDTH-1:0] correction_position = syndrome_zero ?
            POSITION_WIDTH'(HAMMING_WIDTH) : POSITION_WIDTH'(o_syndrome - 1'b1);
        assign o_error_position = o_corrected ? correction_position : '0;

        wire [CODE_WIDTH-1:0] correction_mask;
        wire unused_correction_select_valid;

        // The reusable decoder bounds the one-hot mask. Its validity output
        // does not classify ECC errors, so unknown selects cannot assert success.
        decoder #(.NUM_OUTPUTS(CODE_WIDTH), .SELECT_WIDTH(POSITION_WIDTH)) u_correction (
            .i_enable(o_corrected),
            .i_select(correction_position),
            .o_decoded(correction_mask),
            .o_select_valid(unused_correction_select_valid)
        );

        operand_isolation #(.WIDTH(CODE_WIDTH)) u_fail_closed (
            .i_data(i_decode_codeword ^ correction_mask),
            .i_isolate(o_uncorrectable),
            .o_data(o_corrected_codeword)
        );
    end
endmodule
