`timescale 1ns / 1ps

// Baseline accumulator encoding from the repository specification. Integrations
// must map these fixed values consistently into their released tile contracts.
package accumulator_pkg;
    typedef enum logic [1:0] {
        ACC_CLEAR = 2'b00,
        ACC_LOAD  = 2'b01,
        ACC_ADD   = 2'b10,
        ACC_SUB   = 2'b11
    } accumulator_command_t;
endpackage
