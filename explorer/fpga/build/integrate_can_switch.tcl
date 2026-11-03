set root [file dirname [info script]]
# Rebind external shadow RTL before any editing; baseline files remain immutable.
foreach f {pl_shadow.v pl_stream_monitor.v can_passive_monitor.v} {
 set old [get_files -quiet D:/2026FPGArace/KR260_PL_SHADOW_20261102/rtl/$f]
 if {[llength $old]} {remove_files $old}
 add_files -fileset sources_1 [file join $root rtl $f]
}
add_files -fileset sources_1 [list [file join $root rtl can_axil_endpoint.v] [file join $root rtl can_path_owner.v] [file join $root rtl can_core_service.v] [file join $root rtl arm_command_engine.v] [file join $root rtl can_path_control.v]]
set_property ip_repo_paths [file join $root third_party ctucanfd src] [current_project]
update_ip_catalog
update_compile_order -fileset sources_1
puts [ipcfg::require axi_interconnect_0 {CONFIG.NUM_MI 13} {Two additional independent CAN register slaves}]
puts [ipcfg::require system_irqs {CONFIG.NUM_PORTS 7} {Preserve first three interrupts and append CAN native/control pairs}]
foreach c {0 1} {
 puts [ipcfg::create_cell_cfg user.org:user:CTU_CAN_FD:1.0 pl_can_core$c {CONFIG.rx_buffer_size 512 CONFIG.sup_filtA true CONFIG.sup_filtB true CONFIG.sup_filtC true CONFIG.sup_range true CONFIG.sup_traffic_ctrs true}]
 puts [ipcfg::require pl_can_core$c {CONFIG.rx_buffer_size 512 CONFIG.sup_filtA true CONFIG.sup_filtB true CONFIG.sup_filtC true CONFIG.sup_range true CONFIG.sup_traffic_ctrs true} {Existing verified CTU 2.2 snapshot, dedicated independent controller}]
 create_bd_cell -type module -reference can_path_control can_path$c
 set_property CONFIG.CHANNEL $c [get_bd_cells can_path$c]
 connect_bd_net [get_bd_pins zynq_ultra_ps_e_0/pl_clk0] [get_bd_pins can_path$c/s_axi_aclk] [get_bd_pins pl_can_core$c/aclk] [get_bd_pins axi_interconnect_0/M[expr 11+$c]_ACLK]
 connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_pins can_path$c/s_axi_aresetn] [get_bd_pins axi_interconnect_0/M[expr 11+$c]_ARESETN]
 connect_bd_net [get_bd_pins can_path$c/core_resetn] [get_bd_pins pl_can_core$c/arstn]
 connect_bd_net [get_bd_pins can_path$c/timestamp] [get_bd_pins pl_can_core$c/timestamp]
 foreach {a b} {apb_addr s_apb_paddr apb_sel s_apb_psel apb_enable s_apb_penable apb_write s_apb_pwrite apb_wdata s_apb_pwdata apb_strb s_apb_pstrb apb_prot s_apb_pprot apb_rdata s_apb_prdata apb_ready s_apb_pready apb_error s_apb_pslverr} {
  connect_bd_net [get_bd_pins can_path$c/$a] [get_bd_pins pl_can_core$c/$b]
 }
 connect_bd_net [get_bd_pins pl_can_core$c/CAN_tx] [get_bd_pins can_path$c/pl_tx]
 connect_bd_net [get_bd_pins pl_can_core$c/CAN_rx] [get_bd_pins can_path$c/pl_rx]
 connect_bd_net [get_bd_pins pl_can_core$c/irq] [get_bd_pins can_path$c/core_irq]
 connect_bd_net [get_bd_pins can_path$c/irq_native] [get_bd_pins system_irqs/In[expr 3+2*$c]]
 connect_bd_net [get_bd_pins can_path$c/irq_control] [get_bd_pins system_irqs/In[expr 4+2*$c]]
 connect_bd_intf_net [get_bd_intf_pins axi_interconnect_0/M[expr 11+$c]_AXI] [get_bd_intf_pins can_path$c/S_AXI]
 assign_bd_address -offset [format 0x%08x [expr 0x80310000+$c*0x10000]] -range 0x10000 -target_address_space [get_bd_addr_spaces zynq_ultra_ps_e_0/Data] [get_bd_addr_segs can_path$c/S_AXI/reg0]
 # Separate only the PS endpoints. Existing physical raw taps retain their nets.
 set oldtx [get_bd_nets -of_objects [get_bd_pins zynq_ultra_ps_e_0/emio_can${c}_phy_tx]]
 disconnect_bd_net $oldtx [get_bd_pins zynq_ultra_ps_e_0/emio_can${c}_phy_tx]
 connect_bd_net [get_bd_ports can${c}_tx] [get_bd_pins can_path$c/can_tx]
 connect_bd_net [get_bd_pins zynq_ultra_ps_e_0/emio_can${c}_phy_tx] [get_bd_pins can_path$c/ps_tx]
 set oldrx [get_bd_nets -of_objects [get_bd_pins zynq_ultra_ps_e_0/emio_can${c}_phy_rx]]
 disconnect_bd_net $oldrx [get_bd_pins zynq_ultra_ps_e_0/emio_can${c}_phy_rx]
 connect_bd_net [get_bd_ports can${c}_rx] [get_bd_pins can_path$c/can_rx_raw]
 connect_bd_net [get_bd_pins zynq_ultra_ps_e_0/emio_can${c}_phy_rx] [get_bd_pins can_path$c/ps_rx]
}
validate_bd_design
save_bd_design
set_property STEPS.INIT_DESIGN.TCL.PRE [file join $root implementation_threads.tcl] [get_runs impl_1]
set_property STEPS.OPT_DESIGN.TCL.PRE [file join $root implementation_prepare.tcl] [get_runs impl_1]
puts {CAN_SWITCH_CONNECTED: original physical pin nets retained; new independent owners/controllers and appended IRQs}
