`timescale 1ns / 1ps
`default_nettype none
// Static/Partitioned runtime policy. Datapath services and authoritative ownership
// remain external. Normalized peer records are defined in runtime_controller_pkg.
module runtime_controller #(
    parameter RUNTIME_PROFILE = 1,
    parameter NUM_CLUSTERS = 4,
    parameter MAX_PENDING_KERNELS = 8,
    parameter MAX_ACTIVE_KERNELS = RUNTIME_PROFILE == 0 ? 1 : (NUM_CLUSTERS < 4 ? NUM_CLUSTERS : 4),
    parameter MAX_OWNERS = 4,
    parameter MAX_PACKAGE_VARIANTS = RUNTIME_PROFILE == 0 ? 1 : 4,
    parameter MAX_CLUSTERS_PER_KERNEL = NUM_CLUSTERS,
    parameter MAX_DMA_CHANNELS = 4,
    parameter MAX_MEMORY_PORTS = 4,
    parameter MAX_SCRATCHPAD_REGIONS = 16,
    parameter MAX_EVENT_NAMESPACES = 16,
    parameter MAX_NOC_QOS_PROFILES = 4,
    parameter MAX_MEMORY_QOS_PROFILES = 4,
    parameter MAX_POWER_PROFILES = 4,
    parameter NUM_PRIORITY_LEVELS = 4,
    parameter SUBMISSION_QUEUE_DEPTH = 8,
    parameter ACTION_QUEUE_DEPTH = 8,
    parameter RESPONSE_QUEUE_DEPTH = 8,
    parameter EVENT_QUEUE_DEPTH = 16,
    parameter COUNTER_SNAPSHOT_SLOTS = 4,
    parameter AGE_COUNTER_WIDTH = 16,
    parameter HIGH_PRIORITY_BURST_LIMIT = 8,
    parameter AGE_ESCALATION_CYCLES = 4096,
    parameter POLICY_SAMPLE_INTERVAL = 4096,
    parameter ACTION_TIMEOUT_CYCLES = 1048575,
    parameter KERNEL_TIMEOUT_CYCLES = 0,
    parameter ENABLE_QOS = 1,
    parameter ENABLE_DEADLINE_MONITORING = 1,
    parameter ENABLE_SAFE_SUSPEND = 1,
    parameter ENABLE_RESOURCE_RESIZING = 0,
    parameter ENABLE_MIGRATION = 0,
    parameter ENABLE_POWER_POLICY = 1,
    parameter ENABLE_COUNTER_FEEDBACK = 1,
    parameter ENABLE_FAULT_AWARE_ALLOCATION = 1,
    parameter ENABLE_TRACE = 0,
    parameter CONTROL_PROTECTION = 0,
    parameter ASYNC_SYSTEM_CLOCK = 0,
    parameter ASYNC_ARRAY_CLOCK = 0,
    parameter ASYNC_EVENT_CLOCK = 0,
    parameter ASYNC_RESET = 0,
    parameter ARCHITECTURE_ID = 1297044225,
    parameter PROTOCOL_PROOF_ID = 1,
    parameter MEMORY_BANDWIDTH_CAPACITY = 1000,
    parameter NOC_BANDWIDTH_CAPACITY = 1000,
    parameter POWER_CAPACITY = 1000,
    parameter ENFORCED_SERVICE_MASK = 63,
    parameter OWNER_ID_WIDTH = 16,
    parameter KERNEL_ID_WIDTH = 16,
    parameter DESCRIPTOR_ID_WIDTH = 16,
    parameter DESCRIPTOR_GENERATION_WIDTH = 16,
    parameter PACKAGE_ID_WIDTH = 32,
    parameter MAPPING_ID_WIDTH = 32,
    parameter CONTEXT_ID_WIDTH = 8,
    parameter CLUSTER_ID_WIDTH = 8,
    parameter EXECUTION_EPOCH_WIDTH = 8,
    parameter ALLOCATION_GENERATION_WIDTH = 16,
    parameter RUNTIME_TAG_WIDTH = 16,
    parameter EVENT_SEQUENCE_WIDTH = 16,
    parameter TIMESTAMP_WIDTH = 64,
    parameter DEADLINE_WIDTH = 64,
    parameter ESTIMATED_CYCLES_WIDTH = 48,
    parameter BANDWIDTH_WIDTH = 32,
    parameter POWER_BUDGET_WIDTH = 32,
    parameter ENERGY_BUDGET_WIDTH = 48,
    parameter [NUM_CLUSTERS-1:0] CLUSTER_PRESENT_MASK = '1,
    parameter [NUM_CLUSTERS*32-1:0] CLUSTER_CAPABILITY_TABLE = '1,
    parameter [NUM_CLUSTERS*16-1:0] CLUSTER_COMPATIBILITY_TABLE = default_compatibility(),
    parameter [NUM_CLUSTERS*16-1:0] CLUSTER_MEMORY_PORT_TABLE = default_memory(),
    parameter [NUM_CLUSTERS*32-1:0] CLUSTER_SCRATCHPAD_REGION_TABLE = default_scratchpad(),
    parameter [MAX_OWNERS*16-1:0] OWNER_ID_TABLE = default_owners()
) (
    input wire i_clk,
    input wire i_rstb,
    input wire i_clock_ready,
    input wire i_power_good,
    input wire i_test_mode,
    input wire i_scan_enable,
    output wire o_clock_enable,
    output wire o_retention_save,
    output wire o_retention_restore,
    output wire o_isolation_enable,
    output wire o_idle,
    output wire o_quiescent,
    output wire o_recovery_required,
    output wire o_integrity_error,
    input wire i_reconcile_valid,
    input wire i_reconcile_clean,
    output wire o_reconcile_ready,
    input wire [63:0] i_reconcile_manifest,
    input wire [NUM_CLUSTERS-1:0] i_reconcile_cluster_busy_mask,
    input wire [5:0] i_reconcile_service_busy,
    input wire [15:0] i_reconcile_tag_base,
    input wire [15:0] i_reconcile_allocation_base,
    input wire [7:0] i_reconcile_epoch_base,
    input wire i_submit_valid,
    input wire i_submit_integrity_valid,
    input wire i_submit_admission_class,
    output wire o_submit_ready,
    input wire [15:0] i_submit_descriptor_id,
    input wire [15:0] i_submit_descriptor_generation,
    input wire [15:0] i_submit_owner_id,
    input wire [15:0] i_submit_kernel_id,
    input wire [15:0] i_submit_contract_version,
    input wire [7:0] i_submit_priority,
    input wire [63:0] i_submit_deadline,
    input wire [47:0] i_submit_estimated_cycles,
    input wire [7:0] i_submit_required_clusters,
    input wire [7:0] i_submit_preferred_clusters,
    input wire [31:0] i_submit_required_capabilities,
    input wire [7:0] i_submit_variant_count,
    input wire [MAX_PACKAGE_VARIANTS*256-1:0] i_submit_variant_records,
    input wire [255:0] i_submit_resource_record,
    input wire [127:0] i_submit_qos_record,
    input wire [127:0] i_submit_power_record,
    input wire [127:0] i_submit_lifecycle_record,
    input wire [15:0] i_submit_tag,
    output wire o_admission_valid,
    input wire i_admission_ready,
    output wire [198:0] o_admission_record,
    output wire o_result_valid,
    input wire i_result_ready,
    output wire [198:0] o_result_record,
    output wire o_runtime_event_valid,
    input wire i_runtime_event_ready,
    output wire [227:0] o_runtime_event_record,
    output wire o_policy_response_valid,
    input wire i_policy_response_ready,
    output wire [183:0] o_policy_response_record,
    input wire i_policy_valid,
    output wire o_policy_ready,
    input wire [277:0] i_policy_record,
    input wire i_event_valid,
    output wire o_event_ready,
    input wire [293:0] i_event_record,
    input wire i_snapshot_valid,
    output wire o_snapshot_ready,
    input wire [504:0] i_snapshot_record,
    output wire o_array_runtime_valid,
    input wire i_array_runtime_ready,
    output wire [916:0] o_array_runtime_record,
    input wire i_array_runtime_response_valid,
    output wire o_array_runtime_response_ready,
    input wire [215:0] i_array_runtime_response_record,
    output wire [5:0] o_service_valid,
    input wire [5:0] i_service_ready,
    output wire [5501:0] o_service_record,
    input wire [5:0] i_service_response_valid,
    output wire [5:0] o_service_response_ready,
    input wire [1295:0] i_service_response_record,
    output wire [NUM_CLUSTERS-1:0] o_cluster_reserved_mask,
    output wire [NUM_CLUSTERS-1:0] o_cluster_fault_mask,
    output wire [7:0] o_pending_count,
    output wire [7:0] o_active_count,
    output wire [MAX_PENDING_KERNELS-1:0] o_record_valid,
    output wire [MAX_PENDING_KERNELS*5-1:0] o_record_state,
    output wire [MAX_PENDING_KERNELS*152-1:0] o_record_identity,
    output wire [MAX_PENDING_KERNELS*16-1:0] o_record_cluster_mask,
    output wire [MAX_PENDING_KERNELS*AGE_COUNTER_WIDTH-1:0] o_record_age,
    output wire [MAX_PENDING_KERNELS*64-1:0] o_record_run_cycles,
    output wire [MAX_PENDING_KERNELS*256-1:0] o_record_snapshot_metrics,
    output wire [63:0] o_time,
    output wire o_action_active,
    output wire o_action_sent,
    output wire o_action_timed_out,
    output wire [916:0] o_action_record,
    output wire [2:0] o_action_endpoint,
    output wire [31:0] o_action_timer,
    output wire [7:0] o_error_code,
    input wire i_counter_read,
    input wire [3:0] i_counter_index,
    input wire i_counter_snapshot,
    output wire o_counter_valid,
    output wire [63:0] o_counter_data,
    output wire o_counter_overflow,
    output wire [MAX_PENDING_KERNELS-1:0] o_record_deadline_warned,
    output wire o_diagnostic_overflow,
    output wire [MAX_PENDING_KERNELS-1:0] o_record_reserved,
    output wire [MAX_PENDING_KERNELS-1:0] o_record_array_owned,
    output wire [MAX_PENDING_KERNELS*6-1:0] o_record_service_owned,
    output wire [MAX_PENDING_KERNELS*64-1:0] o_record_allocated_cycles,
    output wire [MAX_PENDING_KERNELS-1:0] o_scheduler_eligible,
    output wire [MAX_PENDING_KERNELS*8-1:0] o_scheduler_rank,
    output wire o_scheduler_grant_valid,
    output wire [3:0] o_scheduler_grant_index,
    output wire [15:0] o_dma_reserved_mask,
    output wire [15:0] o_memory_reserved_mask,
    output wire [31:0] o_scratchpad_reserved_mask,
    output wire [31:0] o_event_reserved_mask,
    output wire [15:0] o_counter_reserved_mask,
    output wire [63:0] o_memory_bandwidth_reserved,
    output wire [63:0] o_noc_bandwidth_reserved,
    output wire [63:0] o_power_reserved,
    input wire i_counter_read_snapshot,
    output wire o_counter_snapshot_valid
);
    import runtime_controller_pkg::*;
    function automatic logic [NUM_CLUSTERS*16-1:0] default_compatibility();
        for (int c = 0; c < NUM_CLUSTERS; c++)
            default_compatibility[c*16+:16] = 16'((64'd1 << NUM_CLUSTERS) - 1);
    endfunction
    function automatic logic [NUM_CLUSTERS*16-1:0] default_memory();
        for (int c = 0; c < NUM_CLUSTERS; c++)
            default_memory[c*16+:16] = 16'((64'd1 << MAX_MEMORY_PORTS) - 1);
    endfunction
    function automatic logic [NUM_CLUSTERS*32-1:0] default_scratchpad();
        for (int c = 0; c < NUM_CLUSTERS; c++)
            default_scratchpad[c*32+:32] = 32'((64'd1 << MAX_SCRATCHPAD_REGIONS) - 1);
    endfunction
    function automatic logic [MAX_OWNERS*16-1:0] default_owners();
        for (int o = 0; o < MAX_OWNERS; o++) default_owners[o*16+:16] = 16'(o + 1);
    endfunction
    function automatic bit owners_valid();
        owners_valid = ((^OWNER_ID_TABLE == 1'b0) || (^OWNER_ID_TABLE == 1'b1)) === 1'b1;
        for (int a = 0; a < MAX_OWNERS; a++) begin
            if (OWNER_ID_TABLE[a*16+:16] == 0) owners_valid = 0;
            for (int b = 0; b < a; b++)
                if (OWNER_ID_TABLE[a*16+:16] == OWNER_ID_TABLE[b*16+:16]) owners_valid = 0;
        end
    endfunction
    localparam bit PARAMETERS_VALID =
        ((64'(RUNTIME_PROFILE) >= 64'd0 && 64'(RUNTIME_PROFILE) <= 64'd1) === 1'b1) &&
        (((^RUNTIME_PROFILE == 1'b0) || (^RUNTIME_PROFILE == 1'b1)) === 1'b1) &&
        ((64'(NUM_CLUSTERS) >= 64'd1 && 64'(NUM_CLUSTERS) <= 64'd16) === 1'b1) &&
        (((^NUM_CLUSTERS == 1'b0) || (^NUM_CLUSTERS == 1'b1)) === 1'b1) &&
        ((64'(MAX_PENDING_KERNELS) >= 64'd1 && 64'(MAX_PENDING_KERNELS) <= 64'd16) === 1'b1) &&
        (((^MAX_PENDING_KERNELS == 1'b0) || (^MAX_PENDING_KERNELS == 1'b1)) === 1'b1) &&
        ((64'(MAX_ACTIVE_KERNELS) >= 64'd1 && 64'(MAX_ACTIVE_KERNELS) <= 64'd4) === 1'b1) &&
        (((^MAX_ACTIVE_KERNELS == 1'b0) || (^MAX_ACTIVE_KERNELS == 1'b1)) === 1'b1) &&
        ((64'(MAX_OWNERS) >= 64'd1 && 64'(MAX_OWNERS) <= 64'd16) === 1'b1) &&
        (((^MAX_OWNERS == 1'b0) || (^MAX_OWNERS == 1'b1)) === 1'b1) &&
        ((64'(MAX_PACKAGE_VARIANTS) >= 64'd1 && 64'(MAX_PACKAGE_VARIANTS) <= 64'd4) === 1'b1) &&
        (((^MAX_PACKAGE_VARIANTS == 1'b0) || (^MAX_PACKAGE_VARIANTS == 1'b1)) === 1'b1) &&
        ((64'(MAX_CLUSTERS_PER_KERNEL) >= 64'd1 && 64'(MAX_CLUSTERS_PER_KERNEL) <= 64'd16) === 1'b1)
            &&
        (((^MAX_CLUSTERS_PER_KERNEL == 1'b0) || (^MAX_CLUSTERS_PER_KERNEL == 1'b1)) === 1'b1) &&
        ((64'(MAX_DMA_CHANNELS) >= 64'd1 && 64'(MAX_DMA_CHANNELS) <= 64'd16) === 1'b1) &&
        (((^MAX_DMA_CHANNELS == 1'b0) || (^MAX_DMA_CHANNELS == 1'b1)) === 1'b1) &&
        ((64'(MAX_MEMORY_PORTS) >= 64'd1 && 64'(MAX_MEMORY_PORTS) <= 64'd16) === 1'b1) &&
        (((^MAX_MEMORY_PORTS == 1'b0) || (^MAX_MEMORY_PORTS == 1'b1)) === 1'b1) &&
        ((64'(MAX_SCRATCHPAD_REGIONS) >= 64'd1 && 64'(MAX_SCRATCHPAD_REGIONS) <= 64'd32) === 1'b1)
            &&
        (((^MAX_SCRATCHPAD_REGIONS == 1'b0) || (^MAX_SCRATCHPAD_REGIONS == 1'b1)) === 1'b1) &&
        ((64'(MAX_EVENT_NAMESPACES) >= 64'd1 && 64'(MAX_EVENT_NAMESPACES) <= 64'd32) === 1'b1) &&
        (((^MAX_EVENT_NAMESPACES == 1'b0) || (^MAX_EVENT_NAMESPACES == 1'b1)) === 1'b1) &&
        ((64'(MAX_NOC_QOS_PROFILES) >= 64'd1 && 64'(MAX_NOC_QOS_PROFILES) <= 64'd16) === 1'b1) &&
        (((^MAX_NOC_QOS_PROFILES == 1'b0) || (^MAX_NOC_QOS_PROFILES == 1'b1)) === 1'b1) &&
        ((64'(MAX_MEMORY_QOS_PROFILES) >= 64'd1 && 64'(MAX_MEMORY_QOS_PROFILES) <= 64'd16) === 1'b1)
            &&
        (((^MAX_MEMORY_QOS_PROFILES == 1'b0) || (^MAX_MEMORY_QOS_PROFILES == 1'b1)) === 1'b1) &&
        ((64'(MAX_POWER_PROFILES) >= 64'd1 && 64'(MAX_POWER_PROFILES) <= 64'd16) === 1'b1) &&
        (((^MAX_POWER_PROFILES == 1'b0) || (^MAX_POWER_PROFILES == 1'b1)) === 1'b1) &&
        ((64'(NUM_PRIORITY_LEVELS) >= 64'd1 && 64'(NUM_PRIORITY_LEVELS) <= 64'd16) === 1'b1) &&
        (((^NUM_PRIORITY_LEVELS == 1'b0) || (^NUM_PRIORITY_LEVELS == 1'b1)) === 1'b1) &&
        ((64'(SUBMISSION_QUEUE_DEPTH) >= 64'd2 && 64'(SUBMISSION_QUEUE_DEPTH) <= 64'd32) === 1'b1)
            &&
        (((^SUBMISSION_QUEUE_DEPTH == 1'b0) || (^SUBMISSION_QUEUE_DEPTH == 1'b1)) === 1'b1) &&
        ((64'(ACTION_QUEUE_DEPTH) >= 64'd2 && 64'(ACTION_QUEUE_DEPTH) <= 64'd32) === 1'b1) &&
        (((^ACTION_QUEUE_DEPTH == 1'b0) || (^ACTION_QUEUE_DEPTH == 1'b1)) === 1'b1) &&
        ((64'(RESPONSE_QUEUE_DEPTH) >= 64'd2 && 64'(RESPONSE_QUEUE_DEPTH) <= 64'd32) === 1'b1) &&
        (((^RESPONSE_QUEUE_DEPTH == 1'b0) || (^RESPONSE_QUEUE_DEPTH == 1'b1)) === 1'b1) &&
        ((64'(EVENT_QUEUE_DEPTH) >= 64'd2 && 64'(EVENT_QUEUE_DEPTH) <= 64'd64) === 1'b1) &&
        (((^EVENT_QUEUE_DEPTH == 1'b0) || (^EVENT_QUEUE_DEPTH == 1'b1)) === 1'b1) &&
        ((64'(COUNTER_SNAPSHOT_SLOTS) >= 64'd2 && 64'(COUNTER_SNAPSHOT_SLOTS) <= 64'd16) === 1'b1)
            &&
        (((^COUNTER_SNAPSHOT_SLOTS == 1'b0) || (^COUNTER_SNAPSHOT_SLOTS == 1'b1)) === 1'b1) &&
        ((64'(AGE_COUNTER_WIDTH) >= 64'd1 && 64'(AGE_COUNTER_WIDTH) <= 64'd32) === 1'b1) &&
        (((^AGE_COUNTER_WIDTH == 1'b0) || (^AGE_COUNTER_WIDTH == 1'b1)) === 1'b1) &&
        ((64'(HIGH_PRIORITY_BURST_LIMIT) >= 64'd1 && 64'(HIGH_PRIORITY_BURST_LIMIT) <= 64'd65535)
            === 1'b1) &&
        (((^HIGH_PRIORITY_BURST_LIMIT == 1'b0) || (^HIGH_PRIORITY_BURST_LIMIT == 1'b1)) === 1'b1) &&
        ((64'(AGE_ESCALATION_CYCLES) >= 64'd1 && 64'(AGE_ESCALATION_CYCLES) <= 64'd4294967295) ===
            1'b1) &&
        (((^AGE_ESCALATION_CYCLES == 1'b0) || (^AGE_ESCALATION_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(POLICY_SAMPLE_INTERVAL) >= 64'd1 && 64'(POLICY_SAMPLE_INTERVAL) <= 64'd4294967295) ===
            1'b1) &&
        (((^POLICY_SAMPLE_INTERVAL == 1'b0) || (^POLICY_SAMPLE_INTERVAL == 1'b1)) === 1'b1) &&
        ((64'(ACTION_TIMEOUT_CYCLES) >= 64'd1 && 64'(ACTION_TIMEOUT_CYCLES) <= 64'd4294967295) ===
            1'b1) &&
        (((^ACTION_TIMEOUT_CYCLES == 1'b0) || (^ACTION_TIMEOUT_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(KERNEL_TIMEOUT_CYCLES) >= 64'd0 && 64'(KERNEL_TIMEOUT_CYCLES) <= 64'd4294967295) ===
            1'b1) &&
        (((^KERNEL_TIMEOUT_CYCLES == 1'b0) || (^KERNEL_TIMEOUT_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(CONTROL_PROTECTION) >= 64'd0 && 64'(CONTROL_PROTECTION) <= 64'd2) === 1'b1) &&
        (((^CONTROL_PROTECTION == 1'b0) || (^CONTROL_PROTECTION == 1'b1)) === 1'b1) &&
        ((64'(MEMORY_BANDWIDTH_CAPACITY) >= 64'd1 && 64'(MEMORY_BANDWIDTH_CAPACITY) <=
            64'd4294967295) === 1'b1) &&
        (((^MEMORY_BANDWIDTH_CAPACITY == 1'b0) || (^MEMORY_BANDWIDTH_CAPACITY == 1'b1)) === 1'b1) &&
        ((64'(NOC_BANDWIDTH_CAPACITY) >= 64'd1 && 64'(NOC_BANDWIDTH_CAPACITY) <= 64'd4294967295) ===
            1'b1) &&
        (((^NOC_BANDWIDTH_CAPACITY == 1'b0) || (^NOC_BANDWIDTH_CAPACITY == 1'b1)) === 1'b1) &&
        ((64'(POWER_CAPACITY) >= 64'd1 && 64'(POWER_CAPACITY) <= 64'd4294967295) === 1'b1) &&
        (((^POWER_CAPACITY == 1'b0) || (^POWER_CAPACITY == 1'b1)) === 1'b1) &&
        ((64'(ENFORCED_SERVICE_MASK) >= 64'd0 && 64'(ENFORCED_SERVICE_MASK) <= 64'd63) === 1'b1) &&
        (((^ENFORCED_SERVICE_MASK == 1'b0) || (^ENFORCED_SERVICE_MASK == 1'b1)) === 1'b1) &&
        ((64'(ARCHITECTURE_ID) >= 64'd1 && 64'(ARCHITECTURE_ID) <= 64'd4294967295) === 1'b1) &&
        (((^ARCHITECTURE_ID == 1'b0) || (^ARCHITECTURE_ID == 1'b1)) === 1'b1) &&
        ((64'(PROTOCOL_PROOF_ID) >= 64'd1 && 64'(PROTOCOL_PROOF_ID) <= 64'd4294967295) === 1'b1) &&
        (((^PROTOCOL_PROOF_ID == 1'b0) || (^PROTOCOL_PROOF_ID == 1'b1)) === 1'b1) &&
        (ENABLE_RESOURCE_RESIZING === 0) &&
        (ENABLE_MIGRATION === 0) &&
        (ENABLE_TRACE === 0) &&
        (ASYNC_SYSTEM_CLOCK === 0) &&
        (ASYNC_ARRAY_CLOCK === 0) &&
        (ASYNC_EVENT_CLOCK === 0) &&
        (ASYNC_RESET === 0) &&
        (ENABLE_QOS === 0 || ENABLE_QOS === 1) &&
        (ENABLE_DEADLINE_MONITORING === 0 || ENABLE_DEADLINE_MONITORING === 1) &&
        (ENABLE_SAFE_SUSPEND === 0 || ENABLE_SAFE_SUSPEND === 1) &&
        (ENABLE_POWER_POLICY === 0 || ENABLE_POWER_POLICY === 1) &&
        (ENABLE_COUNTER_FEEDBACK === 0 || ENABLE_COUNTER_FEEDBACK === 1) &&
        (ENABLE_FAULT_AWARE_ALLOCATION === 0 || ENABLE_FAULT_AWARE_ALLOCATION === 1) &&
        ((MAX_ACTIVE_KERNELS <= MAX_PENDING_KERNELS &&
            MAX_ACTIVE_KERNELS <= NUM_CLUSTERS) === 1'b1) &&
        ((MAX_CLUSTERS_PER_KERNEL <= NUM_CLUSTERS) === 1'b1) &&
        ((RUNTIME_PROFILE != 0 || (MAX_ACTIVE_KERNELS == 1 &&
            MAX_PACKAGE_VARIANTS == 1)) === 1'b1) &&
        (((^CLUSTER_PRESENT_MASK == 1'b0) || (^CLUSTER_PRESENT_MASK == 1'b1)) === 1'b1) &&
        (((^CLUSTER_CAPABILITY_TABLE == 1'b0) || (^CLUSTER_CAPABILITY_TABLE == 1'b1)) === 1'b1) &&
        (((^CLUSTER_COMPATIBILITY_TABLE == 1'b0) || (^CLUSTER_COMPATIBILITY_TABLE == 1'b1)) === 1'b1) &&
        (((^CLUSTER_MEMORY_PORT_TABLE == 1'b0) || (^CLUSTER_MEMORY_PORT_TABLE == 1'b1)) === 1'b1) &&
        (((^CLUSTER_SCRATCHPAD_REGION_TABLE == 1'b0) || (^CLUSTER_SCRATCHPAD_REGION_TABLE == 1'b1)) === 1'b1) &&
        (OWNER_ID_WIDTH === 16) &&
        (KERNEL_ID_WIDTH === 16) &&
        (DESCRIPTOR_ID_WIDTH === 16) &&
        (DESCRIPTOR_GENERATION_WIDTH === 16) &&
        (PACKAGE_ID_WIDTH === 32) &&
        (MAPPING_ID_WIDTH === 32) &&
        (CONTEXT_ID_WIDTH === 8) &&
        (CLUSTER_ID_WIDTH === 8) &&
        (EXECUTION_EPOCH_WIDTH === 8) &&
        (ALLOCATION_GENERATION_WIDTH === 16) &&
        (RUNTIME_TAG_WIDTH === 16) &&
        (EVENT_SEQUENCE_WIDTH === 16) &&
        (TIMESTAMP_WIDTH === 64) &&
        (DEADLINE_WIDTH === 64) &&
        (ESTIMATED_CYCLES_WIDTH === 48) &&
        (BANDWIDTH_WIDTH === 32) &&
        (POWER_BUDGET_WIDTH === 32) &&
        (ENERGY_BUDGET_WIDTH === 48) &&
        ((64'd1 << AGE_COUNTER_WIDTH) - 1 >=
            64'(NUM_PRIORITY_LEVELS - 1) * 64'(AGE_ESCALATION_CYCLES)) &&
        owners_valid();
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        runtime_controller_parameters_must_be_valid invalid_parameters ();
    end else begin : g_runtime
        localparam int N = MAX_PENDING_KERNELS;
        localparam int V = MAX_PACKAGE_VARIANTS;
        localparam int SOURCES = NUM_CLUSTERS + 1;
        localparam int AW = $bits(action_t);
        localparam int KW = $bits(ack_t);
        localparam int NW = $bits(notice_t);
        localparam int EW = $bits(event_t);
        localparam int SW = $bits(snapshot_t);
        localparam int DW = $bits(diagnostic_t);
        localparam int PW = $bits(policy_reply_t);
        localparam int SI = N > 1 ? $clog2(N) : 1;

        // Parameter-dependent storage types stay local. Public fixed-layout
        // commands, variants, identities and errors are declared in the package.
        typedef struct packed {
            logic [V*256-1:0] variants;
            resource_t resources;
            qos_t qos;
            power_t power;
            lifecycle_t lifecycle;
            identity_t identity;
            logic [63:0] deadline;
            logic [47:0] estimated_cycles;
            logic [31:0] capabilities;
            logic [15:0] tag;
            logic [15:0] version;
            logic [7:0] priority_value;
            logic [7:0] minimum_clusters;
            logic [7:0] preferred_clusters;
            logic [7:0] variant_count;
            logic admission_class;
            logic integrity;
        } descriptor_t;

        typedef struct packed {
            logic valid;
            logic [4:0] state;
            logic [4:0] phase;
            logic [2:0] cursor;
            logic reserved;
            logic array_owned;
            logic [5:0] services_owned;
            logic admitted;
            logic admission_queued;
            logic admission_delivered;
            logic result_queued;
            logic cancel;
            logic started;
            logic compute_done;
            logic external_done;
            logic inputs_ready;
            logic output_space;
            logic uncertain;
            logic deadline_warned;
            logic snapshot_valid;
            logic [7:0] error;
            logic [2:0] terminal_status;
            logic [2:0] variant_index;
            identity_t identity;
            logic [15:0] clusters;
            logic [AGE_COUNTER_WIDTH-1:0] age;
            logic [63:0] run_cycles;
            logic [63:0] allocated_cycles;
            logic [15:0] snapshot_generation;
            logic [63:0] snapshot_timestamp;
            logic [63:0] sample_time;
            logic [63:0] completion_time;
            logic [255:0] metrics;
            logic [SOURCES*16-1:0] event_next;
            logic [SOURCES-1:0] event_exhausted;
        } record_t;

        typedef struct packed {
            logic reconciled;
            logic enabled;
            logic halt;
            logic active;
            logic sent;
            logic timed_out;
            logic [2:0] endpoint;
            logic [3:0] slot;
            action_t action;
            logic [31:0] timer;
            logic [15:0] next_tag;
            logic [15:0] next_allocation;
            logic [7:0] next_epoch;
            logic [15:0] fault_mask;
            logic [31:0] burst;
            logic [7:0] first_error;
            logic diagnostic_overflow;
            logic policy_active;
            logic [3:0] policy_slot;
            policy_t policy;
            logic [MAX_OWNERS-1:0] bounds_valid;
            logic [MAX_OWNERS*8-1:0] priority_bounds;
            logic [MAX_OWNERS*32-1:0] power_bounds;
            logic [MAX_OWNERS*32-1:0] bandwidth_bounds;
        } control_t;

        localparam int RW = $bits(record_t);
        localparam int IW = $bits(descriptor_t);
        localparam int GW = $bits(control_t);
        wire [RW-1:0] record_q[N];
        logic [RW-1:0] record_d[N];
        wire [IW-1:0] descriptor_q[N];
        logic [IW-1:0] descriptor_d[N];
        control_t q;
        control_t d;
        descriptor_t submission;
        wire [N-1:0] record_bad;
        wire [N-1:0] record_corrected;
        wire [N-1:0] descriptor_bad;
        wire [N-1:0] descriptor_corrected;
        wire control_bad;
        wire control_corrected;
        wire [7:0] queue_bad;
        wire integrity_bad = control_bad || (|record_bad) || (|descriptor_bad) || (|queue_bad);
        wire clock_ok = i_rstb && i_clock_ready && i_power_good && !i_test_mode && !i_scan_enable;
        wire run = clock_ok && !integrity_bad && !q.halt;
        wire [63:0] time_value;
        wire time_overflow;
        wire command_fire;
        wire response_match;
        wire command_valid;
        wire command_ready;
        wire [AW-1:0] command_bits;
        action_t command_record;
        ack_t response_record;
        wire submission_valid;
        logic submission_pop;
        wire submission_ready;
        wire [SI-1:0] submission_slot;
        wire admission_valid;
        wire admission_ready;
        logic admission_push;
        notice_t admission_input;
        notice_t admission_output;
        wire result_valid;
        wire result_ready;
        logic result_push;
        notice_t result_input;
        notice_t result_output;
        wire event_valid;
        logic event_pop;
        wire event_ready;
        event_t incoming_event;
        wire snapshot_valid;
        logic snapshot_pop;
        wire snapshot_ready;
        snapshot_t incoming_snapshot;
        wire diagnostic_valid;
        wire diagnostic_ready;
        logic diagnostic_push;
        diagnostic_t diagnostic_input;
        wire [DW-1:0] diagnostic_output;
        wire policy_reply_valid;
        wire policy_reply_ready;
        logic policy_reply_push;
        policy_reply_t policy_reply_input;
        wire [PW-1:0] policy_reply_output;
        wire action_ready;
        logic action_push;
        action_t action_input;
        logic [N-1:0] free_requests;
        wire free_valid;
        wire [SI-1:0] free_index;
        logic [N-1:0] eligible;
        logic [N-1:0] ranked;
        wire grant_valid;
        wire [SI-1:0] grant_index;
        logic grant_accept;
        logic [15:0] selected_masks[N];
        integer selected_variants[N];
        integer ranks[N];
        logic [15:0] clusters_used;
        logic [15:0] dma_used;
        logic [15:0] memory_used;
        logic [31:0] scratchpad_used;
        logic [31:0] events_used;
        logic [15:0] counters_used;
        logic [63:0] memory_bandwidth_used;
        logic [63:0] noc_bandwidth_used;
        logic [63:0] power_used;
        logic [63:0] owner_power_used[MAX_OWNERS];
        logic [63:0] owner_bandwidth_used[MAX_OWNERS];
        integer active_count;
        integer pending_count;
        integer maximum_rank;
        integer minimum_rank;
        integer worker;
        logic recovery;
        logic [15:0] statistics;
        wire [15:0] statistics_overflow;
        wire counter_valid;
        wire counter_overflow;
        wire [63:0] counter_data;

        function automatic int owner_index(input logic [15:0] owner);
            owner_index = -1;

            for (int o = 0; o < MAX_OWNERS; o++)
                if (OWNER_ID_TABLE[o*16+:16] == owner) owner_index = o;
        endfunction

        function automatic variant_t get_variant(input descriptor_t desc, input int index);
            get_variant = 256'(desc.variants >> (index * 256));
        endfunction

        function automatic bit variant_legal(input descriptor_t desc, input variant_t variant);
            bit legal;
            legal = variant.reserved == 0 && variant.flags == 0 &&
                variant.architecture_id == ARCHITECTURE_ID && variant.proof_id == PROTOCOL_PROOF_ID
                    &&
                variant.package_id != 0 && variant.mapping_id != 0 &&
                variant.cluster_count == $countones(variant.cluster_mask) &&
                variant.cluster_count >= desc.minimum_clusters &&
                variant.cluster_count <= MAX_CLUSTERS_PER_KERNEL &&
                (variant.cluster_mask & ~16'(CLUSTER_PRESENT_MASK)) == 0 &&
                (variant.required_capabilities & desc.capabilities) == desc.capabilities &&
                variant.noc_profile < MAX_NOC_QOS_PROFILES &&
                variant.memory_profile < MAX_MEMORY_QOS_PROFILES &&
                variant.power_profile < MAX_POWER_PROFILES &&
                ((desc.power.profile_mask >> variant.power_profile) & 16'b1) != 0;

            for (int c = 0; c < NUM_CLUSTERS; c++) begin
                if (((variant.cluster_mask >> c) & 16'b1) != 0) begin
                    if ((CLUSTER_CAPABILITY_TABLE[c*32+:32] &
                        variant.required_capabilities) != variant.required_capabilities) legal = 0;

                    if ((variant.cluster_mask &
                        ~CLUSTER_COMPATIBILITY_TABLE[c*16+:16]) != 0) legal = 0;

                    if ((desc.resources.memory_mask &
                        ~CLUSTER_MEMORY_PORT_TABLE[c*16+:16]) != 0) legal = 0;

                    if ((desc.resources.scratchpad_mask &
                        ~CLUSTER_SCRATCHPAD_REGION_TABLE[c*32+:32]) != 0) legal = 0;
                end
            end

            return legal;
        endfunction

        function automatic logic [7:0] descriptor_error(input descriptor_t desc);
            bit legal_variant;
            legal_variant = 0;

            for (int v = 0; v < V; v++)
                if (v < desc.variant_count && variant_legal(desc, get_variant(desc, v)))
                    legal_variant = 1;

            if (!desc.integrity || desc.version != 1) return ERR_INTEGRITY;

            if (owner_index(desc.identity.owner_id) < 0) return ERR_OWNER;

            if (desc.identity.kernel_id == 0 || desc.priority_value >= NUM_PRIORITY_LEVELS ||
                desc.variant_count == 0 || desc.variant_count > V ||
                desc.minimum_clusters == 0 || desc.minimum_clusters > MAX_CLUSTERS_PER_KERNEL ||
                desc.preferred_clusters < desc.minimum_clusters ||
                desc.preferred_clusters > MAX_CLUSTERS_PER_KERNEL) return ERR_DESCRIPTOR;

            if (desc.resources.reserved != 0 || desc.resources.flags != 0 ||
                desc.qos.reserved != 0 || desc.qos.flags != 0 || desc.qos.latency_limit != 0 ||
                desc.power.reserved != 0 || desc.power.flags != 0 || desc.power.energy_budget != 0
                    ||
                desc.lifecycle.reserved != 0 || desc.lifecycle.flags[6:5] != 0)

                return ERR_UNSUPPORTED;

            if ((desc.lifecycle.flags[0] && !ENABLE_SAFE_SUSPEND) ||
                (desc.lifecycle.flags[4] && !ENABLE_COUNTER_FEEDBACK)) return ERR_UNSUPPORTED;

            if ((64'(desc.resources.dma_mask) >> MAX_DMA_CHANNELS) != 0 ||
                (64'(desc.resources.memory_mask) >> MAX_MEMORY_PORTS) != 0 ||
                (64'(desc.resources.scratchpad_mask) >> MAX_SCRATCHPAD_REGIONS) != 0 ||
                (64'(desc.resources.event_mask) >> MAX_EVENT_NAMESPACES) != 0 ||
                (desc.resources.services & 6'b010001) != 6'b010001 ||
                desc.resources.event_mask == 0 ||
                (desc.lifecycle.flags[4] && desc.resources.counter_mask == 0) ||
                (desc.resources.noc_bandwidth != 0 && !desc.resources.services[EP_NOC]) ||
                (desc.resources.memory_bandwidth != 0 && !desc.resources.services[EP_MEMORY]) ||
                (desc.resources.dma_mask != 0 && !desc.resources.services[EP_DMA]) ||
                (desc.resources.memory_mask != 0 && !desc.resources.services[EP_MEMORY]) ||
                (ENABLE_POWER_POLICY && !desc.resources.services[EP_POWER]) ||
                (!ENABLE_POWER_POLICY && desc.resources.services[EP_POWER])) return ERR_DESCRIPTOR;

            if (desc.resources.memory_bandwidth > MEMORY_BANDWIDTH_CAPACITY ||
                desc.resources.noc_bandwidth > NOC_BANDWIDTH_CAPACITY ||
                desc.resources.power > POWER_CAPACITY ||
                desc.resources.power > desc.power.budget ||
                desc.qos.memory_minimum > desc.resources.memory_bandwidth ||
                desc.qos.noc_minimum > desc.resources.noc_bandwidth) return ERR_BUDGET;

            if (desc.admission_class && (!ENABLE_QOS ||
                (desc.resources.services & ~6'(ENFORCED_SERVICE_MASK)) != 0)) return ERR_PROOF;

            if (!legal_variant) return ERR_CAPABILITY;

            return ERR_NONE;
        endfunction

        function automatic logic [63:0] resource_mask(input resource_t resources, input int ep);
            case (ep)
                EP_DMA: return 64'(resources.dma_mask);
                EP_MEMORY: return {resources.scratchpad_mask, 16'b0, resources.memory_mask};
                EP_EVENT: return {16'b0, resources.counter_mask, resources.event_mask};
                default: return '0;
            endcase
        endfunction

        function automatic notice_t notice(input record_t record, input descriptor_t desc,
                                             input logic [2:0] status, input int slot);
            notice_t value;
            value = '0;
            value.identity = record.identity;
            value.status = status;
            value.error = record.error;
            value.cluster_mask = record.clusters;
            value.tag = desc.tag;
            value.slot = 4'(slot);

            return value;
        endfunction

        function automatic record_t begin_cleanup(input record_t record);
            record_t value;
            value = record;
            value.cursor = 5;
            value.state = value.started && value.state != RT_ERROR &&
                value.state != RT_SUSPENDED ? RT_DRAINING : RT_TERMINATING;
            value.phase = value.started ? PH_ARRAY_DRAIN : PH_RELEASE_SERVICES;

            if (value.started && value.terminal_status != NOTICE_SUCCEEDED)
                value.phase = PH_ARRAY_DRAIN;

            return value;
        endfunction

        // Immutable descriptors and frequently updated lifecycle state use
        // separate protected banks. Corrected words are scrubbed on the next edge.
        for (genvar slot = 0; slot < N; slot++) begin : g_record
            tile_shell_state #(.WIDTH(RW), .PROTECTION(CONTROL_PROTECTION)) u_state (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(record_d[slot] != record_q[slot] || record_corrected[slot]),
                .i_data(record_d[slot]),
                .o_data(record_q[slot]),
                .o_bad(record_bad[slot]),
                .o_corrected(record_corrected[slot])
            );

            tile_shell_state #(.WIDTH(IW), .PROTECTION(CONTROL_PROTECTION)) u_descriptor (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(descriptor_d[slot] != descriptor_q[slot] || descriptor_corrected[slot]),
                .i_data(descriptor_d[slot]),
                .o_data(descriptor_q[slot]),
                .o_bad(descriptor_bad[slot]),
                .o_corrected(descriptor_corrected[slot])
            );
        end

        tile_shell_state #(.WIDTH(GW), .PROTECTION(CONTROL_PROTECTION)) u_control (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(d != q || control_corrected),
            .i_data(d),
            .o_data(q),
            .o_bad(control_bad),
            .o_corrected(control_corrected)
        );

        counter #(.WIDTH(64), .SATURATE(1)) u_time (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(clock_ok),
            .i_clear(1'b0),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value(64'b0),
            .o_count(time_value),
            .o_overflow(time_overflow),
            .o_underflow(),
            .o_terminal()
        );

        priority_encoder #(.WIDTH(N)) u_free (
            .i_request(free_requests),
            .o_valid(free_valid),
            .o_index(free_index),
            .o_onehot(),
            .o_multiple()
        );

        round_robin_arbiter #(.NUM_REQUESTERS(N), .HAS_LOCK(0), .HOLD_PENDING(0)) u_scheduler (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_request(ranked),
            .i_eligible(eligible),
            .i_lock({N{1'b0}}),
            .i_accept(grant_accept),
            .i_flush(1'b0),
            .o_grant_valid(grant_valid),
            .o_grant_index(grant_index),
            .o_grant_onehot(),
            .o_grant_lock(),
            .o_grant_accepted(),
            .o_contended(),
            .o_pending(),
            .o_locked(),
            .o_lock_owner(),
            .o_protocol_error()
        );

        event_barrier_queue #(
            .WIDTH(SI),
            .DEPTH(SUBMISSION_QUEUE_DEPTH),
            .PROTECTED(CONTROL_PROTECTION != 0)
        ) u_submission_queue (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_flush(1'b0),
            .i_valid(i_submit_valid && o_submit_ready),
            .o_ready(submission_ready),
            .i_data(free_index),
            .o_valid(submission_valid),
            .i_ready(submission_pop),
            .o_data(submission_slot),
            .o_occupancy(),
            .o_corrupt(queue_bad[0]),
            .o_occupied(),
            .o_contents()
        );

        event_barrier_queue #(
            .WIDTH(AW),
            .DEPTH(ACTION_QUEUE_DEPTH),
            .PROTECTED(CONTROL_PROTECTION != 0)
        ) u_action_queue (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_flush(1'b0),
            .i_valid(action_push),
            .o_ready(action_ready),
            .i_data(action_input),
            .o_valid(command_valid),
            .i_ready(command_fire),
            .o_data(command_bits),
            .o_occupancy(),
            .o_corrupt(queue_bad[1]),
            .o_occupied(),
            .o_contents()
        );

        event_barrier_queue #(
            .WIDTH(NW),
            .DEPTH(RESPONSE_QUEUE_DEPTH),
            .PROTECTED(CONTROL_PROTECTION != 0)
        ) u_admission_queue (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_flush(1'b0),
            .i_valid(admission_push),
            .o_ready(admission_ready),
            .i_data(admission_input),
            .o_valid(admission_valid),
            .i_ready(run && i_admission_ready),
            .o_data(admission_output),
            .o_occupancy(),
            .o_corrupt(queue_bad[2]),
            .o_occupied(),
            .o_contents()
        );

        event_barrier_queue #(
            .WIDTH(NW),
            .DEPTH(RESPONSE_QUEUE_DEPTH),
            .PROTECTED(CONTROL_PROTECTION != 0)
        ) u_result_queue (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_flush(1'b0),
            .i_valid(result_push),
            .o_ready(result_ready),
            .i_data(result_input),
            .o_valid(result_valid),
            .i_ready(run && i_result_ready),
            .o_data(result_output),
            .o_occupancy(),
            .o_corrupt(queue_bad[3]),
            .o_occupied(),
            .o_contents()
        );

        event_barrier_queue #(
            .WIDTH(EW),
            .DEPTH(EVENT_QUEUE_DEPTH),
            .PROTECTED(CONTROL_PROTECTION != 0)
        ) u_event_queue (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_flush(1'b0),
            .i_valid(run && q.reconciled && i_event_valid),
            .o_ready(event_ready),
            .i_data(i_event_record),
            .o_valid(event_valid),
            .i_ready(event_pop),
            .o_data(incoming_event),
            .o_occupancy(),
            .o_corrupt(queue_bad[4]),
            .o_occupied(),
            .o_contents()
        );

        event_barrier_queue #(
            .WIDTH(SW),
            .DEPTH(COUNTER_SNAPSHOT_SLOTS),
            .PROTECTED(CONTROL_PROTECTION != 0)
        ) u_snapshot_queue (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_flush(1'b0),
            .i_valid(run && q.reconciled && i_snapshot_valid),
            .o_ready(snapshot_ready),
            .i_data(i_snapshot_record),
            .o_valid(snapshot_valid),
            .i_ready(snapshot_pop),
            .o_data(incoming_snapshot),
            .o_occupancy(),
            .o_corrupt(queue_bad[5]),
            .o_occupied(),
            .o_contents()
        );

        event_barrier_queue #(
            .WIDTH(DW),
            .DEPTH(EVENT_QUEUE_DEPTH),
            .PROTECTED(CONTROL_PROTECTION != 0)
        ) u_diagnostic_queue (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_flush(1'b0),
            .i_valid(diagnostic_push),
            .o_ready(diagnostic_ready),
            .i_data(diagnostic_input),
            .o_valid(diagnostic_valid),
            .i_ready(run && i_runtime_event_ready),
            .o_data(diagnostic_output),
            .o_occupancy(),
            .o_corrupt(queue_bad[6]),
            .o_occupied(),
            .o_contents()
        );

        event_barrier_queue #(
            .WIDTH(PW),
            .DEPTH(RESPONSE_QUEUE_DEPTH),
            .PROTECTED(CONTROL_PROTECTION != 0)
        ) u_policy_reply_queue (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_flush(1'b0),
            .i_valid(policy_reply_push),
            .o_ready(policy_reply_ready),
            .i_data(policy_reply_input),
            .o_valid(policy_reply_valid),
            .i_ready(run && i_policy_response_ready),
            .o_data(policy_reply_output),
            .o_occupancy(),
            .o_corrupt(queue_bad[7]),
            .o_occupied(),
            .o_contents()
        );

        performance_counters #(
            .COUNTER_WIDTH(64),
            .NUM_COUNTERS(16),
            .NUM_EVENTS(16),
            .INCREMENT_WIDTH(1),
            .HAS_THRESHOLD(0)
        ) u_statistics (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_global_enable(clock_ok),
            .i_freeze(1'b0),
            .i_counter_enable(16'hffff),
            .i_clear(16'b0),
            .i_event_select(64'hfedcba9876543210),
            .i_event_valid(statistics),
            .i_event_increment(16'hffff),
            .i_threshold_enable(16'b0),
            .i_threshold_value(1024'b0),
            .i_snapshot(i_counter_snapshot && run),
            .i_read_enable(i_counter_read && run),
            .i_read_snapshot(i_counter_read_snapshot),
            .i_read_index(i_counter_index),
            .o_read_data(counter_data),
            .o_read_valid(counter_valid),
            .o_read_overflow(counter_overflow),
            .o_counter_overflow(statistics_overflow),
            .o_threshold_event(),
            .o_config_error(),
            .o_snapshot_valid(o_counter_snapshot_valid)
        );

        assign o_counter_data = counter_data;
        assign o_counter_valid = counter_valid;
        assign o_counter_overflow = counter_overflow;
        assign o_submit_ready = run && q.reconciled && q.enabled && !recovery &&
            free_valid && submission_ready;
        assign o_admission_valid = run && admission_valid;
        assign o_admission_record = admission_output;
        assign o_result_valid = run && result_valid;
        assign o_result_record = result_output;
        assign o_policy_response_valid = run && policy_reply_valid;
        assign o_policy_response_record = policy_reply_output;
        assign o_runtime_event_valid = run && diagnostic_valid;
        assign o_runtime_event_record = diagnostic_output;
        assign o_event_ready = run && event_ready && q.reconciled;
        assign o_snapshot_ready = run && snapshot_ready && q.reconciled;
        assign o_policy_ready = run && q.reconciled && !q.policy_active && policy_reply_ready;
        assign o_array_runtime_valid = run && command_valid && q.endpoint == EP_ARRAY;
        assign o_array_runtime_record = command_bits;
        assign o_array_runtime_response_ready = run;
        assign o_service_response_ready = {6{run}};

        for (genvar ep = 0; ep < 6; ep++) begin : g_service
            assign o_service_valid[ep] = run && command_valid && q.endpoint == 3'(ep);
            assign o_service_record[ep*AW+:AW] = command_bits;
        end

        assign command_ready = q.endpoint == EP_ARRAY ? i_array_runtime_ready :
            i_service_ready[q.endpoint];
        assign command_fire = run && command_valid && command_ready;
        assign command_record = command_bits;

        always @* begin
            response_record = i_array_runtime_response_record;

            if (q.endpoint != EP_ARRAY)
                response_record = i_service_response_record[q.endpoint*KW+:KW];
        end

        assign response_match = run && q.active && (q.sent || command_fire) &&
            (q.endpoint == EP_ARRAY ? i_array_runtime_response_valid :
                i_service_response_valid[q.endpoint]) &&
            response_record.tag == q.action.tag && response_record.command == q.action.command &&
            response_record.identity == q.action.identity;
        assign o_action_active = q.active;
        assign o_action_sent = q.sent;
        assign o_action_timed_out = q.timed_out;
        assign o_action_record = q.action;
        assign o_action_endpoint = q.endpoint;
        assign o_action_timer = q.timer;
        assign o_dma_reserved_mask = dma_used;
        assign o_memory_reserved_mask = memory_used;
        assign o_scratchpad_reserved_mask = scratchpad_used;
        assign o_event_reserved_mask = events_used;
        assign o_counter_reserved_mask = counters_used;
        assign o_memory_bandwidth_reserved = memory_bandwidth_used;
        assign o_noc_bandwidth_reserved = noc_bandwidth_used;
        assign o_power_reserved = power_used;
        assign o_scheduler_eligible = eligible;
        assign o_scheduler_grant_valid = grant_valid;
        assign o_scheduler_grant_index = 4'(grant_index);
        assign o_cluster_reserved_mask = clusters_used[NUM_CLUSTERS-1:0];
        assign o_cluster_fault_mask = q.fault_mask[NUM_CLUSTERS-1:0];
        assign o_pending_count = 8'(pending_count);
        assign o_active_count = 8'(active_count);
        assign o_time = time_value;
        assign o_integrity_error = integrity_bad;
        assign o_error_code = q.first_error;
        assign o_diagnostic_overflow = q.diagnostic_overflow;
        assign o_recovery_required = recovery || integrity_bad || q.halt;
        assign o_retention_save = 1'b0;
        assign o_retention_restore = 1'b0;
        assign o_isolation_enable = !i_power_good || !i_rstb;
        assign o_idle = !q.active && !grant_valid && worker < 0 && !submission_valid &&
            !event_valid;
        assign o_quiescent = q.reconciled && pending_count == 0 && !q.active &&
            !submission_valid && !admission_valid && !result_valid && !event_valid &&
            !snapshot_valid && !diagnostic_valid && !policy_reply_valid && !q.policy_active &&
            !recovery && !integrity_bad;
        assign o_clock_enable = !o_quiescent || i_submit_valid || i_event_valid ||
            i_policy_valid || i_snapshot_valid || i_reconcile_valid || i_test_mode || i_scan_enable;
        // Reconciliation is a SYSTEM-level clean proof, not a command to discard
        // remote ownership. New bases must invalidate all earlier reset epochs.
        assign o_reconcile_ready = run && pending_count == 0 && !q.active &&
            !submission_valid && !admission_valid && !result_valid && !event_valid &&
            !snapshot_valid && !q.policy_active && !policy_reply_valid;

        // Reservations are aggregated from valid protected records. No separate
        // bitmap can drift away from a kernel's identity or release state.
        always @* begin : reservation_view
            record_t record;
            descriptor_t desc;
            variant_t variant;
            int owner;
            int distance;
            int best_distance;
            free_requests = '0;
            clusters_used = '0;
            dma_used = '0;
            memory_used = '0;
            scratchpad_used = '0;
            events_used = '0;
            counters_used = '0;
            memory_bandwidth_used = 0;
            noc_bandwidth_used = 0;
            power_used = 0;
            active_count = 0;
            pending_count = 0;
            recovery = !q.reconciled || q.timed_out;

            for (int o = 0; o < MAX_OWNERS; o++) begin
                owner_power_used[o] = 0;
                owner_bandwidth_used[o] = 0;
            end

            for (int s = 0; s < N; s++) begin
                record = record_q[s];
                desc = descriptor_q[s];
                free_requests[s] = !record.valid;

                if (record.valid) begin
                    pending_count++;
                    recovery = recovery || record.uncertain;

                    if (record.reserved) begin
                        active_count++;
                        clusters_used = clusters_used | record.clusters;
                        dma_used = dma_used | desc.resources.dma_mask;
                        memory_used = memory_used | desc.resources.memory_mask;
                        scratchpad_used = scratchpad_used | desc.resources.scratchpad_mask;
                        events_used = events_used | desc.resources.event_mask;
                        counters_used = counters_used | desc.resources.counter_mask;
                        memory_bandwidth_used = memory_bandwidth_used +
                            64'(desc.resources.memory_bandwidth);
                        noc_bandwidth_used = noc_bandwidth_used + 64'(desc.resources.noc_bandwidth);
                        power_used = power_used + 64'(desc.resources.power);
                        owner = owner_index(record.identity.owner_id);

                        if (owner >= 0) begin
                            owner_power_used[owner] = owner_power_used[owner] +
                                64'(desc.resources.power);
                            owner_bandwidth_used[owner] = owner_bandwidth_used[owner] +
                                64'(desc.resources.memory_bandwidth);
                        end
                    end
                end
            end

            maximum_rank = -1;
            minimum_rank = NUM_PRIORITY_LEVELS;
            eligible = '0;
            ranked = '0;
            worker = -1;

            for (int s = 0; s < N; s++) begin
                record = record_q[s];
                desc = descriptor_q[s];
                selected_masks[s] = 0;
                selected_variants[s] = -1;
                ranks[s] = int'(desc.priority_value) + int'(64'(record.age) /
                    AGE_ESCALATION_CYCLES);

                if (ranks[s] >= NUM_PRIORITY_LEVELS) ranks[s] = NUM_PRIORITY_LEVELS - 1;

                best_distance = 256;
                owner = owner_index(record.identity.owner_id);

                if (record.valid && record.state == RT_WAIT_RESOURCES && !record.cancel &&
                    active_count < MAX_ACTIVE_KERNELS && owner >= 0 &&
                    (dma_used & desc.resources.dma_mask) == 0 &&
                    (memory_used & desc.resources.memory_mask) == 0 &&
                    (scratchpad_used & desc.resources.scratchpad_mask) == 0 &&
                    (events_used & desc.resources.event_mask) == 0 &&
                    (counters_used & desc.resources.counter_mask) == 0 &&
                    memory_bandwidth_used + 64'(desc.resources.memory_bandwidth) <=
                        MEMORY_BANDWIDTH_CAPACITY &&
                    noc_bandwidth_used + 64'(desc.resources.noc_bandwidth) <= NOC_BANDWIDTH_CAPACITY
                        &&
                    power_used + 64'(desc.resources.power) <= POWER_CAPACITY &&
                    (((q.bounds_valid >> owner) & 1'b1) == 0 ||
                        (desc.priority_value <= 8'(q.priority_bounds >> (owner * 8)) &&
                        owner_power_used[owner] + 64'(desc.resources.power) <=
                            64'(32'(q.power_bounds >> (owner * 32))) &&
                        owner_bandwidth_used[owner] + 64'(desc.resources.memory_bandwidth) <=
                            64'(32'(q.bandwidth_bounds >> (owner * 32)))))) begin
                    for (int v = 0; v < V; v++) begin
                        variant = get_variant(desc, v);
                        distance = int'(variant.cluster_count) - int'(desc.preferred_clusters);

                        if (distance < 0) distance = -distance;

                        if (v < desc.variant_count && variant_legal(desc, variant) &&
                            (variant.cluster_mask & clusters_used) == 0 &&
                            (variant.cluster_mask & q.fault_mask) == 0 &&
                            distance < best_distance) begin
                            selected_variants[s] = v;
                            selected_masks[s] = variant.cluster_mask;
                            best_distance = distance;
                        end
                    end

                    eligible[s] = selected_variants[s] >= 0;

                    if (eligible[s]) begin
                        if (ranks[s] > maximum_rank) maximum_rank = ranks[s];

                        if (ranks[s] < minimum_rank) minimum_rank = ranks[s];
                    end
                end

                if (worker < 0 && record.valid && (record.reserved || record.admitted) &&
                    record.phase != PH_EXECUTING && record.phase != PH_SLEEPING &&
                    record.phase != PH_CONTAINED &&
                    (record.phase != PH_DRAIN_SERVICES || record.cursor < 6 ||
                        !desc.lifecycle.flags[4] || (record.snapshot_valid &&
                        record.snapshot_timestamp >= record.completion_time)) &&
                    (record.phase != PH_WAIT_IO || (record.inputs_ready && record.output_space)) &&
                    (record.phase != PH_ADMISSION ||
                        (!record.admission_queued && admission_ready) || record.admission_delivered)
                            &&
                    (record.phase != PH_FINISH || (record.admitted && record.admission_delivered &&
                        result_ready && !record.result_queued &&
                        !(q.policy_active && q.policy_slot == 4'(s))))) worker = s;
            end

            for (int s = 0; s < N; s++)
                ranked[s] = eligible[s] && ranks[s] ==
                    (q.burst >= HIGH_PRIORITY_BURST_LIMIT ? minimum_rank : maximum_rank);
        end

        for (genvar s = 0; s < N; s++) begin : g_status
            record_t record;
            assign record = record_q[s];
            assign o_record_valid[s] = record.valid;
            assign o_record_reserved[s] = record.valid && record.reserved;
            assign o_record_array_owned[s] = record.valid && record.array_owned;
            assign o_record_service_owned[s*6+:6] = record.services_owned;
            assign o_record_allocated_cycles[s*64+:64] = record.allocated_cycles;
            assign o_scheduler_rank[s*8+:8] = 8'(ranks[s]);
            assign o_record_deadline_warned[s] = record.valid && record.deadline_warned;
            assign o_record_state[s*5+:5] = record.state;
            assign o_record_identity[s*152+:152] = record.identity;
            assign o_record_cluster_mask[s*16+:16] = record.clusters;
            assign o_record_age[s*AGE_COUNTER_WIDTH+:AGE_COUNTER_WIDTH] = record.age;
            assign o_record_run_cycles[s*64+:64] = record.run_cycles;
            assign o_record_snapshot_metrics[s*256+:256] = record.metrics;
        end

        always @* begin : descriptor_snapshot
            submission = '0;
            submission.variants = i_submit_variant_records;
            submission.resources = i_submit_resource_record;
            submission.qos = i_submit_qos_record;
            submission.power = i_submit_power_record;
            submission.lifecycle = i_submit_lifecycle_record;
            submission.identity.owner_id = i_submit_owner_id;
            submission.identity.kernel_id = i_submit_kernel_id;
            submission.identity.descriptor_id = i_submit_descriptor_id;
            submission.identity.descriptor_generation = i_submit_descriptor_generation;
            submission.deadline = i_submit_deadline;
            submission.estimated_cycles = i_submit_estimated_cycles;
            submission.capabilities = i_submit_required_capabilities;
            submission.tag = i_submit_tag;
            submission.version = i_submit_contract_version;
            submission.priority_value = i_submit_priority;
            submission.minimum_clusters = i_submit_required_clusters;
            submission.preferred_clusters = i_submit_preferred_clusters;
            submission.variant_count = i_submit_variant_count;
            submission.admission_class = i_submit_admission_class;
            submission.integrity = i_submit_integrity_valid;
        end

        // A single serialized action ledger avoids ambiguous rollback ordering.
        // Running kernels still execute concurrently. Offered commands are never
        // withdrawn on cancellation, and timeout never retires their tags.
        always @* begin : lifecycle
            record_t record;
            record_t other;
            descriptor_t desc;
            variant_t variant;
            policy_t policy;
            logic [7:0] error;
            logic [31:0] timeout_value;
            bit duplicate;
            bit issue;
            bit matched_event;
            bit cleanup_action;
            int owner;
            int slot;
            int endpoint;
            int event_source;
            int prior_state;
            d = q;

            for (int s = 0; s < N; s++) begin
                record_d[s] = record_q[s];
                descriptor_d[s] = descriptor_q[s];
            end

            action_push = 0;
            action_input = '0;
            admission_push = 0;
            admission_input = '0;
            result_push = 0;
            result_input = '0;
            diagnostic_push = 0;
            diagnostic_input = '0;
            policy_reply_push = 0;
            policy_reply_input = '0;
            submission_pop = 0;
            event_pop = 0;
            snapshot_pop = 0;
            grant_accept = 0;
            statistics = '0;
            record = '0;
            other = '0;
            desc = '0;
            variant = '0;
            policy = '0;
            error = ERR_NONE;
            timeout_value = 0;
            duplicate = 0;
            issue = 0;
            matched_event = 0;
            cleanup_action = 0;
            owner = -1;
            slot = -1;
            endpoint = EP_ARRAY;
            event_source = 0;
            prior_state = RT_FREE;

            if (clock_ok && (integrity_bad || time_overflow)) begin
                d.halt = 1;

                if (q.first_error == ERR_NONE)
                    d.first_error = integrity_bad ? ERR_INTEGRITY : ERR_EXHAUSTED;
            end

            if (run) begin
                statistics[15] = control_corrected || (|record_corrected) ||
                    (|descriptor_corrected);
                // A clean system proof is required after reset. Nonzero remote
                // ownership is explicitly refused and cannot be silently cleared.
                if (i_reconcile_valid && o_reconcile_ready) begin
                    if (i_reconcile_clean && i_reconcile_cluster_busy_mask == 0 &&
                        i_reconcile_service_busy == 0 &&
                        i_reconcile_manifest == 64'h4d52540100000001 &&
                        i_reconcile_tag_base != 16'hffff &&
                        i_reconcile_allocation_base != 16'hffff &&
                        i_reconcile_epoch_base != 8'hff &&
                        (!q.reconciled || (i_reconcile_tag_base >= q.next_tag &&
                            i_reconcile_allocation_base >= q.next_allocation &&
                            i_reconcile_epoch_base >= q.next_epoch))) begin
                        d.reconciled = 1;
                        d.enabled = 1;
                        d.next_tag = i_reconcile_tag_base;
                        d.next_allocation = i_reconcile_allocation_base;
                        d.next_epoch = i_reconcile_epoch_base;
                        d.first_error = ERR_NONE;
                    end else if (q.first_error == ERR_NONE) d.first_error = ERR_IDENTITY;
                end

                for (int s = 0; s < N; s++) begin
                    record = record_d[s];
                    prior_state = int'(record.state);
                    desc = descriptor_q[s];

                    if (record.valid) begin
                        if (record.state == RT_WAIT_RESOURCES && !(&record.age))
                            record.age = record.age + 1'b1;

                        if (record.reserved && !(&record.allocated_cycles))
                            record.allocated_cycles = record.allocated_cycles + 1'b1;

                        if (record.state == RT_RUNNING && !(&record.run_cycles))
                            record.run_cycles = record.run_cycles + 1'b1;

                        if (ENABLE_DEADLINE_MONITORING && desc.deadline != 0 &&
                            (time_value >= desc.deadline ||
                            (record.run_cycles < 64'(desc.estimated_cycles) &&
                            65'(time_value) + 65'(desc.estimated_cycles) -
                                65'(record.run_cycles) > 65'(desc.deadline))) &&
                                    !record.deadline_warned) begin
                            record.deadline_warned = 1;
                            statistics[12] = 1;
                            diagnostic_input.identity = record.identity;
                            diagnostic_input.event_type = EV_COUNTERS_CHANGED;
                            diagnostic_input.error = ERR_DEADLINE;
                            diagnostic_input.timestamp = time_value;

                            if (!diagnostic_ready || diagnostic_push) d.diagnostic_overflow = 1;

                            diagnostic_push = diagnostic_ready;
                        end

                        if (record.state == RT_VALIDATING) begin
                            record.error = descriptor_error(desc);

                            if (!ENABLE_FAULT_AWARE_ALLOCATION && q.fault_mask != 0)
                                record.error = ERR_FAULTED;

                            duplicate = 0;

                            for (int t = 0; t < N; t++) begin
                                other = record_q[t];

                                // The older slot already passed validation, or
                                // wins a same-edge tie by its stable slot index.
                                if (t != s && other.valid &&
                                    (other.state != RT_SUBMITTED &&
                                    (other.state != RT_VALIDATING || t < s)) &&
                                    other.identity.owner_id == record.identity.owner_id &&
                                    other.identity.kernel_id == record.identity.kernel_id)
                                    duplicate = 1;
                            end

                            if (duplicate) record.error = ERR_DUPLICATE;

                            record.state = record.error == ERR_NONE ? RT_WAIT_RESOURCES :
                                RT_RELEASING;
                            record.phase = record.error == ERR_NONE ? PH_ARRAY_ALLOCATE : PH_FINISH;
                            record.terminal_status = NOTICE_REJECTED;
                        end

                        if (record.state == RT_RUNNING) begin
                            timeout_value = desc.lifecycle.kernel_timeout != 0 ?
                                desc.lifecycle.kernel_timeout : 32'(KERNEL_TIMEOUT_CYCLES);

                            if (timeout_value != 0 && record.run_cycles >= 64'(timeout_value)) begin
                                record.cancel = 1;
                                record.state = RT_ERROR;
                                record.error = ERR_TIMEOUT;
                                record.terminal_status = NOTICE_FAILED;
                            end

                            if (!record.cancel && record.compute_done &&
                                (!desc.lifecycle.flags[3] || record.external_done)) begin
                                record.state = RT_DRAINING;
                                record.phase = PH_ARRAY_DRAIN;
                                record.terminal_status = NOTICE_SUCCEEDED;
                            end
                        end

                        if (record.cancel && !(q.active && q.slot == 4'(s)) &&
                            !(record.state == RT_ERROR && prior_state != RT_ERROR) &&
                            record.phase != PH_CONTAINED && record.phase != PH_FINISH &&
                            record.state != RT_TERMINATING && record.state != RT_RELEASING) begin

                            if (!record.reserved) begin
                                record.state = RT_RELEASING;
                                record.phase = PH_FINISH;
                                record.terminal_status = NOTICE_CANCELED;
                            end else begin
                                record = begin_cleanup(record);

                                if (prior_state == RT_RESERVING || prior_state == RT_ALLOCATING ||
                                    prior_state == RT_CONFIGURING || prior_state == RT_STARTING ||
                                    prior_state == RT_SUSPEND_PENDING) record.state = RT_ERROR;
                            end
                        end

                        // Rejected descriptors have their own bounded response
                        // queue and remain immutable until that response transfers.
                        if (record.phase == PH_FINISH && !record.admitted &&
                            !record.admission_queued && admission_ready && !admission_push) begin
                            admission_input = notice(record, desc, record.terminal_status, s);
                            admission_push = 1;
                            record.admission_queued = 1;
                        end

                        if (record.phase == PH_FINISH && record.admission_delivered &&
                            !record.admitted && !(q.policy_active && q.policy_slot == 4'(s)))
                            record.valid = 0;
                        record_d[s] = record;
                    end
                end

                if (i_submit_valid && o_submit_ready) begin
                    record = '0;
                    record.valid = 1;
                    record.state = RT_SUBMITTED;
                    record.identity = submission.identity;
                    record.inputs_ready = submission.lifecycle.flags[1];
                    record.output_space = submission.lifecycle.flags[2];
                    record.terminal_status = NOTICE_FAILED;
                    record_d[free_index] = record;
                    descriptor_d[free_index] = submission;
                    statistics[0] = 1;
                end

                if (submission_valid) begin
                    submission_pop = 1;
                    record = record_d[submission_slot];
                    record.state = RT_VALIDATING;
                    record_d[submission_slot] = record;
                end

                if (admission_valid && i_admission_ready) begin
                    record = record_d[admission_output.slot];
                    record.admission_delivered = 1;
                    record_d[admission_output.slot] = record;
                    statistics[1] = admission_output.status == NOTICE_ADMITTED;
                    statistics[2] = admission_output.status != NOTICE_ADMITTED;
                end

                if (result_valid && i_result_ready) begin
                    record = record_d[result_output.slot];
                    record.valid = 0;
                    record_d[result_output.slot] = record;
                    statistics[3] = result_output.status == NOTICE_SUCCEEDED;
                    statistics[4] = result_output.status != NOTICE_SUCCEEDED;
                end

                // All response channels drain independently. Wrong tags or full
                // identities are quarantined; they never mutate kernel ownership.
                statistics[5] = command_fire;
                statistics[6] = response_match;
                statistics[7] = (i_array_runtime_response_valid ||
                    (|i_service_response_valid)) && !response_match;

                if (command_fire) begin
                    d.sent = 1;
                    d.timer = 0;
                end

                if (q.active && q.sent && !q.timed_out && !response_match) begin
                    record = record_d[q.slot];
                    desc = descriptor_q[q.slot];
                    timeout_value = desc.lifecycle.action_timeout != 0 ?
                        desc.lifecycle.action_timeout : 32'(ACTION_TIMEOUT_CYCLES);
                    d.timer = q.timer + 1'b1;

                    if (d.timer >= timeout_value) begin
                        d.timed_out = 1;
                        record.uncertain = 1;
                        record.error = ERR_TIMEOUT;
                        record.state = RT_ERROR;
                        record.terminal_status = NOTICE_FAILED;
                        statistics[14] = 1;
                        record_d[q.slot] = record;
                    end
                end

                if (response_match) begin
                    record = record_d[q.slot];
                    desc = descriptor_q[q.slot];
                    d.active = 0;
                    d.sent = 0;
                    d.timed_out = 0;
                    d.timer = 0;
                    cleanup_action = record.phase == PH_ARRAY_DRAIN ||
                        record.phase == PH_DRAIN_SERVICES || record.phase == PH_RELEASE_SERVICES ||
                        record.phase == PH_ARRAY_RELEASE || record.phase == PH_POWER_IDLE;

                    if ((response_record.status !== ACK_OK && response_record.status !==
                        ACK_NO_EFFECT) ||
                        (response_record.status == ACK_OK &&
                        (response_record.cluster_mask != q.action.cluster_mask ||
                        response_record.error != 0)) ||
                        response_record.status > ACK_UNCERTAIN) begin

                        // Potential partial effects are retained as owned until
                        // an explicitly authorized destructive recovery drains them.
                        if (q.endpoint == EP_ARRAY) record.array_owned = 1;
                        else record.services_owned = record.services_owned | (6'b1 << q.endpoint);

                        record.uncertain = 1;
                        record.error = ERR_PARTIAL;
                        record.state = RT_ERROR;
                        record.phase = PH_CONTAINED;
                        record.terminal_status = NOTICE_FAILED;
                    end else if (response_record.status == ACK_NO_EFFECT && cleanup_action) begin
                        record.uncertain = 1;
                        record.error = ERR_BACKEND;
                        record.terminal_status = NOTICE_FAILED;
                        record.state = RT_ERROR;
                        record.phase = PH_CONTAINED;
                    end else begin
                        if (response_record.status == ACK_OK) begin
                            case (record.phase)
                                PH_ARRAY_ALLOCATE: begin
                                    record.array_owned = 1;
                                    record.state = RT_CONFIGURING;
                                    record.phase = PH_RESERVE_SERVICES;
                                    record.cursor = 0;
                                end
                                PH_RESERVE_SERVICES: begin
                                    record.services_owned = record.services_owned | (6'b1 <<
                                        q.endpoint);
                                    record.cursor = record.cursor + 1'b1;
                                end
                                PH_POWER_WAKE: begin
                                    if (response_record.flags[1]) record.phase = PH_CONFIG_LOAD;
                                    else begin
                                        record.uncertain = 1;
                                        record.error = ERR_PARTIAL;
                                        record.terminal_status = NOTICE_FAILED;
                                    end
                                end
                                PH_CONFIG_LOAD: record.phase = PH_CONFIG_VALIDATE;
                                PH_CONFIG_VALIDATE: record.phase = PH_CONFIG_PREPARE;
                                PH_CONFIG_PREPARE: record.phase = PH_ARRAY_COMMIT;
                                PH_ARRAY_COMMIT: begin
                                    if (q.next_epoch == 8'hff) begin
                                        d.halt = 1;
                                        d.first_error = ERR_EXHAUSTED;
                                    end else begin
                                        d.next_epoch = q.next_epoch + 1'b1;
                                        record.identity.epoch = d.next_epoch;
                                        record.event_next = '0;
                                        record.event_exhausted = '0;
                                        record.snapshot_valid = 0;
                                    end
                                    record.phase = PH_ACTIVATE_SERVICES;
                                    record.cursor = 0;
                                end
                                PH_ACTIVATE_SERVICES: record.cursor = record.cursor + 1'b1;
                                PH_ARRAY_START, PH_ARRAY_RESUME: begin
                                    record.state = RT_RUNNING;
                                    record.phase = PH_EXECUTING;
                                    record.started = 1;
                                end
                                PH_ARRAY_SUSPEND: begin
                                    if (response_record.flags[1:0] == 2'b11) begin
                                        record.phase = PH_PRESERVE_SERVICES;
                                        record.cursor = 0;
                                    end else begin
                                        record.state = RT_ERROR;
                                        record.phase = PH_CONTAINED;
                                        record.uncertain = 1;
                                        record.error = ERR_PARTIAL;
                                    end
                                end
                                PH_PRESERVE_SERVICES: begin
                                    if (response_record.flags[0])
                                        record.cursor = record.cursor + 1'b1;
                                    else begin
                                        record.uncertain = 1;
                                        record.error = ERR_PARTIAL;
                                        record.terminal_status = NOTICE_FAILED;
                                    end
                                end
                                PH_RESUME_SERVICES: begin
                                    if (response_record.flags[0])
                                        record.cursor = record.cursor + 1'b1;
                                    else begin
                                        record.uncertain = 1;
                                        record.error = ERR_PARTIAL;
                                        record.terminal_status = NOTICE_FAILED;
                                    end
                                end
                                PH_ARRAY_DRAIN: begin
                                    record.phase = PH_DRAIN_SERVICES;
                                    record.cursor = 0;
                                    record.started = 0;
                                    if (record.terminal_status != NOTICE_SUCCEEDED)
                                        record.state = RT_TERMINATING;
                                end
                                PH_DRAIN_SERVICES: record.cursor = record.cursor + 1'b1;
                                PH_RELEASE_SERVICES: begin
                                    record.services_owned = record.services_owned & ~(6'b1 <<
                                        q.endpoint);
                                    record.cursor = record.cursor - 1'b1;
                                end
                                PH_ARRAY_RELEASE: begin
                                    record.array_owned = 0;
                                    record.phase = ENABLE_POWER_POLICY ? PH_POWER_IDLE : PH_FINISH;
                                end
                                PH_POWER_IDLE: record.phase = PH_FINISH;
                                default: begin end
                            endcase
                        end else begin
                            record.error = response_record.error != 0 ?
                                response_record.error : ERR_BACKEND;
                            record.terminal_status = NOTICE_FAILED;
                            record.cancel = 1;
                            record = begin_cleanup(record);
                            record.state = RT_ERROR;
                        end

                        if (q.timed_out) begin
                            record.uncertain = 0;
                            record.error = ERR_TIMEOUT;
                            record.terminal_status = NOTICE_FAILED;
                            record.cancel = 1;
                            // A late successful release has already removed the
                            // effect. A late start must be aborted, never replayed.
                            record = begin_cleanup(record);
                        end
                    end

                    if (record.uncertain) begin
                        record.state = RT_ERROR;
                        record.phase = PH_CONTAINED;
                    end

                    record_d[q.slot] = record;
                end

                // Critical events have an ingress FIFO separate from optional
                // diagnostic output. A stopped diagnostic sink cannot stall drain.
                if (event_valid) begin
                    event_pop = 1;
                    matched_event = 0;
                    event_source = int'(incoming_event.source);

                    for (int s = 0; s < N; s++) begin
                        record = record_d[s];

                        if (record.valid && record.reserved &&
                            record.identity == incoming_event.identity && event_source < SOURCES &&
                            (incoming_event.cluster_mask & ~record.clusters) == 0 &&
                            (event_source == NUM_CLUSTERS || ((record.clusters >> event_source) &
                                16'b1) != 0)) begin
                            matched_event = 1;

                            if (((record.event_exhausted >> event_source) & 1'b1) != 0 ||
                                incoming_event.sequence_id >
                                    16'(record.event_next >> (event_source * 16))) begin
                                record.error = ERR_SEQUENCE;
                                record.terminal_status = NOTICE_FAILED;
                                record.uncertain = 1;
                                record.cancel = 1;
                                record.state = RT_ERROR;

                                if (!(q.active && q.slot == 4'(s))) record.phase = PH_CONTAINED;

                                statistics[11] = 1;
                            end else if (incoming_event.sequence_id <
                                16'(record.event_next >> (event_source * 16))) statistics[10] = 1;
                            else begin
                                record.event_next = (record.event_next &
                                    ~({SOURCES*16{1'b1}} >> ((SOURCES - 1) * 16) <<
                                        (event_source * 16))) |
                                    ((SOURCES*16)'(incoming_event.sequence_id + 16'b1) <<
                                        (event_source * 16));

                                if (incoming_event.sequence_id == 16'hffff)
                                    record.event_exhausted = record.event_exhausted |
                                        (SOURCES'(1) << event_source);

                                statistics[8] = 1;

                                case (incoming_event.event_type)
                                    EV_COMPUTE_DONE: begin
                                        if (event_source == NUM_CLUSTERS &&
                                            incoming_event.cluster_mask == record.clusters &&
                                            (record.started || record.state == RT_STARTING))
                                            begin
                                                record.compute_done = 1;
                                                record.completion_time = time_value;
                                            end
                                    end
                                    EV_EXTERNAL_DONE: begin
                                        if (event_source == NUM_CLUSTERS)
                                            record.external_done = 1;
                                    end
                                    EV_INPUT_READY: record.inputs_ready = 1;
                                    EV_OUTPUT_SPACE: record.output_space = 1;
                                    EV_FAULT: begin
                                        d.fault_mask = d.fault_mask | incoming_event.cluster_mask;
                                        record.cancel = 1;
                                        record.state = RT_ERROR;
                                        record.error = ERR_FAULTED;
                                        record.terminal_status = NOTICE_FAILED;
                                    end
                                    default: begin end
                                endcase
                            end

                            record_d[s] = record;
                        end
                    end

                    if (!matched_event) statistics[9] = 1;
                end

                if (snapshot_valid) begin
                    snapshot_pop = 1;

                    for (int s = 0; s < N; s++) begin
                        record = record_d[s];

                        if (ENABLE_COUNTER_FEEDBACK && record.valid && record.reserved &&
                            incoming_snapshot.identity == record.identity &&
                            incoming_snapshot.validity == 16'h000f &&
                            incoming_snapshot.timestamp <= time_value &&
                            (!record.snapshot_valid ||
                                (incoming_snapshot.generation > record.snapshot_generation &&
                                incoming_snapshot.timestamp > record.snapshot_timestamp)) &&
                            (!record.snapshot_valid || incoming_snapshot.critical ||
                                time_value - record.sample_time >= POLICY_SAMPLE_INTERVAL)) begin
                            record.snapshot_valid = 1;
                            record.snapshot_generation = incoming_snapshot.generation;
                            record.snapshot_timestamp = incoming_snapshot.timestamp;
                            record.sample_time = time_value;
                            record.metrics = incoming_snapshot.metrics;
                            statistics[13] = 1;
                            record_d[s] = record;
                        end
                    end
                end

                if (i_policy_valid && o_policy_ready) begin
                    policy = i_policy_record;
                    owner = owner_index(policy.identity.owner_id);
                    slot = -1;

                    for (int s = 0; s < N; s++) begin
                        record = record_d[s];

                        if (record.valid && record.identity == policy.identity) slot = s;
                    end

                    policy_reply_input = '0;
                    policy_reply_input.identity = policy.identity;
                    policy_reply_input.tag = policy.tag;
                    policy_reply_push = 1;
                    error = ERR_NONE;

                    if (!policy.authorized) error = ERR_AUTHORIZATION;
                    else if (policy.command == POL_ENABLE || policy.command == POL_DISABLE) begin
                        if (policy.identity.owner_id != 0) error = ERR_AUTHORIZATION;
                        else d.enabled = policy.command == POL_ENABLE;
                    end else if (policy.command == POL_UPDATE_BOUNDS) begin
                        if (owner < 0) error = ERR_OWNER;
                        else if (policy.priority_limit >= NUM_PRIORITY_LEVELS ||
                            policy.power_budget > POWER_CAPACITY ||
                            policy.bandwidth_budget > MEMORY_BANDWIDTH_CAPACITY ||
                            owner_power_used[owner] > 64'(policy.power_budget) ||
                            owner_bandwidth_used[owner] > 64'(policy.bandwidth_budget))
                            error = ERR_BUDGET;
                        else begin
                            // Existing guaranteed priorities cannot be revoked.
                            for (int s = 0; s < N; s++) begin
                                record = record_d[s];
                                desc = descriptor_q[s];

                                if (record.valid && record.reserved && desc.admission_class &&
                                    record.identity.owner_id == policy.identity.owner_id &&
                                    desc.priority_value > policy.priority_limit) error = ERR_BUDGET;
                            end

                            if (error == ERR_NONE) begin
                                d.bounds_valid = d.bounds_valid | (MAX_OWNERS'(1) << owner);
                                d.priority_bounds = (d.priority_bounds &
                                    ~((MAX_OWNERS*8)'(8'hff) << (owner * 8))) |
                                    ((MAX_OWNERS*8)'(policy.priority_limit) << (owner * 8));
                                d.power_bounds = (d.power_bounds &
                                    ~((MAX_OWNERS*32)'(32'hffffffff) << (owner * 32))) |
                                    ((MAX_OWNERS*32)'(policy.power_budget) << (owner * 32));
                                d.bandwidth_bounds = (d.bandwidth_bounds &
                                    ~((MAX_OWNERS*32)'(32'hffffffff) << (owner * 32))) |
                                    ((MAX_OWNERS*32)'(policy.bandwidth_budget) << (owner * 32));
                            end
                        end
                    end else if (slot < 0) error = ERR_IDENTITY;
                    else begin
                        record = record_d[slot];
                        desc = descriptor_q[slot];
                        policy_reply_input.identity = record.identity;
                        policy_reply_input.state = record.state;

                        case (policy.command)
                            POL_QUERY: begin end
                            POL_REQUEST_SUSPEND: begin
                                if (!ENABLE_SAFE_SUSPEND || !desc.lifecycle.flags[0])
                                    error = ERR_UNSUPPORTED;
                                else if (record.state != RT_RUNNING ||
                                    (q.active && q.slot == 4'(slot))) error = ERR_BUSY;
                                else begin
                                    record.state = RT_SUSPEND_PENDING;
                                    record.phase = PH_ARRAY_SUSPEND;
                                    d.policy_active = 1;
                                end
                            end
                            POL_REQUEST_RESUME: begin
                                if (record.state != RT_SUSPENDED) error = ERR_BUSY;
                                else if (policy.resume_cookie != desc.lifecycle.resume_cookie ||
                                    (record.clusters & q.fault_mask) != 0) error = ERR_IDENTITY;
                                else if (d.next_epoch == 8'hff) error = ERR_EXHAUSTED;
                                else begin
                                    d.next_epoch = d.next_epoch + 1'b1;
                                    record.identity.epoch = d.next_epoch;
                                    record.event_next = '0;
                                    record.event_exhausted = '0;
                                    record.compute_done = 0;
                                    record.external_done = 0;
                                    record.snapshot_valid = 0;
                                    record.phase = PH_RESUME_SERVICES;
                                    record.cursor = 0;
                                    record.state = RT_STARTING;
                                    d.policy_active = 1;
                                end
                            end
                            POL_CANCEL, POL_FORCE_ABORT: begin
                                if (record.phase == PH_FINISH || record.result_queued)
                                    error = ERR_BUSY;
                                else if ((record.started || record.state == RT_STARTING ||
                                    record.uncertain) &&
                                    (!policy.destructive || !desc.lifecycle.flags[7]))
                                    error = ERR_UNSUPPORTED;
                                else begin
                                    record.cancel = 1;
                                    if (record.error == ERR_NONE)
                                        record.terminal_status = NOTICE_CANCELED;
                                    if (record.uncertain && !q.active) begin
                                        record.uncertain = 0;
                                        // Uncertain backends must explicitly drain
                                        // and release, even if START was not seen.
                                        record.started = 1;
                                        record = begin_cleanup(record);
                                    end
                                    d.policy_active = 1;
                                end
                            end
                            default: error = ERR_UNSUPPORTED;
                        endcase

                        record_d[slot] = record;

                        if (d.policy_active) begin
                            d.policy_slot = 4'(slot);
                            d.policy = policy;
                            policy_reply_push = 0;
                        end
                    end

                    policy_reply_input.error = error;
                    policy_reply_input.status = error == ERR_NONE ? ACK_OK : ACK_NO_EFFECT;
                end

                if (q.policy_active && policy_reply_ready) begin
                    record = record_d[q.policy_slot];

                    if (record.phase == PH_FINISH || record.phase == PH_CONTAINED ||
                        (q.policy.command == POL_REQUEST_SUSPEND && record.state == RT_SUSPENDED) ||
                        (q.policy.command == POL_REQUEST_RESUME && record.state == RT_RUNNING))
                            begin
                        policy_reply_input = '0;
                        policy_reply_input.identity = record.identity;
                        policy_reply_input.tag = q.policy.tag;
                        policy_reply_input.state = record.state;
                        policy_reply_input.error = record.error;
                        policy_reply_input.status = record.phase == PH_CONTAINED ?
                            ACK_UNCERTAIN : ACK_OK;
                        policy_reply_push = 1;
                        d.policy_active = 0;
                    end
                end

                if (!q.active && worker >= 0 && action_ready) begin
                    slot = worker;
                    record = record_d[slot];
                    desc = descriptor_q[slot];
                    variant = get_variant(desc, int'(record.variant_index));
                    action_input = '0;
                    action_input.cluster_mask = record.clusters;
                    endpoint = EP_ARRAY;
                    issue = 0;
                    cleanup_action = record.phase == PH_ARRAY_DRAIN ||
                        record.phase == PH_DRAIN_SERVICES || record.phase == PH_RELEASE_SERVICES ||
                        record.phase == PH_ARRAY_RELEASE || record.phase == PH_POWER_IDLE ||
                        record.phase == PH_FINISH;

                    if (!record.uncertain && !record.result_queued &&
                        (!record.cancel || cleanup_action)) begin
                        case (record.phase)
                            PH_ARRAY_ALLOCATE: begin
                                issue = 1;
                                action_input.command = CMD_ALLOCATE;
                                record.state = RT_ALLOCATING;
                            end
                            PH_RESERVE_SERVICES: begin
                                if (record.cursor >= 6) record.phase = PH_ADMISSION;
                                else if (((desc.resources.services >> record.cursor) & 6'b1) != 0)
                                    begin
                                    issue = 1;
                                    endpoint = int'(record.cursor);
                                    action_input.command = CMD_RESERVE;
                                end else record.cursor = record.cursor + 1'b1;
                            end
                            PH_ADMISSION: begin
                                if (!record.admission_queued && admission_ready && !admission_push)
                                    begin
                                    record.admitted = 1;
                                    record.error = ERR_NONE;
                                    admission_input = notice(record, desc, NOTICE_ADMITTED, slot);
                                    admission_push = 1;
                                    record.admission_queued = 1;
                                end else if (record.admission_delivered) begin
                                    record.phase = ENABLE_POWER_POLICY ? PH_POWER_WAKE :
                                        PH_CONFIG_LOAD;
                                end
                            end
                            PH_POWER_WAKE: begin
                                issue = 1;
                                endpoint = EP_POWER;
                                action_input.command = CMD_WAKE;
                            end
                            PH_CONFIG_LOAD, PH_CONFIG_VALIDATE, PH_CONFIG_PREPARE: begin
                                issue = 1;
                                endpoint = EP_CONFIG;
                                case (record.phase)
                                    PH_CONFIG_LOAD: action_input.command = CMD_LOAD;
                                    PH_CONFIG_VALIDATE: action_input.command = CMD_VALIDATE;
                                    default: action_input.command = CMD_PREPARE;
                                endcase
                            end
                            PH_ARRAY_COMMIT: begin
                                issue = 1;
                                action_input.command = CMD_COMMIT;
                            end
                            PH_ACTIVATE_SERVICES, PH_PRESERVE_SERVICES, PH_RESUME_SERVICES,
                            PH_DRAIN_SERVICES: begin
                                if (record.cursor >= 6) begin
                                    case (record.phase)
                                        PH_ACTIVATE_SERVICES: begin
                                            record.state = RT_READY;
                                            record.phase = PH_WAIT_IO;
                                        end
                                        PH_PRESERVE_SERVICES: begin
                                            record.state = RT_SUSPENDED;
                                            record.phase = PH_SLEEPING;
                                        end
                                        PH_RESUME_SERVICES: record.phase = PH_ARRAY_RESUME;
                                        default: begin
                                            if (!desc.lifecycle.flags[4] ||
                                                (record.snapshot_valid && record.snapshot_timestamp
                                                    >=
                                                    record.completion_time)) begin
                                                record.state = record.terminal_status ==
                                                    NOTICE_SUCCEEDED ? RT_COMPLETED : RT_RELEASING;
                                                record.phase = PH_RELEASE_SERVICES;
                                                record.cursor = 5;
                                            end
                                        end
                                    endcase
                                end else if (((record.services_owned >> record.cursor) & 6'b1) != 0)
                                    begin
                                    issue = 1;
                                    endpoint = int'(record.cursor);

                                    case (record.phase)
                                        PH_ACTIVATE_SERVICES: action_input.command = CMD_ACTIVATE;
                                        PH_PRESERVE_SERVICES: begin
                                            action_input.command = CMD_DRAIN;
                                            action_input.flags[0] = 1;
                                        end
                                        PH_RESUME_SERVICES: action_input.command = CMD_RESUME;
                                        default: action_input.command = CMD_DRAIN;
                                    endcase
                                end else record.cursor = record.cursor + 1'b1;
                            end
                            PH_WAIT_IO: begin
                                if (record.inputs_ready && record.output_space) begin
                                    record.state = RT_STARTING;
                                    record.phase = PH_ARRAY_START;
                                end
                            end
                            PH_ARRAY_START, PH_ARRAY_RESUME: begin
                                issue = 1;
                                action_input.command = record.phase == PH_ARRAY_START ?
                                    CMD_START : CMD_RESUME;
                            end
                            PH_ARRAY_SUSPEND: begin
                                issue = 1;
                                action_input.command = CMD_SUSPEND;
                            end
                            PH_ARRAY_DRAIN: begin
                                if (record.array_owned) begin
                                    issue = 1;
                                    action_input.command = record.terminal_status ==
                                        NOTICE_SUCCEEDED ?
                                        CMD_DRAIN : CMD_ABORT;
                                end else begin
                                    record.phase = PH_DRAIN_SERVICES;
                                    record.cursor = 0;
                                end
                            end
                            PH_RELEASE_SERVICES: begin
                                record.state = RT_RELEASING;
                                if (record.cursor >= 6) record.phase = PH_ARRAY_RELEASE;
                                else if (((record.services_owned >> record.cursor) & 6'b1) != 0)
                                    begin
                                    issue = 1;
                                    endpoint = int'(record.cursor);
                                    action_input.command = CMD_RELEASE;
                                end else record.cursor = record.cursor - 1'b1;
                            end
                            PH_ARRAY_RELEASE: begin
                                if (record.array_owned) begin
                                    issue = 1;
                                    action_input.command = CMD_RELEASE;
                                end else record.phase = PH_FINISH;
                            end
                            PH_POWER_IDLE: begin
                                issue = 1;
                                endpoint = EP_POWER;
                                action_input.command = CMD_IDLE;
                            end
                            PH_FINISH: begin
                                record.reserved = 0;
                                record.state = RT_RELEASING;
                                if (record.admitted && record.admission_delivered && result_ready &&
                                    !(q.policy_active && q.policy_slot == 4'(slot))) begin
                                    result_input = notice(record, desc, record.terminal_status,
                                        slot);
                                    result_push = 1;
                                    record.result_queued = 1;
                                end
                            end
                            default: begin end
                        endcase
                    end

                    if (issue) begin
                        if (q.next_tag == 16'hffff) begin
                            d.halt = 1;
                            d.first_error = ERR_EXHAUSTED;
                        end else begin
                            action_input.resources = desc.resources;
                            action_input.qos = desc.qos;
                            action_input.power = desc.power;
                            action_input.lifecycle = desc.lifecycle;
                            action_input.flags[15:8] = desc.lifecycle.safe_point_id;
                            action_input.identity = record.identity;
                            action_input.tag = q.next_tag + 1'b1;
                            action_input.resource_mask = resource_mask(desc.resources, endpoint);

                            case (endpoint)
                                EP_NOC: action_input.profile = 8'(variant.noc_profile);
                                EP_MEMORY: action_input.profile = 8'(variant.memory_profile);
                                EP_POWER: action_input.profile = 8'(variant.power_profile);
                                default: action_input.profile = 0;
                            endcase

                            action_input.flags[1] = desc.admission_class;
                            action_input.flags[2] = record.terminal_status != NOTICE_SUCCEEDED;
                            action_input.flags[3] = desc.lifecycle.flags[4];
                            action_push = 1;
                            d.active = 1;
                            d.sent = 0;
                            d.timed_out = 0;
                            d.timer = 0;
                            d.action = action_input;
                            d.slot = 4'(slot);
                            d.endpoint = 3'(endpoint);
                            d.next_tag = action_input.tag;
                        end
                    end
                    record_d[slot] = record;
                end else if (!q.active && worker < 0 && grant_valid && q.enabled &&
                    q.reconciled && !recovery) begin
                    slot = int'(grant_index);
                    record = record_d[slot];
                    desc = descriptor_q[slot];
                    variant = get_variant(desc, selected_variants[slot]);

                    if (q.next_allocation == 16'hffff) begin
                        d.halt = 1;
                        d.first_error = ERR_EXHAUSTED;
                    end else if (record.state == RT_WAIT_RESOURCES && !record.cancel) begin
                        record.reserved = 1;
                        record.state = RT_RESERVING;
                        record.phase = PH_ARRAY_ALLOCATE;
                        record.clusters = selected_masks[slot];
                        record.variant_index = 3'(selected_variants[slot]);
                        record.identity.package_id = variant.package_id;
                        record.identity.mapping_id = variant.mapping_id;
                        record.identity.allocation_generation = q.next_allocation + 1'b1;
                        d.next_allocation = record.identity.allocation_generation;
                        grant_accept = 1;
                        d.burst = ranks[slot] == minimum_rank ? 0 : q.burst + 1'b1;
                        record_d[slot] = record;
                    end
                end

                for (int s = 0; s < N; s++) begin
                    record = record_d[s];

                    if (record.phase == PH_FINISH) record.reserved = 0;

                    if (record.error != ERR_NONE && d.first_error == ERR_NONE)
                        d.first_error = record.error;

                    record_d[s] = record;
                end
            end
        end
    end
endmodule
`default_nettype wire
