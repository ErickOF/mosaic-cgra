`timescale 1ns / 1ps
`default_nettype none
// One owned request per MST scratchpad client. The directory retains the complete
// opaque command identity until its response is accepted; stores never use flush
// as cancellation. Read/write arbitration rotates only on accepted requests.
module cluster_memory_bridge #(
    parameter ADDRESS_WIDTH = 16,
    parameter TAG_WIDTH = 76,
    parameter IDENTITY_WIDTH = 142
) (
    input wire i_clk,
    input wire i_rstb,
    input wire i_read_valid,
    output wire o_read_ready,
    input wire [31:0] i_read_address,
    input wire [1:0] i_read_size_log2,
    input wire [TAG_WIDTH-1:0] i_read_tag,
    input wire [IDENTITY_WIDTH-1:0] i_read_identity,
    input wire [3:0] i_read_region,
    input wire [15:0] i_read_generation,
    input wire i_write_valid,
    output wire o_write_ready,
    input wire [31:0] i_write_address,
    input wire [1:0] i_write_size_log2,
    input wire [TAG_WIDTH-1:0] i_write_tag,
    input wire [IDENTITY_WIDTH-1:0] i_write_identity,
    input wire [3:0] i_write_region,
    input wire [15:0] i_write_generation,
    input wire [63:0] i_write_data,
    input wire [7:0] i_write_strobe,
    output wire o_read_rsp_valid,
    input wire i_read_rsp_ready,
    output wire o_write_rsp_valid,
    input wire i_write_rsp_ready,
    output wire o_rsp_error,
    output wire [63:0] o_read_data,
    output wire [3:0] o_write_bytes_committed,
    output wire [TAG_WIDTH-1:0] o_rsp_tag,
    output wire [IDENTITY_WIDTH-1:0] o_rsp_identity,
    output wire o_request_valid,
    input wire i_request_ready,
    output wire [1:0] o_request_opcode,
    output wire [ADDRESS_WIDTH-1:0] o_request_address,
    output wire [3:0] o_request_size,
    output wire [63:0] o_request_data,
    output wire [7:0] o_request_strobe,
    output wire [15:0] o_request_owner,
    output wire [15:0] o_request_kernel,
    output wire [2:0] o_request_region,
    output wire [15:0] o_request_generation,
    output wire [TAG_WIDTH-1:0] o_request_tag,
    input wire i_response_valid,
    output wire o_response_ready,
    input wire i_response_error,
    input wire [63:0] i_response_data,
    input wire [TAG_WIDTH-1:0] i_response_tag,
    input wire [1:0] i_response_opcode,
    input wire [2:0] i_response_region,
    input wire [15:0] i_response_generation,
    output wire o_idle,
    output wire o_error
);
    import cluster_pkg::*;

    typedef struct packed {
        memory_phase_t phase;
        logic write_request;
        logic prefer_write;
        logic local_error;
        logic fatal;
        logic [31:0] address;
        logic [1:0] size_log2;
        logic [TAG_WIDTH-1:0] tag;
        logic [IDENTITY_WIDTH-1:0] identity;
        logic [3:0] region;
        logic [15:0] generation;
        logic [63:0] data;
        logic [7:0] strobe;
    } directory_t;

    directory_t q;
    directory_t n;
    wire bad;
    wire choose_write = i_write_valid === 1'b1 &&
        (q.prefer_write || i_read_valid !== 1'b1);
    wire rsp_ready = q.write_request ? i_write_rsp_ready === 1'b1 : i_read_rsp_ready === 1'b1;
    wire response_match = i_response_tag === q.tag &&
        i_response_opcode === (q.write_request ? 2'd1 : 2'd0) &&
        i_response_region === q.region[2:0] && i_response_generation === q.generation;
    wire run = i_rstb === 1'b1 &&!bad &&!q.fatal;
    wire [3:0] byte_count;
    logic [3:0] count;
    wire [7:0] strobe = q.strobe;

    always @* begin
        count = '0;

        for (int b = 0; b < 8; b++) count = count + 4'(strobe[b]);
    end

    assign byte_count = count;

    tile_shell_state #(.WIDTH($bits(directory_t)), .PROTECTION(1)) u_directory (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(1'b1),
        .i_data(n),
        .o_data(q),
        .o_bad(bad),
        .o_corrected()
    );

    assign o_read_ready = run && q.phase == MEMORY_IDLE &&!choose_write;
    assign o_write_ready = run && q.phase == MEMORY_IDLE && choose_write;
    assign o_request_valid = run && q.phase == MEMORY_SEND;
    assign o_request_opcode = q.write_request ? 2'd1 : 2'd0;
    assign o_request_address = q.address[ADDRESS_WIDTH-1:0];

    // The MST uses log2(bytes); the scratchpad public ABI uses a byte count.
    assign o_request_size = 4'(1 << q.size_log2);
    assign o_request_data = q.data;
    assign o_request_strobe = q.strobe;
    assign o_request_owner = q.identity[32+:16];
    assign o_request_kernel = q.identity[48+:16];
    assign o_request_region = q.region[2:0];
    assign o_request_generation = q.generation;
    assign o_request_tag = q.tag;
    assign o_read_rsp_valid = run &&!q.write_request &&
        (q.phase == MEMORY_LOCAL_ERROR || (q.phase == MEMORY_WAIT && i_response_valid &&
        response_match));
    assign o_write_rsp_valid = run && q.write_request &&
        (q.phase == MEMORY_LOCAL_ERROR || (q.phase == MEMORY_WAIT && i_response_valid &&
        response_match));
    assign o_rsp_error = q.local_error || i_response_error;
    assign o_read_data = q.phase == MEMORY_LOCAL_ERROR ? 64'd0 : i_response_data;
    assign o_write_bytes_committed = o_rsp_error ? 4'd0 : byte_count;
    assign o_rsp_tag = q.tag;
    assign o_rsp_identity = q.identity;
    assign o_response_ready = run && q.phase == MEMORY_WAIT && response_match && rsp_ready;
    assign o_idle = q.phase == MEMORY_IDLE;
    assign o_error = bad || q.fatal;

    always @* begin
        n = q;

        if (run && q.phase == MEMORY_IDLE && (i_read_valid === 1'b1 ||
        i_write_valid === 1'b1)) begin
            n.write_request = choose_write;
            n.prefer_write = !choose_write;
            n.address = choose_write ? i_write_address : i_read_address;
            n.size_log2 = choose_write ? i_write_size_log2 : i_read_size_log2;
            n.tag = choose_write ? i_write_tag : i_read_tag;
            n.identity = choose_write ? i_write_identity : i_read_identity;
            n.region = choose_write ? i_write_region : i_read_region;
            n.generation = choose_write ? i_write_generation : i_read_generation;
            n.data = choose_write ? i_write_data : 64'd0;
            n.strobe = choose_write ? i_write_strobe : 8'd0;
            n.local_error = (n.address >> ADDRESS_WIDTH) != 0 || n.region[3] ||
                (^{n.address, n.size_log2, n.tag, n.identity, n.region, n.generation,
                n.data, n.strobe} === 1'bx);
            n.phase = n.local_error ? MEMORY_LOCAL_ERROR : MEMORY_SEND;
        end

        if (run && q.phase == MEMORY_SEND && i_request_ready === 1'b1) n.phase = MEMORY_WAIT;

        if (run && q.phase == MEMORY_WAIT && i_response_valid === 1'b1) begin
            if (!response_match) n.fatal = 1'b1;
            else if (rsp_ready) n.phase = MEMORY_IDLE;
        end

        if (run && q.phase == MEMORY_LOCAL_ERROR && rsp_ready) n.phase = MEMORY_IDLE;
    end
endmodule
`default_nettype wire
