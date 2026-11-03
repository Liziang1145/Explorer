set root [file dirname [info script]]
file mkdir [file join $root delivery reports]
foreach script {verify_can_io.tcl verify_pin_migration.tcl verify_shadow_routed.tcl verify_shadow_cdc.tcl verify_can_switch_cdc.tcl verify_final_routed.tcl verify_lifecycle_ila.tcl} {source [file join $root $script]}
report_utilization -file [file join $root delivery reports final_utilization.rpt]
set f [open [file join $root delivery reports timing_gate.txt] w]
foreach kind {max min} {
 set p [get_timing_paths -delay_type $kind -max_paths 1]
 if {[llength $p]!=1} {error "TIMING_PATH_MISSING $kind"}
 set slack [get_property SLACK $p]
 puts $f "$kind slack=$slack"
 if {$slack<0} {error "TIMING_GATE_FAILED $kind $slack"}
}
close $f
puts {FINAL_CAN_SWITCH_CONNECTION_AND_TIMING_GATES_PASS}
