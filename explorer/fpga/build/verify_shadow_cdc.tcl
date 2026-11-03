set first [get_cells -hier -regexp {.*pl_shadow_0.*/(rx_sync|tx_sync|req_sync|reset_sync|ack_sync)_reg\[0\]}]
if {[llength $first]!=7} {error "SHADOW_CDC_FIRST_COUNT [llength $first]"}
set f [open D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/reports/shadow_cdc_structure.txt w]
foreach c $first {
 if {![get_property ASYNC_REG $c]} {error "SHADOW_ASYNC_REG_MISSING $c"}
 set dest [get_pins -leaf -of_objects [get_nets -segments -of_objects [get_pins $c/Q]] -filter {DIRECTION == IN}]
 if {[llength $dest]!=1 || ![regexp {_reg\[1\]/D$} $dest]} {error "SHADOW_META_EXTRA_FANOUT $c $dest"}
 set second [get_cells -of_objects $dest]
 if {![get_property ASYNC_REG $second]} {error "SHADOW_SECOND_ASYNC_REG_MISSING $second"}
 puts $f "PASS $c -> $dest; both ASYNC_REG; no extra first-stage fanout"
}
close $f
puts "SHADOW_CDC_STRUCTURE_PASS"
