# Only asynchronous input synchronizer FIRST stages are cut. Never mask the mux or whole core.
set can_first [get_cells -hier -regexp {.*can_path[01].*/(ownership/(rx_sync|ps_sync|pl_sync)|monitor/(rx_sync|tx_sync))_reg\[0\]}]
if {[llength $can_first]!=10} {error "CAN_SWITCH_FIRST_STAGE_COUNT [llength $can_first] expected 10"}
set_false_path -to [get_pins -of_objects $can_first -filter {REF_PIN_NAME == D}]
set ctu_first [get_cells -hier -regexp {.*pl_can_core[01].*/can_rx_sig_sync_inst/rff_reg}]
set ctu_second [get_cells -hier -regexp {.*pl_can_core[01].*/can_rx_sig_sync_inst/sync_reg}]
if {[llength $ctu_first]!=2 || [llength $ctu_second]!=2} {error "CTU_CAN_RX_SYNC_COUNT [llength $ctu_first] [llength $ctu_second] expected 2+2"}
set_property ASYNC_REG TRUE [concat $ctu_first $ctu_second]
set_false_path -to [get_pins -of_objects $ctu_first -filter {REF_PIN_NAME == D}]
puts {CAN_SWITCH_CDC_PASS: 10 new observer/owner first stages and 2 CTU RX synchronizers}
