`timescale 1ns / 1ps
// Local v1 command and transport encodings. Width-dependent records stay local.
package cpt_pkg;
    typedef enum logic [3:0] {
        CPT_CMD_PREDICATE = 4'd0,
        CPT_CMD_COMPARE = 4'd1,
        CPT_CMD_LOOP_CONFIG = 4'd2,
        CPT_CMD_LOOP_CONTROL = 4'd3,
        CPT_CMD_EVENT = 4'd4,
        CPT_CMD_BARRIER = 4'd5,
        CPT_CMD_ACTION = 4'd6,
        CPT_CMD_STATUS = 4'd7,
        CPT_CMD_DISPATCH = 4'd8
    } cpt_command_t;

    typedef enum logic [3:0] {
        CPT_ACTION_START = 4'd0,
        CPT_ACTION_STOP = 4'd1,
        CPT_ACTION_SUSPEND = 4'd2,
        CPT_ACTION_RESUME = 4'd3,
        CPT_ACTION_DRAIN = 4'd4,
        CPT_ACTION_ACTIVATE_CONTEXT = 4'd5,
        CPT_ACTION_WAKE = 4'd6,
        CPT_ACTION_CHECKPOINT = 4'd7,
        CPT_ACTION_RECOVER = 4'd8
    } cpt_action_t;

    typedef enum logic [3:0] {
        CPT_RECORD_POST = 4'd0,
        CPT_RECORD_FORWARD = 4'd1,
        CPT_RECORD_WAIT = 4'd2,
        CPT_RECORD_BARRIER = 4'd3,
        CPT_RECORD_LOOP = 4'd4,
        CPT_RECORD_REQUEST = 4'd5,
        CPT_RECORD_RESPONSE = 4'd6,
        CPT_RECORD_SAFE = 4'd7,
        CPT_RECORD_QUERY = 4'd8,
        CPT_RECORD_TERMINAL = 4'd9,
        CPT_RECORD_REJECT = 4'd10
    } cpt_record_kind_t;

    typedef enum logic [3:0] {
        ACTION_FREE = 4'd0,
        ACTION_QUEUED = 4'd1,
        ACTION_SENT = 4'd2,
        ACTION_WAIT_SAFE = 4'd3,
        ACTION_QUERY = 4'd4,
        ACTION_WAIT_QUERY = 4'd5,
        ACTION_COMPLETED = 4'd6,
        ACTION_REJECTED = 4'd7
    } cpt_action_state_t;

    typedef enum logic [2:0] {
        CPT_IDLE = 3'd0,
        CPT_EXECUTE = 3'd1,
        CPT_NATIVE_WAIT = 3'd2,
        CPT_RETIRE = 3'd3
    } cpt_engine_state_t;

    // The envelope uses the shell's parameter-dependent low-bit context/kernel
    // packing. The remaining fields have fixed offsets in the local v1 ABI.
    typedef struct packed {
        logic [7:0] reserved;
        logic [63:0] payload;
        logic [15:0] route_version;
        logic [15:0] package_version;
        logic [15:0] participants;
        logic [7:0] tag;
        logic [15:0] sequence_number;
        logic [15:0] epoch;
        logic [15:0] context_version;
        logic [15:0] owner;
        logic [3:0] flags;
        logic [3:0] namespace_id;
        logic [7:0] source;
        logic [7:0] event_id;
        logic [3:0] opcode;
        logic [3:0] kind;
        logic [31:0] envelope;
    } cpt_record_t;
endpackage
`default_nettype wire
