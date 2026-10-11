`timescale 1ns / 1ps

// Asynchronously assert reset and synchronously release it into one clock domain.
module reset_synchronizer #(
    parameter int unsigned STAGES = 2
) (
    input  logic i_clk,
    input  logic i_async_rstb,
    output logic o_rstb
);
    if (STAGES < 2) begin : gen_invalid_stages
        initial $fatal(1, "STAGES must be greater than or equal to two");
    end

    // Preserve the stage chain for CDC recognition and metastability containment.
    (* ASYNC_REG = "TRUE", SHREG_EXTRACT = "NO", DONT_TOUCH = "TRUE" *)
    logic [STAGES-1:0] sync_stages;

    always_ff @(posedge i_clk or negedge i_async_rstb) begin
        if (!i_async_rstb) begin
            sync_stages <= '0;
        end else begin
            sync_stages <= {sync_stages[STAGES-2:0], 1'b1};
        end
    end

    assign o_rstb = sync_stages[STAGES-1];
endmodule
