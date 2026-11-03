set first [concat [get_cells -hier -regexp {.*can_path[01].*/(ownership/(rx_sync|ps_sync|pl_sync)|monitor/(rx_sync|tx_sync))_reg\[0\]}] [get_cells -hier -regexp {.*pl_can_core[01].*/can_rx_sig_sync_inst/rff_reg}]]
if {[llength $first]!=12} {error "CAN_SYNC_COUNT [llength $first] expected 12"}
set f [open D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/reports/can_switch_cdc_structure.txt w]
foreach c $first {
 if {![get_property ASYNC_REG $c]} {error "ASYNC_REG_MISSING $c"}
 set dest [get_pins -leaf -of_objects [get_nets -segments -of_objects [get_pins $c/Q]] -filter {DIRECTION == IN}]
 if {[llength $dest]!=1 || ![regexp {(_reg\[1\]|/sync_reg)/D$} $dest]} {error "META_EXTRA_FANOUT $c $dest"}
 set second [get_cells -of_objects $dest]
 if {![get_property ASYNC_REG $second]} {error "SECOND_ASYNC_REG_MISSING $second"}
 puts $f "PASS $c -> $dest; both ASYNC_REG; no extra first-stage fanout"
}
close $f
puts "CAN_SWITCH_CDC_STRUCTURE_PASS"
