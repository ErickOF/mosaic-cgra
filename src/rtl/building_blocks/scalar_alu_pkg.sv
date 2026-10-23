`timescale 1ns / 1ps

// Baseline opcode contract from mosaic-scalar-alu. Keep these encodings shared
// by RTL users; this repository does not require an external contracts package.
package scalar_alu_pkg;
    typedef enum logic [4:0] {
        ALU_ADD = 5'h00,
        ALU_SUB = 5'h01,
        ALU_AND = 5'h02,
        ALU_OR = 5'h03,
        ALU_XOR = 5'h04,
        ALU_NOT = 5'h05,
        ALU_SLL = 5'h06,
        ALU_SRL = 5'h07,
        ALU_SRA = 5'h08,
        ALU_EQ = 5'h09,
        ALU_NE = 5'h0a,
        ALU_LT = 5'h0b,
        ALU_LE = 5'h0c,
        ALU_GT = 5'h0d,
        ALU_GE = 5'h0e,
        ALU_SELECT = 5'h0f,
        ALU_PASS_A = 5'h10,
        ALU_PASS_B = 5'h11,
        ALU_MIN = 5'h12,
        ALU_MAX = 5'h13
    } scalar_alu_opcode_t;
endpackage
