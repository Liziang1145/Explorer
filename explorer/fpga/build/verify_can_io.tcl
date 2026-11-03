set out [open D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/reports/can_io_routed_check.txt w]
proc same_net {a b} {
 set ap [get_pins $a];set bp [get_pins $b]
 if {[llength $ap]!=1 || [llength $bp]!=1} {error "MISSING_PIN $a $b"}
 set an [get_nets -segments -of_objects $ap];set bn [get_nets -segments -of_objects $bp]
 foreach n $an {if {[lsearch -exact $bn $n]>=0} {return}}
 error "NET_MISMATCH $a $b"
}
set observer VCU_INIT_i/can_io_observer_0
foreach {port ball} {can0_tx AC12 can0_rx AD12 can1_tx AE10 can1_rx AF10 can2_tx AD11 can2_rx AD10} {
 if {[get_property PACKAGE_PIN [get_ports $port]] ne $ball || [get_property IOSTANDARD [get_ports $port]] ne "LVCMOS33"} {error "PIN_FAIL $port"}
 puts $out "PASS PIN $port $ball LVCMOS33"
}
foreach i {0 1 2} {
 same_net can${i}_tx_OBUF_inst/I $observer/can${i}_tx_raw
 same_net can${i}_rx_IBUF_inst/O $observer/can${i}_rx_raw
 if {$i<2} {
  same_net can${i}_tx_OBUF_inst/I VCU_INIT_i/can_path${i}/can_tx
  same_net can${i}_rx_IBUF_inst/O VCU_INIT_i/can_path${i}/can_rx_raw
  same_net VCU_INIT_i/zynq_ultra_ps_e_0/inst/PS8_i/EMIOCAN${i}PHYTX VCU_INIT_i/can_path${i}/ps_tx
  same_net VCU_INIT_i/zynq_ultra_ps_e_0/inst/PS8_i/EMIOCAN${i}PHYRX VCU_INIT_i/can_path${i}/ps_rx
  same_net VCU_INIT_i/pl_can_core${i}/CAN_tx VCU_INIT_i/can_path${i}/pl_tx
  same_net VCU_INIT_i/pl_can_core${i}/CAN_rx VCU_INIT_i/can_path${i}/pl_rx
 } else {
  same_net can2_tx_OBUF_inst/I VCU_INIT_i/ctu_can2/CAN_tx
  same_net can2_rx_IBUF_inst/O VCU_INIT_i/ctu_can2/CAN_rx
 }
 puts $out "PASS CAN$i functional path and TX/RX observation tap"
}
set balls {AE12 AF11 AF12 AG11 AG10 AH12 AH10 AH11}
for {set i 0} {$i<8} {incr i} {
 set port [get_ports [format {gpio_j18[%d]} $i]]
 if {[get_property PACKAGE_PIN $port] ne [lindex $balls $i] || [get_property IOSTANDARD $port] ne "LVCMOS33"} {error "GPIO_PIN_FAIL $i"}
 foreach {pad signal} {O gpio_i I gpio_o T gpio_t} {
  same_net gpio_j18buf_$i/$pad [format {%s/%s_raw[%d]} $observer $signal $i]
  same_net gpio_j18buf_$i/$pad [format {VCU_INIT_i/axi_gpio_j18/gpio_io_%s[%d]} [string index $signal end] $i]
 }
 puts $out "PASS GPIO$i package pin, functional I/O/T and observation taps"
}
set widths {6 8 8 8 2 1 32};set signals {can_observed gpio_i_observed gpio_o_observed gpio_t_observed resetn_observed sample_tick timestamp}
for {set p 0} {$p<7} {incr p} {
 for {set b 0} {$b<[lindex $widths $p]} {incr b} {
  set name [lindex $signals $p]
  set source [expr {$p==5 ? "$observer/$name" : [format {%s/%s[%d]} $observer $name $b]}]
  same_net [format {VCU_INIT_i/ila_can_io/probe%d[%d]} $p $b] $source
 }
 puts $out "PASS ILA probe$p [lindex $widths $p] bits -> [lindex $signals $p]"
}
set metas [get_cells -hier -filter {NAME =~ *can_io_observer_0*obs_meta_reg* && IS_SEQUENTIAL == 1}]
set syncs [get_cells -hier -filter {NAME =~ *can_io_observer_0*obs_sync_reg* && IS_SEQUENTIAL == 1}]
if {[llength $metas]!=32 || [llength $syncs]!=32} {error "SYNC_COUNT_FAIL"}
foreach c [concat $metas $syncs] {if {![get_property ASYNC_REG $c]} {error "ASYNC_REG_MISSING $c"}}
foreach c $metas {
 set dest [get_pins -leaf -of_objects [get_nets -segments -of_objects [get_pins $c/Q]] -filter {DIRECTION == IN}]
 if {[llength $dest]!=1 || ![string match *obs_sync_reg*/D $dest]} {error "META_EXTRA_FANOUT $c $dest"}
}
puts $out "PASS 32 pairs of preserved ASYNC_REG synchronizers; meta fanout only to second stage"
puts $out "DEBUG_CORES [get_debug_cores]"
close $out
puts "CAN_GPIO_ROUTED_CHECK_PASS"
