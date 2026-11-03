set root [file dirname [info script]]
set f [open [file join $root delivery reports lifecycle_ila_routed.txt] w]
foreach n {0 1} {
 for {set b 0} {$b<512} {incr b} {
  same_net [format {VCU_INIT_i/can_path%d/debug_bus[%d]} $n $b] [format {VCU_INIT_i/ila_can_lifecycle%d/probe0[%d]} $n $b]
 }
 same_net VCU_INIT_i/zynq_ultra_ps_e_0/pl_clk0 VCU_INIT_i/ila_can_lifecycle$n/clk
 puts $f "PASS channel$n: all512 probe bits and PL0 clock connected"
}
puts $f "DEBUG_CORES [get_debug_cores]"
close $f
puts LIFECYCLE_ILA_ROUTED_PASS
