# =============================================================
# run.tcl
# Standalone synthesis in Design Compiler
# =============================================================
# Invoked by make synth. The Makefile exports the MOSAIC_SYNTH_* inputs and
# runs DC from SYNTH_BUILD so intermediate files stay with the selected top.
# RTL, technology libraries, and the optional setup scripts are inputs;
# reports and mapped design handoff files are written under SYNTH_BUILD.
#
# Main environment inputs, mapped from Make options:
#   MOSAIC_SYNTH_TOP          COCOTB_TOPLEVEL: module to elaborate and map.
#   MOSAIC_SYNTH_RTL          VERILOG_SOURCES: ordered Tcl list of RTL paths.
#   MOSAIC_SYNTH_INCLUDES     VERILOG_INCLUDE_DIRS: Tcl list of include paths.
#   MOSAIC_SYNTH_TECH_SETUP   TECH_SETUP_TCL: required technology setup.
#   MOSAIC_SYNTH_DC_SETUP     DC_SETUP_TCL: optional DC-specific setup.
#   MOSAIC_SYNTH_BUILD        SYNTH_BUILD: directory for all generated files.
# Other MOSAIC_SYNTH_* inputs configure constraints, clock port/period,
# elaboration parameters, CPU count, and additional compile options.

# Catch errors across the entire flow and return a failing batch exit code.
# The Makefile also checks that each required handoff file is nonempty.
if {[catch {

# ----------- Base paths -----------
# Locate the repository from this script, independently of DC's working
# directory. Keep generated files in the build directory supplied by Make.
set SCRIPT_DIR          [file dirname [file normalize [info script]]]
set PROJECT_HOME        [file normalize "$SCRIPT_DIR/../.."]
set PROJECT_HOME_SYN    $::env(MOSAIC_SYNTH_BUILD)

# ----------- Design -----------
# Use the top name consistently for elaboration, reports, and output names.
set DESIGN_NAME $::env(MOSAIC_SYNTH_TOP)
set TOP_MODULE  $::env(MOSAIC_SYNTH_TOP)

# ----------- RTL -----------
# The Makefile supplies absolute paths in VERILOG_SOURCES order.
# Preserve that order because SystemVerilog packages must precede consumers.
# Reject missing sources before performing any analysis or optimization.
set RTL_FILES $::env(MOSAIC_SYNTH_RTL)
if {[llength $RTL_FILES] == 0} { error "No RTL files specified." }
foreach rtl $RTL_FILES {
    if {![file readable $rtl]} { error "RTL file not readable: $rtl" }
}

# ----------- Technology setup -----------
# Technology and DC setup files remain on the server.
# Source the library setup first, then allow DC_SETUP_TCL to extend it.
# target_library selects mapping cells; link_library resolves referenced
# designs, standard cells, and macros. The setup must include all needed .dbs.
source $::env(MOSAIC_SYNTH_TECH_SETUP)
if {$::env(MOSAIC_SYNTH_DC_SETUP) ne ""} {
    source $::env(MOSAIC_SYNTH_DC_SETUP)
}
if {![info exists target_library] || [llength $target_library] == 0} {
    error "TECH_SETUP_TCL must configure target_library with technology .db libraries."
}
if {![info exists link_library] || [llength $link_library] == 0} {
    # The literal * also searches designs already loaded in the DC session.
    set_app_var link_library [concat [list *] $target_library]
}
# Extend the site's search paths instead of replacing library locations.
set_app_var search_path [concat $search_path $::env(MOSAIC_SYNTH_INCLUDES)]

# ----------- Create directories -----------
# WORK stores analyzed HDL; DDC stores the mapped design; SVF records
# transformations for a downstream formal equivalence flow.
file mkdir $PROJECT_HOME_SYN/reports
file mkdir $PROJECT_HOME_SYN/db
file mkdir $PROJECT_HOME_SYN/netlist
file mkdir $PROJECT_HOME_SYN/work
define_design_lib WORK -path $PROJECT_HOME_SYN/work
set_svf $PROJECT_HOME_SYN/db/${DESIGN_NAME}.svf

# ----------- Debug -----------
# Record the resolved inputs in dc.log to diagnose server setup mismatches.
puts "==========================================="
puts "PROJECT_HOME      = $PROJECT_HOME"
puts "PROJECT_HOME_SYN  = $PROJECT_HOME_SYN"
puts "TOP_MODULE        = $TOP_MODULE"
puts "DESIGN_NAME       = $DESIGN_NAME"
puts "RTL_FILES         = $RTL_FILES"
puts "target_library    = $target_library"
puts "link_library      = $link_library"
puts "==========================================="

# =============================================================
# Read / Elaborate
# =============================================================
# analyze parses the ordered RTL into WORK; elaborate builds the selected
# module using its defaults or the supplied DC parameter override string.
if {![analyze -library WORK -format sverilog $RTL_FILES]} {
    error "RTL analysis failed."
}
if {$::env(MOSAIC_SYNTH_PARAMETERS) ne ""} {
    elaborate $TOP_MODULE -parameters $::env(MOSAIC_SYNTH_PARAMETERS)
} else {
    elaborate $TOP_MODULE
}

# Parameter overrides cause DC to create a specialized design name, for
# example bct_DATA_WIDTH2. Track the design selected by elaborate instead of
# assuming that the original module name remains in WORK.
set ELABORATED_DESIGN [get_object_name [current_design]]

# Verify that the top exists.
if {$ELABORATED_DESIGN eq "" ||
        [sizeof_collection [get_designs $ELABORATED_DESIGN]] == 0} {
    puts "ERROR: TOP_MODULE '$TOP_MODULE' did not produce an elaborated design."
    list_designs
    error "Elaborated design does not exist for: $TOP_MODULE"
}

puts "ELABORATED_DESIGN = $ELABORATED_DESIGN"
current_design $ELABORATED_DESIGN
# Give shared subdesign instances independent copies before optimization,
# then resolve references against the designs and libraries in link_library.
uniquify
if {![link]} { error "Link failed; check the technology libraries." }

# =============================================================
# Preliminary checks
# =============================================================
# Validate the elaborated design before optimization and keep its diagnostics.
# Capture the command status inside redirect; redirection itself returns "".
redirect -file "$PROJECT_HOME_SYN/reports/${DESIGN_NAME}_check_design.rpt" {
    set design_ok [check_design]
}
if {!$design_ok} { error "Pre-synthesis check_design failed." }
report_reference > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_reference.rpt
report_design    > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_design.rpt

# =============================================================
# Constraints
# =============================================================
# Pass the synthesis settings to the shared SDC's flow-independent interface.
# CLOCK_PERIOD uses the technology library's time unit. A custom SDC replaces
# the shared budget, for example for multiple clocks or a combinational top.
set CLOCK_PORT   $::env(MOSAIC_SYNTH_CLOCK_PORT)
set CLOCK_PERIOD $::env(MOSAIC_SYNTH_CLOCK_PERIOD)
if {$::env(MOSAIC_SYNTH_CONSTRAINTS) ne ""} {
    source $::env(MOSAIC_SYNTH_CONSTRAINTS)
} else {
    source $PROJECT_HOME/src/constraints/timing.sdc
}

# Request separate port connections and buffered constants during compilation
# so the mapped netlist is easier for downstream tools to consume.
set_fix_multiple_port_nets -all -buffer_constants

# =============================================================
# Compile
# =============================================================
# Use the reference command if the environment provides it;
# Design Compiler documents set_host_options for core configuration.
if {[llength [info commands set_multi_cpu_usage]] > 0} {
    set_multi_cpu_usage -num_cpus $::env(MOSAIC_SYNTH_CPUS)
} else {
    set_host_options -max_cores $::env(MOSAIC_SYNTH_CPUS)
}
set_leakage_optimization true
# The compile passes can insert latch-based clock gating and move registers
# through retiming. Simulation tests must match the resulting design behavior.
set_clock_gating_style -sequential_cell latch -control_point before

# Pass 1 - timing-focused full compile
# Expand the extra options as a Tcl list, preserving individual arguments.
if {![compile_ultra -gate_clock -retime {*}$::env(MOSAIC_SYNTH_COMPILE_ARGS)]} {
    error "First compile_ultra pass failed."
}

# Pass 2 - leakage optimization, then incremental timing fix
# Some server environments provide optimize_leakage as an extra command.
# Otherwise the enabled leakage optimization is handled by compile_ultra.
if {[llength [info commands optimize_leakage]] > 0} {
    optimize_leakage
} else {
    puts "INFO: optimize_leakage is unavailable; leakage is optimized during compile_ultra."
}
if {![compile_ultra -gate_clock -retime -incremental {*}$::env(MOSAIC_SYNTH_COMPILE_ARGS)]} {
    error "Incremental compile_ultra pass failed."
}
# Recheck the optimized design before exporting any downstream handoff files.
redirect -file "$PROJECT_HOME_SYN/reports/${DESIGN_NAME}_check_design_post.rpt" {
    set design_ok [check_design]
}
if {!$design_ok} { error "Post-synthesis check_design failed." }

# =============================================================
# Reports
# =============================================================
# Preserve QoR, area, timing, and constraint diagnostics for budget review.
# This flow does not import test activity, so its power report uses estimated
# activity. flows/power/run.tcl consumes the gate simulation's SAIF for test power.
report_qor             > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_qor.rpt
report_area            > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_area.rpt
report_area -hierarchy > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_area_hier.rpt
report_timing -max_paths 10 > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_timing.rpt
report_power           > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_power.rpt
report_resources       > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_resources.rpt
report_constraint -all_violators > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_constraints.rpt
if {[llength [info commands report_units]] > 0} {
    report_units > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_units.rpt
}

# =============================================================
# Outputs
# =============================================================
# Keep names consistent between the netlist and SDF.
# Normalize names once before writing every handoff from the same design.
# DDC is the native DC database; Verilog is consumed by gate simulation;
# SDC carries constraints; SDF carries synthesis delay estimates. Post-route
# simulation and power analysis use matching outputs from implementation.
change_names -rules verilog -hierarchy
write -hierarchy -format ddc -output $PROJECT_HOME_SYN/db/${DESIGN_NAME}.ddc
write -hierarchy -format verilog -output $PROJECT_HOME_SYN/netlist/${DESIGN_NAME}_syn.v
write_sdc $PROJECT_HOME_SYN/netlist/${DESIGN_NAME}.sdc
write_sdf $PROJECT_HOME_SYN/netlist/${DESIGN_NAME}.sdf
# Close the formal guidance stream before a successful batch exit.
set_svf -off

} message]} {
    # A tool/Tcl failure must stop make synth rather than accept partial files.
    puts stderr "Synthesis failed: $message"
    exit 1
}
# End the batch session instead of opening an interactive DC prompt.
quit
