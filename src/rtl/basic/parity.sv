`timescale 1ns / 1ps

// Independent combinational generation/checking of even parity per granule.
module parity #(
    parameter DATA_WIDTH = 32,
    parameter PARITY_GRANULE_WIDTH = 8,
    // Preserve invalid arguments for an elaboration guard without bad slices.
    localparam bit PARAMETERS_VALID =
        ((DATA_WIDTH >= 1) === 1'b1) && (^DATA_WIDTH !== 1'bx) &&
        ((PARITY_GRANULE_WIDTH >= 1) === 1'b1) && (^PARITY_GRANULE_WIDTH !== 1'bx) &&
        (((PARITY_GRANULE_WIDTH >= 1) === 1'b1) ?
            ((DATA_WIDTH % PARITY_GRANULE_WIDTH == 0) === 1'b1) : 1'b0),
    localparam int unsigned DATA_BITS = PARAMETERS_VALID ? DATA_WIDTH : 1,
    localparam int unsigned GRANULE_BITS = PARAMETERS_VALID ? PARITY_GRANULE_WIDTH : 1,
    localparam int unsigned PARITY_WIDTH = DATA_BITS / GRANULE_BITS,
    localparam int unsigned CODE_WIDTH = DATA_BITS + PARITY_WIDTH
) (
    input  logic [DATA_BITS-1:0]    i_generate_data,
    output logic [PARITY_WIDTH-1:0] o_generated_parity,
    input  logic [DATA_BITS-1:0]    i_check_data,
    input  logic [PARITY_WIDTH-1:0] i_check_parity,
    output logic [DATA_BITS-1:0]    o_checked_data,
    output logic [PARITY_WIDTH-1:0] o_error_vector,
    output logic [PARITY_WIDTH-1:0] o_granule_valid,
    output logic                    o_no_error,
    output logic                    o_any_error
);
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        parity_parameters_must_be_valid invalid_parameters ();
    end else begin : g_parity
        // Canonical packed storage form: data low, sidecar parity high.
        wire [CODE_WIDTH-1:0] received_codeword = {i_check_parity, i_check_data};
        // Granule zero is the low data slice and low parity bit. Reduction
        // operators permit balanced XOR trees without procedural accumulators.
        for (genvar granule = 0; granule < PARITY_WIDTH; granule++) begin : g_granule
            assign o_generated_parity[granule] = ^i_generate_data[granule*GRANULE_BITS+:GRANULE_BITS];
            assign o_error_vector[granule] =
                (^received_codeword[granule*GRANULE_BITS+:GRANULE_BITS]) ^ received_codeword[DATA_BITS+granule];
        end
        assign o_granule_valid = ~o_error_vector;
        assign o_any_error = |o_error_vector;
        assign o_no_error = !o_any_error;

        // One failed granule invalidates the compound word. This primitive
        // also preserves uncertainty instead of sanitizing an unknown check.
        operand_isolation #(.WIDTH(DATA_BITS)) u_checked_data (
            .i_data(i_check_data),
            .i_isolate(o_any_error),
            .o_data(o_checked_data)
        );
    end
endmodule
