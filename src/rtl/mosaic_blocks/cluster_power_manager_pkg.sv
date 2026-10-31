`timescale 1ns / 1ps
// Repository-local v1 ABI; generated JSON publishes each numeric encoding and field.
package cluster_power_manager_pkg;
    typedef enum logic [4:0] {
        CPM_RESET = 5'd0,
        CPM_ACTIVE = 5'd1,
        CPM_STALLED = 5'd2,
        CPM_IDLE_ON = 5'd3,
        CPM_CLOCK_GATED = 5'd4,
        CPM_DRAINING = 5'd5,
        CPM_SAVING = 5'd6,
        CPM_ISOLATING = 5'd7,
        CPM_POWERING_DOWN = 5'd8,
        CPM_RETENTION = 5'd9,
        CPM_OFF = 5'd10,
        CPM_POWERING_UP = 5'd11,
        CPM_CLOCK_STARTING = 5'd12,
        CPM_RESTORING = 5'd13,
        CPM_REINITIALIZING = 5'd14,
        CPM_RELOADING = 5'd15,
        CPM_DVFS_DRAINING = 5'd16,
        CPM_DVFS_ISOLATING = 5'd17,
        CPM_DVFS_TRANSITION = 5'd18,
        CPM_DVFS_STABILIZING = 5'd19,
        CPM_WAKEUP = 5'd20,
        CPM_ERROR = 5'd21,
        CPM_TEST = 5'd22
    } state_t;

    typedef enum logic [4:0] {
        PH_NONE = 5'd0,
        PH_POWER = 5'd1,
        PH_CLOCK = 5'd2,
        PH_RESET_HOLD = 5'd3,
        PH_RESET_RELEASE = 5'd4,
        PH_TILE_CONFIG = 5'd5,
        PH_TILE_RUN = 5'd6,
        PH_VALIDATE = 5'd7,
        PH_ISOLATION_HOLD = 5'd8,
        PH_DEISOLATE = 5'd9,
        PH_ENDPOINT_ENABLE = 5'd10,
        PH_STABILIZE = 5'd11,
        PH_DRAIN = 5'd12,
        PH_ENDPOINT_DISABLE = 5'd13,
        PH_TILE_IDLE = 5'd14,
        PH_CLOCK_STOP = 5'd15,
        PH_WAIT_AUTH = 5'd16,
        PH_TEST_ISOLATE = 5'd17
    } phase_t;

    typedef enum logic [3:0] {
        CP_QUERY = 4'd0,
        CP_RUN = 4'd1,
        CP_IDLE_ON = 4'd2,
        CP_CLOCK_GATE = 4'd3,
        CP_RETENTION = 4'd4,
        CP_OFF = 4'd5,
        CP_SET_POINT = 4'd6,
        CP_CLEAR_ERROR = 4'd7,
        CP_RECOVER = 4'd8
    } command_code_t;

    typedef enum logic [7:0] {
        ERR_NONE = 8'd0,
        ERR_COMMAND = 8'd1,
        ERR_IDENTITY = 8'd2,
        ERR_AUTHORITY = 8'd3,
        ERR_POLICY = 8'd4,
        ERR_UNSUPPORTED = 8'd5,
        ERR_RESIDENCY = 8'd6,
        ERR_DRAIN_TIMEOUT = 8'd7,
        ERR_TILE_TIMEOUT = 8'd8,
        ERR_TILE_REJECT = 8'd9,
        ERR_POWER_TIMEOUT = 8'd10,
        ERR_CLOCK_TIMEOUT = 8'd11,
        ERR_RESET_TIMEOUT = 8'd12,
        ERR_REVALIDATE_TIMEOUT = 8'd13,
        ERR_REVALIDATE_FAILED = 8'd14,
        ERR_ISOLATION_TIMEOUT = 8'd15,
        ERR_ENDPOINT_TIMEOUT = 8'd16,
        ERR_POWER_LOSS = 8'd17,
        ERR_CLOCK_LOSS = 8'd18,
        ERR_VOLTAGE_FAULT = 8'd19,
        ERR_THERMAL = 8'd20,
        ERR_PHYSICAL_ACK = 8'd21,
        ERR_UNKNOWN = 8'd22,
        ERR_TEST = 8'd23,
        ERR_INTEGRITY = 8'd24,
        ERR_CANCELED = 8'd25,
        ERR_EXHAUSTED = 8'd26
    } error_t;

    typedef enum logic [2:0] {
        STATUS_OK = 3'd0,
        STATUS_REJECTED = 3'd1,
        STATUS_TIMEOUT = 3'd2,
        STATUS_ROLLED_BACK = 3'd3,
        STATUS_ERROR = 3'd4
    } status_t;

    typedef enum logic [3:0] {
        EV_ACCEPTED = 4'd0,
        EV_REJECTED = 4'd1,
        EV_PHASE = 4'd2,
        EV_COMPLETE = 4'd3,
        EV_WAKE = 4'd4,
        EV_FATAL = 4'd5,
        EV_BAD_WAKE = 4'd6,
        EV_POLICY = 4'd7,
        EV_OVERFLOW = 4'd8
    } event_kind_t;

    typedef struct packed {
        logic [7:0] epoch;
        logic [15:0] allocation_generation;
        logic [31:0] package_id;
        logic [15:0] kernel_id;
        logic [15:0] owner_id;
        logic [7:0] cluster_id;
    } identity_t;

    typedef struct packed {
        logic [15:0] tag;
        logic [15:0] flags;
        logic [7:0] state_policy;
        logic [47:0] expected_idle;
        logic [3:0] point;
        logic [4:0] target;
        logic [3:0] command;
        identity_t identity;
    } command_t;

    typedef struct packed {
        logic [15:0] tag;
        logic [31:0] cycles;
        logic [3:0] point;
        logic [4:0] state;
        logic [7:0] error;
        logic [2:0] status;
        logic [3:0] command;
        identity_t identity;
    } response_t;

    typedef struct packed {
        logic reload;
        logic [15:0] tag;
        logic [15:0] serial;
        logic [15:0] boot_generation;
        identity_t identity;
    } validation_t;

    typedef struct packed {
        logic [3:0] validity;
        logic [1:0] status;
        logic [15:0] tag;
        logic [15:0] serial;
        logic [15:0] boot_generation;
        identity_t identity;
    } validation_response_t;

    typedef struct packed {
        logic [3:0] kind;
        logic [15:0] tag;
        logic [7:0] error;
        logic [2:0] status;
        logic [4:0] phase;
        logic [3:0] point;
        logic [4:0] target_state;
        logic [4:0] old_state;
        logic [63:0] timestamp;
        logic [15:0] sequence_id;
        logic [15:0] boot_generation;
        identity_t identity;
    } event_t;

    function automatic bit stable(input logic [4:0] state);
        case (state)
            CPM_ACTIVE, CPM_STALLED, CPM_IDLE_ON, CPM_CLOCK_GATED, CPM_ERROR, CPM_TEST:
                return 1'b1;
            default: return 1'b0;
        endcase
    endfunction
    typedef struct packed {
        logic valid;
        command_t value;
    } command_slot_t;
    typedef struct packed {
        logic valid;
        response_t value;
    } response_slot_t;
endpackage
