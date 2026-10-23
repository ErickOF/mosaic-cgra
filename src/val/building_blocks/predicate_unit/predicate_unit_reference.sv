`timescale 1ns / 1ps

// Independent behavioral oracle: direct addressed lane lists, no shared decode,
// isolation, write-enable or DFF logic. It also serves the two-state formal flow.
module predicate_unit_reference #(
    parameter int D = 4,
    parameter int N = 4,
    parameter int ASYNC_RESET = 0,
    localparam int AW = D > 1 ? $clog2(D) : 1,
    localparam int B = 3 * N + 5
) (
    input logic i_clk,
    input logic i_rstb,
    input logic i_clock_enable,
    input logic i_valid,
    input logic [3:0] i_opcode,
    input logic [N-1:0] i_lane_mask,
    input logic [AW-1:0] i_source_a_addr,
    input logic [AW-1:0] i_source_b_addr,
    input logic [AW-1:0] i_destination_addr,
    input logic [N-1:0] i_predicate_input,
    input logic i_write_enable,
    output logic [B-1:0] response,
    output logic [D*N-1:0] data,
    output logic [D*N-1:0] validity,
    output logic legal,
    output logic [B-1:0] next_response
);
    logic [N-1:0] value;
    logic [D*N-1:0] next_validity;
    logic need_a;
    logic need_b;

    always_comb begin
        value = '0;
        legal = (^{i_opcode, i_lane_mask, i_write_enable} !== 1'bx) && i_opcode <= 8;
        need_a = i_opcode >= 3 && i_opcode <= 7;
        need_b = i_opcode >= 5 && i_opcode <= 7;
        if (i_opcode == 8 && i_write_enable !== 1'b1) legal = 1'b0;
        for (int lane = 0; lane < N; lane++) begin
            if (i_lane_mask[lane] === 1'b1) begin
                if (need_a) begin
                    if ((^i_source_a_addr === 1'bx) || int'(i_source_a_addr) >= D)
                        legal = 1'b0;
                    else if (validity[int'(i_source_a_addr)*N+lane] !== 1'b1)
                        legal = 1'b0;
                end
                if (need_b) begin
                    if ((^i_source_b_addr === 1'bx) || int'(i_source_b_addr) >= D)
                        legal = 1'b0;
                    else if (validity[int'(i_source_b_addr)*N+lane] !== 1'b1)
                        legal = 1'b0;
                end
                if (i_write_enable === 1'b1 &&
                    ((^i_destination_addr === 1'bx) || int'(i_destination_addr) >= D))
                    legal = 1'b0;
            end
        end
        next_response = '0;
        next_validity = validity;
        if (i_valid === 1'b1) begin
            next_response[B-1] = 1'b1;
            next_response[0] = !legal;
            if (legal) begin
                for (int lane = 0; lane < N; lane++) begin
                    if (i_lane_mask[lane]) begin
                        case (i_opcode)
                            0: value[lane] = 1'b0;
                            1: value[lane] = 1'b1;
                            2: value[lane] = i_predicate_input[lane];
                            3: value[lane] = data[int'(i_source_a_addr)*N+lane];
                            4: value[lane] = !data[int'(i_source_a_addr)*N+lane];
                            5: value[lane] = data[int'(i_source_a_addr)*N+lane] &
                                data[int'(i_source_b_addr)*N+lane];
                            6: value[lane] = data[int'(i_source_a_addr)*N+lane] |
                                data[int'(i_source_b_addr)*N+lane];
                            7: value[lane] = data[int'(i_source_a_addr)*N+lane] ^
                                data[int'(i_source_b_addr)*N+lane];
                            default: value[lane] = 1'b0;
                        endcase
                        if (i_write_enable)
                            next_validity[int'(i_destination_addr)*N+lane] = i_opcode != 8;
                    end
                end
                next_response = {1'b1, value, (i_opcode == 8 ? {N{1'b0}} : i_lane_mask),
                    (|value), (i_opcode != 8 && (|i_lane_mask) && value == i_lane_mask),
                    (i_write_enable ? i_lane_mask : {N{1'b0}}), (i_opcode == 8), 1'b0};
            end
        end
    end

    // Payload is not cleared or rewritten on reset/invalidation in either oracle
    // or DUT. The reference's direct indexing differs from structural per-bit enables.
    always @(posedge i_clk) begin
        if (i_rstb === 1'b1 && i_clock_enable === 1'b1 && i_valid === 1'b1 &&
            legal && i_write_enable && i_opcode != 8) begin
            for (int lane = 0; lane < N; lane++) begin
                if (i_lane_mask[lane]) data[int'(i_destination_addr)*N+lane] <= value[lane];
            end
        end
    end

    if (ASYNC_RESET == 1) begin : g_async
        always @(posedge i_clk or negedge i_rstb) begin
            if (!i_rstb) begin
                response <= '0;
                validity <= '0;
            end else if (i_clock_enable) begin
                response <= next_response;
                validity <= next_validity;
            end
        end
    end else begin : g_sync
        always @(posedge i_clk) begin
            if (!i_rstb) begin
                response <= '0;
                validity <= '0;
            end else if (i_clock_enable) begin
                response <= next_response;
                validity <= next_validity;
            end
        end
    end
endmodule
