`timescale 1ns / 1ps

// Portable model of visible state plus an explicitly saved retention image.
module retention_register #(
    parameter int unsigned WIDTH = 1,
    parameter logic [WIDTH-1:0] RESET_VALUE = '0,
    parameter ASYNC_RESET = 0,
    parameter HAS_ENABLE = 1
) (
    input  logic             i_clk,
    input  logic             i_rstb,
    input  logic             i_enable,
    input  logic             i_save,
    input  logic             i_restore,
    input  logic [WIDTH-1:0] i_d,
    output logic [WIDTH-1:0] o_q
);
    logic [WIDTH-1:0] retained_image;

    if (WIDTH < 1) begin : gen_invalid_width
        retention_register_width_must_be_greater_than_zero invalid_width ();
    end
    if (((^RESET_VALUE == 1'b0) || (^RESET_VALUE == 1'b1)) !== 1'b1) begin : gen_invalid_reset_value
        retention_register_reset_value_must_be_known invalid_reset_value ();
    end
    // Preserve caller values so non-Boolean and X/Z literals are checked
    // before a typed conversion could silently select a valid branch.
    if (ASYNC_RESET !== 0 && ASYNC_RESET !== 1) begin : gen_invalid_async_reset
        retention_register_async_reset_must_be_boolean invalid_async_reset ();
    end
    if (HAS_ENABLE !== 0 && HAS_ENABLE !== 1) begin : gen_invalid_has_enable
        retention_register_has_enable_must_be_boolean invalid_has_enable ();
    end

    // Preserve one interface while selecting enable behavior at elaboration.
    logic functional_enable;
    if (HAS_ENABLE == 1) begin : gen_enable
        assign functional_enable = i_enable;
    end else begin : gen_no_enable
        // This pin remains part of the interface but does not control capture.
        wire unused_enable = i_enable;
        assign functional_enable = 1'b1;
    end

    if (WIDTH >= 1 && (((^RESET_VALUE == 1'b0) || (^RESET_VALUE == 1'b1)) === 1'b1) &&
        (ASYNC_RESET === 0 || ASYNC_RESET === 1) &&
        (HAS_ENABLE === 0 || HAS_ENABLE === 1)) begin : gen_model
        if (ASYNC_RESET == 1) begin : gen_async_reset
            always_ff @(posedge i_clk or negedge i_rstb) begin
                case (i_rstb)
                    1'b0: begin
                        o_q <= RESET_VALUE;
                        retained_image <= RESET_VALUE;
                    end
                    1'b1: begin
                        // Unknown power-management controls invalidate the
                        // portable context instead of silently choosing hold.
                        if (^{i_save, i_restore} === 1'bx) begin
                            o_q <= 'x;
                            retained_image <= 'x;
                        end else if (i_restore) begin
                            o_q <= retained_image;
                        end else if (i_save) begin
                            retained_image <= o_q;
                        end else begin
                            case (functional_enable)
                                1'b1: o_q <= i_d;
                                1'b0: begin end
                                // Unknown functional enable cannot modify
                                // the saved image, only visible state.
                                default: o_q <= 'x;
                            endcase
                        end
                    end
                    default: begin
                        o_q <= 'x;
                        retained_image <= 'x;
                    end
                endcase
            end
        end else begin : gen_sync_reset
            always_ff @(posedge i_clk) begin
                case (i_rstb)
                    1'b0: begin
                        o_q <= RESET_VALUE;
                        retained_image <= RESET_VALUE;
                    end
                    1'b1: begin
                        if (^{i_save, i_restore} === 1'bx) begin
                            o_q <= 'x;
                            retained_image <= 'x;
                        end else if (i_restore) begin
                            o_q <= retained_image;
                        end else if (i_save) begin
                            retained_image <= o_q;
                        end else begin
                            case (functional_enable)
                                1'b1: o_q <= i_d;
                                1'b0: begin end
                                default: o_q <= 'x;
                            endcase
                        end
                    end
                    default: begin
                        o_q <= 'x;
                        retained_image <= 'x;
                    end
                endcase
            end
        end
    end
endmodule
