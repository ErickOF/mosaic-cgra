`timescale 1ns / 1ps
// Runtime v1 wire ABI. All records are LSB-first in the Python adapter.
package runtime_controller_pkg;
    typedef enum logic [4:0] {
        RT_FREE = 5'd0,
        RT_SUBMITTED = 5'd1,
        RT_VALIDATING = 5'd2,
        RT_WAIT_RESOURCES = 5'd3,
        RT_RESERVING = 5'd4,
        RT_ALLOCATING = 5'd5,
        RT_CONFIGURING = 5'd6,
        RT_READY = 5'd7,
        RT_STARTING = 5'd8,
        RT_RUNNING = 5'd9,
        RT_SUSPEND_PENDING = 5'd10,
        RT_SUSPENDED = 5'd11,
        RT_RESIZE_PENDING = 5'd12,
        RT_MIGRATE_PENDING = 5'd13,
        RT_DRAINING = 5'd14,
        RT_COMPLETED = 5'd15,
        RT_TERMINATING = 5'd16,
        RT_ERROR = 5'd17,
        RT_RELEASING = 5'd18
    } kernel_state_t;
    typedef enum logic [4:0] {
        CMD_ALLOCATE = 5'd0,
        CMD_RESERVE = 5'd1,
        CMD_WAKE = 5'd2,
        CMD_LOAD = 5'd3,
        CMD_VALIDATE = 5'd4,
        CMD_PREPARE = 5'd5,
        CMD_COMMIT = 5'd6,
        CMD_ACTIVATE = 5'd7,
        CMD_START = 5'd8,
        CMD_DRAIN = 5'd9,
        CMD_RELEASE = 5'd10,
        CMD_SUSPEND = 5'd11,
        CMD_RESUME = 5'd12,
        CMD_ABORT = 5'd13,
        CMD_IDLE = 5'd14
    } command_t;
    typedef enum logic [3:0] {
        POL_QUERY = 4'd0,
        POL_ENABLE = 4'd1,
        POL_DISABLE = 4'd2,
        POL_UPDATE_BOUNDS = 4'd3,
        POL_REQUEST_SUSPEND = 4'd4,
        POL_REQUEST_RESUME = 4'd5,
        POL_CANCEL = 4'd6,
        POL_FORCE_ABORT = 4'd7
    } policy_command_t;
    typedef enum logic [3:0] {
        EV_COMPUTE_DONE = 4'd0,
        EV_EXTERNAL_DONE = 4'd1,
        EV_INPUT_READY = 4'd2,
        EV_OUTPUT_SPACE = 4'd3,
        EV_SAFE_POINT = 4'd4,
        EV_FAULT = 4'd5,
        EV_COUNTERS_CHANGED = 4'd6
    } event_type_t;
    typedef enum logic [7:0] {
        ERR_NONE = 8'd0,
        ERR_DESCRIPTOR = 8'd1,
        ERR_OWNER = 8'd2,
        ERR_DUPLICATE = 8'd3,
        ERR_CAPABILITY = 8'd4,
        ERR_PROOF = 8'd5,
        ERR_BUDGET = 8'd6,
        ERR_UNSUPPORTED = 8'd7,
        ERR_AUTHORIZATION = 8'd8,
        ERR_IDENTITY = 8'd9,
        ERR_BACKEND = 8'd10,
        ERR_TIMEOUT = 8'd11,
        ERR_PARTIAL = 8'd12,
        ERR_SEQUENCE = 8'd13,
        ERR_DEADLINE = 8'd14,
        ERR_FAULTED = 8'd15,
        ERR_EXHAUSTED = 8'd16,
        ERR_INTEGRITY = 8'd17,
        ERR_BUSY = 8'd18
    } error_t;
    typedef enum logic [2:0] {
        NOTICE_ADMITTED = 3'd0,
        NOTICE_REJECTED = 3'd1,
        NOTICE_CANCELED = 3'd2,
        NOTICE_FAILED = 3'd3,
        NOTICE_SUCCEEDED = 3'd4,
        NOTICE_ABORTED = 3'd5
    } notice_status_t;
    typedef enum logic [2:0] {
        ACK_OK = 3'd0,
        ACK_NO_EFFECT = 3'd1,
        ACK_UNCERTAIN = 3'd2
    } ack_status_t;
    typedef enum logic [2:0] {
        EP_CONFIG = 3'd0,
        EP_DMA = 3'd1,
        EP_MEMORY = 3'd2,
        EP_NOC = 3'd3,
        EP_EVENT = 3'd4,
        EP_POWER = 3'd5,
        EP_ARRAY = 3'd6
    } endpoint_t;
    typedef enum logic [4:0] {
        PH_ARRAY_ALLOCATE = 5'd0,
        PH_RESERVE_SERVICES = 5'd1,
        PH_ADMISSION = 5'd2,
        PH_POWER_WAKE = 5'd3,
        PH_CONFIG_LOAD = 5'd4,
        PH_CONFIG_VALIDATE = 5'd5,
        PH_CONFIG_PREPARE = 5'd6,
        PH_ARRAY_COMMIT = 5'd7,
        PH_ACTIVATE_SERVICES = 5'd8,
        PH_WAIT_IO = 5'd9,
        PH_ARRAY_START = 5'd10,
        PH_EXECUTING = 5'd11,
        PH_ARRAY_SUSPEND = 5'd12,
        PH_PRESERVE_SERVICES = 5'd13,
        PH_SLEEPING = 5'd14,
        PH_RESUME_SERVICES = 5'd15,
        PH_ARRAY_RESUME = 5'd16,
        PH_ARRAY_DRAIN = 5'd17,
        PH_DRAIN_SERVICES = 5'd18,
        PH_RELEASE_SERVICES = 5'd19,
        PH_ARRAY_RELEASE = 5'd20,
        PH_POWER_IDLE = 5'd21,
        PH_FINISH = 5'd22,
        PH_CONTAINED = 5'd23
    } phase_t;
    typedef struct packed {
        logic [7:0] epoch;
        logic [15:0] allocation_generation;
        logic [31:0] mapping_id;
        logic [31:0] package_id;
        logic [15:0] descriptor_generation;
        logic [15:0] descriptor_id;
        logic [15:0] kernel_id;
        logic [15:0] owner_id;
    } identity_t;
    typedef struct packed {
        logic [19:0] reserved;
        logic [31:0] energy_model_id;
        logic [7:0] flags;
        logic [3:0] power_profile;
        logic [3:0] memory_profile;
        logic [3:0] noc_profile;
        logic [31:0] proof_id;
        logic [31:0] architecture_id;
        logic [31:0] required_capabilities;
        logic [7:0] cluster_count;
        logic [15:0] cluster_mask;
        logic [31:0] mapping_id;
        logic [31:0] package_id;
    } variant_t;
    typedef struct packed {
        logic [33:0] reserved;
        logic [7:0] flags;
        logic [5:0] services;
        logic [15:0] counter_mask;
        logic [31:0] power;
        logic [31:0] memory_bandwidth;
        logic [31:0] noc_bandwidth;
        logic [31:0] event_mask;
        logic [31:0] scratchpad_mask;
        logic [15:0] memory_mask;
        logic [15:0] dma_mask;
    } resource_t;
    typedef struct packed {
        logic [23:0] reserved;
        logic [7:0] flags;
        logic [31:0] latency_limit;
        logic [31:0] noc_minimum;
        logic [31:0] memory_minimum;
    } qos_t;
    typedef struct packed {
        logic [23:0] reserved;
        logic [7:0] flags;
        logic [15:0] profile_mask;
        logic [47:0] energy_budget;
        logic [31:0] budget;
    } power_t;
    typedef struct packed {
        logic [15:0] reserved;
        logic [31:0] resume_cookie;
        logic [7:0] safe_point_id;
        logic [31:0] kernel_timeout;
        logic [31:0] action_timeout;
        logic [7:0] flags;
    } lifecycle_t;
    typedef struct packed {
        lifecycle_t lifecycle;
        power_t power;
        qos_t qos;
        resource_t resources;
        logic [15:0] tag;
        logic [15:0] flags;
        logic [7:0] profile;
        logic [63:0] resource_mask;
        logic [15:0] cluster_mask;
        logic [4:0] command;
        identity_t identity;
    } action_t;
    typedef struct packed {
        logic [15:0] tag;
        logic [15:0] flags;
        logic [7:0] error;
        logic [2:0] status;
        logic [15:0] cluster_mask;
        logic [4:0] command;
        identity_t identity;
    } ack_t;
    typedef struct packed {
        logic [3:0] slot;
        logic [15:0] tag;
        logic [15:0] cluster_mask;
        logic [7:0] error;
        logic [2:0] status;
        identity_t identity;
    } notice_t;
    typedef struct packed {
        logic [15:0] tag;
        logic [31:0] resume_cookie;
        logic [31:0] bandwidth_budget;
        logic [31:0] power_budget;
        logic [7:0] priority_limit;
        logic destructive;
        logic authorized;
        logic [3:0] command;
        identity_t identity;
    } policy_t;
    typedef struct packed {
        logic [15:0] tag;
        logic [4:0] state;
        logic [7:0] error;
        logic [2:0] status;
        identity_t identity;
    } policy_reply_t;
    typedef struct packed {
        logic [1:0] severity;
        logic [31:0] payload;
        logic [63:0] timestamp;
        logic [15:0] sequence_id;
        logic [15:0] cluster_mask;
        logic [7:0] source;
        logic [3:0] event_type;
        identity_t identity;
    } event_t;
    typedef struct packed {
        logic critical;
        logic [255:0] metrics;
        logic [15:0] validity;
        logic [63:0] timestamp;
        logic [15:0] generation;
        identity_t identity;
    } snapshot_t;
    typedef struct packed {
        logic [63:0] timestamp;
        logic [7:0] error;
        logic [3:0] event_type;
        identity_t identity;
    } diagnostic_t;
endpackage
