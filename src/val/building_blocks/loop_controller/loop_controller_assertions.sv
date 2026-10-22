`timescale 1ns / 1ps

// Native simulation assertions. Safe-point correctness belongs to the environment;
// the checker asserts only the controller's use of that external input.
module loop_controller_assertions #(
    parameter int TOKEN_WIDTH = 1,
    parameter int RECORD_WIDTH = 1,
    parameter int COUNT_WIDTH = 1,
    parameter int PACE_WIDTH = 1
) (
    input wire i_clk,
    input wire i_rstb,
    input wire i_flush,
    input wire i_fault,
    input wire i_valid,
    input wire i_ready,
    input wire [TOKEN_WIDTH-1:0] i_token,
    input wire i_record_valid,
    input wire i_record_ready,
    input wire [RECORD_WIDTH-1:0] i_record,
    input wire i_transfer_event,
    input wire i_quiesce,
    input wire i_execution_quiescent,
    input wire i_pause_event,
    input wire i_complete_event,
    input wire i_abort_event,
    input wire i_zero_trip,
    input wire [COUNT_WIDTH-1:0] i_linear,
    input wire [COUNT_WIDTH-1:0] i_total,
    input wire [PACE_WIDTH-1:0] i_pacing,
    input wire [15:0] i_controls
);
    logic initialized = 1'b0;
    logic stalled;
    logic record_stalled;
    logic [TOKEN_WIDTH-1:0] held_token;
    logic [RECORD_WIDTH-1:0] held_record;
    integer checks = 0;

    always @(posedge i_clk) begin : check_edge
        logic transferred;
        logic safe_point;
        if (i_rstb !== 1'b1 || i_flush !== 1'b0 || i_fault) begin
            initialized = 1'b0;
        end else begin
            if (initialized) begin
                if (stalled) begin
                    assert (i_valid && i_token === held_token)
                        else $fatal(1, "Loop token changed under backpressure");
                end
                if (record_stalled) begin
                    assert (i_record_valid && i_record === held_record)
                        else $fatal(1, "Loop completion changed under backpressure");
                end
            end
            assert ( ^ i_controls !== 1'bx)
                else $fatal(1, "Unknown loop output control");
            if (i_valid) begin
                assert (i_linear < i_total && i_pacing == 0)
                    else $fatal(1, "Loop launch outside count/pacing range");
                assert (!i_zero_trip) else $fatal(1, "Zero-trip loop launched a token");
            end
            transferred = i_valid && (i_ready === 1'b1);
            safe_point = i_quiesce && (i_execution_quiescent === 1'b1);
            stalled = i_valid && (i_ready !== 1'b1);
            record_stalled = i_record_valid && (i_record_ready !== 1'b1);
            held_token = i_token;
            held_record = i_record;
            initialized = 1'b1;
            #0.001;
            if (i_rstb === 1'b1 && i_flush === 1'b0 &&!i_fault) begin
                assert (i_transfer_event == transferred)
                    else $fatal(1, "Loop transfer event mismatch");
                if (i_pause_event || i_abort_event)
                    assert (safe_point) else $fatal(1, "Loop stopped before safe point");
                if (i_complete_event &&!i_zero_trip)
                    assert (safe_point) else $fatal(1, "Loop completed before safe point");
                checks++;
            end
        end
    end
endmodule
