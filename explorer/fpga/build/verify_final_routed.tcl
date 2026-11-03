source -notrace D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/verify_routed_probes.tcl
set fh [open D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/reports/routed_reset_check.txt w]
foreach i {2 3} {
 set src [format {VCU_INIT_i/eth%d_recovery_reset/peripheral_aresetn[0]} $i]
 set sn [get_nets -segments -of_objects [get_pins $src]]
 if {![llength $sn]} {error "RESET_SOURCE_MISSING $src"}
 foreach dst [list VCU_INIT_i/pl_eth${i}/s_axi_lite_resetn VCU_INIT_i/eth_dma${i}/axi_resetn] {
  set dn [get_nets -segments -of_objects [get_pins $dst]]
  if {![llength $dn]} {error "RESET_DEST_MISSING $dst"}
  set shared 0
  foreach nn $dn {if {[lsearch -exact $sn $nn]>=0} {set shared 1}}
  if {!$shared} {error "RESET_NOT_CONNECTED $src $dst"}
  puts $fh "PASS $src -> $dst"
 }
 set peer [expr {5-$i}]
 set pn [get_nets -segments -of_objects [get_pins VCU_INIT_i/eth_dma${peer}/axi_resetn]]
 foreach nn $pn {if {[lsearch -exact $sn $nn]>=0} {error "RESET_PORTS_SHORTED"}}
 puts $fh "PASS port$i isolated from port$peer"
}
close $fh
report_timing_summary -delay_type min_max -report_unconstrained -check_timing_verbose -file D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/reports/final_timing.rpt
report_drc -file D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/reports/final_drc.rpt
report_route_status -file D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/reports/final_route.rpt
report_cdc -details -file D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/evidence/final_cdc.rpt
report_cdc -from [get_clocks clk_pl_0] -to [get_clocks clk_out1_VCU_INIT_eth_clock_0] -details -file D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/evidence/config_to_eth_cdc.rpt
write_debug_probes -force D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/kr260_j20_j19.ltx
puts "FINAL_ROUTED_CHECKS_COMPLETE"


report_bus_skew -file D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/reports/final_bus_skew.rpt
set licensed [get_cells -quiet -hier -filter {REF_NAME =~ *tri_mode* || REF_NAME =~ *axi_ethernet_buffer*}]
if {[llength $licensed]} {error "LICENSED_MAC_REMAINS: $licensed"}
set fh [open D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/reports/no_temac.txt w]
puts $fh "PASS: no TEMAC or AMD AXI Ethernet buffer instances in routed netlist"
close $fh

# Fail if any TX pin lost setup/hold analysis (e.g. deferred OOC clock constraint).
set fh [open D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/reports/rgmii_endpoint_check.txt w]
foreach port [get_ports {eth2_rgmii_td* eth2_rgmii_tx_ctl eth3_rgmii_td* eth3_rgmii_tx_ctl}] {
    foreach kind {max min} {
        set path [get_timing_paths -to $port -delay_type $kind -max_paths 1]
        if {[llength $path] != 1} {error "TX_TIMING_PATH_MISSING $port $kind"}
        set slack [get_property SLACK $path]
        if {$slack < 0} {error "TX_TIMING_FAIL $port $kind $slack"}
        puts $fh "PASS $port $kind slack=$slack requirement=[get_property REQUIREMENT $path]"
    }
}
close $fh
report_timing -to [get_ports {eth2_rgmii_td* eth2_rgmii_tx_ctl eth3_rgmii_td* eth3_rgmii_tx_ctl}] -delay_type max -max_paths 20 -file D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/reports/rgmii_tx_setup.rpt
report_timing -to [get_ports {eth2_rgmii_td* eth2_rgmii_tx_ctl eth3_rgmii_td* eth3_rgmii_tx_ctl}] -delay_type min -max_paths 20 -file D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/reports/rgmii_tx_hold.rpt
report_timing -from [get_ports {eth2_rgmii_rd* eth2_rgmii_rx_ctl eth3_rgmii_rd* eth3_rgmii_rx_ctl}] -delay_type max -max_paths 20 -file D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/reports/rgmii_rx_setup.rpt
report_timing -from [get_ports {eth2_rgmii_rd* eth2_rgmii_rx_ctl eth3_rgmii_rd* eth3_rgmii_rx_ctl}] -delay_type min -max_paths 20 -file D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/reports/rgmii_rx_hold.rpt
