`timescale 1ns / 1ps
`default_nettype none

// Always-on clocked-cluster sequencer. Technology-specific advanced states are guarded off.
module cluster_power_manager #(
    parameter POWER_PROFILE = 0,
    parameter CLUSTER_ID = 0,
    parameter NUM_TILES = 16,
    parameter NUM_CLOCK_GROUPS = 8,
    parameter NUM_WAKE_SOURCES = 16,
    parameter NUM_STALL_REASONS = 8,
    parameter NUM_ISOLATION_GROUPS = 4,
    parameter NUM_RETENTION_GROUPS = 4,
    parameter NUM_POWER_SWITCH_GROUPS = 1,
    parameter NUM_RESET_GROUPS = 4,
    parameter NUM_OPERATING_POINTS = 1,
    parameter NUM_SRAM_POWER_GROUPS = 1,
    parameter NUM_BOUNDARY_ENDPOINTS = 4,
    parameter IDLE_ENTRY_CYCLES = 32,
    parameter MIN_GATED_RESIDENCY_CYCLES = 8,
    parameter MIN_RETENTION_RESIDENCY_CYCLES = 1024,
    parameter MIN_OFF_RESIDENCY_CYCLES = 4096,
    parameter CLOCK_STABLE_CYCLES = 4,
    parameter POWER_STABLE_CYCLES = 8,
    parameter ISOLATION_SETUP_CYCLES = 2,
    parameter ISOLATION_HOLD_CYCLES = 2,
    parameter RESET_HOLD_CYCLES = 8,
    parameter WAKEUP_STABILIZE_CYCLES = 4,
    parameter DRAIN_TIMEOUT_CYCLES = 65535,
    parameter TILE_ACK_TIMEOUT_CYCLES = 4095,
    parameter RETENTION_TIMEOUT_CYCLES = 4095,
    parameter POWER_TIMEOUT_CYCLES = 65535,
    parameter CLOCK_TIMEOUT_CYCLES = 65535,
    parameter VOLTAGE_TIMEOUT_CYCLES = 65535,
    parameter RELOAD_TIMEOUT_CYCLES = 1048575,
    parameter POWER_GOOD_SYNC_STAGES = 2,
    parameter CLOCK_STATUS_SYNC_STAGES = 2,
    parameter VOLTAGE_STATUS_SYNC_STAGES = 2,
    parameter AUTO_CLOCK_GATE_ENABLE = 1,
    parameter SUPPORT_RETENTION = 0,
    parameter SUPPORT_POWER_GATING = 0,
    parameter SUPPORT_DVFS = 0,
    parameter SUPPORT_SRAM_LOW_POWER = 0,
    parameter SUPPORT_ROLLBACK = 1,
    parameter ENABLE_BREAK_EVEN_CHECK = 1,
    parameter ENABLE_COUNTERS = 1,
    parameter ENABLE_TRACE = 0,
    parameter CONTROL_PROTECTION = 0,
    parameter ASYNC_PHYSICAL_STATUS = 1,
    parameter ASYNC_ARRAY_COMMAND = 0,
    parameter ASYNC_RESET = 0,
    parameter EVENT_QUEUE_DEPTH = 8,
    parameter PHYSICAL_ACK_STABLE_CYCLES = 2,
    parameter CLUSTER_ID_WIDTH = 8,
    parameter OWNER_ID_WIDTH = 16,
    parameter KERNEL_ID_WIDTH = 16,
    parameter PACKAGE_ID_WIDTH = 32,
    parameter ALLOCATION_GENERATION_WIDTH = 16,
    parameter EXECUTION_EPOCH_WIDTH = 8,
    parameter POWER_TAG_WIDTH = 16,
    parameter POWER_SEQUENCE_WIDTH = 16,
    parameter STATE_POLICY_ID_WIDTH = 8,
    parameter OPERATING_POINT_ID_WIDTH = 4,
    parameter EXPECTED_IDLE_WIDTH = 48,
    parameter TIMESTAMP_WIDTH = 64,
    localparam int TG = (NUM_CLOCK_GROUPS > 1) === 1'b1 ? $clog2(NUM_CLOCK_GROUPS) : 1,
    localparam int IG = (NUM_ISOLATION_GROUPS > 1) === 1'b1 ? $clog2(NUM_ISOLATION_GROUPS) : 1,
    parameter [NUM_TILES*TG-1:0] TILE_CLOCK_GROUP_TABLE = default_tile_groups(),
    parameter [NUM_BOUNDARY_ENDPOINTS*IG-1:0] BOUNDARY_ISOLATION_TABLE = default_isolation()
) (
    input wire i_aon_clk,
    input wire i_aon_rstb,
    input wire i_functional_clk,
    input wire i_command_valid,
    input wire i_command_authorized,
    input wire i_system_privileged,
    input wire i_cancel_valid,
    input wire i_config_valid,
    input wire i_config_auto_clock_gate,
    input wire i_config_owner_check,
    input wire i_config_break_even,
    input wire i_cluster_allocated,
    input wire i_array_execution_hold,
    input wire i_array_transition_authorized,
    input wire i_system_transition_authorized,
    input wire i_global_endpoint_drained,
    input wire i_configuration_idle,
    input wire i_runtime_wakeup_required,
    input wire i_fault_excluded,
    input wire i_cluster_busy,
    input wire i_cluster_quiescent,
    input wire i_cluster_drain_done,
    input wire i_scratchpad_idle,
    input wire i_memory_boundary_idle,
    input wire i_local_network_idle,
    input wire i_event_idle,
    input wire i_counter_snapshot_idle,
    input wire i_debug_idle,
    input wire i_voltage_ready,
    input wire i_clock_source_ready,
    input wire i_clock_stopped,
    input wire i_thermal_emergency,
    input wire i_voltage_fault,
    input wire i_clock_fault,
    input wire i_test_mode,
    input wire i_scan_enable,
    input wire i_mbist_enable,
    input wire i_test_clock_enable,
    input wire i_test_authorized,
    input wire i_response_ready,
    input wire i_event_ready,
    input wire i_revalidate_ready,
    input wire i_revalidate_response_valid,
    input wire i_counter_read,
    input wire i_counter_read_snapshot,
    input wire i_counter_snapshot,
    input wire [7:0] i_command_cluster_id,
    input wire [15:0] i_command_owner_id,
    input wire [15:0] i_command_kernel_id,
    input wire [31:0] i_command_package_id,
    input wire [15:0] i_command_allocation_generation,
    input wire [7:0] i_command_execution_epoch,
    input wire [3:0] i_command,
    input wire [4:0] i_command_target_state,
    input wire [3:0] i_command_operating_point,
    input wire [47:0] i_command_expected_idle_cycles,
    input wire [7:0] i_command_state_policy_id,
    input wire [15:0] i_command_flags,
    input wire [15:0] i_command_tag,
    input wire [95:0] i_cancel_identity,
    input wire [15:0] i_cancel_tag,
    input wire [31:0] i_config_idle_entry_cycles,
    input wire [31:0] i_config_min_gated_residency,
    input wire [NUM_WAKE_SOURCES-1:0] i_config_wake_enable,
    input wire [31:0] i_config_allowed_states,
    input wire i_config_allowed_points,
    input wire [15:0] i_allocation_owner_id,
    input wire [15:0] i_allocation_kernel_id,
    input wire [31:0] i_allocation_package_id,
    input wire [15:0] i_allocation_generation,
    input wire [7:0] i_execution_epoch,
    input wire [15:0] i_system_reset_generation,
    input wire [NUM_TILES-1:0] i_tile_busy_mask,
    input wire [NUM_TILES-1:0] i_tile_quiescent_mask,
    input wire [NUM_TILES-1:0] i_tile_drain_done_mask,
    input wire [NUM_TILES*NUM_STALL_REASONS-1:0] i_tile_stall_reason,
    input wire [NUM_STALL_REASONS-1:0] i_stall_reason,
    input wire [NUM_CLOCK_GROUPS-1:0] i_clock_group_request,
    input wire [NUM_WAKE_SOURCES-1:0] i_wakeup_event,
    input wire [95:0] i_wakeup_identity,
    input wire [NUM_POWER_SWITCH_GROUPS-1:0] i_power_good,
    input wire [NUM_POWER_SWITCH_GROUPS-1:0] i_power_switch_ack,
    input wire [NUM_ISOLATION_GROUPS-1:0] i_isolation_ack,
    input wire [NUM_RETENTION_GROUPS-1:0] i_retention_save_ack,
    input wire [NUM_RETENTION_GROUPS-1:0] i_retention_restore_ack,
    input wire [NUM_SRAM_POWER_GROUPS-1:0] i_sram_power_ack,
    input wire [NUM_RESET_GROUPS-1:0] i_reset_ack,
    input wire [NUM_BOUNDARY_ENDPOINTS-1:0] i_boundary_endpoint_ack,
    input wire [NUM_BOUNDARY_ENDPOINTS-1:0] i_boundary_drained,
    input wire [NUM_BOUNDARY_ENDPOINTS-1:0] i_boundary_source_valid,
    input wire [NUM_BOUNDARY_ENDPOINTS-1:0] i_boundary_source_ready,
    input wire [149:0] i_revalidate_response_record,
    input wire [4:0] i_counter_index,
    output wire o_command_ready,
    output wire o_response_valid,
    output wire o_cancel_ready,
    output wire o_cancel_accepted,
    output wire o_cancel_rejected,
    output wire o_config_ready,
    output wire o_config_accepted,
    output wire o_config_rejected,
    output wire o_event_valid,
    output wire o_cluster_accept_enable,
    output wire o_cluster_execution_hold,
    output wire o_cluster_drain_request,
    output wire o_cluster_clock_enable,
    output wire o_cluster_clk,
    output wire o_operand_isolation,
    output wire o_write_disable,
    output wire o_wakeup_request,
    output wire o_wakeup_ack,
    output wire o_transition_active,
    output wire o_idle,
    output wire o_quiescent,
    output wire o_fatal_error,
    output wire o_state_valid,
    output wire o_test_active,
    output wire o_revalidate_valid,
    output wire o_revalidate_response_ready,
    output wire o_counter_valid,
    output wire o_counter_snapshot_valid,
    output wire o_counter_overflow,
    output wire o_diagnostic_overflow,
    output wire o_integrity_error,
    output wire [3:0] o_response_command,
    output wire [2:0] o_response_status,
    output wire [7:0] o_response_error_code,
    output wire [4:0] o_response_reached_state,
    output wire [3:0] o_response_operating_point,
    output wire [15:0] o_response_allocation_generation,
    output wire [31:0] o_response_transition_cycles,
    output wire [15:0] o_response_tag,
    output wire [167:0] o_response_record,
    output wire [7:0] o_config_error_code,
    output wire [241:0] o_event_record,
    output wire [4:0] o_power_state,
    output wire [4:0] o_previous_stable_state,
    output wire [4:0] o_target_state,
    output wire [4:0] o_transition_phase,
    output wire [3:0] o_active_operating_point,
    output wire [3:0] o_requested_operating_point,
    output wire [3:0] o_requested_voltage_id,
    output wire [3:0] o_requested_clock_id,
    output wire [95:0] o_allocation_identity,
    output wire [7:0] o_error_code,
    output wire [4:0] o_first_error_phase,
    output wire [15:0] o_first_error_tag,
    output wire [63:0] o_first_error_timestamp,
    output wire [63:0] o_time,
    output wire [31:0] o_idle_count,
    output wire [31:0] o_state_residency,
    output wire [31:0] o_phase_timer,
    output wire [31:0] o_qualification_count,
    output wire [63:0] o_expected_ack_mask,
    output wire [63:0] o_observed_ack_mask,
    output wire [NUM_WAKE_SOURCES-1:0] o_wakeup_pending,
    output wire [NUM_CLOCK_GROUPS-1:0] o_clock_group_enable,
    output wire [NUM_CLOCK_GROUPS-1:0] o_group_clk,
    output wire [NUM_TILES-1:0] o_tile_functional_clk,
    output wire [NUM_TILES*3-1:0] o_tile_power_command,
    output wire [NUM_TILES-1:0] o_tile_command_valid,
    output wire [NUM_TILES-1:0] o_tile_command_ready,
    output wire [NUM_TILES-1:0] o_tile_command_done,
    output wire [NUM_TILES*4-1:0] o_tile_power_state,
    output wire [NUM_TILES-1:0] o_tile_clock_enable,
    output wire [NUM_TILES-1:0] o_tile_error,
    output wire [NUM_TILES-1:0] o_tile_configured,
    output wire [NUM_TILES-1:0] o_tile_phase_accepted,
    output wire [NUM_TILES-1:0] o_tile_phase_completed,
    output wire [NUM_BOUNDARY_ENDPOINTS-1:0] o_boundary_endpoint_enable,
    output wire [NUM_BOUNDARY_ENDPOINTS-1:0] o_boundary_injection_enable,
    output wire [NUM_BOUNDARY_ENDPOINTS-1:0] o_boundary_valid,
    output wire [NUM_BOUNDARY_ENDPOINTS-1:0] o_boundary_ready,
    output wire [NUM_ISOLATION_GROUPS-1:0] o_isolation_enable,
    output wire [NUM_RETENTION_GROUPS-1:0] o_retention_save,
    output wire [NUM_RETENTION_GROUPS-1:0] o_retention_restore,
    output wire [NUM_RESET_GROUPS-1:0] o_cluster_reset_request,
    output wire [NUM_RESET_GROUPS-1:0] o_functional_rstb,
    output wire [NUM_POWER_SWITCH_GROUPS-1:0] o_power_switch_enable,
    output wire [NUM_SRAM_POWER_GROUPS*2-1:0] o_sram_power_mode,
    output wire [NUM_POWER_SWITCH_GROUPS-1:0] o_qualified_power,
    output wire o_qualified_clock,
    output wire o_qualified_voltage,
    output wire [144:0] o_revalidate_record,
    output wire [63:0] o_counter_data,
    output wire [NUM_WAKE_SOURCES*32-1:0] o_wake_source_count,
    output wire [NUM_CLOCK_GROUPS*32-1:0] o_group_gated_cycles
);
    import cluster_power_manager_pkg::*;
    function automatic logic [NUM_TILES*TG-1:0] default_tile_groups();
        for (int t = 0; t < NUM_TILES; t++)
            default_tile_groups[t*TG+:TG] = TG'(t % NUM_CLOCK_GROUPS);
    endfunction
    function automatic logic [NUM_BOUNDARY_ENDPOINTS*IG-1:0] default_isolation();
        for (int e = 0; e < NUM_BOUNDARY_ENDPOINTS; e++)
            default_isolation[e*IG+:IG] = IG'(e % NUM_ISOLATION_GROUPS);
    endfunction
    function automatic bit tables_valid();
        tables_valid = (((^{TILE_CLOCK_GROUP_TABLE, BOUNDARY_ISOLATION_TABLE} == 1'b0) ||
            (^{TILE_CLOCK_GROUP_TABLE, BOUNDARY_ISOLATION_TABLE} == 1'b1)) === 1'b1);
        for (int t = 0; t < NUM_TILES; t++)
            if (TILE_CLOCK_GROUP_TABLE[t*TG+:TG] >= NUM_CLOCK_GROUPS) tables_valid = 0;
        for (int e = 0; e < NUM_BOUNDARY_ENDPOINTS; e++)
            if (BOUNDARY_ISOLATION_TABLE[e*IG+:IG] >= NUM_ISOLATION_GROUPS) tables_valid = 0;
    endfunction
    localparam bit PARAMETERS_VALID =
        ((64'(NUM_TILES) >= 64'd1 && 64'(NUM_TILES) <= 64'd32) === 1'b1) &&
        (((^NUM_TILES == 1'b0) || (^NUM_TILES == 1'b1)) === 1'b1) &&
        ((64'(NUM_CLOCK_GROUPS) >= 64'd1 && 64'(NUM_CLOCK_GROUPS) <= 64'd32) === 1'b1) &&
        (((^NUM_CLOCK_GROUPS == 1'b0) || (^NUM_CLOCK_GROUPS == 1'b1)) === 1'b1) &&
        ((64'(NUM_WAKE_SOURCES) >= 64'd1 && 64'(NUM_WAKE_SOURCES) <= 64'd32) === 1'b1) &&
        (((^NUM_WAKE_SOURCES == 1'b0) || (^NUM_WAKE_SOURCES == 1'b1)) === 1'b1) &&
        ((64'(NUM_STALL_REASONS) >= 64'd1 && 64'(NUM_STALL_REASONS) <= 64'd32) === 1'b1) &&
        (((^NUM_STALL_REASONS == 1'b0) || (^NUM_STALL_REASONS == 1'b1)) === 1'b1) &&
        ((64'(NUM_ISOLATION_GROUPS) >= 64'd1 && 64'(NUM_ISOLATION_GROUPS) <= 64'd32) === 1'b1) &&
        (((^NUM_ISOLATION_GROUPS == 1'b0) || (^NUM_ISOLATION_GROUPS == 1'b1)) === 1'b1) &&
        ((64'(NUM_RETENTION_GROUPS) >= 64'd1 && 64'(NUM_RETENTION_GROUPS) <= 64'd32) === 1'b1) &&
        (((^NUM_RETENTION_GROUPS == 1'b0) || (^NUM_RETENTION_GROUPS == 1'b1)) === 1'b1) &&
        ((64'(NUM_RESET_GROUPS) >= 64'd1 && 64'(NUM_RESET_GROUPS) <= 64'd32) === 1'b1) &&
        (((^NUM_RESET_GROUPS == 1'b0) || (^NUM_RESET_GROUPS == 1'b1)) === 1'b1) &&
        ((64'(NUM_BOUNDARY_ENDPOINTS) >= 64'd1 && 64'(NUM_BOUNDARY_ENDPOINTS) <= 64'd32) === 1'b1)
            &&
        (((^NUM_BOUNDARY_ENDPOINTS == 1'b0) || (^NUM_BOUNDARY_ENDPOINTS == 1'b1)) === 1'b1) &&
        ((64'(NUM_POWER_SWITCH_GROUPS) >= 64'd1 && 64'(NUM_POWER_SWITCH_GROUPS) <= 64'd8) === 1'b1)
            &&
        (((^NUM_POWER_SWITCH_GROUPS == 1'b0) || (^NUM_POWER_SWITCH_GROUPS == 1'b1)) === 1'b1) &&
        ((64'(NUM_SRAM_POWER_GROUPS) >= 64'd1 && 64'(NUM_SRAM_POWER_GROUPS) <= 64'd8) === 1'b1) &&
        (((^NUM_SRAM_POWER_GROUPS == 1'b0) || (^NUM_SRAM_POWER_GROUPS == 1'b1)) === 1'b1) &&
        ((64'(NUM_OPERATING_POINTS) >= 64'd1 && 64'(NUM_OPERATING_POINTS) <= 64'd1) === 1'b1) &&
        (((^NUM_OPERATING_POINTS == 1'b0) || (^NUM_OPERATING_POINTS == 1'b1)) === 1'b1) &&
        ((64'(POWER_PROFILE) >= 64'd0 && 64'(POWER_PROFILE) <= 64'd4) === 1'b1) &&
        (((^POWER_PROFILE == 1'b0) || (^POWER_PROFILE == 1'b1)) === 1'b1) &&
        ((64'(CLUSTER_ID) >= 64'd0 && 64'(CLUSTER_ID) <= 64'd255) === 1'b1) &&
        (((^CLUSTER_ID == 1'b0) || (^CLUSTER_ID == 1'b1)) === 1'b1) &&
        ((64'(CONTROL_PROTECTION) >= 64'd0 && 64'(CONTROL_PROTECTION) <= 64'd2) === 1'b1) &&
        (((^CONTROL_PROTECTION == 1'b0) || (^CONTROL_PROTECTION == 1'b1)) === 1'b1) &&
        ((64'(EVENT_QUEUE_DEPTH) >= 64'd2 && 64'(EVENT_QUEUE_DEPTH) <= 64'd32) === 1'b1) &&
        (((^EVENT_QUEUE_DEPTH == 1'b0) || (^EVENT_QUEUE_DEPTH == 1'b1)) === 1'b1) &&
        ((64'(IDLE_ENTRY_CYCLES) >= 64'd1 && 64'(IDLE_ENTRY_CYCLES) <= 64'd4294967295) === 1'b1) &&
        (((^IDLE_ENTRY_CYCLES == 1'b0) || (^IDLE_ENTRY_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(MIN_GATED_RESIDENCY_CYCLES) >= 64'd1 && 64'(MIN_GATED_RESIDENCY_CYCLES) <=
            64'd4294967295) === 1'b1) &&
        (((^MIN_GATED_RESIDENCY_CYCLES == 1'b0) || (^MIN_GATED_RESIDENCY_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(MIN_RETENTION_RESIDENCY_CYCLES) >= 64'd1 && 64'(MIN_RETENTION_RESIDENCY_CYCLES) <=
            64'd4294967295) === 1'b1) &&
        (((^MIN_RETENTION_RESIDENCY_CYCLES == 1'b0) || (^MIN_RETENTION_RESIDENCY_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(MIN_OFF_RESIDENCY_CYCLES) >= 64'd1 && 64'(MIN_OFF_RESIDENCY_CYCLES) <= 64'd4294967295)
            === 1'b1) &&
        (((^MIN_OFF_RESIDENCY_CYCLES == 1'b0) || (^MIN_OFF_RESIDENCY_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(CLOCK_STABLE_CYCLES) >= 64'd1 && 64'(CLOCK_STABLE_CYCLES) <= 64'd4294967295) === 1'b1)
            &&
        (((^CLOCK_STABLE_CYCLES == 1'b0) || (^CLOCK_STABLE_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(POWER_STABLE_CYCLES) >= 64'd1 && 64'(POWER_STABLE_CYCLES) <= 64'd4294967295) === 1'b1)
            &&
        (((^POWER_STABLE_CYCLES == 1'b0) || (^POWER_STABLE_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(ISOLATION_SETUP_CYCLES) >= 64'd1 && 64'(ISOLATION_SETUP_CYCLES) <= 64'd4294967295) ===
            1'b1) &&
        (((^ISOLATION_SETUP_CYCLES == 1'b0) || (^ISOLATION_SETUP_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(ISOLATION_HOLD_CYCLES) >= 64'd1 && 64'(ISOLATION_HOLD_CYCLES) <= 64'd4294967295) ===
            1'b1) &&
        (((^ISOLATION_HOLD_CYCLES == 1'b0) || (^ISOLATION_HOLD_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(RESET_HOLD_CYCLES) >= 64'd1 && 64'(RESET_HOLD_CYCLES) <= 64'd4294967295) === 1'b1) &&
        (((^RESET_HOLD_CYCLES == 1'b0) || (^RESET_HOLD_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(WAKEUP_STABILIZE_CYCLES) >= 64'd1 && 64'(WAKEUP_STABILIZE_CYCLES) <= 64'd4294967295)
            === 1'b1) &&
        (((^WAKEUP_STABILIZE_CYCLES == 1'b0) || (^WAKEUP_STABILIZE_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(DRAIN_TIMEOUT_CYCLES) >= 64'd1 && 64'(DRAIN_TIMEOUT_CYCLES) <= 64'd4294967295) ===
            1'b1) &&
        (((^DRAIN_TIMEOUT_CYCLES == 1'b0) || (^DRAIN_TIMEOUT_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(TILE_ACK_TIMEOUT_CYCLES) >= 64'd1 && 64'(TILE_ACK_TIMEOUT_CYCLES) <= 64'd4294967295)
            === 1'b1) &&
        (((^TILE_ACK_TIMEOUT_CYCLES == 1'b0) || (^TILE_ACK_TIMEOUT_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(RETENTION_TIMEOUT_CYCLES) >= 64'd1 && 64'(RETENTION_TIMEOUT_CYCLES) <= 64'd4294967295)
            === 1'b1) &&
        (((^RETENTION_TIMEOUT_CYCLES == 1'b0) || (^RETENTION_TIMEOUT_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(POWER_TIMEOUT_CYCLES) >= 64'd1 && 64'(POWER_TIMEOUT_CYCLES) <= 64'd4294967295) ===
            1'b1) &&
        (((^POWER_TIMEOUT_CYCLES == 1'b0) || (^POWER_TIMEOUT_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(CLOCK_TIMEOUT_CYCLES) >= 64'd1 && 64'(CLOCK_TIMEOUT_CYCLES) <= 64'd4294967295) ===
            1'b1) &&
        (((^CLOCK_TIMEOUT_CYCLES == 1'b0) || (^CLOCK_TIMEOUT_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(VOLTAGE_TIMEOUT_CYCLES) >= 64'd1 && 64'(VOLTAGE_TIMEOUT_CYCLES) <= 64'd4294967295) ===
            1'b1) &&
        (((^VOLTAGE_TIMEOUT_CYCLES == 1'b0) || (^VOLTAGE_TIMEOUT_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(RELOAD_TIMEOUT_CYCLES) >= 64'd1 && 64'(RELOAD_TIMEOUT_CYCLES) <= 64'd4294967295) ===
            1'b1) &&
        (((^RELOAD_TIMEOUT_CYCLES == 1'b0) || (^RELOAD_TIMEOUT_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(POWER_GOOD_SYNC_STAGES) >= 64'd2 && 64'(POWER_GOOD_SYNC_STAGES) <= 64'd4) === 1'b1) &&
        (((^POWER_GOOD_SYNC_STAGES == 1'b0) || (^POWER_GOOD_SYNC_STAGES == 1'b1)) === 1'b1) &&
        ((64'(CLOCK_STATUS_SYNC_STAGES) >= 64'd2 && 64'(CLOCK_STATUS_SYNC_STAGES) <= 64'd4) ===
            1'b1) &&
        (((^CLOCK_STATUS_SYNC_STAGES == 1'b0) || (^CLOCK_STATUS_SYNC_STAGES == 1'b1)) === 1'b1) &&
        ((64'(VOLTAGE_STATUS_SYNC_STAGES) >= 64'd2 && 64'(VOLTAGE_STATUS_SYNC_STAGES) <= 64'd4) ===
            1'b1) &&
        (((^VOLTAGE_STATUS_SYNC_STAGES == 1'b0) || (^VOLTAGE_STATUS_SYNC_STAGES == 1'b1)) === 1'b1) &&
        ((64'(PHYSICAL_ACK_STABLE_CYCLES) >= 64'd1 && 64'(PHYSICAL_ACK_STABLE_CYCLES) <=
            64'd4294967295) === 1'b1) &&
        (((^PHYSICAL_ACK_STABLE_CYCLES == 1'b0) || (^PHYSICAL_ACK_STABLE_CYCLES == 1'b1)) === 1'b1) &&
        ((64'(CLUSTER_ID_WIDTH) >= 64'd8 && 64'(CLUSTER_ID_WIDTH) <= 64'd8) === 1'b1) &&
        (((^CLUSTER_ID_WIDTH == 1'b0) || (^CLUSTER_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((64'(OWNER_ID_WIDTH) >= 64'd16 && 64'(OWNER_ID_WIDTH) <= 64'd16) === 1'b1) &&
        (((^OWNER_ID_WIDTH == 1'b0) || (^OWNER_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((64'(KERNEL_ID_WIDTH) >= 64'd16 && 64'(KERNEL_ID_WIDTH) <= 64'd16) === 1'b1) &&
        (((^KERNEL_ID_WIDTH == 1'b0) || (^KERNEL_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((64'(PACKAGE_ID_WIDTH) >= 64'd32 && 64'(PACKAGE_ID_WIDTH) <= 64'd32) === 1'b1) &&
        (((^PACKAGE_ID_WIDTH == 1'b0) || (^PACKAGE_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((64'(ALLOCATION_GENERATION_WIDTH) >= 64'd16 && 64'(ALLOCATION_GENERATION_WIDTH) <= 64'd16)
            === 1'b1) &&
        (((^ALLOCATION_GENERATION_WIDTH == 1'b0) || (^ALLOCATION_GENERATION_WIDTH == 1'b1)) === 1'b1) &&
        ((64'(EXECUTION_EPOCH_WIDTH) >= 64'd8 && 64'(EXECUTION_EPOCH_WIDTH) <= 64'd8) === 1'b1) &&
        (((^EXECUTION_EPOCH_WIDTH == 1'b0) || (^EXECUTION_EPOCH_WIDTH == 1'b1)) === 1'b1) &&
        ((64'(POWER_TAG_WIDTH) >= 64'd16 && 64'(POWER_TAG_WIDTH) <= 64'd16) === 1'b1) &&
        (((^POWER_TAG_WIDTH == 1'b0) || (^POWER_TAG_WIDTH == 1'b1)) === 1'b1) &&
        ((64'(POWER_SEQUENCE_WIDTH) >= 64'd16 && 64'(POWER_SEQUENCE_WIDTH) <= 64'd16) === 1'b1) &&
        (((^POWER_SEQUENCE_WIDTH == 1'b0) || (^POWER_SEQUENCE_WIDTH == 1'b1)) === 1'b1) &&
        ((64'(STATE_POLICY_ID_WIDTH) >= 64'd8 && 64'(STATE_POLICY_ID_WIDTH) <= 64'd8) === 1'b1) &&
        (((^STATE_POLICY_ID_WIDTH == 1'b0) || (^STATE_POLICY_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((64'(OPERATING_POINT_ID_WIDTH) >= 64'd4 && 64'(OPERATING_POINT_ID_WIDTH) <= 64'd4) ===
            1'b1) &&
        (((^OPERATING_POINT_ID_WIDTH == 1'b0) || (^OPERATING_POINT_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((64'(EXPECTED_IDLE_WIDTH) >= 64'd48 && 64'(EXPECTED_IDLE_WIDTH) <= 64'd48) === 1'b1) &&
        (((^EXPECTED_IDLE_WIDTH == 1'b0) || (^EXPECTED_IDLE_WIDTH == 1'b1)) === 1'b1) &&
        ((64'(TIMESTAMP_WIDTH) >= 64'd64 && 64'(TIMESTAMP_WIDTH) <= 64'd64) === 1'b1) &&
        (((^TIMESTAMP_WIDTH == 1'b0) || (^TIMESTAMP_WIDTH == 1'b1)) === 1'b1) &&
        (AUTO_CLOCK_GATE_ENABLE === 0 || AUTO_CLOCK_GATE_ENABLE === 1) &&
        (SUPPORT_RETENTION === 0 || SUPPORT_RETENTION === 1) &&
        (SUPPORT_POWER_GATING === 0 || SUPPORT_POWER_GATING === 1) &&
        (SUPPORT_DVFS === 0 || SUPPORT_DVFS === 1) &&
        (SUPPORT_SRAM_LOW_POWER === 0 || SUPPORT_SRAM_LOW_POWER === 1) &&
        (SUPPORT_ROLLBACK === 0 || SUPPORT_ROLLBACK === 1) &&
        (ENABLE_BREAK_EVEN_CHECK === 0 || ENABLE_BREAK_EVEN_CHECK === 1) &&
        (ENABLE_COUNTERS === 0 || ENABLE_COUNTERS === 1) &&
        (ENABLE_TRACE === 0 || ENABLE_TRACE === 1) &&
        (ASYNC_PHYSICAL_STATUS === 0 || ASYNC_PHYSICAL_STATUS === 1) &&
        (ASYNC_ARRAY_COMMAND === 0 || ASYNC_ARRAY_COMMAND === 1) &&
        (ASYNC_RESET === 0 || ASYNC_RESET === 1) &&
        (SUPPORT_RETENTION === 0) &&
        (SUPPORT_POWER_GATING === 0) &&
        (SUPPORT_DVFS === 0) &&
        (SUPPORT_SRAM_LOW_POWER === 0) &&
        (ENABLE_TRACE === 0) &&
        (ASYNC_ARRAY_COMMAND === 0) &&
        (POWER_PROFILE === 0 || POWER_PROFILE === 4) &&
        ((POWER_PROFILE != 4 || CONTROL_PROTECTION != 0) === 1'b1) &&
        tables_valid();
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        cluster_power_manager_parameters_must_be_valid invalid_parameters ();
    end else begin : g_manager
        localparam int T = NUM_TILES;
        localparam int G = NUM_CLOCK_GROUPS;
        localparam int W = NUM_WAKE_SOURCES;
        localparam int I = NUM_ISOLATION_GROUPS;
        localparam int R = NUM_RESET_GROUPS;
        localparam int E = NUM_BOUNDARY_ENDPOINTS;
        localparam int P = NUM_POWER_SWITCH_GROUPS;
        localparam int S = NUM_SRAM_POWER_GROUPS;
        localparam int H = NUM_RETENTION_GROUPS;
        localparam int MISC = I + R + E + S + 2 * H + 4;
        typedef struct packed {
            logic root;
            logic [G-1:0] groups;
            logic accept_work;
            logic hold_execution;
            logic drain;
            logic operand;
            logic write_disable;
            logic [I-1:0] isolation;
            logic [R-1:0] resets;
            logic [E-1:0] endpoints;
            logic [E-1:0] injection;
            logic tile_reset;
        } controls_t;
        function automatic controls_t safe_controls();
            controls_t value;
            value = '0;
            value.hold_execution = 1;
            value.operand = 1;
            value.write_disable = 1;
            value.isolation = '1;
            value.resets = '1;
            value.tile_reset = 1;
            return value;
        endfunction
        typedef struct packed {
            logic automatic_gate;
            logic [31:0] idle_threshold;
            logic [31:0] min_residency;
            logic [W-1:0] wakes;
            logic [31:0] states;
        } policy_t;
        function automatic policy_t default_policy();
            policy_t value;
            value = '0;
            value.automatic_gate = AUTO_CLOCK_GATE_ENABLE != 0;
            value.idle_threshold = 32'(IDLE_ENTRY_CYCLES);
            value.min_residency = 32'(MIN_GATED_RESIDENCY_CYCLES);
            value.wakes = '1;
            value.states = 32'h0000001e;
            return value;
        endfunction
        typedef struct packed {
            logic [4:0] state;
            logic [4:0] phase;
            logic [4:0] target;
            logic [4:0] previous;
            identity_t identity;
            logic [15:0] boot_generation;
            logic [15:0] serial;
            logic fatal;
            logic recovering;
            logic run_authorized;
            logic state_valid;
            logic power_qualified;
            logic clock_qualified;
            logic cancel;
            logic cancel_seen;
            logic irreversible;
            logic queued_wake;
            logic test_requested;
            logic reload;
            logic [2:0] outcome;
            logic [7:0] outcome_error;
            logic [W-1:0] wakes;
            logic [T-1:0] tile_sent;
            logic [T-1:0] tile_done;
            logic [T-1:0] configured;
            logic [31:0] idle_count;
            logic [31:0] residency;
            logic [31:0] timer;
            logic [31:0] qualification;
            logic [63:0] start_time;
            logic [7:0] reset_index;
            logic request_active;
            logic request_sent;
            validation_t request;
            logic [7:0] first_error;
            logic [4:0] first_phase;
            logic [15:0] first_tag;
            logic [63:0] first_time;
            logic [63:0] first_expected;
            logic [63:0] first_observed;
            controls_t witness;
        } state_record_t;
        localparam int CW = $bits(controls_t);
        localparam int QW = $bits(state_record_t);
        localparam int PW = $bits(policy_t);
        localparam int KW = $bits(command_slot_t);
        localparam int RW = $bits(response_slot_t);
        localparam logic [CW-1:0] SAFE = safe_controls();
        state_record_t q;
        state_record_t d;
        controls_t controls;
        controls_t controls_d;
        policy_t policy;
        policy_t policy_d;
        command_slot_t command_slot;
        command_slot_t command_d;
        response_slot_t response_slot;
        response_slot_t response_d;
        command_t incoming;
        identity_t live_identity;
        // Only independent stable physical levels cross into AON;
        // command, allocation and validation records are synchronous AON peers.
        wire reset_b;
        wire state_bad;
        wire state_corrected;
        wire policy_bad;
        wire policy_corrected;
        wire command_bad;
        wire command_corrected;
        wire response_bad;
        wire response_corrected;
        wire events_bad;
        wire events_exhausted;
        wire controls_bad = q.state != CPM_RESET && controls !== q.witness;
        wire integrity_bad = state_bad || policy_bad || command_bad || response_bad ||
            events_bad || controls_bad;
        wire [P-1:0] power_good;
        wire [P-1:0] switches;
        wire clock_ready;
        wire voltage_ready;
        wire [MISC-1:0] misc;
        wire [I-1:0] isolation_ack;
        wire [R-1:0] reset_ack;
        wire [E-1:0] endpoints_ack;
        wire [S-1:0] sram_ack;
        wire [H-1:0] save_ack;
        wire [H-1:0] restore_ack;
        wire clock_stopped;
        wire thermal;
        wire voltage_fault;
        wire clock_fault;
        wire [R-1:0] functional_rstb;
        wire [95:0] binding_bits = q.identity;
        wire [T-1:0] tile_configured;
        wire [T-1:0] tile_config_accepted;
        wire [T-1:0] tile_config_ready;
        wire [T-1:0] tile_ready;
        wire [T-1:0] tile_done;
        wire [T-1:0] tile_rejected;
        wire [T-1:0] tile_error;
        wire [T-1:0] tile_clock;
        wire [T-1:0] tile_groups;
        wire [T*4-1:0] tile_state;
        wire [T-1:0] tile_valid;
        wire [T-1:0] tile_config_valid;
        wire [2:0] tile_command;
        wire tile_status_enable = q.phase == PH_NONE || q.phase == PH_DRAIN ||
            q.phase == PH_ENDPOINT_DISABLE || q.phase == PH_TILE_IDLE;
        wire [63:0] time_value;
        wire time_overflow;
        wire normal_ready;
        wire terminal_ready;
        wire terminal_capacity;
        wire events_empty;
        logic normal_push;
        logic terminal_push;
        logic fatal_push;
        event_t normal_event;
        event_t terminal_event;
        event_t fatal_event;
        logic cancel_accepted;
        logic cancel_rejected;
        logic config_accepted;
        logic config_rejected;
        logic [7:0] config_error;
        logic wake_ack;
        logic [W-1:0] consumed_wakes;
        logic [31:0] statistics;
        wire [31:0] state_onehot;
        wire state_select_valid;
        wire [31:0] counter_overflow;
        wire authority = i_array_transition_authorized === 1'b1 &&
            i_system_transition_authorized === 1'b1 && i_fault_excluded === 1'b0;
        wire identity_known = ^{i_cluster_allocated, i_allocation_owner_id,
            i_allocation_kernel_id, i_allocation_package_id, i_allocation_generation,
            i_execution_epoch, i_system_reset_generation} !== 1'bx;
        wire quiet = i_cluster_busy === 1'b0 && i_cluster_quiescent === 1'b1 &&
            i_tile_busy_mask === {T{1'b0}} && i_tile_quiescent_mask === {T{1'b1}} &&
            i_scratchpad_idle === 1'b1 && i_memory_boundary_idle === 1'b1 &&
            i_local_network_idle === 1'b1 && i_event_idle === 1'b1 &&
            i_configuration_idle === 1'b1 && i_counter_snapshot_idle === 1'b1 &&
            i_debug_idle === 1'b1 && i_global_endpoint_drained === 1'b1 &&
            i_boundary_drained === {E{1'b1}};
        wire drained = quiet && i_cluster_drain_done === 1'b1 &&
            i_tile_drain_done_mask === {T{1'b1}};
        wire physical_power = power_good === {P{1'b1}} && switches === {P{1'b1}};
        wire physical_clock = clock_ready === 1'b1 && voltage_ready === 1'b1;
        wire test_requested = i_test_mode === 1'b1 || i_scan_enable === 1'b1 ||
            i_mbist_enable === 1'b1;
        wire stable_state = stable(q.state) && q.phase == PH_NONE;
        wire command_fire = i_command_valid === 1'b1 && o_command_ready;
        wire response_fire = o_response_valid && i_response_ready === 1'b1;
        wire [31:0] capabilities = 32'h0000001e;
        validation_response_t validation_response;
        logic [63:0] expected_ack;
        logic [63:0] observed_ack;

        if (ASYNC_RESET) begin : g_async_reset
            reset_synchronizer u_reset (
                .i_clk(i_aon_clk),
                .i_async_rstb(i_aon_rstb),
                .o_rstb(reset_b)
            );
        end else begin : g_sync_reset
            assign reset_b = i_aon_rstb === 1'b1;
        end

        tile_shell_state #(
            .WIDTH(QW),
            .PROTECTION(CONTROL_PROTECTION)
        ) u_state (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(d != q || state_corrected),
            .i_data(d),
            .o_data(q),
            .o_bad(state_bad),
            .o_corrected(state_corrected)
        );

        tile_shell_state #(
            .WIDTH(PW),
            .PROTECTION(CONTROL_PROTECTION),
            .RESET_VALUE(default_policy())
        ) u_policy (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(policy_d != policy || policy_corrected),
            .i_data(policy_d),
            .o_data(policy),
            .o_bad(policy_bad),
            .o_corrected(policy_corrected)
        );

        tile_shell_state #(
            .WIDTH(KW),
            .PROTECTION(CONTROL_PROTECTION)
        ) u_command (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(command_d != command_slot || command_corrected),
            .i_data(command_d),
            .o_data(command_slot),
            .o_bad(command_bad),
            .o_corrected(command_corrected)
        );

        tile_shell_state #(
            .WIDTH(RW),
            .PROTECTION(CONTROL_PROTECTION)
        ) u_response (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(response_d != response_slot || response_corrected),
            .i_data(response_d),
            .o_data(response_slot),
            .o_bad(response_bad),
            .o_corrected(response_corrected)
        );

        // Physical requests are an independent AON register. Protected state is a
        // witness; decoding an invalid codeword cannot directly toggle controls.
        dff #(
            .WIDTH(CW),
            .RESET_VALUE(SAFE)
        ) u_controls (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(controls_d != controls),
            .i_d(controls_d),
            .o_q(controls)
        );

        cluster_power_manager_sync #(
            .WIDTH(2 * P),
            .STAGES(POWER_GOOD_SYNC_STAGES),
            .ASYNCHRONOUS(ASYNC_PHYSICAL_STATUS)
        ) u_power_sync (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_status({i_power_good, i_power_switch_ack}),
            .o_status({power_good, switches})
        );

        cluster_power_manager_sync #(
            .STAGES(CLOCK_STATUS_SYNC_STAGES),
            .ASYNCHRONOUS(ASYNC_PHYSICAL_STATUS)
        ) u_clock_sync (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_status(i_clock_source_ready),
            .o_status(clock_ready)
        );

        cluster_power_manager_sync #(
            .STAGES(VOLTAGE_STATUS_SYNC_STAGES),
            .ASYNCHRONOUS(ASYNC_PHYSICAL_STATUS)
        ) u_voltage_sync (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_status(i_voltage_ready),
            .o_status(voltage_ready)
        );

        cluster_power_manager_sync #(
            .WIDTH(MISC),
            .STAGES(POWER_GOOD_SYNC_STAGES),
            .ASYNCHRONOUS(ASYNC_PHYSICAL_STATUS)
        ) u_misc_sync (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_status({i_isolation_ack, i_reset_ack, i_boundary_endpoint_ack, i_sram_power_ack,
                i_retention_save_ack, i_retention_restore_ack, i_clock_stopped,
                i_thermal_emergency, i_voltage_fault, i_clock_fault}),
            .o_status(misc)
        );

        assign {isolation_ack, reset_ack, endpoints_ack, sram_ack, save_ack, restore_ack,
            clock_stopped, thermal, voltage_fault, clock_fault} = misc;

        counter #(
            .WIDTH(64),
            .SATURATE(1)
        ) u_time (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(1'b1),
            .i_clear(1'b0),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value(64'b0),
            .o_count(time_value),
            .o_overflow(time_overflow),
            .o_underflow(),
            .o_terminal()
        );

        cluster_power_manager_tiles #(
            .TILES(T),
            .GROUPS(G),
            .STALLS(NUM_STALL_REASONS),
            .TIMEOUT(TILE_ACK_TIMEOUT_CYCLES),
            .TILE_GROUPS(TILE_CLOCK_GROUP_TABLE)
        ) u_tiles (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b && !controls.tile_reset),
            .i_status_enable(tile_status_enable),
            .i_power_good(physical_power),
            .i_epoch(binding_bits[95:88]),
            .i_config_valid(tile_config_valid),
            .i_command_valid(tile_valid),
            .i_command(tile_command),
            .i_busy(i_tile_busy_mask),
            .i_quiescent(i_tile_quiescent_mask),
            .i_drain_done(i_tile_drain_done_mask),
            .i_stalls(i_tile_stall_reason),
            .i_groups(i_clock_group_request),
            .o_configured(tile_configured),
            .o_config_accepted(tile_config_accepted),
            .o_config_ready(tile_config_ready),
            .o_command_ready(tile_ready),
            .o_command_done(tile_done),
            .o_command_rejected(tile_rejected),
            .o_state(tile_state),
            .o_clock(tile_clock),
            .o_groups(tile_groups),
            .o_error(tile_error)
        );

        assign tile_config_valid = reset_b && q.phase == PH_TILE_CONFIG ? ~q.configured : '0;
        assign tile_valid = reset_b && (q.phase == PH_TILE_RUN || q.phase == PH_TILE_IDLE) ?
            ~q.tile_sent : '0;
        assign tile_command = q.phase == PH_TILE_IDLE ?
            tile_power_controller_pkg::POWER_IDLE : tile_power_controller_pkg::POWER_RUN;

        clock_gate u_root_gate (
            .i_clk(i_functional_clk),
            .i_enable(o_cluster_clock_enable),
            .i_test_enable(1'b0),
            .o_gclk(o_cluster_clk)
        );

        for (genvar g = 0; g < G; g++) begin : g_group
            clock_gate u_gate (
                .i_clk(o_cluster_clk),
                .i_enable(o_clock_group_enable[g]),
                .i_test_enable(1'b0),
                .o_gclk(o_group_clk[g])
            );
        end

        for (genvar t = 0; t < T; t++) begin : g_tile_clock
            localparam int GROUP = int'(TILE_CLOCK_GROUP_TABLE[t*TG+:TG]);
            assign o_tile_functional_clk[t] = o_group_clk[GROUP];
        end

        for (genvar r = 0; r < R; r++) begin : g_reset
            reset_synchronizer u_functional_release (
                .i_clk(o_cluster_clk),
                .i_async_rstb(reset_b && !controls.resets[r]),
                .o_rstb(functional_rstb[r])
            );
        end

        for (genvar e = 0; e < E; e++) begin : g_boundary
            localparam int GROUP = int'(BOUNDARY_ISOLATION_TABLE[e*IG+:IG]);
            wire clamp = !o_boundary_endpoint_enable[e] || o_isolation_enable[GROUP];

            isolation_cell u_valid (
                .i_data(i_boundary_source_valid[e]),
                .i_isolate(clamp),
                .o_data(o_boundary_valid[e])
            );

            isolation_cell u_ready (
                .i_data(i_boundary_source_ready[e]),
                .i_isolate(clamp),
                .o_data(o_boundary_ready[e])
            );
        end

        cluster_power_manager_events #(
            .DEPTH(EVENT_QUEUE_DEPTH),
            .PROTECTION(CONTROL_PROTECTION)
        ) u_events (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_normal_valid(normal_push),
            .o_normal_ready(normal_ready),
            .i_normal(normal_event),
            .i_terminal_valid(terminal_push),
            .o_terminal_ready(terminal_ready),
            .o_terminal_capacity(terminal_capacity),
            .i_terminal(terminal_event),
            .i_fatal_valid(fatal_push),
            .i_fatal(fatal_event),
            .o_valid(o_event_valid),
            .i_ready(i_event_ready),
            .o_event(o_event_record),
            .o_empty(events_empty),
            .o_overflow(o_diagnostic_overflow),
            .o_bad(events_bad),
            .o_exhausted(events_exhausted)
        );

        assign o_response_valid = reset_b && response_slot.valid && !response_bad;
        assign o_response_record = response_slot.value;
        assign o_response_command = response_slot.value.command;
        assign o_response_status = response_slot.value.status;
        assign o_response_error_code = response_slot.value.error;
        assign o_response_reached_state = response_slot.value.state;
        assign o_response_operating_point = response_slot.value.point;
        assign o_response_allocation_generation =
            response_slot.value.identity.allocation_generation;
        assign o_response_transition_cycles = response_slot.value.cycles;
        assign o_response_tag = response_slot.value.tag;
        assign o_command_ready = reset_b && stable_state && !command_slot.valid &&
            !response_slot.valid && !integrity_bad && normal_ready && terminal_capacity &&
            i_config_valid === 1'b0;
        assign o_config_ready = reset_b && stable_state && q.state != CPM_ERROR &&
            q.state != CPM_TEST && quiet && !command_slot.valid && events_empty &&
            !q.request_active && q.wakes == 0 && !integrity_bad;
        assign o_cancel_ready = reset_b && command_slot.valid && !response_slot.valid &&
            q.phase != PH_NONE && !q.cancel_seen && !integrity_bad;
        assign o_cancel_accepted = cancel_accepted;
        assign o_cancel_rejected = cancel_rejected;
        assign o_config_accepted = config_accepted;
        assign o_config_rejected = config_rejected;
        assign o_config_error_code = config_error;
        assign o_cluster_accept_enable = reset_b ? controls.accept_work : 1'b0;
        assign o_cluster_execution_hold = reset_b ? controls.hold_execution : 1'b1;
        assign o_cluster_drain_request = reset_b && controls.drain;
        assign o_cluster_clock_enable = reset_b && controls.root;
        assign o_clock_group_enable = reset_b ? controls.groups : '0;
        assign o_operand_isolation = !reset_b || controls.operand;
        assign o_write_disable = !reset_b || controls.write_disable;
        assign o_boundary_endpoint_enable = reset_b ? controls.endpoints : '0;
        assign o_boundary_injection_enable = reset_b ? controls.injection : '0;
        assign o_isolation_enable = reset_b ? controls.isolation : '1;
        assign o_cluster_reset_request = reset_b ? controls.resets : '1;
        assign o_functional_rstb = functional_rstb;
        assign o_retention_save = '0;
        assign o_retention_restore = '0;
        assign o_power_switch_enable = '1;
        assign o_sram_power_mode = '0;
        assign o_active_operating_point = 0;
        assign o_requested_operating_point = 0;
        assign o_requested_voltage_id = 0;
        assign o_requested_clock_id = 0;
        assign o_qualified_power = q.power_qualified && physical_power ? {P{1'b1}} : '0;
        assign o_qualified_clock = q.clock_qualified && physical_clock;
        assign o_qualified_voltage = q.clock_qualified && voltage_ready === 1'b1;
        assign o_tile_configured = tile_configured;
        assign o_tile_power_state = tile_state;
        assign o_tile_clock_enable = tile_clock;
        assign o_tile_error = tile_error;
        assign o_tile_command_valid = tile_valid;
        assign o_tile_command_ready = tile_ready;
        assign o_tile_command_done = tile_done;
        assign o_tile_phase_accepted = q.tile_sent;
        assign o_tile_phase_completed = q.tile_done;

        for (genvar t = 0; t < T; t++) begin : g_command_status
            assign o_tile_power_command[t*3+:3] = tile_command;
        end

        assign o_power_state = q.state;
        assign o_previous_stable_state = q.previous;
        assign o_target_state = q.target;
        assign o_transition_phase = q.phase;
        assign o_transition_active = q.phase != PH_NONE || q.state == CPM_RESET;
        assign o_allocation_identity = q.identity;
        assign o_fatal_error = q.fatal || integrity_bad;
        assign o_integrity_error = integrity_bad;
        assign o_error_code = q.first_error;
        assign o_first_error_phase = q.first_phase;
        assign o_first_error_tag = q.first_tag;
        assign o_first_error_timestamp = q.first_time;
        assign o_expected_ack_mask = q.fatal ? q.first_expected : expected_ack;
        assign o_observed_ack_mask = q.fatal ? q.first_observed : observed_ack;
        assign o_time = time_value;
        assign o_idle_count = q.idle_count;
        assign o_state_residency = q.residency;
        assign o_phase_timer = q.timer;
        assign o_qualification_count = q.qualification;
        assign o_wakeup_pending = q.wakes;
        assign o_wakeup_request = q.wakes != 0 || q.queued_wake ||
            i_runtime_wakeup_required === 1'b1;
        assign o_wakeup_ack = wake_ack;
        assign o_state_valid = q.state_valid && !q.fatal && !integrity_bad;
        assign o_test_active = q.state == CPM_TEST;
        assign o_idle = q.state == CPM_IDLE_ON || q.state == CPM_CLOCK_GATED;
        assign o_quiescent = reset_b && stable_state && !command_slot.valid &&
            !response_slot.valid && events_empty && !q.request_active && q.wakes == 0 &&
            !q.queued_wake && !q.fatal && !integrity_bad && !test_requested &&
            i_runtime_wakeup_required === 1'b0;
        assign o_revalidate_valid = reset_b && q.request_active && !q.request_sent && (!q.fatal ||
            q.recovering);
        assign o_revalidate_record = q.request;
        assign o_revalidate_response_ready = reset_b;
        assign validation_response = i_revalidate_response_record;

        always @* begin : normalized_input
            live_identity = '0;
            live_identity.cluster_id = 8'(CLUSTER_ID);

            if (i_cluster_allocated === 1'b1) begin
                live_identity.owner_id = i_allocation_owner_id;
                live_identity.kernel_id = i_allocation_kernel_id;
                live_identity.package_id = i_allocation_package_id;
                live_identity.allocation_generation = i_allocation_generation;
                live_identity.epoch = i_execution_epoch;
            end

            incoming = '0;
            incoming.identity.cluster_id = i_command_cluster_id;
            incoming.identity.owner_id = i_command_owner_id;
            incoming.identity.kernel_id = i_command_kernel_id;
            incoming.identity.package_id = i_command_package_id;
            incoming.identity.allocation_generation = i_command_allocation_generation;
            incoming.identity.epoch = i_command_execution_epoch;
            incoming.command = i_command;
            incoming.target = i_command_target_state;
            incoming.point = i_command_operating_point;
            incoming.expected_idle = i_command_expected_idle_cycles;
            incoming.state_policy = i_command_state_policy_id;
            incoming.flags = i_command_flags;
            incoming.tag = i_command_tag;
        end

        function automatic command_t known_command(input logic [$bits(command_t)-1:0] value);
            logic [$bits(command_t)-1:0] sanitized;

            for (int b = 0; b < $bits(command_t); b++) sanitized[b] = value[b] === 1'b1;

            return sanitized;
        endfunction

        function automatic logic [7:0] command_error(input command_t value);
            if (^value === 1'bx) return ERR_UNKNOWN;

            if (i_command_authorized !== 1'b1) return ERR_AUTHORITY;

            if (value.command != CP_QUERY && value.command != CP_CLEAR_ERROR && !authority)
                return ERR_AUTHORITY;

            if (!identity_known || value.identity != live_identity) return ERR_IDENTITY;

            if (value.point != 0 || value.state_policy != 0 || value.flags[15:3] != 0)
                return ERR_UNSUPPORTED;

            if ((value.flags[2:0] != 0) && i_system_privileged !== 1'b1) return ERR_AUTHORITY;

            if (test_requested || q.state == CPM_TEST) return ERR_TEST;

            if (q.fatal && value.command != CP_QUERY && value.command != CP_RECOVER)
                return ERR_COMMAND;

            case (value.command)
                CP_QUERY: return ERR_NONE;
                CP_CLEAR_ERROR: return q.fatal ? ERR_COMMAND : ERR_NONE;
                CP_RECOVER: begin
                    if (value.target != CPM_IDLE_ON ||
                        (i_cluster_allocated && (!value.flags[2] ||
                        i_array_execution_hold !== 1'b1))) return ERR_AUTHORITY;
                    return ERR_NONE;
                end
                CP_RUN: begin
                    if (value.target != CPM_ACTIVE) return ERR_COMMAND;
                    if (q.state == CPM_CLOCK_GATED && q.residency < policy.min_residency &&
                        !value.flags[0]) return ERR_RESIDENCY;
                end
                CP_IDLE_ON: if (value.target != CPM_IDLE_ON) return ERR_COMMAND;
                CP_CLOCK_GATE: if (value.target != CPM_CLOCK_GATED) return ERR_COMMAND;
                default: return ERR_UNSUPPORTED;
            endcase

            if (((policy.states >> value.target) & 32'b1) == 0) return ERR_POLICY;
            return ERR_NONE;
        endfunction

        function automatic event_t make_event(input logic [3:0] kind,
            input logic [2:0] status, input logic [7:0] error);
            event_t event_record;
            event_record = '0;
            event_record.identity = q.identity;
            event_record.boot_generation = q.boot_generation;
            event_record.timestamp = time_value;
            event_record.old_state = q.state;
            event_record.target_state = d.target;
            event_record.phase = d.phase;
            event_record.status = status;
            event_record.error = error;
            event_record.tag = command_slot.valid ? command_slot.value.tag : 16'b0;
            event_record.kind = kind;

            return event_record;
        endfunction

        function automatic response_t make_response(input command_t value,
            input logic [2:0] status, input logic [7:0] error, input logic [4:0] state,
            input logic [63:0] cycles);
            response_t result;
            result = '0;
            result.identity = value.identity;
            result.command = value.command;
            result.tag = value.tag;
            result.status = status;
            result.error = error;
            result.state = state;
            result.cycles = cycles > 64'hffffffff ? 32'hffffffff : 32'(cycles);

            return result;
        endfunction

        always @* begin : acknowledgement_view
            expected_ack = 0;
            observed_ack = 0;

            case (q.phase)
                PH_POWER: begin
                    expected_ack = (64'b1 << P) - 1;
                    observed_ack = 64'(power_good & switches);
                end
                PH_CLOCK: begin
                    expected_ack = 7;
                    observed_ack = {61'b0, voltage_ready === 1'b1,
                        clock_ready === 1'b1, clock_stopped === 1'b0};
                end
                PH_RESET_HOLD, PH_RESET_RELEASE: begin
                    expected_ack = 64'(controls.resets);
                    observed_ack = 64'(reset_ack);
                end
                PH_TILE_CONFIG: begin
                    expected_ack = (64'b1 << T) - 1;
                    observed_ack = 64'(q.configured);
                end
                PH_TILE_RUN, PH_TILE_IDLE: begin
                    expected_ack = (64'b1 << T) - 1;
                    observed_ack = 64'(q.tile_done);
                end
                PH_DEISOLATE, PH_TEST_ISOLATE: begin
                    expected_ack = 64'(controls.isolation);
                    observed_ack = 64'(isolation_ack);
                end
                PH_ENDPOINT_ENABLE, PH_ENDPOINT_DISABLE: begin
                    expected_ack = 64'(controls.endpoints);
                    observed_ack = 64'(endpoints_ack);
                end
                PH_CLOCK_STOP: begin
                    expected_ack = 1;
                    observed_ack = clock_stopped === 1'b1 ? 1 : 0;
                end
                PH_DRAIN: begin
                    expected_ack = 1;
                    observed_ack = drained ? 1 : 0;
                end
                default: begin end
            endcase
        end

        // d and controls_d are committed together on the AON edge. Physical
        // outputs use the independent control registers, never a raw state decode.
        always @* begin : sequence_control
            logic [7:0] error;
            logic [7:0] fault;
            logic [31:0] timeout_limit;
            logic [W-1:0] captured;
            logic [T-1:0] sent;
            logic [T-1:0] done;
            bit complete;
            bit phase_ack;
            bit timed_out;
            bit mandatory_wake;
            bit ordinary_wake;
            bit begin_wake;
            bit begin_drain;
            bit controls_known;
            bit transition_identity_bad;
            int group_index;
            d = q;
            controls_d = controls;
            policy_d = policy;
            command_d = command_slot;
            response_d = response_slot;
            normal_push = 0;
            terminal_push = 0;
            fatal_push = 0;
            normal_event = '0;
            terminal_event = '0;
            fatal_event = '0;
            cancel_accepted = 0;
            cancel_rejected = 0;
            config_accepted = 0;
            config_rejected = 0;
            config_error = ERR_NONE;
            wake_ack = 0;
            consumed_wakes = '0;
            statistics = '0;
            statistics[30] = q.fatal;
            statistics[31] = state_corrected || policy_corrected ||
                command_corrected || response_corrected;
            error = ERR_NONE;
            fault = ERR_NONE;
            timeout_limit = 0;
            captured = '0;
            sent = q.tile_sent;
            done = q.tile_done;
            complete = 0;
            phase_ack = 0;
            timed_out = 0;
            mandatory_wake = i_runtime_wakeup_required === 1'b1 || q.queued_wake || test_requested;
            ordinary_wake = 0;
            begin_wake = 0;
            begin_drain = 0;
            group_index = 0;
            controls_known = ^{i_array_execution_hold, i_array_transition_authorized,
                i_system_transition_authorized, i_runtime_wakeup_required, i_fault_excluded,
                i_cluster_busy, i_cluster_quiescent, i_cluster_drain_done, i_tile_busy_mask,
                i_tile_quiescent_mask, i_tile_drain_done_mask, i_tile_stall_reason, i_stall_reason,
                i_clock_group_request, i_scratchpad_idle, i_memory_boundary_idle,
                    i_local_network_idle,
                i_event_idle, i_configuration_idle, i_counter_snapshot_idle, i_debug_idle,
                i_global_endpoint_drained, i_boundary_drained, i_test_mode, i_scan_enable,
                i_mbist_enable, i_test_clock_enable, i_test_authorized} !== 1'bx;
            transition_identity_bad = q.phase != PH_NONE && q.state != CPM_RESET &&
                (live_identity !== q.identity || i_system_reset_generation !== q.boot_generation);

            if (reset_b) begin
                if (response_fire) begin
                    response_d.valid = 0;
                    command_d.valid = 0;
                end

                if (!(&q.residency)) d.residency = q.residency + 1'b1;

                if (q.phase != PH_NONE && !(&q.timer)) d.timer = q.timer + 1'b1;

                d.test_requested = test_requested;

                if (i_wakeup_identity === q.identity && identity_known) begin
                    for (int w = 0; w < W; w++)
                        if (i_wakeup_event[w] === 1'b1 &&
                            ((policy.wakes >> w) & 1'b1) != 0) captured[w] = 1;
                end

                if ((^i_wakeup_event === 1'bx || (|i_wakeup_event)) && captured == 0) begin
                    normal_push = 1;
                    normal_event = make_event(EV_BAD_WAKE, STATUS_REJECTED, ERR_IDENTITY);
                    statistics[29] = 1;
                end

                d.wakes = q.wakes | captured;
                ordinary_wake = d.wakes != 0;

                if (i_cancel_valid === 1'b1 && o_cancel_ready) begin
                    if (i_cancel_identity === command_slot.value.identity &&
                        i_cancel_tag === command_slot.value.tag) begin
                        d.cancel_seen = 1;
                        cancel_accepted = 1;

                        if (q.irreversible) d.queued_wake = 1;
                        else d.cancel = 1;
                    end else cancel_rejected = 1;
                end

                if (i_config_valid === 1'b1 && o_config_ready) begin
                    normal_push = 1;
                    normal_event = make_event(EV_POLICY, STATUS_OK, ERR_NONE);

                    if (^{i_config_auto_clock_gate, i_config_owner_check, i_config_break_even,
                        i_config_idle_entry_cycles, i_config_min_gated_residency,
                        i_config_wake_enable, i_config_allowed_states, i_config_allowed_points}
                        === 1'bx) config_error = ERR_UNKNOWN;
                    else if ((!AUTO_CLOCK_GATE_ENABLE && i_config_auto_clock_gate) ||
                        !i_config_owner_check || i_config_idle_entry_cycles == 0 ||
                        i_config_min_gated_residency == 0 || !i_config_allowed_points ||
                        (i_config_allowed_states & ~capabilities) != 0 ||
                        (i_config_allowed_states & (32'b1 << q.state)) == 0)
                        config_error = ERR_POLICY;

                    if (config_error != ERR_NONE) begin
                        config_rejected = 1;
                        normal_event.status = STATUS_REJECTED;
                        normal_event.error = config_error;
                    end else begin
                        policy_d.automatic_gate = i_config_auto_clock_gate;
                        policy_d.idle_threshold = i_config_idle_entry_cycles;
                        policy_d.min_residency = i_config_min_gated_residency;
                        policy_d.wakes = i_config_wake_enable;
                        policy_d.states = i_config_allowed_states;
                        config_accepted = 1;
                        d.idle_count = 0;
                    end
                end

                case (q.phase)
                    PH_NONE: begin
                        d.timer = 0;
                        d.qualification = 0;

                        if (q.state == CPM_RESET) begin
                            d.identity = live_identity;
                            d.boot_generation = i_system_reset_generation;
                            d.target = CPM_IDLE_ON;
                            d.phase = PH_POWER;
                            d.reload = 1;
                            d.start_time = time_value;
                            controls_d = safe_controls();
                        end else if (q.state == CPM_TEST) begin
                            controls_d.root = i_test_clock_enable === 1'b1 && physical_power &&
                                physical_clock;
                            controls_d.groups = controls_d.root ? {G{1'b1}} : '0;

                            if (!test_requested) begin
                                d.state = CPM_REINITIALIZING;
                                d.phase = PH_RESET_HOLD;
                                d.target = CPM_IDLE_ON;
                                d.reload = 1;
                                d.start_time = time_value;
                                controls_d.root = 1;
                                controls_d.groups = '1;
                                controls_d.resets = '1;
                                controls_d.tile_reset = 0;
                            end
                        end else if (q.state != CPM_ERROR) begin
                            if (live_identity !== q.identity && quiet &&
                                i_array_execution_hold === 1'b1 && identity_known) begin
                                d.identity = live_identity;
                                d.run_authorized = 0;

                                if (q.state != CPM_CLOCK_GATED) d.state = CPM_IDLE_ON;

                                d.state_valid = 0;
                                d.wakes = 0;
                            end

                            if (q.state == CPM_CLOCK_GATED) begin
                                if ((mandatory_wake || (ordinary_wake &&
                                    q.residency >= policy.min_residency)) && authority)
                                    begin_wake = 1;
                            end else if (test_requested && i_test_authorized === 1'b1 &&
                                i_array_execution_hold === 1'b1 && authority && terminal_capacity)
                                    begin
                                d.target = CPM_TEST;
                                begin_drain = 1;
                            end else if ((mandatory_wake || ordinary_wake) && authority) begin
                                if (q.state == CPM_IDLE_ON && !q.run_authorized) begin_wake = 1;
                                else begin
                                    consumed_wakes = d.wakes;
                                    d.wakes = captured;
                                    wake_ack = 1;
                                end
                            end else if (!command_fire && !config_accepted &&
                                i_config_valid === 1'b0) begin
                                if (q.run_authorized && i_cluster_busy === 1'b1)
                                    d.state = (|i_stall_reason) ? CPM_STALLED : CPM_ACTIVE;
                                else if (quiet) d.state = CPM_IDLE_ON;

                                if (d.state == CPM_IDLE_ON && policy.automatic_gate && quiet &&
                                    i_cluster_drain_done === 1'b1 &&
                                    i_tile_drain_done_mask === {T{1'b1}} && authority &&
                                    i_array_execution_hold === 1'b0 && !response_slot.valid &&
                                    terminal_capacity && normal_ready && !test_requested &&
                                    q.state_valid && q.identity === live_identity &&
                                    ((policy.states >> CPM_CLOCK_GATED) & 32'b1) != 0) begin

                                    if (q.idle_count >= policy.idle_threshold - 1'b1) begin
                                        d.target = CPM_CLOCK_GATED;
                                        begin_drain = 1;
                                    end else d.idle_count = q.idle_count + 1'b1;
                                end else d.idle_count = 0;
                            end
                        end
                    end
                    PH_POWER: begin
                        timeout_limit = 32'(POWER_TIMEOUT_CYCLES);
                        phase_ack = physical_power;

                        if (phase_ack && q.qualification >= 32'(POWER_STABLE_CYCLES) - 1) begin
                            d.power_qualified = 1;
                            d.phase = PH_CLOCK;
                            d.state = CPM_CLOCK_STARTING;
                            controls_d.root = 1;
                            controls_d.groups = '1;
                            controls_d.tile_reset = 0;
                        end
                    end
                    PH_CLOCK: begin
                        timeout_limit = 32'(CLOCK_TIMEOUT_CYCLES);
                        phase_ack = physical_clock && clock_stopped === 1'b0;

                        if (phase_ack && q.qualification >= 32'(CLOCK_STABLE_CYCLES) - 1) begin
                            d.clock_qualified = 1;

                            if (q.reload) begin
                                d.phase = PH_RESET_HOLD;
                                d.state = CPM_REINITIALIZING;
                                controls_d.resets = '1;
                            end else begin
                                d.phase = PH_TILE_CONFIG;
                                d.configured = 0;
                            end
                        end
                    end
                    PH_RESET_HOLD: begin
                        timeout_limit = 32'(CLOCK_TIMEOUT_CYCLES);
                        phase_ack = reset_ack === {R{1'b1}};

                        if (phase_ack && q.qualification >= 32'(RESET_HOLD_CYCLES) - 1) begin
                            d.phase = PH_RESET_RELEASE;
                            d.reset_index = 0;
                            controls_d.resets = controls.resets & ~R'(1);
                        end
                    end
                    PH_RESET_RELEASE: begin
                        timeout_limit = 32'(CLOCK_TIMEOUT_CYCLES);
                        phase_ack = reset_ack === controls.resets &&
                            functional_rstb === ~controls.resets;

                        if (phase_ack && q.qualification >= 32'(PHYSICAL_ACK_STABLE_CYCLES) - 1)
                            begin
                            d.qualification = 0;

                            if (q.reset_index == 8'(R - 1)) begin
                                d.phase = PH_TILE_CONFIG;
                                d.configured = 0;
                            end else begin
                                d.reset_index = q.reset_index + 1'b1;
                                controls_d.resets = controls.resets & ~(R'(1) << d.reset_index);
                            end
                        end
                    end
                    PH_TILE_CONFIG: begin
                        timeout_limit = 32'(TILE_ACK_TIMEOUT_CYCLES);
                        d.configured = q.configured | (tile_config_valid & tile_config_ready);
                        phase_ack = &d.configured;

                        if (phase_ack) begin
                            d.phase = PH_TILE_RUN;
                            d.tile_sent = 0;
                            d.tile_done = 0;
                        end
                    end
                    PH_TILE_RUN, PH_TILE_IDLE: begin
                        timeout_limit = 32'(TILE_ACK_TIMEOUT_CYCLES);
                        sent = q.tile_sent | (tile_valid & tile_ready);
                        done = q.tile_done | (tile_done & (sent | q.tile_sent));
                        d.tile_sent = sent;
                        d.tile_done = done;
                        phase_ack = (&sent) && (&done);

                        if (phase_ack) begin
                            if (q.phase == PH_TILE_RUN) begin
                                d.phase = PH_VALIDATE;
                            end else if (d.cancel && !q.irreversible) begin
                                d.outcome = STATUS_ROLLED_BACK;
                                d.outcome_error = ERR_CANCELED;
                                d.target = q.previous;
                                begin_wake = 1;
                            end else if (q.target == CPM_TEST) begin
                                controls_d.isolation = '1;
                                controls_d.resets = '1;
                                controls_d.groups = '1;
                                d.phase = PH_TEST_ISOLATE;
                            end else if (q.target == CPM_IDLE_ON) d.phase = PH_VALIDATE;
                            else begin
                                controls_d.root = 0;
                                controls_d.groups = 0;
                                d.irreversible = 1;
                                d.phase = PH_CLOCK_STOP;
                            end
                        end
                    end
                    PH_VALIDATE: begin
                        timeout_limit = 32'(RELOAD_TIMEOUT_CYCLES);

                        if (!q.request_active) begin
                            if (q.serial == 16'hffff) fault = ERR_EXHAUSTED;
                            else begin
                                d.request_active = 1;
                                d.request_sent = 0;
                                d.serial = q.serial + 1'b1;
                                d.request = '0;
                                d.request.identity = q.identity;
                                d.request.boot_generation = q.boot_generation;
                                d.request.serial = d.serial;
                                d.request.tag = command_slot.valid ? command_slot.value.tag : 16'b0;
                                d.request.reload = q.reload;
                            end
                        end

                        if (o_revalidate_valid && i_revalidate_ready === 1'b1) d.request_sent = 1;

                        if (i_revalidate_response_valid === 1'b1 && q.request_active &&
                            (q.request_sent || (o_revalidate_valid && i_revalidate_ready === 1'b1))
                                &&
                            validation_response.identity === q.request.identity &&
                            validation_response.boot_generation === q.request.boot_generation &&
                            validation_response.serial === q.request.serial &&
                            validation_response.tag === q.request.tag) begin
                            if (validation_response.status !== 2'b00 ||
                                validation_response.validity !== 4'hf) fault =
                                    ERR_REVALIDATE_FAILED;
                            else begin
                                d.request_active = 0;
                                d.request_sent = 0;
                                d.state_valid = 1;
                                d.phase = PH_ISOLATION_HOLD;
                            end
                        end
                    end
                    PH_ISOLATION_HOLD: begin
                        phase_ack = 1;

                        if (q.qualification >= 32'(ISOLATION_HOLD_CYCLES) - 1) begin
                            controls_d.isolation = 0;
                            d.phase = PH_DEISOLATE;
                        end
                    end
                    PH_DEISOLATE: begin
                        timeout_limit = 32'(DRAIN_TIMEOUT_CYCLES);
                        phase_ack = isolation_ack === {I{1'b0}};

                        if (phase_ack && q.qualification >= 32'(PHYSICAL_ACK_STABLE_CYCLES) - 1)
                            begin
                            controls_d.endpoints = '1;
                            d.phase = PH_ENDPOINT_ENABLE;
                        end
                    end
                    PH_ENDPOINT_ENABLE: begin
                        timeout_limit = 32'(DRAIN_TIMEOUT_CYCLES);
                        phase_ack = endpoints_ack === {E{1'b1}} && sram_ack === {S{1'b1}};

                        if (phase_ack && q.qualification >= 32'(PHYSICAL_ACK_STABLE_CYCLES) - 1)
                            begin
                            d.phase = PH_STABILIZE;
                            d.state = CPM_WAKEUP;
                        end
                    end
                    PH_STABILIZE: begin
                        phase_ack = physical_power && physical_clock && authority &&
                            i_array_execution_hold === 1'b0;

                        // IDLE_ON and test recovery can finish under the array hold.
                        if (q.target == CPM_IDLE_ON) phase_ack = physical_power && physical_clock &&
                            authority;

                        timeout_limit = 32'(DRAIN_TIMEOUT_CYCLES);

                        if (phase_ack && q.qualification >= 32'(WAKEUP_STABILIZE_CYCLES) - 1 &&
                            terminal_ready) begin
                            d.state = q.target == CPM_ACTIVE || q.target == CPM_STALLED ?
                                q.target : CPM_IDLE_ON;
                            d.run_authorized = d.state == CPM_ACTIVE || d.state == CPM_STALLED;
                            d.recovering = 0;
                            d.fatal = 0;
                            complete = 1;
                        end
                    end
                    PH_DRAIN: begin
                        timeout_limit = 32'(DRAIN_TIMEOUT_CYCLES);
                        phase_ack = drained;

                        if (d.cancel && !q.irreversible) begin
                            d.state = q.previous;
                            d.outcome = STATUS_ROLLED_BACK;
                            d.outcome_error = ERR_CANCELED;
                            complete = 1;
                        end else if (phase_ack) begin
                            controls_d.endpoints = 0;
                            controls_d.operand = 1;
                            controls_d.write_disable = 1;
                            d.phase = PH_ENDPOINT_DISABLE;
                        end
                    end
                    PH_ENDPOINT_DISABLE: begin
                        timeout_limit = 32'(DRAIN_TIMEOUT_CYCLES);
                        phase_ack = endpoints_ack === {E{1'b0}};

                        if (phase_ack && q.qualification >= 32'(PHYSICAL_ACK_STABLE_CYCLES) - 1)
                            begin
                            d.phase = PH_TILE_IDLE;
                            d.tile_sent = 0;
                            d.tile_done = 0;
                        end
                    end
                    PH_CLOCK_STOP: begin
                        timeout_limit = 32'(CLOCK_TIMEOUT_CYCLES);
                        phase_ack = clock_stopped === 1'b1;
                        if (phase_ack && q.qualification >= 32'(PHYSICAL_ACK_STABLE_CYCLES) - 1 &&
                            terminal_ready) begin
                            d.state = CPM_CLOCK_GATED;
                            complete = 1;
                        end
                    end
                    PH_TEST_ISOLATE: begin
                        timeout_limit = 32'(DRAIN_TIMEOUT_CYCLES);
                        phase_ack = isolation_ack === {I{1'b1}} && reset_ack === {R{1'b1}} &&
                            endpoints_ack === {E{1'b0}};

                        if (phase_ack && q.qualification >= 32'(ISOLATION_SETUP_CYCLES) - 1 &&
                            terminal_ready) begin
                            d.state = CPM_TEST;
                            d.state_valid = 0;
                            d.run_authorized = 0;
                            complete = 1;
                        end
                    end
                    default: fault = ERR_UNKNOWN;
                endcase
                if (command_fire) begin
                    if (!test_requested) begin
                        begin_wake = 0;
                        begin_drain = 0;
                    end

                    command_d.valid = 1;
                    command_d.value = known_command(incoming);
                    error = command_error(incoming);
                    statistics[27] = 1;
                    normal_push = 1;
                    normal_event = make_event(EV_ACCEPTED, STATUS_OK, ERR_NONE);
                    normal_event.identity = command_d.value.identity;
                    normal_event.tag = command_d.value.tag;

                    if (error != ERR_NONE) begin
                        statistics[28] = 1;
                        response_d.valid = 1;
                        response_d.value = make_response(command_d.value, STATUS_REJECTED,
                            error, q.state, 0);
                        normal_event.kind = EV_REJECTED;
                        normal_event.status = STATUS_REJECTED;
                        normal_event.error = error;
                        terminal_push = 1;
                        terminal_event = normal_event;
                        terminal_event.kind = EV_COMPLETE;
                    end else if (incoming.command == CP_QUERY ||
                        incoming.command == CP_CLEAR_ERROR ||
                        (incoming.command == CP_RUN && q.state_valid &&
                        q.identity === live_identity && (q.state == CPM_ACTIVE ||
                        q.state == CPM_STALLED)) || (incoming.command == CP_CLOCK_GATE &&
                        q.state == CPM_CLOCK_GATED) || (incoming.command == CP_IDLE_ON &&
                        q.state == CPM_IDLE_ON)) begin
                        if (incoming.command == CP_CLEAR_ERROR) begin
                            d.first_error = ERR_NONE;
                            d.first_phase = 0;
                            d.first_tag = 0;
                            d.first_time = 0;
                        end

                        if (incoming.command == CP_RUN) begin
                            d.state = CPM_ACTIVE;
                            d.run_authorized = 1;
                        end

                        response_d.valid = 1;
                        response_d.value = make_response(command_d.value, STATUS_OK,
                            ERR_NONE, d.state, 0);
                        terminal_push = 1;
                        terminal_event = make_event(EV_COMPLETE, STATUS_OK, ERR_NONE);
                        terminal_event.identity = command_d.value.identity;
                        terminal_event.tag = command_d.value.tag;
                    end else begin
                        d.cancel = 0;
                        d.cancel_seen = 0;
                        d.outcome = STATUS_OK;
                        d.outcome_error = ERR_NONE;
                        d.previous = q.state;
                        d.start_time = time_value;
                        d.target = incoming.target;

                        if (incoming.command == CP_RECOVER) begin
                            d.recovering = 1;
                            d.state = CPM_RESET;
                            d.phase = PH_POWER;
                            d.identity = live_identity;
                            d.boot_generation = i_system_reset_generation;
                            d.reload = 1;
                            d.power_qualified = 0;
                            d.clock_qualified = 0;
                            d.state_valid = 0;
                            d.request_active = 0;
                            d.request_sent = 0;
                            controls_d = safe_controls();
                        end else if (incoming.command == CP_RUN || q.state == CPM_CLOCK_GATED)
                            begin_wake = 1;
                        else begin_drain = 1;
                    end
                end

                if (begin_wake) begin
                    d.previous = q.state;
                    d.start_time = time_value;
                    d.phase = PH_CLOCK;
                    d.state = CPM_CLOCK_STARTING;
                    d.reload = 0;
                    d.request_active = 0;
                    d.request_sent = 0;
                    d.configured = 0;

                    if (!command_slot.valid && !command_fire) d.target = CPM_ACTIVE;

                    if (q.test_requested || test_requested) d.target = CPM_IDLE_ON;

                    controls_d.root = 1;
                    controls_d.groups = '1;
                    controls_d.accept_work = 0;
                    controls_d.hold_execution = 1;
                    controls_d.injection = 0;
                    controls_d.endpoints = 0;
                    controls_d.drain = 0;
                    controls_d.operand = 1;
                    controls_d.write_disable = 1;
                    controls_d.tile_reset = 0;

                    if (q.phase == PH_NONE) begin
                        d.outcome = STATUS_OK;
                        d.outcome_error = ERR_NONE;
                    end

                    consumed_wakes = d.wakes;
                    d.wakes = captured;
                    d.queued_wake = 0;
                    wake_ack = 1;
                    statistics[24] = 1;
                end

                if (begin_drain) begin
                    d.previous = q.state;
                    d.start_time = time_value;
                    d.phase = PH_DRAIN;
                    d.state = CPM_DRAINING;
                    d.idle_count = 0;
                    d.cancel = 0;
                    d.cancel_seen = 0;
                    d.irreversible = 0;
                    d.outcome = STATUS_OK;
                    d.outcome_error = ERR_NONE;
                    d.request_active = 0;
                    controls_d.accept_work = 0;
                    controls_d.hold_execution = 1;
                    controls_d.injection = 0;
                    controls_d.drain = 1;
                    controls_d.root = 1;
                    controls_d.groups = '1;
                    // Existing work retires during DRAIN; mutation is suppressed
                    // only once all subsystems have acknowledged quiescence.
                    controls_d.operand = 0;
                    controls_d.write_disable = 0;
                end

                if (q.phase != PH_NONE) begin
                    if (phase_ack && !(&q.qualification))
                        d.qualification = q.qualification + 1'b1;
                    else if (!phase_ack) d.qualification = 0;

                    timed_out = timeout_limit != 0 && q.timer >= timeout_limit - 1'b1 &&
                        d.phase == q.phase && !complete;

                    if (timed_out) begin
                        statistics[25] = 1;

                        case (q.phase)
                            PH_DRAIN: error = ERR_DRAIN_TIMEOUT;
                            PH_TILE_CONFIG, PH_TILE_RUN, PH_TILE_IDLE: error = ERR_TILE_TIMEOUT;
                            PH_POWER: error = ERR_POWER_TIMEOUT;
                            PH_CLOCK, PH_CLOCK_STOP: error = ERR_CLOCK_TIMEOUT;
                            PH_RESET_HOLD, PH_RESET_RELEASE: error = ERR_RESET_TIMEOUT;
                            PH_VALIDATE: error = ERR_REVALIDATE_TIMEOUT;
                            PH_DEISOLATE, PH_TEST_ISOLATE: error = ERR_ISOLATION_TIMEOUT;
                            default: error = ERR_ENDPOINT_TIMEOUT;
                        endcase

                        if (q.phase == PH_DRAIN && SUPPORT_ROLLBACK) begin
                            d.state = q.previous;
                            d.outcome = STATUS_ROLLED_BACK;
                            d.outcome_error = error;
                            complete = terminal_ready;
                            statistics[26] = complete;
                        end else fault = error;
                    end
                end

                if (complete) begin
                    d.phase = PH_NONE;
                    d.request_active = 0;
                    d.request_sent = 0;
                    d.irreversible = 0;
                    d.cancel = 0;
                    controls_d.drain = 0;
                    terminal_push = 1;
                    terminal_event = make_event(EV_COMPLETE, d.outcome, d.outcome_error);
                    statistics[23] = 1;

                    if (command_slot.valid && !response_slot.valid) begin
                        response_d.valid = 1;
                        response_d.value = make_response(command_slot.value, d.outcome,
                            d.outcome_error, d.state, time_value - q.start_time);
                    end
                end

                // Stable controls are generated from the reached state. Test has
                // a separate declared output row and never exposes functional work.
                if (d.phase == PH_NONE) begin
                    case (d.state)
                        CPM_ACTIVE, CPM_STALLED, CPM_IDLE_ON: begin
                            controls_d.root = 1;
                            controls_d.groups = i_clock_group_request;

                            for (int t = 0; t < T; t++) begin
                                group_index = int'(TILE_CLOCK_GROUP_TABLE[t*TG+:TG]);

                                if (tile_groups[t] || i_tile_busy_mask[t] === 1'b1 ||
                                    i_tile_quiescent_mask[t] !== 1'b1)
                                    controls_d.groups = controls_d.groups | (G'(1) << group_index);
                            end

                            controls_d.isolation = 0;
                            controls_d.resets = 0;
                            controls_d.tile_reset = 0;
                            controls_d.endpoints = d.state_valid ? {E{1'b1}} : '0;
                            controls_d.accept_work = d.run_authorized &&
                                (d.state == CPM_ACTIVE || d.state == CPM_STALLED) && authority &&
                                i_array_execution_hold === 1'b0 && !test_requested && d.state_valid;
                            controls_d.hold_execution = !controls_d.accept_work;
                            controls_d.injection = controls_d.accept_work ? {E{1'b1}} : '0;
                            controls_d.operand = !controls_d.accept_work;
                            controls_d.write_disable = !controls_d.accept_work;
                        end
                        CPM_CLOCK_GATED: begin
                            controls_d.root = 0;
                            controls_d.groups = 0;
                            controls_d.accept_work = 0;
                            controls_d.hold_execution = 1;
                            controls_d.endpoints = 0;
                            controls_d.injection = 0;
                            controls_d.isolation = 0;
                            controls_d.resets = 0;
                            controls_d.operand = 1;
                            controls_d.write_disable = 1;
                        end
                        CPM_TEST: begin
                            controls_d = safe_controls();
                            controls_d.tile_reset = 0;
                            controls_d.root = i_test_clock_enable === 1'b1 && physical_power &&
                                physical_clock;
                            controls_d.groups = controls_d.root ? {G{1'b1}} : '0;
                        end
                        default: begin end
                    endcase
                end

                // Priority: registered physical emergencies and integrity errors,
                // timeout containment, then functional sequencing. Raw asynchronous
                // status never drives these requests or a clock directly.
                if (q.phase == PH_NONE && q.state != CPM_RESET && q.state != CPM_ERROR &&
                    !physical_clock) fault = ERR_CLOCK_LOSS;

                if (stable_state && q.state_valid && !q.fatal &&
                    (q.state == CPM_ACTIVE || q.state == CPM_STALLED ||
                    q.state == CPM_IDLE_ON || q.state == CPM_CLOCK_GATED)) begin

                    if (isolation_ack !== controls.isolation || reset_ack !== controls.resets ||
                        endpoints_ack !== controls.endpoints || sram_ack !== {S{1'b1}})
                        fault = ERR_PHYSICAL_ACK;

                    if (clock_stopped !== !controls.root) fault = ERR_CLOCK_LOSS;
                end

                if (save_ack !== {H{1'b0}} || restore_ack !== {H{1'b0}}) begin
                    if (error == ERR_NONE) error = ERR_PHYSICAL_ACK;
                end

                if (q.state != CPM_RESET && q.state != CPM_ERROR && !physical_power)
                    fault = ERR_POWER_LOSS;

                if (thermal === 1'b1) fault = ERR_THERMAL;

                if (voltage_fault === 1'b1) fault = ERR_VOLTAGE_FAULT;

                if (clock_fault === 1'b1) fault = ERR_CLOCK_LOSS;

                if (!controls_known && q.state != CPM_RESET) fault = ERR_UNKNOWN;

                if (!identity_known || transition_identity_bad) fault = ERR_IDENTITY;

                if (test_requested && (i_test_authorized !== 1'b1 ||
                    i_array_execution_hold !== 1'b1 || !authority)) fault = ERR_TEST;

                if ((q.phase == PH_TILE_RUN || q.phase == PH_TILE_IDLE) &&
                    (|tile_rejected)) fault = ERR_TILE_REJECT;

                if (!controls.tile_reset && (|tile_error)) fault = ERR_TILE_REJECT;

                if (integrity_bad) fault = ERR_INTEGRITY;

                if (time_overflow || events_exhausted) fault = ERR_EXHAUSTED;

                if (fault != ERR_NONE) begin
                    // An uncorrectable record cannot supply containment metadata.
                    // Rebuild only from known live identity and safe constants.
                    if (state_bad || policy_bad || controls_bad) begin
                        d = '0;
                        d.identity = identity_known ? live_identity : '0;
                        d.boot_generation = ^i_system_reset_generation === 1'bx ?
                            16'b0 : i_system_reset_generation;
                    end

                    d.state = CPM_ERROR;
                    d.phase = PH_NONE;
                    d.fatal = 1;
                    d.recovering = 0;
                    d.state_valid = 0;
                    d.run_authorized = 0;
                    d.request_active = 0;
                    d.request_sent = 0;
                    controls_d = safe_controls();

                    if (!q.fatal || state_bad) begin
                        fatal_push = 1;
                        fatal_event = '0;
                        fatal_event.kind = EV_FATAL;
                        fatal_event.status = STATUS_ERROR;
                        fatal_event.error = fault;
                        fatal_event.old_state = state_bad ? CPM_ERROR : q.state;
                        fatal_event.target_state = CPM_ERROR;
                        fatal_event.phase = state_bad ? PH_NONE : q.phase;
                        fatal_event.timestamp = time_value;
                        fatal_event.boot_generation = d.boot_generation;
                        fatal_event.identity = identity_known ? live_identity : '0;
                        fatal_event.tag = command_d.valid ? command_d.value.tag : 16'b0;
                    end

                    if (command_d.valid && !response_slot.valid && !command_bad && !response_bad)
                        begin
                        response_d.valid = 1;
                        response_d.value = make_response(command_d.value,
                            timed_out ? STATUS_TIMEOUT : STATUS_ERROR, fault, CPM_ERROR,
                            time_value - q.start_time);
                    end

                    error = fault;

                    if (integrity_bad) normal_push = 0;

                    terminal_push = 0;
                end

                if (error != ERR_NONE && d.first_error == ERR_NONE) begin
                    d.first_error = error;
                    d.first_phase = state_bad ? PH_NONE : q.phase;
                    d.first_tag = command_d.valid ? command_d.value.tag : 16'b0;
                    d.first_time = time_value;
                    d.first_expected = expected_ack;
                    d.first_observed = observed_ack;
                end

                if (d.phase != q.phase) begin
                    d.timer = 0;
                    d.qualification = 0;

                    if (!normal_push && !integrity_bad) begin
                        normal_push = 1;
                        normal_event = make_event(EV_PHASE, STATUS_OK, ERR_NONE);
                    end
                end

                if (q.phase == PH_RESET_RELEASE && controls_d.resets != controls.resets) begin
                    d.timer = 0;
                    d.qualification = 0;
                end

                if (d.state != q.state) d.residency = 0;

                if (q.state == CPM_RESET || q.state == CPM_ERROR) d.idle_count = 0;

                if (q.phase != PH_NONE && !q.cancel && !q.cancel_seen) d.idle_count = 0;

                d.witness = controls_d;
            end
        end

        decoder #(
            .NUM_OUTPUTS(32)
        ) u_state_events (
            .i_enable(1'b1),
            .i_select(q.state),
            .o_decoded(state_onehot),
            .o_select_valid(state_select_valid)
        );

        if (ENABLE_COUNTERS) begin : g_counters
            performance_counters #(
                .COUNTER_WIDTH(64),
                .NUM_COUNTERS(32),
                .NUM_EVENTS(32),
                .INCREMENT_WIDTH(1),
                .HAS_THRESHOLD(0)
            ) u_statistics (
                .i_clk(i_aon_clk),
                .i_rstb(reset_b),
                .i_global_enable(1'b1),
                .i_freeze(1'b0),
                .i_counter_enable(32'hffffffff),
                .i_clear(32'b0),
                .i_event_select(160'hffbbcdeb38bdab49ca307b9ac5a928398a418820),
                .i_event_valid(statistics | state_onehot),
                .i_event_increment(32'hffffffff),
                .i_threshold_enable(32'b0),
                .i_threshold_value(2048'b0),
                .i_snapshot(i_counter_snapshot),
                .i_read_enable(i_counter_read),
                .i_read_snapshot(i_counter_read_snapshot),
                .i_read_index(i_counter_index),
                .o_read_data(o_counter_data),
                .o_read_valid(o_counter_valid),
                .o_read_overflow(o_counter_overflow),
                .o_counter_overflow(counter_overflow),
                .o_threshold_event(),
                .o_config_error(),
                .o_snapshot_valid(o_counter_snapshot_valid)
            );

            for (genvar w = 0; w < W; w++) begin : g_wake
                counter #(
                    .WIDTH(32),
                    .SATURATE(1)
                ) u_count (
                    .i_clk(i_aon_clk),
                    .i_rstb(reset_b),
                    .i_enable(consumed_wakes[w]),
                    .i_clear(1'b0),
                    .i_load(1'b0),
                    .i_direction(1'b0),
                    .i_load_value(32'b0),
                    .o_count(o_wake_source_count[w*32+:32]),
                    .o_overflow(),
                    .o_underflow(),
                    .o_terminal()
                );
            end

            for (genvar g = 0; g < G; g++) begin : g_clock
                counter #(
                    .WIDTH(32),
                    .SATURATE(1)
                ) u_count (
                    .i_clk(i_aon_clk),
                    .i_rstb(reset_b),
                    .i_enable(!controls.root || !controls.groups[g]),
                    .i_clear(1'b0),
                    .i_load(1'b0),
                    .i_direction(1'b0),
                    .i_load_value(32'b0),
                    .o_count(o_group_gated_cycles[g*32+:32]),
                    .o_overflow(),
                    .o_underflow(),
                    .o_terminal()
                );
            end
        end else begin : g_no_counters
            assign o_counter_data = 0;
            assign o_counter_valid = 0;
            assign o_counter_overflow = 0;
            assign o_counter_snapshot_valid = 0;
            assign o_wake_source_count = 0;
            assign o_group_gated_cycles = 0;
        end
    end
endmodule
`default_nettype wire
