`timescale 1ns / 1ps
`default_nettype none
// Always-on policy and physical sequencing. Clock gates and power cells are
// integrated by tile wrappers; this module emits registered request levels.
module tile_power_controller #(
    parameter NUM_CLOCK_GROUPS = 4,
    parameter NUM_WAKE_SOURCES = 8,
    parameter NUM_STALL_REASONS = 4,
    parameter CONTEXT_ID_WIDTH = 8,
    parameter IDLE_ENTRY_CYCLES = 8,
    parameter MIN_IDLE_RESIDENCY_CYCLES = 2,
    parameter WAKEUP_STABILIZE_CYCLES = 2,
    parameter ISOLATION_SETUP_CYCLES = 2,
    parameter POWER_STABLE_CYCLES = 4,
    parameter RESET_HOLD_CYCLES = 4,
    parameter DRAIN_TIMEOUT_CYCLES = 1024,
    parameter ACK_TIMEOUT_CYCLES = 64,
    parameter POWER_TIMEOUT_CYCLES = 1024,
    parameter POWER_GOOD_SYNC_STAGES = 2,
    parameter SUPPORT_RETENTION = 0,
    parameter SUPPORT_POWER_GATING = 0,
    parameter WAKE_ON_EVENT = 1,
    parameter ASYNC_RESET = 0,
    localparam bit GEOMETRY_VALID =
        ((NUM_CLOCK_GROUPS > 0) === 1'b1) &&
        ((NUM_WAKE_SOURCES > 0) === 1'b1) &&
        ((NUM_STALL_REASONS > 0) === 1'b1) &&
        ((CONTEXT_ID_WIDTH > 0) === 1'b1) &&
        ((IDLE_ENTRY_CYCLES > 0) === 1'b1) &&
        ((MIN_IDLE_RESIDENCY_CYCLES > 0) === 1'b1) &&
        ((WAKEUP_STABILIZE_CYCLES > 0) === 1'b1) &&
        ((ISOLATION_SETUP_CYCLES > 0) === 1'b1) &&
        ((POWER_STABLE_CYCLES > 0) === 1'b1) &&
        ((RESET_HOLD_CYCLES > 0) === 1'b1) &&
        ((DRAIN_TIMEOUT_CYCLES > 0) === 1'b1) &&
        ((ACK_TIMEOUT_CYCLES > 0) === 1'b1) &&
        ((POWER_TIMEOUT_CYCLES > 0) === 1'b1) &&
        ((POWER_GOOD_SYNC_STAGES >= 2) === 1'b1) &&
        ((SUPPORT_RETENTION === 0) || (SUPPORT_RETENTION === 1)) &&
        ((SUPPORT_POWER_GATING === 0) || (SUPPORT_POWER_GATING === 1)) &&
        ((WAKE_ON_EVENT === 0) || (WAKE_ON_EVENT === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        (!SUPPORT_RETENTION || SUPPORT_POWER_GATING) &&
        ((128'(NUM_CLOCK_GROUPS) + 128'(NUM_WAKE_SOURCES) + 128'(NUM_STALL_REASONS) +
            128'(CONTEXT_ID_WIDTH) + 128'(POWER_GOOD_SYNC_STAGES) < 128'd2147483647) === 1'b1) &&
        ((64'(IDLE_ENTRY_CYCLES) < 64'd2147483647) === 1'b1) &&
        ((64'(MIN_IDLE_RESIDENCY_CYCLES) < 64'd2147483647) === 1'b1) &&
        ((64'(WAKEUP_STABILIZE_CYCLES) < 64'd2147483647) === 1'b1) &&
        ((64'(ISOLATION_SETUP_CYCLES) < 64'd2147483647) === 1'b1) &&
        ((64'(POWER_STABLE_CYCLES) < 64'd2147483647) === 1'b1) &&
        ((64'(RESET_HOLD_CYCLES) < 64'd2147483647) === 1'b1) &&
        ((64'(DRAIN_TIMEOUT_CYCLES) < 64'd2147483647) === 1'b1) &&
        ((64'(ACK_TIMEOUT_CYCLES) < 64'd2147483647) === 1'b1) &&
        ((64'(POWER_TIMEOUT_CYCLES) < 64'd2147483647) === 1'b1),
    localparam int G = GEOMETRY_VALID ? NUM_CLOCK_GROUPS : 1,
    localparam int W = GEOMETRY_VALID ? NUM_WAKE_SOURCES : 1,
    localparam int S = GEOMETRY_VALID ? NUM_STALL_REASONS : 1,
    localparam int C = GEOMETRY_VALID ? CONTEXT_ID_WIDTH : 1,
    localparam int PG = GEOMETRY_VALID ? POWER_GOOD_SYNC_STAGES : 2,
    localparam int IW = GEOMETRY_VALID ? $clog2(64'(IDLE_ENTRY_CYCLES) + 1) : 1,
    parameter CLOCK_GROUP_ALWAYS_ON_MASK = {G{1'b0}},
    parameter WAKEUP_CLOCK_GROUP_MASK = {G{1'b1}},
    localparam bit PARAMETERS_VALID = GEOMETRY_VALID &&
        ($bits(CLOCK_GROUP_ALWAYS_ON_MASK) == G) &&
        ($bits(WAKEUP_CLOCK_GROUP_MASK) == G) &&
        (((^CLOCK_GROUP_ALWAYS_ON_MASK == 1'b0) ||
            (^CLOCK_GROUP_ALWAYS_ON_MASK == 1'b1)) === 1'b1) &&
        (((^WAKEUP_CLOCK_GROUP_MASK == 1'b0) ||
            (^WAKEUP_CLOCK_GROUP_MASK == 1'b1)) === 1'b1)
) (
    input logic i_aon_clk,
    input logic i_aon_rstb,
    input logic i_error_clear,
    input logic i_test_mode,
    input logic i_test_clock_enable,
    input logic i_config_valid,
    output logic o_config_ready,
    input logic i_config_auto_idle_enable,
    input logic [W-1:0] i_config_wake_enable,
    input logic i_config_context_check,
    input logic [C-1:0] i_config_context_id,
    output logic o_config_accepted,
    output logic o_config_rejected,
    input logic i_command_valid,
    output logic o_command_ready,
    input logic [tile_power_controller_pkg::POWER_COMMAND_WIDTH-1:0] i_command,
    input logic [C-1:0] i_command_context_id,
    output logic o_command_accepted,
    output logic o_command_rejected,
    output logic o_command_done,
    input logic i_tile_busy,
    input logic i_tile_quiescent,
    input logic i_drain_done,
    input logic [S-1:0] i_stall_reason,
    input logic [G-1:0] i_clock_group_request,
    input logic [W-1:0] i_wakeup_event,
    input logic i_power_good_async,
    input logic i_retention_save_ack,
    input logic i_retention_restore_ack,
    output logic o_tile_accept_enable,
    output logic o_drain_request,
    output logic o_tile_clock_enable,
    output logic [G-1:0] o_clock_group_enable,
    output logic o_operand_isolation_enable,
    output logic o_write_disable,
    output logic o_tile_reset_request,
    output logic o_isolation_enable,
    output logic o_retention_save,
    output logic o_retention_restore,
    output logic o_power_switch_enable,
    output logic [tile_power_controller_pkg::POWER_STATE_WIDTH-1:0] o_power_state,
    output logic [tile_power_controller_pkg::POWER_STATE_WIDTH-1:0] o_target_state,
    output logic [tile_power_controller_pkg::POWER_STATE_WIDTH-1:0] o_previous_stable_state,
    output logic o_transition_active,
    output logic o_power_good_sync,
    output logic [W-1:0] o_wakeup_pending,
    output logic o_policy_valid,
    output logic [C-1:0] o_active_context_id,
    output logic [IW-1:0] o_idle_count,
    output logic [tile_power_controller_pkg::POWER_RESIDENCY_WIDTH-1:0] o_state_residency,
    output logic o_idle,
    output logic o_quiescent,
    output logic o_error,
    output logic o_fatal_error,
    output logic [tile_power_controller_pkg::POWER_ERROR_WIDTH-1:0] o_error_code,
    output logic o_event_state_change,
    output logic o_event_idle_entry,
    output logic o_event_wakeup,
    output logic o_event_stall_entry,
    output logic o_event_retention_entry,
    output logic o_event_off_entry,
    output logic o_event_timeout
);
    import tile_power_controller_pkg::*;
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        tile_power_controller_parameters_must_be_valid invalid_parameters ();
    end else begin : g_controller
        // Preserve X/Z in the power-good chain. Only the last stage is consumed
        // by the controller; no raw asynchronous power input drives an output.
        wire external_reset_b = i_aon_rstb === 1'b1;
        wire reset_b;
        (* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO", DONT_TOUCH = "TRUE" *)
        wire [PG-1:0] power_pipeline;
        wire synchronized_power = power_pipeline[PG-1];

        if (ASYNC_RESET == 1) begin : g_reset_release
            reset_synchronizer u_release (
                .i_clk(i_aon_clk),
                .i_async_rstb(external_reset_b),
                .o_rstb(reset_b)
            );
        end else begin : g_direct_reset
            assign reset_b = external_reset_b;
        end

        dff #(.WIDTH(PG),
            .ASYNC_RESET(ASYNC_RESET),
            .HAS_ENABLE(0)) u_power_sync (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(1'b1),
            .i_d({power_pipeline[PG-2:0], i_power_good_async}),
            .o_q(power_pipeline)
        );

        typedef struct packed {
            logic valid;
            logic auto_idle;
            logic [W-1:0] wake_enable;
            logic context_check;
            logic [C-1:0] context_id;
        } policy_t;

        typedef struct packed {
            logic tile_accept;
            logic drain;
            logic tile_clock;
            logic [G-1:0] groups;
            logic operand_isolation;
            logic write_disable;
            logic isolation;
            logic save;
            logic restore;
            logic power_switch;
            logic reset_hold;
            logic qualified_power;
        } controls_t;

        localparam int POLICY_BITS = $bits(policy_t);
        localparam int CONTROL_BITS = $bits(controls_t);
        // Reset requests power-on, isolation, operand/write protection and reset.
        localparam logic [CONTROL_BITS-1:0] SAFE_CONTROLS =
            {3'b000, {G{1'b0}}, 3'b111, 2'b00, 3'b110};
        wire [POLICY_BITS-1:0] policy_bits;
        policy_t policy;
        policy_t policy_next;
        wire [CONTROL_BITS-1:0] control_bits;
        controls_t control;
        controls_t control_next;
        wire [POWER_STATE_WIDTH-1:0] state;
        logic [POWER_STATE_WIDTH-1:0] next_state;
        wire [POWER_STATE_WIDTH-1:0] target;
        logic [POWER_STATE_WIDTH-1:0] next_target;
        wire [POWER_STATE_WIDTH-1:0] previous;
        wire command_pending;
        logic next_command_pending;
        wire run_authorized;
        logic next_run_authorized;
        wire test_active;
        logic next_test_active;
        wire [W-1:0] pending_wakes;
        logic [W-1:0] next_pending_wakes;
        wire [W-1:0] wake_mask = policy.wake_enable;
        logic [W-1:0] captured_wakes;
        wire [POWER_ERROR_WIDTH-1:0] error_code;
        logic [POWER_ERROR_WIDTH-1:0] detected_error;
        wire fatal;
        logic fail_transition;
        logic timeout;
        logic wake_started;
        logic command_done;
        logic command_legal;
        logic [POWER_ERROR_WIDTH-1:0] command_error;
        logic [POWER_STATE_WIDTH-1:0] command_target;
        logic [G-1:0] known_groups;
        wire [11:0] events;
        wire [11:0] next_events;
        wire tile_reset_released;
        wire run = reset_b === 1'b1;
        wire stable = stable_state(state);
        wire functional = state == PWR_ACTIVE || state == PWR_STALLED;
        wire service_state = state == PWR_ACTIVE || state == PWR_IDLE;
        wire controls_known = ^{i_error_clear, i_test_mode, i_test_clock_enable,
            i_config_valid, i_command_valid, i_tile_busy, i_tile_quiescent,
            i_drain_done, i_stall_reason, i_clock_group_request, i_wakeup_event,
            i_retention_save_ack, i_retention_restore_ack} !== 1'bx;
        wire policy_known = ^{i_config_auto_idle_enable, i_config_wake_enable,
            i_config_context_check, i_config_context_id} !== 1'bx;
        wire waking = WAKE_ON_EVENT == 1 && (|(pending_wakes & wake_mask));
        wire config_accept = o_config_ready && i_config_valid === 1'b1;
        wire config_good = config_accept && policy_known;
        wire config_bad = config_accept && !policy_known;
        wire command_accept = o_command_ready && i_command_valid === 1'b1;
        wire idle_candidate = i_tile_busy === 1'b0 && i_tile_quiescent === 1'b1 &&
            i_stall_reason === {S{1'b0}};
        localparam int IDLE_WIDTH = $clog2(64'(IDLE_ENTRY_CYCLES) + 1);
        wire [IDLE_WIDTH-1:0] idle_count;
        localparam int QUALIFICATION_WIDTH = $clog2(64'(POWER_STABLE_CYCLES) + 1);
        wire [QUALIFICATION_WIDTH-1:0] qualification_count;
        localparam int DRAIN_WIDTH = $clog2(64'(DRAIN_TIMEOUT_CYCLES) + 1);
        wire [DRAIN_WIDTH-1:0] drain_count;
        localparam int SAVE_WIDTH = $clog2(64'(ACK_TIMEOUT_CYCLES) + 1);
        wire [SAVE_WIDTH-1:0] save_count;
        localparam int RESTORE_WIDTH = $clog2(64'(ACK_TIMEOUT_CYCLES) + 1);
        wire [RESTORE_WIDTH-1:0] restore_count;
        localparam int POWER_UP_WIDTH = $clog2(64'(POWER_TIMEOUT_CYCLES) + 1);
        wire [POWER_UP_WIDTH-1:0] power_up_count;
        localparam int POWER_DOWN_WIDTH = $clog2(64'(POWER_TIMEOUT_CYCLES) + 1);
        wire [POWER_DOWN_WIDTH-1:0] power_down_count;
        localparam int ISOLATION_WIDTH = $clog2(64'(ISOLATION_SETUP_CYCLES) + 1);
        wire [ISOLATION_WIDTH-1:0] isolation_count;
        localparam int RESET_WIDTH = $clog2(64'(RESET_HOLD_CYCLES) + 1);
        wire [RESET_WIDTH-1:0] reset_count;
        localparam int WAKE_WIDTH = $clog2(64'(WAKEUP_STABILIZE_CYCLES) + 1);
        wire [WAKE_WIDTH-1:0] wake_count;
        wire [POWER_RESIDENCY_WIDTH-1:0] residency;
        wire power_ready = synchronized_power === 1'b1 &&
            64'(qualification_count) >= 64'(POWER_STABLE_CYCLES) - 1;
        wire base_quiescent = run && power_ready && service_state && !command_pending && !waking &&
            i_tile_quiescent === 1'b1 && i_test_mode === 1'b0 && !fatal && controls_known;
        wire requested_wake = WAKE_ON_EVENT == 1 &&
            (|((pending_wakes | captured_wakes) & wake_mask));
        wire idle_qualify = run && functional && policy.valid && policy.auto_idle &&
            idle_candidate && controls_known && !requested_wake &&
            i_command_valid === 1'b0 && i_config_valid === 1'b0 &&
            i_test_mode === 1'b0 && !fatal;
        assign o_config_ready = base_quiescent;
        assign o_command_ready = run && stable && state != PWR_ERROR && !command_pending &&
            i_test_mode === 1'b0 && !fatal && !config_accept && controls_known &&
            (state == PWR_RETENTION || state == PWR_OFF || power_ready);
        assign o_quiescent = base_quiescent && !config_accept && !command_accept;
        assign o_power_state = state;
        assign o_target_state = target;
        assign o_previous_stable_state = previous;
        assign o_transition_active = !stable;
        assign o_idle = state == PWR_IDLE || state == PWR_RETENTION || state == PWR_OFF;
        assign o_policy_valid = policy.valid;
        assign o_active_context_id = policy.context_id;
        assign o_wakeup_pending = pending_wakes;
        assign o_error_code = error_code;
        assign o_error = error_code != PWR_ERR_NONE;
        assign o_fatal_error = fatal;
        assign o_idle_count = idle_count;
        assign o_state_residency = residency;
        assign o_tile_accept_enable = run ? control.tile_accept : 1'b0;
        assign o_drain_request = run ? control.drain : 1'b0;
        assign o_tile_clock_enable = run ? control.tile_clock : 1'b0;
        assign o_clock_group_enable = run ? control.groups : {G{1'b0}};
        assign o_operand_isolation_enable = run ? control.operand_isolation : 1'b1;
        assign o_write_disable = run ? control.write_disable : 1'b1;
        assign o_isolation_enable = run ? control.isolation : 1'b1;
        assign o_retention_save = run ? control.save : 1'b0;
        assign o_retention_restore = run ? control.restore : 1'b0;
        assign o_power_switch_enable = run ? control.power_switch : 1'b1;
        assign o_power_good_sync = run ? control.qualified_power : 1'b0;
        assign o_tile_reset_request = !tile_reset_released;

        // The tile request asserts asynchronously from a registered control and
        // releases through the common AON-clocked reset wrapper. A tile whose
        // functional clock is unrelated to AON must add its own release wrapper.
        reset_synchronizer u_tile_reset (
            .i_clk(i_aon_clk),
            .i_async_rstb(reset_b && !control.reset_hold),
            .o_rstb(tile_reset_released)
        );

        always_comb begin
            policy = policy_bits;
            control = control_bits;
            policy_next.valid = 1'b1;
            policy_next.auto_idle = i_config_auto_idle_enable;
            policy_next.wake_enable = i_config_wake_enable;
            policy_next.context_check = i_config_context_check;
            policy_next.context_id = i_config_context_id;
            captured_wakes = '0;
            known_groups = '0;

            for (int w = 0; w < W; w++)
                captured_wakes[w] = i_wakeup_event[w] === 1'b1 && wake_mask[w];

            for (int g = 0; g < G; g++)
                known_groups[g] = i_clock_group_request[g] === 1'b1;
        end

        // Reject unsupported targets without changing command ownership. A
        // non-RUN transition starts from a powered state or repeats its target.
        always_comb begin
            command_target = target;
            command_error = PWR_ERR_NONE;

            case (i_command)
                POWER_RUN: command_target = PWR_ACTIVE;
                POWER_IDLE: command_target = PWR_IDLE;
                POWER_RETENTION: begin
                    command_target = PWR_RETENTION;
                    if (SUPPORT_RETENTION == 0) command_error = PWR_ERR_COMMAND;
                end
                POWER_OFF: begin
                    command_target = PWR_OFF;
                    if (SUPPORT_POWER_GATING == 0) command_error = PWR_ERR_COMMAND;
                end
                default: command_error = PWR_ERR_COMMAND;
            endcase
            if (^{i_command, i_command_context_id} === 1'bx)
                command_error = PWR_ERR_COMMAND;
            else if (command_error == PWR_ERR_NONE && policy.context_check &&
                i_command_context_id != policy.context_id) command_error = PWR_ERR_CONTEXT;
            else if (command_error == PWR_ERR_NONE && command_target != PWR_ACTIVE &&
                !functional && state != PWR_IDLE && state != command_target)
                command_error = PWR_ERR_TRANSITION;
            command_legal = command_error == PWR_ERR_NONE;
        end

        always_comb begin
            next_state = state;
            next_target = target;
            next_command_pending = command_pending;
            next_run_authorized = run_authorized;
            next_test_active = test_active;
            next_pending_wakes = pending_wakes | captured_wakes;
            detected_error = PWR_ERR_NONE;
            fail_transition = 1'b0;
            timeout = 1'b0;
            wake_started = 1'b0;
            command_done = 1'b0;

            if (!controls_known || synchronized_power === 1'bx || synchronized_power === 1'bz)
                detected_error = PWR_ERR_UNKNOWN;
            else if (config_bad) detected_error = PWR_ERR_CONFIG;
            else if (command_accept && !command_legal) detected_error = command_error;
            else if ((i_retention_save_ack === 1'b1 && !control.save) ||
                (i_retention_restore_ack === 1'b1 && !control.restore))
                detected_error = PWR_ERR_ACK;

            if (i_test_mode === 1'b0) next_test_active = 1'b0;
            else if (i_test_mode === 1'b1 && !test_active) begin
                if (state == PWR_ACTIVE && power_ready && run_authorized &&
                    !command_pending && controls_known)
                    next_test_active = 1'b1;
                else if (detected_error == PWR_ERR_NONE) detected_error = PWR_ERR_TEST;
            end

            case (state)
                PWR_RESET: begin
                    next_target = PWR_ACTIVE;
                    if (power_ready) next_state = PWR_REINITIALIZING;
                    else if (64'(power_up_count) >= 64'(POWER_TIMEOUT_CYCLES) - 1) begin
                        timeout = 1'b1;
                        detected_error = PWR_ERR_POWER_UP_TIMEOUT;
                    end
                end
                PWR_DRAINING: begin
                    if (controls_known && i_tile_quiescent === 1'b1 && i_drain_done === 1'b1) begin
                        case (target)
                            PWR_IDLE: next_state = PWR_IDLE;
                            PWR_RETENTION: next_state = PWR_SAVING;
                            PWR_OFF: next_state = PWR_ISOLATING;
                            default: begin
                                fail_transition = 1'b1;
                                detected_error = PWR_ERR_SEQUENCE;
                            end
                        endcase
                    end else if (64'(drain_count) >= 64'(DRAIN_TIMEOUT_CYCLES) - 1) begin
                        timeout = 1'b1;
                        detected_error = PWR_ERR_DRAIN_TIMEOUT;
                    end
                end
                PWR_SAVING: begin
                    if (controls_known && i_retention_save_ack === 1'b1)
                        next_state = PWR_ISOLATING;
                    else if (64'(save_count) >= 64'(ACK_TIMEOUT_CYCLES) - 1) begin
                        timeout = 1'b1;
                        detected_error = PWR_ERR_SAVE_TIMEOUT;
                    end
                end
                PWR_ISOLATING: begin
                    if (controls_known && 64'(isolation_count) >=
                        64'(ISOLATION_SETUP_CYCLES) - 1) next_state = PWR_POWERING_DOWN;
                end
                PWR_POWERING_DOWN: begin
                    if (synchronized_power === 1'b0) next_state = target;
                    else if (64'(power_down_count) >= 64'(POWER_TIMEOUT_CYCLES) - 1) begin
                        timeout = 1'b1;
                        detected_error = PWR_ERR_POWER_DOWN_TIMEOUT;
                    end
                end
                PWR_POWERING_UP: begin
                    if (power_ready) next_state = previous == PWR_RETENTION ?
                        PWR_RESTORING : PWR_REINITIALIZING;
                    else if (64'(power_up_count) >= 64'(POWER_TIMEOUT_CYCLES) - 1) begin
                        timeout = 1'b1;
                        detected_error = PWR_ERR_POWER_UP_TIMEOUT;
                    end
                end
                PWR_RESTORING: begin
                    if (controls_known && i_retention_restore_ack === 1'b1) next_state = PWR_WAKEUP;
                    else if (64'(restore_count) >= 64'(ACK_TIMEOUT_CYCLES) - 1) begin
                        timeout = 1'b1;
                        detected_error = PWR_ERR_RESTORE_TIMEOUT;
                    end
                end
                PWR_REINITIALIZING: begin
                    if (controls_known && !control.reset_hold && tile_reset_released === 1'b1)
                        next_state = PWR_WAKEUP;
                end
                PWR_WAKEUP: begin
                    if (controls_known && 64'(wake_count) >= 64'(WAKEUP_STABILIZE_CYCLES) - 1)
                        next_state = PWR_ACTIVE;
                end
                PWR_ACTIVE, PWR_STALLED, PWR_IDLE, PWR_RETENTION, PWR_OFF: begin
                    if (controls_known && !config_accept && !test_active &&
                        i_test_mode === 1'b0) begin
                        if (command_accept && command_legal) begin
                            next_target = command_target;
                            next_command_pending = 1'b1;
                            if (command_target == state ||
                                (command_target == PWR_ACTIVE && functional)) begin
                                next_state = command_target;
                                command_done = 1'b1;
                                next_command_pending = 1'b0;
                            end else if (command_target == PWR_ACTIVE) begin
                                next_state = state == PWR_IDLE ? PWR_WAKEUP : PWR_POWERING_UP;
                                wake_started = 1'b1;
                            end else next_state = PWR_DRAINING;
                        end else if (!command_accept) begin
                            if (requested_wake) begin
                                next_target = PWR_ACTIVE;
                                if (!functional) begin
                                    next_state = state == PWR_IDLE ? PWR_WAKEUP : PWR_POWERING_UP;
                                    wake_started = 1'b1;
                                end
                            end else if (state == PWR_IDLE && i_tile_busy === 1'b1 &&
                                64'(residency) >= 64'(MIN_IDLE_RESIDENCY_CYCLES) - 1) begin
                                next_target = PWR_ACTIVE;
                                next_state = PWR_WAKEUP;
                                wake_started = 1'b1;
                            end else if (functional) begin
                                if (idle_qualify && 64'(idle_count) >=
                                    64'(IDLE_ENTRY_CYCLES) - 1) begin
                                    next_state = PWR_IDLE;
                                    next_target = PWR_IDLE;
                                end else if (i_tile_busy === 1'b1 && (|i_stall_reason))
                                    next_state = PWR_STALLED;
                                else next_state = PWR_ACTIVE;
                            end
                        end
                    end
                end
                PWR_ERROR: begin end
                default: begin
                    fail_transition = 1'b1;
                    detected_error = PWR_ERR_SEQUENCE;
                end
            endcase

            // Loss and timeout have higher priority than all software or test
            // controls. Hold the switch request; never reverse physical progress.
            if (state != PWR_RESET && state != PWR_POWERING_UP && state != PWR_POWERING_DOWN &&
                state != PWR_RETENTION && state != PWR_OFF &&
                state != PWR_ERROR && !power_ready) begin
                fail_transition = 1'b1;
                timeout = 1'b0;
                detected_error = PWR_ERR_POWER_LOSS;
            end
            if (timeout || fail_transition || fatal) begin
                next_state = PWR_ERROR;
                command_done = 1'b0;
                wake_started = 1'b0;
                next_command_pending = 1'b0;
                next_test_active = 1'b0;
            end else begin
                if (next_command_pending && stable_state(next_state) &&
                    next_state == next_target) begin
                    command_done = 1'b1;
                    next_command_pending = 1'b0;
                end
                if (command_done && next_target == PWR_ACTIVE) next_run_authorized = 1'b1;
                if (next_state == PWR_DRAINING || next_state == PWR_IDLE)
                    next_run_authorized = 1'b0;
                if (wake_started || (functional && requested_wake) ||
                    (command_done && next_target == PWR_ACTIVE))
                    next_pending_wakes = (pending_wakes & ~wake_mask) | captured_wakes;
            end
        end

        // Compute one registered control word from the selected destination
        // state. Preserve supply direction in ERROR and keep all unavailable
        // tile interfaces protected, including unconfigured ACTIVE operation.
        always_comb begin
            control_next = '0;
            control_next.power_switch = control.power_switch;
            control_next.isolation = 1'b1;
            control_next.operand_isolation = 1'b1;
            control_next.write_disable = 1'b1;
            control_next.qualified_power = power_ready;
            control_next.reset_hold = 1'b1;

            case (next_state)
                PWR_RESET: control_next.power_switch = 1'b1;
                PWR_ACTIVE, PWR_STALLED: begin
                    control_next.power_switch = 1'b1;
                    control_next.isolation = 1'b0;
                    control_next.reset_hold = 1'b0;
                    control_next.tile_clock = power_ready;
                    control_next.groups = known_groups | CLOCK_GROUP_ALWAYS_ON_MASK;
                    control_next.tile_accept = (policy.valid || config_good) &&
                        !next_test_active && i_test_mode === 1'b0 && controls_known;
                    control_next.operand_isolation = !control_next.tile_accept ||
                        (next_state == PWR_STALLED && i_clock_group_request === {G{1'b0}});
                    control_next.write_disable = !control_next.tile_accept;
                end
                PWR_IDLE: begin
                    control_next.power_switch = 1'b1;
                    control_next.isolation = 1'b0;
                    control_next.reset_hold = 1'b0;
                end
                PWR_DRAINING, PWR_SAVING, PWR_ISOLATING, PWR_RESTORING,
                PWR_REINITIALIZING, PWR_WAKEUP: begin
                    control_next.power_switch = 1'b1;
                    control_next.tile_clock = power_ready;
                    control_next.groups = WAKEUP_CLOCK_GROUP_MASK | CLOCK_GROUP_ALWAYS_ON_MASK;
                    control_next.drain = next_state == PWR_DRAINING;
                    control_next.save = next_state == PWR_SAVING;
                    control_next.restore = next_state == PWR_RESTORING ||
                        (next_state == PWR_WAKEUP && previous == PWR_RETENTION);
                    control_next.isolation = next_state == PWR_ISOLATING ||
                        next_state == PWR_RESTORING || next_state == PWR_REINITIALIZING ||
                        (next_state == PWR_WAKEUP && control.isolation);
                    control_next.reset_hold = next_state == PWR_REINITIALIZING &&
                        (state != PWR_REINITIALIZING || (control.reset_hold &&
                        64'(reset_count) < 64'(RESET_HOLD_CYCLES) - 1));
                end
                PWR_POWERING_DOWN, PWR_RETENTION, PWR_OFF: begin
                    control_next.power_switch = 1'b0;
                    control_next.reset_hold = next_target == PWR_OFF;
                end
                PWR_POWERING_UP: begin
                    control_next.power_switch = 1'b1;
                    control_next.reset_hold = previous != PWR_RETENTION && state != PWR_RETENTION;
                end
                PWR_ERROR: begin
                    control_next.tile_clock = control.power_switch && power_ready;
                    control_next.groups = WAKEUP_CLOCK_GROUP_MASK | CLOCK_GROUP_ALWAYS_ON_MASK;
                end
                default: begin end
            endcase

            if (next_test_active) begin
                control_next.tile_clock = i_test_mode === 1'b1 &&
                    i_test_clock_enable === 1'b1 && power_ready && controls_known;
                control_next.groups = WAKEUP_CLOCK_GROUP_MASK | CLOCK_GROUP_ALWAYS_ON_MASK;
                control_next.tile_accept = 1'b0;
                control_next.operand_isolation = 1'b1;
                control_next.write_disable = 1'b1;
            end
            if (!control_next.tile_clock) control_next.groups = '0;
        end

        dff #(
            .WIDTH(POLICY_BITS),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_policy (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(config_good),
            .i_d(policy_next),
            .o_q(policy_bits)
        );

        dff #(
            .WIDTH(CONTROL_BITS),
            .RESET_VALUE(SAFE_CONTROLS),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_controls (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(control_bits !== control_next),
            .i_d(control_next),
            .o_q(control_bits)
        );

        dff #(
            .WIDTH(POWER_STATE_WIDTH),
            .RESET_VALUE(PWR_RESET),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_state (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(state != next_state),
            .i_d(next_state),
            .o_q(state)
        );

        dff #(
            .WIDTH(POWER_STATE_WIDTH),
            .RESET_VALUE(PWR_ACTIVE),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_target (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(target != next_target),
            .i_d(next_target),
            .o_q(target)
        );

        dff #(
            .WIDTH(POWER_STATE_WIDTH),
            .RESET_VALUE(PWR_RESET),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_previous (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(stable && state != next_state),
            .i_d(state),
            .o_q(previous)
        );

        dff #(.ASYNC_RESET(ASYNC_RESET)) u_command_pending (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(command_pending != next_command_pending),
            .i_d(next_command_pending),
            .o_q(command_pending)
        );

        dff #(.ASYNC_RESET(ASYNC_RESET)) u_run_authorized (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(run_authorized != next_run_authorized),
            .i_d(next_run_authorized),
            .o_q(run_authorized)
        );

        dff #(.ASYNC_RESET(ASYNC_RESET)) u_test (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(test_active != next_test_active),
            .i_d(next_test_active),
            .o_q(test_active)
        );

        dff #(
            .WIDTH(W),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_wakes (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(pending_wakes != next_pending_wakes),
            .i_d(next_pending_wakes),
            .o_q(pending_wakes)
        );

        wire clear_error = o_quiescent && i_error_clear === 1'b1 && !fatal &&
            detected_error == PWR_ERR_NONE;

        dff #(
            .WIDTH(POWER_ERROR_WIDTH),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_error (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(run && (clear_error || (!o_error && detected_error != PWR_ERR_NONE))),
            .i_d(clear_error ? {POWER_ERROR_WIDTH{1'b0}} : detected_error),
            .o_q(error_code)
        );
        dff #(.ASYNC_RESET(ASYNC_RESET)) u_fatal (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(timeout || fail_transition),
            .i_d(1'b1),
            .o_q(fatal)
        );

        assign next_events = {config_good, config_bad, command_accept && command_legal,
            command_accept && !command_legal, command_done,
            next_state != state, next_state != state && next_state == PWR_IDLE,
            wake_started, next_state != state && next_state == PWR_STALLED,
            next_state != state && next_state == PWR_RETENTION,
            next_state != state && next_state == PWR_OFF, timeout};

        dff #(
            .WIDTH(12),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_events (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable((|events) || (|next_events)),
            .i_d(next_events),
            .o_q(events)
        );

        assign {o_config_accepted, o_config_rejected, o_command_accepted,
            o_command_rejected, o_command_done, o_event_state_change, o_event_idle_entry,
            o_event_wakeup, o_event_stall_entry, o_event_retention_entry, o_event_off_entry,
            o_event_timeout} = run ? events : '0;

        counter #(
            .WIDTH(IDLE_WIDTH),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_idle_timer (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(run && (idle_qualify) && 64'(idle_count) < 64'(IDLE_ENTRY_CYCLES)),
            .i_clear((|idle_count) && (!idle_qualify)),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value({IDLE_WIDTH{1'b0}}),
            .o_count(idle_count),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );

        counter #(
            .WIDTH(QUALIFICATION_WIDTH),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_qualification_timer (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(run && (synchronized_power === 1'b1) &&
                64'(qualification_count) < 64'(POWER_STABLE_CYCLES)),
            .i_clear((|qualification_count) && (synchronized_power !== 1'b1)),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value({QUALIFICATION_WIDTH{1'b0}}),
            .o_count(qualification_count),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );

        counter #(
            .WIDTH(DRAIN_WIDTH),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_drain_timer (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(run && next_state == state && (state == PWR_DRAINING) &&
                64'(drain_count) < 64'(DRAIN_TIMEOUT_CYCLES)),
            .i_clear((|drain_count) && (!(state == PWR_DRAINING) || next_state != state)),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value({DRAIN_WIDTH{1'b0}}),
            .o_count(drain_count),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );

        counter #(
            .WIDTH(SAVE_WIDTH),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_save_timer (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(run && next_state == state &&
                (state == PWR_SAVING) && 64'(save_count) < 64'(ACK_TIMEOUT_CYCLES)),
            .i_clear((|save_count) && (!(state == PWR_SAVING) || next_state != state)),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value({SAVE_WIDTH{1'b0}}),
            .o_count(save_count),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );

        counter #(
            .WIDTH(RESTORE_WIDTH),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_restore_timer (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(run && next_state == state && (state == PWR_RESTORING) &&
                64'(restore_count) < 64'(ACK_TIMEOUT_CYCLES)),
            .i_clear((|restore_count) && (!(state == PWR_RESTORING) || next_state != state)),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value({RESTORE_WIDTH{1'b0}}),
            .o_count(restore_count),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );

        counter #(
            .WIDTH(POWER_UP_WIDTH),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_power_up_timer (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(run && next_state == state &&
                (state == PWR_POWERING_UP || state == PWR_RESET) &&
                64'(power_up_count) < 64'(POWER_TIMEOUT_CYCLES)),
            .i_clear((|power_up_count) &&
                (!(state == PWR_POWERING_UP || state == PWR_RESET) || next_state != state)),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value({POWER_UP_WIDTH{1'b0}}),
            .o_count(power_up_count),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );

        counter #(
            .WIDTH(POWER_DOWN_WIDTH),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_power_down_timer (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(run && next_state == state && (state == PWR_POWERING_DOWN) &&
                64'(power_down_count) < 64'(POWER_TIMEOUT_CYCLES)),
            .i_clear((|power_down_count) && (!(state == PWR_POWERING_DOWN) || next_state != state)),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value({POWER_DOWN_WIDTH{1'b0}}),
            .o_count(power_down_count),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );

        counter #(
            .WIDTH(ISOLATION_WIDTH),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_isolation_timer (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(run && next_state == state && (state == PWR_ISOLATING) &&
                64'(isolation_count) < 64'(ISOLATION_SETUP_CYCLES)),
            .i_clear((|isolation_count) && (!(state == PWR_ISOLATING) || next_state != state)),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value({ISOLATION_WIDTH{1'b0}}),
            .o_count(isolation_count),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );

        counter #(
            .WIDTH(RESET_WIDTH),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_reset_timer (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(run && next_state == state &&
                (state == PWR_REINITIALIZING && control.reset_hold) &&
                64'(reset_count) < 64'(RESET_HOLD_CYCLES)),
            .i_clear((|reset_count) &&
                (state != PWR_REINITIALIZING || next_state != PWR_REINITIALIZING)),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value({RESET_WIDTH{1'b0}}),
            .o_count(reset_count),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );

        counter #(
            .WIDTH(WAKE_WIDTH),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_wake_timer (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(run && next_state == state && (state == PWR_WAKEUP) &&
                64'(wake_count) < 64'(WAKEUP_STABILIZE_CYCLES)),
            .i_clear((|wake_count) && (!(state == PWR_WAKEUP) || next_state != state)),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value({WAKE_WIDTH{1'b0}}),
            .o_count(wake_count),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );

        counter #(
            .WIDTH(POWER_RESIDENCY_WIDTH),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_residency (
            .i_clk(i_aon_clk),
            .i_rstb(reset_b),
            .i_enable(run && next_state == state && stable),
            .i_clear((|residency) && (!stable || next_state != state)),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value({POWER_RESIDENCY_WIDTH{1'b0}}),
            .o_count(residency),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );
    end
endmodule
`default_nettype wire
