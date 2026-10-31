`timescale 1ns / 1ps
// Repository-local Cluster-MVP ABI. Optional profiles require separate contracts.
package cluster_pkg;
    typedef enum logic [3:0] {
        CLUSTER_QUERY = 0,
        CLUSTER_RESERVE = 1,
        CLUSTER_CONFIGURE = 2,
        CLUSTER_VALIDATE = 3,
        CLUSTER_START = 4,
        CLUSTER_SUSPEND = 5,
        CLUSTER_RESUME = 6,
        CLUSTER_DRAIN = 7,
        CLUSTER_ABORT = 8,
        CLUSTER_RELEASE = 9,
        CLUSTER_CLEAR_ERROR = 10,
        CLUSTER_COUNTER_SNAPSHOT = 11,
        CLUSTER_POWER_REQUEST = 12
    } runtime_command_t;

    typedef enum logic [3:0] {
        CLUSTER_FREE = 0,
        CLUSTER_RESERVED = 1,
        CLUSTER_CONFIGURING = 2,
        CLUSTER_READY = 3,
        CLUSTER_RUNNING_SINGLE = 4,
        CLUSTER_RUNNING_MULTI = 5,
        CLUSTER_PARTIALLY_IDLE = 6,
        CLUSTER_DRAINING = 7,
        CLUSTER_SUSPENDING = 8,
        CLUSTER_SUSPENDED = 9,
        CLUSTER_POWER_TRANSITION = 10,
        CLUSTER_POWER_GATED = 11,
        CLUSTER_RECOVERING = 12,
        CLUSTER_ERROR_ISOLATED = 13
    } state_t;

    typedef enum logic [7:0] {
        CLUSTER_OK = 0,
        CLUSTER_ERR_UNKNOWN = 1,
        CLUSTER_ERR_COMMAND = 2,
        CLUSTER_ERR_OWNER = 3,
        CLUSTER_ERR_STATE = 4,
        CLUSTER_ERR_RESOURCE = 5,
        CLUSTER_ERR_PACKAGE = 6,
        CLUSTER_ERR_CONTEXT = 7,
        CLUSTER_ERR_BUSY = 8,
        CLUSTER_ERR_TILE = 9,
        CLUSTER_ERR_TIMEOUT = 10,
        CLUSTER_ERR_CONFIGURATION = 11,
        CLUSTER_ERR_NETWORK = 12,
        CLUSTER_ERR_MEMORY = 13,
        CLUSTER_ERR_METADATA = 14,
        CLUSTER_ERR_COMPLETION = 15,
        CLUSTER_ERR_UNSUPPORTED = 16,
        CLUSTER_ERR_INTEGRITY = 17,
        CLUSTER_ERR_EPOCH = 18
    } error_t;

    typedef enum logic [3:0] {
        CLUSTER_PHASE_IDLE = 0,
        CLUSTER_PHASE_RELEASE_HOLD = 1,
        CLUSTER_PHASE_FANOUT = 2,
        CLUSTER_PHASE_SETTLE = 3,
        CLUSTER_PHASE_RELEASE_MEMORY = 4,
        CLUSTER_PHASE_RELEASE_FABRIC = 5
    } phase_t;

    typedef enum logic [3:0] {
        INFRA_IDLE = 0,
        INFRA_WRITE_SEND = 1,
        INFRA_WRITE_WAIT = 2,
        INFRA_NATIVE_SEND = 3,
        INFRA_NATIVE_WAIT = 4,
        INFRA_INVALIDATE_SEND = 5,
        INFRA_INVALIDATE_WAIT = 6,
        INFRA_PROVISION_SEND = 7,
        INFRA_PROVISION_WAIT = 8
    } infrastructure_phase_t;

    typedef enum logic [1:0] {
        MEMORY_IDLE = 0,
        MEMORY_SEND = 1,
        MEMORY_WAIT = 2,
        MEMORY_LOCAL_ERROR = 3
    } memory_phase_t;

    typedef enum logic [2:0] {
        CLUSTER_EVENT_TILE = 0,
        CLUSTER_EVENT_MEMORY = 1,
        CLUSTER_EVENT_COMPLETE = 2,
        CLUSTER_EVENT_FAULT = 3
    } event_type_t;
endpackage
