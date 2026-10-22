`timescale 1ns / 1ps

// Repository-local encodings, shared by RTL and integration testbenches.
package loop_controller_pkg;
    typedef enum logic [1:0] {
        LOOP_COUNTED = 2'd0,
        LOOP_BOUNDED = 2'd1
    } loop_mode_t;

    typedef enum logic [2:0] {
        LOOP_COMPARE_LT = 3'd0,
        LOOP_COMPARE_LE = 3'd1,
        LOOP_COMPARE_GT = 3'd2,
        LOOP_COMPARE_GE = 3'd3
    } loop_compare_t;

    typedef enum logic [1:0] {
        LOOP_PAUSE = 2'd0,
        LOOP_RESUME = 2'd1,
        LOOP_ABORT = 2'd2
    } loop_control_t;

    typedef enum logic [1:0] {
        LOOP_COMPLETE = 2'd0,
        LOOP_ABORTED = 2'd1,
        LOOP_FLUSHED = 2'd2
    } loop_completion_t;

    typedef enum logic [2:0] {
        LOOP_IDLE,
        LOOP_ISSUE,
        LOOP_PAUSE_WAIT,
        LOOP_SUSPENDED,
        LOOP_ABORT_WAIT,
        LOOP_COMPLETE_WAIT,
        LOOP_RECORD
    } loop_state_t;

    typedef enum logic [4:0] {
        LOOP_ERR_NONE,
        LOOP_ERR_UNKNOWN,
        LOOP_ERR_DEPTH,
        LOOP_ERR_MODE,
        LOOP_ERR_COMPARE,
        LOOP_ERR_STEP,
        LOOP_ERR_INTERVAL,
        LOOP_ERR_BOUNDS,
        LOOP_ERR_INDEX,
        LOOP_ERR_PRODUCT,
        LOOP_ERR_EVENT,
        LOOP_ERR_INACTIVE,
        LOOP_ERR_START,
        LOOP_ERR_CONTROL,
        LOOP_ERR_CORRUPT,
        LOOP_ERR_INVARIANT
    } loop_error_t;

    localparam int MODE_WIDTH = $bits(loop_mode_t);
    localparam int COMPARE_WIDTH = $bits(loop_compare_t);
    localparam int CONTROL_WIDTH = $bits(loop_control_t);
    localparam int COMPLETION_WIDTH = $bits(loop_completion_t);
    localparam int ERROR_WIDTH = $bits(loop_error_t);
endpackage
