`timescale 1ns / 1ps
// Repository-local synchronous Array-MVP ABI. Scheduling stays outside this boundary.
package array_pkg;
    typedef enum logic [4:0] {
        ARRAY_QUERY = 0,
        ARRAY_ALLOCATE = 1,
        ARRAY_CONFIGURE = 2,
        ARRAY_VALIDATE = 3,
        ARRAY_COMMIT = 4,
        ARRAY_START = 5,
        ARRAY_SUSPEND = 6,
        ARRAY_RESUME = 7,
        ARRAY_DRAIN = 8,
        ARRAY_RESIZE = 9,
        ARRAY_MIGRATE = 10,
        ARRAY_ABORT = 11,
        ARRAY_RELEASE = 12,
        ARRAY_COUNTER_SNAPSHOT = 13,
        ARRAY_CLEAR_ERROR = 14,
        ARRAY_POWER_REQUEST = 15
    } array_command_t;

    typedef enum logic [3:0] {
        ARRAY_RESET = 0,
        ARRAY_IDLE = 1,
        ARRAY_CONFIGURING = 2,
        ARRAY_ACTIVE = 3,
        ARRAY_MIXED = 4,
        ARRAY_DRAINING = 5,
        ARRAY_SUSPENDED = 6,
        ARRAY_POWER_TRANSITION = 7,
        ARRAY_DEGRADED = 8,
        ARRAY_ERROR_ISOLATED = 9
    } array_state_t;

    typedef enum logic [7:0] {
        ARRAY_OK = 0,
        ARRAY_ERR_COMMAND = 1,
        ARRAY_ERR_OWNER = 2,
        ARRAY_ERR_RESOURCE = 3,
        ARRAY_ERR_STATE = 4,
        ARRAY_ERR_GENERATION = 5,
        ARRAY_ERR_PACKAGE = 6,
        ARRAY_ERR_CLUSTER = 7,
        ARRAY_ERR_TIMEOUT = 8,
        ARRAY_ERR_EVENT = 9,
        ARRAY_ERR_NETWORK = 10,
        ARRAY_ERR_UNSUPPORTED = 11,
        ARRAY_ERR_INTEGRITY = 12,
        ARRAY_ERR_EPOCH = 13
    } array_error_t;

    typedef enum logic [2:0] {
        ARRAY_CLUSTER_FREE = 0,
        ARRAY_CLUSTER_ALLOCATED = 1,
        ARRAY_CLUSTER_CONFIGURING = 2,
        ARRAY_CLUSTER_PREPARED = 3,
        ARRAY_CLUSTER_COMMITTED = 4,
        ARRAY_CLUSTER_RUNNING = 5,
        ARRAY_CLUSTER_SUSPENDED = 6,
        ARRAY_CLUSTER_DRAINED = 7
    } array_cluster_stage_t;

    typedef enum logic [2:0] {
        ARRAY_PHASE_IDLE,
        ARRAY_PHASE_SEND,
        ARRAY_PHASE_WAIT,
        ARRAY_PHASE_COMMIT,
        ARRAY_PHASE_COMMIT_WAIT,
        ARRAY_PHASE_ROLLBACK
    } array_phase_t;
endpackage
