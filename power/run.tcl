# =============================================================
# run.tcl
# Simulation-driven average power analysis in PrimeTime PX/PrimePower
# =============================================================
# Invoked by make power-report, either directly on an existing gate SAIF or
# after make power runs the selected PyUVM test with VCS. This driver loads
# the simulated netlist, annotates its activity, and writes average power.
# power/summarize.py then combines that report with the SAIF capture duration
# to calculate interval energy in joules.
#
# Environment inputs exported by Make:
#   MOSAIC_POWER_TOP          Module name in the simulation netlist.
#   MOSAIC_POWER_NETLIST      Same mapped/post-route netlist used by VCS.
#   MOSAIC_POWER_TECH_SETUP   Required .db library and search-path setup.
#   MOSAIC_POWER_TOOL_SETUP   Optional PrimeTime setup; independent of DC.
#   MOSAIC_POWER_SDC          Constraints matching the analyzed design.
#   MOSAIC_POWER_SPEF         Extracted parasitics, or empty for an estimate.
#   MOSAIC_POWER_SAIF         Activity captured over the test interval.
#   MOSAIC_POWER_STRIP_PATH   SAIF hierarchy corresponding to the design root.
#   MOSAIC_POWER_BUILD        Directory containing reports and power.log.

# Convert tool/Tcl errors into a failing exit status for the Make target.
if {[catch {

# ----------- Paths and technology setup -----------
# All input paths are resolved by Make before the shell changes directory.
# Setup scripts run before design loading. The selected .db corner must
# contain timing, internal power, and leakage models for the mapped cells.
set DESIGN_NAME $::env(MOSAIC_POWER_TOP)
set BUILD_DIR   $::env(MOSAIC_POWER_BUILD)
file mkdir $BUILD_DIR/reports
source $::env(MOSAIC_POWER_TECH_SETUP)
if {$::env(MOSAIC_POWER_TOOL_SETUP) ne ""} {
    source $::env(MOSAIC_POWER_TOOL_SETUP)
}
if {![info exists link_library] || [llength $link_library] == 0} {
    if {![info exists target_library] || [llength $target_library] == 0} {
        error "Technology setup must configure link_library or target_library with power-characterized .db libraries."
    }
    # Reuse a DC-compatible target_library if no explicit link list is given.
    # The literal * includes designs already loaded in the tool session.
    set_app_var link_library [concat [list *] $target_library]
}
# Enable the power engine and select the statistical mode supported by SAIF.
# SAIF does not retain the event sequence needed for a peak-power waveform.
set_app_var power_enable_analysis true
set_app_var power_analysis_mode averaged
# Missing cell models must fail linking instead of becoming empty black boxes.
set_app_var link_create_black_boxes false
# Preserve the test's measured toggle rates; do not rescale to the SDC clock.
set_app_var power_enable_clock_scaling false

# =============================================================
# Read / Link
# =============================================================
# Analyze the netlist that produced the SAIF; loading RTL here would lose the
# mapped cell names and internal nets needed for gate activity annotation.
if {![read_verilog $::env(MOSAIC_POWER_NETLIST)]} { error "Netlist read failed." }
current_design $DESIGN_NAME
if {![link_design $DESIGN_NAME]} { error "Netlist link failed; check the technology libraries." }
if {![read_sdc $::env(MOSAIC_POWER_SDC)]} { error "Constraint read failed." }
# SPEF supplies extracted interconnect loads for a physical power analysis.
# SDF is used by the VCS timing simulation; it does not replace these loads.
if {$::env(MOSAIC_POWER_SPEF) ne ""} {
    if {![read_parasitics $::env(MOSAIC_POWER_SPEF)]} { error "Parasitic read failed." }
    report_annotated_parasitics > $BUILD_DIR/reports/parasitics.rpt
} else {
    puts "INFO: No SPEF supplied; this is a mapped-netlist power estimate."
}
# Compute timing and pin transitions before power lookup. Save timing checks
# so missing clocks, constraints, or other timing setup issues can be reviewed.
update_timing
check_timing -verbose > $BUILD_DIR/reports/check_timing.rpt

# =============================================================
# Activity / Power
# =============================================================
# The SAIF hierarchy at strip_path corresponds to the current design root.
# For a capture under tb/dut, stripping tb/dut maps the enclosed signal names
# onto this design. A mismatched scope can leave the design unannotated.
if {![read_saif $::env(MOSAIC_POWER_SAIF) -strip_path $::env(MOSAIC_POWER_STRIP_PATH)]} {
    error "SAIF read failed; check the activity hierarchy and netlist."
}
report_switching_activity > $BUILD_DIR/reports/activity.rpt
# Preserve the file annotation coverage before activity propagation. The
# Python summary rejects zero file-annotated nets; partial coverage still
# requires review because the tool can estimate activity for unmatched nets.
report_switching_activity -list_not_annotated > $BUILD_DIR/reports/activity_unannotated.rpt
# Combine annotated activity, library power models, and net loads. Internal
# plus switching power is dynamic power; adding leakage gives total power.
if {![update_power]} { error "Power update failed; check the power license and library models." }

# =============================================================
# Reports
# =============================================================
# Verbose output declares the units used by the numeric summary.
# Dynamic and leakage units can differ, so the Python summary normalizes
# components to watts before adding them. Retain hierarchy detail for review;
# the top-level summary already includes descendants and must not be summed
# again with their hierarchical totals.
report_power -verbose > $BUILD_DIR/reports/power.rpt
report_power -hierarchy > $BUILD_DIR/reports/power_hierarchy.rpt

} message]} {
    # Make removes old results first and cannot publish energy after this exit.
    puts stderr "Power analysis failed: $message"
    exit 1
}
# Exit the batch shell after all required power reports have been written.
exit
