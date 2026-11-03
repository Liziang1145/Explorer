# All sampled single-bit async inputs use two ASYNC_REG FFs.
set first [get_cells -hier -regexp {.*pl_shadow_0.*/(rx_sync|tx_sync|req_sync|reset_sync|ack_sync)_reg\[0\]}]
if {[llength $first]!=7} {error "SHADOW_FIRST_STAGE_COUNT [llength $first] expected 7"}
set_false_path -to [get_pins -of_objects $first -filter {REF_PIN_NAME == D}]
# Bundled-data mailbox: held source snapshot, ack crosses two FFs; destination
# captures no earlier than the third destination clock. Source changes only on req.
set hold [get_cells -hier -regexp {.*pl_shadow_0.*/streams/snapshot_reg\[[0-9]+\]}]
set dest [get_cells -hier -regexp {.*pl_shadow_0.*/eth_snap_reg\[[0-9]+\]}]
if {[llength $hold]!=1024 || [llength $dest]!=1024} {error "SHADOW_MAILBOX_WIDTH [llength $hold] [llength $dest]"}
set_max_delay -datapath_only 20.000 -from $hold -to $dest
set_bus_skew 8.000 -from $hold -to $dest
puts "SHADOW_CDC_CONSTRAINTS_PASS"
