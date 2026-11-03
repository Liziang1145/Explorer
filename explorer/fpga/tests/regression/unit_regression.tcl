set root D:/2026FPGArace/KR260_PL_CAN_FIX_20261103
close_sim
set f [open $root/evidence/unit_regression.txt w]
foreach {top modules duration} {tb_can_owner {can_path_owner.v} 1ms tb_arm_queue {arm_command_engine.v} 10ms tb_can_axil {can_axil_endpoint.v} 1ms tb_shadow {pl_shadow.v can_passive_monitor.v pl_stream_monitor.v} 20ms} {
 set fs unit_$top
 create_fileset -simset $fs
 set_property SOURCE_SET {} [get_filesets $fs]
 foreach m $modules {add_files -fileset $fs $root/rtl/$m}
 add_files -fileset $fs $root/tests/$top.sv
 set_property top $top [get_filesets $fs]
 set_property xsim.simulate.runtime 0ns [get_filesets $fs]
 launch_simulation -simset $fs -mode behavioral
 run $duration
 set p [get_value -radix unsigned /$top/test_pass]
 puts $f "$top pass=$p checks=[get_value -radix unsigned /$top/checks]"
 flush $f
 if {$p!=1} {close $f;error "TEST_FAILED $top"}
 close_sim
}
close $f
puts UNIT_REGRESSION_PASS
