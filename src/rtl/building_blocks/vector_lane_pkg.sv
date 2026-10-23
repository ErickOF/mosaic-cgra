`timescale 1ns / 1ps
`default_nettype none

// The lane shares the scalar ALU's baseline encodings and adds two operations.
// Parameter-dependent response records stay in vector_lane.sv.
package vector_lane_pkg;
    typedef enum logic [4:0] {
        VLANE_ADD = scalar_alu_pkg::ALU_ADD,
        VLANE_SUB = scalar_alu_pkg::ALU_SUB,
        VLANE_AND = scalar_alu_pkg::ALU_AND,
        VLANE_OR = scalar_alu_pkg::ALU_OR,
        VLANE_XOR = scalar_alu_pkg::ALU_XOR,
        VLANE_NOT = scalar_alu_pkg::ALU_NOT,
        VLANE_SLL = scalar_alu_pkg::ALU_SLL,
        VLANE_SRL = scalar_alu_pkg::ALU_SRL,
        VLANE_SRA = scalar_alu_pkg::ALU_SRA,
        VLANE_EQ = scalar_alu_pkg::ALU_EQ,
        VLANE_NE = scalar_alu_pkg::ALU_NE,
        VLANE_LT = scalar_alu_pkg::ALU_LT,
        VLANE_LE = scalar_alu_pkg::ALU_LE,
        VLANE_GT = scalar_alu_pkg::ALU_GT,
        VLANE_GE = scalar_alu_pkg::ALU_GE,
        VLANE_SELECT = scalar_alu_pkg::ALU_SELECT,
        VLANE_PASS_A = scalar_alu_pkg::ALU_PASS_A,
        VLANE_PASS_B = scalar_alu_pkg::ALU_PASS_B,
        VLANE_MIN = scalar_alu_pkg::ALU_MIN,
        VLANE_MAX = scalar_alu_pkg::ALU_MAX,
        VLANE_MUL = 5'h14,
        VLANE_MAC = 5'h15
    } vector_lane_opcode_t;

    typedef enum logic [1:0] {
        VLANE_RESULT_BOOLEAN = 2'b00,
        VLANE_RESULT_ELEMENT = 2'b01,
        VLANE_RESULT_PRODUCT = 2'b10,
        VLANE_RESULT_ACCUMULATOR = 2'b11
    } vector_lane_result_format_t;
endpackage
`default_nettype wire
