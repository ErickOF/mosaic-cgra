`timescale 1ns / 1ps
`default_nettype none
// Reliable configuration delivery. Native endpoints own image storage and
// semantics; this fabric owns transport, ordered completion and execution hold.
module configuration_network #(
    parameter TOPOLOGY_PROFILE = 1,
    parameter NUM_MASTERS = 1,
    parameter NUM_ENDPOINTS = 20,
    parameter NUM_TILE_ENDPOINTS = 16,
    parameter NUM_INFRA_ENDPOINTS = 4,
    parameter TREE_BRANCH_FACTOR = 4,
    parameter CONFIG_DATA_WIDTH = 64,
    parameter CONFIG_FLIT_WIDTH = 64,
    parameter ENDPOINT_ID_WIDTH = 8,
    parameter ENDPOINT_TYPE_WIDTH = 4,
    parameter COMMAND_WIDTH = 5,
    parameter CONTEXT_ID_WIDTH = 8,
    parameter CONTEXT_VERSION_WIDTH = 16,
    parameter OWNER_ID_WIDTH = 16,
    parameter KERNEL_ID_WIDTH = 16,
    parameter PACKAGE_ID_WIDTH = 32,
    parameter CONFIG_EPOCH_WIDTH = 4,
    parameter TRANSACTION_ID_WIDTH = 8,
    parameter TAG_WIDTH = 16,
    parameter WORD_INDEX_WIDTH = 16,
    parameter BYTE_STROBE_WIDTH = 8,
    parameter PACKET_CRC_WIDTH = 32,
    parameter IMAGE_CRC_WIDTH = 32,
    parameter STATUS_WIDTH = 4,
    parameter ERROR_CODE_WIDTH = 8,
    parameter COMMAND_QUEUE_DEPTH = 8,
    parameter RESPONSE_QUEUE_DEPTH = 8,
    parameter BRANCH_BUFFER_DEPTH = 2,
    parameter ENDPOINT_QUEUE_DEPTH = 2,
    parameter MAX_OUTSTANDING_TRANSACTIONS = 4,
    parameter TRANSACTION_TIMEOUT_CYCLES = 4096,
    parameter COMMIT_TIMEOUT_CYCLES = 1024,
    parameter SUPPORT_MULTICAST = 1,
    parameter SUPPORT_READBACK = 1,
    parameter SUPPORT_ASYNC_ENDPOINTS = 0,
    parameter SUPPORT_PACKET_RETRY = 0,
    parameter ENABLE_PACKET_CRC = 1,
    parameter CONTROL_PROTECTION = 1,
    parameter RESPONSE_ORDERING = 0,
    parameter ASYNC_RESET = 0,
    // A cluster-exclusive allocation may supply the current owner dynamically.
    // Endpoint read/write/admin rights still come from the permission table.
    parameter USE_ALLOCATION_OWNER = 0,
    localparam int NM = ((NUM_MASTERS >= 1 && NUM_MASTERS <= 4) === 1'b1) ?
        NUM_MASTERS : 1,
    localparam int NE = ((NUM_ENDPOINTS >= 1 && NUM_ENDPOINTS <= 128) === 1'b1) ?
        NUM_ENDPOINTS : 20,
    localparam int NT = ((NUM_TILE_ENDPOINTS >= 0 && NUM_TILE_ENDPOINTS <= 64) === 1'b1) ?
        NUM_TILE_ENDPOINTS : 16,
    localparam int NF = ((NUM_INFRA_ENDPOINTS >= 0 && NUM_INFRA_ENDPOINTS <= 64) === 1'b1) ?
        NUM_INFRA_ENDPOINTS : 4,
    localparam int BF = ((TREE_BRANCH_FACTOR >= 2 && TREE_BRANCH_FACTOR <= 4) === 1'b1) ?
        TREE_BRANCH_FACTOR : 4,
    localparam int D = ((CONFIG_DATA_WIDTH >= 8 && CONFIG_DATA_WIDTH <= 256) === 1'b1) ?
        CONFIG_DATA_WIDTH : 64,
    localparam int F = ((CONFIG_FLIT_WIDTH >= 8 && CONFIG_FLIT_WIDTH <= 256) === 1'b1) ?
        CONFIG_FLIT_WIDTH : 64,
    localparam int EI = ((ENDPOINT_ID_WIDTH >= 1 && ENDPOINT_ID_WIDTH <= 16) === 1'b1) ?
        ENDPOINT_ID_WIDTH : 8,
    localparam int ET = ((ENDPOINT_TYPE_WIDTH >= 1 && ENDPOINT_TYPE_WIDTH <= 8) === 1'b1) ?
        ENDPOINT_TYPE_WIDTH : 4,
    localparam int C = ((COMMAND_WIDTH >= 4 && COMMAND_WIDTH <= 8) === 1'b1) ?
        COMMAND_WIDTH : 5,
    localparam int CI = ((CONTEXT_ID_WIDTH >= 1 && CONTEXT_ID_WIDTH <= 16) === 1'b1) ?
        CONTEXT_ID_WIDTH : 8,
    localparam int V = ((CONTEXT_VERSION_WIDTH >= 1 && CONTEXT_VERSION_WIDTH <= 32) === 1'b1) ?
        CONTEXT_VERSION_WIDTH : 16,
    localparam int OW = ((OWNER_ID_WIDTH >= 1 && OWNER_ID_WIDTH <= 32) === 1'b1) ?
        OWNER_ID_WIDTH : 16,
    localparam int K = ((KERNEL_ID_WIDTH >= 1 && KERNEL_ID_WIDTH <= 32) === 1'b1) ?
        KERNEL_ID_WIDTH : 16,
    localparam int P = ((PACKAGE_ID_WIDTH >= 1 && PACKAGE_ID_WIDTH <= 64) === 1'b1) ?
        PACKAGE_ID_WIDTH : 32,
    localparam int EP = ((CONFIG_EPOCH_WIDTH >= 1 && CONFIG_EPOCH_WIDTH <= 16) === 1'b1) ?
        CONFIG_EPOCH_WIDTH : 4,
    localparam int TI = ((TRANSACTION_ID_WIDTH >= 1 && TRANSACTION_ID_WIDTH <= 16) === 1'b1) ?
        TRANSACTION_ID_WIDTH : 8,
    localparam int TG = ((TAG_WIDTH >= 1 && TAG_WIDTH <= 32) === 1'b1) ?
        TAG_WIDTH : 16,
    localparam int WI = ((WORD_INDEX_WIDTH >= 1 && WORD_INDEX_WIDTH <= 32) === 1'b1) ?
        WORD_INDEX_WIDTH : 16,
    localparam int BY = ((BYTE_STROBE_WIDTH >= 1 && BYTE_STROBE_WIDTH <= 32) === 1'b1) ?
        BYTE_STROBE_WIDTH : 8,
    localparam int CQ = ((COMMAND_QUEUE_DEPTH >= 1 && COMMAND_QUEUE_DEPTH <= 32) === 1'b1) ?
        COMMAND_QUEUE_DEPTH : 8,
    localparam int RQ = ((RESPONSE_QUEUE_DEPTH >= 1 && RESPONSE_QUEUE_DEPTH <= 32) === 1'b1) ?
        RESPONSE_QUEUE_DEPTH : 8,
    localparam int BQ = ((BRANCH_BUFFER_DEPTH >= 1 && BRANCH_BUFFER_DEPTH <= 8) === 1'b1) ?
        BRANCH_BUFFER_DEPTH : 2,
    localparam int EQ = ((ENDPOINT_QUEUE_DEPTH >= 1 && ENDPOINT_QUEUE_DEPTH <= 8) === 1'b1) ?
        ENDPOINT_QUEUE_DEPTH : 2,
    localparam int NS = ((MAX_OUTSTANDING_TRANSACTIONS >= 1
        && MAX_OUTSTANDING_TRANSACTIONS <= 16) === 1'b1) ?
        MAX_OUTSTANDING_TRANSACTIONS : 4,
    localparam int MI = NM > 1 ? $clog2(NM) : 1,
    localparam int OC = $clog2(NS + 1),
    localparam int SI = NS > 1 ? $clog2(NS) : 1,
    localparam int CAP = 1 << C,
    localparam int CB = C + TI + TG + OW + K + P + EP + CI + V + WI + D + BY + 32 + NE + MI + 48,
    localparam int CP = ((CB + 32 + F - 1) / F) * F,
    localparam int RB = C + TI + TG + EI + CI + V + D + 32 + EP + 4 + 8 + 32 + 8 + 2,
    localparam int RP = ((RB + 32 + F - 1) / F) * F,
    localparam int CF = CP / F,
    localparam int RF = RP / F,
    localparam int CX = CF > 1 ? $clog2(CF) : 1,
    localparam int RX = RF > 1 ? $clog2(RF) : 1,
    localparam int ENV = NE + TI + EP + 32 + MI,
    localparam int FL = F + CX + 3 + ENV,
    localparam int RL = F + RX + 3 + ENV,
    parameter ENDPOINT_PRESENT_MASK = {NE{1'b1}},
    parameter ENDPOINT_TYPE_TABLE = default_types(),
    parameter ENDPOINT_ID_TABLE = default_ids(),
    parameter ENDPOINT_CAPABILITY_TABLE = default_capabilities(),
    parameter ENDPOINT_PERMISSION_TABLE = default_permissions(),
    parameter ENDPOINT_CLOCK_DOMAIN_TABLE = {NE{1'b0}},
    parameter ENDPOINT_WORD_COUNT_TABLE = default_words(),
    parameter ENDPOINT_CONTEXT_DEPTH_TABLE = default_contexts(),
    parameter ENDPOINT_SCHEMA_TABLE = default_words(),
    parameter MULTICAST_GROUP_TABLE = {NE*NE{1'b1}},
    parameter COMMIT_DOMAIN_TABLE = {NE{1'b0}}
) (
    input wire i_clk,
    input wire i_reset_n,
    input wire i_drain,
    input wire i_flush,
    input wire i_resume,
    input wire i_error_clear,
    input wire i_test_enable,
    input wire i_scan_enable,
    input wire i_execution_release,
    input wire i_release_safe,
    input wire i_commit_valid,
    input wire i_allocation_owner_valid,
    input wire [OW-1:0] i_allocation_owner_id,
    input wire [NM-1:0] i_cfg_request_valid,
    output logic [NM-1:0] o_cfg_request_ready,
    input wire [NM*(C)-1:0] i_cfg_request_command,
    input wire [NM*(NE)-1:0] i_cfg_request_destination_mask,
    input wire [NM*(OW)-1:0] i_cfg_request_owner_id,
    input wire [NM*(K)-1:0] i_cfg_request_kernel_id,
    input wire [NM*(P)-1:0] i_cfg_request_package_id,
    input wire [NM*(CI)-1:0] i_cfg_request_context_id,
    input wire [NM*(V)-1:0] i_cfg_request_expected_version,
    input wire [NM*(WI)-1:0] i_cfg_request_word_index,
    input wire [NM*(D)-1:0] i_cfg_request_write_data,
    input wire [NM*(BY)-1:0] i_cfg_request_write_strobe,
    input wire [NM*(32)-1:0] i_cfg_request_expected_crc,
    input wire [NM*(TG)-1:0] i_cfg_request_tag,
    input wire [NM*(EP)-1:0] i_cfg_request_epoch,
    input wire [NM*(8)-1:0] i_cfg_request_flags,
    input wire [NM*(8)-1:0] i_cfg_request_protocol,
    output logic [NM-1:0] o_cfg_response_valid,
    input wire [NM-1:0] i_cfg_response_ready,
    output logic [NM*(C)-1:0] o_cfg_response_command,
    output logic [NM*(TI)-1:0] o_cfg_response_transaction_id,
    output logic [NM*(EI)-1:0] o_cfg_response_endpoint_id,
    output logic [NM*(ET)-1:0] o_cfg_response_endpoint_type,
    output logic [NM*(4)-1:0] o_cfg_response_status,
    output logic [NM*(8)-1:0] o_cfg_response_error_code,
    output logic [NM*(D)-1:0] o_cfg_response_read_data,
    output logic [NM*(CI)-1:0] o_cfg_response_context_id,
    output logic [NM*(V)-1:0] o_cfg_response_context_version,
    output logic [NM*(32)-1:0] o_cfg_response_crc,
    output logic [NM*(TG)-1:0] o_cfg_response_tag,
    output logic [NM*(EP)-1:0] o_cfg_response_epoch,
    output logic [NM*(1)-1:0] o_cfg_response_first,
    output logic [NM*(1)-1:0] o_cfg_response_last,
    output logic [NM*(1)-1:0] o_cfg_response_prepared,
    output logic [NM*(1)-1:0] o_cfg_response_committed,
    output logic [NM*(NE)-1:0] o_cfg_response_failure_mask,
    output logic [NM*(NE)-1:0] o_cfg_response_success_mask,
    output logic [NM*(NE)-1:0] o_cfg_response_timeout_mask,
    output logic [NM*(NE)-1:0] o_cfg_response_not_present_mask,
    input wire [NE-1:0] i_commit_destination_mask,
    input wire [P-1:0] i_commit_package_id,
    input wire [K-1:0] i_commit_kernel_id,
    input wire [OW-1:0] i_commit_owner_id,
    input wire [EP-1:0] i_commit_epoch,
    input wire [NE*CI-1:0] i_commit_context_ids,
    input wire [NE*V-1:0] i_commit_context_versions,
    output logic o_commit_ready,
    output logic o_execution_hold,
    output logic o_commit_complete,
    output logic o_commit_error,
    output logic o_idle,
    output logic o_drained,
    output logic o_flushed,
    output logic o_draining,
    output logic o_flushing,
    output logic o_fail_stop,
    output logic o_error,
    output logic o_counter_valid,
    output logic [NE-1:0] o_commit_ack_mask,
    output logic [NE-1:0] o_commit_failure_mask,
    output logic [NE-1:0] o_armed_mask,
    output logic [P-1:0] o_active_package_id,
    output logic [EP-1:0] o_active_commit_epoch,
    output logic [EP-1:0] o_configuration_epoch,
    output logic [OC-1:0] o_outstanding_transactions,
    output logic [7:0] o_error_code,
    output logic [EI-1:0] o_error_endpoint,
    output logic [TI-1:0] o_error_transaction,
    output logic [C-1:0] o_error_command,
    output logic [NE-1:0] o_endpoint_clock_enable,
    output logic [31:0] o_counter_value,
    input wire i_counter_read,
    input wire [5-1:0] i_counter_index,
    input wire [NE-1:0] i_endpoint_power_safe,
    input wire [NE-1:0] i_endpoint_quiescent,
    input wire [NE-1:0] i_endpoint_prepared_retained,
    input wire [NE-1:0] i_endpoint_cancel_ack,
    input wire [NE-1:0] i_endpoint_commit_ready,
    input wire [NE-1:0] i_endpoint_commit_ack_valid,
    output logic [NE-1:0] o_endpoint_cancel,
    output logic [NE-1:0] o_endpoint_commit_valid,
    output logic [NE-1:0] o_endpoint_commit_ack_ready,
    output logic [NE-1:0] o_endpoint_request_valid,
    input wire [NE-1:0] i_endpoint_request_ready,
    input wire [NE-1:0] i_endpoint_response_valid,
    output logic [NE-1:0] o_endpoint_response_ready,
    output logic [NE*(C)-1:0] o_endpoint_request_command,
    output logic [NE*(TI)-1:0] o_endpoint_request_transaction_id,
    output logic [NE*(32)-1:0] o_endpoint_request_sequence_id,
    output logic [NE*(TG)-1:0] o_endpoint_request_tag,
    output logic [NE*(OW)-1:0] o_endpoint_request_owner_id,
    output logic [NE*(K)-1:0] o_endpoint_request_kernel_id,
    output logic [NE*(P)-1:0] o_endpoint_request_package_id,
    output logic [NE*(EP)-1:0] o_endpoint_request_epoch,
    output logic [NE*(CI)-1:0] o_endpoint_request_context_id,
    output logic [NE*(V)-1:0] o_endpoint_request_expected_version,
    output logic [NE*(WI)-1:0] o_endpoint_request_word_index,
    output logic [NE*(D)-1:0] o_endpoint_request_write_data,
    output logic [NE*(BY)-1:0] o_endpoint_request_write_strobe,
    output logic [NE*(32)-1:0] o_endpoint_request_expected_crc,
    input wire [NE*(TI)-1:0] i_endpoint_response_transaction_id,
    input wire [NE*(32)-1:0] i_endpoint_response_sequence_id,
    input wire [NE*(EP)-1:0] i_endpoint_response_epoch,
    input wire [NE*(4)-1:0] i_endpoint_response_status,
    input wire [NE*(8)-1:0] i_endpoint_response_error_code,
    input wire [NE*(D)-1:0] i_endpoint_response_read_data,
    input wire [NE*(V)-1:0] i_endpoint_response_context_version,
    input wire [NE*(32)-1:0] i_endpoint_response_image_crc,
    input wire [NE*(1)-1:0] i_endpoint_response_prepared,
    output logic [NE*(CI)-1:0] o_endpoint_commit_context_id,
    input wire [NE*(CI)-1:0] i_endpoint_active_context_id,
    output logic [NE*(V)-1:0] o_endpoint_commit_context_version,
    input wire [NE*(V)-1:0] i_endpoint_active_context_version,
    output logic [NE*(P)-1:0] o_endpoint_commit_package_id,
    input wire [NE*(P)-1:0] i_endpoint_active_package_id,
    output logic [NE*(OW)-1:0] o_endpoint_commit_owner_id,
    input wire [NE*(OW)-1:0] i_endpoint_active_owner_id,
    output logic [NE*(K)-1:0] o_endpoint_commit_kernel_id,
    input wire [NE*(K)-1:0] i_endpoint_active_kernel_id,
    output logic [NE*(EP)-1:0] o_endpoint_commit_epoch,
    input wire [NE*(EP)-1:0] i_endpoint_active_epoch,
    output logic [NE*(32)-1:0] o_endpoint_commit_image_crc,
    input wire [NE*(32)-1:0] i_endpoint_active_image_crc,
    input wire [NE-1:0] i_endpoint_commit_error,
    output logic [NM*32-1:0] o_cfg_response_sequence_id,
    output logic [NM*8-1:0] o_cfg_response_protocol,
    output logic [NM*32-1:0] o_cfg_response_packet_crc,
    output logic [NM-1:0] o_cfg_response_transaction_success
);
    import configuration_network_pkg::*;

    function automatic logic [NE*(ET)-1:0] default_types();
        logic [NE*(ET)-1:0] result;
        int e;
        result = '0;

        for (e = 0; e < NE; e++) result[e*(ET)+:(ET)] = ET'(e < NT ? 0 : 1);

        return result;
    endfunction

    function automatic logic [NE*(EI)-1:0] default_ids();
        logic [NE*(EI)-1:0] result;
        int e;
        result = '0;

        for (e = 0; e < NE; e++) result[e*(EI)+:(EI)] = EI'(e);

        return result;
    endfunction

    function automatic logic [NE*(CAP)-1:0] default_capabilities();
        logic [NE*(CAP)-1:0] result;
        int e;
        result = '0;

        for (e = 0; e < NE; e++) result[e*(CAP)+:(CAP)] = CAP'(SUPPORT_READBACK ? 32'h1fe
            : 32'h1fa);

        return result;
    endfunction

    function automatic logic [NE*(OW+4)-1:0] default_permissions();
        logic [NE*(OW+4)-1:0] result;
        int e;
        result = '0;

        for (e = 0; e < NE; e++) result[e*(OW+4)+:(OW+4)] = (OW+4)'(15) << OW;

        return result;
    endfunction

    function automatic logic [NE*(32)-1:0] default_words();
        logic [NE*(32)-1:0] result;
        int e;
        result = '0;

        for (e = 0; e < NE; e++) result[e*(32)+:(32)] = 32'd4;

        return result;
    endfunction

    function automatic logic [NE*(32)-1:0] default_contexts();
        logic [NE*(32)-1:0] result;
        int e;
        result = '0;

        for (e = 0; e < NE; e++) result[e*(32)+:(32)] = 32'd4;

        return result;
    endfunction

    typedef struct packed {
        logic [7:0] flags;
        logic [7:0] protocol;
        logic [31:0] sequence_id;
        logic [MI-1:0] master;
        logic [NE-1:0] destination;
        logic [31:0] image_crc;
        logic [BY-1:0] strobe;
        logic [D-1:0] write_data;
        logic [WI-1:0] word_index;
        logic [V-1:0] version;
        logic [CI-1:0] context_id;
        logic [EP-1:0] epoch;
        logic [P-1:0] package_id;
        logic [K-1:0] kernel;
        logic [OW-1:0] owner;
        logic [TG-1:0] tag;
        logic [TI-1:0] transaction;
        logic [C-1:0] command;
    } command_packet_t;

    typedef struct packed {
        logic committed;
        logic prepared;
        logic [7:0] protocol;
        logic [31:0] sequence_id;
        logic [7:0] error_code;
        logic [3:0] status;
        logic [EP-1:0] epoch;
        logic [31:0] image_crc;
        logic [D-1:0] read_data;
        logic [V-1:0] version;
        logic [CI-1:0] context_id;
        logic [EI-1:0] endpoint;
        logic [TG-1:0] tag;
        logic [TI-1:0] transaction;
        logic [C-1:0] command;
    } response_t;

    typedef struct packed {
        logic valid;
        logic first;
        logic synthetic;
        logic [NE-1:0] targets;
        logic [NE-1:0] done;
        logic [NE-1:0] success;
        logic [NE-1:0] failure;
        logic [NE-1:0] timeout_mask;
        logic [NE-1:0] absent;
        logic [NE*RB-1:0] results;
        logic [31:0] timer;
        command_packet_t request;
    } slot_t;

    localparam int SLOT = $bits(slot_t);

    typedef struct packed {
        logic valid;
        logic [CI-1:0] context_id;
        logic [V-1:0] version;
        logic [OW-1:0] owner;
        logic [K-1:0] kernel;
        logic [P-1:0] package_id;
        logic [31:0] crc;
    } prepared_t;

    localparam int PREP = $bits(prepared_t);

    typedef struct packed {
        logic [NS*SLOT-1:0] entries;
        logic [NE*PREP-1:0] prepared;
        logic [OC-1:0] count;
        logic [SI-1:0] head;
        logic [SI-1:0] tail;
        logic [31:0] sequence_id;
        logic [EP-1:0] epoch;
        logic drain;
        logic bootstrapped;
        logic [31:0] flush_generation;
        logic flushing;
        logic flush_seen;
        logic flushed;
        logic flush_response;
        command_packet_t flush_command;
        logic [NE-1:0] cancel;
        logic recovery;
        logic fatal;
        logic [7:0] error_code;
        logic [EI-1:0] error_endpoint;
        logic [TI-1:0] error_transaction;
        logic [C-1:0] error_command;
        commit_phase_t phase;
        logic [NE-1:0] commit_mask;
        logic [NE-1:0] ack_mask;
        logic [NE-1:0] commit_failure;
        logic [P-1:0] commit_package;
        logic [K-1:0] commit_kernel;
        logic [OW-1:0] commit_owner;
        logic [EP-1:0] commit_epoch;
        logic [31:0] commit_timer;
        logic active_valid;
        logic [NE-1:0] active_mask;
        logic [P-1:0] active_package;
        logic [EP-1:0] active_epoch;
        logic released;
        logic commit_complete;
    } control_t;

    typedef struct packed {
        logic [31:0] generation;
        logic [MI-1:0] master;
        logic [TG-1:0] tag;
        logic first;
        logic last;
        logic synthetic;
        logic [NE-1:0] failure;
        logic [NE-1:0] success;
        logic [NE-1:0] timeout_mask;
        logic [NE-1:0] absent;
        response_t response;
    } retirement_t;

    localparam int RETIRE = $bits(retirement_t);

    function automatic logic descriptors_valid();
        int e;
        int other;

        for (e = 0; e < NE; e++) begin
            if (ENDPOINT_WORD_COUNT_TABLE[e*32+:32] < 1 ||
                ENDPOINT_WORD_COUNT_TABLE[e*32+:32] > 65536 ||
                ENDPOINT_CONTEXT_DEPTH_TABLE[e*32+:32] < 1 ||
                ENDPOINT_CONTEXT_DEPTH_TABLE[e*32+:32] > 256 ||
                (64'd1 << CI) < 64'(ENDPOINT_CONTEXT_DEPTH_TABLE[e*32+:32]) ||
                (64'd1 << WI) < 64'(ENDPOINT_WORD_COUNT_TABLE[e*32+:32])) return 1'b0;

            for (other = 0; other < e; other++)
                if (ENDPOINT_ID_TABLE[e*EI+:EI] == ENDPOINT_ID_TABLE[other*EI+:EI])
                    return 1'b0;
        end

        return ENDPOINT_CLOCK_DOMAIN_TABLE == 0 && COMMIT_DOMAIN_TABLE == 0;
    endfunction

    localparam bit PARAMETERS_VALID =
        ((TOPOLOGY_PROFILE >= 0 && TOPOLOGY_PROFILE <= 2) === 1'b1) &&
        ((NUM_MASTERS >= 1 && NUM_MASTERS <= 4) === 1'b1) &&
        ((NUM_ENDPOINTS >= 1 && NUM_ENDPOINTS <= 128) === 1'b1) &&
        ((NUM_TILE_ENDPOINTS >= 0 && NUM_TILE_ENDPOINTS <= 64) === 1'b1) &&
        ((NUM_INFRA_ENDPOINTS >= 0 && NUM_INFRA_ENDPOINTS <= 64) === 1'b1) &&
        ((TREE_BRANCH_FACTOR >= 2 && TREE_BRANCH_FACTOR <= 4) === 1'b1) &&
        ((CONFIG_DATA_WIDTH >= 8 && CONFIG_DATA_WIDTH <= 256) === 1'b1) &&
        ((CONFIG_FLIT_WIDTH >= 8 && CONFIG_FLIT_WIDTH <= 256) === 1'b1) &&
        ((ENDPOINT_ID_WIDTH >= 1 && ENDPOINT_ID_WIDTH <= 16) === 1'b1) &&
        ((ENDPOINT_TYPE_WIDTH >= 1 && ENDPOINT_TYPE_WIDTH <= 8) === 1'b1) &&
        ((COMMAND_WIDTH >= 4 && COMMAND_WIDTH <= 8) === 1'b1) &&
        ((CONTEXT_ID_WIDTH >= 1 && CONTEXT_ID_WIDTH <= 16) === 1'b1) &&
        ((CONTEXT_VERSION_WIDTH >= 1 && CONTEXT_VERSION_WIDTH <= 32) === 1'b1) &&
        ((OWNER_ID_WIDTH >= 1 && OWNER_ID_WIDTH <= 32) === 1'b1) &&
        ((KERNEL_ID_WIDTH >= 1 && KERNEL_ID_WIDTH <= 32) === 1'b1) &&
        ((PACKAGE_ID_WIDTH >= 1 && PACKAGE_ID_WIDTH <= 64) === 1'b1) &&
        ((CONFIG_EPOCH_WIDTH >= 1 && CONFIG_EPOCH_WIDTH <= 16) === 1'b1) &&
        ((TRANSACTION_ID_WIDTH >= 1 && TRANSACTION_ID_WIDTH <= 16) === 1'b1) &&
        ((TAG_WIDTH >= 1 && TAG_WIDTH <= 32) === 1'b1) &&
        ((WORD_INDEX_WIDTH >= 1 && WORD_INDEX_WIDTH <= 32) === 1'b1) &&
        ((BYTE_STROBE_WIDTH >= 1 && BYTE_STROBE_WIDTH <= 32) === 1'b1) &&
        ((COMMAND_QUEUE_DEPTH >= 1 && COMMAND_QUEUE_DEPTH <= 32) === 1'b1) &&
        ((RESPONSE_QUEUE_DEPTH >= 1 && RESPONSE_QUEUE_DEPTH <= 32) === 1'b1) &&
        ((BRANCH_BUFFER_DEPTH >= 1 && BRANCH_BUFFER_DEPTH <= 8) === 1'b1) &&
        ((ENDPOINT_QUEUE_DEPTH >= 1 && ENDPOINT_QUEUE_DEPTH <= 8) === 1'b1) &&
        ((MAX_OUTSTANDING_TRANSACTIONS >= 1 && MAX_OUTSTANDING_TRANSACTIONS <= 16) === 1'b1) &&
        ((TRANSACTION_TIMEOUT_CYCLES >= 8 && TRANSACTION_TIMEOUT_CYCLES <= 1048576) === 1'b1) &&
        ((COMMIT_TIMEOUT_CYCLES >= 4 && COMMIT_TIMEOUT_CYCLES <= 1048576) === 1'b1) &&
        (SUPPORT_MULTICAST === 0 || SUPPORT_MULTICAST === 1) &&
        (SUPPORT_READBACK === 0 || SUPPORT_READBACK === 1) &&
        (ENABLE_PACKET_CRC === 0 || ENABLE_PACKET_CRC === 1) &&
        (ASYNC_RESET === 0 || ASYNC_RESET === 1) &&
        (USE_ALLOCATION_OWNER === 0 || USE_ALLOCATION_OWNER === 1) &&
        SUPPORT_ASYNC_ENDPOINTS === 0 &&
        SUPPORT_PACKET_RETRY === 0 &&
        RESPONSE_ORDERING === 0 &&
        (CONTROL_PROTECTION === 0 || CONTROL_PROTECTION === 1 || CONTROL_PROTECTION === 2) &&
        PACKET_CRC_WIDTH === 32 &&
        IMAGE_CRC_WIDTH === 32 &&
        STATUS_WIDTH === 4 &&
        ERROR_CODE_WIDTH === 8 &&
        (NUM_TILE_ENDPOINTS + NUM_INFRA_ENDPOINTS == NUM_ENDPOINTS) &&
        D % 8 == 0 && F % 8 == 0 && BY == D / 8 &&
        (64'd1 << EI) >= NE && (64'd1 << TI) >= NS &&
        $bits(ENDPOINT_PRESENT_MASK) == (NE) && (^ENDPOINT_PRESENT_MASK !== 1'bx) &&
        $bits(ENDPOINT_TYPE_TABLE) == (NE*ET) && (^ENDPOINT_TYPE_TABLE !== 1'bx) &&
        $bits(ENDPOINT_ID_TABLE) == (NE*EI) && (^ENDPOINT_ID_TABLE !== 1'bx) &&
        $bits(ENDPOINT_CAPABILITY_TABLE) == (NE*CAP) && (^ENDPOINT_CAPABILITY_TABLE !== 1'bx) &&
        $bits(ENDPOINT_PERMISSION_TABLE) == (NE*(OW+4)) && (^ENDPOINT_PERMISSION_TABLE !== 1'bx) &&
        $bits(ENDPOINT_CLOCK_DOMAIN_TABLE) == (NE) && (^ENDPOINT_CLOCK_DOMAIN_TABLE !== 1'bx) &&
        $bits(ENDPOINT_WORD_COUNT_TABLE) == (NE*32) && (^ENDPOINT_WORD_COUNT_TABLE !== 1'bx) &&
        $bits(ENDPOINT_CONTEXT_DEPTH_TABLE) == (NE*32)
            && (^ENDPOINT_CONTEXT_DEPTH_TABLE !== 1'bx) &&
        $bits(ENDPOINT_SCHEMA_TABLE) == (NE*32) && (^ENDPOINT_SCHEMA_TABLE !== 1'bx) &&
        $bits(MULTICAST_GROUP_TABLE) == (NE*NE) && (^MULTICAST_GROUP_TABLE !== 1'bx) &&
        $bits(COMMIT_DOMAIN_TABLE) == (NE) && (^COMMIT_DOMAIN_TABLE !== 1'bx) &&
        descriptors_valid();

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        configuration_network_parameters_must_be_valid invalid_parameters ();
    end else begin : g_network
        control_t q;
        control_t n;
        wire state_bad;
        wire [$bits(control_t)-1:0] raw_control;

        always @* q = raw_control;

        wire run = i_reset_n === 1'b1;
        wire known_control = (^{i_drain, i_flush, i_resume, i_error_clear, i_test_enable,
            i_scan_enable, i_execution_release, i_release_safe, i_commit_valid} !== 1'bx);
        wire integrity_latched;
        wire transport = run && known_control && q.bootstrapped &&!q.flushing &&!q.fatal
            &&!state_bad &&
            !integrity_latched && i_test_enable === 1'b0 && i_scan_enable === 1'b0;
        wire flush_all = run && (q.flushing || i_flush === 1'b1);
        wire [NS*SLOT-1:0] slots = q.entries;
        wire [NE*PREP-1:0] prepared = q.prepared;
        logic [NS*SLOT-1:0] next_slots;
        logic [NE*PREP-1:0] next_prepared;
        wire [NE-1:0] cancel_mask = q.cancel | ((q.flushing || !q.bootstrapped)
            ? ENDPOINT_PRESENT_MASK : '0);
        wire [NE-1:0] endpoint_idle;
        wire [NE-1:0] endpoint_bad;
        wire [NE-1:0] endpoint_protocol_error;
        wire [NE-1:0] endpoint_frame_error;
        wire [NE-1:0] native_take;
        wire [NE-1:0] native_complete;
        wire [NE-1:0] leaf_forward_valid;
        wire [NE-1:0] leaf_forward_ready;
        wire [NE*FL-1:0] raw_leaf_forward;
        logic [NE*FL-1:0] leaf_forward_flit;

        always @* leaf_forward_flit = raw_leaf_forward;

        wire [NE-1:0] leaf_reverse_valid;
        wire [NE-1:0] leaf_reverse_ready;
        wire [NE*RL-1:0] raw_leaf_reverse;
        logic [NE*RL-1:0] leaf_reverse_flit;

        always @* leaf_reverse_flit = raw_leaf_reverse;

        wire forward_valid;
        wire forward_ready;
        wire [FL-1:0] forward_flit;
        wire reverse_valid;
        wire reverse_ready;
        wire [RL-1:0] reverse_flit;
        wire tree_idle;
        wire tree_bad;
        wire [31:0] forward_transfers;
        wire [31:0] reverse_transfers;
        wire [31:0] command_count;
        wire command_queue_bad;
        wire command_valid;
        wire command_ready;
        wire [CB-1:0] command_bits;
        command_packet_t queued_command;
        command_packet_t ingress_command;
        logic [7:0] admission_error;
        logic [NE-1:0] ingress_targets;
        wire [NE-1:0] ingress_destination = ingress_command.destination;
        wire ingress_fire;
        wire command_push = ingress_fire && admission_error == CFG_OK &&
            ingress_command.command >= C'(CFG_WRITE) &&
            ingress_command.command <= C'(CFG_ABORT_PREPARE) &&
            (|(ingress_command.destination & ENDPOINT_PRESENT_MASK));
        wire grant;
        wire [NM-1:0] grant_mask;
        wire [MI-1:0] grant_master;
        wire ingress_arbiter_bad;
        wire [CP-33:0] command_body = (CP-32)'(command_bits);
        wire [31:0] command_crc;
        wire [CP-1:0] command_packet = {
            ENABLE_PACKET_CRC ? command_crc : 32'b0, command_body};
        wire serializer_idle;
        wire serializer_bad;
        wire root_valid;
        wire root_ready;
        wire [RP-1:0] root_packet;
        wire [ENV-1:0] root_envelope;
        wire root_frame_error;
        wire root_receiver_idle;
        wire root_receiver_bad;
        wire [31:0] root_crc;
        response_t root_response;
        wire root_crc_ok = (^root_packet !== 1'bx) &&
            (root_packet[0+:RP-32] >> RB) == 0 && root_packet[RP-32+:32] ==
            (ENABLE_PACKET_CRC ? root_crc : 32'b0);
        wire [31:0] retirement_count;
        wire retirement_bad;
        wire retirement_ready;
        wire retirement_valid;
        wire [RETIRE-1:0] retirement_bits;
        retirement_t retired;
        retirement_t retiring;
        logic retire_valid;
        wire retire_fire = retire_valid && retirement_ready;
        wire idle_transport = tree_idle && serializer_idle && root_receiver_idle &&
            (&endpoint_idle) && command_count == 0;
        wire all_idle = idle_transport && q.count == 0 && retirement_count == 0;
        wire integrity_bad = state_bad || tree_bad || serializer_bad || root_receiver_bad ||
            command_queue_bad || retirement_bad || (|endpoint_bad) || ingress_arbiter_bad;
        logic [NE-1:0] armed;
        logic commit_identity_ok;
        wire commit_fire = i_commit_valid === 1'b1 && o_commit_ready;
        wire commit_send;
        wire response_fire;
        logic [7:0] runtime_code;
        logic [EI-1:0] runtime_endpoint;
        logic [TI-1:0] runtime_transaction;
        logic [C-1:0] runtime_command;

        function automatic response_t response_for(
            input command_packet_t request,
            input int endpoint,
            input logic [3:0] status,
            input logic [7:0] code
        );
            response_t result;
            result = '0;
            result.command = request.command;
            result.transaction = request.transaction;
            result.tag = request.tag;
            result.endpoint = ENDPOINT_ID_TABLE[endpoint*EI+:EI];
            result.context_id = request.context_id;
            result.epoch = request.epoch;
            result.sequence_id = request.sequence_id;
            result.protocol = 8'd1;
            result.status = status;
            result.error_code = code;

            return result;
        endfunction

        function automatic logic [EI-1:0] first_endpoint(input logic [NE-1:0] mask);
            logic [EI-1:0] result;
            logic found;
            result = '1;
            found = 1'b0;

            for (int e = 0; e < NE; e++)
                if (mask[e] && (!found || ENDPOINT_ID_TABLE[e*EI+:EI] < result)) begin
                    result = ENDPOINT_ID_TABLE[e*EI+:EI];
                    found = 1'b1;
                end

            return result;
        endfunction

        round_robin_arbiter #(
            .NUM_REQUESTERS(NM),
            .HAS_LOCK(0),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_ingress_arbiter (
            .i_clk(i_clk),
            .i_rstb(i_reset_n),
            .i_request(i_cfg_request_valid),
            .i_eligible('1),
            .i_lock('0),
            .i_accept(ingress_fire),
            .i_flush(flush_all),
            .o_grant_valid(grant),
            .o_grant_onehot(grant_mask),
            .o_grant_index(grant_master),
            .o_grant_lock(),
            .o_grant_accepted(),
            .o_contended(),
            .o_pending(),
            .o_locked(),
            .o_lock_owner(),
            .o_protocol_error(ingress_arbiter_bad)
        );

        always @* begin
            ingress_command = '0;
            ingress_command.command = i_cfg_request_command[int'(grant_master)*C+:C];
            ingress_command.transaction = TI'(q.sequence_id);
            ingress_command.tag = i_cfg_request_tag[int'(grant_master)*TG+:TG];
            ingress_command.owner = i_cfg_request_owner_id[int'(grant_master)*OW+:OW];
            ingress_command.kernel = i_cfg_request_kernel_id[int'(grant_master)*K+:K];
            ingress_command.package_id = i_cfg_request_package_id[int'(grant_master)*P+:P];
            ingress_command.epoch = i_cfg_request_epoch[int'(grant_master)*EP+:EP];
            ingress_command.context_id = i_cfg_request_context_id[int'(grant_master)*CI+:CI];
            ingress_command.version = i_cfg_request_expected_version[int'(grant_master)*V+:V];
            ingress_command.word_index = i_cfg_request_word_index[int'(grant_master)*WI+:WI];
            ingress_command.write_data = i_cfg_request_write_data[int'(grant_master)*D+:D];
            ingress_command.strobe = i_cfg_request_write_strobe[int'(grant_master)*BY+:BY];
            ingress_command.image_crc = i_cfg_request_expected_crc[int'(grant_master)*32+:32];
            ingress_command.destination = i_cfg_request_destination_mask[int'(grant_master)*NE+:NE];
            ingress_command.master = grant_master;
            ingress_command.sequence_id = q.sequence_id;
            ingress_command.protocol = i_cfg_request_protocol[int'(grant_master)*8+:8];
            ingress_command.flags = i_cfg_request_flags[int'(grant_master)*8+:8];
        end

        always @* begin
            int selected;
            logic [31:0] schema;
            logic schema_valid;
            logic compatible_group;
            selected = $countones(ingress_command.destination);
            ingress_targets = ingress_command.destination;

            if (ingress_targets == 0) ingress_targets[0] = 1'b1;

            admission_error = CFG_OK;
            schema = '0;
            schema_valid = 1'b0;
            compatible_group = 1'b0;

            for (int g = 0; g < NE; g++)
                if ((ingress_command.destination & ~MULTICAST_GROUP_TABLE[g*NE+:NE]) == 0)
                    compatible_group = 1'b1;

            if (^ingress_command === 1'bx || ingress_command.protocol != 1 ||
                (ingress_command.flags & 8'hfe) != 0) admission_error = CFG_ERR_UNKNOWN;
            else if (ingress_command.epoch != q.epoch) admission_error = CFG_ERR_EPOCH;
            else if (USE_ALLOCATION_OWNER == 1 && (i_allocation_owner_valid !== 1'b1 ||
                ingress_command.owner !== i_allocation_owner_id))
                admission_error = CFG_ERR_PERMISSION;
            else if (ingress_command.command > C'(CFG_FLUSH) ||
                ingress_command.command == C'(CFG_COMMIT)) admission_error = CFG_ERR_COMMAND;
            else if (ingress_command.command >= C'(CFG_WRITE) &&
                ingress_command.command <= C'(CFG_ABORT_PREPARE) && selected == 0)
                admission_error = CFG_ERR_DESTINATION;
            else if ((ingress_command.command == C'(CFG_READ) ||
                ingress_command.command == C'(CFG_QUERY)) && selected != 1)
                admission_error = CFG_ERR_DESTINATION;
            else if (selected > 1 && (!SUPPORT_MULTICAST || !compatible_group))
                admission_error = CFG_ERR_DESTINATION;
            else if (ingress_command.command == C'(CFG_READ) &&!SUPPORT_READBACK)
                admission_error = CFG_ERR_CAPABILITY;
            else if ((ingress_command.command == C'(CFG_NOP) ||
                ingress_command.command >= C'(CFG_DRAIN)) && selected != 0)
                admission_error = CFG_ERR_DESTINATION;

            for (int e = 0; e < NE; e++) begin
                logic [OW+3:0] permission;
                permission = ENDPOINT_PERMISSION_TABLE[e*(OW+4)+:(OW+4)];

                if (ingress_destination[e] && ENDPOINT_PRESENT_MASK[e] &&
                    admission_error == CFG_OK) begin

                    if (!ENDPOINT_CAPABILITY_TABLE[e*CAP+int'(ingress_command.command)])
                        admission_error = CFG_ERR_CAPABILITY;
                    else if ((USE_ALLOCATION_OWNER == 1 ?
                        (i_allocation_owner_valid !== 1'b1 ||
                        ingress_command.owner !== i_allocation_owner_id) :
                        (ingress_command.owner != permission[0+:OW] &&
                        !(ingress_command.flags[0] && permission[OW+3] &&
                            ingress_command.owner == 0))) ||
                        (ingress_command.command == C'(CFG_WRITE) &&!permission[OW+1]) ||
                        (ingress_command.command == C'(CFG_READ) &&!permission[OW]) ||
                        (ingress_command.command >= C'(CFG_VALIDATE) &&!permission[OW+2]))
                        admission_error = CFG_ERR_PERMISSION;
                    else if (i_endpoint_power_safe[e] !== 1'b1) admission_error = CFG_ERR_POWER;
                    else if (int'(ingress_command.context_id) >=
                        int'(ENDPOINT_CONTEXT_DEPTH_TABLE[e*32+:32]))
                        admission_error = CFG_ERR_CONTEXT;
                    else if ((ingress_command.command == C'(CFG_WRITE) ||
                        ingress_command.command == C'(CFG_READ)) &&
                        64'(ingress_command.word_index) >=
                        64'(ENDPOINT_WORD_COUNT_TABLE[e*32+:32])) admission_error = CFG_ERR_WORD;

                    if (ingress_command.command == C'(CFG_WRITE)) begin
                        if (schema_valid && schema != ENDPOINT_SCHEMA_TABLE[e*32+:32])
                            admission_error = CFG_ERR_SCHEMA;

                        schema_valid = 1'b1;
                        schema = ENDPOINT_SCHEMA_TABLE[e*32+:32];
                    end
                end
            end
        end

        wire ingress_enabled = transport &&!q.recovery &&!q.drain && i_drain === 1'b0 &&
            i_flush === 1'b0 && i_commit_valid === 1'b0 && q.phase == COMMIT_IDLE &&
            i_test_enable === 1'b0 && i_scan_enable === 1'b0 &&
            q.count < OC'(NS) && q.sequence_id != 32'hffffffff;

        always @* begin
            o_cfg_request_ready = '0;

            if (ingress_enabled && grant && (^ingress_command !== 1'bx) &&
                (admission_error != CFG_OK || ingress_command.command == 0 ||
                    ingress_command.command >= C'(CFG_DRAIN) || command_count < CQ))
                o_cfg_request_ready = grant_mask;
        end

        assign ingress_fire = |(i_cfg_request_valid & o_cfg_request_ready);
        assign queued_command = command_bits;

        static_mesh_queue #(
            .WIDTH(CB),
            .DEPTH(CQ),
            .PROTECTION(CONTROL_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_command_queue (
            .i_clk(i_clk),
            .i_reset_n(i_reset_n),
            .i_flush(flush_all),
            .i_valid(command_push),
            .o_ready(),
            .i_data(ingress_command),
            .o_valid(command_valid),
            .i_ready(command_ready),
            .o_data(command_bits),
            .o_count(command_count),
            .o_bad(command_queue_bad)
        );

        configuration_network_crc #(.WIDTH(CP - 32)) u_command_crc (
            .i_data(command_body),
            .o_crc(command_crc)
        );

        configuration_network_serializer #(
            .WIDTH(CP),
            .FLIT(F),
            .ENVELOPE(ENV),
            .PROTECTION(CONTROL_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_command_serializer (
            .i_clk(i_clk),
            .i_reset_n(i_reset_n),
            .i_flush(flush_all),
            .i_run(transport),
            .i_valid(command_valid),
            .o_ready(command_ready),
            .i_packet(command_packet),
            .i_envelope({queued_command.master, queued_command.sequence_id, queued_command.epoch,
                queued_command.transaction, queued_command.destination}),
            .o_valid(forward_valid),
            .i_ready(forward_ready),
            .o_flit(forward_flit),
            .o_idle(serializer_idle),
            .o_bad(serializer_bad)
        );

        configuration_network_tree #(
            .ENDPOINTS(NE),
            .BRANCH(BF),
            .PROFILE(TOPOLOGY_PROFILE),
            .FORWARD(FL),
            .REVERSE(RL),
            .DESTINATION_OFFSET(F + 2 + CX),
            .LAST_OFFSET(F + 1),
            .DEPTH(BQ),
            .PROTECTION(CONTROL_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET),
            .PRESENT(ENDPOINT_PRESENT_MASK)
        ) u_tree (
            .i_clk(i_clk),
            .i_reset_n(i_reset_n),
            .i_flush(flush_all),
            .i_run(transport),
            .i_valid(forward_valid),
            .o_ready(forward_ready),
            .i_flit(forward_flit),
            .o_endpoint_valid(leaf_forward_valid),
            .i_endpoint_ready(leaf_forward_ready),
            .o_endpoint_flit(raw_leaf_forward),
            .i_response_valid(leaf_reverse_valid),
            .o_response_ready(leaf_reverse_ready),
            .i_response_flit(leaf_reverse_flit),
            .o_valid(reverse_valid),
            .i_ready(reverse_ready),
            .o_flit(reverse_flit),
            .o_idle(tree_idle),
            .o_bad(tree_bad),
            .o_forward_transfers(forward_transfers),
            .o_reverse_transfers(reverse_transfers)
        );

        for (genvar e = 0; e < NE; e++) begin : g_endpoint
            if (ENDPOINT_PRESENT_MASK[e]) begin : g_present
                typedef struct packed {
                    logic busy;
                    logic sent;
                    logic result_valid;
                    logic protocol_error;
                    command_packet_t request;
                    response_t response;
                } endpoint_state_t;

                endpoint_state_t state;
                endpoint_state_t next_state;
                wire [$bits(endpoint_state_t)-1:0] raw_state;
                always @* state = raw_state;
                wire [CP-1:0] packet;
                wire [ENV-1:0] envelope;
                wire packet_valid;
                wire packet_ready;
                wire frame_error;
                wire receiver_idle;
                wire receiver_bad;
                wire queue_valid;
                wire queue_ready;
                wire [CP+ENV:0] queue_data;
                wire [31:0] queue_count;
                wire queue_bad;
                wire [CP-1:0] offered_packet = queue_data[0+:CP];
                wire [ENV-1:0] offered_envelope = queue_data[CP+:ENV];
                wire offered_frame_error = queue_data[CP+ENV];
                command_packet_t offered;
                wire [31:0] crc;
                wire crc_ok = (^offered_packet !== 1'bx) &&
                    (offered_packet[0+:CP-32] >> CB) == 0 && offered_packet[CP-32+:32] ==
                        (ENABLE_PACKET_CRC ? crc : 32'b0);
                wire envelope_ok = offered_envelope == {offered.master, offered.sequence_id,
                    offered.epoch, offered.transaction, offered.destination};
                wire state_integrity;
                wire send_ready;
                wire send_idle;
                wire send_bad;
                wire [31:0] response_crc;
                command_packet_t saved_request;
                response_t saved_response;
                assign saved_request = state.request;
                assign saved_response = state.response;
                wire [RP-33:0] response_body = (RP-32)'(state.response);
                wire [RP-1:0] response_packet = {
                    ENABLE_PACKET_CRC ? response_crc : 32'b0, response_body};
                wire enabled = transport &&!state_integrity &&!cancel_mask[e] && i_flush === 1'b0;
                wire response_known = (^{i_endpoint_response_transaction_id[e*TI+:TI],
                    i_endpoint_response_sequence_id[e*32+:32],
                    i_endpoint_response_epoch[e*EP+:EP], i_endpoint_response_status[e*4+:4],
                    i_endpoint_response_error_code[e*8+:8],
                    i_endpoint_response_read_data[e*D+:D],
                    i_endpoint_response_context_version[e*V+:V],
                    i_endpoint_response_image_crc[e*32+:32],
                    i_endpoint_response_prepared[e]} !== 1'bx);
                wire response_matches = response_known &&
                    i_endpoint_response_transaction_id[e*TI+:TI] == state.request.transaction &&
                    i_endpoint_response_sequence_id[e*32+:32] == state.request.sequence_id &&
                    i_endpoint_response_epoch[e*EP+:EP] == state.request.epoch;
                assign offered = offered_packet[0+:CB];
                assign queue_ready = enabled &&!state.busy &&!state.result_valid;
                assign o_endpoint_request_valid[e] = enabled && state.busy &&!state.sent &&
                    i_endpoint_power_safe[e] === 1'b1;
                assign o_endpoint_response_ready[e] = run && (cancel_mask[e] ||
                    (transport &&!state.result_valid));
                assign native_take[e] = o_endpoint_request_valid[e] &&
                    i_endpoint_request_ready[e] === 1'b1;
                assign native_complete[e] = enabled && i_endpoint_response_valid[e] === 1'b1 &&
                    o_endpoint_response_ready[e] && state.busy && state.sent;
                assign endpoint_protocol_error[e] = state.protocol_error;
                assign endpoint_frame_error[e] = frame_error;
                assign endpoint_idle[e] = receiver_idle && queue_count == 0 &&!state.busy &&
                    !state.result_valid && send_idle;
                assign endpoint_bad[e] = state_integrity || receiver_bad || queue_bad || send_bad;
                assign o_endpoint_clock_enable[e] = run && (!endpoint_idle[e] || armed[e] ||
                    q.phase != COMMIT_IDLE || !q.bootstrapped || q.flushing || q.recovery ||
                    i_test_enable === 1'b1 || i_scan_enable === 1'b1 || state_bad || integrity_bad);
                assign o_endpoint_request_command[e*C+:C] =
                    o_endpoint_request_valid[e] ? state.request.command : '0;
                assign o_endpoint_request_transaction_id[e*TI+:TI] =
                    o_endpoint_request_valid[e] ? state.request.transaction : '0;
                assign o_endpoint_request_sequence_id[e*32+:32] =
                    o_endpoint_request_valid[e] ? state.request.sequence_id : '0;
                assign o_endpoint_request_tag[e*TG+:TG] =
                    o_endpoint_request_valid[e] ? state.request.tag : '0;
                assign o_endpoint_request_owner_id[e*OW+:OW] =
                    o_endpoint_request_valid[e] ? state.request.owner : '0;
                assign o_endpoint_request_kernel_id[e*K+:K] =
                    o_endpoint_request_valid[e] ? state.request.kernel : '0;
                assign o_endpoint_request_package_id[e*P+:P] =
                    o_endpoint_request_valid[e] ? state.request.package_id : '0;
                assign o_endpoint_request_epoch[e*EP+:EP] =
                    o_endpoint_request_valid[e] ? state.request.epoch : '0;
                assign o_endpoint_request_context_id[e*CI+:CI] =
                    o_endpoint_request_valid[e] ? state.request.context_id : '0;
                assign o_endpoint_request_expected_version[e*V+:V] =
                    o_endpoint_request_valid[e] ? state.request.version : '0;
                assign o_endpoint_request_word_index[e*WI+:WI] =
                    o_endpoint_request_valid[e] ? state.request.word_index : '0;
                assign o_endpoint_request_write_data[e*D+:D] =
                    o_endpoint_request_valid[e] ? state.request.write_data : '0;
                assign o_endpoint_request_write_strobe[e*BY+:BY] =
                    o_endpoint_request_valid[e] ? state.request.strobe : '0;
                assign o_endpoint_request_expected_crc[e*32+:32] =
                    o_endpoint_request_valid[e] ? state.request.image_crc : '0;

                configuration_network_receiver #(
                    .WIDTH(CP),
                    .FLIT(F),
                    .ENVELOPE(ENV),
                    .PROTECTION(CONTROL_PROTECTION),
                    .ASYNC_RESET(ASYNC_RESET)
                ) u_receiver (
                    .i_clk(i_clk),
                    .i_reset_n(i_reset_n),
                    .i_flush(flush_all || cancel_mask[e]),
                    .i_run(transport),
                    .i_valid(leaf_forward_valid[e]),
                    .o_ready(leaf_forward_ready[e]),
                    .i_flit(leaf_forward_flit[e*FL+:FL]),
                    .o_valid(packet_valid),
                    .i_ready(packet_ready),
                    .o_packet(packet),
                    .o_envelope(envelope),
                    .o_frame_error(frame_error),
                    .o_idle(receiver_idle),
                    .o_bad(receiver_bad)
                );

                static_mesh_queue #(
                    .WIDTH(CP + ENV + 1),
                    .DEPTH(EQ),
                    .PROTECTION(CONTROL_PROTECTION),
                    .ASYNC_RESET(ASYNC_RESET)
                ) u_queue (
                    .i_clk(i_clk),
                    .i_reset_n(i_reset_n),
                    .i_flush(flush_all || cancel_mask[e]),
                    .i_valid(packet_valid && enabled),
                    .o_ready(packet_ready),
                    .i_data({frame_error, envelope, packet}),
                    .o_valid(queue_valid),
                    .i_ready(queue_ready),
                    .o_data(queue_data),
                    .o_count(queue_count),
                    .o_bad(queue_bad)
                );

                configuration_network_crc #(.WIDTH(CP - 32)) u_crc (
                    .i_data(offered_packet[0+:CP-32]),
                    .o_crc(crc)
                );

                always @* begin
                    next_state = state;
                    next_state.protocol_error = 1'b0;

                    if (state.result_valid && send_ready) next_state.result_valid = 1'b0;

                    if (queue_valid && queue_ready) begin
                        next_state.request = offered;
                        next_state.sent = 1'b0;

                        if (offered_frame_error || !envelope_ok || !crc_ok ||
                            offered.protocol != 1 || !offered.destination[e] ||
                            offered.epoch != q.epoch || (^offered === 1'bx)) begin
                            next_state.result_valid = 1'b1;
                            next_state.response = response_for(offered, e, CFG_REJECTED,
                                offered_frame_error || !envelope_ok ? CFG_ERR_FRAME :
                                !crc_ok ? CFG_ERR_CRC : offered.epoch != q.epoch ?
                                CFG_ERR_EPOCH : CFG_ERR_DESTINATION);

                            // Trust the separately carried envelope for transport
                            // failure attribution, never corrupted payload IDs.
                            next_state.request.master = offered_envelope[NE+TI+EP+32+:MI];
                            next_state.response.transaction = offered_envelope[NE+:TI];
                            next_state.response.epoch = offered_envelope[NE+TI+:EP];
                            next_state.response.sequence_id = offered_envelope[NE+TI+EP+:32];
                        end else begin
                            next_state.busy = 1'b1;
                        end
                    end

                    if (native_take[e]) next_state.sent = 1'b1;

                    if (enabled && state.busy &&!state.sent &&
                        i_endpoint_power_safe[e] !== 1'b1) begin
                        next_state.busy = 1'b0;
                        next_state.result_valid = 1'b1;
                        next_state.response = response_for(state.request, e,
                            CFG_REJECTED, CFG_ERR_POWER);
                    end

                    if (native_complete[e]) begin
                        next_state.busy = 1'b0;
                        next_state.sent = 1'b0;
                        next_state.result_valid = 1'b1;
                        next_state.response = response_for(state.request, e,
                            response_matches ? i_endpoint_response_status[e*4+:4] :
                                CFG_REJECTED,
                            !response_known ? CFG_ERR_UNKNOWN : !response_matches ?
                                CFG_ERR_IDENTITY : i_endpoint_response_error_code[e*8+:8]);

                        if (response_matches) begin
                            next_state.response.read_data = i_endpoint_response_read_data[e*D+:D];
                            next_state.response.version
                                = i_endpoint_response_context_version[e*V+:V];
                            next_state.response.image_crc = i_endpoint_response_image_crc[e*32+:32];
                            next_state.response.prepared = i_endpoint_response_prepared[e];

                            if (i_endpoint_response_status[e*4+:4] > CFG_NOT_PRESENT ||
                                (i_endpoint_response_status[e*4+:4] == CFG_SUCCESS &&
                                i_endpoint_response_error_code[e*8+:8] != CFG_OK)) begin
                                next_state.response.status = CFG_REJECTED;
                                next_state.response.error_code = CFG_ERR_RESPONSE;
                            end
                        end
                    end

                    if (enabled && i_endpoint_response_valid[e] === 1'b1 &&
                        o_endpoint_response_ready[e] && !(state.busy && state.sent))
                        next_state.protocol_error = 1'b1;

                    if (cancel_mask[e]) begin
                        next_state.result_valid = 1'b0;

                        if (i_endpoint_cancel_ack[e] === 1'b1) begin
                            next_state.busy = 1'b0;
                            next_state.sent = 1'b0;
                        end
                    end
                end

                banked_scratchpad_state #(
                    .WIDTH($bits(endpoint_state_t)),
                    .PROTECTION(CONTROL_PROTECTION),
                    .ASYNC_RESET(ASYNC_RESET)
                ) u_state (
                    .i_clk(i_clk),
                    .i_reset_n(i_reset_n),
                    .i_data(next_state),
                    .o_data(raw_state),
                    .o_bad(state_integrity)
                );

                configuration_network_crc #(.WIDTH(RP - 32)) u_response_crc (
                    .i_data(response_body),
                    .o_crc(response_crc)
                );

                configuration_network_serializer #(
                    .WIDTH(RP),
                    .PACKET_TYPE(1),
                    .FLIT(F),
                    .ENVELOPE(ENV),
                    .PROTECTION(CONTROL_PROTECTION),
                    .ASYNC_RESET(ASYNC_RESET)
                ) u_serializer (
                    .i_clk(i_clk),
                    .i_reset_n(i_reset_n),
                    .i_flush(flush_all || cancel_mask[e]),
                    .i_run(transport),
                    .i_valid(state.result_valid &&!cancel_mask[e]),
                    .o_ready(send_ready),
                    .i_packet(response_packet),
                    .i_envelope({saved_request.master,
                        saved_response.sequence_id, saved_response.epoch,
                        saved_response.transaction, (NE'(1) << e)}),
                    .o_valid(leaf_reverse_valid[e]),
                    .i_ready(leaf_reverse_ready[e]),
                    .o_flit(raw_leaf_reverse[e*RL+:RL]),
                    .o_idle(send_idle),
                    .o_bad(send_bad)
                );
            end else begin : g_absent
                assign leaf_forward_ready[e] = 1'b0;
                assign leaf_reverse_valid[e] = 1'b0;
                assign raw_leaf_reverse[e*RL+:RL] = '0;
                assign endpoint_idle[e] = 1'b1;
                assign endpoint_bad[e] = 1'b0;
                assign endpoint_protocol_error[e] = 1'b0;
                assign endpoint_frame_error[e] = 1'b0;
                assign native_take[e] = 1'b0;
                assign native_complete[e] = 1'b0;
                assign o_endpoint_request_valid[e] = 1'b0;
                assign o_endpoint_response_ready[e] = 1'b0;
                assign o_endpoint_clock_enable[e] = 1'b0;
                assign o_endpoint_request_command[e*C+:C] = '0;
                assign o_endpoint_request_transaction_id[e*TI+:TI] = '0;
                assign o_endpoint_request_sequence_id[e*32+:32] = '0;
                assign o_endpoint_request_tag[e*TG+:TG] = '0;
                assign o_endpoint_request_owner_id[e*OW+:OW] = '0;
                assign o_endpoint_request_kernel_id[e*K+:K] = '0;
                assign o_endpoint_request_package_id[e*P+:P] = '0;
                assign o_endpoint_request_epoch[e*EP+:EP] = '0;
                assign o_endpoint_request_context_id[e*CI+:CI] = '0;
                assign o_endpoint_request_expected_version[e*V+:V] = '0;
                assign o_endpoint_request_word_index[e*WI+:WI] = '0;
                assign o_endpoint_request_write_data[e*D+:D] = '0;
                assign o_endpoint_request_write_strobe[e*BY+:BY] = '0;
                assign o_endpoint_request_expected_crc[e*32+:32] = '0;
            end
        end

        configuration_network_receiver #(
            .WIDTH(RP),
            .PACKET_TYPE(1),
            .FLIT(F),
            .ENVELOPE(ENV),
            .PROTECTION(CONTROL_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_root_receiver (
            .i_clk(i_clk),
            .i_reset_n(i_reset_n),
            .i_flush(flush_all),
            .i_run(transport),
            .i_valid(reverse_valid),
            .o_ready(reverse_ready),
            .i_flit(reverse_flit),
            .o_valid(root_valid),
            .i_ready(root_ready),
            .o_packet(root_packet),
            .o_envelope(root_envelope),
            .o_frame_error(root_frame_error),
            .o_idle(root_receiver_idle),
            .o_bad(root_receiver_bad)
        );

        configuration_network_crc #(.WIDTH(RP - 32)) u_root_crc (
            .i_data(root_packet[0+:RP-32]),
            .o_crc(root_crc)
        );

        assign root_response = root_packet[0+:RB];
        assign root_ready = transport;

        // Pending root records survive flush as explicit cancellation records.
        // Their new epoch distinguishes cancellation from an old completion.
        retirement_t original_retired;
        response_t canceled_response;

        always @* begin
            original_retired = retirement_bits;
            retired = original_retired;
            canceled_response = original_retired.response;

            if (original_retired.generation != q.flush_generation) begin
                canceled_response.epoch = q.epoch;
                canceled_response.status = CFG_CANCELED;
                canceled_response.error_code = CFG_ERR_CANCELED;
                canceled_response.read_data = '0;
                canceled_response.prepared = 1'b0;
                canceled_response.committed = 1'b0;
                retired.response = canceled_response;
                retired.failure = original_retired.failure | original_retired.success;
                retired.success = '0;
                retired.timeout_mask = '0;
            end
        end

        static_mesh_queue #(
            .WIDTH(RETIRE),
            .DEPTH(RQ),
            .PROTECTION(CONTROL_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_retirement_queue (
            .i_clk(i_clk),
            .i_reset_n(i_reset_n),
            .i_flush(1'b0),
            .i_valid(retire_valid),
            .o_ready(retirement_ready),
            .i_data(retiring),
            .o_valid(retirement_valid),
            .i_ready(response_fire),
            .o_data(retirement_bits),
            .o_count(retirement_count),
            .o_bad(retirement_bad)
        );

        // Native safe-point and prepared signals are in i_clk's domain. The
        // external power controller must remove availability before power loss.
        always @* begin
            prepared_t record;
            armed = '0;
            commit_identity_ok = i_commit_destination_mask != 0 &&
                (^i_commit_destination_mask !== 1'bx) &&
                (i_commit_destination_mask & ~ENDPOINT_PRESENT_MASK) == 0;

            for (int e = 0; e < NE; e++) begin
                record = prepared[e*PREP+:PREP];
                armed[e] = record.valid && i_endpoint_prepared_retained[e] === 1'b1 &&
                    i_endpoint_power_safe[e] === 1'b1;

                if (i_commit_destination_mask[e] && (!armed[e] ||
                    i_endpoint_quiescent[e] !== 1'b1 ||
                    record.package_id !== i_commit_package_id ||
                    record.kernel !== i_commit_kernel_id || record.owner !== i_commit_owner_id ||
                    record.context_id !== i_commit_context_ids[e*CI+:CI] ||
                    record.version !== i_commit_context_versions[e*V+:V]))
                    commit_identity_ok = 1'b0;
            end

            if (armed != i_commit_destination_mask ||
                (^{i_commit_package_id, i_commit_kernel_id, i_commit_owner_id,
                    i_commit_epoch, i_commit_context_ids, i_commit_context_versions} === 1'bx))
                commit_identity_ok = 1'b0;
        end

        assign o_commit_ready = transport &&!q.recovery &&!q.drain &&!q.flushing &&
            i_flush === 1'b0 && i_drain === 1'b0 && i_test_enable === 1'b0 &&
            i_scan_enable === 1'b0 && q.phase == COMMIT_IDLE && all_idle &&
            commit_identity_ok && !(|i_cfg_request_valid);
        assign commit_send = transport && i_flush === 1'b0 && q.phase == COMMIT_DELIVER &&
            ((i_endpoint_commit_ready & q.commit_mask) === q.commit_mask) &&
            ((i_endpoint_quiescent & q.commit_mask) === q.commit_mask) &&
            ((armed & q.commit_mask) === q.commit_mask);
        assign o_endpoint_commit_valid = commit_send ? q.commit_mask : '0;
        assign o_endpoint_commit_ack_ready = transport && q.phase == COMMIT_ACK ?
            q.commit_mask & ~q.ack_mask : '0;

        for (genvar e = 0; e < NE; e++) begin : g_commit_fields
            prepared_t record;
            assign record = prepared[e*PREP+:PREP];
            assign o_endpoint_commit_context_id[e*CI+:CI] =
                o_endpoint_commit_valid[e] ? record.context_id : '0;
            assign o_endpoint_commit_context_version[e*V+:V] =
                o_endpoint_commit_valid[e] ? record.version : '0;
            assign o_endpoint_commit_package_id[e*P+:P] =
                o_endpoint_commit_valid[e] ? q.commit_package : '0;
            assign o_endpoint_commit_owner_id[e*OW+:OW] =
                o_endpoint_commit_valid[e] ? q.commit_owner : '0;
            assign o_endpoint_commit_kernel_id[e*K+:K] =
                o_endpoint_commit_valid[e] ? q.commit_kernel : '0;
            assign o_endpoint_commit_epoch[e*EP+:EP] =
                o_endpoint_commit_valid[e] ? q.commit_epoch : '0;
            assign o_endpoint_commit_image_crc[e*32+:32] =
                o_endpoint_commit_valid[e] ? record.crc : '0;
        end

        assign o_endpoint_cancel = run &&!state_bad ? cancel_mask & ENDPOINT_PRESENT_MASK :
            ENDPOINT_PRESENT_MASK;
        assign o_execution_hold = !run || !known_control || state_bad || integrity_bad
            || integrity_latched ||
            !q.released || !q.active_valid || q.recovery || q.fatal ||
            ((i_endpoint_power_safe & q.active_mask) !== q.active_mask) ||
            q.phase != COMMIT_IDLE;
        assign o_commit_complete = run &&!state_bad && q.commit_complete;
        assign o_commit_error = run &&!state_bad && q.phase == COMMIT_FAILED;
        assign o_commit_ack_mask = run &&!state_bad ? q.ack_mask : '0;
        assign o_commit_failure_mask = run &&!state_bad ? q.commit_failure : '0;
        assign o_active_package_id = run &&!state_bad && q.active_valid ? q.active_package : '0;
        assign o_active_commit_epoch = run &&!state_bad && q.active_valid ? q.active_epoch : '0;
        assign o_configuration_epoch = run &&!state_bad ? q.epoch : '0;
        assign o_outstanding_transactions = run &&!state_bad ? q.count : '0;
        assign o_armed_mask = run &&!state_bad ? armed : '0;
        assign o_error = run && (integrity_bad || integrity_latched || q.error_code != CFG_OK);
        assign o_error_code = !run ? CFG_OK : (integrity_bad || integrity_latched)
            ? CFG_ERR_INTEGRITY : q.error_code;
        assign o_error_endpoint = run &&!state_bad ? q.error_endpoint : '0;
        assign o_error_transaction = run &&!state_bad ? q.error_transaction : '0;
        assign o_error_command = run &&!state_bad ? q.error_command : '0;
        assign o_idle = run &&!integrity_bad && q.bootstrapped && all_idle &&!q.flushing;
        assign o_drained = o_idle && (i_drain === 1'b1 || q.drain);
        assign o_draining = run &&!state_bad && (i_drain === 1'b1 || q.drain);
        assign o_flushing = run &&!state_bad && q.flushing;
        assign o_flushed = run &&!state_bad && q.flushed;
        assign o_fail_stop = run && (state_bad || integrity_latched || q.fatal
            || q.phase == COMMIT_FAILED);

        // Retirement sorts architecture IDs, never physical leaf/tree positions.
        always @* begin
            slot_t head;
            logic [NE-1:0] targets;
            logic [NE*RB-1:0] head_results;
            int endpoint;
            logic found;
            head = slots[int'(q.head)*SLOT+:SLOT];
            targets = head.targets;
            head_results = head.results;
            endpoint = 0;
            found = 1'b0;

            for (int e = 0; e < NE; e++)
                if (targets[e] && (!found ||
                    ENDPOINT_ID_TABLE[e*EI+:EI] < ENDPOINT_ID_TABLE[endpoint*EI+:EI])) begin
                    endpoint = e;
                    found = 1'b1;
                end

            retiring = '0;
            retiring.generation = q.flush_generation;
            retiring.master = head.request.master;
            retiring.tag = head.request.tag;
            retiring.first = head.first;
            retiring.last = $countones(targets) == 1;
            retiring.synthetic = head.synthetic;
            retiring.failure = head.synthetic ? '0 : head.failure;
            retiring.success = head.synthetic ? '0 : head.success;
            retiring.timeout_mask = head.synthetic ? '0 : head.timeout_mask;
            retiring.absent = head.synthetic ? '0 : head.absent;
            retiring.response = head_results[endpoint*RB+:RB];
            retire_valid = transport && i_flush === 1'b0 && q.count != 0 &&
                head.valid && found && (head.done & targets) == targets;
        end

        assign response_fire = transport && i_flush === 1'b0 && retirement_valid &&
            i_cfg_response_ready[int'(retired.master)] === 1'b1;
        localparam int COMPLETION_BODY = RB + ET + 3 + 4 * NE;
        localparam int COMPLETION_PAD = (COMPLETION_BODY + 7) / 8 * 8;
        wire transaction_success = retired.last && retired.failure == 0 &&
            retired.timeout_mask == 0 && retired.absent == 0 &&
            retired.response.status == CFG_SUCCESS;
        response_t completion_response;
        logic [ET-1:0] completion_type;
        wire [COMPLETION_PAD-1:0] completion_bits = COMPLETION_PAD'({
            retired.last ? retired.absent : {NE{1'b0}},
            retired.last ? retired.timeout_mask : {NE{1'b0}},
            retired.last ? retired.success : {NE{1'b0}},
            retired.last ? retired.failure : {NE{1'b0}},
            transaction_success, retired.last, retired.first, completion_type,
                completion_response});
        wire [31:0] completion_crc;

        always @* begin
            completion_response = retired.response;

            if (retired.synthetic) completion_response.endpoint = '1;

            completion_type = '0;

            for (int e = 0; e < NE; e++)
                if (!retired.synthetic && ENDPOINT_ID_TABLE[e*EI+:EI] == retired.response.endpoint)
                    completion_type = ENDPOINT_TYPE_TABLE[e*ET+:ET];
        end

        configuration_network_crc #(.WIDTH(COMPLETION_PAD)) u_completion_crc (
            .i_data(completion_bits),
            .o_crc(completion_crc)
        );

        for (genvar m = 0; m < NM; m++) begin : g_master_response
            wire valid = transport && i_flush === 1'b0 && retirement_valid &&
                retired.master == MI'(m);
            assign o_cfg_response_valid[m] = valid;
            assign o_cfg_response_transaction_success[m] = valid && transaction_success;
            assign o_cfg_response_sequence_id[m*32+:32] = valid
                ? completion_response.sequence_id : '0;
            assign o_cfg_response_protocol[m*8+:8] = valid ? 8'd1 : '0;
            assign o_cfg_response_packet_crc[m*32+:32] = valid && ENABLE_PACKET_CRC ?
                completion_crc : '0;
            assign o_cfg_response_command[m*(C)+:(C)] =
                valid ? (retired.response.command) : '0;
            assign o_cfg_response_transaction_id[m*(TI)+:(TI)] =
                valid ? (retired.response.transaction) : '0;
            assign o_cfg_response_endpoint_id[m*(EI)+:(EI)] =
                valid ? (retired.synthetic ? {EI{1'b1}} : retired.response.endpoint) : '0;
            logic [ET-1:0] endpoint_type;

            always @* begin
                endpoint_type = '0;

                for (int e = 0; e < NE; e++)
                    if (!retired.synthetic
                        && ENDPOINT_ID_TABLE[e*EI+:EI] == retired.response.endpoint)
                        endpoint_type = ENDPOINT_TYPE_TABLE[e*ET+:ET];
            end

            assign o_cfg_response_endpoint_type[m*(ET)+:(ET)] =
                valid ? (endpoint_type) : '0;
            assign o_cfg_response_status[m*(4)+:(4)] =
                valid ? (retired.response.status) : '0;
            assign o_cfg_response_error_code[m*(8)+:(8)] =
                valid ? (retired.response.error_code) : '0;
            assign o_cfg_response_read_data[m*(D)+:(D)] =
                valid ? (retired.response.read_data) : '0;
            assign o_cfg_response_context_id[m*(CI)+:(CI)] =
                valid ? (retired.response.context_id) : '0;
            assign o_cfg_response_context_version[m*(V)+:(V)] =
                valid ? (retired.response.version) : '0;
            assign o_cfg_response_crc[m*(32)+:(32)] =
                valid ? (retired.response.image_crc) : '0;
            assign o_cfg_response_tag[m*(TG)+:(TG)] =
                valid ? (retired.tag) : '0;
            assign o_cfg_response_epoch[m*(EP)+:(EP)] =
                valid ? (retired.response.epoch) : '0;
            assign o_cfg_response_first[m*(1)+:(1)] =
                valid ? (retired.first) : '0;
            assign o_cfg_response_last[m*(1)+:(1)] =
                valid ? (retired.last) : '0;
            assign o_cfg_response_prepared[m*(1)+:(1)] =
                valid ? (retired.response.prepared) : '0;
            assign o_cfg_response_committed[m*(1)+:(1)] =
                valid ? (retired.response.committed) : '0;
            assign o_cfg_response_failure_mask[m*(NE)+:(NE)] =
                valid ? (retired.last ? retired.failure : '0) : '0;
            assign o_cfg_response_success_mask[m*(NE)+:(NE)] =
                valid ? (retired.last ? retired.success : '0) : '0;
            assign o_cfg_response_timeout_mask[m*(NE)+:(NE)] =
                valid ? (retired.last ? retired.timeout_mask : '0) : '0;
            assign o_cfg_response_not_present_mask[m*(NE)+:(NE)] =
                valid ? (retired.last ? retired.absent : '0) : '0;
        end

        // A slot owns all endpoint results until their ordered records move to
        // the reserved response queue. Native failures can never imply success.
        always @* begin
            slot_t item;
            slot_t head;
            slot_t accepted;
            prepared_t record;
            response_t result;
            command_packet_t request;
            logic [NE-1:0] done_mask;
            logic [NE-1:0] target_mask;
            logic [NE-1:0] missing;
            logic [NE-1:0] ack;
            logic [NE-1:0] failure;
            logic [NE*RB-1:0] item_results;
            logic [NE*RB-1:0] accepted_results;
            logic response_matched;
            logic start_flush;
            int source_endpoint;
            int retire_endpoint;
            n = q;
            next_slots = slots;
            next_prepared = prepared;
            n.flushed = 1'b0;
            n.commit_complete = 1'b0;
            runtime_code = CFG_OK;
            runtime_endpoint = '0;
            runtime_transaction = '0;
            runtime_command = '0;
            response_matched = 1'b0;
            source_endpoint = -1;
            start_flush = (i_flush === 1'b1 &&!q.flush_seen) ||
                (ingress_fire && admission_error == CFG_OK &&
                    ingress_command.command == C'(CFG_FLUSH));
            ack = q.ack_mask;
            failure = q.commit_failure;

            // The envelope's endpoint bit, ID, sequence and epoch are checked
            // independently of the CRC-protected response's software fields.
            for (int e = 0; e < NE; e++)
                if (root_envelope[e]) source_endpoint = source_endpoint == -1 ? e : -2;

            if (run &&!q.bootstrapped &&!q.fatal) begin
                n.commit_timer = q.commit_timer + 1'b1;

                if ((&endpoint_idle) &&
                    ((i_endpoint_cancel_ack & ENDPOINT_PRESENT_MASK)
                        === ENDPOINT_PRESENT_MASK)) begin
                    n.bootstrapped = 1'b1;
                    n.commit_timer = '0;
                end else if (q.commit_timer >= 32'(TRANSACTION_TIMEOUT_CYCLES - 1)) begin
                    n.fatal = 1'b1;
                    n.recovery = 1'b1;
                    runtime_code = CFG_ERR_TIMEOUT;
                end
            end

            if (run && q.bootstrapped && known_control &&!q.fatal &&!q.flushing && i_flush
                === 1'b0) begin
                if (i_resume === 1'b1 && all_idle) n.drain = 1'b0;

                for (int e = 0; e < NE; e++) begin
                    record = next_prepared[e*PREP+:PREP];

                    if (q.phase == COMMIT_IDLE && record.valid
                        && (i_endpoint_prepared_retained[e] !== 1'b1 ||
                        i_endpoint_power_safe[e] !== 1'b1)) record.valid = 1'b0;

                    next_prepared[e*PREP+:PREP] = record;
                end

                for (int t = 0; t < NS; t++) begin
                    item = slots[t*SLOT+:SLOT];
                    item_results = item.results;
                    target_mask = item.targets;
                    done_mask = item.done;
                    missing = target_mask & ~done_mask;
                    request = item.request;

                    if (root_valid && root_ready && item.valid && source_endpoint >= 0 &&
                        request.transaction == root_envelope[NE+:TI] &&
                        request.epoch == root_envelope[NE+TI+:EP] &&
                        request.sequence_id == root_envelope[NE+TI+EP+:32] &&
                        request.master == root_envelope[NE+TI+EP+32+:MI]) begin
                        response_matched = 1'b1;

                        if (target_mask[source_endpoint] &&!done_mask[source_endpoint]) begin
                            result = root_response;

                            if (root_frame_error || !root_crc_ok) result =
                                response_for(request, source_endpoint, CFG_REJECTED,
                                    root_frame_error ? CFG_ERR_FRAME : CFG_ERR_CRC);
                            else if (root_response.status != CFG_SUCCESS &&
                                (root_response.error_code == CFG_ERR_CRC ||
                                    root_response.error_code == CFG_ERR_FRAME)) result =
                                response_for(request, source_endpoint, CFG_REJECTED,
                                    root_response.error_code);
                            else if (root_response.transaction !== request.transaction ||
                                root_response.sequence_id !== request.sequence_id ||
                                root_response.epoch !== request.epoch ||
                                root_response.command !== request.command ||
                                root_response.context_id !== request.context_id ||
                                root_response.tag !== request.tag || root_response.protocol != 1 ||
                                root_response.endpoint !==
                                    ENDPOINT_ID_TABLE[source_endpoint*EI+:EI]) result =
                                response_for(request, source_endpoint, CFG_REJECTED,
                                    CFG_ERR_IDENTITY);

                            if (request.command == C'(CFG_PREPARE) &&
                                result.status == CFG_SUCCESS &&
                                (!result.prepared || result.version != request.version ||
                                    result.image_crc != request.image_crc)) result =
                                response_for(request, source_endpoint, CFG_REJECTED,
                                    CFG_ERR_PREPARE);

                            item_results[source_endpoint*RB+:RB] = result;
                            item.done = item.done | (NE'(1) << source_endpoint);

                            if (result.status == CFG_SUCCESS && result.error_code == CFG_OK) begin
                                item.success = item.success | (NE'(1) << source_endpoint);

                                if (request.command == C'(CFG_PREPARE)) begin
                                    record = '0;
                                    record.valid = 1'b1;
                                    record.context_id = request.context_id;
                                    record.version = result.version;
                                    record.owner = request.owner;
                                    record.kernel = request.kernel;
                                    record.package_id = request.package_id;
                                    record.crc = result.image_crc;
                                    next_prepared[source_endpoint*PREP+:PREP] = record;
                                end
                            end else begin
                                item.failure = item.failure | (NE'(1) << source_endpoint);

                                if (result.status == CFG_TIMEOUT) item.timeout_mask =
                                    item.timeout_mask | (NE'(1) << source_endpoint);

                                if (result.error_code == CFG_ERR_CRC ||
                                    result.error_code == CFG_ERR_FRAME ||
                                    result.error_code == CFG_ERR_IDENTITY ||
                                    result.error_code == CFG_ERR_RESPONSE ||
                                    result.error_code == CFG_ERR_UNKNOWN ||
                                    result.error_code == CFG_ERR_TIMEOUT ||
                                    result.status == CFG_TIMEOUT) begin
                                    n.recovery = 1'b1;
                                    n.released = 1'b0;
                                    n.cancel = n.cancel | (NE'(1) << source_endpoint);
                                    runtime_code = result.error_code;
                                    runtime_endpoint = ENDPOINT_ID_TABLE[source_endpoint*EI+:EI];
                                    runtime_transaction = request.transaction;
                                    runtime_command = request.command;
                                end
                            end
                        end else begin
                            runtime_code = CFG_ERR_RESPONSE;
                            runtime_endpoint = ENDPOINT_ID_TABLE[source_endpoint*EI+:EI];
                            n.recovery = 1'b1;
                            n.released = 1'b0;
                        end
                    end

                    done_mask = item.done;
                    missing = target_mask & ~done_mask;

                    if (item.valid && missing != 0) begin
                        item.timer = item.timer + 1'b1;

                        if (request.command == C'(CFG_DRAIN)) begin
                            if (q.count == 1 && idle_transport && retirement_count == 0) begin
                                item.done = target_mask;
                                item.success = target_mask;
                            end
                        end else if (item.timer >= 32'(TRANSACTION_TIMEOUT_CYCLES)) begin
                            for (int e = 0; e < NE; e++)
                                if (missing[e]) item_results[e*RB+:RB] =
                                    response_for(request, e, CFG_TIMEOUT, CFG_ERR_TIMEOUT);

                            item.done = done_mask | missing;
                            item.failure = item.failure | missing;
                            item.timeout_mask = item.timeout_mask | missing;
                            n.cancel = n.cancel | (missing & ENDPOINT_PRESENT_MASK);
                            n.recovery = 1'b1;
                            n.released = 1'b0;
                            runtime_code = CFG_ERR_TIMEOUT;
                            runtime_endpoint = first_endpoint(missing);
                            runtime_transaction = request.transaction;
                            runtime_command = request.command;
                        end
                    end

                    item.results = item_results;
                    next_slots[t*SLOT+:SLOT] = item;
                end

                if (root_valid && root_ready &&!response_matched) begin
                    runtime_code = CFG_ERR_RESPONSE;
                    n.recovery = 1'b1;
                    n.released = 1'b0;
                end

                if (ingress_fire && (ingress_command.command != C'(CFG_FLUSH) ||
                    admission_error != CFG_OK)) begin
                    accepted = '0;
                    accepted_results = '0;
                    accepted.valid = 1'b1;
                    accepted.first = 1'b1;
                    accepted.synthetic = ingress_command.destination == 0;
                    accepted.targets = ingress_targets;
                    accepted.request = ingress_command;

                    for (int e = 0; e < NE; e++) begin
                        if (ingress_targets[e]) begin
                            result = response_for(ingress_command, e, CFG_SUCCESS, CFG_OK);

                            if (admission_error != CFG_OK ||
                                (!ENDPOINT_PRESENT_MASK[e] &&!accepted.synthetic)) begin
                                result.status = !ENDPOINT_PRESENT_MASK[e] &&!accepted.synthetic ?
                                    CFG_NOT_PRESENT : CFG_REJECTED;
                                result.error_code = !ENDPOINT_PRESENT_MASK[e] &&
                                    !accepted.synthetic ? CFG_ERR_DESTINATION : admission_error;
                                accepted.done = accepted.done | (NE'(1) << e);
                                accepted.failure = accepted.failure | (NE'(1) << e);

                                if (result.status == CFG_NOT_PRESENT)
                                    accepted.absent = accepted.absent | (NE'(1) << e);
                            end else if (ingress_command.command == C'(CFG_NOP)) begin
                                accepted.done = accepted.targets;
                                accepted.success = accepted.targets;
                            end

                            accepted_results[e*RB+:RB] = result;

                            if (admission_error == CFG_OK &&
                                (ingress_command.command == C'(CFG_WRITE) ||
                                    ingress_command.command == C'(CFG_INVALIDATE) ||
                                    ingress_command.command == C'(CFG_ABORT_PREPARE)))
                                next_prepared[e*PREP+:PREP] = '0;
                        end
                    end

                    accepted.results = accepted_results;
                    next_slots[int'(q.tail)*SLOT+:SLOT] = accepted;
                    n.tail = q.tail == SI'(NS - 1) ? '0 : q.tail + 1'b1;
                    n.count = q.count + 1'b1;
                    n.sequence_id = q.sequence_id + 1'b1;

                    if (admission_error == CFG_OK && ingress_command.command == C'(CFG_DRAIN))
                        n.drain = 1'b1;
                end

                if (retire_fire) begin
                    head = next_slots[int'(q.head)*SLOT+:SLOT];
                    retire_endpoint = -1;
                    target_mask = head.targets;

                    for (int e = 0; e < NE; e++)
                        if (target_mask[e] && (retire_endpoint == -1 ||
                            ENDPOINT_ID_TABLE[e*EI+:EI] <
                                ENDPOINT_ID_TABLE[retire_endpoint*EI+:EI])) retire_endpoint = e;

                    head.targets = target_mask & ~(NE'(1) << retire_endpoint);
                    head.first = 1'b0;

                    if (head.targets == 0) begin
                        head.valid = 1'b0;
                        n.head = q.head == SI'(NS - 1) ? '0 : q.head + 1'b1;
                        n.count = n.count - 1'b1;
                    end

                    next_slots[int'(q.head)*SLOT+:SLOT] = head;
                end

                if (commit_fire) begin
                    n.phase = COMMIT_HOLD;
                    n.commit_mask = i_commit_destination_mask;
                    n.commit_package = i_commit_package_id;
                    n.commit_kernel = i_commit_kernel_id;
                    n.commit_owner = i_commit_owner_id;
                    n.commit_epoch = i_commit_epoch;
                    n.ack_mask = '0;
                    n.commit_failure = '0;
                    n.commit_timer = '0;
                    n.released = 1'b0;
                end

                if (q.phase == COMMIT_HOLD) n.phase = COMMIT_DELIVER;

                if (commit_send) n.phase = COMMIT_ACK;

                if (q.phase == COMMIT_ACK) begin
                    for (int e = 0; e < NE; e++) begin
                        record = prepared[e*PREP+:PREP];

                        if (o_endpoint_commit_ack_ready[e] &&
                            i_endpoint_commit_ack_valid[e] === 1'b1) begin

                            if (i_endpoint_commit_error[e] !== 1'b0 ||
                                i_endpoint_power_safe[e] !== 1'b1 ||
                                i_endpoint_active_context_id[e*CI+:CI] !== record.context_id ||
                                i_endpoint_active_context_version[e*V+:V] !== record.version ||
                                i_endpoint_active_package_id[e*P+:P] !== q.commit_package ||
                                i_endpoint_active_owner_id[e*OW+:OW] !== q.commit_owner ||
                                i_endpoint_active_kernel_id[e*K+:K] !== q.commit_kernel ||
                                i_endpoint_active_epoch[e*EP+:EP] !== q.commit_epoch ||
                                i_endpoint_active_image_crc[e*32+:32] !== record.crc)
                                failure[e] = 1'b1;
                            else ack[e] = 1'b1;
                        end
                    end

                    n.ack_mask = ack;
                    n.commit_failure = failure;

                    if (failure != 0) begin
                        n.phase = COMMIT_FAILED;
                        n.recovery = 1'b1;
                        runtime_code = CFG_ERR_COMMIT;
                        runtime_endpoint = first_endpoint(failure);
                    end else if (ack == q.commit_mask) begin
                        n.phase = COMMIT_HELD;
                        n.commit_complete = 1'b1;
                        n.active_valid = 1'b1;
                        n.active_mask = q.commit_mask;
                        n.active_package = q.commit_package;
                        n.active_epoch = q.commit_epoch;
                    end
                end

                if (q.phase == COMMIT_HOLD || q.phase == COMMIT_DELIVER ||
                    q.phase == COMMIT_ACK) begin
                    n.commit_timer = q.commit_timer + 1'b1;

                    if (((q.phase == COMMIT_HOLD || q.phase == COMMIT_DELIVER) &&
                        (armed & q.commit_mask) != q.commit_mask) ||
                        (q.commit_timer >= 32'(COMMIT_TIMEOUT_CYCLES - 1) &&
                            ack != q.commit_mask)) begin
                        n.phase = COMMIT_FAILED;
                        n.commit_failure = q.commit_mask & ~ack;
                        n.recovery = 1'b1;
                        runtime_code = CFG_ERR_COMMIT;
                        runtime_endpoint = first_endpoint(q.commit_mask & ~ack);
                    end
                end

                if (i_execution_release === 1'b1 && i_release_safe === 1'b1 &&
                    q.phase == COMMIT_HELD && q.active_valid && q.error_code == CFG_OK &&
                    !q.recovery && q.ack_mask == q.commit_mask) begin
                    n.phase = COMMIT_IDLE;
                    n.released = 1'b1;
                    next_prepared = '0;
                end
            end

            if (run && i_flush === 1'b0) n.flush_seen = 1'b0;

            if (run && start_flush) begin
                n.flush_seen = 1'b1;
                n.released = 1'b0;

                if (q.phase == COMMIT_ACK || q.phase == COMMIT_FAILED) begin
                    // Once activation might have occurred, cancellation cannot
                    // establish rollback. Recovery keeps execution held.
                    n.phase = COMMIT_FAILED;
                    n.recovery = 1'b1;
                    n.commit_failure = q.commit_mask & ~q.ack_mask;
                    runtime_code = CFG_ERR_COMMIT;
                end else if (q.flush_generation == 32'hffffffff) begin
                    n.fatal = 1'b1;
                    n.recovery = 1'b1;
                    runtime_code = CFG_ERR_OVERFLOW;
                end else begin
                    n.flushing = 1'b1;
                    n.flush_generation = q.flush_generation + 1'b1;
                    n.commit_timer = '0;
                    n.epoch = q.epoch + 1'b1;
                    n.drain = 1'b0;

                    if (q.phase != COMMIT_HELD) n.phase = COMMIT_IDLE;

                    // Cancel every unretired endpoint copy in place. Retired
                    // prefixes remain ordered in the root response FIFO.
                    // Include retirement from this edge before canceling the
                    // remaining targets; otherwise a canonical FLUSH can
                    // resurrect a destination already enqueued for retirement.
                    for (int t = 0; t < NS; t++) begin
                        item = next_slots[t*SLOT+:SLOT];
                        target_mask = item.targets;
                        item_results = item.results;
                        request = item.request;
                        request.epoch = q.epoch + 1'b1;

                        if (item.valid) begin
                            for (int e = 0; e < NE; e++)
                                if (target_mask[e]) item_results[e*RB+:RB] =
                                    response_for(request, e, CFG_CANCELED, CFG_ERR_CANCELED);

                            item.results = item_results;
                            item.done = target_mask;
                            item.failure = item.failure | item.success | target_mask;
                            item.success = '0;
                            item.timeout_mask = '0;
                            item.request = request;
                            next_slots[t*SLOT+:SLOT] = item;
                        end
                    end

                    next_prepared = '0;

                    if (ingress_fire && ingress_command.command == C'(CFG_FLUSH)) begin
                        n.flush_response = 1'b1;
                        n.flush_command = ingress_command;
                    end
                end
            end

            if (run && q.flushing) begin
                n.commit_timer = q.commit_timer + 1'b1;

                if (q.commit_timer >= 32'(TRANSACTION_TIMEOUT_CYCLES - 1)) begin
                    n.fatal = 1'b1;
                    n.recovery = 1'b1;
                    runtime_code = CFG_ERR_TIMEOUT;
                end
            end

            if (run && q.flushing &&!q.fatal && idle_transport &&
                ((i_endpoint_cancel_ack & ENDPOINT_PRESENT_MASK) === ENDPOINT_PRESENT_MASK)) begin
                n.flushing = 1'b0;
                n.flushed = 1'b1;
                n.cancel = '0;
                n.recovery = 1'b0;

                if (q.flush_response) begin
                    accepted = '0;
                    accepted_results = '0;
                    accepted.valid = 1'b1;
                    accepted.first = 1'b1;
                    accepted.synthetic = 1'b1;
                    accepted.targets = NE'(1);
                    accepted.done = NE'(1);
                    accepted.success = NE'(1);
                    accepted.request = q.flush_command;
                    accepted.request.epoch = q.epoch;
                    accepted.results = (NE*RB)'(response_for(accepted.request, 0, CFG_SUCCESS,
                        CFG_OK));
                    next_slots[int'(q.tail)*SLOT+:SLOT] = accepted;
                    n.count = q.count + 1'b1;
                    n.tail = q.tail == SI'(NS - 1) ? '0 : q.tail + 1'b1;
                    n.flush_response = 1'b0;
                    n.sequence_id = q.sequence_id + 1'b1;
                end
            end

            if (run && q.active_valid &&
                ((i_endpoint_power_safe & q.active_mask) !== q.active_mask)) begin
                n.released = 1'b0;
                n.recovery = 1'b1;
                runtime_code = CFG_ERR_POWER;
                runtime_endpoint = first_endpoint(q.active_mask & ~i_endpoint_power_safe);
            end

            if (run && i_error_clear === 1'b1 && all_idle &&!q.recovery &&
                !q.fatal && q.phase == COMMIT_IDLE &&!integrity_bad && known_control)
                n.error_code = CFG_OK;

            if (run && ((|endpoint_frame_error) || root_frame_error)) begin
                runtime_code = CFG_ERR_FRAME;
                n.recovery = 1'b1;
                n.released = 1'b0;
                n.cancel = n.cancel | endpoint_frame_error;
                runtime_endpoint = first_endpoint(endpoint_frame_error);
            end

            if (run && (integrity_bad || !known_control || (|endpoint_protocol_error))) begin
                runtime_code = integrity_bad ? CFG_ERR_INTEGRITY :
                    !known_control ? CFG_ERR_UNKNOWN : CFG_ERR_RESPONSE;
                n.released = 1'b0;
                n.recovery = 1'b1;

                if (integrity_bad) n.fatal = 1'b1;
            end

            if (run && runtime_code != CFG_OK && q.error_code == CFG_OK) begin
                n.error_code = runtime_code;
                n.error_endpoint = runtime_endpoint;
                n.error_transaction = runtime_transaction;
                n.error_command = runtime_command;
            end

            n.entries = next_slots;
            n.prepared = next_prepared;
        end

        banked_scratchpad_state #(
            .WIDTH($bits(control_t)),
            .PROTECTION(CONTROL_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_control (
            .i_clk(i_clk),
            .i_reset_n(i_reset_n),
            .i_data(n),
            .o_data(raw_control),
            .o_bad(state_bad)
        );

        dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET)) u_integrity_latch (
            .i_clk(i_clk),
            .i_rstb(i_reset_n),
            .i_enable(1'b1),
            .i_d(integrity_latched || integrity_bad),
            .o_q(integrity_latched)
        );

        // Statistics are passive, saturating lifetime observations. Completion
        // storage and execution release never depend on a counter read request.
        logic [1023:0] increments;
        wire [31:0] counts [32];
        wire [32:0] counter_read;
        logic [31:0] read_value;

        always @* begin
            increments = '0;
            increments[0*32+:32] = 32'(ingress_fire);
            increments[1*32+:32] = 32'(forward_valid && forward_ready);
            increments[2*32+:32] = 32'(reverse_valid && reverse_ready);
            increments[3*32+:32] = forward_transfers;
            increments[4*32+:32] = reverse_transfers;
            increments[5*32+:32] = 32'($countones(native_take));
            increments[6*32+:32] = 32'($countones(native_complete));
            increments[7*32+:32] = 32'(retire_fire);
            increments[8*32+:32] = 32'(response_fire);
            increments[9*32+:32] = 32'(commit_fire);
            increments[10*32+:32] = 32'(q.commit_complete);
            increments[11*32+:32] = 32'(q.phase == COMMIT_FAILED);
            increments[12*32+:32] = 32'(q.flushed);
            increments[13*32+:32] = 32'(q.flushing);
            increments[14*32+:32] = 32'(o_execution_hold);
            increments[15*32+:32] = 32'(all_idle);
            increments[16*32+:32] = 32'(ingress_fire && admission_error != CFG_OK);
            increments[17*32+:32] = 32'(ingress_fire &&
                $countones(ingress_command.destination) > 1);
            increments[18*32+:32] = ingress_fire ?
                32'($countones(ingress_command.destination & ENDPOINT_PRESENT_MASK)) : 0;
            increments[19*32+:32] = 32'(runtime_code == CFG_ERR_TIMEOUT);
            increments[20*32+:32] = 32'(runtime_code == CFG_ERR_CRC);
            increments[21*32+:32] = 32'(runtime_code == CFG_ERR_FRAME);
            increments[22*32+:32] = 32'(runtime_code == CFG_ERR_RESPONSE);
            increments[23*32+:32] = 32'($countones(i_cfg_request_valid & ~o_cfg_request_ready));
            increments[24*32+:32] = 32'(retirement_valid &&!response_fire);
            increments[25*32+:32] = 32'(q.count);
            increments[26*32+:32] = command_count;
            increments[27*32+:32] = retirement_count;
            increments[28*32+:32] = 32'($countones(armed));
            increments[29*32+:32] = 32'(i_drain === 1'b1 || q.drain);

            for (int e = 0; e < NE; e++) begin
                if (native_take[e] && o_endpoint_request_command[e*C+:C] == C'(CFG_WRITE)) begin
                    increments[30*32+:32] += 1;
                    increments[31*32+:32] +=
                        32'($countones(o_endpoint_request_write_strobe[e*BY+:BY]));
                end
            end

            read_value = counts[i_counter_index];
        end

        for (genvar c = 0; c < 32; c++) begin : g_counter
            banked_scratchpad_counters #(
                .COUNT(1),
                .PEAKS(1),
                .ASYNC_RESET(ASYNC_RESET)
            ) u_count (
                .i_clk(i_clk),
                .i_reset_n(i_reset_n),
                .i_increments(increments[c*32+:32]),
                .i_occupancy(32'b0),
                .o_counts(counts[c]),
                .o_peaks()
            );
        end

        dff #(.WIDTH(33), .ASYNC_RESET(ASYNC_RESET)) u_counter_read (
            .i_clk(i_clk),
            .i_rstb(i_reset_n),
            .i_enable(1'b1),
            .i_d({i_counter_read === 1'b1 && (^i_counter_index !== 1'bx), read_value}),
            .o_q(counter_read)
        );

        assign o_counter_valid = run && counter_read[32];
        assign o_counter_value = o_counter_valid ? counter_read[0+:32] : '0;
    end
endmodule
`default_nettype wire
