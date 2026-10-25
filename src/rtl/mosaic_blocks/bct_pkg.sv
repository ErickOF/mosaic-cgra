`timescale 1ns / 1ps
`default_nettype none

// Repository-local BCT v1 encodings. Scalar opcodes reuse scalar_alu_pkg.
package bct_pkg;
    typedef enum logic [1:0] {
        BCT_PROFILE_A = 2'd0,
        BCT_PROFILE_M = 2'd1,
        BCT_PROFILE_MAC = 2'd2
    } bct_profile_t;

    typedef enum logic [1:0] {
        BCT_FU_ALU = 2'd0,
        BCT_FU_MULTIPLY = 2'd1,
        BCT_FU_MAC = 2'd2
    } bct_fu_t;

    typedef enum logic [1:0] {
        BCT_BYPASS_MINIMAL = 2'd0,
        BCT_BYPASS_BALANCED = 2'd1,
        BCT_BYPASS_FLEXIBLE = 2'd2
    } bct_bypass_t;

    typedef enum logic [1:0] {
        BCT_SYNC_NONE = 2'd0,
        BCT_SYNC_RDU = 2'd1,
        BCT_SYNC_ELASTIC = 2'd2
    } bct_sync_t;

    typedef enum logic [1:0] {
        BCT_PRED_ALWAYS = 2'd0,
        BCT_PRED_EXTERNAL = 2'd1,
        BCT_PRED_LOCAL = 2'd2,
        BCT_PRED_NEVER = 2'd3
    } bct_predicate_t;

    typedef enum logic [7:0] {
        BCT_OK = 8'd0,
        BCT_ERR_CONTEXT = 8'd64,
        BCT_ERR_SOURCE = 8'd65,
        BCT_ERR_CANONICAL = 8'd66,
        BCT_ERR_SCHEDULE = 8'd67,
        BCT_ERR_INTEGRITY = 8'd68,
        BCT_ERR_OWNERSHIP = 8'd69,
        BCT_ERR_OVERFLOW = 8'd70,
        BCT_ERR_CORRECTED = 8'd71
    } bct_error_t;
endpackage
`default_nettype wire
