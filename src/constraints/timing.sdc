# =============================================================
# Shared single-clock timing constraints
# =============================================================
# Source this file after loading/linking the design and technology libraries.
# Set CLOCK_PORT, CLOCK_PERIOD, CLOCK_NAME, and OUTPUT_LOAD before sourcing
# to override the defaults. No synthesis-specific environment is required.
# Time and capacitance values use the loaded technology library's units.

if {![info exists CLOCK_PORT]}   { set CLOCK_PORT i_clk }
if {![info exists CLOCK_PERIOD]} { set CLOCK_PERIOD 4.0 }
if {![info exists CLOCK_NAME]}   { set CLOCK_NAME CLK }
if {![info exists OUTPUT_LOAD]}  { set OUTPUT_LOAD 0.04 }

# Apply the sequential budget only when the design has the selected clock.
# Combinational designs can supply a separate constraint file.
set clock_ports [get_ports -quiet $CLOCK_PORT]
if {[sizeof_collection $clock_ports] > 0} {
    if {![string is double -strict $CLOCK_PERIOD] || $CLOCK_PERIOD <= 0} {
        error "CLOCK_PERIOD must be positive."
    }
    if {![string is double -strict $OUTPUT_LOAD] || $OUTPUT_LOAD < 0} {
        error "OUTPUT_LOAD must be nonnegative."
    }

    # Default budget: 4 ns -> 250 MHz for libraries with ns time units.
    create_clock -name $CLOCK_NAME -period $CLOCK_PERIOD $clock_ports

    # Clock setup uncertainty 5%; hold uncertainty 2%.
    set_clock_uncertainty -setup [expr {$CLOCK_PERIOD * 0.05}] [get_clocks $CLOCK_NAME]
    set_clock_uncertainty -hold [expr {$CLOCK_PERIOD * 0.02}] [get_clocks $CLOCK_NAME]

    # Clock transition 2%.
    set_clock_transition -max [expr {$CLOCK_PERIOD * 0.02}] [get_clocks $CLOCK_NAME]

    # Clock source latency from 2% to 5%.
    set_clock_latency -source -min [expr {$CLOCK_PERIOD * 0.02}] [get_clocks $CLOCK_NAME]
    set_clock_latency -source -max [expr {$CLOCK_PERIOD * 0.05}] [get_clocks $CLOCK_NAME]

    # Clock network latency from 1% to 2%.
    set_clock_latency -min [expr {$CLOCK_PERIOD * 0.01}] [get_clocks $CLOCK_NAME]
    set_clock_latency -max [expr {$CLOCK_PERIOD * 0.02}] [get_clocks $CLOCK_NAME]

    # Input delay from 5% to 20%; exclude the clock port.
    set inputs [remove_from_collection [all_inputs] $clock_ports]
    if {[sizeof_collection $inputs] > 0} {
        set_input_delay -min [expr {$CLOCK_PERIOD * 0.05}] -clock $CLOCK_NAME $inputs
        set_input_delay -max [expr {$CLOCK_PERIOD * 0.20}] -clock $CLOCK_NAME $inputs
    }

    # Output delay from 0% to 15%.
    set outputs [all_outputs]
    if {[sizeof_collection $outputs] > 0} {
        set_output_delay -min 0 -clock $CLOCK_NAME $outputs
        set_output_delay -max [expr {$CLOCK_PERIOD * 0.15}] -clock $CLOCK_NAME $outputs

        # Maximum output transition 5%.
        set_max_transition [expr {$CLOCK_PERIOD * 0.05}] $outputs

        # Output load: 0.04 by default (pF if the library uses pF).
        set_load -max $OUTPUT_LOAD $outputs
    }

    # Input transition from 1% to 5%.
    if {[sizeof_collection $inputs] > 0} {
        set_input_transition -min [expr {$CLOCK_PERIOD * 0.01}] $inputs
        set_input_transition -max [expr {$CLOCK_PERIOD * 0.05}] $inputs
    }
}
