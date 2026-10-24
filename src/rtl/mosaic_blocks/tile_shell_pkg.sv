`timescale 1ns / 1ps
// Repository-local v1 shell boundary, shared by tile bodies and verification.
// Metadata field widths remain parameterized in the shell; numerical payloads
// and context images are opaque to this package.
package tile_shell_pkg;
    typedef enum logic [2:0] {
        TILE_CLASS_BCT = 3'd0,
        TILE_CLASS_VCT = 3'd1,
        TILE_CLASS_SFT = 3'd2,
        TILE_CLASS_MST = 3'd3,
        TILE_CLASS_CPT = 3'd4
    } tile_class_t;
    typedef enum logic [2:0] {
        CFG_WRITE = 3'd0,
        CFG_READ = 3'd1,
        CFG_VALIDATE = 3'd2,
        CFG_ACTIVATE = 3'd3,
        CFG_INVALIDATE = 3'd4,
        CFG_QUERY = 3'd5
    } configuration_command_t;
    typedef enum logic [2:0] {
        RUNTIME_ALLOCATE = 3'd0,
        RUNTIME_START = 3'd1,
        RUNTIME_SUSPEND = 3'd2,
        RUNTIME_RESUME = 3'd3,
        RUNTIME_DRAIN = 3'd4,
        RUNTIME_TERMINATE = 3'd5,
        RUNTIME_RELEASE = 3'd6,
        RUNTIME_CLEAR_ERROR = 3'd7
    } runtime_command_t;
    typedef enum logic [3:0] {
        TILE_UNALLOCATED = 4'd0,
        TILE_CONFIGURING = 4'd1,
        TILE_READY = 4'd2,
        TILE_ACTIVE = 4'd3,
        TILE_INPUT_STALL = 4'd4,
        TILE_OUTPUT_STALL = 4'd5,
        TILE_MEMORY_STALL = 4'd6,
        TILE_SYNC_STALL = 4'd7,
        TILE_SUSPENDING = 4'd8,
        TILE_SUSPENDED = 4'd9,
        TILE_DRAINING = 4'd10,
        TILE_COMPLETED = 4'd11,
        TILE_ERROR = 4'd12,
        TILE_POWER_TRANSITION = 4'd13
    } execution_state_t;
    typedef enum logic [2:0] {
        POWER_ACTIVE = 3'd0,
        POWER_STALLED = 3'd1,
        POWER_IDLE = 3'd2,
        POWER_RETENTION = 3'd3,
        POWER_OFF = 3'd4,
        POWER_WAKEUP = 3'd5,
        POWER_SAFE = 3'd6
    } shell_power_state_t;
    typedef enum logic [2:0] {
        EVENT_COMPLETE = 3'd0,
        EVENT_WAKEUP = 3'd1,
        EVENT_BARRIER_ARRIVE = 3'd2,
        EVENT_BARRIER_RELEASE = 3'd3,
        EVENT_CONTEXT = 3'd4,
        EVENT_ERROR = 3'd5,
        EVENT_FATAL = 3'd6,
        EVENT_BODY = 3'd7
    } shell_event_t;
    typedef enum logic [7:0] {
        SHELL_OK = 8'd0,
        SHELL_ERR_UNKNOWN = 8'd1,
        SHELL_ERR_TILE = 8'd2,
        SHELL_ERR_OWNER = 8'd3,
        SHELL_ERR_CONTEXT = 8'd4,
        SHELL_ERR_WORD = 8'd5,
        SHELL_ERR_ACTIVE = 8'd6,
        SHELL_ERR_INCOMPLETE = 8'd7,
        SHELL_ERR_CRC = 8'd8,
        SHELL_ERR_BODY = 8'd9,
        SHELL_ERR_STALE = 8'd10,
        SHELL_ERR_COMMAND = 8'd11,
        SHELL_ERR_STATE = 8'd12,
        SHELL_ERR_METADATA = 8'd13,
        SHELL_ERR_SCHEDULE = 8'd14,
        SHELL_ERR_DEBUG = 8'd15,
        SHELL_ERR_CORRECTED = 8'd16,
        SHELL_ERR_INTEGRITY = 8'd17,
        SHELL_ERR_VERSION = 8'd18,
        SHELL_ERR_COMPLETION = 8'd19,
        SHELL_ERR_POWER = 8'd20,
        SHELL_ERR_POWER_LOSS = 8'd21
    } shell_error_t;
    typedef enum logic [2:0] {
        ERROR_SOURCE_CONFIGURATION = 3'd0,
        ERROR_SOURCE_BODY = 3'd1,
        ERROR_SOURCE_POWER = 3'd2,
        ERROR_SOURCE_RUNTIME = 3'd3,
        ERROR_SOURCE_PROTOCOL = 3'd4,
        ERROR_SOURCE_DEBUG = 3'd5,
        ERROR_SOURCE_INTEGRITY = 3'd6
    } shell_error_source_t;
endpackage
