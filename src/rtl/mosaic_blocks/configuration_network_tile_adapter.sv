`timescale 1ns / 1ps
`default_nettype none
// Synchronous adapter for the released tile_shell configuration interface.
// QUERY checks the real version before writes/validation. PREPARE owns a
// network-level record and never sends native CFG_ACTIVATE.
module configuration_network_tile_adapter #(
    parameter CONFIG_DATA_WIDTH = 64,
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
    parameter CONTEXT_DEPTH = 4,
    parameter CONFIG_WORD_COUNT = 8,
    parameter SHELL_TAG_WIDTH = 8,
    parameter TILE_ID_WIDTH = 16,
    parameter TILE_ID = 0,
    parameter CONTROL_PROTECTION = 1,
    parameter ASYNC_RESET = 0,
    localparam int D = ((CONFIG_DATA_WIDTH >= 8 && CONFIG_DATA_WIDTH <= 256) === 1'b1)
        ? CONFIG_DATA_WIDTH : 8,
    localparam int C = ((COMMAND_WIDTH >= 4 && COMMAND_WIDTH <= 8) === 1'b1) ? COMMAND_WIDTH : 4,
    localparam int CI = ((CONTEXT_ID_WIDTH >= 1 && CONTEXT_ID_WIDTH <= 16) === 1'b1)
        ? CONTEXT_ID_WIDTH : 1,
    localparam int V = ((CONTEXT_VERSION_WIDTH >= 1 && CONTEXT_VERSION_WIDTH <= 32) === 1'b1)
        ? CONTEXT_VERSION_WIDTH : 1,
    localparam int OW = ((OWNER_ID_WIDTH >= 1 && OWNER_ID_WIDTH <= 32) === 1'b1)
        ? OWNER_ID_WIDTH : 1,
    localparam int K = ((KERNEL_ID_WIDTH >= 1 && KERNEL_ID_WIDTH <= 32) === 1'b1)
        ? KERNEL_ID_WIDTH : 1,
    localparam int P = ((PACKAGE_ID_WIDTH >= 1 && PACKAGE_ID_WIDTH <= 64) === 1'b1)
        ? PACKAGE_ID_WIDTH : 1,
    localparam int EP = ((CONFIG_EPOCH_WIDTH >= 1 && CONFIG_EPOCH_WIDTH <= 16) === 1'b1)
        ? CONFIG_EPOCH_WIDTH : 1,
    localparam int TI = ((TRANSACTION_ID_WIDTH >= 1 && TRANSACTION_ID_WIDTH <= 16) === 1'b1)
        ? TRANSACTION_ID_WIDTH : 1,
    localparam int TG = ((TAG_WIDTH >= 1 && TAG_WIDTH <= 32) === 1'b1) ? TAG_WIDTH : 1,
    localparam int WI = ((WORD_INDEX_WIDTH >= 1 && WORD_INDEX_WIDTH <= 32) === 1'b1)
        ? WORD_INDEX_WIDTH : 1,
    localparam int CTX = ((CONTEXT_DEPTH >= 1 && CONTEXT_DEPTH <= 256) === 1'b1)
        ? CONTEXT_DEPTH : 1,
    localparam int WORDS = ((CONFIG_WORD_COUNT >= 1 && CONFIG_WORD_COUNT <= 256) === 1'b1)
        ? CONFIG_WORD_COUNT : 1,
    localparam int ST = ((SHELL_TAG_WIDTH >= 1 && SHELL_TAG_WIDTH <= 32) === 1'b1)
        ? SHELL_TAG_WIDTH : 1,
    localparam int ID = ((TILE_ID_WIDTH >= 1 && TILE_ID_WIDTH <= 32) === 1'b1) ? TILE_ID_WIDTH : 1,
    localparam int BY = D / 8,
    localparam int SC = CTX > 1 ? $clog2(CTX) : 1,
    localparam int SW = WORDS > 1 ? $clog2(WORDS) : 1
) (
    input wire i_clk,
    input wire i_reset_n,
    input wire i_cancel,
    input wire i_request_valid,
    input wire i_response_ready,
    input wire i_commit_valid,
    input wire i_commit_ack_ready,
    input wire i_power_safe,
    input wire i_quiescent,
    input wire i_shell_active_valid,
    input wire i_shell_request_ready,
    input wire i_shell_response_valid,
    input wire i_shell_response_error,
    output wire o_cancel_ack,
    output wire o_request_ready,
    output wire o_response_valid,
    output wire o_prepared_retained,
    output wire o_commit_ready,
    output wire o_commit_ack_valid,
    output wire o_commit_error,
    output wire o_shell_request_valid,
    output wire o_shell_response_ready,
    output wire o_error,
    input wire [C-1:0] i_request_command,
    input wire [TI-1:0] i_request_transaction_id,
    input wire [31:0] i_request_sequence_id,
    input wire [TG-1:0] i_request_tag,
    input wire [OW-1:0] i_request_owner_id,
    input wire [K-1:0] i_request_kernel_id,
    input wire [P-1:0] i_request_package_id,
    input wire [EP-1:0] i_request_epoch,
    input wire [CI-1:0] i_request_context_id,
    input wire [V-1:0] i_request_expected_version,
    input wire [WI-1:0] i_request_word_index,
    input wire [D-1:0] i_request_write_data,
    input wire [BY-1:0] i_request_write_strobe,
    input wire [31:0] i_request_expected_crc,
    output wire [TI-1:0] o_response_transaction_id,
    output wire [31:0] o_response_sequence_id,
    output wire [EP-1:0] o_response_epoch,
    output wire [3:0] o_response_status,
    output wire [7:0] o_response_error_code,
    output wire [D-1:0] o_response_read_data,
    output wire [V-1:0] o_response_context_version,
    output wire [31:0] o_response_image_crc,
    output wire o_response_prepared,
    input wire [CI-1:0] i_commit_context_id,
    output wire [CI-1:0] o_active_context_id,
    input wire [V-1:0] i_commit_context_version,
    output wire [V-1:0] o_active_context_version,
    input wire [P-1:0] i_commit_package_id,
    output wire [P-1:0] o_active_package_id,
    input wire [OW-1:0] i_commit_owner_id,
    output wire [OW-1:0] o_active_owner_id,
    input wire [K-1:0] i_commit_kernel_id,
    output wire [K-1:0] o_active_kernel_id,
    input wire [EP-1:0] i_commit_epoch,
    output wire [EP-1:0] o_active_epoch,
    input wire [31:0] i_commit_image_crc,
    output wire [31:0] o_active_image_crc,
    output wire [2:0] o_shell_request_command,
    output wire [ID-1:0] o_shell_request_tile_id,
    output wire [OW-1:0] o_shell_request_owner_id,
    output wire [SC-1:0] o_shell_request_context_id,
    output wire [SW-1:0] o_shell_request_word_index,
    output wire [D-1:0] o_shell_request_write_data,
    output wire [BY-1:0] o_shell_request_write_strobe,
    output wire [31:0] o_shell_request_expected_crc,
    output wire [ST-1:0] o_shell_request_tag,
    input wire [2:0] i_shell_response_command,
    input wire [SC-1:0] i_shell_response_context_id,
    input wire [D-1:0] i_shell_response_read_data,
    input wire [V-1:0] i_shell_response_context_version,
    input wire [31:0] i_shell_response_crc,
    input wire [7:0] i_shell_response_error_code,
    input wire [ST-1:0] i_shell_response_tag,
    input wire [SC-1:0] i_shell_context_id,
    input wire [V-1:0] i_shell_context_version,
    input wire [OW-1:0] i_shell_owner_id,
    input wire [K-1:0] i_shell_kernel_id,
    input wire [CTX-1:0] i_shell_validated
);
    import configuration_network_pkg::*;
    localparam bit PARAMETERS_VALID =
        ((CONFIG_DATA_WIDTH >= 8 && CONFIG_DATA_WIDTH <= 256) === 1'b1) &&
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
        ((CONTEXT_DEPTH >= 1 && CONTEXT_DEPTH <= 256) === 1'b1) &&
        ((CONFIG_WORD_COUNT >= 1 && CONFIG_WORD_COUNT <= 256) === 1'b1) &&
        ((SHELL_TAG_WIDTH >= 1 && SHELL_TAG_WIDTH <= 32) === 1'b1) &&
        ((TILE_ID_WIDTH >= 1 && TILE_ID_WIDTH <= 32) === 1'b1) &&
        ((TILE_ID >= 0 && 64'(TILE_ID) < (64'd1 << ID)) === 1'b1) &&
        CONFIG_DATA_WIDTH % 8 == 0 &&
        (64'd1 << CI) >= CTX &&
        (64'd1 << WI) >= WORDS &&
        (CONTROL_PROTECTION === 0 || CONTROL_PROTECTION === 1 || CONTROL_PROTECTION === 2) &&
        (ASYNC_RESET === 0 || ASYNC_RESET === 1);
    if (!PARAMETERS_VALID) begin : g_invalid_parameters
        configuration_network_tile_adapter_parameters_must_be_valid invalid_parameters ();
    end
    // These width-dependent records are local to this parameterized adapter.
    typedef struct packed {
        logic [C-1:0] command;
        logic [TI-1:0] transaction;
        logic [31:0] sequence_id;
        logic [TG-1:0] tag;
        logic [OW-1:0] owner;
        logic [K-1:0] kernel;
        logic [P-1:0] package_id;
        logic [EP-1:0] epoch;
        logic [CI-1:0] context_id;
        logic [V-1:0] version;
        logic [WI-1:0] word_index;
        logic [D-1:0] data;
        logic [BY-1:0] strobe;
        logic [31:0] crc;
    } request_t;
    typedef struct packed {
        logic bound;
        logic loading;
        logic dirty;
        logic [P-1:0] package_id;
        logic [OW-1:0] owner;
        logic [K-1:0] kernel;
        logic [WORDS*BY-1:0] rewritten;
    } directory_t;
    localparam int DIRECTORY = $bits(directory_t);
    typedef struct packed {
        adapter_phase_t phase;
        request_t request;
        logic response;
        logic [3:0] status;
        logic [7:0] error_code;
        logic [D-1:0] data;
        logic [V-1:0] version;
        logic [31:0] crc;
        logic [ST-1:0] token;
        logic [ST-1:0] next_token;
        logic [CTX*DIRECTORY-1:0] directory;
        logic prepared;
        logic [CI-1:0] prepared_context;
        logic [V-1:0] prepared_version;
        logic [P-1:0] prepared_package;
        logic [OW-1:0] prepared_owner;
        logic [K-1:0] prepared_kernel;
        logic [31:0] prepared_crc;
        logic ack;
        logic commit_error;
        logic [EP-1:0] epoch;
        logic [CI-1:0] active_context;
        logic [V-1:0] active_version;
        logic [P-1:0] active_package;
        logic [OW-1:0] active_owner;
        logic [K-1:0] active_kernel;
        logic [31:0] active_crc;
        logic poison;
        logic cancel_seen;
    } state_t;
    state_t q;
    state_t n;
    request_t incoming;
    wire [$bits(state_t)-1:0] raw_state;
    wire state_bad;
    wire fatal;
    wire run = i_reset_n === 1'b1 &&!state_bad &&!fatal;
    wire [CTX*DIRECTORY-1:0] directory = q.directory;
    logic [CTX*DIRECTORY-1:0] next_directory;
    wire [CI-1:0] context_id = q.request.context_id;
    wire [WORDS*BY-1:0] all_bytes = '1;
    wire [BY-1:0] byte_strobe = q.request.strobe;
    wire waiting = q.phase == ADAPTER_QUERY_WAIT || q.phase == ADAPTER_NATIVE_WAIT ||
        q.phase == ADAPTER_COMMIT_WAIT;
    wire request_fire = i_request_valid === 1'b1 && o_request_ready;
    wire native_fire = o_shell_request_valid && i_shell_request_ready === 1'b1;
    wire native_result = i_shell_response_valid === 1'b1 && o_shell_response_ready;
    wire [2:0] native_command = q.phase == ADAPTER_QUERY_SEND ? 3'd5 :
        q.phase == ADAPTER_NATIVE_SEND ? (q.request.command == C'(CFG_WRITE) ? 3'd0 :
            q.request.command == C'(CFG_READ) ? 3'd1 :
            q.request.command == C'(CFG_VALIDATE) ? 3'd2 :
            q.request.command == C'(CFG_INVALIDATE) ? 3'd4 : 3'd5) : 3'd3;
    wire current_active = i_shell_active_valid === 1'b1 && CI'(i_shell_context_id) == context_id;
    wire known_response = (^{i_shell_response_command, i_shell_response_context_id,
        i_shell_response_read_data, i_shell_response_context_version, i_shell_response_crc,
        i_shell_response_error, i_shell_response_error_code, i_shell_response_tag} !== 1'bx);
    wire response_matches = known_response && i_shell_response_context_id == SC'(context_id) &&
        i_shell_response_tag == q.token && i_shell_response_command ==
            (q.phase == ADAPTER_QUERY_WAIT ? 3'd5 :
                q.phase == ADAPTER_COMMIT_WAIT ? 3'd3 :
                    q.request.command == C'(CFG_WRITE) ? 3'd0 :
                    q.request.command == C'(CFG_READ) ? 3'd1 :
                    q.request.command == C'(CFG_VALIDATE) ? 3'd2 :
                    q.request.command == C'(CFG_INVALIDATE) ? 3'd4 : 3'd5);
    wire commit_identity = (^{i_commit_context_id, i_commit_context_version,
        i_commit_package_id, i_commit_owner_id, i_commit_kernel_id, i_commit_epoch,
        i_commit_image_crc} !== 1'bx) && i_commit_context_id == q.prepared_context &&
        i_commit_context_version == q.prepared_version &&
        i_commit_package_id == q.prepared_package && i_commit_owner_id == q.prepared_owner &&
        i_commit_kernel_id == q.prepared_kernel && i_commit_image_crc == q.prepared_crc;
    always @* q = raw_state;
    always @* begin
        incoming.command = i_request_command;
        incoming.transaction = i_request_transaction_id;
        incoming.sequence_id = i_request_sequence_id;
        incoming.tag = i_request_tag;
        incoming.owner = i_request_owner_id;
        incoming.kernel = i_request_kernel_id;
        incoming.package_id = i_request_package_id;
        incoming.epoch = i_request_epoch;
        incoming.context_id = i_request_context_id;
        incoming.version = i_request_expected_version;
        incoming.word_index = i_request_word_index;
        incoming.data = i_request_write_data;
        incoming.strobe = i_request_write_strobe;
        incoming.crc = i_request_expected_crc;
    end
    assign o_request_ready = run &&!q.poison && i_cancel === 1'b0 &&
        i_commit_valid === 1'b0 && q.phase == ADAPTER_IDLE &&!q.response &&!q.ack &&
        (^incoming !== 1'bx);
    assign o_response_valid = run && i_cancel === 1'b0 && q.response;
    assign o_response_transaction_id = o_response_valid ? q.request.transaction : '0;
    assign o_response_sequence_id = o_response_valid ? q.request.sequence_id : '0;
    assign o_response_epoch = o_response_valid ? q.request.epoch : '0;
    assign o_response_status = o_response_valid ? q.status : '0;
    assign o_response_error_code = o_response_valid ? q.error_code : '0;
    assign o_response_read_data = o_response_valid ? q.data : '0;
    assign o_response_context_version = o_response_valid ? q.version : '0;
    assign o_response_image_crc = o_response_valid ? q.crc : '0;
    assign o_response_prepared = o_response_valid && q.prepared;
    assign o_prepared_retained = run &&!q.poison && q.prepared &&
        i_power_safe === 1'b1 && i_shell_validated[int'(q.prepared_context)] === 1'b1 &&
        i_shell_owner_id === q.prepared_owner && i_shell_kernel_id === q.prepared_kernel
            && i_cancel === 1'b0;
    // Ready is independent of commit payload: the fabric may clamp inactive
    // commit buses. Metadata is checked on the actual accepted commit pulse.
    assign o_commit_ready = o_prepared_retained &&
        q.phase == ADAPTER_IDLE &&!q.response &&!q.ack && i_power_safe === 1'b1 &&
        i_quiescent === 1'b1 && i_shell_request_ready === 1'b1;
    assign o_commit_ack_valid = run && q.ack;
    assign o_commit_error = o_commit_ack_valid && q.commit_error;
    assign o_cancel_ack = run && i_cancel === 1'b1 &&!waiting &&!q.response &&!q.ack &&!q.poison &&
        i_quiescent === 1'b1 && i_shell_response_valid === 1'b0;
    assign o_error = state_bad || fatal || q.poison;
    assign o_shell_request_valid = run &&!q.poison && i_cancel === 1'b0 &&
        i_power_safe === 1'b1 && ((q.phase == ADAPTER_QUERY_SEND ||
            q.phase == ADAPTER_NATIVE_SEND) ||
            (i_commit_valid === 1'b1 && o_commit_ready && commit_identity));
    assign o_shell_request_command = o_shell_request_valid ? native_command : '0;
    assign o_shell_request_tile_id = o_shell_request_valid ? ID'(TILE_ID) : '0;
    assign o_shell_request_owner_id = o_shell_request_valid ?
        (i_commit_valid === 1'b1 && o_commit_ready ? q.prepared_owner : q.request.owner) : '0;
    assign o_shell_request_context_id = o_shell_request_valid ?
        (i_commit_valid === 1'b1 && o_commit_ready ? SC'(q.prepared_context)
            : SC'(context_id)) : '0;
    assign o_shell_request_word_index = o_shell_request_valid &&
        (native_command == 0 || native_command == 1) ? SW'(q.request.word_index) : '0;
    assign o_shell_request_write_data = o_shell_request_valid && native_command == 0 ?
        q.request.data : '0;
    assign o_shell_request_write_strobe = o_shell_request_valid && native_command == 0 ?
        q.request.strobe : '0;
    assign o_shell_request_expected_crc = o_shell_request_valid && native_command == 2 ?
        q.request.crc : '0;
    assign o_shell_request_tag = o_shell_request_valid ? q.next_token : '0;
    assign o_shell_response_ready = run && (waiting || i_cancel === 1'b1);
    assign o_active_context_id = run && q.ack ? q.active_context : '0;
    assign o_active_context_version = run && q.ack ? q.active_version : '0;
    assign o_active_package_id = run && q.ack ? q.active_package : '0;
    assign o_active_owner_id = run && q.ack ? q.active_owner : '0;
    assign o_active_kernel_id = run && q.ack ? q.active_kernel : '0;
    assign o_active_epoch = run && q.ack ? q.epoch : '0;
    assign o_active_image_crc = run && q.ack ? q.active_crc : '0;
    always @* begin
        directory_t record;
        logic [WORDS*BY-1:0] rewritten;
        int index;
        n = q;
        next_directory = directory;
        index = int'(context_id) < CTX ? int'(context_id) : 0;
        record = directory[index*DIRECTORY+:DIRECTORY];
        rewritten = record.rewritten;
        if (o_response_valid && i_response_ready === 1'b1) n.response = 1'b0;
        if (o_commit_ack_valid && i_commit_ack_ready === 1'b1) n.ack = 1'b0;
        if (request_fire) begin
            n.request = incoming;
            n.data = '0;
            n.version = '0;
            n.crc = '0;
            n.status = CFG_SUCCESS;
            n.error_code = CFG_OK;
            if (incoming.context_id >= CTX ||
                ((incoming.command == C'(CFG_WRITE) || incoming.command == C'(CFG_READ)) &&
                64'(incoming.word_index) >= 64'(WORDS))) begin
                n.response = 1'b1;
                n.status = CFG_REJECTED;
                n.error_code = incoming.context_id >= CTX ? CFG_ERR_CONTEXT : CFG_ERR_WORD;
            end else if (i_power_safe !== 1'b1 || incoming.owner !== i_shell_owner_id ||
                incoming.kernel !== i_shell_kernel_id) begin
                n.response = 1'b1;
                n.status = CFG_REJECTED;
                n.error_code = i_power_safe !== 1'b1 ? CFG_ERR_POWER : CFG_ERR_PERMISSION;
            end else if ((incoming.command == C'(CFG_WRITE) ||
                incoming.command == C'(CFG_INVALIDATE) || incoming.command == C'(CFG_PREPARE)) &&
                i_shell_active_valid === 1'b1
                    && incoming.context_id == CI'(i_shell_context_id)) begin
                n.response = 1'b1;
                n.status = CFG_REJECTED;
                n.error_code = CFG_ERR_ENDPOINT;
            end else if (incoming.command == C'(CFG_ABORT_PREPARE)) begin
                n.prepared = 1'b0;
                n.response = 1'b1;
            end else if (incoming.command == C'(CFG_WRITE) ||
                incoming.command == C'(CFG_VALIDATE) || incoming.command == C'(CFG_PREPARE))
                n.phase = ADAPTER_QUERY_SEND;
            else if (incoming.command == C'(CFG_READ) || incoming.command == C'(CFG_QUERY) ||
                incoming.command == C'(CFG_INVALIDATE)) n.phase = ADAPTER_NATIVE_SEND;
            else begin
                n.response = 1'b1;
                n.status = CFG_REJECTED;
                n.error_code = CFG_ERR_COMMAND;
            end
        end
        if (native_fire) begin
            n.token = q.next_token;
            n.next_token = q.next_token + 1'b1;
            if (q.phase == ADAPTER_QUERY_SEND) n.phase = ADAPTER_QUERY_WAIT;
            else if (q.phase == ADAPTER_NATIVE_SEND) n.phase = ADAPTER_NATIVE_WAIT;
        end
        if (i_commit_valid === 1'b1 && o_commit_ready) begin
            n.epoch = i_commit_epoch;
            n.commit_error = !commit_identity;
            n.request.context_id = q.prepared_context;
            if (commit_identity) n.phase = ADAPTER_COMMIT_WAIT;
            else n.ack = 1'b1;
        end
        if (native_result && waiting) begin
            n.phase = ADAPTER_IDLE;
            n.data = i_shell_response_read_data;
            n.version = i_shell_response_context_version;
            n.crc = i_shell_response_crc;
            if (!response_matches) begin
                n.poison = 1'b1;
                n.data = '0;
                n.version = '0;
                n.crc = '0;
                n.status = CFG_REJECTED;
                n.error_code = CFG_ERR_IDENTITY;
                n.response = q.phase != ADAPTER_COMMIT_WAIT;
                if (q.phase == ADAPTER_COMMIT_WAIT) begin
                    n.ack = 1'b1;
                    n.commit_error = 1'b1;
                end
            end else if (q.phase == ADAPTER_COMMIT_WAIT) begin
                n.ack = 1'b1;
                n.prepared = 1'b0;
                n.commit_error = i_shell_response_error || i_shell_active_valid !== 1'b1 ||
                    i_shell_context_id != SC'(q.prepared_context) ||
                    i_shell_context_version != q.prepared_version;
                n.active_context = CI'(i_shell_context_id);
                n.active_version = i_shell_context_version;
                n.active_package = q.prepared_package;
                n.active_owner = i_shell_owner_id;
                n.active_kernel = i_shell_kernel_id;
                n.active_crc = q.prepared_crc;
            end else if (i_shell_response_error) begin
                n.response = 1'b1;
                n.status = CFG_REJECTED;
                n.error_code = i_shell_response_error_code == 8 ?
                    CFG_ERR_IMAGE_CRC : CFG_ERR_ENDPOINT;
            end else if (q.phase == ADAPTER_QUERY_WAIT) begin
                if ((record.loading || (record.bound &&
                    q.request.command != C'(CFG_WRITE))) &&
                    (record.package_id != q.request.package_id ||
                        record.owner != q.request.owner || record.kernel != q.request.kernel)) begin
                    n.response = 1'b1;
                    n.status = CFG_REJECTED;
                    n.error_code = CFG_ERR_PACKAGE;
                end else if (i_shell_response_context_version != q.request.version ||
                    (q.request.command == C'(CFG_VALIDATE) && record.dirty &&
                        rewritten != all_bytes)) begin
                    n.response = 1'b1;
                    n.status = CFG_REJECTED;
                    n.error_code = i_shell_response_context_version != q.request.version ?
                        CFG_ERR_VERSION : CFG_ERR_ENDPOINT;
                end else if (q.request.command == C'(CFG_PREPARE)) begin
                    // The native QUERY response itself can keep tile_shell
                    // non-quiescent. Recheck after that response is consumed.
                    n.phase = ADAPTER_PREPARE_CHECK;
                end else n.phase = ADAPTER_NATIVE_SEND;
            end else begin
                n.response = 1'b1;
                if (q.request.command == C'(CFG_WRITE)) begin
                    if (!record.loading) record.rewritten = '0;
                    record.loading = 1'b1;
                    record.package_id = q.request.package_id;
                    record.owner = q.request.owner;
                    record.kernel = q.request.kernel;
                    record.bound = 1'b0;
                    n.prepared = 1'b0;
                    rewritten = record.rewritten;
                    for (int b = 0; b < BY; b++)
                        if (byte_strobe[b]) rewritten[int'(q.request.word_index)*BY+b] = 1'b1;
                    record.rewritten = rewritten;
                end else if (q.request.command == C'(CFG_VALIDATE)) begin
                    record.bound = 1'b1;
                    record.loading = 1'b0;
                    record.dirty = 1'b0;
                    record.package_id = q.request.package_id;
                    record.owner = q.request.owner;
                    record.kernel = q.request.kernel;
                end else if (q.request.command == C'(CFG_INVALIDATE)) begin
                    record.bound = 1'b0;
                    record.dirty = 1'b0;
                    record.loading = 1'b0;
                    record.rewritten = '0;
                    n.prepared = 1'b0;
                end
                next_directory[index*DIRECTORY+:DIRECTORY] = record;
            end
        end
        if (q.phase == ADAPTER_PREPARE_CHECK && i_quiescent === 1'b1) begin
            n.phase = ADAPTER_IDLE;
            n.response = 1'b1;
            if (!record.bound || record.dirty || record.package_id != q.request.package_id ||
                record.owner != q.request.owner || record.kernel != q.request.kernel ||
                i_shell_validated[index] !== 1'b1 || q.crc != q.request.crc || current_active ||
                i_power_safe !== 1'b1 || i_shell_owner_id !== q.request.owner ||
                i_shell_kernel_id !== q.request.kernel) begin
                n.status = CFG_REJECTED;
                n.error_code = CFG_ERR_PREPARE;
            end else begin
                n.prepared = 1'b1;
                n.prepared_context = context_id;
                n.prepared_version = q.version;
                n.prepared_package = q.request.package_id;
                n.prepared_owner = q.request.owner;
                n.prepared_kernel = q.request.kernel;
                n.prepared_crc = q.crc;
            end
        end
        if (i_cancel === 1'b0) n.cancel_seen = 1'b0;
        if (i_cancel === 1'b1) begin
            n.prepared = 1'b0;
            n.response = 1'b0;
            if (!q.cancel_seen) begin
                for (int c = 0; c < CTX; c++) begin
                    record = directory[c*DIRECTORY+:DIRECTORY];
                    record.dirty = 1'b1;
                    record.loading = 1'b0;
                    record.bound = 1'b0;
                    record.rewritten = '0;
                    next_directory[c*DIRECTORY+:DIRECTORY] = record;
                end
                n.cancel_seen = 1'b1;
            end
            if (!waiting || native_result) n.phase = ADAPTER_IDLE;
            if (q.phase == ADAPTER_COMMIT_WAIT || q.ack) n.poison = 1'b1;
        end
        n.directory = next_directory;
    end
    banked_scratchpad_state #(
        .WIDTH($bits(state_t)),
        .PROTECTION(CONTROL_PROTECTION),
        .ASYNC_RESET(ASYNC_RESET)
    ) u_state (
        .i_clk(i_clk),
        .i_reset_n(i_reset_n),
        .i_data(n),
        .o_data(raw_state),
        .o_bad(state_bad)
    );
    dff #(.WIDTH(1), .ASYNC_RESET(ASYNC_RESET)) u_fatal (
        .i_clk(i_clk),
        .i_rstb(i_reset_n),
        .i_enable(1'b1),
        .i_d(fatal || state_bad),
        .o_q(fatal)
    );
endmodule
`default_nettype wire
