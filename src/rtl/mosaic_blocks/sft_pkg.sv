`timescale 1ns / 1ps
`default_nettype none
// Repository-local v1 ABI. Native FU opcodes retain their released encodings.
package sft_pkg;
    typedef enum logic [3:0] {
        SFT_ALU = 4'd0,
        SFT_MULTIPLY = 4'd1,
        SFT_LUT = 4'd2,
        SFT_POLYNOMIAL = 4'd3,
        SFT_RECIPROCAL = 4'd4,
        SFT_RSQRT = 4'd5,
        SFT_EXP = 4'd6,
        SFT_REDUCE = 4'd7,
        SFT_FORMAT = 4'd8,
        SFT_ACCUMULATOR = 4'd9
    } operation_t;

    typedef enum logic [2:0] {
        SFT_INPUT_A,
        SFT_INPUT_B,
        SFT_RF_A,
        SFT_RF_B,
        SFT_ACC,
        SFT_PREVIOUS,
        SFT_IMMEDIATE,
        SFT_ZERO
    } source_t;

    typedef enum logic [2:0] {
        REDUCE_BEAT,
        REDUCE_CLEAR,
        REDUCE_BEGIN,
        REDUCE_UPDATE,
        REDUCE_END,
        REDUCE_READ
    } reduction_phase_t;

    typedef enum logic [1:0] {
        REDUCE_SUM,
        REDUCE_SUMSQ,
        REDUCE_MIN,
        REDUCE_MAX
    } reduction_op_t;

    typedef enum logic [2:0] {
        ENGINE_IDLE,
        ENGINE_DISPATCH,
        ENGINE_WAIT,
        ENGINE_RETIRE
    } engine_phase_t;

    typedef enum logic [2:0] {
        PROGRAM_IDLE,
        PROGRAM_INVALIDATE,
        PROGRAM_WRITE,
        PROGRAM_COMMIT,
        PROGRAM_RESPONSE,
        PROGRAM_DONE
    } program_phase_t;

    typedef enum logic [7:0] {
        SFT_OK = 8'd0,
        SFT_ERR_CONTEXT = 8'd80,
        SFT_ERR_SOURCE = 8'd81,
        SFT_ERR_CANONICAL = 8'd82,
        SFT_ERR_STATE = 8'd83,
        SFT_ERR_RANGE = 8'd84,
        SFT_ERR_INTEGRITY = 8'd85,
        SFT_ERR_RESPONSE = 8'd86,
        SFT_ERR_COUNT = 8'd87
    } error_t;
endpackage
`default_nettype wire
