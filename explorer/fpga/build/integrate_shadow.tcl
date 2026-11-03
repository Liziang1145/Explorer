set root [file dirname [info script]]
create_bd_cell -type module -reference pl_shadow pl_shadow_0
proc tap {src dst} {
 set source [get_bd_pins $src]
 if {[llength $source]!=1} {error "TAP_SOURCE $src"}
 set dest [get_bd_pins $dst]
 if {[llength $dest]!=1} {error "TAP_DEST $dst"}
 connect_bd_net $source $dest
}
tap zynq_ultra_ps_e_0/pl_clk0 pl_shadow_0/s_axi_aclk
tap proc_sys_reset_0/peripheral_aresetn pl_shadow_0/s_axi_aresetn
tap zynq_ultra_ps_e_0/pl_clk0 axi_interconnect_0/M10_ACLK
tap proc_sys_reset_0/peripheral_aresetn axi_interconnect_0/M10_ARESETN
tap eth_clock/clk_out1 pl_shadow_0/eth_clk
foreach c {0 1} { foreach dir {rx tx} {tap can_io_observer_0/can${c}_${dir}_raw pl_shadow_0/can${c}_${dir}_raw} }
foreach port {2 3} {
 foreach field {valid ready last keep} {
  tap eth_dma${port}/m_axis_mm2s_t${field} pl_shadow_0/tx${port}_${field}
  tap eth_dma${port}/s_axis_s2mm_t${field} pl_shadow_0/rx${port}_${field}
 }
}
connect_bd_intf_net [get_bd_intf_pins axi_interconnect_0/M10_AXI] [get_bd_intf_pins pl_shadow_0/S_AXI]
assign_bd_address -offset 0x80300000 -range 0x00010000 -target_address_space [get_bd_addr_spaces zynq_ultra_ps_e_0/Data] [get_bd_addr_segs pl_shadow_0/S_AXI/reg0]
# Explicit endpoints preserve scalar taps on existing AXIS interfaces.
foreach port {2 3} { foreach field {valid ready last keep} {
 connect_bd_net [get_bd_pins eth_dma${port}/m_axis_mm2s_t${field}] [get_bd_pins pl_eth${port}/eth_buf/AXI_STR_TXD_T[string toupper $field]]
 connect_bd_net [get_bd_pins eth_dma${port}/s_axis_s2mm_t${field}] [get_bd_pins pl_eth${port}/eth_buf/AXI_STR_RXD_[string toupper $field]]
} }
validate_bd_design
save_bd_design
set_property STEPS.INIT_DESIGN.TCL.PRE [file join $root implementation_threads.tcl] [get_runs impl_1]
set_property STEPS.OPT_DESIGN.TCL.PRE [file join $root implementation_prepare.tcl] [get_runs impl_1]
puts "SHADOW_CONNECTED: read-only taps, one MMIO slave, no output/IRQ/reset drivers"
