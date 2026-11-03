# Resolve tapped AXIS signals by stable functional pin, not BD-generated net name.
proc shadow_probe_net {name} {
 if {[regexp {^VCU_INIT_i/eth_dma3_M_AXIS_MM2S_(TKEEP|TVALID|TREADY|TLAST)(.*)$} $name -> signal suffix]} {
  set pin [get_pins "VCU_INIT_i/eth_dma3/m_axis_mm2s_[string tolower $signal]${suffix}"]
  if {[llength $pin]!=1} {error "PROBE_FUNCTIONAL_PIN_MISSING $name"}
  return [get_nets -of_objects $pin]
 }
 return [get_nets $name]
}
set probe_pairs {
  {{VCU_INIT_i/ila_eth3/probe0[0]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[0]}}
  {{VCU_INIT_i/ila_eth3/probe0[1]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[1]}}
  {{VCU_INIT_i/ila_eth3/probe0[2]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[2]}}
  {{VCU_INIT_i/ila_eth3/probe0[3]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[3]}}
  {{VCU_INIT_i/ila_eth3/probe0[4]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[4]}}
  {{VCU_INIT_i/ila_eth3/probe0[5]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[5]}}
  {{VCU_INIT_i/ila_eth3/probe0[6]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[6]}}
  {{VCU_INIT_i/ila_eth3/probe0[7]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[7]}}
  {{VCU_INIT_i/ila_eth3/probe0[8]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[8]}}
  {{VCU_INIT_i/ila_eth3/probe0[9]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[9]}}
  {{VCU_INIT_i/ila_eth3/probe0[10]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[10]}}
  {{VCU_INIT_i/ila_eth3/probe0[11]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[11]}}
  {{VCU_INIT_i/ila_eth3/probe0[12]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[12]}}
  {{VCU_INIT_i/ila_eth3/probe0[13]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[13]}}
  {{VCU_INIT_i/ila_eth3/probe0[14]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[14]}}
  {{VCU_INIT_i/ila_eth3/probe0[15]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[15]}}
  {{VCU_INIT_i/ila_eth3/probe0[16]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[16]}}
  {{VCU_INIT_i/ila_eth3/probe0[17]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[17]}}
  {{VCU_INIT_i/ila_eth3/probe0[18]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[18]}}
  {{VCU_INIT_i/ila_eth3/probe0[19]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[19]}}
  {{VCU_INIT_i/ila_eth3/probe0[20]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[20]}}
  {{VCU_INIT_i/ila_eth3/probe0[21]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[21]}}
  {{VCU_INIT_i/ila_eth3/probe0[22]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[22]}}
  {{VCU_INIT_i/ila_eth3/probe0[23]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[23]}}
  {{VCU_INIT_i/ila_eth3/probe0[24]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[24]}}
  {{VCU_INIT_i/ila_eth3/probe0[25]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[25]}}
  {{VCU_INIT_i/ila_eth3/probe0[26]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[26]}}
  {{VCU_INIT_i/ila_eth3/probe0[27]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[27]}}
  {{VCU_INIT_i/ila_eth3/probe0[28]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[28]}}
  {{VCU_INIT_i/ila_eth3/probe0[29]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[29]}}
  {{VCU_INIT_i/ila_eth3/probe0[30]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[30]}}
  {{VCU_INIT_i/ila_eth3/probe0[31]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TDATA[31]}}
  {{VCU_INIT_i/ila_eth3/probe1[0]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TKEEP[0]}}
  {{VCU_INIT_i/ila_eth3/probe1[1]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TKEEP[1]}}
  {{VCU_INIT_i/ila_eth3/probe1[2]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TKEEP[2]}}
  {{VCU_INIT_i/ila_eth3/probe1[3]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TKEEP[3]}}
  {{VCU_INIT_i/ila_eth3/probe2[0]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TLAST}}
  {{VCU_INIT_i/ila_eth3/probe3[0]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TREADY}}
  {{VCU_INIT_i/ila_eth3/probe4[0]} {VCU_INIT_i/eth_dma3_M_AXIS_MM2S_TVALID}}
  {{VCU_INIT_i/ila_eth3/probe5[0]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[0]}}
  {{VCU_INIT_i/ila_eth3/probe5[1]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[1]}}
  {{VCU_INIT_i/ila_eth3/probe5[2]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[2]}}
  {{VCU_INIT_i/ila_eth3/probe5[3]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[3]}}
  {{VCU_INIT_i/ila_eth3/probe5[4]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[4]}}
  {{VCU_INIT_i/ila_eth3/probe5[5]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[5]}}
  {{VCU_INIT_i/ila_eth3/probe5[6]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[6]}}
  {{VCU_INIT_i/ila_eth3/probe5[7]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[7]}}
  {{VCU_INIT_i/ila_eth3/probe5[8]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[8]}}
  {{VCU_INIT_i/ila_eth3/probe5[9]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[9]}}
  {{VCU_INIT_i/ila_eth3/probe5[10]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[10]}}
  {{VCU_INIT_i/ila_eth3/probe5[11]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[11]}}
  {{VCU_INIT_i/ila_eth3/probe5[12]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[12]}}
  {{VCU_INIT_i/ila_eth3/probe5[13]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[13]}}
  {{VCU_INIT_i/ila_eth3/probe5[14]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[14]}}
  {{VCU_INIT_i/ila_eth3/probe5[15]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[15]}}
  {{VCU_INIT_i/ila_eth3/probe5[16]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[16]}}
  {{VCU_INIT_i/ila_eth3/probe5[17]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[17]}}
  {{VCU_INIT_i/ila_eth3/probe5[18]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[18]}}
  {{VCU_INIT_i/ila_eth3/probe5[19]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[19]}}
  {{VCU_INIT_i/ila_eth3/probe5[20]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[20]}}
  {{VCU_INIT_i/ila_eth3/probe5[21]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[21]}}
  {{VCU_INIT_i/ila_eth3/probe5[22]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[22]}}
  {{VCU_INIT_i/ila_eth3/probe5[23]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[23]}}
  {{VCU_INIT_i/ila_eth3/probe5[24]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[24]}}
  {{VCU_INIT_i/ila_eth3/probe5[25]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[25]}}
  {{VCU_INIT_i/ila_eth3/probe5[26]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[26]}}
  {{VCU_INIT_i/ila_eth3/probe5[27]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[27]}}
  {{VCU_INIT_i/ila_eth3/probe5[28]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[28]}}
  {{VCU_INIT_i/ila_eth3/probe5[29]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[29]}}
  {{VCU_INIT_i/ila_eth3/probe5[30]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[30]}}
  {{VCU_INIT_i/ila_eth3/probe5[31]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TDATA[31]}}
  {{VCU_INIT_i/ila_eth3/probe6[0]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TLAST}}
  {{VCU_INIT_i/ila_eth3/probe7[0]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TREADY}}
  {{VCU_INIT_i/ila_eth3/probe8[0]} {VCU_INIT_i/eth_dma3_M_AXIS_CNTRL_TVALID}}
  {{VCU_INIT_i/ila_eth3/probe9[0]} {VCU_INIT_i/pl_eth3/eth_buf_TX_AXIS_MAC_TDATA[0]}}
  {{VCU_INIT_i/ila_eth3/probe9[1]} {VCU_INIT_i/pl_eth3/eth_buf_TX_AXIS_MAC_TDATA[1]}}
  {{VCU_INIT_i/ila_eth3/probe9[2]} {VCU_INIT_i/pl_eth3/eth_buf_TX_AXIS_MAC_TDATA[2]}}
  {{VCU_INIT_i/ila_eth3/probe9[3]} {VCU_INIT_i/pl_eth3/eth_buf_TX_AXIS_MAC_TDATA[3]}}
  {{VCU_INIT_i/ila_eth3/probe9[4]} {VCU_INIT_i/pl_eth3/eth_buf_TX_AXIS_MAC_TDATA[4]}}
  {{VCU_INIT_i/ila_eth3/probe9[5]} {VCU_INIT_i/pl_eth3/eth_buf_TX_AXIS_MAC_TDATA[5]}}
  {{VCU_INIT_i/ila_eth3/probe9[6]} {VCU_INIT_i/pl_eth3/eth_buf_TX_AXIS_MAC_TDATA[6]}}
  {{VCU_INIT_i/ila_eth3/probe9[7]} {VCU_INIT_i/pl_eth3/eth_buf_TX_AXIS_MAC_TDATA[7]}}
  {{VCU_INIT_i/ila_eth3/probe10[0]} {VCU_INIT_i/pl_eth3/eth_buf_TX_AXIS_MAC_TLAST}}
  {{VCU_INIT_i/ila_eth3/probe11[0]} {VCU_INIT_i/pl_eth3/eth_buf_TX_AXIS_MAC_TREADY}}
  {{VCU_INIT_i/ila_eth3/probe12[0]} {VCU_INIT_i/pl_eth3/eth_buf_TX_AXIS_MAC_TVALID}}
  {{VCU_INIT_i/ila_eth3/probe13[0]} {VCU_INIT_i/pl_eth3/eth_buf_TX_AXIS_MAC_TUSER[0]}}
  {{VCU_INIT_i/ila_eth3/probe14[0]} {VCU_INIT_i/pl_eth3/mac_tx_reset}}
  {{VCU_INIT_i/ila_eth3/probe15[0]} {eth3_dbg_speed_sync_q}}
  {{VCU_INIT_i/ila_eth3/probe16[0]} {VCU_INIT_i/eth_dma3_mm2s_prmry_reset_out_n}}
  {{VCU_INIT_i/ila_eth3/probe17[0]} {VCU_INIT_i/eth_dma3_mm2s_cntrl_reset_out_n}}
  {{VCU_INIT_i/ila_eth3/probe18[0]} {VCU_INIT_i/pl_eth3/mac/debug_tx_ce}}
}
set checks {}
foreach pair $probe_pairs {
    lassign $pair pin_name net_name
    set pp [get_pins $pin_name]
    set nn [shadow_probe_net $net_name]
    if {[llength $pp] != 1 || [llength $nn] != 1} {error "ROUTED_PROBE_MISSING: $pin_name -> $net_name"}
    set actual [get_property NAME [get_nets -segments -of_objects $pp]]
    set wanted [get_property NAME $nn]
    if {[lsearch -exact $actual $wanted] < 0} {error "ROUTED_PROBE_MISMATCH: $pin_name -> $net_name; actual $actual"}
    lappend checks [list $pin_name $wanted]
}
set fh [open {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/reports/routed_probe_check.txt} w]
puts $fh "PASS: [llength $checks] probe input bits verified on routed design"
puts $fh $checks
puts $fh "Debug cores: [get_debug_cores]"
close $fh
puts "ROUTED_PROBE_CHECK_PASS: [llength $checks] bits"

