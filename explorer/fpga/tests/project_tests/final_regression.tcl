set root [file normalize [file join [file dirname [info script]] ..]]
if {![llength [get_filesets -quiet sim_shadow_regression]]} {create_fileset -simset sim_shadow_regression}
set_property SOURCE_SET {} [get_filesets sim_shadow_regression]
add_files -fileset sim_shadow_regression [list [file join $root rtl pl_shadow.v] [file join $root rtl can_passive_monitor.v] [file join $root rtl pl_stream_monitor.v] [file join $root tests tb_shadow.sv]]
set_property top tb_shadow [get_filesets sim_shadow_regression]
set_property xsim.simulate.runtime 0ns [get_filesets sim_shadow_regression]
set report [open [file join $root evidence final_simulation.txt] w]
foreach {fs top duration} {sim_can_owner tb_can_owner 1ms sim_arm_queue tb_arm_queue 10ms sim_shadow_regression tb_shadow 20ms sim_can_actual tb_can_actual 19ms} {
 current_fileset -simset [get_filesets $fs]
 launch_simulation -simset $fs -mode behavioral
 run $duration
 set passed [get_value -radix unsigned /$top/test_pass]
 set checks [get_value -radix unsigned /$top/checks]
 puts $report "$top passed=$passed checks=$checks"
 flush $report
 if {$passed!=1} {close $report;error "REGRESSION_FAILED $top"}
 close_sim
}
close $report
puts {ALL_CAN_SWITCH_REGRESSIONS_PASS}
