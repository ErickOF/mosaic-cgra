`timescale 1ns / 1ps
`default_nettype none
// Always-on, cluster-exclusive lifecycle coordinator. Responses and fanout
// obligations remain owned until the corresponding ready/valid transfer.
module cluster_control #(
    parameter NUM_TILES = 4,
    parameter TIMEOUT_CYCLES = 65535,
    parameter CONTROL_PROTECTION = 1,
    localparam int N = NUM_TILES > 0 && NUM_TILES <= 64 ? NUM_TILES : 1
) (
    input wire i_clk,
    input wire i_rstb,
    input wire i_runtime_valid,
    output wire o_runtime_ready,
    input wire [3:0] i_runtime_command,
    input wire [15:0] i_runtime_owner_id,
    input wire [15:0] i_runtime_kernel_id,
    input wire [31:0] i_runtime_package_id,
    input wire [7:0] i_runtime_context_id,
    input wire [N-1:0] i_runtime_resource_mask,
    input wire [7:0] i_runtime_flags,
    input wire [15:0] i_runtime_tag,
    output wire o_runtime_response_valid,
    input wire i_runtime_response_ready,
    output wire [3:0] o_runtime_response_command,
    output wire [3:0] o_runtime_response_status,
    output wire [7:0] o_runtime_response_error_code,
    output wire [15:0] o_runtime_response_tag,
    output wire [3:0] o_runtime_response_state,
    output wire [N-1:0] o_tile_runtime_valid,
    input wire [N-1:0] i_tile_runtime_ready,
    output wire [2:0] o_tile_runtime_command,
    input wire [N-1:0] i_tile_response_valid,
    output wire [N-1:0] o_tile_response_ready,
    input wire [N-1:0] i_tile_response_error,
    input wire [N*3-1:0] i_tile_response_command,
    input wire [N*16-1:0] i_tile_response_tag,
    input wire [N*4-1:0] i_tile_state,
    input wire i_transport_idle,
    input wire i_events_empty,
    input wire i_all_quiescent,
    input wire i_cfg_idle,
    input wire i_cfg_hold,
    input wire i_suspend_allowed,
    input wire i_cfg_commit_complete,
    input wire i_cfg_commit_error,
    input wire [31:0] i_cfg_package_id,
    input wire [15:0] i_cfg_owner_id,
    input wire [15:0] i_cfg_kernel_id,
    input wire [7:0] i_cfg_context_id,
    input wire [3:0] i_cfg_epoch,
    input wire [N-1:0] i_completion_mask,
    input wire i_fault,
    input wire [7:0] i_fault_code,
    input wire [7:0] i_fault_source,
    input wire i_memory_release_done,
    input wire i_memory_release_error,
    input wire i_cfg_flushed,
    output wire o_memory_release,
    output wire o_cfg_flush,
    output wire o_cfg_release,
    output wire o_snapshot,
    output wire o_counter_clear,
    output wire o_package_clear,
    output wire o_launch_clear,
    output wire o_error_clear,
    output wire o_terminal_event,
    input wire i_terminal_ready,
    output wire o_fault_event,
    input wire i_fault_event_ready,
    output wire o_allocated,
    output wire o_running,
    output wire o_boundary_enable,
    output wire o_configuration_enable,
    output wire [3:0] o_state,
    output wire [15:0] o_owner_id,
    output wire [15:0] o_kernel_id,
    output wire [31:0] o_package_id,
    output wire [7:0] o_context_id,
    output wire [3:0] o_epoch,
    output wire [15:0] o_allocation_generation,
    output wire o_error,
    output wire o_fatal,
    output wire [7:0] o_first_error_code,
    output wire [7:0] o_first_error_source
);
    import cluster_pkg::*;

    if (!(NUM_TILES >= 1 && NUM_TILES <= 64 && TIMEOUT_CYCLES >= 16 &&
        TIMEOUT_CYCLES <= 16777215 && CONTROL_PROTECTION >= 0 && CONTROL_PROTECTION <= 2))
        begin : g_invalid_parameters
            cluster_control_parameters_must_be_valid invalid_parameters ();
        end

    // Width-dependent masks keep this record local to the parameterized block.
    typedef struct packed {
        logic allocated;
        logic committed;
        logic launched;
        logic terminal;
        logic terminal_pending;
        logic fault_pending;
        logic fatal;
        logic [7:0] error_code;
        logic [7:0] error_source;
        logic [15:0] owner;
        logic [15:0] kernel;
        logic [31:0] package_id;
        logic [7:0] context_id;
        logic [3:0] epoch;
        logic [15:0] generation;
        state_t state;
        phase_t phase;
        logic [3:0] command;
        logic [2:0] native_command;
        logic [15:0] tag;
        logic [N-1:0] target;
        logic [N-1:0] sent;
        logic [N-1:0] acknowledged;
        logic response;
        logic [7:0] response_error;
        logic [3:0] response_state;
        logic flush_sent;
    } control_t;

    control_t q;
    control_t n;
    wire bad;

    // Integrity failure cannot be repaired by re-encoding a corrupted next state.
    // This independent sticky latch requires coordinated reset for recovery.
    logic integrity_fault;
    logic integrity_event_pending;

    always_ff @(posedge i_clk) begin
        if (!i_rstb) begin
            integrity_fault <= 1'b0;
            integrity_event_pending <= 1'b0;
        end else begin
            if (bad &&!integrity_fault) begin
                integrity_fault <= 1'b1;
                integrity_event_pending <= 1'b1;
            end else if (integrity_event_pending && i_fault_event_ready === 1'b1)
                integrity_event_pending <= 1'b0;
        end
    end

    wire [N-1:0] sent = q.sent;
    wire [N-1:0] acknowledged = q.acknowledged;
    logic [N-1:0] next_acknowledged;
    wire [23:0] timer;
    wire run = i_rstb === 1'b1 &&!bad &&!integrity_fault;
    logic [7:0] request_error;
    logic [N-1:0] active_targets;
    wire request_known = (^{i_runtime_command, i_runtime_owner_id, i_runtime_kernel_id,
        i_runtime_package_id, i_runtime_context_id, i_runtime_resource_mask,
        i_runtime_flags, i_runtime_tag} !== 1'bx);
    wire request_fire = o_runtime_ready && i_runtime_valid === 1'b1;
    wire running = q.state == CLUSTER_RUNNING_SINGLE || q.state == CLUSTER_PARTIALLY_IDLE;
    wire all_done = &i_completion_mask;
    wire quiet = i_transport_idle === 1'b1 && i_events_empty === 1'b1 &&
        i_all_quiescent === 1'b1 && i_cfg_idle === 1'b1;

    tile_shell_state #(.WIDTH($bits(control_t)), .PROTECTION(CONTROL_PROTECTION)) u_state (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(1'b1),
        .i_data(n),
        .o_data(q),
        .o_bad(bad),
        .o_corrected()
    );

    counter #(.WIDTH(24)) u_timeout (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(q.phase != CLUSTER_PHASE_IDLE),
        .i_clear(q.phase == CLUSTER_PHASE_IDLE || q.phase != n.phase),
        .i_load(1'b0),
        .i_direction(1'b0),
        .i_load_value(24'd0),
        .o_count(timer),
        .o_overflow(),
        .o_underflow(),
        .o_terminal()
    );

    assign o_runtime_ready = run && q.phase == CLUSTER_PHASE_IDLE &&!q.response && request_known;
    assign o_runtime_response_valid = run && q.response;
    assign o_runtime_response_command = q.command;
    assign o_runtime_response_status = q.response_error == CLUSTER_OK ? 4'd0 : 4'd1;
    assign o_runtime_response_error_code = q.response_error;
    assign o_runtime_response_tag = q.tag;
    assign o_runtime_response_state = q.response_state;
    assign o_tile_runtime_valid = run && q.phase == CLUSTER_PHASE_FANOUT ?
        q.target & ~q.sent : '0;
    assign o_tile_runtime_command = q.native_command;
    assign o_tile_response_ready = run && q.phase == CLUSTER_PHASE_FANOUT ?
        q.target & q.sent & ~q.acknowledged : '0;
    assign o_cfg_release = run && q.phase == CLUSTER_PHASE_RELEASE_HOLD;
    assign o_memory_release = run && q.phase == CLUSTER_PHASE_RELEASE_MEMORY;
    assign o_cfg_flush = run && q.phase == CLUSTER_PHASE_RELEASE_FABRIC &&!q.flush_sent;
    assign o_snapshot = request_fire && request_error == CLUSTER_OK &&
        i_runtime_command == CLUSTER_COUNTER_SNAPSHOT;
    assign o_counter_clear = request_fire && request_error == CLUSTER_OK &&
        i_runtime_command == CLUSTER_RESERVE;
    assign o_launch_clear = request_fire && request_error == CLUSTER_OK &&
        i_runtime_command == CLUSTER_START;
    assign o_package_clear = request_fire && request_error == CLUSTER_OK &&
        i_runtime_command == CLUSTER_CONFIGURE;
    assign o_error_clear = request_fire && request_error == CLUSTER_OK &&
        i_runtime_command == CLUSTER_CLEAR_ERROR;
    assign o_terminal_event = run && q.terminal_pending;
    assign o_fault_event = i_rstb === 1'b1 && (q.fault_pending || integrity_event_pending);
    assign o_allocated = run && q.allocated;
    assign o_running = run && running &&!q.fatal;
    assign o_boundary_enable = o_running && q.phase == CLUSTER_PHASE_IDLE;
    assign o_configuration_enable = run && q.allocated &&!q.fatal &&
        q.phase == CLUSTER_PHASE_IDLE && (q.state == CLUSTER_RESERVED ||
        q.state == CLUSTER_CONFIGURING || q.state == CLUSTER_READY);
    assign o_state = bad || integrity_fault ? CLUSTER_ERROR_ISOLATED : q.state;
    assign o_owner_id = q.allocated ? q.owner : '0;
    assign o_kernel_id = q.allocated ? q.kernel : '0;
    assign o_package_id = q.package_id;
    assign o_context_id = q.context_id;
    assign o_epoch = q.epoch;
    assign o_allocation_generation = q.generation;
    assign o_error = bad || integrity_fault || q.error_code != CLUSTER_OK;
    assign o_fatal = bad || integrity_fault || q.fatal;
    assign o_first_error_code = bad || integrity_fault ? CLUSTER_ERR_INTEGRITY : q.error_code;
    assign o_first_error_source = bad || integrity_fault ? 8'hff : q.error_source;

    always @* begin
        active_targets = '0;

        for (int t = 0; t < N; t++) begin
            if (i_tile_state[t*4+:4] != tile_shell_pkg::TILE_COMPLETED &&
                i_tile_state[t*4+:4] != tile_shell_pkg::TILE_READY)
                active_targets[t] = 1'b1;
        end

        request_error = CLUSTER_OK;

        if (^{i_runtime_command, i_runtime_owner_id, i_runtime_kernel_id,
            i_runtime_package_id, i_runtime_context_id, i_runtime_resource_mask,
            i_runtime_flags, i_runtime_tag} === 1'bx) request_error = CLUSTER_ERR_UNKNOWN;
        else if (i_runtime_command > CLUSTER_POWER_REQUEST) request_error = CLUSTER_ERR_COMMAND;
        else if (i_runtime_command == CLUSTER_QUERY) begin end
        else if (i_runtime_flags != 0) request_error = CLUSTER_ERR_UNSUPPORTED;
        else if (i_runtime_command == CLUSTER_RESERVE) begin
            if (q.allocated || q.state != CLUSTER_FREE ||!quiet || &q.generation)
                request_error = CLUSTER_ERR_STATE;
            else if (i_runtime_resource_mask != {N{1'b1}})
                request_error = CLUSTER_ERR_RESOURCE;
        end else if (!q.allocated || i_runtime_owner_id != q.owner ||
            i_runtime_kernel_id != q.kernel) request_error = CLUSTER_ERR_OWNER;
        else if (q.fatal) request_error = CLUSTER_ERR_STATE;
        else if (i_runtime_resource_mask != {N{1'b1}}) request_error = CLUSTER_ERR_RESOURCE;
        else case (i_runtime_command)
            CLUSTER_CONFIGURE: begin
                if (!(q.state == CLUSTER_RESERVED || q.state == CLUSTER_READY) ||!quiet)
                    request_error = CLUSTER_ERR_BUSY;
            end
            CLUSTER_VALIDATE: begin
                if (q.state != CLUSTER_CONFIGURING ||!q.committed ||!quiet ||
                    i_runtime_package_id != q.package_id ||
                    i_runtime_context_id != q.context_id ||!i_cfg_hold)
                    request_error = CLUSTER_ERR_PACKAGE;
            end
            CLUSTER_START: begin
                if (q.state != CLUSTER_READY ||!q.committed || q.launched ||!quiet ||
                    !i_cfg_hold) request_error = CLUSTER_ERR_STATE;
                else if (i_runtime_package_id != q.package_id ||
                    i_runtime_context_id != q.context_id) request_error = CLUSTER_ERR_PACKAGE;
            end
            CLUSTER_SUSPEND, CLUSTER_DRAIN, CLUSTER_ABORT: begin
                if (!running && q.state != CLUSTER_SUSPENDED)
                    request_error = CLUSTER_ERR_STATE;
                else if (i_runtime_command == CLUSTER_SUSPEND &&!i_suspend_allowed)
                    request_error = CLUSTER_ERR_UNSUPPORTED;
                if (i_runtime_command == CLUSTER_ABORT &&
                    (!i_transport_idle ||!i_events_empty))
                    request_error = CLUSTER_ERR_BUSY;
            end
            CLUSTER_RESUME: begin
                if (q.state != CLUSTER_SUSPENDED || i_cfg_hold)
                    request_error = CLUSTER_ERR_STATE;
                else if (i_runtime_package_id != q.package_id ||
                    i_runtime_context_id != q.context_id) request_error = CLUSTER_ERR_PACKAGE;
            end
            CLUSTER_RELEASE: begin
                if (running || q.state == CLUSTER_SUSPENDED ||!quiet)
                    request_error = CLUSTER_ERR_BUSY;
            end
            CLUSTER_CLEAR_ERROR: begin
                if (!quiet) request_error = CLUSTER_ERR_BUSY;
            end
            CLUSTER_COUNTER_SNAPSHOT: begin end
            default: request_error = CLUSTER_ERR_UNSUPPORTED;
        endcase
    end

    always @* begin
        n = q;
        next_acknowledged = acknowledged;

        if (q.response && i_runtime_response_ready === 1'b1) n.response = 1'b0;

        if (q.terminal_pending && i_terminal_ready === 1'b1) n.terminal_pending = 1'b0;

        if (q.fault_pending && i_fault_event_ready === 1'b1) n.fault_pending = 1'b0;

        if (run && i_cfg_commit_complete) begin
            if (q.allocated && i_cfg_owner_id == q.owner && i_cfg_kernel_id == q.kernel &&
                o_configuration_enable && i_cfg_epoch != q.epoch) begin
                n.committed = 1'b1;
                n.launched = 1'b0;
                n.package_id = i_cfg_package_id;
                n.context_id = i_cfg_context_id;
                n.epoch = i_cfg_epoch;
            end else begin
                n.fatal = 1'b1;
                n.error_code = CLUSTER_ERR_CONFIGURATION;
                n.state = CLUSTER_ERROR_ISOLATED;
                n.fault_pending = 1'b1;
            end
        end

        if (run && request_fire) begin
            n.command = i_runtime_command;
            n.tag = i_runtime_tag;
            n.response_error = request_error;
            n.response = 1'b1;

            if (request_error == CLUSTER_OK) begin
                case (i_runtime_command)
                    CLUSTER_RESERVE: begin
                        n.allocated = 1'b1;
                        n.owner = i_runtime_owner_id;
                        n.kernel = i_runtime_kernel_id;
                        n.generation = q.generation + 1'b1;
                        n.state = CLUSTER_RESERVED;
                        n.phase = CLUSTER_PHASE_FANOUT;
                        n.native_command = tile_shell_pkg::RUNTIME_ALLOCATE;
                        n.target = '1;
                        n.sent = '0;
                        next_acknowledged = '0;
                        n.response = 1'b0;
                    end
                    CLUSTER_CONFIGURE: begin
                        n.state = CLUSTER_CONFIGURING;
                        n.committed = 1'b0;
                    end
                    CLUSTER_VALIDATE: n.state = CLUSTER_READY;
                    CLUSTER_START: begin
                        n.phase = CLUSTER_PHASE_RELEASE_HOLD;
                        n.native_command = tile_shell_pkg::RUNTIME_START;
                        n.target = '1;
                        n.sent = '0;
                        next_acknowledged = '0;
                        n.response = 1'b0;
                        n.terminal = 1'b0;
                        n.launched = 1'b1;
                    end
                    CLUSTER_SUSPEND, CLUSTER_RESUME, CLUSTER_DRAIN, CLUSTER_ABORT: begin
                        n.phase = CLUSTER_PHASE_FANOUT;
                        n.native_command = i_runtime_command == CLUSTER_SUSPEND ?
                            tile_shell_pkg::RUNTIME_SUSPEND :
                            i_runtime_command == CLUSTER_RESUME ? tile_shell_pkg::RUNTIME_RESUME :
                            i_runtime_command == CLUSTER_ABORT ? tile_shell_pkg::RUNTIME_TERMINATE :
                            tile_shell_pkg::RUNTIME_DRAIN;
                        n.target = active_targets;
                        n.sent = '0;
                        next_acknowledged = '0;
                        n.response = 1'b0;

                        if (i_runtime_command == CLUSTER_SUSPEND) n.state = CLUSTER_SUSPENDING;

                        if (i_runtime_command == CLUSTER_DRAIN) n.state = CLUSTER_DRAINING;

                        if (i_runtime_command == CLUSTER_ABORT) n.state = CLUSTER_RECOVERING;
                    end
                    CLUSTER_RELEASE: begin
                        n.phase = CLUSTER_PHASE_RELEASE_MEMORY;
                        n.response = 1'b0;
                        n.committed = 1'b0;
                    end
                    CLUSTER_CLEAR_ERROR: begin
                        n.error_code = CLUSTER_OK;
                        n.error_source = '0;
                    end
                    default: begin end
                endcase
            end
        end

        if (run && q.phase == CLUSTER_PHASE_RELEASE_HOLD &&!i_cfg_hold)
            n.phase = CLUSTER_PHASE_FANOUT;

        if (run && q.phase == CLUSTER_PHASE_FANOUT) begin
            n.sent = q.sent | (o_tile_runtime_valid & i_tile_runtime_ready);

            for (int t = 0; t < N; t++) begin
                if (o_tile_response_ready[t] && i_tile_response_valid[t] === 1'b1) begin
                    next_acknowledged[t] = 1'b1;

                    if (i_tile_response_error[t] !== 1'b0 ||
                        i_tile_response_command[t*3+:3] !== q.native_command ||
                        i_tile_response_tag[t*16+:16] !== q.tag) begin
                        n.fatal = 1'b1;
                        n.response_error = CLUSTER_ERR_TILE;
                    end
                end
            end

            if ((next_acknowledged & q.target) == q.target) n.phase = CLUSTER_PHASE_SETTLE;
        end

        if (run && q.phase == CLUSTER_PHASE_SETTLE &&
            (q.command == CLUSTER_RELEASE ? quiet :
            (q.command == CLUSTER_DRAIN || q.command == CLUSTER_ABORT) ?
            i_transport_idle === 1'b1 : 1'b1)) begin
            n.phase = CLUSTER_PHASE_IDLE;
            n.response = 1'b1;
            case (q.command)
                CLUSTER_START, CLUSTER_RESUME: n.state = CLUSTER_RUNNING_SINGLE;
                CLUSTER_SUSPEND: n.state = CLUSTER_SUSPENDED;
                CLUSTER_DRAIN, CLUSTER_ABORT: n.state = CLUSTER_READY;
                CLUSTER_RELEASE: begin
                    n.state = CLUSTER_FREE;
                    n.allocated = 1'b0;
                    n.package_id = '0;
                    n.context_id = '0;
                    n.launched = 1'b0;
                    n.terminal = 1'b0;
                end
                default: begin end
            endcase
        end

        if (run && q.phase == CLUSTER_PHASE_RELEASE_MEMORY && i_memory_release_done) begin
            if (i_memory_release_error) begin
                n.fatal = 1'b1;
                n.response_error = CLUSTER_ERR_MEMORY;
            end

            n.phase = CLUSTER_PHASE_RELEASE_FABRIC;
            n.flush_sent = 1'b0;
        end

        if (run && q.phase == CLUSTER_PHASE_RELEASE_FABRIC) begin
            n.flush_sent = 1'b1;

            if (i_cfg_flushed) begin
                n.phase = CLUSTER_PHASE_FANOUT;
                n.native_command = tile_shell_pkg::RUNTIME_RELEASE;
                n.target = '1;
                n.sent = '0;
                next_acknowledged = '0;
            end
        end

        if (run && running && q.phase == CLUSTER_PHASE_IDLE &&!request_fire &&
            all_done && i_transport_idle &&!q.terminal) begin
            n.terminal = 1'b1;
            n.terminal_pending = 1'b1;
            n.state = CLUSTER_READY;
        end else if (run && running && q.phase == CLUSTER_PHASE_IDLE &&!request_fire &&
        !all_done) begin
            n.state = |i_completion_mask ? CLUSTER_PARTIALLY_IDLE : CLUSTER_RUNNING_SINGLE;
        end

        if (run && q.phase != CLUSTER_PHASE_IDLE && timer >= TIMEOUT_CYCLES) begin
            n.phase = CLUSTER_PHASE_IDLE;
            n.response = 1'b1;
            n.response_error = CLUSTER_ERR_TIMEOUT;
            n.fatal = 1'b1;
        end

        if (run && (i_fault || i_cfg_commit_error || n.fatal)) begin
            if (q.error_code == CLUSTER_OK) begin
                n.error_code = i_fault ? i_fault_code : i_cfg_commit_error ?
                    CLUSTER_ERR_CONFIGURATION : n.response_error;
                n.error_source = i_fault ? i_fault_source : 8'hff;
                n.fault_pending = 1'b1;
            end

            n.fatal = 1'b1;
            n.state = CLUSTER_ERROR_ISOLATED;

            if (q.phase != CLUSTER_PHASE_IDLE) begin
                n.phase = CLUSTER_PHASE_IDLE;
                n.response = 1'b1;

                if (n.response_error == CLUSTER_OK) n.response_error = n.error_code;
            end
        end

        if (!q.response && n.response) n.response_state = n.state;

        n.acknowledged = next_acknowledged;
    end
endmodule
`default_nettype wire
