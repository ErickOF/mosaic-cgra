`timescale 1ns / 1ps
`default_nettype none

// Reduction opcodes extend the repository's integer-vector operation inventory.
// Result formats reuse the existing vector package rather than redefining values.
package vector_reduction_pkg;
    typedef enum logic [2:0] {
        VRED_SUM = 3'b000,
        VRED_MIN = 3'b001,
        VRED_MAX = 3'b010,
        VRED_AND = 3'b011,
        VRED_OR = 3'b100
    } vector_reduction_opcode_t;

    typedef vector_lane_pkg::vector_lane_result_format_t vector_reduction_result_format_t;
endpackage
`default_nettype wire
