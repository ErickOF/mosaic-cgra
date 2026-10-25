`timescale 1ns / 1ps
// Repository-local ABI, extending the released scratchpad memory error namespace.
package banked_scratchpad_pkg;
    localparam int REQ_OPCODE_WIDTH = 2;
    localparam int REGION_CMD_WIDTH = 3;
    localparam int REGION_STATE_WIDTH = 3;
    localparam int BUFFER_ROLE_WIDTH = 2;
    localparam int BANK_POWER_STATE_WIDTH = 2;
    localparam int MEM_ERROR_WIDTH = 8;
    localparam int REGION_ERROR_WIDTH = 8;
    localparam int BSP_ERROR_WIDTH = 8;
    localparam int EVENT_CODE_WIDTH = 3;
    localparam int SLOT_GENERATION_WIDTH = 32;

    typedef enum logic {
        BSP_MAP_LINEAR_STRIPED = 0,
        BSP_MAP_XOR_STRIPED = 1
    } mapping_t;
    typedef enum logic [1:0] {
        BSP_PROTECTION_NONE = 0,
        BSP_PROTECTION_PARITY = 1,
        BSP_PROTECTION_SECDED = 2
    } protection_t;
    typedef enum logic [1:0] {
        BSP_REQ_READ = 0,
        BSP_REQ_WRITE = 1,
        BSP_REQ_FENCE = 2
    } request_opcode_t;

    typedef enum logic [2:0] {
        REGION_UNASSIGNED = 0,
        REGION_HOST_OWNED = 1,
        REGION_DMA_OWNED = 2,
        REGION_CGRA_OWNED = 3,
        REGION_SHARED_READ_ONLY = 4,
        REGION_TRANSFER = 5
    } region_state_t;

    typedef enum logic [1:0] {
        BUFFER_ROLE_NONE = 0,
        BUFFER_ROLE_ACTIVE = 1,
        BUFFER_ROLE_STAGING = 2
    } buffer_role_t;

    typedef enum logic [2:0] {
        REGION_CMD_READ = 0,
        REGION_CMD_PROVISION = 1,
        REGION_CMD_TRANSITION = 2,
        REGION_CMD_SWAP = 3,
        REGION_CMD_INVALIDATE = 4
    } region_command_t;

    typedef enum logic [1:0] {
        BANK_POWER_ACTIVE = 0,
        BANK_POWER_CLOCK_GATED = 1,
        BANK_POWER_RETENTION = 2,
        BANK_POWER_OFF = 3
    } bank_power_t;

    typedef enum logic [2:0] {
        POWER_STABLE = 0,
        POWER_STOP = 1,
        POWER_SAVE = 2,
        POWER_ISOLATE = 3,
        POWER_CHANGE = 4,
        POWER_WAKE = 5,
        POWER_RESTORE = 6
    } power_phase_t;

    typedef enum logic [1:0] {
        MANAGER_IDLE = 0,
        MANAGER_WAIT = 1,
        MANAGER_PERMISSIONS = 2,
        MANAGER_RESPONSE = 3
    } manager_phase_t;

    typedef enum logic [7:0] {
        BSP_MEM_NONE = 0,
        BSP_MEM_UNKNOWN = 1,
        BSP_MEM_RANGE = 2,
        BSP_MEM_SIZE = 3,
        BSP_MEM_ALIGNMENT = 4,
        BSP_MEM_CROSSING = 5,
        BSP_MEM_STROBE = 6,
        BSP_MEM_PARITY = 7,
        BSP_MEM_ECC = 8,
        BSP_MEM_PROTOCOL = 9,
        BSP_MEM_PERMISSION = 10,
        BSP_MEM_OPCODE = 11,
        BSP_MEM_REGION = 12,
        BSP_MEM_GENERATION = 13,
        BSP_MEM_OWNER = 14,
        BSP_MEM_CONTENTS = 15,
        BSP_MEM_BANK_POWER = 16
    } memory_error_t;

    typedef enum logic [7:0] {
        REGION_ERR_NONE = 0,
        REGION_ERR_UNKNOWN = 1,
        REGION_ERR_INDEX = 2,
        REGION_ERR_OPCODE = 3,
        REGION_ERR_RANGE = 4,
        REGION_ERR_OVERLAP = 5,
        REGION_ERR_VALID = 6,
        REGION_ERR_COMPARE = 7,
        REGION_ERR_GENERATION = 8,
        REGION_ERR_PAIR = 9,
        REGION_ERR_CONTENTS = 10,
        REGION_ERR_STATE = 11,
        REGION_ERR_POWER = 12
    } region_error_t;

    typedef enum logic [7:0] {
        BSP_ERR_NONE = 0,
        BSP_ERR_CONTROL = 1,
        BSP_ERR_COMPLETION = 2,
        BSP_ERR_CONTROLLER = 3,
        BSP_ERR_BANK = 4,
        BSP_ERR_POWER = 5,
        BSP_ERR_GENERATION = 6
    } internal_error_t;

    typedef enum logic [2:0] {
        BSP_EVENT_FILLED = 0,
        BSP_EVENT_CONSUMED = 1,
        BSP_EVENT_SWAPPED = 2,
        BSP_EVENT_INVALIDATED = 3,
        BSP_EVENT_ERROR = 4,
        BSP_EVENT_TRANSITION = 5
    } event_code_t;
endpackage
