set base [file dirname [info script]]
source [file join $base constraints axis_async_fifo.tcl]
source [file join $base constraints open_mac_cdc.tcl]
source [file join $base connect_eth3_probes.tcl]
set sync_d [get_pins -hier -filter {NAME =~ *can_io_observer_0*obs_meta_reg*/D}]
if {[llength $sync_d] != 32} {error "CAN_OBSERVER_SYNC_COUNT [llength $sync_d]"}
set_false_path -to $sync_d
puts "CAN_OBSERVER_CDC_PASS: 32 first-stage inputs"
