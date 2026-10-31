`timescale 1ns / 1ps
`default_nettype none
// Whole-cluster ownership and tagged lifecycle fanout. No scheduling policy lives here.
module array_control #(
    parameter NUM_CLUSTERS = 2,
    parameter TIMEOUT_CYCLES = 65535,
    parameter logic [255:0] ARCHITECTURE_HASH = '0,
    localparam bit VALID = ((NUM_CLUSTERS >= 1 && NUM_CLUSTERS <= 4) === 1'b1) &&
        (^NUM_CLUSTERS !== 1'bx) && (^ARCHITECTURE_HASH !== 1'bx) &&
        ((TIMEOUT_CYCLES >= 16) === 1'b1) &&
        ((64'(TIMEOUT_CYCLES) <= 64'hffffff) === 1'b1),
    localparam int N = VALID ? NUM_CLUSTERS : 1
) (
    input wire i_clk,
    input wire i_rstb,
    input wire i_test_mode,
    input wire i_runtime_valid,
    output wire o_runtime_ready,
    input wire [4:0] i_runtime_command,
    input wire [15:0] i_runtime_owner_id,
    input wire [15:0] i_runtime_kernel_id,
    input wire [31:0] i_runtime_array_package_id,
    input wire [255:0] i_runtime_manifest_hash,
    input wire [N-1:0] i_runtime_cluster_mask,
    input wire [15:0] i_runtime_allocation_generation,
    input wire [7:0] i_runtime_execution_epoch,
    input wire [7:0] i_runtime_context_id,
    input wire [N*32-1:0] i_runtime_local_package_ids,
    input wire [N*96-1:0] i_runtime_context_versions,
    input wire [7:0] i_runtime_mapping_variant,
    input wire [7:0] i_runtime_qos_profile,
    input wire [7:0] i_runtime_power_profile,
    input wire [7:0] i_runtime_flags,
    input wire [15:0] i_runtime_tag,
    output wire o_runtime_response_valid,
    input wire i_runtime_response_ready,
    output wire [4:0] o_runtime_response_command,
    output wire [3:0] o_runtime_response_status,
    output wire [7:0] o_runtime_response_error_code,
    output wire [N-1:0] o_runtime_response_cluster_mask,
    output wire [15:0] o_runtime_response_tag,
    output wire [3:0] o_runtime_response_array_state,
    input wire [N-1:0] i_cluster_ready,
    output wire [N-1:0] o_cluster_valid,
    output wire [3:0] o_cluster_command,
    input wire [N-1:0] i_cluster_response_valid,
    output wire [N-1:0] o_cluster_response_ready,
    input wire [N*4-1:0] i_cluster_response_command,
    input wire [N*16-1:0] i_cluster_response_tag,
    input wire [N*8-1:0] i_cluster_response_error,
    input wire [N-1:0] i_cluster_prepared,
    output wire [N-1:0] o_cluster_commit_valid,
    input wire [N-1:0] i_cluster_commit_ready,
    input wire [N-1:0] i_cluster_commit_complete,
    input wire [N-1:0] i_cluster_commit_error,
    input wire [N-1:0] i_cluster_error,
    input wire [N-1:0] i_cluster_quiescent,
    input wire [N-1:0] i_completion,
    input wire i_event_error,
    input wire i_network_error,
    input wire i_network_idle,
    input wire i_network_configured,
    input wire i_events_empty,
    output wire [N-1:0] o_allocated,
    output wire [N-1:0] o_running,
    output wire [N-1:0] o_fatal,
    output wire [N-1:0] o_completion_mask,
    output wire [N-1:0] o_terminal_valid,
    input wire [N-1:0] i_terminal_ready,
    output wire [N*N-1:0] o_group_masks,
    output wire [N*16-1:0] o_owner_ids,
    output wire [N*16-1:0] o_kernel_ids,
    output wire [N*32-1:0] o_array_package_ids,
    output wire [N*32-1:0] o_local_package_ids,
    output wire [N*8-1:0] o_context_ids,
    output wire [N*8-1:0] o_execution_epochs,
    output wire [N*16-1:0] o_allocation_generations,
    output wire [N*96-1:0] o_commit_versions,
    output wire [15:0] o_command_owner,
    output wire [15:0] o_command_kernel,
    output wire [15:0] o_command_tag,
    output wire [3:0] o_array_state,
    output wire [7:0] o_first_error,
    output wire o_busy
);
    import array_pkg::*;

    if (!VALID) begin : g_invalid
        array_control_parameters_must_be_valid invalid_parameters ();
    end else begin : g_control
        // These records depend on N and therefore remain in the parameterized RTL.
        typedef struct packed {
            logic [N-1:0] allocated;
            logic [N-1:0] running;
            logic [N-1:0] fatal;
            logic [N-1:0] done;
            logic [N-1:0] reported;
            logic [N*N-1:0] groups;
            logic [N*3-1:0] stage;
            logic [N*16-1:0] owner;
            logic [N*16-1:0] kernel;
            logic [N*32-1:0] package_id;
            logic [N*32-1:0] local_package;
            logic [N*8-1:0] context_id;
            logic [N*8-1:0] epoch;
            logic [N*16-1:0] generation;
            logic [N*96-1:0] versions;
            logic [15:0] serial;
            array_phase_t phase;
            logic [4:0] command;
            logic [3:0] native_command;
            logic [N-1:0] target;
            logic [N-1:0] original_target;
            logic [N-1:0] sent;
            logic [N-1:0] ack;
            logic [N-1:0] succeeded;
            logic [15:0] command_owner;
            logic [15:0] command_kernel;
            logic [15:0] tag;
            logic response;
            logic [7:0] error_code;
            logic [7:0] first_error;
            logic [3:0] response_state;
            logic rollback;
        } state_t;

        state_t q;
        state_t n;
        wire [N-1:0] stored_allocated = q.allocated;
        logic [N-1:0] next_allocated;
        wire [N*8-1:0] stored_context_id = q.context_id;
        logic [N*8-1:0] next_context_id;
        wire [N-1:0] stored_done = q.done;
        logic [N-1:0] next_done;
        wire [N*8-1:0] stored_epoch = q.epoch;
        logic [N*8-1:0] next_epoch;
        wire [N-1:0] stored_fatal = q.fatal;
        logic [N-1:0] next_fatal;
        wire [N*16-1:0] stored_generation = q.generation;
        logic [N*16-1:0] next_generation;
        wire [N*N-1:0] stored_groups = q.groups;
        logic [N*N-1:0] next_groups;
        wire [N*16-1:0] stored_kernel = q.kernel;
        logic [N*16-1:0] next_kernel;
        wire [N*32-1:0] stored_local_package = q.local_package;
        logic [N*32-1:0] next_local_package;
        wire [N*16-1:0] stored_owner = q.owner;
        logic [N*16-1:0] next_owner;
        wire [N*32-1:0] stored_package_id = q.package_id;
        logic [N*32-1:0] next_package_id;
        wire [N-1:0] stored_reported = q.reported;
        logic [N-1:0] next_reported;
        wire [N-1:0] stored_running = q.running;
        logic [N-1:0] next_running;
        wire [N*3-1:0] stored_stage = q.stage;
        logic [N*3-1:0] next_stage;
        wire [N-1:0] stored_target = q.target;
        logic [N-1:0] next_target;
        wire [N*96-1:0] stored_versions = q.versions;
        logic [N*96-1:0] next_versions;
        wire bad;
        logic integrity_failed;
        wire run = !integrity_failed && i_rstb === 1'b1 && !bad;
        wire [23:0] timer;
        wire request_known = ^{i_runtime_command, i_runtime_owner_id,
            i_runtime_kernel_id, i_runtime_array_package_id, i_runtime_manifest_hash,
            i_runtime_cluster_mask,
            i_runtime_allocation_generation, i_runtime_execution_epoch, i_runtime_context_id,
            i_runtime_local_package_ids, i_runtime_context_versions, i_runtime_mapping_variant,
            i_runtime_qos_profile, i_runtime_power_profile, i_runtime_flags,
            i_runtime_tag} !== 1'bx;
        wire target_safe = ((stored_fatal | i_cluster_error) & stored_target) === {N{1'b0}} &&
            i_event_error === 1'b0 && i_network_error === 1'b0;
        wire fire = i_runtime_valid === 1'b1 && o_runtime_ready;
        logic [7:0] request_error;
        logic [N-1:0] new_ack;
        logic [N-1:0] new_success;
        logic [N-1:0] terminals;
        logic [N-1:0] group_mask;
        logic [3:0] aggregate;
        logic group_leader;

        function automatic logic [3:0] summarize(
            input logic [N-1:0] allocated,
            input logic [N-1:0] running,
            input logic [N-1:0] fatal,
            input logic [N*3-1:0] stage
        );
            logic all_suspended;
            all_suspended = allocated != 0;

            for (int c = 0; c < N; c++)
                if (allocated[c] && stage[c*3+:3] != ARRAY_CLUSTER_SUSPENDED) all_suspended = 1'b0;

            if (fatal != 0) return (fatal & allocated) == allocated ?
                ARRAY_ERROR_ISOLATED : ARRAY_DEGRADED;

            if (allocated == 0) return ARRAY_IDLE;

            if (all_suspended) return ARRAY_SUSPENDED;

            if (running == allocated) return ARRAY_ACTIVE;

            if (running == 0) return ARRAY_CONFIGURING;

            return ARRAY_MIXED;
        endfunction

        tile_shell_state #(.WIDTH($bits(state_t)), .PROTECTION(1)) u_state (
            .i_clk(i_clk),
            .i_rstb(i_rstb === 1'b1),
            .i_enable(1'b1),
            .i_data(n),
            .o_data(q),
            .o_bad(bad),
            .o_corrected()
        );

        counter #(.WIDTH(24)) u_timeout (
            .i_clk(i_clk),
            .i_rstb(i_rstb === 1'b1),
            .i_enable(q.phase != ARRAY_PHASE_IDLE),
            .i_clear(q.phase == ARRAY_PHASE_IDLE || q.phase != n.phase),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value(24'd0),
            .o_count(timer),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );

        assign o_busy = q.phase != ARRAY_PHASE_IDLE || q.response;
        assign o_runtime_ready = run && (i_test_mode === 1'b0) && request_known &&
            !o_busy;
        assign o_runtime_response_valid = run && q.response;
        assign o_runtime_response_command = q.command;
        assign o_runtime_response_tag = q.tag;
        assign o_runtime_response_error_code = q.error_code;
        assign o_runtime_response_status = q.error_code != ARRAY_OK ? 4'd1 : 4'd0;
        assign o_runtime_response_cluster_mask = q.original_target;
        assign o_runtime_response_array_state = q.response_state;
        // A start is accepted by all gateways on the same edge. No valid depends
        // on its own ready: the native cluster ingress is independent of valid.
        assign o_cluster_valid = run && (i_test_mode === 1'b0) &&
            q.phase == ARRAY_PHASE_SEND && target_safe &&
            ((i_cluster_ready & stored_target) == stored_target) ? stored_target : '0;
        assign o_cluster_response_ready = run && q.phase == ARRAY_PHASE_WAIT ?
            stored_target & ~q.ack : '0;
        assign o_cluster_command = q.native_command;
        assign o_cluster_commit_valid = run && (i_test_mode === 1'b0) &&
            q.phase == ARRAY_PHASE_COMMIT && target_safe ?
            stored_target & ~q.sent : '0;
        assign o_allocated = run ? stored_allocated : '0;
        assign o_running = run ? stored_running & ~stored_fatal : '0;
        assign o_fatal = bad || integrity_failed ? {N{1'b1}} : stored_fatal;
        assign o_completion_mask = stored_done;
        assign o_terminal_valid = run ? terminals : '0;
        assign o_group_masks = stored_groups;
        assign o_owner_ids = stored_owner;
        assign o_kernel_ids = stored_kernel;
        assign o_array_package_ids = stored_package_id;
        assign o_local_package_ids = stored_local_package;
        assign o_context_ids = stored_context_id;
        assign o_execution_epochs = stored_epoch;
        assign o_allocation_generations = stored_generation;
        assign o_commit_versions = stored_versions;
        assign o_command_owner = q.command_owner;
        assign o_command_kernel = q.command_kernel;
        assign o_command_tag = q.tag;
        assign o_first_error = bad || integrity_failed ? ARRAY_ERR_INTEGRITY : q.first_error;
        assign o_array_state = bad || integrity_failed ? ARRAY_ERROR_ISOLATED : aggregate;

        always @(posedge i_clk) begin
            if (i_rstb !== 1'b1) integrity_failed <= 1'b0;
            else if (bad) integrity_failed <= 1'b1;
        end

        always @* begin
            aggregate = summarize(stored_allocated, stored_running, stored_fatal, stored_stage);
            terminals = '0;

            for (int c = 0; c < N; c++) begin
                group_mask = stored_groups[c*N+:N];
                group_leader = 1'b1;

                for (int k = 0; k < c; k++)
                    if (group_mask[k]) group_leader = 1'b0;

                terminals[c] = group_leader && stored_allocated[c] && !stored_reported[c] &&
                    stored_stage[c*3+:3] == ARRAY_CLUSTER_RUNNING &&
            (stored_done & group_mask) == group_mask &&
                    (stored_fatal & group_mask) == 0 && i_network_idle;
            end
        end

        always @* begin
            request_error = ARRAY_OK;

            if (i_runtime_command > ARRAY_POWER_REQUEST) request_error = ARRAY_ERR_COMMAND;
            else if (i_runtime_command == ARRAY_QUERY) begin end
            else if (i_runtime_manifest_hash !== ARCHITECTURE_HASH)
                request_error = ARRAY_ERR_PACKAGE;
            else if (i_runtime_flags != 0 || i_runtime_mapping_variant != 0 ||
                i_runtime_qos_profile != 0 || i_runtime_power_profile != 0 ||
                i_runtime_command == ARRAY_RESIZE || i_runtime_command == ARRAY_MIGRATE ||
                i_runtime_command == ARRAY_POWER_REQUEST)
                request_error = ARRAY_ERR_UNSUPPORTED;
            else if (i_runtime_cluster_mask == 0) request_error = ARRAY_ERR_RESOURCE;
            else if (i_runtime_command == ARRAY_ALLOCATE) begin
                if ((stored_allocated & i_runtime_cluster_mask) != 0 || &q.serial ||
                    (stored_fatal & i_runtime_cluster_mask) != 0)
                    request_error = ARRAY_ERR_RESOURCE;
                else if (i_runtime_allocation_generation != q.serial)
                    request_error = ARRAY_ERR_GENERATION;

                for (int c = 0; c < N; c++) begin
                    if (request_error == ARRAY_OK && stored_allocated[c] &&
                        stored_owner[c*16+:16] == i_runtime_owner_id &&
                        stored_kernel[c*16+:16] == i_runtime_kernel_id)
                        request_error = ARRAY_ERR_OWNER;
                end
            end else begin
                for (int c = 0; c < N; c++) begin
                    if (i_runtime_cluster_mask[c]) begin
                        if (!stored_allocated[c] ||
            stored_groups[c*N+:N] != i_runtime_cluster_mask ||
                            stored_owner[c*16+:16] != i_runtime_owner_id ||
                            stored_kernel[c*16+:16] != i_runtime_kernel_id)
                            request_error = ARRAY_ERR_OWNER;
                        else if (stored_generation[c*16+:16] != i_runtime_allocation_generation)
                            request_error = ARRAY_ERR_GENERATION;
                        else if (stored_package_id[c*32+:32] != i_runtime_array_package_id)
                            request_error = ARRAY_ERR_PACKAGE;
                        else if (stored_epoch[c*8+:8] != i_runtime_execution_epoch)
                            request_error = ARRAY_ERR_EPOCH;
                        else if (stored_fatal[c]) request_error = ARRAY_ERR_STATE;
                        else case (i_runtime_command)
                            ARRAY_CONFIGURE: if (stored_stage[c*3+:3] != ARRAY_CLUSTER_ALLOCATED)
                                request_error = ARRAY_ERR_STATE;
                            ARRAY_VALIDATE: if (stored_stage[c*3+:3] != ARRAY_CLUSTER_CONFIGURING ||
            i_cluster_prepared[c] !== 1'b1)
                                request_error = ARRAY_ERR_PACKAGE;
                            ARRAY_COMMIT: if (stored_stage[c*3+:3] != ARRAY_CLUSTER_PREPARED ||
                                i_cluster_prepared[c] !== 1'b1 || i_network_configured !== 1'b1 ||
                                i_network_idle !== 1'b1 || stored_epoch[c*8+:8] >= 15)
                                request_error = ARRAY_ERR_PACKAGE;
                            ARRAY_START: if (stored_stage[c*3+:3] != ARRAY_CLUSTER_COMMITTED ||
            i_network_configured !== 1'b1)
                                request_error = ARRAY_ERR_STATE;
                            ARRAY_SUSPEND, ARRAY_DRAIN, ARRAY_ABORT:
                                if (stored_stage[c*3+:3] != ARRAY_CLUSTER_RUNNING ||
            !stored_running[c] ||
                                    i_network_idle !== 1'b1)
                                    request_error = ARRAY_ERR_STATE;
                            ARRAY_RESUME: if (stored_stage[c*3+:3] != ARRAY_CLUSTER_SUSPENDED ||
                                i_network_idle !== 1'b1)
                                request_error = ARRAY_ERR_STATE;
                            ARRAY_RELEASE: if (stored_running[c] ||
            i_cluster_quiescent[c] !== 1'b1 ||
                                i_network_idle !== 1'b1 || i_events_empty !== 1'b1)
                                request_error = ARRAY_ERR_STATE;
                            ARRAY_CLEAR_ERROR, ARRAY_COUNTER_SNAPSHOT: begin end
                            default: request_error = ARRAY_ERR_COMMAND;
                        endcase
                    end
                end
            end
        end

        always @* begin
            n = q;
            next_allocated = stored_allocated;
            next_context_id = stored_context_id;
            next_done = stored_done;
            next_epoch = stored_epoch;
            next_fatal = stored_fatal;
            next_generation = stored_generation;
            next_groups = stored_groups;
            next_kernel = stored_kernel;
            next_local_package = stored_local_package;
            next_owner = stored_owner;
            next_package_id = stored_package_id;
            next_reported = stored_reported;
            next_running = stored_running;
            next_stage = stored_stage;
            next_target = stored_target;
            next_versions = stored_versions;

            new_ack = q.ack;
            new_success = q.succeeded;

            if (q.response && i_runtime_response_ready === 1'b1) n.response = 1'b0;

            for (int c = 0; c < N; c++) begin
                if (i_completion[c]) begin
                    if (!stored_allocated[c] ||
            stored_stage[c*3+:3] != ARRAY_CLUSTER_RUNNING || stored_done[c]) begin
                        next_fatal = next_fatal | stored_groups[c*N+:N];
                        if (q.first_error == 0) n.first_error = ARRAY_ERR_EVENT;
                    end else next_done[c] = 1'b1;
                end

                if (terminals[c] && i_terminal_ready[c]) begin
                    next_reported = next_reported | stored_groups[c*N+:N];
                    next_running = next_running & ~stored_groups[c*N+:N];
                end

                if (i_cluster_error[c]) begin
                    next_fatal = next_fatal | stored_groups[c*N+:N];
                    if (q.first_error == 0) n.first_error = ARRAY_ERR_CLUSTER;
                end
            end

            if (i_event_error || i_network_error) begin
                next_fatal = '1;

                if (q.first_error == 0)
                    n.first_error = i_event_error ? ARRAY_ERR_EVENT : ARRAY_ERR_NETWORK;
            end

            if (fire) begin
                n.command = i_runtime_command;
                next_target = i_runtime_cluster_mask;
                n.original_target = i_runtime_cluster_mask;
                n.command_owner = i_runtime_owner_id;
                n.command_kernel = i_runtime_kernel_id;
                n.tag = i_runtime_tag;
                n.error_code = request_error;
                n.response = 1'b1;
                n.ack = '0;
                n.sent = '0;
                n.succeeded = '0;
                n.rollback = 1'b0;

                if (request_error == ARRAY_OK && i_runtime_command != ARRAY_QUERY) begin
                    n.response = 1'b0;
                    n.phase = ARRAY_PHASE_SEND;

                    case (i_runtime_command)
                        ARRAY_ALLOCATE: n.native_command = 1;
                        ARRAY_CONFIGURE: n.native_command = 2;
                        ARRAY_COMMIT: n.phase = ARRAY_PHASE_COMMIT;
                        ARRAY_START: n.native_command = 4;
                        ARRAY_SUSPEND: n.native_command = 5;
                        ARRAY_RESUME: n.native_command = 6;
                        ARRAY_DRAIN: n.native_command = 7;
                        ARRAY_ABORT: n.native_command = 8;
                        ARRAY_RELEASE: n.native_command = 9;
                        ARRAY_CLEAR_ERROR: n.native_command = 10;
                        ARRAY_COUNTER_SNAPSHOT: n.native_command = 11;
                        default: begin
                            n.phase = ARRAY_PHASE_IDLE;
                            n.response = 1'b1;
                        end
                    endcase

                    for (int c = 0; c < N; c++) begin
                        if (i_runtime_cluster_mask[c]) begin
                            if (i_runtime_command == ARRAY_ALLOCATE) begin
                                next_owner[c*16+:16] = i_runtime_owner_id;
                                next_kernel[c*16+:16] = i_runtime_kernel_id;
                                next_package_id[c*32+:32] = i_runtime_array_package_id;
                                next_groups[c*N+:N] = i_runtime_cluster_mask;
                            end

                            if (i_runtime_command == ARRAY_CONFIGURE) begin
                                next_local_package[c*32+:32]
            = i_runtime_local_package_ids[c*32+:32];
                                next_context_id[c*8+:8] = i_runtime_context_id;
                            end

                            if (i_runtime_command == ARRAY_VALIDATE) begin
                                next_stage[c*3+:3] = ARRAY_CLUSTER_PREPARED;
                                next_versions[c*96+:96] = i_runtime_context_versions[c*96+:96];
                            end

                            if (i_runtime_command == ARRAY_START) begin
                                next_done[c] = 1'b0;
                                next_reported[c] = 1'b0;
                            end
                        end
                    end
                end
            end

            if (q.phase == ARRAY_PHASE_SEND && o_cluster_valid != 0) begin
                n.phase = ARRAY_PHASE_WAIT;
                n.sent = stored_target;
            end

            if (q.phase == ARRAY_PHASE_COMMIT) begin
                n.sent = q.sent | (o_cluster_commit_valid & i_cluster_commit_ready);

                if (n.sent == stored_target) n.phase = ARRAY_PHASE_COMMIT_WAIT;
            end

            if (q.phase == ARRAY_PHASE_COMMIT || q.phase == ARRAY_PHASE_COMMIT_WAIT) begin
                n.ack = q.ack | (i_cluster_commit_complete & q.sent);

                if ((i_cluster_commit_error & stored_target) != 0) begin
                    next_fatal = next_fatal | stored_target;
                    n.error_code = ARRAY_ERR_CLUSTER;
                    n.phase = ARRAY_PHASE_IDLE;
                    n.response = 1'b1;
                end else if (q.phase == ARRAY_PHASE_COMMIT_WAIT && n.ack == stored_target) begin
                    n.native_command = 3;
                    n.phase = ARRAY_PHASE_SEND;
                    n.ack = '0;
                    n.succeeded = '0;
                    for (int c = 0; c < N; c++)
                        if (stored_target[c]) next_epoch[c*8+:8] = stored_epoch[c*8+:8] + 1'b1;
                end
            end

            if (q.phase == ARRAY_PHASE_WAIT) begin
                for (int c = 0; c < N; c++) begin
                    if (o_cluster_response_ready[c] && i_cluster_response_valid[c]) begin
                        new_ack[c] = 1'b1;
                        if (i_cluster_response_command[c*4+:4] !== q.native_command ||
                            i_cluster_response_tag[c*16+:16] !== q.tag) begin
                            n.error_code = ARRAY_ERR_INTEGRITY;
                            next_fatal = next_fatal | stored_target;
                        end else if (i_cluster_response_error[c*8+:8] !== 0)
                            n.error_code = ARRAY_ERR_CLUSTER;
                        else new_success[c] = 1'b1;
                    end
                end

                n.ack = new_ack;
                n.succeeded = new_success;

                if ((next_fatal & stored_target) != 0 && n.error_code == ARRAY_OK)
                    n.error_code = ARRAY_ERR_CLUSTER;

                if (new_ack == stored_target) begin
                    n.phase = ARRAY_PHASE_IDLE;
                    n.response = 1'b1;

                    if (n.error_code != 0 && q.command == ARRAY_ALLOCATE && !q.rollback &&
                        new_success != 0) begin
                        next_target = new_success;
                        n.native_command = 9;
                        n.phase = ARRAY_PHASE_SEND;
                        n.ack = '0;
                        n.succeeded = '0;
                        n.rollback = 1'b1;
                        n.response = 1'b0;
                    end else if (q.rollback) begin
                        if (new_success != stored_target) next_fatal = next_fatal | stored_target;
                    end else if (n.error_code != 0) begin
                        if (q.command != ARRAY_ALLOCATE) next_fatal = next_fatal | stored_target;
                    end else begin
                        if (q.command == ARRAY_ALLOCATE) n.serial = q.serial + 1'b1;

                        for (int c = 0; c < N; c++) begin
                            if (stored_target[c]) case (q.command)
                                ARRAY_ALLOCATE: begin
                                    next_allocated[c] = 1'b1;
                                    next_done[c] = 1'b0;
                                    next_reported[c] = 1'b0;
                                    next_stage[c*3+:3] = ARRAY_CLUSTER_ALLOCATED;
                                    next_generation[c*16+:16] = q.serial + 1'b1;
                                end
                                ARRAY_CONFIGURE: next_stage[c*3+:3] = ARRAY_CLUSTER_CONFIGURING;
                                ARRAY_COMMIT: next_stage[c*3+:3] = ARRAY_CLUSTER_COMMITTED;
                                ARRAY_START, ARRAY_RESUME: begin
                                    next_stage[c*3+:3] = ARRAY_CLUSTER_RUNNING;
                                    next_running[c] = 1'b1;
                                end
                                ARRAY_SUSPEND: begin
                                    next_stage[c*3+:3] = ARRAY_CLUSTER_SUSPENDED;
                                    next_running[c] = 1'b0;
                                end
                                ARRAY_ABORT, ARRAY_DRAIN: begin
                                    next_stage[c*3+:3] = ARRAY_CLUSTER_DRAINED;
                                    next_running[c] = 1'b0;
                                end
                                ARRAY_RELEASE: begin
                                    next_allocated[c] = 1'b0;
                                    next_stage[c*3+:3] = ARRAY_CLUSTER_FREE;
                                    next_groups[c*N+:N] = '0;
                                    next_owner[c*16+:16] = '0;
                                    next_kernel[c*16+:16] = '0;
                                    next_package_id[c*32+:32] = '0;
                                end
                                default: begin end
                            endcase
                        end
                    end
                end
            end

            if (q.phase != ARRAY_PHASE_IDLE && timer >= TIMEOUT_CYCLES) begin
                n.phase = ARRAY_PHASE_IDLE;
                n.response = 1'b1;
                n.error_code = ARRAY_ERR_TIMEOUT;
                next_fatal = next_fatal | stored_target;
            end

            // A newly observed target fault must cancel unsent work immediately.
            // Accepted child work is quarantined; only coordinated reset recovers it.
            if (q.phase != ARRAY_PHASE_IDLE && (next_fatal & stored_target) != 0) begin
                n.phase = ARRAY_PHASE_IDLE;
                n.response = 1'b1;

                if (n.error_code == ARRAY_OK) n.error_code = ARRAY_ERR_CLUSTER;
            end

            if (!q.response && n.response)
                n.response_state = summarize(next_allocated, next_running, next_fatal, next_stage);

            if (next_fatal != 0 && q.first_error == 0 && n.first_error == 0)
                n.first_error = n.error_code == 0 ? ARRAY_ERR_CLUSTER : n.error_code;

            n.allocated = next_allocated;
            n.context_id = next_context_id;
            n.done = next_done;
            n.epoch = next_epoch;
            n.fatal = next_fatal;
            n.generation = next_generation;
            n.groups = next_groups;
            n.kernel = next_kernel;
            n.local_package = next_local_package;
            n.owner = next_owner;
            n.package_id = next_package_id;
            n.reported = next_reported;
            n.running = next_running;
            n.stage = next_stage;
            n.target = next_target;
            n.versions = next_versions;
        end
    end
endmodule
`default_nettype wire
