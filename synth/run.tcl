# =============================================================
# run.tcl
# Standalone synthesis in Design Compiler
# =============================================================

# Propagate Tcl errors to the Makefile.
if {[catch {

# ----------- Base paths -----------
set SCRIPT_DIR          [file dirname [file normalize [info script]]]
set PROJECT_HOME        [file normalize "$SCRIPT_DIR/.."]
set PROJECT_HOME_SYN    $::env(MOSAIC_SYNTH_BUILD)

# ----------- Design -----------
set DESIGN_NAME $::env(MOSAIC_SYNTH_TOP)
set TOP_MODULE  $::env(MOSAIC_SYNTH_TOP)

# ----------- RTL -----------
# The Makefile supplies absolute paths in VERILOG_SOURCES order.
set RTL_FILES $::env(MOSAIC_SYNTH_RTL)
if {[llength $RTL_FILES] == 0} { error "No RTL files specified." }
foreach rtl $RTL_FILES {
    if {![file readable $rtl]} { error "RTL file not readable: $rtl" }
}

# ----------- Technology setup -----------
# Technology and DC setup files remain on the server.
source $::env(MOSAIC_SYNTH_TECH_SETUP)
if {$::env(MOSAIC_SYNTH_DC_SETUP) ne ""} {
    source $::env(MOSAIC_SYNTH_DC_SETUP)
}
if {![info exists target_library] || [llength $target_library] == 0} {
    error "TECH_SETUP_TCL must configure target_library with technology .db libraries."
}
if {![info exists link_library] || [llength $link_library] == 0} {
    set_app_var link_library [concat [list *] $target_library]
}
set_app_var search_path [concat $search_path $::env(MOSAIC_SYNTH_INCLUDES)]

# ----------- Create directories -----------
file mkdir $PROJECT_HOME_SYN/reports
file mkdir $PROJECT_HOME_SYN/db
file mkdir $PROJECT_HOME_SYN/netlist
file mkdir $PROJECT_HOME_SYN/work
define_design_lib WORK -path $PROJECT_HOME_SYN/work
set_svf $PROJECT_HOME_SYN/db/${DESIGN_NAME}.svf

# ----------- Debug -----------
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
if {![analyze -library WORK -format sverilog $RTL_FILES]} {
    error "RTL analysis failed."
}
if {$::env(MOSAIC_SYNTH_PARAMETERS) ne ""} {
    elaborate $TOP_MODULE -parameters $::env(MOSAIC_SYNTH_PARAMETERS)
} else {
    elaborate $TOP_MODULE
}

# Verify that the top exists.
if {[sizeof_collection [get_designs $TOP_MODULE]] == 0} {
    puts "ERROR: TOP_MODULE '$TOP_MODULE' was not elaborated correctly."
    list_designs
    error "Design does not exist: $TOP_MODULE"
}

current_design $TOP_MODULE
uniquify
if {![link]} { error "Link failed; check the technology libraries." }

# =============================================================
# Preliminary checks
# =============================================================
set design_ok [check_design > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_check_design.rpt]
if {!$design_ok} { error "Pre-synthesis check_design failed." }
report_reference > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_reference.rpt
report_design    > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_design.rpt

# =============================================================
# Constraints
# =============================================================
# Pass the synthesis settings to the shared SDC's flow-independent interface.
set CLOCK_PORT   $::env(MOSAIC_SYNTH_CLOCK_PORT)
set CLOCK_PERIOD $::env(MOSAIC_SYNTH_CLOCK_PERIOD)
if {$::env(MOSAIC_SYNTH_CONSTRAINTS) ne ""} {
    source $::env(MOSAIC_SYNTH_CONSTRAINTS)
} else {
    source $PROJECT_HOME/constraints/timing.sdc
}

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
set_clock_gating_style -sequential_cell latch -control_point before

# Pass 1 - timing-focused full compile
if {![compile_ultra -gate_clock -retime {*}$::env(MOSAIC_SYNTH_COMPILE_ARGS)]} {
    error "First compile_ultra pass failed."
}

# Pass 2 - leakage optimization, then incremental timing fix
if {[llength [info commands optimize_leakage]] > 0} {
    optimize_leakage
} else {
    puts "INFO: optimize_leakage is unavailable; leakage is optimized during compile_ultra."
}
if {![compile_ultra -gate_clock -retime -incremental {*}$::env(MOSAIC_SYNTH_COMPILE_ARGS)]} {
    error "Incremental compile_ultra pass failed."
}
set design_ok [check_design > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_check_design_post.rpt]
if {!$design_ok} { error "Post-synthesis check_design failed." }

# =============================================================
# Reports
# =============================================================
report_qor             > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_qor.rpt
report_area            > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_area.rpt
report_area -hierarchy > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_area_hier.rpt
report_timing -max_paths 10 > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_timing.rpt
report_power           > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_power.rpt
report_resources       > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_resources.rpt
report_constraint -all_violators > $PROJECT_HOME_SYN/reports/${DESIGN_NAME}_constraints.rpt

# =============================================================
# Outputs
# =============================================================
# Keep names consistent between the netlist and SDF.
change_names -rules verilog -hierarchy
write -hierarchy -format ddc -output $PROJECT_HOME_SYN/db/${DESIGN_NAME}.ddc
write -hierarchy -format verilog -output $PROJECT_HOME_SYN/netlist/${DESIGN_NAME}_syn.v
write_sdc $PROJECT_HOME_SYN/netlist/${DESIGN_NAME}.sdc
write_sdf $PROJECT_HOME_SYN/netlist/${DESIGN_NAME}.sdf
set_svf -off

} message]} {
    puts stderr "Synthesis failed: $message"
    exit 1
}
quit
