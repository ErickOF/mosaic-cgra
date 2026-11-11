`timescale 1ns / 1ps
`default_nettype none

// Region-managed composition of the released controller and real SRAM banks.
module banked_scratchpad #(
    parameter DATA_WIDTH = 64,
    parameter NUM_BANKS = 8,
    parameter BANK_DEPTH_WORDS = 1024,
    parameter NUM_CLIENTS = 4,
    parameter CLIENT_TAG_WIDTH = 8,
    parameter MAX_OUTSTANDING_PER_CLIENT = 8,
    parameter INTERLEAVE_BYTES = 8,
    parameter MAP_MODE = 0,
    parameter BACKEND_READ_LATENCY = 1,
    parameter NUM_REGIONS = 8,
    parameter OWNER_ID_WIDTH = 16,
    parameter KERNEL_ID_WIDTH = 16,
    parameter REGION_GENERATION_WIDTH = 16,
    parameter BUFFER_GROUP_WIDTH = 4,
    parameter ENFORCE_REGIONS = 1,
    parameter ENFORCE_BANK_PERMISSIONS = 1,
    parameter DEFAULT_ALLOW = 0,
    parameter SUPPORT_DOUBLE_BUFFER = 1,
    parameter PROTECTION_MODE = 0,
    parameter PARITY_GRANULARITY = 8,
    parameter SCRUB_ON_CORRECT = 1,
    parameter SUPPORT_BANK_POWER_GATING = 0,
    parameter SUPPORT_BANK_RETENTION = 0,
    parameter CONTROL_PROTECTION = 0,
    parameter ASYNC_RESET = 0,
    localparam bit PARAMETERS_VALID =
        ((DATA_WIDTH > 0) === 1'b1) && (((^DATA_WIDTH == 1'b0) || (^DATA_WIDTH == 1'b1)) === 1'b1) &&
        ((NUM_BANKS > 0) === 1'b1) && (((^NUM_BANKS == 1'b0) || (^NUM_BANKS == 1'b1)) === 1'b1) &&
        ((BANK_DEPTH_WORDS > 0) === 1'b1) && (((^BANK_DEPTH_WORDS == 1'b0) || (^BANK_DEPTH_WORDS == 1'b1)) === 1'b1) &&
        ((NUM_CLIENTS > 0) === 1'b1) && (((^NUM_CLIENTS == 1'b0) || (^NUM_CLIENTS == 1'b1)) === 1'b1) &&
        ((CLIENT_TAG_WIDTH > 0) === 1'b1) && (((^CLIENT_TAG_WIDTH == 1'b0) || (^CLIENT_TAG_WIDTH == 1'b1)) === 1'b1) &&
        ((MAX_OUTSTANDING_PER_CLIENT > 0) === 1'b1) && (((^MAX_OUTSTANDING_PER_CLIENT == 1'b0) || (^MAX_OUTSTANDING_PER_CLIENT == 1'b1)) === 1'b1) &&
        ((INTERLEAVE_BYTES > 0) === 1'b1) && (((^INTERLEAVE_BYTES == 1'b0) || (^INTERLEAVE_BYTES == 1'b1)) === 1'b1) &&
        ((BACKEND_READ_LATENCY > 0) === 1'b1) && (((^BACKEND_READ_LATENCY == 1'b0) || (^BACKEND_READ_LATENCY == 1'b1)) === 1'b1) &&
        ((NUM_REGIONS > 0) === 1'b1) && (((^NUM_REGIONS == 1'b0) || (^NUM_REGIONS == 1'b1)) === 1'b1) &&
        ((OWNER_ID_WIDTH > 0) === 1'b1) && (((^OWNER_ID_WIDTH == 1'b0) || (^OWNER_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((KERNEL_ID_WIDTH > 0) === 1'b1) && (((^KERNEL_ID_WIDTH == 1'b0) || (^KERNEL_ID_WIDTH == 1'b1)) === 1'b1) &&
        ((REGION_GENERATION_WIDTH > 0) === 1'b1) && (((^REGION_GENERATION_WIDTH == 1'b0) || (^REGION_GENERATION_WIDTH == 1'b1)) === 1'b1) &&
        ((BUFFER_GROUP_WIDTH > 0) === 1'b1) && (((^BUFFER_GROUP_WIDTH == 1'b0) || (^BUFFER_GROUP_WIDTH == 1'b1)) === 1'b1) &&
        ((PARITY_GRANULARITY > 0) === 1'b1) && (((^PARITY_GRANULARITY == 1'b0) || (^PARITY_GRANULARITY == 1'b1)) === 1'b1) &&
        ((ENFORCE_REGIONS === 0) || (ENFORCE_REGIONS === 1)) &&
        ((ENFORCE_BANK_PERMISSIONS === 0) || (ENFORCE_BANK_PERMISSIONS === 1)) &&
        ((DEFAULT_ALLOW === 0) || (DEFAULT_ALLOW === 1)) &&
        ((SUPPORT_DOUBLE_BUFFER === 0) || (SUPPORT_DOUBLE_BUFFER === 1)) &&
        ((SCRUB_ON_CORRECT === 0) || (SCRUB_ON_CORRECT === 1)) &&
        ((SUPPORT_BANK_POWER_GATING === 0) || (SUPPORT_BANK_POWER_GATING === 1)) &&
        ((SUPPORT_BANK_RETENTION === 0) || (SUPPORT_BANK_RETENTION === 1)) &&
        ((ASYNC_RESET === 0) || (ASYNC_RESET === 1)) &&
        ((DATA_WIDTH % 8 == 0) === 1'b1) &&
        ((((DATA_WIDTH / 8) & ((DATA_WIDTH / 8) - 1)) == 0) === 1'b1) &&
        (((INTERLEAVE_BYTES & (INTERLEAVE_BYTES - 1)) == 0) === 1'b1) &&
        ((INTERLEAVE_BYTES >= DATA_WIDTH / 8) === 1'b1) &&
        ((64'(BANK_DEPTH_WORDS) * 64'(DATA_WIDTH / 8) %
            64'(INTERLEAVE_BYTES > 0 ? INTERLEAVE_BYTES : 1) == 0) === 1'b1) &&
        ((MAP_MODE === 0) || (MAP_MODE === 1)) &&
        ((MAP_MODE == 0 || (NUM_BANKS & (NUM_BANKS - 1)) == 0) === 1'b1) &&
        ((PROTECTION_MODE === 0) || (PROTECTION_MODE === 1) || (PROTECTION_MODE === 2)) &&
        ((CONTROL_PROTECTION === 0) || (CONTROL_PROTECTION === 1) || (CONTROL_PROTECTION === 2)) &&
        ((PROTECTION_MODE != 2 || DATA_WIDTH <= 256) === 1'b1) &&
        ((PROTECTION_MODE != 1 || (PARITY_GRANULARITY >= 8 &&
            PARITY_GRANULARITY % 8 == 0 && DATA_WIDTH %
            (PARITY_GRANULARITY > 0 ? PARITY_GRANULARITY : 1) == 0)) === 1'b1) &&
        ((SUPPORT_BANK_RETENTION == 0 || SUPPORT_BANK_POWER_GATING == 1) === 1'b1) &&
        ((128'(NUM_BANKS) * 128'(BANK_DEPTH_WORDS) * 128'(DATA_WIDTH) <
            128'd2147483647) === 1'b1) &&
        ((128'(NUM_CLIENTS) * 128'(MAX_OUTSTANDING_PER_CLIENT) *
            (128'(DATA_WIDTH) + 128'(CLIENT_TAG_WIDTH) + 512) < 128'd2147483647) === 1'b1),
    localparam int D = PARAMETERS_VALID ? DATA_WIDTH : 8,
    localparam int B = PARAMETERS_VALID ? NUM_BANKS : 1,
    localparam int C = PARAMETERS_VALID ? NUM_CLIENTS : 1,
    localparam int N = PARAMETERS_VALID ? MAX_OUTSTANDING_PER_CLIENT : 1,
    localparam int R = PARAMETERS_VALID ? NUM_REGIONS : 1,
    localparam int T = PARAMETERS_VALID ? CLIENT_TAG_WIDTH : 1,
    localparam int O = PARAMETERS_VALID ? OWNER_ID_WIDTH : 1,
    localparam int K = PARAMETERS_VALID ? KERNEL_ID_WIDTH : 1,
    localparam int G = PARAMETERS_VALID ? REGION_GENERATION_WIDTH : 1,
    localparam int BG = PARAMETERS_VALID ? BUFFER_GROUP_WIDTH : 1,
    localparam int WORDS = PARAMETERS_VALID ? BANK_DEPTH_WORDS : 1,
    localparam int STRIPE = PARAMETERS_VALID ? INTERLEAVE_BYTES : 1,
    localparam int Y = D / 8,
    localparam logic [63:0] BANK_BYTES = 64'(WORDS) * 64'(Y),
    localparam logic [63:0] CAPACITY = 64'(B) * BANK_BYTES,
    localparam int A = CAPACITY > 1 ? $clog2(CAPACITY) : 1,
    localparam int BA = BANK_BYTES > 1 ? $clog2(BANK_BYTES) : 1,
    localparam int Z = $clog2(Y + 1),
    localparam int LZ = Y > 1 ? $clog2($clog2(Y) + 1) : 1,
    localparam int RI = R > 1 ? $clog2(R) : 1,
    localparam int CI = C > 1 ? $clog2(C) : 1,
    localparam int BI = B > 1 ? $clog2(B) : 1,
    localparam int SI = N > 1 ? $clog2(N) : 1,
    localparam int CO = $clog2(64'(N) + 1),
    localparam int RO = $clog2(64'(C) * 64'(N) + 1),
    localparam int BN = N > BACKEND_READ_LATENCY ? N : BACKEND_READ_LATENCY,
    localparam int BO = $clog2(64'(PARAMETERS_VALID ? BN : 1) + 1),
    localparam int BT = CI + SI,
    localparam int IT = CI + SI + 32,
    localparam int DW = 1 + A + A + 1 + O + K + 3 + 1 + 2 * C + G + BG + 2 + 2
) (
    input wire i_clk,
    input wire i_reset_n,
    input wire i_enable,
    input wire i_drain,
    input wire i_flush,
    input wire i_error_clear,
    output wire o_idle,
    output wire o_busy,
    output wire o_drained,
    output wire o_flush_completed,
    input wire [C-1:0] i_client_req_valid,
    input wire [C-1:0] i_client_rsp_ready,
    output wire [C-1:0] o_client_req_ready,
    output wire [C-1:0] o_client_rsp_valid,
    output wire [C-1:0] o_client_rsp_error,
    output wire [C-1:0] o_client_rsp_corrected,
    output wire [C-1:0] o_client_rsp_uncorrectable,
    output wire [C-1:0] o_permission_denied,
    input wire [C*2-1:0] i_client_req_opcode,
    input wire [C*A-1:0] i_client_req_addr,
    input wire [C*Z-1:0] i_client_req_size,
    input wire [C*D-1:0] i_client_req_wdata,
    input wire [C*Y-1:0] i_client_req_wstrb,
    input wire [C*O-1:0] i_client_req_owner_id,
    input wire [C*K-1:0] i_client_req_kernel_id,
    input wire [C*RI-1:0] i_client_req_region_id,
    input wire [C*G-1:0] i_client_req_generation,
    input wire [C*T-1:0] i_client_req_tag,
    output wire [C*2-1:0] o_client_rsp_opcode,
    output wire [C*D-1:0] o_client_rsp_rdata,
    output wire [C*RI-1:0] o_client_rsp_region_id,
    output wire [C*G-1:0] o_client_rsp_generation,
    output wire [C*T-1:0] o_client_rsp_tag,
    output wire [C*8-1:0] o_client_rsp_error_code,
    input wire i_region_cmd_valid,
    input wire i_region_contents_valid,
    input wire i_region_rsp_ready,
    output wire o_region_cmd_ready,
    output wire o_region_rsp_valid,
    output wire o_region_rsp_error,
    input wire [2:0] i_region_cmd_opcode,
    input wire [RI-1:0] i_region_cmd_a,
    input wire [RI-1:0] i_region_cmd_b,
    input wire [G-1:0] i_region_expected_generation_a,
    input wire [G-1:0] i_region_expected_generation_b,
    input wire [2:0] i_region_expected_state_a,
    input wire [2:0] i_region_expected_state_b,
    input wire [A-1:0] i_region_base,
    input wire [(A+1)-1:0] i_region_limit,
    input wire [O-1:0] i_region_owner_id,
    input wire [K-1:0] i_region_kernel_id,
    input wire [2:0] i_region_state,
    input wire [C-1:0] i_region_read_mask,
    input wire [C-1:0] i_region_write_mask,
    input wire [BG-1:0] i_region_buffer_group,
    input wire [1:0] i_region_buffer_role,
    output wire [DW-1:0] o_region_rsp_descriptor,
    output wire [7:0] o_region_rsp_error_code,
    input wire [B-1:0] i_bank_power_cmd_valid,
    input wire [B-1:0] i_bank_power_ack,
    input wire [B*2-1:0] i_bank_power_state,
    output wire [B*2-1:0] o_bank_power_state,
    output wire [B-1:0] o_bank_power_cmd_ready,
    output wire [B-1:0] o_bank_clock_enable,
    output wire [B-1:0] o_bank_isolate,
    output wire [B-1:0] o_bank_retention_save,
    output wire [B-1:0] o_bank_retention_restore,
    output wire [B-1:0] o_bank_power_enable,
    output wire [B-1:0] o_bank_contents_valid,
    output wire [B-1:0] o_bank_conflict,
    output wire [B-1:0] o_corrected_event,
    output wire [B-1:0] o_uncorrectable_event,
    output wire [C*CO-1:0] o_client_outstanding,
    output wire [R*RO-1:0] o_region_outstanding,
    output wire [B*BO-1:0] o_bank_outstanding,
    output wire [B*CI-1:0] o_bank_grant,
    output wire o_region_transition_event,
    output wire o_error,
    output wire o_event_valid,
    output wire [7:0] o_error_code,
    output wire [7:0] o_event_error_code,
    input wire i_event_ready,
    output wire [2:0] o_event_code,
    output wire [RI-1:0] o_event_region_a,
    output wire [RI-1:0] o_event_region_b,
    output wire [G-1:0] o_event_generation_a,
    output wire [G-1:0] o_event_generation_b,
    output wire [K-1:0] o_event_kernel_id
);
    import banked_scratchpad_pkg::*;

    if (!PARAMETERS_VALID) begin : g_invalid
        banked_scratchpad_parameters_must_be_valid u_invalid ();
    end else begin : g_scratchpad
        // Width-dependent records stay with their parameterized owner. Descriptor
        // packing is MSB-first in this declaration order (documented with the API).
        typedef struct packed {
            logic valid;
            logic [A-1:0] base;
            logic [A:0] limit;
            logic [O-1:0] owner;
            logic [K-1:0] kernel;
            logic [2:0] state;
            logic contents;
            logic [C-1:0] read_mask;
            logic [C-1:0] write_mask;
            logic [G-1:0] generation;
            logic [BG-1:0] group_id;
            logic [1:0] role;
            logic corrected;
            logic uncorrectable;
        } descriptor_t;

        typedef struct packed {
            logic allocated;
            logic complete;
            logic dispatched;
            logic [31:0] epoch;
            logic [15:0] age;
            logic [1:0] opcode;
            logic [A-1:0] address;
            logic [Z-1:0] size;
            logic [D-1:0] wdata;
            logic [Y-1:0] strobe;
            logic [O-1:0] owner;
            logic [K-1:0] kernel;
            logic [RI-1:0] region_id;
            logic [G-1:0] generation;
            logic [T-1:0] tag;
            logic [BI-1:0] bank;
            logic region_counted;
            logic [D-1:0] data;
            logic [7:0] code;
            logic corrected;
            logic uncorrectable;
        } slot_t;

        typedef struct packed {
            logic [SI-1:0] head;
            logic [SI-1:0] tail;
            logic [CO-1:0] count;
            logic fence;
        } client_t;

        typedef struct packed {
            logic [1:0] phase;
            logic [2:0] command;
            logic [RI-1:0] a;
            logic [RI-1:0] b;
            logic [G-1:0] expected_a;
            logic [G-1:0] expected_b;
            logic [2:0] state_a;
            logic [2:0] state_b;
            logic unknown_command;
            descriptor_t proposed;
            descriptor_t response;
            logic [7:0] code;
            logic event_valid;
            logic [2:0] event_code;
            logic [RI-1:0] event_a;
            logic [RI-1:0] event_b;
            logic [G-1:0] event_ga;
            logic [G-1:0] event_gb;
            logic [K-1:0] event_kernel;
            logic [7:0] event_error;
            logic transition_event;
        } manager_t;

        localparam int SW = $bits(slot_t);
        localparam int CW = $bits(client_t);
        wire [DW-1:0] descriptors [R];
        logic [DW-1:0] descriptor_next [R];
        wire [SW-1:0] slots [C][N];
        logic [SW-1:0] slot_next [C][N];
        wire [CW-1:0] clients [C];
        logic [CW-1:0] client_next [C];
        wire [R-1:0] descriptor_bad;
        wire [C*N-1:0] slot_bad;
        wire [C-1:0] client_bad;
        manager_t manager;
        manager_t manager_next;
        wire manager_bad;
        wire [B-1:0] power_busy;
        wire [B-1:0] power_bad;
        logic [B-1:0] off_allowed;
        logic [B-1:0] publish;
        logic [C*B-1:0] read_permission;
        logic [C*B-1:0] write_permission;
        logic [R*RO-1:0] region_outstanding;
        logic [C*CO-1:0] client_outstanding;
        logic any_outstanding;
        wire controller_idle;
        wire controller_error;
        wire [3:0] controller_error_code;
        wire controller_flush_done;
        wire controller_flushing;
        wire permission_ready;
        wire permission_updated;
        wire [B-1:0] bank_idle;
        wire [B-1:0] bank_bad;
        wire [B-1:0] bank_flush_done;
        wire [B-1:0] bank_flush;
        wire [B-1:0] bank_req_valid;
        wire [B-1:0] bank_req_ready;
        wire [B-1:0] bank_req_write;
        wire [B*BA-1:0] bank_req_address;
        wire [B*LZ-1:0] bank_req_size;
        wire [B*D-1:0] bank_req_data;
        wire [B*Y-1:0] bank_req_strobe;
        wire [B*BT-1:0] bank_req_tag;
        wire [B-1:0] bank_rsp_valid;
        wire [B-1:0] bank_rsp_ready;
        wire [B-1:0] bank_rsp_write;
        wire [B*D-1:0] bank_rsp_data;
        wire [B*BT-1:0] bank_rsp_tag;
        wire [B-1:0] bank_rsp_error;
        wire [B*4-1:0] bank_rsp_code;
        wire [B-1:0] bank_rsp_corrected;
        wire [B-1:0] bank_rsp_uncorrectable;
        logic [C-1:0] dispatch_valid;
        logic [C-1:0] dispatch_write;
        logic [C*A-1:0] dispatch_address;
        logic [C*LZ-1:0] dispatch_size;
        logic [C*D-1:0] dispatch_data;
        logic [C*Y-1:0] dispatch_strobe;
        logic [C*IT-1:0] dispatch_tag;
        logic [SI-1:0] dispatch_slot [C];
        wire [C-1:0] dispatch_ready;
        wire [C-1:0] completion_valid;
        wire [C-1:0] completion_write;
        wire [C*D-1:0] completion_data;
        wire [C*IT-1:0] completion_tag;
        wire [C-1:0] completion_error;
        wire [C*4-1:0] completion_code;
        wire [C-1:0] completion_corrected;
        wire [C-1:0] completion_uncorrectable;
        logic [C-1:0] admission_ready;
        logic [C-1:0] response_valid;
        logic [C*2-1:0] response_opcode;
        logic [C*D-1:0] response_data;
        logic [C*RI-1:0] response_region;
        logic [C*G-1:0] response_generation;
        logic [C*T-1:0] response_tag;
        logic [C-1:0] response_error;
        logic [C*8-1:0] response_code;
        logic [C-1:0] response_corrected;
        logic [C-1:0] response_uncorrectable;
        logic [C-1:0] denied;
        logic [7:0] new_error;
        logic [7:0] sticky_next;
        wire [7:0] sticky;
        wire sticky_bad;
        wire run = i_reset_n === 1'b1;
        wire cancel = i_flush !== 1'b0 || controller_flushing;
        wire integrity_bad = manager_bad || (|descriptor_bad) || (|slot_bad) ||
            (|client_bad) || sticky_bad;
        wire quiet = !any_outstanding && controller_idle && !(|power_busy);
        wire manager_blocks = manager.phase != MANAGER_IDLE &&
            !(manager.command == REGION_CMD_READ && manager.phase == MANAGER_RESPONSE);
        wire active = run && !cancel && !o_error && !integrity_bad;
        wire permission_offer = active && manager.phase == MANAGER_PERMISSIONS;
        wire power_quiet = active && quiet && manager.phase == MANAGER_IDLE &&
            i_region_cmd_valid === 1'b0 && i_client_req_valid === {C{1'b0}};

        function automatic int mapped_bank(input logic [63:0] address);
            logic [63:0] stripe_number;
            logic [63:0] bank;
            stripe_number = address / STRIPE;
            bank = stripe_number % B;

            if (MAP_MODE == 1) bank ^= (stripe_number / B) % B;

            return int'(bank);
        endfunction

        // A contiguous range of 2*B stripes contains a complete bank row, also
        // for XOR mapping. Inspect shorter ranges exactly, including row seams.
        function automatic logic touches(input descriptor_t d, input int bank);
            logic hit;
            logic [63:0] first;
            logic [63:0] last;
            hit = 1'b0;
            first = 64'(d.base) / STRIPE;
            last = 64'(d.limit) / STRIPE;

            if (d.valid) begin
                if (last - first >= 64'(2 * B)) hit = 1'b1;
                else for (int offset = 0; offset < 2 * B; offset++) begin
                    if (first + 64'(offset) < last &&
                        mapped_bank((first + 64'(offset)) * STRIPE) == bank) hit = 1'b1;
                end
            end

            return hit;
        endfunction

        // Baseline port classes: host=0, DMA=1, CGRA/MST=2 and higher.
        // TRANSFER selects its producer through the explicit descriptor masks.
        function automatic logic class_allowed(input logic [2:0] state, input int client);
            case (state)
                REGION_HOST_OWNED: return client == 0;
                REGION_DMA_OWNED: return client == 1;
                REGION_CGRA_OWNED: return client >= 2;
                REGION_SHARED_READ_ONLY: return 1'b1;
                REGION_TRANSFER: return 1'b1;
                default: return 1'b0;
            endcase
        endfunction

        function automatic logic [SI-1:0] next_slot(input logic [SI-1:0] slot);
            return slot == SI'(N - 1) ? {SI{1'b0}} : slot + 1'b1;
        endfunction

        assign o_client_req_ready = admission_ready;
        assign o_client_rsp_valid = response_valid;
        assign o_client_rsp_opcode = response_opcode;
        assign o_client_rsp_rdata = response_data;
        assign o_client_rsp_region_id = response_region;
        assign o_client_rsp_generation = response_generation;
        assign o_client_rsp_tag = response_tag;
        assign o_client_rsp_error = response_error;
        assign o_client_rsp_error_code = response_code;
        assign o_client_rsp_corrected = response_corrected;
        assign o_client_rsp_uncorrectable = response_uncorrectable;
        assign o_client_outstanding = client_outstanding;
        assign o_region_outstanding = region_outstanding;
        assign o_permission_denied = run ? denied : {C{1'b0}};
        assign o_region_cmd_ready = active && i_drain === 1'b0 &&
            manager.phase == MANAGER_IDLE && !(|power_busy) &&
            (!manager.event_valid || i_event_ready === 1'b1);
        assign o_region_rsp_valid = run && !cancel && !manager_bad &&
            manager.phase == MANAGER_RESPONSE;
        assign o_region_rsp_descriptor = manager.response;
        assign o_region_rsp_error = manager.code != 0;
        assign o_region_rsp_error_code = manager.code;
        assign o_region_transition_event = run && manager.transition_event;
        assign o_event_valid = run && !manager_bad && manager.event_valid;
        assign o_event_code = manager.event_code;
        assign o_event_region_a = manager.event_a;
        assign o_event_region_b = manager.event_b;
        assign o_event_generation_a = manager.event_ga;
        assign o_event_generation_b = manager.event_gb;
        assign o_event_kernel_id = manager.event_kernel;
        assign o_event_error_code = manager.event_error;
        assign o_idle = run && quiet && manager.phase == MANAGER_IDLE &&
            !manager.event_valid && !controller_flushing && !o_error;
        assign o_busy = run && !o_idle;
        assign o_drained = i_drain === 1'b1 && o_idle;
        assign o_flush_completed = run && controller_flush_done;
        assign o_error = run && (sticky != 0 || integrity_bad);
        assign o_error_code = integrity_bad ? BSP_ERR_CONTROL : sticky;

        // Coarse permissions are always derived from the same descriptor snapshot
        // used for precise checks. No request issues during atomic mask installation.
        always @* begin
            read_permission = '0;
            write_permission = '0;
            off_allowed = {B{1'b1}};

            for (int r = 0; r < R; r++) begin
                descriptor_t d;
                d = descriptors[r];

                for (int b = 0; b < B; b++) begin
                    if (touches(d, b)) begin
                        off_allowed[b] = 1'b0;

                        for (int c = 0; c < C; c++) begin
                            if (class_allowed(d.state, c)) begin
                                read_permission[c*B+b] |= ((d.read_mask >> c) & 1'b1) && d.contents;
                                write_permission[c*B+b] |= ((d.write_mask >> c) & 1'b1) &&
                                    d.state != REGION_SHARED_READ_ONLY;
                            end
                        end
                    end
                end
            end

            if (ENFORCE_REGIONS == 0) begin
                read_permission = {C*B{1'b1}};
                write_permission = {C*B{1'b1}};
            end
        end

        // Slot ownership includes completed but unconsumed responses. This is also
        // the region fence: descriptor mutation cannot race a stalled response.
        always @* begin
            region_outstanding = '0;
            client_outstanding = '0;
            any_outstanding = 1'b0;

            for (int c = 0; c < C; c++) begin
                client_t q;
                q = clients[c];
                client_outstanding[c*CO+:CO] = q.count;
                any_outstanding |= q.count != 0;

                for (int s = 0; s < N; s++) begin
                    slot_t x;
                    x = slots[c][s];

                    if (x.allocated && x.region_counted && int'(x.region_id) < R)
                        region_outstanding[x.region_id*RO+:RO] =
                            region_outstanding[x.region_id*RO+:RO] + 1'b1;
                end
            end
        end

        always @* begin
            admission_ready = '0;
            response_valid = '0;
            response_opcode = '0;
            response_data = '0;
            response_region = '0;
            response_generation = '0;
            response_tag = '0;
            response_error = '0;
            response_code = '0;
            response_corrected = '0;
            response_uncorrectable = '0;
            dispatch_valid = '0;
            dispatch_write = '0;
            dispatch_address = '0;
            dispatch_size = '0;
            dispatch_data = '0;
            dispatch_strobe = '0;
            dispatch_tag = '0;

            for (int c = 0; c < C; c++) begin
                client_t q;
                slot_t head;
                logic selected;
                logic earlier_complete;
                q = clients[c];
                head = '0;

                if (int'(q.head) < N) head = slots[c][q.head];

                selected = 1'b0;
                earlier_complete = 1'b1;
                dispatch_slot[c] = '0;
                admission_ready[c] = active && i_enable === 1'b1 && i_drain === 1'b0 &&
                    !manager_blocks && i_region_cmd_valid === 1'b0 && !(|power_busy) &&
                    i_bank_power_cmd_valid === {B{1'b0}} && !q.fence && q.count < N;

                if (run && !cancel && !client_bad[c] &&
                    !slot_bad[c*N+int'(q.head)] && q.count != 0 &&
                    head.allocated && head.complete) begin
                    response_valid[c] = 1'b1;
                    response_opcode[c*2+:2] = head.opcode;
                    response_data[c*D+:D] = head.data;
                    response_region[c*RI+:RI] = head.region_id;
                    response_generation[c*G+:G] = head.generation;
                    response_tag[c*T+:T] = head.tag;
                    response_code[c*8+:8] = head.code;
                    response_error[c] = head.code != 0;
                    response_corrected[c] = head.corrected;
                    response_uncorrectable[c] = head.uncorrectable;
                end

                // Walk acceptance order, skipping already dispatched obligations.
                // A fence completes when all preceding results exist, regardless
                // of their public consumption or unrelated client activity.
                for (int offset = 0; offset < N; offset++) begin
                    int s;
                    slot_t x;
                    s = (int'(q.head) + offset) % N;
                    x = slots[c][s];

                    if (offset < int'(q.count) && x.allocated) begin
                        if (!selected && !x.complete && !x.dispatched) begin
                            selected = 1'b1;

                            if (x.opcode != BSP_REQ_FENCE && active) begin
                                dispatch_valid[c] = 1'b1;
                                dispatch_slot[c] = SI'(s);
                                dispatch_write[c] = x.opcode == BSP_REQ_WRITE;
                                dispatch_address[c*A+:A] = x.address;

                                for (int exponent = 0; exponent <= $clog2(Y); exponent++)
                                    if (x.size == Z'(64'd1 << exponent))
                                        dispatch_size[c*LZ+:LZ] = LZ'(exponent);

                                dispatch_data[c*D+:D] = x.wdata;
                                dispatch_strobe[c*Y+:Y] = x.strobe >> (x.address % Y);
                                dispatch_tag[c*IT+:IT] = {CI'(c), SI'(s), x.epoch};
                            end
                        end

                        earlier_complete &= x.complete;
                    end
                end
            end
        end

        always @* begin
            denied = '0;
            new_error = BSP_ERR_NONE;

            for (int c = 0; c < C; c++) begin
                client_t q;
                client_t n;
                slot_t head;
                logic earlier_complete;
                q = clients[c];
                n = q;
                head = '0;

                if (int'(q.head) < N) head = slots[c][q.head];

                earlier_complete = 1'b1;

                if (q.count > N || int'(q.head) >= N || int'(q.tail) >= N)
                    new_error = BSP_ERR_CONTROL;

                for (int s = 0; s < N; s++) begin
                    slot_t aging;
                    aging = slots[c][s];

                    if (aging.allocated && !(&aging.age)) aging.age = aging.age + 1'b1;

                    slot_next[c][s] = aging;
                end

                for (int offset = 0; offset < N; offset++) begin
                    int s;
                    slot_t x;
                    s = (int'(q.head) + offset) % N;
                    x = slots[c][s];

                    if (offset < int'(q.count) && x.allocated) begin
                        if (!x.complete && x.opcode == BSP_REQ_FENCE &&
                            earlier_complete && active) begin
                            x.complete = 1'b1;
                            slot_next[c][s] = x;
                        end

                        earlier_complete &= x.complete;
                    end
                end

                if (dispatch_valid[c] && dispatch_ready[c]) begin
                    slot_t x;
                    x = slot_next[c][dispatch_slot[c]];
                    x.dispatched = 1'b1;
                    slot_next[c][dispatch_slot[c]] = x;
                end

                if (active && completion_valid[c]) begin
                    logic [IT-1:0] tag;
                    int s;
                    slot_t x;
                    tag = completion_tag[c*IT+:IT];
                    s = int'(tag[32+:SI]);
                    x = '0;

                    if (s < N) x = slot_next[c][s];

                    if (^tag === 1'bx || int'(tag[32+SI+:CI]) != c || s >= N ||
                        !x.allocated || !x.dispatched || x.complete ||
                        tag[31:0] != x.epoch ||
                        completion_write[c] !== (x.opcode == BSP_REQ_WRITE) ||
                        (^{completion_error[c], completion_code[c*4+:4],
                            completion_corrected[c], completion_uncorrectable[c]} === 1'bx))
                        new_error = BSP_ERR_COMPLETION;
                    else begin
                        x.complete = 1'b1;
                        x.data = completion_error[c] ? {D{1'b0}} : completion_data[c*D+:D];
                        x.code = {4'b0, completion_code[c*4+:4]};
                        x.corrected = completion_corrected[c];
                        x.uncorrectable = completion_uncorrectable[c];
                        slot_next[c][s] = x;
                    end
                end

                if (response_valid[c] && i_client_rsp_ready[c] === 1'b1) begin
                    slot_t x;
                    x = slots[c][q.head];
                    x.allocated = 1'b0;
                    slot_next[c][q.head] = x;
                    n.head = next_slot(q.head);
                    n.count = n.count - 1'b1;

                    if (head.opcode == BSP_REQ_FENCE) n.fence = 1'b0;
                end

                if (admission_ready[c] && i_client_req_valid[c] === 1'b1) begin
                    slot_t x;
                    slot_t old;
                    descriptor_t d;
                    logic [63:0] address;
                    logic [63:0] size;
                    logic [63:0] ending;
                    logic [Y-1:0] canonical;
                    logic [D-1:0] payload;
                    int match_count;
                    int bank;
                    x = '0;
                    old = slots[c][q.tail];
                    x.allocated = 1'b1;
                    x.epoch = old.epoch + 1'b1;
                    x.opcode = i_client_req_opcode[c*2+:2];
                    x.address = i_client_req_addr[c*A+:A];
                    x.size = i_client_req_size[c*Z+:Z];
                    x.wdata = i_client_req_wdata[c*D+:D];
                    x.strobe = i_client_req_wstrb[c*Y+:Y];
                    x.owner = i_client_req_owner_id[c*O+:O];
                    x.kernel = i_client_req_kernel_id[c*K+:K];
                    x.region_id = i_client_req_region_id[c*RI+:RI];
                    x.generation = i_client_req_generation[c*G+:G];
                    x.tag = i_client_req_tag[c*T+:T];
                    address = 64'(x.address);
                    size = 64'(x.size);
                    ending = address + size;
                    canonical = '0;
                    payload = '0;
                    bank = 0;
                    match_count = 0;
                    d = '0;

                    for (int r = 0; r < R; r++) begin
                        descriptor_t candidate;
                        candidate = descriptors[r];

                        if (candidate.valid && address >= 64'(candidate.base) &&
                            address < 64'(candidate.limit)) begin
                            match_count++;
                            d = candidate;

                            if (x.region_id == RI'(r)) x.region_counted = 1'b1;
                        end
                    end

                    if (old.allocated) new_error = BSP_ERR_COMPLETION;

                    if (&old.epoch) begin
                        x.code = BSP_MEM_PROTOCOL;
                        new_error = BSP_ERR_GENERATION;
                    end else if ((^{x.opcode, x.tag, x.region_id, x.generation} === 1'bx))
                        x.code = BSP_MEM_UNKNOWN;
                    else if (x.opcode > BSP_REQ_FENCE) x.code = BSP_MEM_OPCODE;
                    else if (x.opcode != BSP_REQ_FENCE) begin
                        if ((^{x.address, x.size, x.owner, x.kernel} === 1'bx) ||
                            (x.opcode == BSP_REQ_WRITE && ^x.strobe === 1'bx))
                            x.code = BSP_MEM_UNKNOWN;
                        else if (address >= CAPACITY || ending > CAPACITY)
                            x.code = BSP_MEM_RANGE;
                        else if (size == 0 || size > Y || (size & (size - 1)) != 0)
                            x.code = BSP_MEM_SIZE;
                        else if (address % Y + size > Y || address % STRIPE + size > STRIPE)
                            x.code = BSP_MEM_CROSSING;
                        else if (address % size != 0) x.code = BSP_MEM_ALIGNMENT;
                        else begin
                            for (int byte_index = 0; byte_index < Y; byte_index++)
                                canonical[byte_index] = 64'(byte_index) >= address % Y &&
                                    64'(byte_index) < address % Y + size;

                            bank = mapped_bank(address);
                            x.bank = BI'(bank);

                            if (x.opcode == BSP_REQ_WRITE && x.strobe != canonical)
                                x.code = BSP_MEM_STROBE;
                            else if (ENFORCE_REGIONS == 1) begin
                                if (match_count != 1 || !x.region_counted || ending > 64'(d.limit))
                                    x.code = BSP_MEM_REGION;
                                else if (x.generation != d.generation)
                                    x.code = BSP_MEM_GENERATION;
                                else if (d.state != REGION_SHARED_READ_ONLY &&
                                    (x.owner != d.owner || x.kernel != d.kernel))
                                    x.code = BSP_MEM_OWNER;
                                else if (!class_allowed(d.state, c) ||
                                    (x.opcode == BSP_REQ_READ && !((d.read_mask >> c) & 1'b1)) ||
                                    (x.opcode == BSP_REQ_WRITE && (!((d.write_mask >> c) & 1'b1) ||
                                        d.state == REGION_SHARED_READ_ONLY)))
                                    x.code = BSP_MEM_PERMISSION;
                                else if (x.opcode == BSP_REQ_READ && !d.contents)
                                    x.code = BSP_MEM_CONTENTS;
                            end

                            if (x.code == BSP_MEM_NONE &&
                                o_bank_power_state[bank*2+:2] != BANK_POWER_ACTIVE)
                                x.code = BSP_MEM_BANK_POWER;

                            if (x.code == BSP_MEM_NONE && x.opcode == BSP_REQ_READ &&
                                !o_bank_contents_valid[bank]) x.code = BSP_MEM_CONTENTS;
                        end
                    end

                    if (x.opcode == BSP_REQ_WRITE && x.code == 0) begin
                        payload = x.wdata;
                        for (int byte_index = 0; byte_index < Y; byte_index++)
                            if (64'(byte_index) >= size) payload[byte_index*8+:8] = '0;
                        if (^payload === 1'bx) x.code = BSP_MEM_UNKNOWN;
                        x.wdata = payload;
                    end
                    // Inactive payloads and rejected unknown controls never enter
                    // protected state as X; the classified response remains local.
                    if (x.opcode != BSP_REQ_WRITE || x.code != 0) begin
                        x.wdata = '0;
                        x.strobe = '0;
                    end
                    if (^x.address === 1'bx) x.address = '0;
                    if (^x.size === 1'bx) x.size = '0;
                    if (^x.owner === 1'bx) x.owner = '0;
                    if (^x.kernel === 1'bx) x.kernel = '0;
                    if (^x.opcode === 1'bx) x.opcode = '0;
                    if (^x.tag === 1'bx) x.tag = '0;
                    if (^x.region_id === 1'bx) x.region_id = '0;
                    if (^x.generation === 1'bx) x.generation = '0;
                    if (ENFORCE_REGIONS == 0 || x.opcode == BSP_REQ_FENCE)
                        x.region_counted = 1'b0;
                    if (x.code != 0) begin
                        x.complete = 1'b1;
                        if (x.code >= BSP_MEM_PERMISSION && x.code <= BSP_MEM_OWNER)
                            denied[c] = 1'b1;
                    end
                    if (x.opcode == BSP_REQ_FENCE) n.fence = 1'b1;
                    slot_next[c][q.tail] = x;
                    n.tail = next_slot(q.tail);
                    n.count = n.count + 1'b1;
                end

                if (run && cancel) begin
                    n = '0;

                    for (int s = 0; s < N; s++) begin
                        slot_t x;
                        x = slots[c][s];
                        x.allocated = 1'b0;
                        x.complete = 1'b0;
                        x.dispatched = 1'b0;
                        slot_next[c][s] = x;
                    end
                end
                client_next[c] = n;
            end

            if (controller_error) new_error = BSP_ERR_CONTROLLER;
            if (|bank_bad) new_error = BSP_ERR_BANK;
            if (|power_bad) new_error = BSP_ERR_POWER;
            if (integrity_bad) new_error = BSP_ERR_CONTROL;

            sticky_next = sticky;

            if (sticky == 0 && new_error != 0) sticky_next = new_error;
            else if (quiet && manager.phase == MANAGER_IDLE && i_error_clear === 1'b1 &&
                new_error == 0) sticky_next = '0;
        end

        // Management serializes mutations with a global drain because the reused
        // controller replaces its complete permission matrix only while idle.
        // An event has one lossless holding slot: backpressure delays commands.
        always @* begin
            descriptor_t a;
            descriptor_t b;
            descriptor_t next_a;
            descriptor_t next_b;
            logic [7:0] code;
            logic mutation;
            logic update_b;
            manager_next = manager;
            manager_next.transition_event = 1'b0;
            publish = '0;
            a = '0;
            b = '0;
            next_a = '0;
            next_b = '0;
            code = REGION_ERR_NONE;
            mutation = 1'b0;
            update_b = 1'b0;

            for (int r = 0; r < R; r++) descriptor_next[r] = descriptors[r];

            if (manager.event_valid && i_event_ready === 1'b1)
                manager_next.event_valid = 1'b0;

            // Storage fault summaries belong to the accepted descriptor epoch.
            for (int c = 0; c < C; c++) begin
                int s;
                slot_t x;
                descriptor_t d;
                s = int'(completion_tag[c*IT+32+:SI]);
                x = '0;

                if (s < N) x = slots[c][s];

                d = '0;

                if (int'(x.region_id) < R) d = descriptor_next[x.region_id];

                if (active && completion_valid[c] && x.allocated && x.region_counted &&
                    !x.complete && x.epoch == completion_tag[c*IT+:32] &&
                    int'(x.region_id) < R && d.valid && d.generation == x.generation) begin
                    d.corrected |= completion_corrected[c];
                    d.uncorrectable |= completion_uncorrectable[c];
                    descriptor_next[x.region_id] = d;
                end
            end

            if (manager.phase == MANAGER_RESPONSE && i_region_rsp_ready === 1'b1)
                manager_next.phase = MANAGER_IDLE;

            if (o_region_cmd_ready && i_region_cmd_valid === 1'b1) begin
                manager_next.phase = MANAGER_WAIT;
                manager_next.command = i_region_cmd_opcode;
                manager_next.a = i_region_cmd_a;
                manager_next.b = i_region_cmd_b;
                manager_next.expected_a = i_region_expected_generation_a;
                manager_next.expected_b = i_region_expected_generation_b;
                manager_next.state_a = i_region_expected_state_a;
                manager_next.state_b = i_region_expected_state_b;
                manager_next.proposed = '0;
                manager_next.proposed.valid = 1'b1;
                manager_next.proposed.base = i_region_base;
                manager_next.proposed.limit = i_region_limit;
                manager_next.proposed.owner = i_region_owner_id;
                manager_next.proposed.kernel = i_region_kernel_id;
                manager_next.proposed.state = i_region_state;
                manager_next.proposed.contents = i_region_contents_valid;
                manager_next.proposed.read_mask = i_region_read_mask;
                manager_next.proposed.write_mask = i_region_write_mask;
                manager_next.proposed.group_id = i_region_buffer_group;
                manager_next.proposed.role = i_region_buffer_role;
                manager_next.unknown_command = (^{i_region_cmd_opcode, i_region_cmd_a,
                    i_region_cmd_b, i_region_expected_generation_a,
                    i_region_expected_generation_b, i_region_expected_state_a,
                    i_region_expected_state_b, i_region_base, i_region_limit,
                    i_region_owner_id, i_region_kernel_id, i_region_state,
                    i_region_contents_valid, i_region_read_mask, i_region_write_mask,
                    i_region_buffer_group, i_region_buffer_role} === 1'bx);

                if (manager_next.unknown_command) begin
                    manager_next.command = 3'd7;
                    manager_next.a = '0;
                    manager_next.b = '0;
                    manager_next.expected_a = '0;
                    manager_next.expected_b = '0;
                    manager_next.state_a = '0;
                    manager_next.state_b = '0;
                    manager_next.proposed = '0;
                end
            end

            if (active && manager.phase == MANAGER_WAIT &&
                (manager.command == REGION_CMD_READ || quiet)) begin
                if (int'(manager.a) < R) a = descriptors[manager.a];
                if (int'(manager.b) < R) b = descriptors[manager.b];

                next_a = a;
                next_b = b;

                if (manager.unknown_command) code = REGION_ERR_UNKNOWN;
                else if (int'(manager.a) >= R) code = REGION_ERR_INDEX;
                else if (manager.command > REGION_CMD_INVALIDATE) code = REGION_ERR_OPCODE;
                else if (manager.command == REGION_CMD_PROVISION) begin
                    if (a.valid) code = REGION_ERR_VALID;
                    else if (manager.proposed.base >= manager.proposed.limit ||
                        64'(manager.proposed.limit) > CAPACITY ||
                        64'(manager.proposed.base) % STRIPE != 0 ||
                        64'(manager.proposed.limit) % STRIPE != 0) code = REGION_ERR_RANGE;
                    else begin
                        for (int r = 0; r < R; r++) begin
                            descriptor_t d;
                            d = descriptors[r];

                            if (d.valid && manager.proposed.base < d.limit &&
                                manager.proposed.limit > d.base) code = REGION_ERR_OVERLAP;
                        end

                        next_a = manager.proposed;

                        // Invalidating/reprovisioning is the explicit generation
                        // namespace restart; software discards stale schedules.
                        next_a.generation = (&a.generation) ? G'(1) : a.generation + 1'b1;
                    end
                end else if (manager.command != REGION_CMD_READ) begin
                    if (!a.valid) code = REGION_ERR_VALID;
                    else if (a.generation != manager.expected_a || a.state != manager.state_a)
                        code = REGION_ERR_COMPARE;
                    else if (manager.command != REGION_CMD_INVALIDATE && &a.generation)
                        code = REGION_ERR_GENERATION;
                    else if (manager.command == REGION_CMD_INVALIDATE) begin
                        next_a.valid = 1'b0;
                        next_a.contents = 1'b0;
                    end else if (manager.command == REGION_CMD_TRANSITION) begin
                        next_a.owner = manager.proposed.owner;
                        next_a.kernel = manager.proposed.kernel;
                        next_a.state = manager.proposed.state;
                        next_a.contents = manager.proposed.contents;
                        next_a.read_mask = manager.proposed.read_mask;
                        next_a.write_mask = manager.proposed.write_mask;
                        next_a.generation = a.generation + 1'b1;
                    end else if (manager.command == REGION_CMD_SWAP) begin
                        if (SUPPORT_DOUBLE_BUFFER != 1 || int'(manager.b) >= R ||
                            manager.a == manager.b || !b.valid || a.group_id == 0 ||
                            a.group_id != b.group_id || a.limit - a.base != b.limit - b.base ||
                            !((a.role == BUFFER_ROLE_ACTIVE && b.role == BUFFER_ROLE_STAGING) ||
                                (b.role == BUFFER_ROLE_ACTIVE && a.role == BUFFER_ROLE_STAGING)))
                            code = REGION_ERR_PAIR;
                        else if (b.generation != manager.expected_b || b.state != manager.state_b)
                            code = REGION_ERR_COMPARE;
                        else if (&b.generation) code = REGION_ERR_GENERATION;
                        else if ((a.role == BUFFER_ROLE_STAGING && !a.contents) ||
                            (b.role == BUFFER_ROLE_STAGING && !b.contents))
                            code = REGION_ERR_CONTENTS;
                        else begin
                            next_a = b;
                            next_a.base = a.base;
                            next_a.limit = a.limit;
                            next_a.group_id = a.group_id;
                            next_a.generation = a.generation + 1'b1;
                            next_a.corrected = a.corrected;
                            next_a.uncorrectable = a.uncorrectable;
                            next_b = a;
                            next_b.base = b.base;
                            next_b.limit = b.limit;
                            next_b.group_id = b.group_id;
                            next_b.generation = b.generation + 1'b1;
                            next_b.corrected = b.corrected;
                            next_b.uncorrectable = b.uncorrectable;
                            update_b = 1'b1;
                        end
                    end
                end

                if (code == 0 && manager.command != REGION_CMD_READ &&
                    manager.command != REGION_CMD_INVALIDATE) begin

                    if (next_a.state > REGION_TRANSFER || next_a.role > BUFFER_ROLE_STAGING ||
                        ((next_a.group_id == 0) != (next_a.role == BUFFER_ROLE_NONE)) ||
                        (SUPPORT_DOUBLE_BUFFER == 0 && next_a.role != BUFFER_ROLE_NONE))
                        code = REGION_ERR_STATE;

                    for (int bank = 0; bank < B; bank++) begin
                        if ((touches(next_a, bank) || (update_b && touches(next_b, bank))) &&
                            o_bank_power_state[bank*2+:2] != BANK_POWER_ACTIVE)
                            code = REGION_ERR_POWER;
                    end
                end

                mutation = code == 0 && manager.command != REGION_CMD_READ;
                manager_next.response = mutation ? next_a : a;
                manager_next.code = code;
                manager_next.phase = mutation && ENFORCE_BANK_PERMISSIONS == 1 ?
                    MANAGER_PERMISSIONS : MANAGER_RESPONSE;

                if (mutation) begin
                    descriptor_next[manager.a] = next_a;

                    if (update_b) descriptor_next[manager.b] = next_b;

                    manager_next.transition_event = manager.command == REGION_CMD_TRANSITION ||
                        manager.command == REGION_CMD_SWAP;

                    for (int bank = 0; bank < B; bank++) begin
                        if ((next_a.valid && next_a.contents && touches(next_a, bank)) ||
                            (update_b && next_b.contents && touches(next_b, bank)))
                            publish[bank] = 1'b1;
                    end
                end

                if (mutation || code != 0) begin
                    manager_next.event_valid = 1'b1;
                    manager_next.event_code = code != 0 ? BSP_EVENT_ERROR :
                        manager.command == REGION_CMD_SWAP ? BSP_EVENT_SWAPPED :
                        manager.command == REGION_CMD_INVALIDATE ? BSP_EVENT_INVALIDATED :
                        next_a.contents && next_a.role == BUFFER_ROLE_STAGING ? BSP_EVENT_FILLED :
                        !next_a.contents && a.contents ? BSP_EVENT_CONSUMED : BSP_EVENT_TRANSITION;
                    manager_next.event_a = manager.a;
                    manager_next.event_b = manager.b;
                    manager_next.event_ga = mutation ? next_a.generation : a.generation;
                    manager_next.event_gb = update_b && mutation ? next_b.generation : b.generation;
                    manager_next.event_kernel = mutation ? next_a.kernel : a.kernel;
                    manager_next.event_error = code;
                end
            end

            if (manager.phase == MANAGER_PERMISSIONS && permission_offer && permission_ready)
                manager_next.phase = MANAGER_RESPONSE;

            // Flush cancels only protocol work; committed descriptors and events
            // survive. A pending matrix install completes after coordinated flush.
            if (run && cancel && manager.phase != MANAGER_PERMISSIONS)
                manager_next.phase = MANAGER_IDLE;
        end

        banked_scratchpad_state #(
            .WIDTH($bits(manager_t)),
            .PROTECTION(CONTROL_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_manager (
            .i_clk(i_clk),
            .i_reset_n(i_reset_n),
            .i_data(manager_next),
            .o_data(manager),
            .o_bad(manager_bad)
        );

        banked_scratchpad_state #(
            .WIDTH(8),
            .PROTECTION(CONTROL_PROTECTION),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_error (
            .i_clk(i_clk),
            .i_reset_n(i_reset_n),
            .i_data(sticky_next),
            .o_data(sticky),
            .o_bad(sticky_bad)
        );

        for (genvar r = 0; r < R; r++) begin : g_region
            banked_scratchpad_state #(
                .WIDTH(DW),
                .PROTECTION(CONTROL_PROTECTION),
                .ASYNC_RESET(ASYNC_RESET)
            ) u_descriptor (
                .i_clk(i_clk),
                .i_reset_n(i_reset_n),
                .i_data(descriptor_next[r]),
                .o_data(descriptors[r]),
                .o_bad(descriptor_bad[r])
            );
        end

        for (genvar c = 0; c < C; c++) begin : g_client
            banked_scratchpad_state #(
                .WIDTH(CW),
                .PROTECTION(CONTROL_PROTECTION),
                .ASYNC_RESET(ASYNC_RESET)
            ) u_control (
                .i_clk(i_clk),
                .i_reset_n(i_reset_n),
                .i_data(client_next[c]),
                .o_data(clients[c]),
                .o_bad(client_bad[c])
            );

            for (genvar s = 0; s < N; s++) begin : g_slot
                banked_scratchpad_state #(
                    .WIDTH(SW),
                    .PROTECTION(CONTROL_PROTECTION),
                    .ASYNC_RESET(ASYNC_RESET)
                ) u_state (
                    .i_clk(i_clk),
                    .i_reset_n(i_reset_n),
                    .i_data(slot_next[c][s]),
                    .o_data(slots[c][s]),
                    .o_bad(slot_bad[c*N+s])
                );
            end
        end

        // These packed observation buses are integration/debug hooks. They are
        // real synthesizable lifetime counters, not verification-only monitors.
        localparam int CLIENT_COUNTERS = 18;
        localparam int BANK_COUNTERS = 16;
        localparam int REGION_COUNTERS = 6;
        localparam int GLOBAL_COUNTERS = 10;
        localparam int COUNTERS = C * CLIENT_COUNTERS + B * BANK_COUNTERS +
            R * REGION_COUNTERS + GLOBAL_COUNTERS;
        localparam int BANK_BASE = C * CLIENT_COUNTERS;
        localparam int REGION_BASE = BANK_BASE + B * BANK_COUNTERS;
        localparam int GLOBAL_BASE = REGION_BASE + R * REGION_COUNTERS;
        wire [COUNTERS*32-1:0] statistics;
        wire [(C+B+R)*32-1:0] outstanding_peaks;
        logic [COUNTERS*32-1:0] increments;
        logic [(C+B+R)*32-1:0] observed_occupancy;

        always @* begin
            increments = '0;
            observed_occupancy = '0;

            for (int c = 0; c < C; c++) begin
                client_t q;
                slot_t x;
                int base;
                int latency_bin;
                q = clients[c];
                x = '0;
                base = c * CLIENT_COUNTERS;
                latency_bin = 0;
                observed_occupancy[c*32+:32] = 32'(q.count);
                increments[(base+7)*32+:32] = 32'(dispatch_valid[c] && !dispatch_ready[c]);
                increments[(base+8)*32+:32] = 32'(i_client_req_valid[c] === 1'b1 && q.count == N);
                increments[(base+9)*32+:32] = 32'(response_valid[c] &&
                    i_client_rsp_ready[c] !== 1'b1);
                increments[(base+17)*32+:32] = 32'(q.fence);

                if (admission_ready[c] && i_client_req_valid[c] === 1'b1) begin
                    x = slot_next[c][q.tail];

                    if (x.opcode == BSP_REQ_READ || x.opcode == BSP_REQ_WRITE) begin
                        increments[(base+int'(x.opcode))*32+:32] = 1;
                        increments[(base+2+int'(x.opcode))*32+:32] = 32'(x.size);
                    end

                    increments[(base+5)*32+:32] = 32'(denied[c]);
                    increments[(base+6)*32+:32] = 32'(x.code == BSP_MEM_GENERATION);
                    increments[(base+16)*32+:32] = 32'(x.opcode == BSP_REQ_FENCE);

                    if (x.region_counted && x.opcode <= BSP_REQ_WRITE) begin
                        int rbase;
                        rbase = REGION_BASE + int'(x.region_id) * REGION_COUNTERS;
                        increments[(rbase+int'(x.opcode))*32+:32] =
                            increments[(rbase+int'(x.opcode))*32+:32] + 1'b1;
                        increments[(rbase+2)*32+:32] = increments[(rbase+2)*32+:32] + 32'(x.size);
                    end
                end

                if (response_valid[c] && i_client_rsp_ready[c] === 1'b1) begin
                    x = slots[c][q.head];
                    latency_bin = x.age < 8 ? 0 : x.age < 32 ? 1 : 2;

                    if (x.opcode <= BSP_REQ_WRITE)
                        increments[(base+10+3*int'(x.opcode)+latency_bin)*32+:32] = 1;
                end

                if (active && completion_valid[c]) begin
                    int slot;
                    slot = int'(completion_tag[c*IT+32+:SI]);
                    x = '0;

                    if (slot < N) x = slots[c][slot];

                    if (x.allocated && x.epoch == completion_tag[c*IT+:32]) begin
                        if (x.opcode == BSP_REQ_WRITE && !completion_error[c]) begin
                            increments[(base+4)*32+:32] = 32'(x.size);
                            increments[(BANK_BASE+int'(x.bank)*BANK_COUNTERS+3)*32+:32] =
                                increments[(BANK_BASE+int'(x.bank)*BANK_COUNTERS+3)*32+:32] +
                                32'(x.size);

                            if (x.region_counted) begin
                                int rbase;
                                rbase = REGION_BASE + int'(x.region_id) * REGION_COUNTERS;
                                increments[(rbase+3)*32+:32] = increments[(rbase+3)*32+:32] +
                                    32'(x.size);
                            end
                        end

                        if (x.region_counted) begin
                            int rbase;
                            rbase = REGION_BASE + int'(x.region_id) * REGION_COUNTERS;
                            increments[(rbase+4)*32+:32] = increments[(rbase+4)*32+:32] +
                                32'(completion_corrected[c]);
                            increments[(rbase+5)*32+:32] = increments[(rbase+5)*32+:32] +
                                32'(completion_uncorrectable[c]);
                        end
                    end
                end
            end

            for (int b = 0; b < B; b++) begin
                int base;
                logic accepted;
                base = BANK_BASE + b * BANK_COUNTERS;
                accepted = bank_req_valid[b] && bank_req_ready[b];
                observed_occupancy[(C+b)*32+:32] = 32'(o_bank_outstanding[b*BO+:BO]);
                increments[(base+0)*32+:32] = 32'(accepted && !bank_req_write[b]);
                increments[(base+1)*32+:32] = 32'(accepted && bank_req_write[b]);

                if (accepted) increments[(base+2)*32+:32] = 32'd1 << bank_req_size[b*LZ+:LZ];

                increments[(base+4)*32+:32] = 32'(o_bank_conflict[b]);
                increments[(base+5)*32+:32] = 32'(o_corrected_event[b]);
                increments[(base+6)*32+:32] = 32'(o_uncorrectable_event[b]);
                increments[(base+7)*32+:32] = 32'(o_bank_clock_enable[b]);
                increments[(base+8)*32+:32] = 32'(o_bank_clock_enable[b] && bank_idle[b]);
                increments[(base+9)*32+:32] =
                    32'(o_bank_power_state[b*2+:2] == BANK_POWER_CLOCK_GATED);
                increments[(base+10)*32+:32] =
                    32'(o_bank_power_state[b*2+:2] == BANK_POWER_RETENTION);
                increments[(base+11)*32+:32] = 32'(o_bank_power_state[b*2+:2] == BANK_POWER_OFF);
                increments[(base+12)*32+:32] = 32'(o_bank_power_cmd_ready[b] &&
                    i_bank_power_cmd_valid[b] === 1'b1 &&
                    i_bank_power_state[b*2+:2] == BANK_POWER_ACTIVE &&
                    o_bank_power_state[b*2+:2] != BANK_POWER_ACTIVE);
                increments[(base+13)*32+:32] = 32'(power_busy[b] &&
                    o_bank_power_state[b*2+:2] != BANK_POWER_ACTIVE);
                increments[(base+14)*32+:32] = 32'(bank_req_valid[b] && !bank_req_ready[b]);
                increments[(base+15)*32+:32] = 32'(bank_rsp_valid[b] && !bank_rsp_ready[b]);
            end

            for (int r = 0; r < R; r++)
                observed_occupancy[(C+B+r)*32+:32] = 32'(region_outstanding[r*RO+:RO]);

            increments[(GLOBAL_BASE+0)*32+:32] = 32'(i_drain === 1'b1);
            increments[(GLOBAL_BASE+1)*32+:32] = 32'(cancel);
            increments[(GLOBAL_BASE+2)*32+:32] = 32'(controller_flush_done);
            increments[(GLOBAL_BASE+3)*32+:32] = 32'(manager.phase == MANAGER_WAIT &&
                manager.command == REGION_CMD_TRANSITION);
            increments[(GLOBAL_BASE+4)*32+:32] = 32'(manager.phase == MANAGER_WAIT &&
                manager.command == REGION_CMD_SWAP);
            increments[(GLOBAL_BASE+5)*32+:32] = 32'(o_region_cmd_ready &&
                i_region_cmd_valid === 1'b1);
            increments[(GLOBAL_BASE+6)*32+:32] = 32'(o_event_valid && i_event_ready === 1'b1);
            increments[(GLOBAL_BASE+7)*32+:32] = 1;
            increments[(GLOBAL_BASE+8)*32+:32] = 32'(|(bank_req_valid & bank_req_ready));
            increments[(GLOBAL_BASE+9)*32+:32] = 32'(|(i_client_req_valid & ~admission_ready));
        end

        banked_scratchpad_counters #(
            .COUNT(COUNTERS),
            .PEAKS(C + B + R),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_statistics (
            .i_clk(i_clk),
            .i_reset_n(i_reset_n),
            .i_increments(increments),
            .i_occupancy(observed_occupancy),
            .o_counts(statistics),
            .o_peaks(outstanding_peaks)
        );

        scratchpad_controller #(
            .DATA_WIDTH(D),
            .NUM_BANKS(B),
            .BANK_DEPTH_WORDS(WORDS),
            .NUM_CLIENTS(C),
            .CLIENT_TAG_WIDTH(IT),
            .MAX_OUTSTANDING_PER_CLIENT(N),
            .INTERLEAVE_BYTES(STRIPE),
            .MAP_MODE(MAP_MODE),
            .ENFORCE_PERMISSIONS(ENFORCE_BANK_PERMISSIONS),
            .DEFAULT_ALLOW(ENFORCE_REGIONS == 0 ? 1 : DEFAULT_ALLOW),
            .ASYNC_RESET(ASYNC_RESET)
        ) u_controller (
            .i_clk(i_clk),
            .i_rstb(i_reset_n),
            .i_flush(i_flush),
            .i_error_clear(i_error_clear),
            .i_perm_valid(permission_offer),
            .o_perm_ready(permission_ready),
            .i_read_permission(read_permission),
            .i_write_permission(write_permission),
            .o_permission_updated(permission_updated),
            .i_client_req_valid(dispatch_valid),
            .i_client_req_write(dispatch_write),
            .i_client_req_address(dispatch_address),
            .i_client_req_size_log2(dispatch_size),
            .i_client_req_wdata(dispatch_data),
            .i_client_req_wstrobe(dispatch_strobe),
            .i_client_req_tag(dispatch_tag),
            .o_client_req_ready(dispatch_ready),
            .i_client_rsp_ready({C{active}}),
            .o_client_rsp_valid(completion_valid),
            .o_client_rsp_write(completion_write),
            .o_client_rsp_rdata(completion_data),
            .o_client_rsp_tag(completion_tag),
            .o_client_rsp_error(completion_error),
            .o_client_rsp_error_code(completion_code),
            .o_client_rsp_corrected(completion_corrected),
            .o_client_rsp_uncorrectable(completion_uncorrectable),
            .o_idle(controller_idle),
            .o_busy(),
            .o_flushing(controller_flushing),
            .o_flush_completed(controller_flush_done),
            .o_client_outstanding(),
            .o_bank_conflict(o_bank_conflict),
            .o_request_accepted(),
            .o_response_accepted(),
            .o_permission_denied(),
            .o_error(controller_error),
            .o_error_code(controller_error_code),
            .o_bank_req_valid(bank_req_valid),
            .o_bank_req_write(bank_req_write),
            .o_bank_req_address(bank_req_address),
            .o_bank_req_size_log2(bank_req_size),
            .o_bank_req_wdata(bank_req_data),
            .o_bank_req_wstrobe(bank_req_strobe),
            .o_bank_req_tag(bank_req_tag),
            .i_bank_req_ready(bank_req_ready),
            .i_bank_rsp_valid(bank_rsp_valid),
            .i_bank_rsp_write(bank_rsp_write),
            .i_bank_rsp_rdata(bank_rsp_data),
            .i_bank_rsp_tag(bank_rsp_tag),
            .i_bank_rsp_error(bank_rsp_error),
            .i_bank_rsp_error_code(bank_rsp_code),
            .i_bank_rsp_corrected(bank_rsp_corrected),
            .i_bank_rsp_uncorrectable(bank_rsp_uncorrectable),
            .o_bank_rsp_ready(bank_rsp_ready),
            .o_bank_flush(bank_flush),
            .i_bank_flush_completed(bank_flush_done),
            .i_bank_idle(bank_idle)
        );

        for (genvar b = 0; b < B; b++) begin : g_bank
            banked_scratchpad_power #(.SUPPORT_GATING(SUPPORT_BANK_POWER_GATING),
                .SUPPORT_RETENTION(SUPPORT_BANK_RETENTION),
                .CONTROL_PROTECTION(CONTROL_PROTECTION),
                .ASYNC_RESET(ASYNC_RESET)
            ) u_power (
                .i_clk(i_clk),
                .i_reset_n(i_reset_n),
                .i_quiescent(power_quiet),
                .i_off_allowed(off_allowed[b]),
                .i_publish(publish[b]),
                .i_cmd_valid(i_bank_power_cmd_valid[b]),
                .i_target(i_bank_power_state[b*2+:2]),
                .i_ack(i_bank_power_ack[b]),
                .o_cmd_ready(o_bank_power_cmd_ready[b]),
                .o_state(o_bank_power_state[b*2+:2]),
                .o_clock_enable(o_bank_clock_enable[b]),
                .o_isolate(o_bank_isolate[b]),
                .o_save(o_bank_retention_save[b]),
                .o_restore(o_bank_retention_restore[b]),
                .o_power_enable(o_bank_power_enable[b]),
                .o_contents_valid(o_bank_contents_valid[b]),
                .o_busy(power_busy[b]),
                .o_bad(power_bad[b])
            );

            wire physical_ready;
            assign bank_req_ready[b] = physical_ready && o_bank_clock_enable[b] &&
                !o_bank_isolate[b];
            assign o_bank_grant[b*CI+:CI] = bank_req_valid[b] && bank_req_ready[b] ?
                bank_req_tag[b*BT+SI+:CI] : {CI{1'b0}};

            scratchpad_bank #(
                .DATA_WIDTH(D),
                .DEPTH_WORDS(WORDS),
                .TAG_WIDTH(BT),
                .MAX_OUTSTANDING(BN),
                .BACKEND_READ_LATENCY(BACKEND_READ_LATENCY),
                .PROTECTION_MODE(PROTECTION_MODE),
                .PARITY_GRANULARITY(PARITY_GRANULARITY),
                .SCRUB_ON_CORRECT(SCRUB_ON_CORRECT),
                .ASYNC_RESET(ASYNC_RESET)
            ) u_bank (
                .i_clk(i_clk),
                .i_rstb(i_reset_n),
                .i_flush(bank_flush[b]),
                .i_error_clear(i_error_clear),
                .i_req_valid(bank_req_valid[b] && o_bank_clock_enable[b] && !o_bank_isolate[b]),
                .o_req_ready(physical_ready),
                .i_req_write(bank_req_write[b]),
                .i_req_address(bank_req_address[b*BA+:BA]),
                .i_req_size_log2(bank_req_size[b*LZ+:LZ]),
                .i_req_wdata(bank_req_data[b*D+:D]),
                .i_req_wstrobe(bank_req_strobe[b*Y+:Y]),
                .i_req_tag(bank_req_tag[b*BT+:BT]),
                .o_rsp_valid(bank_rsp_valid[b]),
                .i_rsp_ready(bank_rsp_ready[b]),
                .o_rsp_write(bank_rsp_write[b]),
                .o_rsp_rdata(bank_rsp_data[b*D+:D]),
                .o_rsp_tag(bank_rsp_tag[b*BT+:BT]),
                .o_rsp_error(bank_rsp_error[b]),
                .o_rsp_error_code(bank_rsp_code[b*4+:4]),
                .o_rsp_corrected(bank_rsp_corrected[b]),
                .o_rsp_uncorrectable(bank_rsp_uncorrectable[b]),
                .o_idle(bank_idle[b]),
                .o_busy(),
                .o_outstanding(o_bank_outstanding[b*BO+:BO]),
                .o_request_accepted(),
                .o_read_accepted(),
                .o_write_accepted(),
                .o_response_accepted(),
                .o_corrected_event(o_corrected_event[b]),
                .o_uncorrectable_event(o_uncorrectable_event[b]),
                .o_scrub_completed(),
                .o_flush_completed(bank_flush_done[b]),
                .o_error(bank_bad[b]),
                .o_error_code()
            );
        end
    end
endmodule
`default_nettype wire