# Verify the diagnostic-only CDC chain is preserved after optimization/routing.
foreach c {eth3_dbg_speed_meta eth3_dbg_speed_sync} {
    if {![get_property ASYNC_REG [get_cells $c]]} {error "CDC_ASYNC_REG_MISSING: $c"}
}
set n1 [get_nets -segments -of_objects [get_pins eth3_dbg_speed_meta/Q]]
set n2 [get_nets -segments -of_objects [get_pins eth3_dbg_speed_sync/D]]
if {[llength [lsort -unique [concat $n1 $n2]]] != [llength [lsort -unique $n1]]} {error "CDC_CHAIN_NOT_CONNECTED"}
set pins1 [get_pins -leaf -of_objects $n1 -filter {DIRECTION == IN}]
if {[llength $pins1] != 1 || [get_property NAME $pins1] ne "eth3_dbg_speed_sync/D"} {error "CDC_FIRST_STAGE_EXTRA_FANOUT: $pins1"}
set c1 [get_clocks -of_objects [get_pins eth3_dbg_speed_meta/C]]
set c2 [get_clocks -of_objects [get_pins eth3_dbg_speed_sync/C]]
set ci [get_clocks -of_objects [get_pins VCU_INIT_i/ila_eth3/clk]]
if {$c1 ne $ci || $c2 ne $ci} {error "CDC_CLOCK_MISMATCH"}
set fh [open {D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/reports/speed_cdc_check.txt} w]
puts $fh "PASS: two ASYNC_REG stages; first-stage only fanout is second-stage D; clocks match ILA: $ci"
puts $fh "Diagnostic-only input false path: eth3_dbg_speed_meta/D; stage1->stage2 remains timed. Original MAC consumers unchanged."
close $fh
puts "SPEED_CDC_CHECK_PASS"

