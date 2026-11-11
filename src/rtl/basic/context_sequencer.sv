`timescale 1ns / 1ps

// Single-clock selection of committed contexts. Execution acceptance and safe
// points are supplied by the tile; this controller neither executes nor drains it.
module context_sequencer #(
    // Untyped parameters retain negative, oversized, and X/Z caller values.
    parameter CONTEXT_DEPTH = 4,
    parameter LOOP_COUNT_WIDTH = 16,
    parameter HAS_LOOP = 1,
    parameter HAS_SUSPEND = 1,
    parameter HAS_EXTERNAL_SWITCH = 1,
    parameter ASYNC_RESET = 0,
    localparam int unsigned STORAGE_DEPTH = ((CONTEXT_DEPTH >= 1) === 1'b1) ? CONTEXT_DEPTH : 1,
    localparam int unsigned COUNT_WIDTH = ((LOOP_COUNT_WIDTH >= 1) === 1'b1) ? LOOP_COUNT_WIDTH : 1,
    localparam int unsigned ADDR_WIDTH = STORAGE_DEPTH > 1 ? $clog2(STORAGE_DEPTH) : 1,
    localparam int unsigned TRANSITION_MODE_WIDTH = context_sequencer_pkg::TRANSITION_MODE_WIDTH,
    localparam int unsigned ERROR_CODE_WIDTH = context_sequencer_pkg::ERROR_CODE_WIDTH,
    localparam int unsigned INTERFACE_VERSION = context_sequencer_pkg::INTERFACE_VERSION
) (
    input  logic i_clk,
    input  logic i_rstb,
    input  logic i_start_enable,
    input  logic [ADDR_WIDTH-1:0] i_start_context,
    input  logic i_stop_request,
    input  logic i_suspend_request,
    input  logic i_resume_request,
    input  logic i_switch_request,
    input  logic [ADDR_WIDTH-1:0] i_switch_context,
    input  logic i_error_clear,
    input  logic i_step_accepted,
    input  logic i_safe_point,
    input  logic [TRANSITION_MODE_WIDTH-1:0] i_transition_mode,
    input  logic [ADDR_WIDTH-1:0] i_transition_target,
    input  logic [COUNT_WIDTH-1:0] i_loop_count,
    input  logic i_active_context_valid,
    input  logic i_candidate_context_valid,
    output logic o_active_read_enable,
    output logic [ADDR_WIDTH-1:0] o_active_context,
    output logic o_candidate_read_enable,
    output logic [ADDR_WIDTH-1:0] o_candidate_context,
    output logic o_context_enable,
    output logic o_quiesce_request,
    output logic o_idle,
    output logic o_active,
    output logic o_context_wait,
    output logic o_stop_pending,
    output logic o_suspend_pending,
    output logic o_suspended,
    output logic o_switch_pending,
    output logic o_completed,
    output logic o_error,
    output logic [ERROR_CODE_WIDTH-1:0] o_error_code,
    output logic o_context_activated,
    output logic o_context_changed,
    output logic o_sequence_completed,
    output logic o_loop_active,
    output logic [ADDR_WIDTH-1:0] o_loop_owner,
    output logic [COUNT_WIDTH-1:0] o_loop_remaining
);
    import context_sequencer_pkg::*;
    typedef enum logic [3:0] {
        IDLE = 4'd0, START_WAIT = 4'd1, ACTIVE = 4'd2, CONTEXT_WAIT = 4'd3,
        STOP_PENDING = 4'd4, SUSPEND_PENDING = 4'd5, SUSPENDED = 4'd6,
        SWITCH_PENDING = 4'd7, SWITCH_WAIT = 4'd8, COMPLETED = 4'd9, ERROR = 4'd10
    } sequencer_state_t;
    typedef enum logic [1:0] {
        LOOP_PRESERVE = 2'd0, LOOP_LOAD = 2'd1, LOOP_DECREMENT = 2'd2, LOOP_CLEAR = 2'd3
    } loop_action_t;

    localparam bit PARAMETERS_VALID =
        INTERFACE_VERSION == 1 &&
        ((CONTEXT_DEPTH >= 1) === 1'b1) &&
        ((LOOP_COUNT_WIDTH >= 1) === 1'b1) &&
        (HAS_LOOP === 0 || HAS_LOOP === 1) &&
        (HAS_SUSPEND === 0 || HAS_SUSPEND === 1) &&
        (HAS_EXTERNAL_SWITCH === 0 || HAS_EXTERNAL_SWITCH === 1) &&
        (ASYNC_RESET === 0 || ASYNC_RESET === 1);

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        context_sequencer_parameters_must_be_valid invalid_parameters ();
    end else begin : g_controller
        localparam int unsigned CONTROL_WIDTH = $bits(sequencer_state_t) + ERROR_CODE_WIDTH + 5 + 3 * ADDR_WIDTH;
        logic [CONTROL_WIDTH-1:0] control_q, control_d;
        sequencer_state_t state, next_state;
        logic [ADDR_WIDTH-1:0] active_context, next_active_context;
        logic [ADDR_WIDTH-1:0] pending_context, next_pending_context;
        logic pending_scheduled, next_pending_scheduled;
        logic loop_active, next_loop_active;
        logic [ADDR_WIDTH-1:0] loop_owner, next_loop_owner;
        logic [COUNT_WIDTH-1:0] loop_remaining;
        sequencer_error_code_t error_code, next_error_code;
        logic event_activated, event_changed, event_completed;
        logic next_event_activated, next_event_changed, next_event_completed;
        logic loop_clear, loop_load, loop_decrement;
        wire [5:0] commands = {i_start_enable, i_stop_request, i_suspend_request,
                              i_resume_request, i_switch_request, i_error_clear};
        wire [ADDR_WIDTH:0] incremented = {1'b0, active_context} + 1'b1;
        wire suspend_command, resume_command, switch_command;
        wire configured_repeat, remaining_repeat;
        if (COUNT_WIDTH > 1) begin : g_repeat_count
            assign configured_repeat = i_loop_count > COUNT_WIDTH'(1);
            assign remaining_repeat = loop_remaining > COUNT_WIDTH'(1);
        end else begin : g_single_visit
            assign configured_repeat = 1'b0;
            assign remaining_repeat = 1'b0;
        end

        // A known zero asserts reset. X/Z reset is a protocol error sampled by
        // the FSM, with execution already clamped off; it cannot activate work.
        wire storage_rstb = i_rstb !== 1'b0;
        dff #(.WIDTH(CONTROL_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0)) u_control (
            .i_clk(i_clk),
            .i_rstb(storage_rstb),
            .i_enable(1'b1),
            .i_d(control_d),
            .o_q(control_q)
        );
        assign {state, active_context, pending_context, pending_scheduled,
                loop_active, loop_owner, error_code,
                event_activated, event_changed, event_completed} = control_q;

        if (HAS_LOOP == 1) begin : g_loop
            wire [2:0] unused_counter_status;
            wire [COUNT_WIDTH-1:0] loop_load_value = i_loop_count - 1'b1;
            // Count only accepted visits to the owner. Load has priority over
            // decrement; saturating arithmetic cannot wrap a finished loop.
            counter #(.WIDTH(COUNT_WIDTH), .ASYNC_RESET(ASYNC_RESET != 0), .SATURATE(1'b1)) u_remaining (
                .i_clk(i_clk),
                .i_rstb(storage_rstb),
                .i_enable(loop_decrement),
                .i_clear(loop_clear),
                .i_load(loop_load),
                .i_direction(1'b1),
                .i_load_value(loop_load_value),
                .o_count(loop_remaining),
                .o_overflow(unused_counter_status[0]),
                .o_underflow(unused_counter_status[1]),
                .o_terminal(unused_counter_status[2])
            );
        end else begin : g_no_loop
            // These generic next-state controls have no storage destination.
            wire unused_loop_controls = ^{loop_load, loop_decrement};
            assign loop_remaining = '0;
        end
        if (HAS_SUSPEND == 1) begin : g_suspend
            assign suspend_command = i_suspend_request;
            assign resume_command = i_resume_request;
        end else begin : g_no_suspend
            assign suspend_command = 1'b0;
            assign resume_command = 1'b0;
        end
        if (HAS_EXTERNAL_SWITCH == 1) begin : g_switch
            assign switch_command = i_switch_request;
        end else begin : g_no_switch
            assign switch_command = 1'b0;
        end

        function automatic bit address_ok(input logic [ADDR_WIDTH-1:0] address);
            address_ok = (^address !== 1'bx) &&
                         {1'b0, address} < (ADDR_WIDTH + 1)'(STORAGE_DEPTH);
        endfunction

        logic scheduled_read;
        logic [ADDR_WIDTH-1:0] scheduled_context;
        sequencer_error_code_t transition_error;
        loop_action_t loop_action;

        // Candidate calculation never depends on candidate validity. This keeps
        // the memory address -> read-valid -> next-state path free of feedback.
        always_comb begin
            scheduled_read = 1'b0;
            scheduled_context = '0;
            transition_error = SEQ_ERR_NONE;
            loop_action = LOOP_PRESERVE;
            case (i_transition_mode)
                CONTEXT_HOLD, CONTEXT_END: begin end
                CONTEXT_INCREMENT: begin
                    if (incremented >= (ADDR_WIDTH + 1)'(STORAGE_DEPTH)) transition_error = SEQ_ERR_ADDRESS;
                    else begin
                        scheduled_read = 1'b1;
                        scheduled_context = incremented[ADDR_WIDTH-1:0];
                    end
                end
                CONTEXT_JUMP: begin
                    if (!address_ok(i_transition_target)) transition_error = SEQ_ERR_ADDRESS;
                    else begin
                        scheduled_read = 1'b1;
                        scheduled_context = i_transition_target;
                    end
                end
                CONTEXT_LOOP: begin
                    if (HAS_LOOP == 0) transition_error = SEQ_ERR_TRANSITION;
                    else if (loop_active && (loop_owner != active_context || loop_remaining == '0))
                        transition_error = SEQ_ERR_LOOP;
                    else if (!loop_active && ((^i_loop_count === 1'bx) || i_loop_count == '0))
                        transition_error = SEQ_ERR_LOOP;
                    else if ((loop_active && remaining_repeat) || (!loop_active && configured_repeat)) begin
                        if (!address_ok(i_transition_target)) transition_error = SEQ_ERR_ADDRESS;
                        else begin
                            scheduled_read = 1'b1;
                            scheduled_context = i_transition_target;
                            if (loop_active) loop_action = LOOP_DECREMENT;
                            else loop_action = LOOP_LOAD;
                        end
                    end else begin
                        if (incremented >= (ADDR_WIDTH + 1)'(STORAGE_DEPTH)) transition_error = SEQ_ERR_ADDRESS;
                        else begin
                            scheduled_read = 1'b1;
                            scheduled_context = incremented[ADDR_WIDTH-1:0];
                            loop_action = LOOP_CLEAR;
                        end
                    end
                end
                default: transition_error = SEQ_ERR_TRANSITION;
            endcase
        end

        always_comb begin
            o_active_read_enable = 1'b0;
            o_candidate_read_enable = 1'b0;
            o_candidate_context = '0;
            if (i_rstb === 1'b1) begin
                o_active_read_enable = state == ACTIVE || (state == SUSPENDED && resume_command === 1'b1);
                if ((state == IDLE || state == COMPLETED) && i_start_enable === 1'b1 && address_ok(i_start_context)) begin
                    o_candidate_read_enable = 1'b1;
                    o_candidate_context = i_start_context;
                end else if ((state == ACTIVE || state == CONTEXT_WAIT || state == SUSPENDED) &&
                             switch_command === 1'b1 && !loop_active && address_ok(i_switch_context)) begin
                    o_candidate_read_enable = 1'b1;
                    o_candidate_context = i_switch_context;
                end else if (state == START_WAIT || state == CONTEXT_WAIT || state == SWITCH_PENDING || state == SWITCH_WAIT) begin
                    o_candidate_read_enable = 1'b1;
                    o_candidate_context = pending_context;
                end else if (state == ACTIVE && commands === 6'b0 && scheduled_read) begin
                    o_candidate_read_enable = 1'b1;
                    o_candidate_context = scheduled_context;
                end
            end
        end
        assign o_active_context = active_context;
        assign o_context_enable = i_rstb === 1'b1 && state == ACTIVE &&
                                  i_active_context_valid === 1'b1 && commands === 6'b0;
        assign o_quiesce_request = i_rstb === 1'b1 &&
            (state == STOP_PENDING || state == SUSPEND_PENDING || state == SWITCH_PENDING || state == SWITCH_WAIT ||
             ((state == ACTIVE || state == CONTEXT_WAIT || state == START_WAIT || state == SUSPENDED) &&
              (i_stop_request === 1'b1 || suspend_command === 1'b1 || switch_command === 1'b1)));
        assign o_idle = state == IDLE;
        assign o_active = state == ACTIVE;
        assign o_context_wait = state == START_WAIT || state == CONTEXT_WAIT || state == SWITCH_WAIT;
        assign o_stop_pending = state == STOP_PENDING;
        assign o_suspend_pending = state == SUSPEND_PENDING;
        assign o_suspended = state == SUSPENDED;
        assign o_switch_pending = state == SWITCH_PENDING || state == SWITCH_WAIT;
        assign o_completed = state == COMPLETED;
        assign o_error = state == ERROR;
        assign o_error_code = error_code;
        assign o_context_activated = event_activated;
        assign o_context_changed = event_changed;
        assign o_sequence_completed = event_completed;
        assign o_loop_active = HAS_LOOP == 1 ? loop_active : 1'b0;
        assign o_loop_owner = HAS_LOOP == 1 ? loop_owner : '0;
        assign o_loop_remaining = loop_remaining;

        logic command_legal;
        logic safe_required;
        sequencer_error_code_t detected_error;
        always_comb begin
            command_legal = 1'b1;
            if (i_start_enable === 1'b1) command_legal = state == IDLE || state == COMPLETED;
            if (i_stop_request === 1'b1) command_legal = state == START_WAIT || state == ACTIVE || state == CONTEXT_WAIT ||
                state == SUSPEND_PENDING || state == SUSPENDED || state == SWITCH_PENDING || state == SWITCH_WAIT;
            if (i_suspend_request === 1'b1) command_legal = HAS_SUSPEND == 1 && (state == ACTIVE || state == CONTEXT_WAIT);
            if (i_resume_request === 1'b1) command_legal = HAS_SUSPEND == 1 && state == SUSPENDED;
            if (i_switch_request === 1'b1) command_legal = HAS_EXTERNAL_SWITCH == 1 && !loop_active &&
                (state == ACTIVE || state == CONTEXT_WAIT || state == SUSPENDED);
            if (i_error_clear === 1'b1) command_legal = state == ERROR;
            safe_required = state == STOP_PENDING || state == SUSPEND_PENDING || state == SWITCH_PENDING ||
                i_stop_request === 1'b1 || suspend_command === 1'b1 || switch_command === 1'b1;
            detected_error = SEQ_ERR_NONE;
            if (i_rstb !== 1'b0) begin
                if (i_rstb !== 1'b1 || (^commands === 1'bx) || (^i_step_accepted === 1'bx)) detected_error = SEQ_ERR_PROTOCOL;
                else if ((commands & (commands - 6'd1)) != 0 || !command_legal) detected_error = SEQ_ERR_COMMAND;
                else if ((o_active_read_enable && (^i_active_context_valid === 1'bx)) ||
                         (o_candidate_read_enable && (^i_candidate_context_valid === 1'bx)) ||
                         (safe_required && (^i_safe_point === 1'bx))) detected_error = SEQ_ERR_PROTOCOL;
                else if (state == ACTIVE && i_active_context_valid === 1'b0) detected_error = SEQ_ERR_ACTIVE_INVALID;
                else if (i_step_accepted && !o_context_enable) detected_error = SEQ_ERR_PROTOCOL;
                else if ((i_start_enable && !address_ok(i_start_context)) ||
                         (switch_command && !address_ok(i_switch_context))) detected_error = SEQ_ERR_ADDRESS;
                else if (resume_command && i_active_context_valid === 1'b0) detected_error = SEQ_ERR_ACTIVE_INVALID;
                else if (state == ACTIVE && i_step_accepted) detected_error = transition_error;
            end
        end

        // One packed DFF bank owns control state. Events clear on every edge,
        // independently of stalls; counted-loop updates use the common counter.
        always_comb begin
            next_state = state;
            next_active_context = active_context;
            next_pending_context = pending_context;
            next_pending_scheduled = pending_scheduled;
            next_loop_active = loop_active;
            next_loop_owner = loop_owner;
            next_error_code = error_code;
            next_event_activated = 1'b0;
            next_event_changed = 1'b0;
            next_event_completed = 1'b0;
            loop_clear = 1'b0;
            loop_load = 1'b0;
            loop_decrement = 1'b0;
            if (state == ERROR) begin
                // Secondary errors cannot replace the first classified error.
                if (commands === 6'b000001 && i_step_accepted === 1'b0 && i_rstb === 1'b1) begin
                    next_state = IDLE;
                    next_active_context = '0;
                    next_pending_context = '0;
                    next_pending_scheduled = 1'b0;
                    next_error_code = SEQ_ERR_NONE;
                    loop_clear = 1'b1;
                end
            end else if (detected_error != SEQ_ERR_NONE) begin
                next_state = ERROR;
                next_error_code = detected_error;
            end else if (i_start_enable === 1'b1) begin
                next_pending_context = i_start_context;
                next_pending_scheduled = 1'b0;
                loop_clear = 1'b1;
                next_state = START_WAIT;
                if (i_candidate_context_valid === 1'b1) begin
                    next_state = ACTIVE;
                    next_active_context = i_start_context;
                    next_event_activated = 1'b1;
                end
            end else if (i_stop_request === 1'b1 || state == STOP_PENDING) begin
                next_state = STOP_PENDING;
                if (i_safe_point === 1'b1) begin
                    next_state = IDLE;
                    next_active_context = '0;
                    next_pending_context = '0;
                    next_pending_scheduled = 1'b0;
                    loop_clear = 1'b1;
                end
            end else if (suspend_command === 1'b1 || state == SUSPEND_PENDING) begin
                if (i_safe_point === 1'b1) next_state = SUSPENDED;
                else next_state = SUSPEND_PENDING;
            end else if (switch_command === 1'b1) begin
                next_pending_context = i_switch_context;
                next_pending_scheduled = 1'b0;
                next_state = SWITCH_PENDING;
                if (i_safe_point === 1'b1) begin
                    next_state = SWITCH_WAIT;
                    if (i_candidate_context_valid === 1'b1) begin
                        next_state = ACTIVE;
                        next_active_context = i_switch_context;
                        next_event_activated = 1'b1;
                        loop_clear = 1'b1;
                    end
                end
            end else if (resume_command === 1'b1) begin
                if (pending_scheduled) next_state = CONTEXT_WAIT;
                else next_state = ACTIVE;
                next_event_activated = !pending_scheduled;
            end else begin
                case (state)
                    START_WAIT, CONTEXT_WAIT, SWITCH_WAIT: begin
                        if (i_candidate_context_valid === 1'b1) begin
                            next_state = ACTIVE;
                            next_active_context = pending_context;
                            next_pending_scheduled = 1'b0;
                            next_event_activated = 1'b1;
                            if (state == SWITCH_WAIT) loop_clear = 1'b1;
                        end
                    end
                    SWITCH_PENDING: begin
                        if (i_safe_point === 1'b1) begin
                            next_state = SWITCH_WAIT;
                            if (i_candidate_context_valid === 1'b1) begin
                                next_state = ACTIVE;
                                next_active_context = pending_context;
                                next_event_activated = 1'b1;
                                loop_clear = 1'b1;
                            end
                        end
                    end
                    ACTIVE: begin
                        if (i_step_accepted === 1'b1) begin
                            if (i_transition_mode == CONTEXT_END) begin
                                next_state = COMPLETED;
                                next_pending_context = '0;
                                next_pending_scheduled = 1'b0;
                                next_event_completed = 1'b1;
                                loop_clear = 1'b1;
                            end else if (scheduled_read) begin
                                next_pending_context = scheduled_context;
                                next_pending_scheduled = 1'b1;
                                next_state = CONTEXT_WAIT;
                                if (i_candidate_context_valid === 1'b1) begin
                                    next_state = ACTIVE;
                                    next_active_context = scheduled_context;
                                    next_pending_scheduled = 1'b0;
                                    next_event_activated = 1'b1;
                                end
                                case (loop_action)
                                    LOOP_LOAD: begin
                                        next_loop_active = 1'b1;
                                        next_loop_owner = active_context;
                                        loop_load = 1'b1;
                                    end
                                    LOOP_DECREMENT: loop_decrement = 1'b1;
                                    LOOP_CLEAR: loop_clear = 1'b1;
                                    default: begin end
                                endcase
                            end
                        end
                    end
                    IDLE, COMPLETED, SUSPENDED: begin end
                    default: begin
                        next_state = ERROR;
                        next_error_code = SEQ_ERR_PROTOCOL;
                    end
                endcase
            end
            if (loop_clear) begin
                next_loop_active = 1'b0;
                next_loop_owner = '0;
            end
            next_event_changed = next_event_activated && next_active_context != active_context;
            control_d = {next_state, next_active_context, next_pending_context, next_pending_scheduled,
                         next_loop_active, next_loop_owner, next_error_code,
                         next_event_activated, next_event_changed, next_event_completed};
        end
    end
endmodule
