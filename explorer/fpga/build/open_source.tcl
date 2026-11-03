set base [file dirname [file normalize [info script]]]
open_project [file join $base KR260_PL_CAN_SWITCH.xpr]
set_property ip_repo_paths [list [file join $base third_party ctucanfd src]] [current_project]
update_ip_catalog
set_property STEPS.INIT_DESIGN.TCL.PRE [file join $base implementation_threads_retry.tcl] [get_runs impl_1]
set_property STEPS.OPT_DESIGN.TCL.PRE [file join $base implementation_prepare.tcl] [get_runs impl_1]
set_property STEPS.PLACE_DESIGN.TCL.PRE [file join $base implementation_threads_stable.tcl] [get_runs impl_1]
update_compile_order -fileset sources_1
puts SOURCE_PACKAGE_OPEN_PASS
