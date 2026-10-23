`timescale 1ns / 1ps
`default_nettype none

// Baseline encodings from the predicate-unit specification. The repository owns
// these values until an external contract package is integrated.
package predicate_unit_pkg;
    typedef enum logic [3:0] {
        PRED_CLEAR = 4'h0,
        PRED_SET = 4'h1,
        PRED_LOAD = 4'h2,
        PRED_PASS_A = 4'h3,
        PRED_NOT_A = 4'h4,
        PRED_AND = 4'h5,
        PRED_OR = 4'h6,
        PRED_XOR = 4'h7,
        PRED_INVALIDATE = 4'h8
    } predicate_opcode_t;
endpackage
`default_nettype wire
