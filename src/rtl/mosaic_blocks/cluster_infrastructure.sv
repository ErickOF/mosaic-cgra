`timescale 1ns / 1ps
`default_nettype none
// A shell-compatible configuration endpoint for shared resources. Staging never
// changes live routing or permissions. Native validation/activation must finish
// before the endpoint reports success to configuration_network_tile_adapter.
module cluster_infrastructure #(
    parameter RESOURCE_KIND = 0, // 0: released static_mesh, 1: banked_scratchpad.
    parameter CONFIG_WORD_COUNT = 10,
    parameter CONTEXT_DEPTH = 4,
    parameter SCRATCHPAD_ADDR_WIDTH = 16,
    parameter SCRATCHPAD_CLIENTS = 4,
    parameter CONTROL_PROTECTION = 1,
    localparam int N = CONFIG_WORD_COUNT,
    localparam int C = CONTEXT_DEPTH,
    localparam int CI = C > 1 ? $clog2(C) : 1,
    localparam int WI = N > 1 ? $clog2(N) : 1,
    localparam int A = SCRATCHPAD_ADDR_WIDTH,
    localparam int P = SCRATCHPAD_CLIENTS
) (
    input wire i_clk,
    input wire i_rstb,
    input wire [15:0] i_owner_id,
    input wire [15:0] i_kernel_id,
    input wire [3:0] i_activation_epoch,
    input wire i_quiescent,
    input wire i_release,
    output wire o_release_done,
    output wire o_release_error,
    input wire i_cfg_request_valid,
    output wire o_cfg_request_ready,
    input wire [2:0] i_cfg_request_command,
    input wire [15:0] i_cfg_request_owner_id,
    input wire [CI-1:0] i_cfg_request_context_id,
    input wire [WI-1:0] i_cfg_request_word_index,
    input wire [63:0] i_cfg_request_write_data,
    input wire [7:0] i_cfg_request_write_strobe,
    input wire [31:0] i_cfg_request_expected_crc,
    input wire [15:0] i_cfg_request_tag,
    output wire o_cfg_response_valid,
    input wire i_cfg_response_ready,
    output wire [2:0] o_cfg_response_command,
    output wire [CI-1:0] o_cfg_response_context_id,
    output wire [63:0] o_cfg_response_read_data,
    output wire [15:0] o_cfg_response_context_version,
    output wire [31:0] o_cfg_response_crc,
    output wire o_cfg_response_error,
    output wire [7:0] o_cfg_response_error_code,
    output wire [15:0] o_cfg_response_tag,
    output wire [CI-1:0] o_active_context_id,
    output wire [15:0] o_active_context_version,
    output wire o_active_valid,
    output wire [C-1:0] o_context_valid,
    output wire o_error,
    output wire o_mesh_cfg_valid,
    input wire i_mesh_cfg_ready,
    output wire [2:0] o_mesh_cfg_opcode,
    output wire [7:0] o_mesh_cfg_context_id,
    output wire [15:0] o_mesh_cfg_context_version,
    output wire [WI-1:0] o_mesh_cfg_word_index,
    output wire [63:0] o_mesh_cfg_write_data,
    output wire [15:0] o_mesh_cfg_kernel_id,
    output wire [31:0] o_mesh_cfg_proof_id,
    output wire [31:0] o_mesh_cfg_checksum,
    input wire i_mesh_cfg_rsp_valid,
    output wire o_mesh_cfg_rsp_ready,
    input wire i_mesh_cfg_rsp_error,
    input wire [7:0] i_mesh_active_context_id,
    input wire [15:0] i_mesh_active_context_version,
    input wire [3:0] i_mesh_active_epoch,
    input wire i_mesh_active_valid,
    output wire o_region_cmd_valid,
    input wire i_region_cmd_ready,
    output wire [2:0] o_region_cmd_opcode,
    output wire [15:0] o_region_expected_generation,
    output wire [A-1:0] o_region_base,
    output wire [A:0] o_region_limit,
    output wire [P-1:0] o_region_read_mask,
    output wire [P-1:0] o_region_write_mask,
    input wire i_region_rsp_valid,
    output wire o_region_rsp_ready,
    input wire i_region_rsp_error,
    output wire [15:0] o_region_generation,
    output wire o_region_valid
);
    import tile_shell_pkg::*;
    import cluster_pkg::*;

    if (!(RESOURCE_KIND >= 0 && RESOURCE_KIND <= 1 && N >= 2 && N <= 63 &&
        C >= 1 && C <= 16 && A >= 4 && A <= 20 && P >= 2 && P <= 8 &&
        8 + A + A + 1 + 2 * P <= 64)) begin : g_invalid_parameters
        cluster_infrastructure_parameters_must_be_valid invalid_parameters ();
    end

    // Images are not reset. Only the protected written-byte directory grants
    // permission to read them; unwritten bytes enter CRC/readback as zero.
    wire [C*N*64-1:0] images;
    wire [C-1:0] image_bad;
    logic [N*64-1:0] next_image;
    wire image_write;

    typedef struct packed {
        logic [C*N*8-1:0] written;
        logic [C*16-1:0] versions;
        logic [C-1:0] validated;
        logic active;
        logic [CI-1:0] active_context;
        logic [15:0] active_version;
        infrastructure_phase_t phase;
        logic response;
        logic [2:0] command;
        logic [CI-1:0] context_id;
        logic [15:0] tag;
        logic [63:0] data;
        logic [31:0] crc;
        logic [7:0] code;
        logic [WI-1:0] index;
        logic [3:0] epoch;
        logic region_valid;
        logic [15:0] generation;
        logic release_seen;
        logic release_done;
        logic release_error;
    } state_t;

    state_t q;
    state_t n;
    wire bad;
    wire [C*16-1:0] versions = q.versions;
    wire [C*N*8-1:0] written_map = q.written;
    wire [C-1:0] validated = q.validated;
    logic [C*16-1:0] next_versions;
    logic [C*N*8-1:0] next_written;
    logic [C-1:0] next_validated;
    wire run = i_rstb === 1'b1 &&!bad;
    wire idle = q.phase == INFRA_IDLE &&!q.response;
    wire cfg_fire = i_cfg_request_valid === 1'b1 && o_cfg_request_ready;
    wire [CI-1:0] selected = idle ? i_cfg_request_context_id : q.context_id;
    wire valid_index = int'(selected) < C;
    logic [N*64-1:0] image;
    wire [31:0] image_crc;
    wire [15:0] version = valid_index ? versions[int'(selected)*16+:16] : 16'd0;
    wire [N*8-1:0] written = valid_index ? written_map[int'(selected)*N*8+:N*8] : '0;
    logic [7:0] code;
    wire region_invalidating = q.phase == INFRA_INVALIDATE_SEND || q.phase == INFRA_INVALIDATE_WAIT;

    tile_shell_state #(.WIDTH($bits(state_t)), .PROTECTION(CONTROL_PROTECTION)) u_state (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(1'b1),
        .i_data(n),
        .o_data(q),
        .o_bad(bad),
        .o_corrected()
    );

    always @* begin
        image = '0;

        for (int b = 0; b < N * 8; b++) begin
            if (valid_index && written[b]) image[b*8+:8] = images[(int'(selected)*N*64)+b*8+:8];
        end
    end

    configuration_network_crc #(.WIDTH(N * 64)) u_crc (.i_data(image), .o_crc(image_crc));

    assign o_cfg_request_ready = run && idle &&!i_release;
    assign o_cfg_response_valid = run && q.response;
    assign o_cfg_response_command = q.command;
    assign o_cfg_response_context_id = q.context_id;
    assign o_cfg_response_read_data = q.data;
    assign o_cfg_response_context_version = versions[int'(q.context_id)*16+:16];
    assign o_cfg_response_crc = q.crc;
    assign o_cfg_response_error = q.code != SHELL_OK;
    assign o_cfg_response_error_code = q.code;
    assign o_cfg_response_tag = q.tag;
    assign o_active_context_id = q.active_context;
    assign o_active_context_version = q.active_version;
    assign o_active_valid = run && q.active;
    assign o_context_valid = q.validated & ~image_bad;
    assign o_error = bad || (|image_bad);
    assign o_release_done = run && q.release_done;
    assign o_release_error = q.release_error;
    assign o_region_generation = q.generation;
    assign o_region_valid = q.region_valid;
    assign o_mesh_cfg_valid = run && RESOURCE_KIND == 0 && (q.phase == INFRA_WRITE_SEND ||
        q.phase == INFRA_NATIVE_SEND);
    assign o_mesh_cfg_rsp_ready = run && (q.phase == INFRA_WRITE_WAIT ||
        q.phase == INFRA_NATIVE_WAIT);
    assign o_mesh_cfg_opcode = q.phase == INFRA_WRITE_SEND || q.phase == INFRA_WRITE_WAIT ? 3'd0 :
        q.command == CFG_ACTIVATE ? 3'd3 : 3'd2;
    assign o_mesh_cfg_context_id = 8'(q.context_id);
    assign o_mesh_cfg_context_version = version;
    assign o_mesh_cfg_word_index = q.index;
    assign o_mesh_cfg_write_data = image[int'(q.index)*64+:64];
    assign o_mesh_cfg_kernel_id = i_kernel_id;
    assign o_mesh_cfg_proof_id = image[72+:32];
    assign o_mesh_cfg_checksum = q.crc;
    assign o_region_cmd_valid = run && RESOURCE_KIND == 1 &&
        (q.phase == INFRA_INVALIDATE_SEND || q.phase == INFRA_PROVISION_SEND);
    assign o_region_rsp_ready = run && (q.phase == INFRA_INVALIDATE_WAIT ||
        q.phase == INFRA_PROVISION_WAIT);
    assign o_region_cmd_opcode = region_invalidating ? 3'd4 : 3'd1;
    assign o_region_expected_generation = q.generation;
    assign o_region_base = image[8+:A];
    assign o_region_limit = image[8+A+:(A+1)];
    assign o_region_read_mask = image[9+2*A+:P];
    assign o_region_write_mask = image[9+2*A+P+:P];

    always @* begin
        code = SHELL_OK;

        if (^{i_cfg_request_command, i_cfg_request_context_id, i_cfg_request_owner_id,
            i_cfg_request_tag} === 1'bx) code = SHELL_ERR_UNKNOWN;
        else if (!valid_index) code = SHELL_ERR_CONTEXT;
        else if (image_bad[selected]) code = SHELL_ERR_CRC;
        else if (i_cfg_request_owner_id != i_owner_id) code = SHELL_ERR_OWNER;
        else if (i_cfg_request_command > CFG_QUERY) code = SHELL_ERR_COMMAND;
        else if ((i_cfg_request_command == CFG_WRITE || i_cfg_request_command == CFG_INVALIDATE) &&
            q.active && selected == q.active_context) code = SHELL_ERR_STATE;
        else if (i_cfg_request_command == CFG_WRITE || i_cfg_request_command == CFG_READ) begin
            if (int'(i_cfg_request_word_index) >= N) code = SHELL_ERR_WORD;
            else if (i_cfg_request_command == CFG_WRITE &&
                ^{i_cfg_request_write_data, i_cfg_request_write_strobe} === 1'bx)
                code = SHELL_ERR_UNKNOWN;
            else if (i_cfg_request_command == CFG_WRITE && &version) code = SHELL_ERR_VERSION;
        end else if (i_cfg_request_command == CFG_VALIDATE) begin
            if (!(&written)) code = SHELL_ERR_INCOMPLETE;
            else if (i_cfg_request_expected_crc !== image_crc) code = SHELL_ERR_CRC;
            else if (RESOURCE_KIND == 1 && (image[7:0] != 1 ||
                image[64+:16] != i_owner_id || image[80+:16] != i_kernel_id ||
                image[96+:16] != q.generation + 16'd1 || image[127:112] != 0 ||
                (image[63:0] >> (9 + 2 * A + 2 * P)) != 0 ||
                image[8+:A] >= image[8+A+:(A+1)] ||
                image[8+A+:(A+1)] > (64'd1 << A))) code = SHELL_ERR_CONTEXT;
        end else if (i_cfg_request_command == CFG_ACTIVATE) begin
            if (!validated[selected] || i_quiescent !== 1'b1) code = SHELL_ERR_STATE;
        end
    end

    always @* begin
        n = q;
        next_versions = versions;
        next_written = written_map;
        next_validated = validated;

        if (q.response && i_cfg_response_ready === 1'b1) n.response = 1'b0;

        if (!i_release) begin
            n.release_seen = 1'b0;
            n.release_done = 1'b0;
            n.release_error = 1'b0;
        end

        if (run && i_release &&!q.release_seen && idle && i_quiescent) begin
            n.release_seen = 1'b1;
            next_validated = '0;
            n.active = 1'b0;

            if (RESOURCE_KIND == 1 && q.region_valid) n.phase = INFRA_INVALIDATE_SEND;
            else n.release_done = 1'b1;
        end

        if (run && cfg_fire) begin
            n.command = i_cfg_request_command;
            n.context_id = i_cfg_request_context_id;
            n.tag = i_cfg_request_tag;
            n.data = '0;
            n.crc = image_crc;
            n.code = code;
            n.response = 1'b1;
            n.index = '0;

            if (code == SHELL_OK) begin
                case (i_cfg_request_command)
                    CFG_WRITE: begin
                        next_versions[int'(selected)*16+:16] = version + 1'b1;
                        next_validated[selected] = 1'b0;

                        for (int b = 0; b < 8; b++) begin
                            if (i_cfg_request_write_strobe[b])
                                next_written[int'(selected)*N*8+
                                    int'(i_cfg_request_word_index)*8+b] = 1'b1;
                        end

                        n.crc = '0;
                    end
                    CFG_READ: n.data = image[int'(i_cfg_request_word_index)*64+:64];
                    CFG_QUERY: n.data = 64'(written_words(written)) |
                        (64'(validated[selected]) << N);
                    CFG_INVALIDATE: begin
                        next_validated[selected] = 1'b0;
                        next_written[int'(selected)*N*8+:N*8] = '0;
                    end
                    CFG_VALIDATE: begin
                        if (RESOURCE_KIND == 0) begin
                            n.phase = INFRA_WRITE_SEND;
                            n.response = 1'b0;
                        end else next_validated[selected] = 1'b1;
                    end
                    CFG_ACTIVATE: begin
                        n.epoch = i_activation_epoch;
                        n.response = 1'b0;
                        n.phase = RESOURCE_KIND == 0 ? INFRA_NATIVE_SEND :
                            q.region_valid ? INFRA_INVALIDATE_SEND : INFRA_PROVISION_SEND;
                    end
                    default: begin end
                endcase
            end
        end

        if (run && q.phase == INFRA_WRITE_SEND && i_mesh_cfg_ready) n.phase = INFRA_WRITE_WAIT;

        if (run && q.phase == INFRA_WRITE_WAIT && i_mesh_cfg_rsp_valid) begin
            if (i_mesh_cfg_rsp_error) begin
                n.code = SHELL_ERR_CONTEXT;
                n.response = 1'b1;
                n.phase = INFRA_IDLE;
            end else if (int'(q.index) == N - 1) n.phase = INFRA_NATIVE_SEND;
            else begin
                n.index = q.index + 1'b1;
                n.phase = INFRA_WRITE_SEND;
            end
        end

        if (run && q.phase == INFRA_NATIVE_SEND && i_mesh_cfg_ready) n.phase = INFRA_NATIVE_WAIT;

        if (run && q.phase == INFRA_NATIVE_WAIT && i_mesh_cfg_rsp_valid) begin
            n.phase = INFRA_IDLE;
            n.response = 1'b1;

            if (i_mesh_cfg_rsp_error) n.code = SHELL_ERR_CONTEXT;
            else if (q.command == CFG_VALIDATE) next_validated[q.context_id] = 1'b1;
            else if (!i_mesh_active_valid || i_mesh_active_context_id != 8'(q.context_id) ||
                i_mesh_active_context_version != version || i_mesh_active_epoch != q.epoch)
                n.code = SHELL_ERR_CONTEXT;
            else begin
                n.active = 1'b1;
                n.active_context = q.context_id;
                n.active_version = version;
            end
        end

        if (run && q.phase == INFRA_INVALIDATE_SEND && i_region_cmd_ready) n.phase =
        INFRA_INVALIDATE_WAIT;

        if (run && q.phase == INFRA_INVALIDATE_WAIT && i_region_rsp_valid) begin
            if (i_region_rsp_error) begin
                n.phase = INFRA_IDLE;
                n.code = SHELL_ERR_CONTEXT;
                n.release_error = 1'b1;
                n.release_done = q.release_seen;
                n.response = !q.release_seen;
            end else begin
                n.region_valid = 1'b0;
                n.phase = q.release_seen ? INFRA_IDLE : INFRA_PROVISION_SEND;
                n.release_done = q.release_seen;
            end
        end

        if (run && q.phase == INFRA_PROVISION_SEND && i_region_cmd_ready) n.phase =
        INFRA_PROVISION_WAIT;

        if (run && q.phase == INFRA_PROVISION_WAIT && i_region_rsp_valid) begin
            n.phase = INFRA_IDLE;
            n.response = 1'b1;

            if (i_region_rsp_error) n.code = SHELL_ERR_CONTEXT;
            else begin
                n.region_valid = 1'b1;
                n.generation = q.generation + 1'b1;
                n.active = 1'b1;
                n.active_context = q.context_id;
                n.active_version = version;
            end
        end

        n.versions = next_versions;
        n.written = next_written;
        n.validated = next_validated;
    end

    function automatic logic [N-1:0] written_words(input logic [N*8-1:0] bytes_written);
        for (int w = 0; w < N; w++) written_words[w] = &bytes_written[w*8+:8];
    endfunction

    assign image_write = run && cfg_fire && code == SHELL_OK &&
        i_cfg_request_command == CFG_WRITE;

    always @* begin
        next_image = image;

        for (int b = 0; b < 8; b++) begin
            if (i_cfg_request_write_strobe[b])
                next_image[int'(i_cfg_request_word_index)*64+b*8+:8] =
                    i_cfg_request_write_data[b*8+:8];
        end
    end

    for (genvar c = 0; c < C; c++) begin : g_image
        tile_shell_state #(.WIDTH(N * 64), .PROTECTION(CONTROL_PROTECTION)) u_storage (
            .i_clk(i_clk),
            .i_rstb(i_rstb),
            .i_enable(image_write && int'(selected) == c),
            .i_data(next_image),
            .o_data(images[c*N*64+:N*64]),
            .o_bad(image_bad[c]),
            .o_corrected()
        );
    end
endmodule
`default_nettype wire
