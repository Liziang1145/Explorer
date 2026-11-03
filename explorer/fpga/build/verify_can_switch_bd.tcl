set root [file dirname [info script]]
proc same_net {a b} {
 set na [get_bd_nets -of_objects $a];set nb [get_bd_nets -of_objects $b]
 if {[llength $na]!=1||$na!=$nb} {error "NET_MISMATCH $a $b : $na $nb"}
}
foreach c {0 1} {
 same_net [get_bd_ports can${c}_tx] [get_bd_pins can_path$c/can_tx]
 same_net [get_bd_ports can${c}_rx] [get_bd_pins can_path$c/can_rx_raw]
 same_net [get_bd_ports can${c}_tx] [get_bd_pins can_io_observer_0/can${c}_tx_raw]
 same_net [get_bd_ports can${c}_rx] [get_bd_pins can_io_observer_0/can${c}_rx_raw]
 same_net [get_bd_ports can${c}_tx] [get_bd_pins pl_shadow_0/can${c}_tx_raw]
 same_net [get_bd_ports can${c}_rx] [get_bd_pins pl_shadow_0/can${c}_rx_raw]
 same_net [get_bd_pins zynq_ultra_ps_e_0/emio_can${c}_phy_tx] [get_bd_pins can_path$c/ps_tx]
 same_net [get_bd_pins zynq_ultra_ps_e_0/emio_can${c}_phy_rx] [get_bd_pins can_path$c/ps_rx]
 same_net [get_bd_pins can_path$c/irq_native] [get_bd_pins system_irqs/In[expr 3+2*$c]]
 same_net [get_bd_pins can_path$c/irq_control] [get_bd_pins system_irqs/In[expr 4+2*$c]]
 same_net [get_bd_pins zynq_ultra_ps_e_0/pl_clk0] [get_bd_pins pl_can_core$c/aclk]
}
same_net [get_bd_ports can2_tx] [get_bd_pins ctu_can2/CAN_tx]
same_net [get_bd_ports can2_rx] [get_bd_pins ctu_can2/CAN_rx]
same_net [get_bd_pins system_irqs/dout] [get_bd_pins zynq_ultra_ps_e_0/pl_ps_irq0]
set f [open [file join $root evidence can_switch_bd_connections.txt] w]
puts $f {PASS: both physical mux paths, PS/PL RX isolation endpoints, raw observer taps, CAN2 unchanged, IRQ 3..6 and PL0 clock}
foreach c {0 1} {
 foreach p [get_bd_pins can_path$c/*] {puts $f "$p [get_bd_nets -of_objects $p]"}
}
close $f
puts {CAN_SWITCH_BD_CONNECTIONS_PASS}
