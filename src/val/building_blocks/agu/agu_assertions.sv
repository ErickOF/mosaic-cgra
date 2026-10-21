`timescale 1ns / 1ps

// Port-only simulation checker. History advances on real handshakes; the
// closed-form address equation does not reuse DUT recurrence or range logic.
// The one-precision-tick delay observes post-NBA state in zero-delay RTL only.
module agu_assertions #(
    parameter int W=32, C=16, E=3, S=2, H=4, T=8, ASYNC_RESET=0,
    localparam int M=E+S+H+T+2,
    localparam int A=W+2*C+3
) (
    input logic i_clk,i_rstb,i_error_clear,i_config_valid,o_config_ready,
    input logic [1:0] i_mode,
    input logic [W-1:0] i_base_address,i_inner_stride,i_outer_stride,
    input logic [C-1:0] i_inner_count,i_outer_count,
    input logic [E-1:0] i_element_size_log2,
    input logic i_is_write,
    input logic [S-1:0] i_address_space,
    input logic [H-1:0] i_channel_id,
    input logic [T-1:0] i_context_id,
    input logic i_emit_end_of_stream,o_valid,i_ready,
    input logic [W-1:0] o_address,
    input logic [C-1:0] o_inner_index,o_outer_index,
    input logic o_first,o_last,o_row_first,o_row_last,o_end_of_stream,
    input logic [E-1:0] o_element_size_log2,
    input logic o_is_write,
    input logic [S-1:0] o_address_space,
    input logic [H-1:0] o_channel_id,
    input logic [T-1:0] o_context_id,
    input logic o_idle,o_active,o_descriptor_started,o_address_accepted,o_completed,
    input logic [2*C-1:0] o_addresses_accepted,
    input logic o_error,
    input logic [3:0] o_error_code
);
    logic initialized=0, expected_active;
    logic [2*C-1:0] accepted;
    logic [C-1:0] inner_count,outer_count;
    logic [M-1:0] captured_metadata;
    logic signed [A-1:0] base,inner_step,outer_step,expected_address,next_address;
    logic [2*C-1:0] row,column,next_row,next_column;
    logic config_event,address_event,final_event,clear_event;
    logic [3:0] previous_error;
    logic [M-1:0] input_metadata;
    logic [W-1:0] configured_base;
    logic [C-1:0] configured_inner_count,configured_outer_count;
    logic signed [A-1:0] configured_inner_step,configured_outer_step;

    task automatic check_edge;
        if (i_rstb===1'b0) begin
            initialized=1;expected_active=0;accepted='0;
            #1ps;
            assert ({o_active,o_valid,o_error,o_error_code,o_addresses_accepted,
                o_descriptor_started,o_address_accepted,o_completed}==='0)
                else $fatal(1,"AGU HDL assertion: reset state");
        end else if (initialized) begin
            assert ((i_rstb===1'b1) && (^{i_config_valid,i_error_clear}!==1'bx))
                else $fatal(1,"AGU HDL assertion: known controls");
            config_event=o_config_ready && i_config_valid;
            address_event=o_valid && (i_ready===1'b1);
            final_event=address_event && o_last;
            clear_event=!o_active && i_error_clear;
            previous_error=o_error_code;
            assert (o_valid===expected_active && o_active===expected_active)
                else $fatal(1,"AGU HDL assertion: active lifetime");
            if (expected_active) begin
                row=accepted/(2*C)'(inner_count);
                column=accepted%(2*C)'(inner_count);
                expected_address=base+$signed(A'(row))*outer_step+$signed(A'(column))*inner_step;
                assert ((A'({1'b0,o_address})===expected_address) &&
                    (o_inner_index===C'(column)) && (o_outer_index===C'(row)))
                    else $fatal(1,"AGU HDL assertion: address equation and indices");
                assert ((o_first===(accepted=='0)) && (o_row_first===(column=='0)) &&
                    (o_row_last===(column==(2*C)'(inner_count)-1'b1)) &&
                    (o_last===((column==(2*C)'(inner_count)-1'b1) && (row==(2*C)'(outer_count)-1'b1))))
                    else $fatal(1,"AGU HDL assertion: markers");
                assert ({o_element_size_log2,o_is_write,o_address_space,o_channel_id,
                    o_context_id,o_end_of_stream}==={captured_metadata[M-1:1],(o_last && captured_metadata[0])})
                    else $fatal(1,"AGU HDL assertion: captured metadata");
                assert ((o_address & (W'(1 << o_element_size_log2)-1'b1))=='0)
                    else $fatal(1,"AGU HDL assertion: alignment");
            end
            if (config_event) begin
                configured_base=i_base_address;
                configured_inner_count=i_inner_count;configured_outer_count=i_outer_count;
                configured_inner_step=(i_mode==0) ? (A'(1) << i_element_size_log2) : A'($signed(i_inner_stride));
                configured_outer_step=(i_mode==2) ? A'($signed(i_outer_stride)) : '0;
                input_metadata={i_element_size_log2,i_is_write,i_address_space,i_channel_id,i_context_id,i_emit_end_of_stream};
                accepted='0;
            end else if (clear_event) accepted='0;
            else if (address_event) begin
                accepted=accepted+1'b1;
                if (final_event) expected_active=0;
                else begin
                    next_row=accepted/(2*C)'(inner_count);next_column=accepted%(2*C)'(inner_count);
                    next_address=base+$signed(A'(next_row))*outer_step+$signed(A'(next_column))*inner_step;
                    if ((next_address<0) || (next_address>$signed({{(A-W){1'b0}},{W{1'b1}}})))
                        expected_active=0;
                end
            end
            #1ps;
            if (config_event && o_descriptor_started) begin
                base=$signed({{(A-W){1'b0}},configured_base});
                inner_count=configured_inner_count;outer_count=configured_outer_count;
                inner_step=configured_inner_step;outer_step=configured_outer_step;
                captured_metadata=input_metadata;expected_active=1;
            end
            assert (o_addresses_accepted===accepted && o_address_accepted===address_event
                && o_completed===final_event && o_valid===expected_active && o_active===expected_active)
                else $fatal(1,"AGU HDL assertion: handshake history");
            assert (!o_completed || (!o_error && !o_valid))
                else $fatal(1,"AGU HDL assertion: completion exclusivity");
            if (previous_error!=0 && !clear_event)
                assert (o_error_code===previous_error && !o_config_ready && !o_valid)
                    else $fatal(1,"AGU HDL assertion: sticky first error");
            assert (o_idle===(!o_active && !o_error))
                else $fatal(1,"AGU HDL assertion: idle qualification");
        end
    endtask
    if (ASYNC_RESET) begin : g_async
        always @(posedge i_clk or negedge i_rstb) check_edge();
    end else begin : g_sync
        always @(posedge i_clk) check_edge();
    end
endmodule
