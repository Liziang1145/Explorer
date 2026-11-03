# Diagnostic-only synchronizer for the slowly changing MAC speed state.
# AXI config clock and external Ethernet reference clock are asynchronous.
# Original MAC consumers remain on the original net; only ILA probe15 changes.
if {[llength [get_cells -quiet eth3_dbg_speed_meta]] == 0} {
    create_cell -reference FDRE eth3_dbg_speed_meta
    create_cell -reference FDRE eth3_dbg_speed_sync
    create_cell -reference GND eth3_dbg_gnd
    create_cell -reference VCC eth3_dbg_vcc
    create_net eth3_dbg_gnd_net
    create_net eth3_dbg_vcc_net
    create_net eth3_dbg_speed_meta_q
    create_net eth3_dbg_speed_sync_q
    connect_net -net [get_nets eth3_dbg_gnd_net] -objects [get_pins {eth3_dbg_gnd/G eth3_dbg_speed_meta/R eth3_dbg_speed_sync/R}]
    connect_net -net [get_nets eth3_dbg_vcc_net] -objects [get_pins {eth3_dbg_vcc/P eth3_dbg_speed_meta/CE eth3_dbg_speed_sync/CE}]
    connect_net -net [get_nets eth3_dbg_speed_meta_q] -objects [get_pins {eth3_dbg_speed_meta/Q eth3_dbg_speed_sync/D}]
    connect_net -net [get_nets eth3_dbg_speed_sync_q] -objects [get_pins eth3_dbg_speed_sync/Q]
    connect_net -hierarchical -net [get_nets -of_objects [get_pins VCU_INIT_i/ila_eth3/clk]] -objects [get_pins {eth3_dbg_speed_meta/C eth3_dbg_speed_sync/C}]
    connect_net -hierarchical -net [get_nets VCU_INIT_i/pl_eth3/mac_speedis10100] -objects [get_pins eth3_dbg_speed_meta/D]
}
set_property ASYNC_REG TRUE [get_cells {eth3_dbg_speed_meta eth3_dbg_speed_sync}]
set_property DONT_TOUCH TRUE [get_cells {eth3_dbg_speed_meta eth3_dbg_speed_sync}]
set_property INIT 1'b0 [get_cells {eth3_dbg_speed_meta eth3_dbg_speed_sync}]
set_false_path -to [get_pins eth3_dbg_speed_meta/D]
# Only reconnect instantiated ILA input pins; preserve functional drivers.
# Implementation OPT_DESIGN.TCL.PRE hook.
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
    set nn [get_nets $net_name]
    if {[llength $pp] != 1 || [llength $nn] != 1} {
        error "ETH3_PROBE_MISSING: $pin_name -> $net_name"
    }
    if {[get_property DIRECTION $pp] ne "IN"} {
        error "ETH3_PROBE_NOT_INPUT: $pin_name"
    }
}
foreach pair $probe_pairs {
    lassign $pair pin_name net_name
    set pp [get_pins $pin_name]
    set nn [get_nets $net_name]
    set wanted [get_property NAME $nn]
    set existing [get_property NAME [get_nets -segments -of_objects $pp]]
    if {[lsearch -exact $existing $wanted] >= 0} {
        lappend checks [list $pin_name $wanted]
        continue
    }
    foreach old [get_nets -of_objects $pp] {
        set known_raw_speed [expr {$pin_name eq "VCU_INIT_i/ila_eth3/probe15\[0\]" && [lsearch -exact [get_property NAME [get_nets -segments -of_objects $pp]] {VCU_INIT_i/pl_eth3/mac_speedis10100}] >= 0}]
        if {![string match {VCU_INIT_i/dbg_zero*} [get_property NAME $old]] && !$known_raw_speed} {
            error "ETH3_UNEXPECTED_PLACEHOLDER: $pin_name -> $old"
        }
        if {!$known_raw_speed} {set_property DONT_TOUCH false $old}
    }
    disconnect_net -objects $pp
    connect_net -hierarchical -net $nn -objects $pp
    set actual [get_property NAME [get_nets -segments -of_objects $pp]]
    set wanted [get_property NAME $nn]
    if {[lsearch -exact $actual $wanted] < 0} {
        error "ETH3_PROBE_VERIFY_FAIL: $pin_name -> $net_name, actual $actual"
    }
    lappend checks [list $pin_name $wanted]
}
set evidence_dir [file join [get_property DIRECTORY [current_project]] evidence]
file mkdir $evidence_dir
set fh [open [file join $evidence_dir probe_connections_verified.tcllist] w]
puts $fh $checks
close $fh
puts "ETH3_PROBE_VERIFY_PASS: [llength $checks] input bits connected"

