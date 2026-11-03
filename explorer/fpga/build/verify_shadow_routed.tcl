set root [file dirname [info script]]
set fh [open [file join $root delivery reports shadow_isolation.txt] w]
proc same_net {a b} {
 set an [get_nets -segments -of_objects [get_pins $a]]
 set bn [get_nets -segments -of_objects [get_pins $b]]
 if {![llength $an] || ![llength $bn]} {error "MISSING_NET $a $b"}
 foreach x $an {if {[lsearch -exact $bn $x]>=0} {return 1}}
 error "NET_MISMATCH $a $b"
}
set sh VCU_INIT_i/pl_shadow_0
set outputs [get_pins -of_objects [get_cells $sh] -filter {DIRECTION == OUT}]
if {![llength $outputs]} {error "SHADOW_CELL_OUTPUTS_MISSING"}
foreach p $outputs {
 set leaf [get_property REF_PIN_NAME $p]
 if {![string match s_axi_* $leaf]} {error "UNEXPECTED_SHADOW_OUTPUT $p"}
}
puts $fh "PASS: shadow outputs only AXI-Lite response/handshake pins ([llength $outputs] bits)"
foreach port {2 3} {
 foreach field {valid ready last keep} {
  set width [expr {$field eq "keep" ? 4 : 1}]
  for {set b 0} {$b<$width} {incr b} {
    set suffix [expr {$width==1 ? "" : [format {[%d]} $b]}]
    foreach dir {tx rx} {
      set dma [expr {$dir eq "tx" ? "m_axis_mm2s_t${field}" : "s_axis_s2mm_t${field}"}]
      set buf [expr {$dir eq "tx" ? "AXI_STR_TXD_T[string toupper $field]" : "AXI_STR_RXD_[string toupper $field]"}]
      same_net VCU_INIT_i/eth_dma${port}/${dma}${suffix} VCU_INIT_i/pl_eth${port}/eth_buf/${buf}${suffix}
      same_net VCU_INIT_i/eth_dma${port}/${dma}${suffix} ${sh}/${dir}${port}_${field}${suffix}
      puts $fh "PASS eth$port $dir $field$suffix original endpoints and monitor share net"
    }
  }
 }
}
foreach c {0 1} {foreach d {rx tx} {
 same_net VCU_INIT_i/can_io_observer_0/can${c}_${d}_raw ${sh}/can${c}_${d}_raw
 puts $fh "PASS CAN$c $d original observer and passive monitor share net"
}}
same_net VCU_INIT_i/zynq_ultra_ps_e_0/pl_clk0 ${sh}/s_axi_aclk
same_net VCU_INIT_i/eth_clock/clk_out1 ${sh}/eth_clk
same_net VCU_INIT_i/proc_sys_reset_0/peripheral_aresetn ${sh}/s_axi_aresetn
puts $fh "PASS clocks/reset input connection"
close $fh
report_utilization -hierarchical -file [file join $root delivery reports utilization_hier.rpt]
report_utilization -file [file join $root delivery reports utilization.rpt]
puts "SHADOW_ISOLATION_PASS"
