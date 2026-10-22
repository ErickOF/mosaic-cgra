`timescale 1ns / 1ps

// One rectangular nest, with safe-point ownership of every accepted launch.
module loop_controller #(
    parameter MAX_LOOP_DEPTH = 4,
    parameter INDEX_WIDTH = 32,
    parameter TRIP_COUNT_WIDTH = 32,
    parameter LINEAR_COUNT_WIDTH = 64,
    parameter II_WIDTH = 8,
    parameter CONTEXT_ID_WIDTH = 8,
    parameter RUN_ID_WIDTH = 8,
    parameter NUM_EVENTS = 16,
    parameter CONFIG_EPOCH_WIDTH = 2,
    parameter SUPPORT_BOUNDED_MODE = 1,
    parameter SUPPORT_SUSPEND = 1,
    parameter SUPPORT_ABORT = 1,
    parameter PROTECT_STATE = 0,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((MAX_LOOP_DEPTH >= 1) === 1'b1) && ( ^ MAX_LOOP_DEPTH !== 1'bx) &&
        ((INDEX_WIDTH >= 1) === 1'b1) && ( ^ INDEX_WIDTH !== 1'bx) &&
        ((TRIP_COUNT_WIDTH >= 1) === 1'b1) && ( ^ TRIP_COUNT_WIDTH !== 1'bx) &&
        ((LINEAR_COUNT_WIDTH >= 1) === 1'b1) && ( ^ LINEAR_COUNT_WIDTH !== 1'bx) &&
        ((II_WIDTH >= 1) === 1'b1) && ( ^ II_WIDTH !== 1'bx) &&
        ((CONTEXT_ID_WIDTH >= 1) === 1'b1) && ( ^ CONTEXT_ID_WIDTH !== 1'bx) &&
        ((RUN_ID_WIDTH >= 1) === 1'b1) && ( ^ RUN_ID_WIDTH !== 1'bx) &&
        ((NUM_EVENTS >= 1) === 1'b1) && ( ^ NUM_EVENTS !== 1'bx) &&
        ((CONFIG_EPOCH_WIDTH >= 2) === 1'b1) && ( ^ CONFIG_EPOCH_WIDTH !== 1'bx) &&
        ((SUPPORT_BOUNDED_MODE === 0) || (SUPPORT_BOUNDED_MODE === 1)) &&
        ((SUPPORT_SUSPEND === 0) || (SUPPORT_SUSPEND === 1)) &&
        ((SUPPORT_ABORT === 0) || (SUPPORT_ABORT === 1)) &&
        ((PROTECT_STATE === 0) || (PROTECT_STATE === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((64'(MAX_LOOP_DEPTH) *
            (64'(INDEX_WIDTH) * 8 + 64'(TRIP_COUNT_WIDTH) * 4 + 64) +
            64'(LINEAR_COUNT_WIDTH) * 8 + 64'(II_WIDTH) * 4 +
            64'(CONTEXT_ID_WIDTH) * 4 + 64'(RUN_ID_WIDTH) * 4 +
            64'(CONFIG_EPOCH_WIDTH) * 4 + 64'(NUM_EVENTS) < 64'd2147483647) === 1'b1),
    localparam int D = PARAMETERS_VALID ? MAX_LOOP_DEPTH : 1,
    localparam int I = PARAMETERS_VALID ? INDEX_WIDTH : 1,
    localparam int T = PARAMETERS_VALID ? TRIP_COUNT_WIDTH : 1,
    localparam int L = PARAMETERS_VALID ? LINEAR_COUNT_WIDTH : 1,
    localparam int P = PARAMETERS_VALID ? II_WIDTH : 1,
    localparam int C = PARAMETERS_VALID ? CONTEXT_ID_WIDTH : 1,
    localparam int R = PARAMETERS_VALID ? RUN_ID_WIDTH : 1,
    localparam int E = PARAMETERS_VALID ? CONFIG_EPOCH_WIDTH : 2,
    localparam int DEPTH_WIDTH = $clog2(D + 1),
    localparam int EVENT_ID_WIDTH = NUM_EVENTS > 1 && PARAMETERS_VALID ? $clog2(NUM_EVENTS) : 1,
    localparam int INDEX_VECTOR_WIDTH = D * I,
    localparam int TRIP_VECTOR_WIDTH = D * T,
    localparam int MODE_WIDTH = loop_controller_pkg::MODE_WIDTH,
    localparam int COMPARE_WIDTH = loop_controller_pkg::COMPARE_WIDTH,
    localparam int CONTROL_WIDTH = loop_controller_pkg::CONTROL_WIDTH
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_flush,
    input logic i_error_clear,
    input logic i_config_valid,
    output logic o_config_ready,
    input logic [DEPTH_WIDTH-1:0] i_config_depth,
    input logic [D*MODE_WIDTH-1:0] i_config_level_mode,
    input logic [INDEX_VECTOR_WIDTH-1:0] i_config_initial,
    input logic [INDEX_VECTOR_WIDTH-1:0] i_config_bound,
    input logic [INDEX_VECTOR_WIDTH-1:0] i_config_step,
    input logic [TRIP_VECTOR_WIDTH-1:0] i_config_trip_count,
    input logic [D*COMPARE_WIDTH-1:0] i_config_compare,
    input logic [P-1:0] i_config_initiation_interval,
    input logic [C-1:0] i_config_context_id,
    input logic i_config_completion_event_enable,
    input logic [EVENT_ID_WIDTH-1:0] i_config_completion_event_id,
    output logic o_config_accepted,
    output logic o_config_rejected,
    output logic o_config_validating,
    input logic i_start_valid,
    output logic o_start_ready,
    input logic [C-1:0] i_start_context_id,
    input logic [R-1:0] i_start_run_id,
    output logic o_start_accepted,
    output logic o_start_rejected,
    input logic i_control_valid,
    output logic o_control_ready,
    input logic [CONTROL_WIDTH-1:0] i_control_command,
    input logic [C-1:0] i_control_context_id,
    input logic [R-1:0] i_control_run_id,
    output logic o_control_accepted,
    output logic o_control_rejected,
    input logic i_execution_quiescent,
    output logic o_quiesce_request,
    output logic o_iteration_valid,
    input logic i_iteration_ready,
    output logic [INDEX_VECTOR_WIDTH-1:0] o_iteration_index,
    output logic [TRIP_VECTOR_WIDTH-1:0] o_iteration_ordinal,
    output logic [D-1:0] o_iteration_first_mask,
    output logic [D-1:0] o_iteration_last_mask,
    output logic [D-1:0] o_iteration_active_mask,
    output logic [L-1:0] o_iteration_linear,
    output logic [C-1:0] o_iteration_context_id,
    output logic [R-1:0] o_iteration_run_id,
    output logic [E-1:0] o_iteration_epoch,
    output logic o_completion_valid,
    input logic i_completion_ready,
    output logic o_completion_event_enable,
    output logic [EVENT_ID_WIDTH-1:0] o_completion_event_id,
    output logic [C-1:0] o_completion_context_id,
    output logic [R-1:0] o_completion_run_id,
    output logic [loop_controller_pkg::COMPLETION_WIDTH-1:0] o_completion_status,
    output logic [L-1:0] o_completion_iterations,
    output logic o_configured,
    output logic o_active,
    output logic o_pause_pending,
    output logic o_abort_pending,
    output logic o_completion_pending,
    output logic o_suspended,
    output logic [DEPTH_WIDTH-1:0] o_current_depth,
    output logic [C-1:0] o_current_context_id,
    output logic [R-1:0] o_current_run_id,
    output logic [E-1:0] o_current_epoch,
    output logic [L-1:0] o_total_iterations,
    output logic [P-1:0] o_pacing_count,
    output logic o_idle,
    output logic o_quiescent,
    output logic o_error,
    output logic o_fatal_error,
    output logic [loop_controller_pkg::ERROR_WIDTH-1:0] o_error_code,
    output logic o_event_iteration_transfer,
    output logic o_event_inner_wrap,
    output logic [D-1:0] o_event_outer_wrap,
    output logic o_event_run_complete,
    output logic o_event_iteration_stall,
    output logic o_event_pause,
    output logic o_event_resume,
    output logic o_event_abort
);
    import loop_controller_pkg::*;

    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        loop_controller_parameters_must_be_valid invalid_parameters ();
    end else begin : g_controller
        localparam int W = I + T + 2;

        // These records depend on module widths and deliberately remain local.
        typedef struct packed {
            logic [DEPTH_WIDTH-1:0] depth;
            logic [D*MODE_WIDTH-1:0] mode;
            logic [INDEX_VECTOR_WIDTH-1:0] initial_value;
            logic [INDEX_VECTOR_WIDTH-1:0] bound;
            logic [INDEX_VECTOR_WIDTH-1:0] step;
            logic [TRIP_VECTOR_WIDTH-1:0] trips;
            logic [D*COMPARE_WIDTH-1:0] compare;
            logic [P-1:0] interval;
            logic [C-1:0] context_id;
            logic event_enable;
            logic [EVENT_ID_WIDTH-1:0] event_id;
            logic [L-1:0] total;
        } configuration_t;

        typedef struct packed {
            loop_state_t state;
            logic configured;
            logic validating;
            logic candidate_known;
            logic presented;
            logic [E-1:0] epoch;
            logic [R-1:0] run_id;
            logic [INDEX_VECTOR_WIDTH-1:0] indices;
            logic [TRIP_VECTOR_WIDTH-1:0] ordinals;
            logic [L-1:0] accepted;
            logic [P-1:0] pacing;
            loop_completion_t completion;
            logic config_accepted;
            logic config_rejected;
            logic start_accepted;
            logic start_rejected;
            logic control_accepted;
            logic control_rejected;
            logic transfer;
            logic [D-1:0] wraps;
            logic stall;
            logic complete;
            logic pause;
            logic resume;
            logic abort_run;
        } state_t;

        configuration_t candidate;
        configuration_t incoming;
        // Retain the entire accepted record for parity. Some validated fields
        // (bound/mode/compare) have no execution fanout in the unprotected profile.
        /* verilator lint_off UNUSEDSIGNAL */
        configuration_t configuration;
        /* verilator lint_on UNUSEDSIGNAL */
        configuration_t installed_next;
        state_t q;
        state_t d;
        logic [D-1:0] active_mask;
        logic [D-1:0] first_mask;
        logic [D-1:0] last_mask;
        logic invariant_error;
        loop_error_t detected;
        loop_error_t validation_error;
        logic [L-1:0] candidate_total;
        logic legal_control;
        logic legal_start;
        wire candidate_corrupt;
        wire config_corrupt;
        wire state_corrupt;
        wire fatal;
        wire [ERROR_WIDTH-1:0] sticky_error;
        wire reset_b = i_rstb !== 1'b0;
        wire clock_enabled = i_rstb === 1'b1;
        wire flushing = clock_enabled && (i_flush === 1'b1);
        wire running = clock_enabled && (i_flush === 1'b0);
        wire corrupt = state_corrupt || (q.configured && config_corrupt) ||
            (q.validating && q.candidate_known && candidate_corrupt);
        wire safe = running&&!fatal&&!corrupt&&!invariant_error;
        wire idle = (q.state == LOOP_IDLE) &&!q.validating;
        wire config_take = o_config_ready && (i_config_valid === 1'b1);
        wire start_take = o_start_ready && (i_start_valid === 1'b1);
        wire control_take = o_control_ready && (i_control_valid === 1'b1);
        wire transfer = o_iteration_valid && (i_iteration_ready === 1'b1);
        wire record_take = o_completion_valid && (i_completion_ready === 1'b1);
        wire last_token = (&(last_mask | ~active_mask));
        wire state_enable = flushing || (safe && (d !== q));
        wire config_enable = flushing ||
            (safe && q.validating && (validation_error == LOOP_ERR_NONE));
        wire error_enable = clock_enabled && (flushing ||
            (running && ((idle && (i_error_clear === 1'b1)) ||
            ((sticky_error == LOOP_ERR_NONE) && (detected != LOOP_ERR_NONE)))));
        wire [ERROR_WIDTH-1:0] error_next =
            flushing || (idle && (i_error_clear === 1'b1)) ?
            ERROR_WIDTH'(LOOP_ERR_NONE) : detected;
        wire [TRIP_VECTOR_WIDTH-1:0] ordinals = q.ordinals;
        wire [INDEX_VECTOR_WIDTH-1:0] indices = q.indices;
        wire [TRIP_VECTOR_WIDTH-1:0] trips = configuration.trips;
        wire [INDEX_VECTOR_WIDTH-1:0] initials = configuration.initial_value;
        wire [INDEX_VECTOR_WIDTH-1:0] steps = configuration.step;

        // Parity is compiled out when PROTECT_STATE=0. Data and parity use the
        // same enable, so idle holding and fault checks do not rewrite state.
        event_barrier_state #(
            .WIDTH($bits(state_t)), .PROTECTED(1'(PROTECT_STATE)), .ASYNC_RESET(1'(ASYNC_RESET))
        ) u_state (
            .i_clk(i_clk), .i_rstb(reset_b), .i_enable(state_enable),
            .i_data(d), .o_data(q), .o_corrupt(state_corrupt)
        );

        event_barrier_state #(
            .WIDTH($bits(configuration_t)), .PROTECTED(1'(PROTECT_STATE)),
            .ASYNC_RESET(1'(ASYNC_RESET))
        ) u_configuration (
            .i_clk(i_clk), .i_rstb(reset_b), .i_enable(config_enable),
            .i_data(installed_next), .o_data(configuration), .o_corrupt(config_corrupt)
        );

        event_barrier_state #(
            .WIDTH($bits(configuration_t)),
            .PROTECTED(1'(PROTECT_STATE)),
            .ASYNC_RESET(1'(ASYNC_RESET))
        ) u_candidate (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(flushing || config_take),
            .i_data(flushing ? {$bits(configuration_t){1'b0}} : incoming),
            .o_data(candidate),
            .o_corrupt(candidate_corrupt)
        );

        dff #(.WIDTH(1), .ASYNC_RESET(1'(ASYNC_RESET))) u_fatal (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(running && (corrupt || invariant_error)),
            .i_d(1'b1),
            .o_q(fatal)
        );

        dff #(.WIDTH(ERROR_WIDTH), .ASYNC_RESET(1'(ASYNC_RESET))) u_error (
            .i_clk(i_clk),
            .i_rstb(reset_b),
            .i_enable(error_enable),
            .i_d(error_next),
            .o_q(sticky_error)
        );

        // Last and post are widened before multiplication/addition. Counted
        // post is explicitly unused; bounded post is compared without narrowing.
        function automatic logic compare_value(
            input logic signed [W-1:0] value,
            input logic signed [W-1:0] bound,
            input logic [COMPARE_WIDTH-1:0] comparison
        );
            case (comparison)
                LOOP_COMPARE_LT: compare_value = value < bound;
                LOOP_COMPARE_LE: compare_value = value <= bound;
                LOOP_COMPARE_GT: compare_value = value > bound;
                LOOP_COMPARE_GE: compare_value = value >= bound;
                default: compare_value = 1'b0;
            endcase
        endfunction

        always_comb begin : capture_fields
            incoming = '0;
            incoming.depth = i_config_depth;
            incoming.mode = i_config_level_mode;
            incoming.initial_value = i_config_initial;
            incoming.bound = i_config_bound;
            incoming.step = i_config_step;
            incoming.trips = i_config_trip_count;
            incoming.compare = i_config_compare;
            incoming.interval = i_config_initiation_interval;
            incoming.context_id = i_config_context_id;
            incoming.event_enable = i_config_completion_event_enable;
            incoming.event_id = i_config_completion_event_id;
        end

        always_comb begin : validate_candidate
            logic zero_trip;
            logic [L+T:0] product_value;
            logic [T-1:0] count;
            logic [MODE_WIDTH-1:0] mode;
            logic [COMPARE_WIDTH-1:0] comparison;
            logic signed [W-1:0] first_value;
            logic signed [W-1:0] step_value;
            logic signed [W-1:0] bound_value;
            logic signed [W-1:0] last_value;
            logic signed [W-1:0] post_value;
            logic signed [W-1:0] count_value;
            logic [I-1:0] narrowed;
            loop_error_t level_error;
            // Plain vectors avoid tool-dependent variable selects of structs.
            logic [TRIP_VECTOR_WIDTH-1:0] candidate_trips;
            logic [INDEX_VECTOR_WIDTH-1:0] candidate_initials;
            logic [INDEX_VECTOR_WIDTH-1:0] candidate_steps;
            logic [INDEX_VECTOR_WIDTH-1:0] candidate_bounds;
            logic [D*MODE_WIDTH-1:0] candidate_modes;
            logic [D*COMPARE_WIDTH-1:0] candidate_compares;
            candidate_trips = candidate.trips;
            candidate_initials = candidate.initial_value;
            candidate_steps = candidate.step;
            candidate_bounds = candidate.bound;
            candidate_modes = candidate.mode;
            candidate_compares = candidate.compare;
            validation_error = LOOP_ERR_NONE;
            candidate_total = L'(1);
            zero_trip = 1'b0;
            product_value = '0;
            count = '0;
            mode = '0;
            comparison = '0;
            first_value = '0;
            step_value = '0;
            bound_value = '0;
            last_value = '0;
            post_value = '0;
            count_value = '0;
            narrowed = '0;
            level_error = LOOP_ERR_NONE;

            if (!q.candidate_known || ( ^ candidate === 1'bx))
                validation_error = LOOP_ERR_UNKNOWN;
            else if (candidate.depth < 1 || int'(candidate.depth) > D)
                validation_error = LOOP_ERR_DEPTH;
            else if (candidate.interval == 0)
                validation_error = LOOP_ERR_INTERVAL;
            else if (candidate.event_enable && int'(candidate.event_id) >= NUM_EVENTS)
                validation_error = LOOP_ERR_EVENT;

            // Scan zero first: a zero product cannot overflow even if a lower
            // prefix would exceed LINEAR_COUNT_WIDTH.
            for (int level = 0; level < D; level++) begin
                if (level < int'(candidate.depth) && candidate_trips[level*T+:T] == 0)
                    zero_trip = 1'b1;
            end

            for (int level = 0; level < D; level++) begin
                count = candidate_trips[level*T+:T];
                mode = candidate_modes[level*MODE_WIDTH+:MODE_WIDTH];
                comparison = candidate_compares[level*COMPARE_WIDTH+:COMPARE_WIDTH];
                first_value = W'($signed(candidate_initials[level*I+:I]));
                step_value = W'($signed(candidate_steps[level*I+:I]));
                bound_value = W'($signed(candidate_bounds[level*I+:I]));
                count_value = $signed({{(W-T){1'b0}}, count});
                last_value = first_value + (count_value - 1) * step_value;
                post_value = first_value + count_value * step_value;
                narrowed = last_value[I-1:0];
                level_error = LOOP_ERR_NONE;

                if (level < int'(candidate.depth)) begin
                    if ((mode != LOOP_COUNTED) &&
                        ((mode != LOOP_BOUNDED) || (SUPPORT_BOUNDED_MODE == 0)))
                        level_error = LOOP_ERR_MODE;
                    else if (comparison > LOOP_COMPARE_GE)
                        level_error = LOOP_ERR_COMPARE;
                    else if ((count != 0) && (step_value == 0))
                        level_error = LOOP_ERR_STEP;
                    else if ((count != 0) && (last_value != W'($signed(narrowed))))
                        level_error = LOOP_ERR_INDEX;
                    else if ((SUPPORT_BOUNDED_MODE == 1) && (mode == LOOP_BOUNDED)) begin
                        if (count == 0) begin
                            if (compare_value(first_value, bound_value, comparison))
                                level_error = LOOP_ERR_BOUNDS;
                        end else if (!compare_value(first_value, bound_value, comparison) ||
                            !compare_value(last_value, bound_value, comparison) ||
                            compare_value(post_value, bound_value, comparison) ||
                            ((comparison <= LOOP_COMPARE_LE) && (step_value < 0)) ||
                            ((comparison >= LOOP_COMPARE_GT) && (step_value > 0)))
                            level_error = LOOP_ERR_BOUNDS;
                    end

                    if (!zero_trip) begin
                        product_value = {{(T+1){1'b0}}, candidate_total} * (L + T + 1)'(count);
                        if ((product_value >> L) != 0 && level_error == LOOP_ERR_NONE)
                            level_error = LOOP_ERR_PRODUCT;
                        candidate_total = product_value[L-1:0];
                    end
                end else if ({count, mode, comparison, candidate_initials[level*I+:I],
                    candidate_steps[level*I+:I], candidate_bounds[level*I+:I]} != '0)
                    level_error = LOOP_ERR_INACTIVE;
                if (validation_error == LOOP_ERR_NONE)
                    validation_error = level_error;
            end

            if (zero_trip)
                candidate_total = '0;

            installed_next = candidate;
            installed_next.total = candidate_total;

            if (flushing)
                installed_next = '0;
        end

        // Runtime checks use widened arithmetic too. They diagnose a broken
        // live coordinate even in the unprotected profile; parity adds coverage
        // of configuration, control, ownership and inactive state corruption.
        always_comb begin : live_invariants
            logic signed [W-1:0] expected_index;
            logic [T-1:0] ordinal;
            active_mask = '0;
            first_mask = '0;
            last_mask = '0;
            invariant_error = ( ^ q === 1'bx) || (q.state > LOOP_RECORD) ||
                ((q.state != LOOP_IDLE) &&!q.configured);
            expected_index = '0;
            ordinal = '0;

            if (q.configured && (q.state != LOOP_IDLE)) begin
                if (q.accepted > configuration.total || q.state > LOOP_RECORD)
                    invariant_error = 1'b1;

                for (int level = 0; level < D; level++) begin
                    ordinal = ordinals[level*T+:T];

                    if (level < int'(configuration.depth)) begin
                        active_mask[level] = 1'b1;
                        first_mask[level] = ordinal == 0;
                        last_mask[level] = ordinal == (trips[level*T+:T] - T'(1));
                        expected_index = W'($signed(initials[level*I+:I])) +
                            W'({1'b0, ordinal}) * W'($signed(steps[level*I+:I]));

                        if (configuration.total != 0 &&
                            ((ordinal >= trips[level*T+:T]) ||
                            (expected_index != W'($signed(indices[level*I+:I])))))
                            invariant_error = 1'b1;
                    end else if ({ordinal, indices[level*I+:I]} != '0)
                        invariant_error = 1'b1;
                end

                if ((q.state == LOOP_ISSUE) && q.accepted >= configuration.total)
                    invariant_error = 1'b1;
            end
        end

        always_comb begin : interface_outputs
            legal_start = q.configured &&
                (i_start_context_id === configuration.context_id) &&
                ( ^ {i_start_context_id, i_start_run_id} !== 1'bx);
            legal_control =
                ( ^ {i_control_context_id, i_control_run_id, i_control_command} !== 1'bx) &&
                (i_control_context_id == configuration.context_id) &&
                (i_control_run_id == q.run_id) &&
                (((i_control_command == LOOP_PAUSE) && (SUPPORT_SUSPEND == 1) &&
                    (q.state == LOOP_ISSUE)) ||
                 ((i_control_command == LOOP_RESUME) && (SUPPORT_SUSPEND == 1) &&
                    (q.state == LOOP_SUSPENDED)) ||
                 ((i_control_command == LOOP_ABORT) && (SUPPORT_ABORT == 1) &&
                    ((q.state == LOOP_ISSUE) || (q.state == LOOP_PAUSE_WAIT) ||
                    (q.state == LOOP_SUSPENDED))));
            // Start > control > configuration arbitration; invalid requests are
            // consumed/rejected when otherwise idle, including unconfigured start.
            o_start_ready = safe && idle;
            o_control_ready = safe&&!q.validating && (q.state != LOOP_RECORD) &&
                ((i_start_valid === 1'b0) ||!idle);
            o_config_ready = safe && idle && (i_start_valid === 1'b0) &&
                (i_control_valid === 1'b0);
            o_config_validating = safe && q.validating;
            o_config_accepted = safe && q.config_accepted;
            o_config_rejected = safe && q.config_rejected;
            o_start_accepted = safe && q.start_accepted;
            o_start_rejected = safe && q.start_rejected;
            o_control_accepted = safe && q.control_accepted;
            o_control_rejected = safe && q.control_rejected;
            o_iteration_valid = safe &&
                (((q.state == LOOP_ISSUE) && (q.pacing == 0)) ||
                (((q.state == LOOP_PAUSE_WAIT) || (q.state == LOOP_ABORT_WAIT)) && q.presented));
            o_iteration_index = o_iteration_valid ? indices : '0;
            o_iteration_ordinal = o_iteration_valid ? ordinals : '0;
            o_iteration_first_mask = o_iteration_valid ? first_mask : '0;
            o_iteration_last_mask = o_iteration_valid ? last_mask : '0;
            o_iteration_active_mask = o_iteration_valid ? active_mask : '0;
            o_iteration_linear = o_iteration_valid ? q.accepted : '0;
            o_iteration_context_id = o_iteration_valid ? configuration.context_id : '0;
            o_iteration_run_id = o_iteration_valid ? q.run_id : '0;
            o_iteration_epoch = o_iteration_valid ? q.epoch : '0;
            o_completion_valid = safe && (q.state == LOOP_RECORD);
            o_completion_event_enable = o_completion_valid && configuration.event_enable;
            o_completion_event_id = o_completion_valid ? configuration.event_id : '0;
            o_completion_context_id = o_completion_valid ? configuration.context_id : '0;
            o_completion_run_id = o_completion_valid ? q.run_id : '0;
            o_completion_status = o_completion_valid ? q.completion : '0;
            o_completion_iterations = o_completion_valid ? q.accepted : '0;
            o_quiesce_request = safe && ((q.state == LOOP_COMPLETE_WAIT) ||
                (((q.state == LOOP_PAUSE_WAIT) || (q.state == LOOP_ABORT_WAIT)) &&!q.presented));
            o_configured = safe && q.configured;
            o_active = safe && (q.state != LOOP_IDLE) && (q.state != LOOP_SUSPENDED) &&
                (q.state != LOOP_RECORD);
            o_pause_pending = safe && (q.state == LOOP_PAUSE_WAIT);
            o_abort_pending = safe && (q.state == LOOP_ABORT_WAIT);
            o_completion_pending = safe && (q.state == LOOP_COMPLETE_WAIT);
            o_suspended = safe && (q.state == LOOP_SUSPENDED);
            o_current_depth = o_configured ? configuration.depth : '0;
            o_current_context_id = o_configured ? configuration.context_id : '0;
            o_current_run_id = safe && (q.state != LOOP_IDLE) ? q.run_id : '0;
            o_current_epoch = clock_enabled&&!corrupt&&!invariant_error ? q.epoch : '0;
            o_total_iterations = o_configured ? configuration.total : '0;
            o_pacing_count = safe && (q.state != LOOP_IDLE) ? q.pacing : '0;
            o_idle = safe && idle;
            o_quiescent = o_idle&&!config_take&&!start_take&&!control_take;
            o_error = clock_enabled && (sticky_error != LOOP_ERR_NONE);
            o_fatal_error = clock_enabled && fatal;
            o_error_code = clock_enabled ? sticky_error : ERROR_WIDTH'(LOOP_ERR_NONE);
            o_event_iteration_transfer = safe && q.transfer;
            o_event_inner_wrap = safe && q.wraps[0];
            o_event_outer_wrap = safe ? q.wraps : '0;
            o_event_iteration_stall = safe && q.stall;
            o_event_run_complete = safe && q.complete;
            o_event_pause = safe && q.pause;
            o_event_resume = safe && q.resume;
            o_event_abort = safe && q.abort_run;
        end

        always_comb begin : next_state
            logic carry;
            logic [D-1:0] wraps;
            logic [INDEX_VECTOR_WIDTH-1:0] next_indices;
            logic [TRIP_VECTOR_WIDTH-1:0] next_ordinals;
            d = q;
            detected = LOOP_ERR_NONE;
            carry = 1'b0;
            next_indices = indices;
            next_ordinals = ordinals;
            d.config_accepted = 1'b0;
            d.config_rejected = 1'b0;
            d.start_accepted = 1'b0;
            d.start_rejected = 1'b0;
            d.control_accepted = 1'b0;
            d.control_rejected = 1'b0;
            d.transfer = transfer;
            wraps = '0;
            d.stall = o_iteration_valid && (i_iteration_ready === 1'b0);
            d.complete = 1'b0;
            d.pause = 1'b0;
            d.resume = 1'b0;
            d.abort_run = 1'b0;

            if (config_take) begin
                d.validating = 1'b1;
                // An intentionally unknown request is a recoverable rejection,
                // while corruption of an originally known candidate is fatal.
                d.candidate_known = ( ^ incoming !== 1'bx);
            end

            if (q.validating) begin
                d.validating = 1'b0;
                if (validation_error == LOOP_ERR_NONE) begin
                    d.configured = 1'b1;
                    d.epoch = q.epoch + E'(1);
                    d.config_accepted = 1'b1;
                end else begin
                    d.config_rejected = 1'b1;
                    detected = validation_error;
                end
            end

            if (start_take) begin
                if (legal_start) begin
                    d.run_id = i_start_run_id;
                    d.indices = initials;
                    d.ordinals = '0;
                    d.accepted = '0;
                    d.pacing = '0;
                    d.start_accepted = 1'b1;
                    d.state = LOOP_ISSUE;
                    if (configuration.total == 0) begin
                        d.state = LOOP_RECORD;
                        d.completion = LOOP_COMPLETE;
                        d.complete = 1'b1;
                    end
                end else begin
                    d.start_rejected = 1'b1;
                    detected = LOOP_ERR_START;
                end
            end

            if ((q.state == LOOP_ISSUE) && (q.pacing != 0))
                d.pacing = q.pacing - P'(1);

            if (transfer) begin
                d.accepted = q.accepted + L'(1);
                d.pacing = configuration.interval - P'(1);
                d.presented = 1'b0;

                if (last_token) begin
                    if (q.state != LOOP_ABORT_WAIT)
                        d.state = LOOP_COMPLETE_WAIT;
                end else begin
                    carry = 1'b1;
                    for (int level = 0; level < D; level++) begin
                        if (carry && active_mask[level]) begin
                            if (last_mask[level]) begin
                                next_indices[level*I+:I] = initials[level*I+:I];
                                next_ordinals[level*T+:T] = '0;
                                wraps[level] = 1'b1;
                            end else begin
                                next_indices[level*I+:I] = indices[level*I+:I] + steps[level*I+:I];
                                next_ordinals[level*T+:T] = ordinals[level*T+:T] + T'(1);
                                carry = 1'b0;
                            end
                        end
                    end

                    d.indices = next_indices;
                    d.ordinals = next_ordinals;
                end
            end

            // A previously visible token belongs to the downstream consumer.
            // A stop command cannot revoke it, even when ready stays low.
            if (control_take) begin
                if (legal_control) begin
                    d.control_accepted = 1'b1;

                    case (i_control_command)
                        LOOP_PAUSE: begin
                            if (!(transfer && last_token)) begin
                                d.state = LOOP_PAUSE_WAIT;
                                d.presented = o_iteration_valid&&!transfer;
                            end
                        end
                        LOOP_RESUME: begin
                            d.state = LOOP_ISSUE;
                            d.resume = 1'b1;
                        end
                        LOOP_ABORT: begin
                            d.state = LOOP_ABORT_WAIT;
                            d.presented = o_iteration_valid&&!transfer;
                        end
                        default: begin end
                    endcase
                end else begin
                    d.control_rejected = 1'b1;
                    detected = LOOP_ERR_CONTROL;
                end
            end

            if (o_quiesce_request && (i_execution_quiescent === 1'b1)) begin
                if (q.state == LOOP_PAUSE_WAIT) begin
                    d.state = LOOP_SUSPENDED;
                    d.pause = 1'b1;
                    // An abort accepted at the same safe edge supersedes pause.
                    if (control_take && legal_control && (i_control_command == LOOP_ABORT)) begin
                        d.state = LOOP_RECORD;
                        d.completion = LOOP_ABORTED;
                        d.abort_run = 1'b1;
                        d.pause = 1'b0;
                    end
                end else begin
                    d.state = LOOP_RECORD;
                    d.completion = q.state == LOOP_ABORT_WAIT ? LOOP_ABORTED : LOOP_COMPLETE;
                    d.complete = q.state == LOOP_COMPLETE_WAIT;
                    d.abort_run = q.state == LOOP_ABORT_WAIT;
                end
            end

            if (record_take) begin
                d.state = LOOP_IDLE;
                d.run_id = '0;
                d.indices = '0;
                d.ordinals = '0;
                d.accepted = '0;
                d.pacing = '0;
                d.completion = LOOP_COMPLETE;
            end
            if ( ^ {i_rstb, i_flush, i_error_clear, i_config_valid, i_start_valid,
                i_control_valid, i_iteration_ready, i_completion_ready,
                i_execution_quiescent} === 1'bx)
                detected = LOOP_ERR_UNKNOWN;
            if (invariant_error)
                detected = LOOP_ERR_INVARIANT;
            if (corrupt)
                detected = LOOP_ERR_CORRUPT;
            d.wraps = wraps;
            if (flushing) begin
                d = '0;
                d.epoch = q.epoch + E'(1);
            end
        end
`ifdef MOSAIC_LOOP_CONTROLLER_ASSERTIONS
        // Verification sources are never part of synthesis or netlist builds.
        localparam int TOKEN_BITS = INDEX_VECTOR_WIDTH + TRIP_VECTOR_WIDTH + 3 * D + L + C + R + E;
        localparam int RECORD_BITS = 1 + EVENT_ID_WIDTH + C + R + COMPLETION_WIDTH + L;
        wire [TOKEN_BITS-1:0] assertion_token = {o_iteration_index, o_iteration_ordinal,
            o_iteration_first_mask, o_iteration_last_mask, o_iteration_active_mask,
            o_iteration_linear, o_iteration_context_id, o_iteration_run_id, o_iteration_epoch};
        wire [RECORD_BITS-1:0] assertion_record = {o_completion_event_enable,
            o_completion_event_id, o_completion_context_id, o_completion_run_id,
            o_completion_status, o_completion_iterations};
        wire [15:0] assertion_controls = {o_config_ready, o_config_validating,
            o_start_ready, o_control_ready, o_iteration_valid, o_completion_valid,
            o_quiesce_request, o_configured, o_active, o_pause_pending, o_abort_pending,
            o_completion_pending, o_suspended, o_idle, o_quiescent, o_fatal_error};
        loop_controller_assertions #(
            .TOKEN_WIDTH(TOKEN_BITS),
            .RECORD_WIDTH(RECORD_BITS),
            .COUNT_WIDTH(L),
            .PACE_WIDTH(P)
        ) u_assertions (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_flush(i_flush),
            .i_fault(fatal || corrupt || invariant_error),
            .i_valid(o_iteration_valid),
            .i_ready(i_iteration_ready),
            .i_token(assertion_token),
            .i_record_valid(o_completion_valid),
            .i_record_ready(i_completion_ready),
            .i_record(assertion_record),
            .i_transfer_event(o_event_iteration_transfer),
            .i_quiesce(o_quiesce_request),
            .i_execution_quiescent(i_execution_quiescent),
            .i_pause_event(o_event_pause),
            .i_complete_event(o_event_run_complete),
            .i_abort_event(o_event_abort),
            .i_zero_trip(configuration.total == 0),
            .i_linear(o_iteration_linear),
            .i_total(o_total_iterations),
            .i_pacing(o_pacing_count),
            .i_controls(assertion_controls)
        );
`endif
    end
endmodule
