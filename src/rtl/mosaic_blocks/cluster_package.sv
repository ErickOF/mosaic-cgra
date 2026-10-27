`timescale 1ns / 1ps
`default_nettype none
// One resident MVP manifest. Configuration may stage inactive images, but commit
// must match this immutable manifest and every successfully prepared image CRC.
module cluster_package #(
    parameter NUM_TILES = 4,
    parameter NUM_ENDPOINTS = NUM_TILES + 2,
    parameter ARCHITECTURE_HASH = 256'd0,
    localparam int N = NUM_TILES,
    localparam int E = NUM_ENDPOINTS
) (
    input wire i_clk,
    input wire i_rstb,
    input wire i_clear,
    input wire i_enable,
    input wire i_commit_fire,
    input wire [15:0] i_owner_id,
    input wire [15:0] i_kernel_id,
    input wire [15:0] i_allocation_generation,
    input wire [31:0] i_topology_id,
    input wire [3:0] i_next_epoch,
    input wire i_package_valid,
    output wire o_package_ready,
    input wire [15:0] i_package_owner_id,
    input wire [15:0] i_package_kernel_id,
    input wire [31:0] i_package_id,
    input wire [7:0] i_package_context_id,
    input wire [15:0] i_package_allocation_generation,
    input wire [255:0] i_package_architecture_hash,
    input wire [31:0] i_package_topology_id,
    input wire [15:0] i_package_contract_version,
    input wire [15:0] i_package_requirements,
    input wire [N-1:0] i_package_resource_mask,
    input wire [E-1:0] i_package_endpoint_mask,
    input wire [E*16-1:0] i_package_context_versions,
    input wire [E*32-1:0] i_package_image_crcs,
    input wire [3:0] i_package_epoch,
    input wire i_package_suspend_safe,
    input wire [15:0] i_package_tag,
    output wire o_package_response_valid,
    input wire i_package_response_ready,
    output wire [7:0] o_package_response_error_code,
    output wire [15:0] o_package_response_tag,
    input wire [31:0] i_commit_package_id,
    input wire [7:0] i_commit_context_id,
    input wire [E*16-1:0] i_commit_context_versions,
    input wire [3:0] i_commit_epoch,
    input wire [E*32-1:0] i_prepared_image_crcs,
    output wire o_commit_compatible,
    output wire o_suspend_safe,
    output wire o_manifest_valid,
    output wire o_idle,
    output wire o_error
);
    import cluster_pkg::*;

    typedef struct packed {
        logic valid;
        logic locked;
        logic response;
        logic [7:0] code;
        logic [15:0] tag;
        logic [31:0] package_id;
        logic [7:0] context_id;
        logic [E*16-1:0] versions;
        logic [E*32-1:0] crcs;
        logic [3:0] epoch;
        logic suspend_safe;
    } manifest_t;

    manifest_t q;
    manifest_t n;
    wire bad;
    logic [7:0] code;

    tile_shell_state #(.WIDTH($bits(manifest_t)), .PROTECTION(1)) u_state (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(1'b1),
        .i_data(n),
        .o_data(q),
        .o_bad(bad),
        .o_corrected()
    );

    assign o_package_ready = i_rstb === 1'b1 && i_enable &&!bad &&!q.response &&!q.locked &&
        (^i_package_tag !== 1'bx);
    assign o_package_response_valid = i_rstb === 1'b1 &&!bad && q.response;
    assign o_package_response_error_code = q.code;
    assign o_package_response_tag = q.tag;
    assign o_commit_compatible = i_rstb === 1'b1 &&!bad && q.valid &&!q.response &&
        i_commit_package_id === q.package_id && i_commit_context_id === q.context_id &&
        i_commit_context_versions === q.versions && i_commit_epoch === q.epoch &&
        i_prepared_image_crcs === q.crcs;
    assign o_suspend_safe = !bad && q.valid && q.suspend_safe;
    assign o_manifest_valid = !bad && q.valid;
    assign o_idle = !q.response;
    assign o_error = bad;

    always @* begin
        code = CLUSTER_OK;

        if (^{i_package_owner_id, i_package_kernel_id, i_package_id, i_package_context_id,
            i_package_allocation_generation, i_package_architecture_hash, i_package_topology_id,
            i_package_contract_version, i_package_requirements, i_package_resource_mask,
            i_package_endpoint_mask, i_package_context_versions, i_package_image_crcs,
            i_package_epoch, i_package_suspend_safe, i_package_tag} === 1'bx)
            code = CLUSTER_ERR_UNKNOWN;
        else if (i_package_owner_id != i_owner_id || i_package_kernel_id != i_kernel_id ||
            i_package_allocation_generation != i_allocation_generation) code = CLUSTER_ERR_OWNER;
        else if (i_package_architecture_hash != ARCHITECTURE_HASH ||
            i_package_topology_id != i_topology_id || i_package_contract_version != 1)
            code = CLUSTER_ERR_PACKAGE;
        else if (i_package_requirements != 0) code = CLUSTER_ERR_UNSUPPORTED;
        else if (i_package_context_id >= 4) code = CLUSTER_ERR_CONTEXT;
        else if (i_package_resource_mask != {N{1'b1}} ||
            i_package_endpoint_mask != {E{1'b1}}) code = CLUSTER_ERR_RESOURCE;
        else if (i_package_epoch != i_next_epoch) code = CLUSTER_ERR_EPOCH;
    end

    always @* begin
        n = q;

        if (q.response && i_package_response_ready === 1'b1) n.response = 1'b0;

        if (i_clear) begin
            n.valid = 1'b0;
            n.locked = 1'b0;
        end

        if (i_commit_fire) n.locked = 1'b1;

        if (o_package_ready && i_package_valid === 1'b1) begin
            n.response = 1'b1;
            n.code = code;
            n.tag = i_package_tag;

            if (code == CLUSTER_OK) begin
                n.valid = 1'b1;
                n.package_id = i_package_id;
                n.context_id = i_package_context_id;
                n.versions = i_package_context_versions;
                n.crcs = i_package_image_crcs;
                n.epoch = i_package_epoch;
                n.suspend_safe = i_package_suspend_safe;
            end
        end
    end
endmodule
`default_nettype wire
