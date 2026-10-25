`timescale 1ns / 1ps

// Native RTL checker. Snapshot inputs before NBA and check one precision tick
// later. Producer persistence and consumer progress are environment obligations;
// they are deliberately not assumed by these safety assertions.
module event_barrier_assertions #(
    parameter int E = 16,
    parameter int K = 4,
    parameter int W = 4,
    parameter int B = 4,
    parameter int P = 16,
    parameter int G = 4,
    parameter int EI = 4,
    parameter int BI = 2,
    parameter int RESULT_BITS = 49,
    parameter int RELEASE_BITS = 43,
    parameter int QW = 3,
    parameter int QR = 3
) (
    input wire i_clk,
    input wire i_rstb,
    input wire i_flush,
    input wire i_fatal,
    input wire i_post,
    input wire i_ack,
    input wire [1:0] i_ack_mode,
    input wire [EI-1:0] i_post_id,
    input wire [EI-1:0] i_ack_id,
    input wire i_release_post,
    input wire [EI-1:0] i_release_event,
    input wire [E-1:0] i_consumed,
    input wire i_wait_complete,
    input wire i_wait_consume,
    input wire [1:0] i_wait_mode,
    input wire [E-1:0] i_wait_mask,
    input wire [E-1:0] i_matched,
    input wire [E*K-1:0] i_counts,
    input wire [E-1:0] i_pending,
    input wire [E-1:0] i_saturated,
    input wire [W-1:0] i_wait_active,
    input wire i_release,
    input wire [BI-1:0] i_barrier_id,
    input wire [B-1:0] i_barrier_enable,
    input wire [B*P-1:0] i_arrived,
    input wire [B*P-1:0] i_expected,
    input wire [B*G-1:0] i_generations,
    input wire i_result_valid,
    input wire i_result_ready,
    input wire [RESULT_BITS-1:0] i_result,
    input wire i_release_valid,
    input wire i_release_ready,
    input wire [RELEASE_BITS-1:0] i_release_payload,
    input wire [QW-1:0] i_result_occupancy,
    input wire [QR-1:0] i_release_occupancy,
    input wire i_result_create,
    input wire i_cancel_create,
    input wire [3:0] i_mutation_commits,
    input wire i_event_post,
    input wire i_event_ack,
    input wire i_event_wait,
    input wire i_event_release
);
    logic initialized = 1'b0;
    logic [K-1:0] expected_counts[E];
    logic [G-1:0] expected_generations[B];
    logic [RESULT_BITS-1:0] held_result;
    logic [RELEASE_BITS-1:0] held_release;
    logic check_result;
    logic check_release;
    logic expected_post;
    logic expected_ack;
    logic expected_wait;
    logic expected_release;
    logic [QW-1:0] result_occupancy;
    logic [QR-1:0] release_occupancy;
    logic [E-1:0] eligible;
    logic [E-1:0] lowest;
    logic seen;
    integer commits;

    always @(posedge i_clk) begin
        if (i_rstb === 1'b0) initialized = 1'b1;
        if (initialized && i_rstb === 1'b1) begin
            commits = 0;
            for (int m = 0; m < 4; m++) commits += int'(i_mutation_commits[m]);
            assert (commits <= 1) else $fatal(1, "Multiple event-bank writers");
            assert (!(i_cancel_create && i_wait_complete))
                else $fatal(1, "Multiple wait results");
            assert (i_release_post == (i_release && i_mutation_commits[3]))
                else $fatal(1, "Nonatomic release event");
            eligible = i_wait_mask & i_pending;
            lowest = '0;
            seen = 1'b0;
            for (int e = 0; e < E; e++) begin
                if (eligible[e] &&!seen) begin
                    lowest[e] = 1'b1;
                    seen = 1'b1;
                end
                expected_counts[e] = i_counts[e*K+:K];
                if (i_flush) expected_counts[e] = '0;
                else begin
                    if ((i_post && i_post_id == EI'(e)) ||
                        (i_release_post && i_release_event == EI'(e))) begin
                        assert (expected_counts[e] != {K{1'b1}})
                            else $fatal(1, "Event overflow");
                        expected_counts[e] += 1'b1;
                    end
                    if (i_ack && i_ack_id == EI'(e)) begin
                        assert (expected_counts[e] != '0) else $fatal(1, "Event underflow");
                        if (i_ack_mode == 2'd0) expected_counts[e] -= 1'b1;
                        else expected_counts[e] = '0;
                    end
                    if (i_consumed[e]) begin
                        assert (expected_counts[e] != '0) else $fatal(1, "Consume underflow");
                        expected_counts[e] -= 1'b1;
                    end
                end
            end
            if (i_wait_complete) begin
                assert (i_matched == (i_wait_mode == 2'd0 ? lowest : i_wait_mask))
                    else $fatal(1, "Wait matching");
                assert (i_matched != '0 && (i_matched & i_pending) == i_matched)
                    else $fatal(1, "Unsatisfied wait completion");
                assert (i_consumed == (i_wait_consume ? i_matched : {E{1'b0}}))
                    else $fatal(1, "Wait consumption");
            end
            for (int b = 0; b < B; b++) begin
                assert ((i_arrived[b*P+:P] & ~ i_expected[b*P+:P]) == '0)
                    else $fatal(1, "Unauthorized participant state");
                expected_generations[b] = i_generations[b*G+:G];
                if ((i_flush && i_barrier_enable[b]) || (i_release && i_barrier_id == BI'(b)))
                    expected_generations[b] += 1'b1;
            end
            check_result = i_result_valid &&!i_result_ready &&!i_flush &&!i_fatal;
            check_release = i_release_valid &&!i_release_ready &&!i_flush &&!i_fatal;
            held_result = i_result;
            held_release = i_release_payload;
            result_occupancy = i_flush ? '0 : i_result_occupancy + QW'(i_result_create) -
                QW'(i_result_valid && i_result_ready);
            release_occupancy = i_flush ? '0 : i_release_occupancy + QR'(i_release) -
                QR'(i_release_valid && i_release_ready);
            expected_post = i_post || i_release_post;
            expected_ack = i_ack;
            expected_wait = i_wait_complete;
            expected_release = i_release;
            #1ps;
            for (int e = 0; e < E; e++) begin
                assert (i_counts[e*K+:K] === expected_counts[e])
                    else $fatal(1, "Atomic event next value");
                assert (i_pending[e] === (expected_counts[e] != '0))
                    else $fatal(1, "Pending correspondence");
                assert (i_saturated[e] === (expected_counts[e] == {K{1'b1}}))
                    else $fatal(1, "Saturated correspondence");
            end
            for (int b = 0; b < B; b++)
                assert (i_generations[b*G+:G] === expected_generations[b])
                    else $fatal(1, "Generation/release correspondence");
            if (check_result &&!i_fatal &&!i_flush)
                assert (i_result_valid && i_result === held_result)
                    else $fatal(1, "Wait result changed under backpressure");
            if (check_release &&!i_fatal &&!i_flush)
                assert (i_release_valid && i_release_payload === held_release)
                    else $fatal(1, "Barrier release changed under backpressure");
            assert (i_result_occupancy === result_occupancy)
                else $fatal(1, "Wait queue occupancy");
            assert (i_release_occupancy === release_occupancy)
                else $fatal(1, "Release queue occupancy");
            assert ({i_event_post, i_event_ack, i_event_wait, i_event_release} ===
                {expected_post, expected_ack, expected_wait, expected_release})
                else $fatal(1, "Event pulse correspondence");
        end
        if (initialized && i_rstb === 1'b0) begin
            #1ps;
            assert (i_counts == '0 && i_generations == '0 && i_wait_active == '0 &&
                i_arrived == '0 &&!i_result_valid &&!i_release_valid)
                else $fatal(1, "Reset left live state");
        end
    end
endmodule
