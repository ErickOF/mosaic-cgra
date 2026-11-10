`timescale 1ns / 1ps
`default_nettype none
// Synchronous canonical System-RTL. One memory obligation and one dispatched
// record are live at a time; a protected queue holds immutable program doorbells.
module system_core #(
    parameter NUM_CLUSTERS = 2,
    parameter NUM_BUFFERS = 4,
    parameter COMMAND_DEPTH = 2,
    parameter EVENT_DEPTH = 8,
    parameter MEM_DATA_WIDTH = 128,
    parameter MEMORY_TIMEOUT = 65535,
    parameter SRAM_BYTES = 512,
    parameter logic [255:0] SYSTEM_HASH = '0,
    parameter logic [255:0] ARRAY_HASH = '0,
    localparam bit VALID = ((NUM_CLUSTERS == 1 || NUM_CLUSTERS == 2) === 1'b1) &&
        ((NUM_BUFFERS >= 1 && NUM_BUFFERS <= 8) === 1'b1) &&
        ((COMMAND_DEPTH >= 1 && COMMAND_DEPTH <= 8) === 1'b1) &&
        ((EVENT_DEPTH >= 1 && EVENT_DEPTH <= 32) === 1'b1) &&
        ((MEM_DATA_WIDTH == 64 || MEM_DATA_WIDTH == 128) === 1'b1) &&
        ((MEMORY_TIMEOUT >= 16 && 64'(MEMORY_TIMEOUT) <= 64'hffffff) === 1'b1) &&
        ((SRAM_BYTES >= 512 && SRAM_BYTES <= 65536) === 1'b1) &&
        (^{NUM_CLUSTERS, NUM_BUFFERS, COMMAND_DEPTH, EVENT_DEPTH,
            MEM_DATA_WIDTH, MEMORY_TIMEOUT, SRAM_BYTES, SYSTEM_HASH, ARRAY_HASH} !== 1'bx),
    localparam int N = VALID ? NUM_CLUSTERS : 1,
    localparam int B = VALID ? NUM_BUFFERS : 1,
    localparam int D = VALID ? MEM_DATA_WIDTH : 64
) (
    input wire i_clk,
    input wire i_rstb,
    input wire i_test_mode,
    input wire i_memory_reset_done,
    input wire i_ctrl_valid,
    output wire o_ctrl_ready,
    input wire i_ctrl_write,
    input wire [31:0] i_ctrl_address,
    input wire [31:0] i_ctrl_write_data,
    input wire [3:0] i_ctrl_write_strobe,
    input wire [15:0] i_ctrl_requester_id,
    input wire [2:0] i_ctrl_privilege,
    input wire [7:0] i_ctrl_tag,
    output wire o_ctrl_response_valid,
    input wire i_ctrl_response_ready,
    output wire [31:0] o_ctrl_response_data,
    output wire [7:0] o_ctrl_response_status,
    output wire [7:0] o_ctrl_response_tag,
    output wire o_mem_request_valid,
    input wire i_mem_request_ready,
    output wire o_mem_request_write,
    output wire [63:0] o_mem_request_address,
    output wire [15:0] o_mem_request_length,
    output wire [2:0] o_mem_request_size,
    output wire [15:0] o_mem_request_id,
    output wire [7:0] o_mem_request_requester,
    output wire [15:0] o_mem_request_owner,
    output wire [15:0] o_mem_request_kernel,
    output wire [15:0] o_mem_request_buffer,
    output wire [15:0] o_mem_request_generation,
    output wire [15:0] o_mem_request_descriptor_generation,
    output wire [31:0] o_mem_request_package,
    output wire [7:0] o_mem_request_epoch,
    output wire o_mem_write_valid,
    input wire i_mem_write_ready,
    output wire [D-1:0] o_mem_write_data,
    output wire [D/8-1:0] o_mem_write_strobe,
    output wire o_mem_write_last,
    output wire [15:0] o_mem_write_id,
    input wire i_mem_read_valid,
    output wire o_mem_read_ready,
    input wire [D-1:0] i_mem_read_data,
    input wire [D/8-1:0] i_mem_read_keep,
    input wire i_mem_read_last,
    input wire [15:0] i_mem_read_id,
    input wire [3:0] i_mem_read_status,
    input wire i_mem_write_response_valid,
    output wire o_mem_write_response_ready,
    input wire [15:0] i_mem_write_response_id,
    input wire [3:0] i_mem_write_response_status,
    output wire o_fence_valid,
    input wire i_fence_ready,
    output wire [15:0] o_fence_owner,
    output wire [15:0] o_fence_kernel,
    output wire [15:0] o_fence_buffer,
    output wire [15:0] o_fence_tag,
    input wire i_fence_response_valid,
    output wire o_fence_response_ready,
    input wire [15:0] i_fence_response_tag,
    input wire [3:0] i_fence_response_status,
    output wire o_dispatch_valid,
    input wire i_dispatch_ready,
    output wire [7:0] o_dispatch_kind,
    output wire [7:0] o_dispatch_slot,
    output wire [15:0] o_dispatch_owner,
    output wire [15:0] o_dispatch_kernel,
    output wire [31:0] o_dispatch_package,
    output wire [15:0] o_dispatch_tag,
    output wire [7:0] o_dispatch_epoch,
    output wire [1535:0] o_dispatch_payload,
    input wire [15:0] i_dispatch_payload_bits,
    input wire i_dispatch_response_valid,
    output wire o_dispatch_response_ready,
    input wire [7:0] i_dispatch_response_error,
    input wire i_dispatch_response_fault,
    input wire [1023:0] i_dispatch_response_data,
    input wire [255:0] i_array_manifest_hash,
    input wire [N-1:0] i_array_allocated,
    input wire [N-1:0] i_array_running,
    input wire [N-1:0] i_array_fatal,
    input wire [N*4-1:0] i_array_native_epochs,
    input wire [N*16-1:0] i_array_native_generations,
    input wire [N*16-1:0] i_array_scratchpad_generations,
    input wire i_array_event_valid,
    output wire o_array_event_ready,
    input wire [2:0] i_array_event_type,
    input wire [15:0] i_array_event_source,
    input wire [15:0] i_array_event_owner,
    input wire [15:0] i_array_event_kernel,
    input wire [31:0] i_array_event_package,
    input wire [7:0] i_array_event_epoch,
    input wire [7:0] i_array_event_context,
    input wire [255:0] i_array_event_payload,
    input wire [31:0] i_array_event_sequence,
    input wire [1:0] i_array_event_severity,
    output wire o_interrupt,
    output wire o_fatal,
    output wire o_boot_ready,
    output wire [4:0] o_core_phase,
    output wire [3:0] o_system_state,
    output wire [31:0] o_event_count,
    output wire [31:0] o_command_count,
    output wire [255:0] o_system_manifest_hash
);
    import system_pkg::*;
    import system_registers_pkg::*;

    if (!VALID) begin : g_invalid
        system_core_parameters_must_be_valid invalid_parameters ();
    end else begin : g_core
        localparam int MB = D / 8;
        localparam int BEATS = 256 / MB;
        localparam int WORDS = D / 64;
        localparam int REGION_BITS = $bits(system_region_t);
        system_phase_t phase;
        logic response_valid;
        logic [31:0] response_data;
        logic [7:0] response_status;
        logic [7:0] response_tag;
        logic fatal;
        logic boot_seen;
        logic drain;
        logic [7:0] first_error;
        logic [63:0] first_address;
        logic [15:0] first_owner;
        logic [15:0] first_kernel;
        logic [31:0] irq_mask;
        logic [31:0] host_cycles;
        logic [31:0] program_shadow[3];
        logic [2:0] program_written;
        logic [15:0] program_lease;
        logic [31:0] buffer_shadow[6];
        logic [5:0] buffer_written;
        logic [15:0] buffer_lease;
        wire [REGION_BITS-1:0] region_words[B];
        wire [63:0] buffer_base[B];
        wire [31:0] buffer_size[B];
        wire [15:0] buffer_owner[B];
        wire [15:0] buffer_kernel[B];
        wire [15:0] buffer_generation[B];
        wire [1:0] buffer_permissions[B];
        wire [B-1:0] buffer_valid;
        wire [B-1:0] buffer_bad;
        logic [1:0] buffer_state[B];
        logic [15:0] last_generation[B];
        logic [B-1:0] buffer_locked;
        logic [B-1:0] output_filled;
        logic [B-1:0] input_loaded;
        logic register_commit;
        system_region_t new_region;
        wire ctrl_fire = i_ctrl_valid === 1'b1 && o_ctrl_ready;
        wire privileged = i_ctrl_privilege >= 4 && ^i_ctrl_privilege !== 1'bx;
        wire admin = privileged && i_ctrl_requester_id === 16'd1;
        wire control_known = ^{i_ctrl_write, i_ctrl_address, i_ctrl_write_data,
            i_ctrl_write_strobe, i_ctrl_requester_id, i_ctrl_privilege, i_ctrl_tag} !== 1'bx;
        logic [7:0] access_error;
        logic [31:0] read_data;
        logic program_push;
        wire program_ready;
        wire program_valid;
        wire program_bad;
        wire [103:0] program_head;
        wire [$clog2(COMMAND_DEPTH+1)-1:0] command_occupancy;
        wire publish_kernel;
        wire program_pop = phase == SYS_IDLE && program_valid && !fatal &&
            i_test_mode === 1'b0 && o_boot_ready && !program_bad && !publish_kernel;
        logic [7:0] program_buffer;
        logic [31:0] program_offset;
        logic [15:0] program_count;
        logic [15:0] program_generation;
        logic [15:0] program_owner;
        logic [15:0] program_kernel;
        logic [63:0] program_base;
        logic [15:0] program_region_generation;
        logic [15:0] record_index;
        logic [7:0] beat_index;
        logic [2047:0] record_data;
        wire [7:0] record_kind = record_data[55:48];
        wire [7:0] record_flags = record_data[63:56];
        wire [7:0] record_slot = record_data[159:152];
        wire [15:0] record_tag = record_data[207:192];
        wire dispatch_known = ^{i_dispatch_response_error,
            i_dispatch_response_fault, i_dispatch_response_data} !== 1'bx;
        logic [7:0] operation_error;
        logic cancel;
        logic [1023:0] last_result;
        logic [15:0] memory_id;
        logic [D-1:0] memory_data;
        logic [7:0] copy_buffer;
        logic [31:0] copy_offset;
        logic [31:0] copy_local;
        logic [31:0] copy_length;
        logic [31:0] copy_done;
        logic [1:0] copy_word;
        logic copy_store;
        logic [63:0] copy_base;
        logic [15:0] copy_region_generation;
        logic fence_from_host;
        logic [7:0] fence_buffer;
        logic [1:0] fence_target;
        logic [15:0] fence_tag;
        logic [15:0] fence_owner;
        logic [15:0] fence_kernel;
        logic [15:0] fence_generation;
        logic kernel_live;
        logic compute_done;
        logic kernel_reported;
        logic kernel_failed;
        logic [15:0] kernel_owner;
        logic [15:0] kernel_id;
        logic [31:0] kernel_package;
        logic [7:0] kernel_epoch;
        logic [B-1:0] kernel_outputs;
        logic [255:0] kernel_payload;
        logic kernel_pending;
        logic [31:0] kernel_timestamp;
        logic native_waiting;
        logic [31:0] native_timestamp;
        logic [31:0] finish_timestamp;
        logic finish_latched;
        logic [7:0] finish_error;
        logic kernel_report_error;
        logic [31:0] native_sequence;
        logic [31:0] event_sequence;
        wire event_ready;
        wire event_valid;
        wire event_bad;
        wire [511:0] event_head;
        wire [EVENT_DEPTH-1:0] event_occupied;
        wire [EVENT_DEPTH*512-1:0] event_contents;
        wire [$clog2(EVENT_DEPTH+1)-1:0] event_occupancy;
        logic event_ack;
        logic event_irq;
        logic output_ready;
        assign publish_kernel = kernel_live && compute_done && !kernel_reported &&
            (output_ready || kernel_failed);
        logic native_identity_ok;
        logic [2:0] event_request;
        wire [2:0] event_grant;
        wire event_grant_valid;
        wire event_arbiter_bad;
        system_event_t native_event;
        system_event_t program_event;
        system_event_t kernel_event;
        wire [511:0] selected_event = event_grant[0] ? native_event :
            event_grant[1] ? program_event : kernel_event;
        wire event_push = event_grant_valid && event_ready;
        wire [23:0] timer;
        logic [4:0] previous_phase;
        wire timer_clear = phase == SYS_IDLE || phase != previous_phase;
        wire [63:0] control_count;
        wire [63:0] read_count;
        wire [63:0] write_count;
        wire [63:0] event_count;
        logic [255:0] counter_snapshot;
        logic snapshot_valid;
        wire memory_read_phase = phase == SYS_FETCH_READ || phase == SYS_COPY_READ;
        wire read_identity = ^{i_mem_read_id, i_mem_read_status, i_mem_read_last,
            i_mem_read_keep, i_mem_read_data} !== 1'bx && i_mem_read_id == memory_id &&
            (i_mem_read_status != 0 ? i_mem_read_last :
                i_mem_read_last == (phase == SYS_COPY_READ || beat_index == BEATS - 1)) &&
            (&i_mem_read_keep);
        wire write_identity = ^{i_mem_write_response_id,
            i_mem_write_response_status} !== 1'bx && i_mem_write_response_id == memory_id;
        wire fence_identity = ^{i_fence_response_tag,
            i_fence_response_status} !== 1'bx && i_fence_response_tag == fence_tag;
        wire [7:0] memory_buffer = phase == SYS_FETCH_REQUEST || phase == SYS_FETCH_READ ?
            program_buffer : copy_buffer;
        wire [63:0] fetch_address = program_base + 64'(program_offset) +
            (64'(record_index) << 8) + 64'(beat_index) * MB;
        wire [63:0] copy_address = copy_base + 64'(copy_offset) +
            64'(copy_done);
        wire copy_local_phase = phase == SYS_COPY_LOCAL_ISSUE || phase == SYS_COPY_LOCAL_REPLY;
        logic [1535:0] local_payload;

        // The external reset-complete acknowledgement promises that old memory
        // responses are drained. Reset never guesses that a committed write vanished.
        assign o_boot_ready = i_rstb === 1'b1 && boot_seen && i_memory_reset_done === 1'b1 &&
            i_array_manifest_hash === ARRAY_HASH && !fatal && !(|buffer_bad) &&
            !program_bad && !event_bad;
        assign o_ctrl_ready = i_rstb === 1'b1 &&
            (!response_valid || i_ctrl_response_ready === 1'b1);
        assign o_ctrl_response_valid = i_rstb === 1'b1 && response_valid;
        assign o_ctrl_response_data = response_data;
        assign o_ctrl_response_status = response_status;
        assign o_ctrl_response_tag = response_tag;
        assign o_fatal = fatal;
        assign o_core_phase = phase;
        assign o_system_manifest_hash = SYSTEM_HASH;
        assign o_system_state = fatal ? 4'd6 : !o_boot_ready ? 4'd0 : drain ? 4'd5 :
            kernel_live && !kernel_reported ? 4'd4 : phase != SYS_IDLE || program_valid ?
            4'd3 : (|i_array_allocated) || event_valid || response_valid ? 4'd2 : 4'd1;
        assign o_event_count = 32'(event_occupancy);
        assign o_command_count = 32'(command_occupancy);
        assign o_interrupt = i_rstb === 1'b1 && (fatal || event_irq);
        assign o_mem_request_valid = i_rstb === 1'b1 && (phase == SYS_FETCH_REQUEST ||
            phase == SYS_COPY_READ_REQUEST || phase == SYS_COPY_WRITE_REQUEST);
        assign o_mem_request_write = phase == SYS_COPY_WRITE_REQUEST;
        assign o_mem_request_address = phase == SYS_FETCH_REQUEST ? fetch_address : copy_address;
        assign o_mem_request_length = phase == SYS_FETCH_REQUEST ? 16'd256 : 16'(MB);
        assign o_mem_request_size = 3'($clog2(MB));
        assign o_mem_request_id = memory_id;
        assign o_mem_request_requester = phase == SYS_FETCH_REQUEST ? 8'd0 : 8'd1;
        assign o_mem_request_owner = program_owner;
        assign o_mem_request_kernel = program_kernel;
        assign o_mem_request_buffer = 16'(memory_buffer);
        assign o_mem_request_generation = phase == SYS_FETCH_REQUEST ?
            program_region_generation : copy_region_generation;
        assign o_mem_request_descriptor_generation = program_generation;
        assign o_mem_request_package = phase == SYS_FETCH_REQUEST ? 32'd0 : record_data[127:96];
        assign o_mem_request_epoch = record_data[151:144];
        assign o_mem_write_valid = i_rstb === 1'b1 && phase == SYS_COPY_WRITE_DATA;
        assign o_mem_write_data = memory_data;
        assign o_mem_write_strobe = '1;
        assign o_mem_write_last = 1'b1;
        assign o_mem_write_id = memory_id;
        assign o_mem_read_ready = i_rstb === 1'b1 && memory_read_phase && read_identity;
        assign o_mem_write_response_ready = i_rstb === 1'b1 &&
            phase == SYS_COPY_WRITE_REPLY && write_identity;
        assign o_fence_valid = i_rstb === 1'b1 && phase == SYS_FENCE_REQUEST;
        assign o_fence_owner = fence_owner;
        assign o_fence_kernel = fence_kernel;
        assign o_fence_buffer = 16'(fence_buffer);
        assign o_fence_tag = fence_tag;
        assign o_fence_response_ready = i_rstb === 1'b1 && phase == SYS_FENCE_REPLY &&
            fence_identity;
        assign o_dispatch_valid = i_rstb === 1'b1 &&
            (phase == SYS_ISSUE || phase == SYS_COPY_LOCAL_ISSUE);
        assign o_dispatch_kind = copy_local_phase ? SYS_SRAM : record_kind;
        assign o_dispatch_slot = record_slot;
        assign o_dispatch_owner = program_owner;
        assign o_dispatch_kernel = program_kernel;
        assign o_dispatch_package = record_data[127:96];
        assign o_dispatch_tag = record_tag;
        assign o_dispatch_epoch = record_data[151:144];
        assign o_dispatch_payload = copy_local_phase ? local_payload : record_data[2047:512];
        assign o_dispatch_response_ready = i_rstb === 1'b1 &&
            (phase == SYS_REPLY || phase == SYS_COPY_LOCAL_REPLY);

        for (genvar slot = 0; slot < B; slot++) begin : g_region
            system_region_t decoded;
            assign decoded = region_words[slot];
            assign buffer_base[slot] = decoded.base;
            assign buffer_size[slot] = decoded.size;
            assign buffer_owner[slot] = decoded.owner;
            assign buffer_kernel[slot] = decoded.kernel;
            assign buffer_generation[slot] = decoded.generation;
            assign buffer_permissions[slot] = decoded.permissions;
            assign buffer_valid[slot] = decoded.valid;

            tile_shell_state #(.WIDTH(REGION_BITS),
            .PROTECTION(1)) u_region (
                .i_clk(i_clk),
                .i_rstb(i_rstb),
                .i_enable(register_commit && buffer_shadow[0] == slot),
                .i_data(new_region),
                .o_data(region_words[slot]),
                .o_bad(buffer_bad[slot]),
                .o_corrected()
            );
        end

        event_barrier_queue #(.WIDTH(104),
        .DEPTH(COMMAND_DEPTH),
        .PROTECTED(1)) u_commands (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_flush(1'b0),
            .i_valid(program_push),
            .o_ready(program_ready),
            .i_data({i_ctrl_requester_id, buffer_kernel[program_shadow[0][7:0]],
                program_shadow[0][7:0], program_shadow[1], program_shadow[2][15:0],
                program_shadow[2][31:16]}),
            .o_valid(program_valid),
            .i_ready(program_pop),
            .o_data(program_head),
            .o_occupancy(command_occupancy),
            .o_corrupt(program_bad),
            .o_occupied(),
            .o_contents()
        );

        event_barrier_queue #(.WIDTH(512),
        .DEPTH(EVENT_DEPTH),
        .PROTECTED(1)) u_events (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_flush(1'b0),
            .i_valid(event_grant_valid),
            .o_ready(event_ready),
            .i_data(selected_event),
            .o_valid(event_valid),
            .i_ready(event_ack),
            .o_data(event_head),
            .o_occupancy(event_occupancy),
            .o_corrupt(event_bad),
            .o_occupied(event_occupied),
            .o_contents(event_contents)
        );

        round_robin_arbiter #(.NUM_REQUESTERS(3),
        .HAS_LOCK(0)) u_event_arbiter (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_request(event_request),
            .i_eligible(3'b111),
            .i_lock(3'b000),
            .i_accept(event_grant_valid && event_ready),
            .i_flush(1'b0),
            .o_grant_valid(event_grant_valid),
            .o_grant_onehot(event_grant),
            .o_grant_index(),
            .o_grant_lock(),
            .o_grant_accepted(),
            .o_contended(),
            .o_pending(),
            .o_locked(),
            .o_lock_owner(),
            .o_protocol_error(event_arbiter_bad)
        );

        counter #(.WIDTH(24)) u_timeout (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(!timer_clear),
            .i_clear(timer_clear),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value(24'd0),
            .o_count(timer),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );

        counter #(.WIDTH(64)) u_control_count (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(ctrl_fire),
            .i_clear(1'b0),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value(64'd0),
            .o_count(control_count),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );

        counter #(.WIDTH(64)) u_read_count (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(i_mem_read_valid === 1'b1 && o_mem_read_ready),
            .i_clear(1'b0),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value(64'd0),
            .o_count(read_count),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );

        counter #(.WIDTH(64)) u_write_count (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(i_mem_write_response_valid === 1'b1 && o_mem_write_response_ready &&
                i_mem_write_response_status == 0),
            .i_clear(1'b0),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value(64'd0),
            .o_count(write_count),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );

        counter #(.WIDTH(64)) u_event_count (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(event_push),
            .i_clear(1'b0),
            .i_load(1'b0),
            .i_direction(1'b0),
            .i_load_value(64'd0),
            .o_count(event_count),
            .o_overflow(),
            .o_underflow(),
            .o_terminal()
        );

        always_comb begin
            local_payload = '0;
            local_payload[1:0] = copy_store ? 2'd0 : 2'd1;
            local_payload[33:2] = copy_local + copy_done + 32'(copy_word) * 8;
            local_payload[97:34] = 64'(memory_data >> (64 * copy_word));
            local_payload[105:98] = 8'hff;
            local_payload[121:106] = record_data[655:640];
            local_payload[124:122] = record_data[658:656];
        end

        // IRQ scans all occupied records, including unmasked records behind a
        // masked queue head. Reading a word never pops or acknowledges an event.
        always_comb begin
            event_irq = 1'b0;

            for (int slot = 0; slot < EVENT_DEPTH; slot++) begin
                if (event_occupied[slot] &&
                    (irq_mask[event_contents[slot*512+:8] < 8 ?
                        event_contents[slot*512+:8] : 7] ||
                        event_contents[slot*512+8+:2] == 3)) event_irq = 1'b1;
            end

            output_ready = 1'b1;

            for (int slot = 0; slot < B; slot++) begin
                if (kernel_outputs[slot] &&
                    (!output_filled[slot] || buffer_state[slot] !== SYS_HOST_OWNED))
                    output_ready = 1'b0;
            end

            native_identity_ok = ^{i_array_event_type, i_array_event_source,
                i_array_event_owner, i_array_event_kernel, i_array_event_package,
                i_array_event_epoch, i_array_event_context, i_array_event_payload,
                i_array_event_sequence, i_array_event_severity} !== 1'bx &&
                i_array_event_sequence == native_sequence;

            if (i_array_event_type == 2) native_identity_ok = native_identity_ok &&
                kernel_live && !compute_done && i_array_event_owner == kernel_owner &&
                i_array_event_kernel == kernel_id && i_array_event_package == kernel_package &&
                i_array_event_epoch == kernel_epoch;

            native_event = '0;
            native_event.kind = 8'h80 | {5'd0, i_array_event_type};
            native_event.severity = i_array_event_severity;
            native_event.source = i_array_event_source;
            native_event.owner = i_array_event_owner;
            native_event.kernel = i_array_event_kernel;
            native_event.package_id = i_array_event_package;
            native_event.epoch = i_array_event_epoch;
            native_event.context_id = i_array_event_context;
            native_event.payload = i_array_event_payload;
            native_event.source_sequence = i_array_event_sequence;
            native_event.sequence_id = event_sequence;
            native_event.timestamp = native_waiting ? native_timestamp : host_cycles;
            program_event = '0;
            program_event.kind = fence_from_host ? 8'd5 : 8'd3;
            program_event.owner = fence_from_host ? fence_owner : program_owner;
            program_event.kernel = fence_from_host ? fence_kernel : program_kernel;
            program_event.generation = fence_from_host ?
                fence_generation : program_generation;
            program_event.payload[15:0] = record_index;
            program_event.payload[23:16] = fence_from_host ? fence_buffer : program_buffer;
            program_event.payload[25:24] = fence_target;
            program_event.tag = fence_from_host ? fence_tag : record_tag;
            program_event.package_id = fence_from_host ? 32'd0 : record_data[127:96];
            program_event.detail = {8'd0, finish_latched ? finish_error : operation_error};
            program_event.sequence_id = event_sequence;
            program_event.timestamp = finish_timestamp;
            program_event.severity = program_event.detail == 0 ? 2'd0 : 2'd2;
            kernel_event = '0;
            kernel_event.kind = 8'd1;
            kernel_event.owner = kernel_owner;
            kernel_event.kernel = kernel_id;
            kernel_event.package_id = kernel_package;
            kernel_event.epoch = kernel_epoch;
            kernel_event.payload = kernel_payload;
            kernel_event.flags = kernel_report_error ? 6'b001001 : 6'b000111;
            kernel_event.detail = kernel_report_error ? 16'(SYS_MEMORY) : 16'd0;
            kernel_event.severity = kernel_report_error ? 2'd2 : 2'd0;
            kernel_event.sequence_id = event_sequence;
            kernel_event.timestamp = kernel_timestamp;
            event_request = '0;
            event_request[0] = i_array_event_valid === 1'b1 && native_identity_ok &&
                i_array_event_type != 2 && !event_bad;
            event_request[1] = phase == SYS_FINISH && !event_bad;
            event_request[2] = kernel_pending && !event_bad;

            if (event_sequence == 32'hffffffff) event_request = '0;
        end

        assign o_array_event_ready = i_rstb === 1'b1 && native_identity_ok &&
            (i_array_event_type == 2 ? !compute_done : event_grant[0] && event_ready);

        // Register validation is combinational; every architectural mutation is
        // qualified by exactly one accepted, fully validated control transfer.
        always_comb begin
            access_error = SYS_OK;
            read_data = '0;
            register_commit = 1'b0;
            program_push = 1'b0;
            event_ack = 1'b0;
            new_region = '0;
            new_region.valid = 1'b1;
            new_region.base = {buffer_shadow[2], buffer_shadow[1]};
            new_region.size = buffer_shadow[3];
            new_region.owner = buffer_shadow[4][15:0];
            new_region.kernel = buffer_shadow[4][31:16];
            new_region.generation = buffer_shadow[5][15:0];
            new_region.permissions = buffer_shadow[5][17:16];

            if (!control_known) access_error = SYS_INTEGRITY;
            else if (i_ctrl_address[1:0] != 0) access_error = SYS_ALIGNMENT;
            else if (i_ctrl_address >= 65536) access_error = SYS_DECODE;
            else if (i_ctrl_requester_id == 0 || i_ctrl_requester_id == 65535)
                access_error = SYS_PERMISSION;
            else if (i_ctrl_write && i_ctrl_write_strobe != 4'hf &&
                i_ctrl_address != SYS_REG_INTERRUPT_MASK) access_error = SYS_STROBE;
            else if (!i_ctrl_write) begin
                case (i_ctrl_address)
                    SYS_REG_IDENTITY: read_data = 32'h4d535953;
                    SYS_REG_VERSION: read_data = 32'h00010001;
                    SYS_REG_GEOMETRY: read_data = {8'(D), 8'(N), 8'(B), 8'd1};
                    SYS_REG_QUEUES: read_data = {8'(EVENT_DEPTH), 8'(COMMAND_DEPTH), 16'd256};
                    SYS_REG_STATUS: read_data = {29'd0, fatal, drain, o_boot_ready};
                    SYS_REG_STATE: read_data = {28'd0, o_system_state};
                    SYS_REG_PROGRAM_STATUS: read_data = {16'd0, 8'(phase), 8'(command_occupancy)};
                    SYS_REG_PROGRAM_RESULT: read_data = {8'd0, operation_error, record_index};
                    SYS_REG_NATIVE_EPOCHS, SYS_REG_NATIVE_GENERATIONS,
                        SYS_REG_SCRATCHPAD_GENERATIONS: begin
                        if (!admin && program_owner != i_ctrl_requester_id)
                            access_error = SYS_PERMISSION;
                        else case (i_ctrl_address)
                            SYS_REG_NATIVE_EPOCHS: read_data = 32'(i_array_native_epochs);
                            SYS_REG_NATIVE_GENERATIONS: read_data = 32'(i_array_native_generations);
                            SYS_REG_SCRATCHPAD_GENERATIONS: read_data =
                                32'(i_array_scratchpad_generations);
                            default: begin end
                        endcase
                    end
                    SYS_REG_BUFFER_STATUS: begin
                        if (buffer_shadow[0] >= B) access_error = SYS_BOUNDS;
                        else if (!admin && buffer_owner[buffer_shadow[0]] !=
                            i_ctrl_requester_id) access_error = SYS_PERMISSION;
                        else read_data = {last_generation[buffer_shadow[0]], 12'd0,
                            buffer_locked[buffer_shadow[0]], output_filled[buffer_shadow[0]],
                            buffer_state[buffer_shadow[0]]};
                    end
                    SYS_REG_INTERRUPT_MASK: begin
                        if (!admin) access_error = SYS_PERMISSION;
                        else read_data = irq_mask;
                    end
                    SYS_REG_EVENT_COUNT: read_data = {24'd0, 8'(event_occupancy)};
                    SYS_REG_INTERRUPT_STATUS: read_data = {31'd0, o_interrupt};
                    SYS_REG_COUNTER_VALID: begin
                        if (!admin) access_error = SYS_PERMISSION;
                        else read_data = {31'd0, snapshot_valid};
                    end
                    SYS_REG_FIRST_ERROR: begin
                        if (!admin) access_error = SYS_PERMISSION;
                        else read_data = {23'd0, fatal, first_error};
                    end
                    SYS_REG_ERROR_ADDRESS_LO: read_data = admin ? first_address[31:0] : 32'd0;
                    SYS_REG_ERROR_ADDRESS_HI: read_data = admin ? first_address[63:32] : 32'd0;
                    SYS_REG_ERROR_IDENTITY: read_data = admin ? {first_kernel, first_owner} : 32'd0;
                    SYS_REG_PROGRAM_DOORBELL, SYS_REG_PROGRAM_DISCARD, SYS_REG_PROGRAM_CANCEL,
                        SYS_REG_BUFFER_COMMIT, SYS_REG_BUFFER_DISCARD,
                    SYS_REG_BUFFER_FENCE, SYS_REG_EVENT_ACK, SYS_REG_COUNTER_SNAPSHOT,
                        SYS_REG_ERROR_CLEAR, SYS_REG_DRAIN: read_data = '0;
                    default: begin
                        if (i_ctrl_address >= SYS_REG_SYSTEM_HASH &&
                            i_ctrl_address < SYS_REG_ARRAY_HASH)
                            read_data = SYSTEM_HASH[(i_ctrl_address-SYS_REG_SYSTEM_HASH)*8+:32];
                        else if (i_ctrl_address >= SYS_REG_ARRAY_HASH && i_ctrl_address < 32'h0080)
                            read_data = ARRAY_HASH[(i_ctrl_address-SYS_REG_ARRAY_HASH)*8+:32];
                        else if (i_ctrl_address >= SYS_REG_PROGRAM_BUFFER && i_ctrl_address <=
                            SYS_REG_PROGRAM_COUNT_GENERATION)
                            read_data = program_lease == i_ctrl_requester_id ?
                                program_shadow[(i_ctrl_address-SYS_REG_PROGRAM_BUFFER)/4] : 32'd0;
                        else if (i_ctrl_address >= SYS_REG_BUFFER_INDEX && i_ctrl_address <=
                            SYS_REG_BUFFER_GENERATION_PERMISSIONS)
                            read_data = buffer_lease == i_ctrl_requester_id ?
                                buffer_shadow[(i_ctrl_address-SYS_REG_BUFFER_INDEX)/4] : 32'd0;
                        else if (i_ctrl_address >= SYS_REG_EVENT_HEAD &&
                            i_ctrl_address < 32'h4080) begin
                            if (!event_valid) access_error = SYS_BUSY;
                            else if (!admin && event_head[47:32] != i_ctrl_requester_id)
                                access_error = SYS_PERMISSION;
                            else read_data = event_head[(i_ctrl_address-SYS_REG_EVENT_HEAD)*8+:32];
                        end else if (i_ctrl_address >= SYS_REG_COUNTERS &&
                            i_ctrl_address < 32'h5030) begin
                            if (!admin) access_error = SYS_PERMISSION;
                            else if (!snapshot_valid) access_error = SYS_BUSY;
                            else read_data =
                                counter_snapshot[(i_ctrl_address-SYS_REG_COUNTERS)*8+:32];
                        end else if (i_ctrl_address >= SYS_REG_LAST_ARRAY_RESPONSE &&
                            i_ctrl_address < 32'h7180) begin
                            if (!admin && program_owner != i_ctrl_requester_id)
                                access_error = SYS_PERMISSION;
                            else read_data =
                                last_result[(i_ctrl_address-SYS_REG_LAST_ARRAY_RESPONSE)*8+:32];
                        end else access_error = SYS_DECODE;
                    end
                endcase
            end else begin
                case (i_ctrl_address)
                    SYS_REG_PROGRAM_BUFFER, SYS_REG_PROGRAM_OFFSET,
                        SYS_REG_PROGRAM_COUNT_GENERATION: begin
                        if (program_written != 0 && program_lease != i_ctrl_requester_id)
                            access_error = SYS_PERMISSION;
                        else if (!o_boot_ready || drain || i_test_mode !== 1'b0)
                            access_error = SYS_BUSY;
                    end
                    SYS_REG_PROGRAM_DOORBELL: begin
                        if (i_ctrl_write_data != 1 || program_written != 7)
                            access_error = SYS_DESCRIPTOR_ERROR;
                        else if (program_lease != i_ctrl_requester_id) access_error =
                            SYS_PERMISSION;
                        else if (!o_boot_ready || drain || i_test_mode !== 1'b0 || !program_ready)
                            access_error = SYS_BUSY;
                        else if (program_shadow[0] >= B || !buffer_valid[program_shadow[0]])
                            access_error = SYS_BOUNDS;
                        else if (buffer_owner[program_shadow[0]] != i_ctrl_requester_id)
                            access_error = SYS_PERMISSION;
                        else if (buffer_locked[program_shadow[0]] !== 1'b0) access_error = SYS_BUSY;
                        else if (buffer_state[program_shadow[0]] !== SYS_DMA_OWNED ||
                            !buffer_permissions[program_shadow[0]][0]) access_error = SYS_OWNERSHIP;
                        else if (program_shadow[1][7:0] != 0) access_error = SYS_ALIGNMENT;
                        else if (program_shadow[2][15:0] == 0 ||
                            {1'b0, program_shadow[1]} + ({17'd0, program_shadow[2][15:0]} << 8) >
                                {1'b0, buffer_size[program_shadow[0]]}) access_error = SYS_BOUNDS;
                        else if (last_generation[program_shadow[0]] == 65535 ||
                            program_shadow[2][31:16] != last_generation[program_shadow[0]] + 16'd1)
                            access_error = SYS_GENERATION;
                        else program_push = ctrl_fire;
                    end
                    SYS_REG_PROGRAM_DISCARD: begin
                        if (i_ctrl_write_data != 1) access_error = SYS_UNSUPPORTED;
                        else if (program_written != 0 && program_lease != i_ctrl_requester_id)
                            access_error = SYS_PERMISSION;
                    end
                    SYS_REG_PROGRAM_CANCEL: begin
                        if (i_ctrl_write_data != 1) access_error = SYS_UNSUPPORTED;
                        else if (program_owner != i_ctrl_requester_id || phase == SYS_IDLE ||
                            fence_from_host) access_error = SYS_PERMISSION;
                    end
                    SYS_REG_BUFFER_INDEX, SYS_REG_BUFFER_BASE_LO, SYS_REG_BUFFER_BASE_HI,
                        SYS_REG_BUFFER_SIZE, SYS_REG_BUFFER_OWNER_KERNEL,
                        SYS_REG_BUFFER_GENERATION_PERMISSIONS: begin
                        if (!privileged) access_error = SYS_PERMISSION;
                        else if (buffer_written != 0 && buffer_lease != i_ctrl_requester_id)
                            access_error = SYS_PERMISSION;
                    end
                    SYS_REG_BUFFER_DISCARD: begin
                        if (i_ctrl_write_data != 1) access_error = SYS_UNSUPPORTED;
                        else if (buffer_written != 0 && buffer_lease != i_ctrl_requester_id)
                            access_error = SYS_PERMISSION;
                    end
                    SYS_REG_BUFFER_COMMIT: begin
                        if (!privileged || buffer_lease != i_ctrl_requester_id ||
                            (!admin && new_region.owner != i_ctrl_requester_id))
                            access_error = SYS_PERMISSION;
                        else if (!o_boot_ready || i_test_mode !== 1'b0) access_error = SYS_BUSY;
                        else if (i_ctrl_write_data != 1 || buffer_written != 63 ||
                            buffer_shadow[5][31:18] != 0 || new_region.permissions == 0 ||
                            new_region.owner == 0 || new_region.owner == 65535)
                            access_error = SYS_DESCRIPTOR_ERROR;
                        else if (buffer_shadow[0] >= B || new_region.size == 0 ||
                            new_region.base < 64'h100000 ||
                            {1'b0, new_region.base} + 65'(new_region.size) > 65'hffffffffffffffff)
                            access_error = SYS_BOUNDS;
                        else if (new_region.base[7:0] != 0) access_error = SYS_ALIGNMENT;
                        else if (buffer_valid[buffer_shadow[0]] && !admin &&
                            buffer_owner[buffer_shadow[0]] != i_ctrl_requester_id)
                            access_error = SYS_PERMISSION;
                        else if (buffer_locked[buffer_shadow[0]] !== 1'b0 ||
                            buffer_state[buffer_shadow[0]] !== SYS_HOST_OWNED ||
                            (i_array_allocated !== {N{1'b0}})) access_error = SYS_BUSY;
                        else if (buffer_generation[buffer_shadow[0]] == 65535 ||
                            new_region.generation != buffer_generation[buffer_shadow[0]] + 16'd1)
                            access_error = SYS_GENERATION;

                        for (int slot = 0; slot < B; slot++) begin
                            if (slot != buffer_shadow[0] && buffer_valid[slot] &&
                                {1'b0, new_region.base} < {1'b0, buffer_base[slot]} +
                                    65'(buffer_size[slot]) && {1'b0, buffer_base[slot]} <
                                    {1'b0, new_region.base} + 65'(new_region.size))
                                access_error = SYS_BOUNDS;
                        end

                        register_commit = ctrl_fire && access_error == SYS_OK;
                    end
                    SYS_REG_BUFFER_FENCE: begin
                        if (!o_boot_ready || phase != SYS_IDLE || program_valid || publish_kernel ||
                            i_test_mode !== 1'b0) access_error = SYS_BUSY;
                        else if (i_ctrl_write_data[31:9] != 0 || i_ctrl_write_data[7:0] >= B ||
                            !buffer_valid[i_ctrl_write_data[7:0]]) access_error = SYS_BOUNDS;
                        else if (buffer_owner[i_ctrl_write_data[7:0]] != i_ctrl_requester_id)
                            access_error = SYS_PERMISSION;
                        else if (buffer_locked[i_ctrl_write_data[7:0]] !== 1'b0 ||
                            (i_ctrl_write_data[8] ?
                                buffer_state[i_ctrl_write_data[7:0]] !== SYS_HOST_OWNED :
                                buffer_state[i_ctrl_write_data[7:0]] !== SYS_DMA_OWNED))
                            access_error = SYS_OWNERSHIP;
                        else if (!i_ctrl_write_data[8] && kernel_live &&
                            kernel_outputs[i_ctrl_write_data[7:0]] &&
                            !output_filled[i_ctrl_write_data[7:0]]) access_error = SYS_OWNERSHIP;
                    end
                    SYS_REG_INTERRUPT_MASK: begin
                        if (!admin) access_error = SYS_PERMISSION;
                        else begin
                            for (int lane = 1; lane < 4; lane++) begin
                                if (i_ctrl_write_strobe[lane] &&
                                    i_ctrl_write_data[lane*8+:8] != 0)
                                    access_error = SYS_DESCRIPTOR_ERROR;
                            end
                        end
                    end
                    SYS_REG_EVENT_ACK: begin
                        if (!event_valid) access_error = SYS_BUSY;
                        else if (!admin && event_head[47:32] != i_ctrl_requester_id)
                            access_error = SYS_PERMISSION;
                        else if (i_ctrl_write_data != event_head[159:128])
                            access_error = SYS_GENERATION;
                        else event_ack = ctrl_fire;
                    end
                    SYS_REG_COUNTER_SNAPSHOT, SYS_REG_ERROR_CLEAR, SYS_REG_DRAIN: begin
                        if (!admin) access_error = SYS_PERMISSION;
                        else if (i_ctrl_write_data != 1) access_error = SYS_UNSUPPORTED;
                        else if (i_ctrl_address == SYS_REG_ERROR_CLEAR && fatal)
                            access_error = SYS_INTEGRITY;
                    end
                    default: access_error = system_register_readonly(i_ctrl_address) ?
                        SYS_PERMISSION : SYS_DECODE;
                endcase
            end
        end

        // Timeout containment records the fault but preserves any already offered
        // request/data bundle until its peer accepts it. There is no write retry.
        task automatic fail_operation(input logic [7:0] code, input logic hard);
            if (operation_error == 0) operation_error <= code;

            if (first_error == 0) begin
                first_error <= code;
                first_address <= ^o_mem_request_address !== 1'bx ? o_mem_request_address : 64'd0;
                first_owner <= ^program_owner !== 1'bx ? program_owner : 16'd0;
                first_kernel <= ^program_kernel !== 1'bx ? program_kernel : 16'd0;
            end

            if (hard) fatal <= 1'b1;

            if (kernel_live && kernel_owner == program_owner && kernel_id == program_kernel)
                kernel_failed <= 1'b1;
        endtask

        always_ff @(posedge i_clk) begin
            if (i_rstb !== 1'b1) begin
                phase <= SYS_IDLE;
                previous_phase <= SYS_IDLE;
                response_valid <= 1'b0;
                response_data <= '0;
                response_status <= '0;
                response_tag <= '0;
                fatal <= 1'b0;
                boot_seen <= 1'b0;
                drain <= 1'b0;
                first_error <= '0;
                first_address <= '0;
                first_owner <= '0;
                first_kernel <= '0;
                irq_mask <= 32'hff;
                host_cycles <= '0;
                program_written <= '0;
                program_lease <= '0;
                buffer_written <= '0;
                buffer_lease <= '0;
                buffer_locked <= '0;
                output_filled <= '0;
                input_loaded <= '0;
                program_buffer <= '0;
                program_offset <= '0;
                program_count <= '0;
                program_generation <= '0;
                program_owner <= '0;
                program_kernel <= '0;
                program_base <= '0;
                program_region_generation <= '0;
                record_index <= '0;
                beat_index <= '0;
                record_data <= '0;
                operation_error <= '0;
                cancel <= 1'b0;
                last_result <= '0;
                memory_id <= 16'd1;
                memory_data <= '0;
                copy_buffer <= '0;
                copy_offset <= '0;
                copy_local <= '0;
                copy_length <= '0;
                copy_done <= '0;
                copy_word <= '0;
                copy_store <= 1'b0;
                copy_base <= '0;
                copy_region_generation <= '0;
                fence_from_host <= 1'b0;
                fence_buffer <= '0;
                fence_target <= '0;
                fence_tag <= '0;
                fence_owner <= '0;
                fence_kernel <= '0;
                fence_generation <= '0;
                kernel_live <= 1'b0;
                compute_done <= 1'b0;
                kernel_reported <= 1'b0;
                kernel_failed <= 1'b0;
                kernel_owner <= '0;
                kernel_id <= '0;
                kernel_package <= '0;
                kernel_epoch <= '0;
                kernel_outputs <= '0;
                kernel_payload <= '0;
                kernel_pending <= 1'b0;
                kernel_timestamp <= '0;
                native_waiting <= 1'b0;
                native_timestamp <= '0;
                finish_timestamp <= '0;
                finish_latched <= 1'b0;
                finish_error <= '0;
                kernel_report_error <= 1'b0;
                native_sequence <= '0;
                event_sequence <= '0;
                counter_snapshot <= '0;
                snapshot_valid <= 1'b0;

                for (int word_index = 0; word_index < 3; word_index++)
                    program_shadow[word_index] <= '0;

                for (int word_index = 0; word_index < 6; word_index++)
                    buffer_shadow[word_index] <= '0;

                for (int slot = 0; slot < B; slot++) begin
                    buffer_state[slot] <= SYS_HOST_OWNED;
                    last_generation[slot] <= '0;
                end
            end else begin
                if (i_memory_reset_done === 1'b1 && i_array_manifest_hash === ARRAY_HASH)
                    boot_seen <= 1'b1;

                host_cycles <= host_cycles == 32'hffffffff ? host_cycles : host_cycles + 1'b1;
                previous_phase <= phase;
                if (phase != SYS_FINISH) finish_timestamp <= host_cycles + 1'b1;
                if (phase != SYS_FINISH) finish_latched <= 1'b0;
                else if (!finish_latched) begin
                    finish_error <= operation_error;
                    finish_latched <= 1'b1;
                end
                if (i_array_event_valid === 1'b1 && !native_waiting) begin
                    native_waiting <= 1'b1;
                    native_timestamp <= host_cycles;
                end
                if (phase == SYS_IDLE && publish_kernel && !kernel_pending) begin
                    kernel_pending <= 1'b1;
                    kernel_timestamp <= host_cycles;
                    kernel_report_error <= kernel_failed;
                end

                if (response_valid && i_ctrl_response_ready === 1'b1) response_valid <= 1'b0;

                if (ctrl_fire) begin
                    response_valid <= 1'b1;
                    response_data <= access_error == 0 ? read_data : 32'd0;
                    response_status <= access_error;
                    response_tag <= ^i_ctrl_tag !== 1'bx ? i_ctrl_tag : 8'd0;

                    if (access_error != 0 && first_error == 0) begin
                        first_error <= access_error;
                        first_address <= ^i_ctrl_address !== 1'bx ?
                            {32'd0, i_ctrl_address} : 64'd0;
                        first_owner <= ^i_ctrl_requester_id !== 1'bx ?
                            i_ctrl_requester_id : 16'd0;
                        first_kernel <= '0;
                    end

                    if (i_ctrl_write && access_error == 0) begin
                        case (i_ctrl_address)
                            SYS_REG_PROGRAM_BUFFER, SYS_REG_PROGRAM_OFFSET,
                                SYS_REG_PROGRAM_COUNT_GENERATION: begin
                                program_shadow[(i_ctrl_address-SYS_REG_PROGRAM_BUFFER)/4] <=
                                    i_ctrl_write_data;
                                program_written[(i_ctrl_address-SYS_REG_PROGRAM_BUFFER)/4] <= 1'b1;
                                program_lease <= i_ctrl_requester_id;
                            end
                            SYS_REG_PROGRAM_DOORBELL: begin
                                program_written <= '0;
                                buffer_locked[program_shadow[0]] <= 1'b1;
                                last_generation[program_shadow[0]] <= program_shadow[2][31:16];
                            end
                            SYS_REG_PROGRAM_DISCARD: program_written <= '0;
                            SYS_REG_PROGRAM_CANCEL: cancel <= 1'b1;
                            SYS_REG_BUFFER_INDEX, SYS_REG_BUFFER_BASE_LO,
                                SYS_REG_BUFFER_BASE_HI, SYS_REG_BUFFER_SIZE,
                                SYS_REG_BUFFER_OWNER_KERNEL,
                                SYS_REG_BUFFER_GENERATION_PERMISSIONS: begin
                                buffer_shadow[(i_ctrl_address-SYS_REG_BUFFER_INDEX)/4] <=
                                    i_ctrl_write_data;
                                buffer_written[(i_ctrl_address-SYS_REG_BUFFER_INDEX)/4] <= 1'b1;
                                buffer_lease <= i_ctrl_requester_id;
                            end
                            SYS_REG_BUFFER_COMMIT: begin
                                buffer_written <= '0;
                                last_generation[buffer_shadow[0]] <= '0;
                                output_filled[buffer_shadow[0]] <= 1'b0;
                                input_loaded[buffer_shadow[0]] <= 1'b0;
                            end
                            SYS_REG_BUFFER_DISCARD: buffer_written <= '0;
                            SYS_REG_BUFFER_FENCE: begin
                                buffer_locked[i_ctrl_write_data[7:0]] <= 1'b1;
                                fence_buffer <= i_ctrl_write_data[7:0];
                                fence_owner <= buffer_owner[i_ctrl_write_data[7:0]];
                                fence_kernel <= buffer_kernel[i_ctrl_write_data[7:0]];
                                fence_generation <= buffer_generation[i_ctrl_write_data[7:0]];
                                fence_target <= i_ctrl_write_data[8] ? SYS_DMA_OWNED
                                    : SYS_HOST_OWNED;
                                fence_tag <= {8'd0, i_ctrl_tag};
                                fence_from_host <= 1'b1;
                                operation_error <= '0;
                                phase <= SYS_FENCE_REQUEST;
                            end
                            SYS_REG_INTERRUPT_MASK: begin
                                for (int lane = 0; lane < 4; lane++) begin
                                    if (i_ctrl_write_strobe[lane])
                                        irq_mask[lane*8+:8] <= i_ctrl_write_data[lane*8+:8];
                                end
                            end
                            SYS_REG_COUNTER_SNAPSHOT: begin
                                counter_snapshot <= {event_count, write_count * MB,
                                    read_count * MB, control_count};
                                snapshot_valid <= 1'b1;
                            end
                            SYS_REG_ERROR_CLEAR: first_error <= '0;
                            SYS_REG_DRAIN: drain <= 1'b1;
                            default: begin end
                        endcase
                    end
                end

                if (event_push) begin
                    event_sequence <= event_sequence + 1'b1;

                    if (event_grant[2]) begin
                        kernel_reported <= 1'b1;
                        kernel_pending <= 1'b0;
                    end
                end

                if (i_array_event_valid === 1'b1 && o_array_event_ready) begin
                    native_waiting <= 1'b0;
                    native_sequence <= native_sequence + 1'b1;

                    if (i_array_event_type == 2) begin
                        compute_done <= 1'b1;
                        kernel_payload <= i_array_event_payload;
                    end

                    if (i_array_event_severity == 3) fail_operation(SYS_ARRAY, 1'b1);
                end

                if (boot_seen && ((|buffer_bad) || program_bad || event_bad || event_arbiter_bad ||
                    (|i_array_fatal) || (^{i_array_fatal} === 1'bx) ||
                    (i_array_event_valid === 1'b1 && !native_identity_ok) ||
                    event_sequence == 32'hffffffff || native_sequence == 32'hffffffff))
                    fail_operation(SYS_INTEGRITY, 1'b1);
                if (boot_seen && (i_memory_reset_done !== 1'b1 ||
                    i_array_manifest_hash !== ARRAY_HASH))
                    fail_operation(SYS_INTEGRITY, 1'b1);

                if (phase != SYS_IDLE && phase != SYS_FINISH && timer >= MEMORY_TIMEOUT)
                    fail_operation(SYS_TIMEOUT, 1'b1);

                if (memory_read_phase && i_mem_read_valid === 1'b1 && !read_identity)
                    fail_operation(SYS_MEMORY, 1'b1);

                if (phase == SYS_COPY_WRITE_REPLY && i_mem_write_response_valid === 1'b1 &&
                    !write_identity) fail_operation(SYS_MEMORY, 1'b1);

                if (phase == SYS_FENCE_REPLY && i_fence_response_valid === 1'b1 && !fence_identity)
                    fail_operation(SYS_MEMORY, 1'b1);

                case (phase)
                    SYS_IDLE: begin
                        if (program_pop) begin
                            {program_owner, program_kernel, program_buffer, program_offset,
                                program_count, program_generation} <= program_head;
                            program_base <= buffer_base[program_head[71:64]];
                            program_region_generation <= buffer_generation[program_head[71:64]];
                            record_index <= '0;
                            beat_index <= '0;
                            record_data <= '0;
                            operation_error <= '0;
                            cancel <= 1'b0;
                            fence_from_host <= 1'b0;
                            phase <= SYS_FETCH_REQUEST;
                        end
                    end
                    SYS_FETCH_REQUEST: begin
                        if (i_mem_request_ready === 1'b1) phase <= SYS_FETCH_READ;
                    end
                    SYS_FETCH_READ: begin
                        if (i_mem_read_valid === 1'b1 && o_mem_read_ready) begin
                            record_data[32'(beat_index)*D+:D] <= i_mem_read_data;

                            if (i_mem_read_status != 0 || i_mem_read_last) memory_id <=
                                memory_id + 1'b1;

                            if (i_mem_read_status != 0 ||
                                (i_mem_read_last && (fatal || cancel))) begin
                                fail_operation(cancel ? SYS_CANCELED : SYS_MEMORY, 1'b0);
                                phase <= SYS_FINISH;
                            end else if (beat_index == BEATS - 1) phase <= SYS_CHECK;
                            else begin
                                beat_index <= beat_index + 1'b1;
                            end
                        end
                    end
                    SYS_CHECK: begin
                        if (^{record_data} === 1'bx || record_data[31:0] != 32'h5359534d ||
                            record_data[47:32] != 1 || record_data[511:256] != SYSTEM_HASH ||
                            record_data[95:64] != {program_kernel, program_owner} ||
                            record_data[143:128] != program_generation ||
                            record_data[191:176] != 0 || record_data[223:208] != 0 ||
                            record_data[255:224] != system_crc(record_data) ||
                            i_dispatch_payload_bits == 16'hffff ||
                            record_data[175:160] != i_dispatch_payload_bits ||
                            (record_data[2047:512] >> i_dispatch_payload_bits) != 0 ||
                            record_slot >= N || record_kind == SYS_SRAM ||
                            (record_flags != 0 && !(record_kind == SYS_RUNTIME &&
                                record_data[516:512] == 5'd5))) begin
                            fail_operation(SYS_DESCRIPTOR_ERROR, 1'b0);
                            phase <= SYS_FINISH;
                        end else if (record_kind == SYS_RUNTIME &&
                            record_data[517+:N] != {N{1'b1}}) begin
                            fail_operation(SYS_UNSUPPORTED, 1'b0);
                            phase <= SYS_FINISH;
                        end else if (record_kind == SYS_RUNTIME &&
                            record_data[533+N+:8] != record_data[151:144]) begin
                            fail_operation(SYS_DESCRIPTOR_ERROR, 1'b0);
                            phase <= SYS_FINISH;
                        end else if (record_kind == SYS_RUNTIME &&
                            record_data[516:512] == 5'd12 && kernel_live && !kernel_reported) begin
                            fail_operation(SYS_BUSY, 1'b0);
                            phase <= SYS_FINISH;
                        end else if (fatal || cancel) begin
                            fail_operation(cancel ? SYS_CANCELED : SYS_INTEGRITY, 1'b0);
                            phase <= SYS_FINISH;
                        end else if (record_kind == SYS_LOAD || record_kind == SYS_STORE) begin
                            copy_buffer <= record_data[519:512];
                            copy_offset <= record_data[575:544];
                            copy_local <= record_data[607:576];
                            copy_length <= record_data[639:608];
                            copy_done <= '0;
                            copy_word <= '0;
                            copy_store <= record_kind == SYS_STORE;
                            phase <= SYS_COPY_CHECK;
                        end else if (record_kind == SYS_WAIT) begin
                            if (!kernel_live || program_owner != kernel_owner ||
                                program_kernel != kernel_id ||
                                    record_data[127:96] != kernel_package ||
                                record_data[151:144] != kernel_epoch) begin
                                fail_operation(SYS_OWNERSHIP, 1'b0);
                                phase <= SYS_FINISH;
                            end else phase <= SYS_WAIT_ARRAY;
                        end else if (record_kind == SYS_FENCE) begin
                            if (record_data[519:512] >= B ||
                                buffer_owner[record_data[519:512]] != program_owner ||
                                buffer_kernel[record_data[519:512]] != program_kernel ||
                                buffer_state[record_data[519:512]] !== SYS_DMA_OWNED ||
                                buffer_locked[record_data[519:512]] !== 1'b0 ||
                                (kernel_outputs[record_data[519:512]] &&
                                    !output_filled[record_data[519:512]])) begin
                                fail_operation(SYS_OWNERSHIP, 1'b0);
                                phase <= SYS_FINISH;
                            end else begin
                                fence_buffer <= record_data[519:512];
                                fence_owner <= buffer_owner[record_data[519:512]];
                                fence_kernel <= buffer_kernel[record_data[519:512]];
                                fence_generation <= buffer_generation[record_data[519:512]];
                                fence_target <= SYS_HOST_OWNED;
                                fence_tag <= record_tag;
                                phase <= SYS_FENCE_REQUEST;
                            end
                        end else if (record_kind == SYS_RUNTIME &&
                            record_data[516:512] == 5'd5) begin

                            if (kernel_live || (record_flags >> B) != 0) begin
                                fail_operation(SYS_BUSY, 1'b0);
                                phase <= SYS_FINISH;
                            end else begin
                                phase <= SYS_ISSUE;

                                for (int slot = 0; slot < B; slot++) begin
                                    if (record_flags[slot] && (!buffer_valid[slot] ||
                                        buffer_owner[slot] != program_owner ||
                                        buffer_kernel[slot] != program_kernel ||
                                        !buffer_permissions[slot][1] ||
                                        buffer_state[slot] !== SYS_DMA_OWNED)) begin
                                        fail_operation(SYS_OWNERSHIP, 1'b0);
                                        phase <= SYS_FINISH;
                                    end
                                    if (slot != program_buffer && buffer_valid[slot] &&
                                        buffer_owner[slot] == program_owner &&
                                        buffer_kernel[slot] == program_kernel &&
                                        buffer_permissions[slot][0] &&
                                        (!input_loaded[slot] ||
                                            buffer_state[slot] !== SYS_DMA_OWNED)) begin
                                        fail_operation(SYS_OWNERSHIP, 1'b0);
                                        phase <= SYS_FINISH;
                                    end
                                end
                            end
                        end else phase <= SYS_ISSUE;
                    end
                    SYS_ISSUE: begin
                        if (i_dispatch_ready === 1'b1) phase <= SYS_REPLY;
                    end
                    SYS_REPLY: begin
                        if (i_dispatch_response_valid === 1'b1) begin
                            if (dispatch_known) last_result <= i_dispatch_response_data;

                            if (i_dispatch_response_fault !== 1'b0 || !dispatch_known) begin
                                fail_operation(SYS_INTEGRITY, 1'b1);
                                phase <= SYS_FINISH;
                            end else if (i_dispatch_response_error !== 8'd0 || fatal) begin
                                fail_operation(SYS_ARRAY, 1'b0);
                                phase <= SYS_FINISH;
                            end else begin
                                if (record_kind == SYS_RUNTIME &&
                                    record_data[516:512] == 5'd5) begin
                                    kernel_live <= 1'b1;
                                    compute_done <= 1'b0;
                                    kernel_reported <= 1'b0;
                                    kernel_failed <= 1'b0;
                                    kernel_owner <= program_owner;
                                    kernel_id <= program_kernel;
                                    kernel_package <= record_data[127:96];
                                    kernel_epoch <= record_data[151:144];
                                    kernel_outputs <= B'(record_flags);
                                    output_filled <= output_filled & ~B'(record_flags);
                                end

                                if (record_kind == SYS_RUNTIME && record_data[516:512] == 5'd12)
                                    kernel_live <= 1'b0;

                                phase <= SYS_NEXT;
                            end
                        end
                    end
                    SYS_NEXT: begin
                        if (cancel || fatal) begin
                            fail_operation(cancel ? SYS_CANCELED : SYS_INTEGRITY, 1'b0);
                            phase <= SYS_FINISH;
                        end else if (record_index + 16'd1 == program_count) phase <= SYS_FINISH;
                        else begin
                            record_index <= record_index + 1'b1;
                            beat_index <= '0;
                            record_data <= '0;
                            phase <= SYS_FETCH_REQUEST;
                        end
                    end
                    SYS_FINISH: begin
                        if (event_push && event_grant[1]) begin
                            if (fence_from_host) buffer_locked[fence_buffer] <= 1'b0;
                            else buffer_locked[program_buffer] <= 1'b0;
                            phase <= SYS_IDLE;
                        end
                    end
                    SYS_COPY_CHECK: begin
                        if (copy_buffer >= B || copy_buffer == program_buffer ||
                            !buffer_valid[copy_buffer] || buffer_locked[copy_buffer] !== 1'b0 ||
                            copy_length == 0 || copy_length > 4096 ||
                            {1'b0, copy_offset} + {1'b0, copy_length} >
                                {1'b0, buffer_size[copy_buffer]} ||
                            {1'b0, copy_local} + {1'b0, copy_length} > SRAM_BYTES) begin
                            fail_operation(SYS_BOUNDS, 1'b0);
                            phase <= SYS_FINISH;
                        end else if (buffer_owner[copy_buffer] != program_owner ||
                            buffer_kernel[copy_buffer] != program_kernel ||
                            buffer_state[copy_buffer] !== SYS_DMA_OWNED ||
                            !buffer_permissions[copy_buffer][copy_store ? 1 : 0]) begin
                            fail_operation(SYS_OWNERSHIP, 1'b0);
                            phase <= SYS_FINISH;
                        end else if (copy_offset % MB != 0 || copy_length % MB != 0 ||
                            copy_local % MB != 0 || record_data[543:520] != 0 ||
                            record_data[671:659] != 0) begin
                            fail_operation(SYS_ALIGNMENT, 1'b0);
                            phase <= SYS_FINISH;
                        end else if (fatal || cancel) begin
                            fail_operation(cancel ? SYS_CANCELED : SYS_INTEGRITY, 1'b0);
                            phase <= SYS_FINISH;
                        end else if (kernel_live && (program_owner != kernel_owner ||
                            program_kernel != kernel_id || record_data[127:96] != kernel_package ||
                            record_data[151:144] != kernel_epoch)) begin
                            fail_operation(SYS_OWNERSHIP, 1'b0);
                            phase <= SYS_FINISH;
                        end else if (kernel_live && !compute_done) begin
                            if (copy_store) phase <= SYS_WAIT_ARRAY;
                            else begin
                                fail_operation(SYS_BUSY, 1'b0);
                                phase <= SYS_FINISH;
                            end
                        end else begin
                            copy_base <= buffer_base[copy_buffer];
                            copy_region_generation <= buffer_generation[copy_buffer];
                            phase <= copy_store ? SYS_COPY_LOCAL_ISSUE : SYS_COPY_READ_REQUEST;
                        end
                    end
                    SYS_COPY_READ_REQUEST: begin
                        if (i_mem_request_ready === 1'b1) phase <= SYS_COPY_READ;
                    end
                    SYS_COPY_READ: begin
                        if (i_mem_read_valid === 1'b1 && o_mem_read_ready) begin
                            memory_data <= i_mem_read_data;
                            memory_id <= memory_id + 1'b1;

                            if (i_mem_read_status != 0 || fatal || cancel) begin
                                fail_operation(cancel ? SYS_CANCELED : SYS_MEMORY, 1'b0);
                                buffer_state[copy_buffer] <= SYS_INVALID;
                                phase <= SYS_FINISH;
                            end else phase <= SYS_COPY_LOCAL_ISSUE;
                        end
                    end
                    SYS_COPY_LOCAL_ISSUE: begin
                        if (i_dispatch_ready === 1'b1) phase <= SYS_COPY_LOCAL_REPLY;
                    end
                    SYS_COPY_LOCAL_REPLY: begin
                        if (i_dispatch_response_valid === 1'b1) begin
                            if (dispatch_known) last_result <= i_dispatch_response_data;
                            if (i_dispatch_response_fault !== 1'b0 || !dispatch_known) begin
                                fail_operation(SYS_INTEGRITY, 1'b1);
                                buffer_state[copy_buffer] <= SYS_INVALID;
                                phase <= SYS_FINISH;
                            end else if (i_dispatch_response_error !== 8'd0 || fatal ||
                                cancel) begin
                                fail_operation(cancel ? SYS_CANCELED : SYS_ARRAY, 1'b0);
                                buffer_state[copy_buffer] <= SYS_INVALID;
                                phase <= SYS_FINISH;
                            end else begin
                                if (copy_store) memory_data[32'(copy_word)*64+:64] <=
                                    i_dispatch_response_data[63:0];

                                if (copy_word + 1 == WORDS) begin
                                    copy_word <= '0;
                                    phase <= copy_store ? SYS_COPY_WRITE_REQUEST : SYS_COPY_NEXT;
                                end else begin
                                    copy_word <= copy_word + 1'b1;
                                    phase <= SYS_COPY_LOCAL_ISSUE;
                                end
                            end
                        end
                    end
                    SYS_COPY_WRITE_REQUEST: begin
                        if (i_mem_request_ready === 1'b1) phase <= SYS_COPY_WRITE_DATA;
                    end
                    SYS_COPY_WRITE_DATA: begin
                        if (i_mem_write_ready === 1'b1) phase <= SYS_COPY_WRITE_REPLY;
                    end
                    SYS_COPY_WRITE_REPLY: begin
                        if (i_mem_write_response_valid === 1'b1 && o_mem_write_response_ready) begin
                            memory_id <= memory_id + 1'b1;

                            if (i_mem_write_response_status != 0 || fatal || cancel) begin
                                fail_operation(cancel ? SYS_CANCELED : SYS_MEMORY, 1'b0);
                                buffer_state[copy_buffer] <= SYS_INVALID;
                                phase <= SYS_FINISH;
                            end else phase <= SYS_COPY_NEXT;
                        end
                    end
                    SYS_COPY_NEXT: begin
                        if (cancel || fatal) begin
                            fail_operation(cancel ? SYS_CANCELED : SYS_INTEGRITY, 1'b0);
                            buffer_state[copy_buffer] <= SYS_INVALID;
                            phase <= SYS_FINISH;
                        end else if (copy_done + MB == copy_length) begin
                            if (copy_store && copy_offset == 0 &&
                                copy_length == buffer_size[copy_buffer])
                                output_filled[copy_buffer] <= 1'b1;
                            if (!copy_store && copy_offset == 0 &&
                                copy_length == buffer_size[copy_buffer]) begin
                                input_loaded[copy_buffer] <= 1'b1;
                            end
                            phase <= SYS_NEXT;
                        end else begin
                            copy_done <= copy_done + MB;
                            phase <= copy_store ? SYS_COPY_LOCAL_ISSUE : SYS_COPY_READ_REQUEST;
                        end
                    end
                    SYS_WAIT_ARRAY: begin
                        if (cancel || fatal) begin
                            fail_operation(cancel ? SYS_CANCELED : SYS_INTEGRITY, 1'b0);
                            phase <= SYS_FINISH;
                        end else if (compute_done) begin
                            phase <= record_kind == SYS_STORE ? SYS_COPY_CHECK : SYS_NEXT;
                        end
                    end
                    SYS_FENCE_REQUEST: begin
                        if (i_fence_ready === 1'b1) phase <= SYS_FENCE_REPLY;
                    end
                    SYS_FENCE_REPLY: begin
                        if (i_fence_response_valid === 1'b1 && o_fence_response_ready) begin
                            if (i_fence_response_status != 0 || fatal) begin
                                fail_operation(SYS_MEMORY, 1'b0);
                                buffer_state[fence_buffer] <= SYS_INVALID;
                                phase <= SYS_FINISH;
                            end else begin
                                buffer_state[fence_buffer] <= fence_target;
                                if (fence_target == SYS_DMA_OWNED) begin
                                    input_loaded[fence_buffer] <= 1'b0;
                                    output_filled[fence_buffer] <= 1'b0;
                                end
                                phase <= fence_from_host ? SYS_FINISH : SYS_NEXT;
                            end
                        end
                    end
                    default: fail_operation(SYS_INTEGRITY, 1'b1);
                endcase

                if (memory_id == 65535 && phase != SYS_IDLE && phase != SYS_FINISH)
                    fail_operation(SYS_GENERATION, 1'b1);
            end
        end
    end
endmodule
`default_nettype wire
