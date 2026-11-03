set f [open D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/reports/pin_migration_check.txt w]
if {[llength [get_ports]] != 45} {error "PORT_COUNT_CHANGED"}
if {[get_property PACKAGE_PIN [get_ports {eth2_rgmii_rd[0]}]] ne "A1" || [get_property IOSTANDARD [get_ports {eth2_rgmii_rd[0]}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth2_rgmii_rd[0]"}
puts $f {PASS eth2_rgmii_rd[0] A1 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth2_rgmii_txc}]] ne "A2" || [get_property IOSTANDARD [get_ports {eth2_rgmii_txc}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth2_rgmii_txc"}
puts $f {PASS eth2_rgmii_txc A2 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth2_rgmii_rd[2]}]] ne "A3" || [get_property IOSTANDARD [get_ports {eth2_rgmii_rd[2]}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth2_rgmii_rd[2]"}
puts $f {PASS eth2_rgmii_rd[2] A3 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth2_rgmii_rx_ctl}]] ne "A4" || [get_property IOSTANDARD [get_ports {eth2_rgmii_rx_ctl}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth2_rgmii_rx_ctl"}
puts $f {PASS eth2_rgmii_rx_ctl A4 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth2_resetn[0]}]] ne "B1" || [get_property IOSTANDARD [get_ports {eth2_resetn[0]}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth2_resetn[0]"}
puts $f {PASS eth2_resetn[0] B1 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth2_rgmii_rd[1]}]] ne "B3" || [get_property IOSTANDARD [get_ports {eth2_rgmii_rd[1]}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth2_rgmii_rd[1]"}
puts $f {PASS eth2_rgmii_rd[1] B3 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth2_rgmii_rd[3]}]] ne "B4" || [get_property IOSTANDARD [get_ports {eth2_rgmii_rd[3]}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth2_rgmii_rd[3]"}
puts $f {PASS eth2_rgmii_rd[3] B4 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {can2_tx}]] ne "AD11" || [get_property IOSTANDARD [get_ports {can2_tx}]] ne "LVCMOS33"} {error "PIN_MIGRATION_FAIL can2_tx"}
puts $f {PASS can2_tx AD11 LVCMOS33}
if {[get_property PACKAGE_PIN [get_ports {eth_refclk_25}]] ne "C3" || [get_property IOSTANDARD [get_ports {eth_refclk_25}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth_refclk_25"}
puts $f {PASS eth_refclk_25 C3 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {can1_rx}]] ne "AF10" || [get_property IOSTANDARD [get_ports {can1_rx}]] ne "LVCMOS33"} {error "PIN_MIGRATION_FAIL can1_rx"}
puts $f {PASS can1_rx AF10 LVCMOS33}
if {[get_property PACKAGE_PIN [get_ports {eth2_rgmii_td[1]}]] ne "D1" || [get_property IOSTANDARD [get_ports {eth2_rgmii_td[1]}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth2_rgmii_td[1]"}
puts $f {PASS eth2_rgmii_td[1] D1 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth2_rgmii_rxc}]] ne "D4" || [get_property IOSTANDARD [get_ports {eth2_rgmii_rxc}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth2_rgmii_rxc"}
puts $f {PASS eth2_rgmii_rxc D4 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {can1_tx}]] ne "AE10" || [get_property IOSTANDARD [get_ports {can1_tx}]] ne "LVCMOS33"} {error "PIN_MIGRATION_FAIL can1_tx"}
puts $f {PASS can1_tx AE10 LVCMOS33}
if {[get_property PACKAGE_PIN [get_ports {eth2_rgmii_td[0]}]] ne "E1" || [get_property IOSTANDARD [get_ports {eth2_rgmii_td[0]}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth2_rgmii_td[0]"}
puts $f {PASS eth2_rgmii_td[0] E1 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth2_rgmii_td[3]}]] ne "E2" || [get_property IOSTANDARD [get_ports {eth2_rgmii_td[3]}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth2_rgmii_td[3]"}
puts $f {PASS eth2_rgmii_td[3] E2 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {can0_rx}]] ne "AD12" || [get_property IOSTANDARD [get_ports {can0_rx}]] ne "LVCMOS33"} {error "PIN_MIGRATION_FAIL can0_rx"}
puts $f {PASS can0_rx AD12 LVCMOS33}
if {[get_property PACKAGE_PIN [get_ports {can2_rx}]] ne "AD10" || [get_property IOSTANDARD [get_ports {can2_rx}]] ne "LVCMOS33"} {error "PIN_MIGRATION_FAIL can2_rx"}
puts $f {PASS can2_rx AD10 LVCMOS33}
if {[get_property PACKAGE_PIN [get_ports {eth2_rgmii_tx_ctl}]] ne "F1" || [get_property IOSTANDARD [get_ports {eth2_rgmii_tx_ctl}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth2_rgmii_tx_ctl"}
puts $f {PASS eth2_rgmii_tx_ctl F1 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth2_rgmii_td[2]}]] ne "F2" || [get_property IOSTANDARD [get_ports {eth2_rgmii_td[2]}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth2_rgmii_td[2]"}
puts $f {PASS eth2_rgmii_td[2] F2 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth2_mdio_mdio_io}]] ne "F3" || [get_property IOSTANDARD [get_ports {eth2_mdio_mdio_io}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth2_mdio_mdio_io"}
puts $f {PASS eth2_mdio_mdio_io F3 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {gpio_j18[7]}]] ne "AH11" || [get_property IOSTANDARD [get_ports {gpio_j18[7]}]] ne "LVCMOS33"} {error "PIN_MIGRATION_FAIL gpio_j18[7]"}
puts $f {PASS gpio_j18[7] AH11 LVCMOS33}
if {[get_property PACKAGE_PIN [get_ports {gpio_j18[5]}]] ne "AH12" || [get_property IOSTANDARD [get_ports {gpio_j18[5]}]] ne "LVCMOS33"} {error "PIN_MIGRATION_FAIL gpio_j18[5]"}
puts $f {PASS gpio_j18[5] AH12 LVCMOS33}
if {[get_property PACKAGE_PIN [get_ports {eth2_mdio_mdc}]] ne "G3" || [get_property IOSTANDARD [get_ports {eth2_mdio_mdc}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth2_mdio_mdc"}
puts $f {PASS eth2_mdio_mdc G3 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {gpio_j18[3]}]] ne "AG11" || [get_property IOSTANDARD [get_ports {gpio_j18[3]}]] ne "LVCMOS33"} {error "PIN_MIGRATION_FAIL gpio_j18[3]"}
puts $f {PASS gpio_j18[3] AG11 LVCMOS33}
if {[get_property PACKAGE_PIN [get_ports {eth3_rgmii_rd[0]}]] ne "H1" || [get_property IOSTANDARD [get_ports {eth3_rgmii_rd[0]}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth3_rgmii_rd[0]"}
puts $f {PASS eth3_rgmii_rd[0] H1 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth3_rgmii_rx_ctl}]] ne "H3" || [get_property IOSTANDARD [get_ports {eth3_rgmii_rx_ctl}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth3_rgmii_rx_ctl"}
puts $f {PASS eth3_rgmii_rx_ctl H3 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth3_rgmii_rd[3]}]] ne "H4" || [get_property IOSTANDARD [get_ports {eth3_rgmii_rd[3]}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth3_rgmii_rd[3]"}
puts $f {PASS eth3_rgmii_rd[3] H4 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {gpio_j18[1]}]] ne "AF11" || [get_property IOSTANDARD [get_ports {gpio_j18[1]}]] ne "LVCMOS33"} {error "PIN_MIGRATION_FAIL gpio_j18[1]"}
puts $f {PASS gpio_j18[1] AF11 LVCMOS33}
if {[get_property PACKAGE_PIN [get_ports {can0_tx}]] ne "AC12" || [get_property IOSTANDARD [get_ports {can0_tx}]] ne "LVCMOS33"} {error "PIN_MIGRATION_FAIL can0_tx"}
puts $f {PASS can0_tx AC12 LVCMOS33}
if {[get_property PACKAGE_PIN [get_ports {eth3_rgmii_txc}]] ne "J1" || [get_property IOSTANDARD [get_ports {eth3_rgmii_txc}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth3_rgmii_txc"}
puts $f {PASS eth3_rgmii_txc J1 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth3_rgmii_rd[2]}]] ne "J2" || [get_property IOSTANDARD [get_ports {eth3_rgmii_rd[2]}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth3_rgmii_rd[2]"}
puts $f {PASS eth3_rgmii_rd[2] J2 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {gpio_j18[2]}]] ne "AF12" || [get_property IOSTANDARD [get_ports {gpio_j18[2]}]] ne "LVCMOS33"} {error "PIN_MIGRATION_FAIL gpio_j18[2]"}
puts $f {PASS gpio_j18[2] AF12 LVCMOS33}
if {[get_property PACKAGE_PIN [get_ports {gpio_j18[0]}]] ne "AE12" || [get_property IOSTANDARD [get_ports {gpio_j18[0]}]] ne "LVCMOS33"} {error "PIN_MIGRATION_FAIL gpio_j18[0]"}
puts $f {PASS gpio_j18[0] AE12 LVCMOS33}
if {[get_property PACKAGE_PIN [get_ports {eth3_resetn[0]}]] ne "K1" || [get_property IOSTANDARD [get_ports {eth3_resetn[0]}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth3_resetn[0]"}
puts $f {PASS eth3_resetn[0] K1 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth3_rgmii_rd[1]}]] ne "K2" || [get_property IOSTANDARD [get_ports {eth3_rgmii_rd[1]}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth3_rgmii_rd[1]"}
puts $f {PASS eth3_rgmii_rd[1] K2 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth3_rgmii_rxc}]] ne "K4" || [get_property IOSTANDARD [get_ports {eth3_rgmii_rxc}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth3_rgmii_rxc"}
puts $f {PASS eth3_rgmii_rxc K4 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {gpio_j18[6]}]] ne "AH10" || [get_property IOSTANDARD [get_ports {gpio_j18[6]}]] ne "LVCMOS33"} {error "PIN_MIGRATION_FAIL gpio_j18[6]"}
puts $f {PASS gpio_j18[6] AH10 LVCMOS33}
if {[get_property PACKAGE_PIN [get_ports {gpio_j18[4]}]] ne "AG10" || [get_property IOSTANDARD [get_ports {gpio_j18[4]}]] ne "LVCMOS33"} {error "PIN_MIGRATION_FAIL gpio_j18[4]"}
puts $f {PASS gpio_j18[4] AG10 LVCMOS33}
if {[get_property PACKAGE_PIN [get_ports {eth3_mdio_mdc}]] ne "R8" || [get_property IOSTANDARD [get_ports {eth3_mdio_mdc}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth3_mdio_mdc"}
puts $f {PASS eth3_mdio_mdc R8 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth3_mdio_mdio_io}]] ne "T8" || [get_property IOSTANDARD [get_ports {eth3_mdio_mdio_io}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth3_mdio_mdio_io"}
puts $f {PASS eth3_mdio_mdio_io T8 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth3_rgmii_td[2]}]] ne "U8" || [get_property IOSTANDARD [get_ports {eth3_rgmii_td[2]}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth3_rgmii_td[2]"}
puts $f {PASS eth3_rgmii_td[2] U8 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth3_rgmii_td[0]}]] ne "U9" || [get_property IOSTANDARD [get_ports {eth3_rgmii_td[0]}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth3_rgmii_td[0]"}
puts $f {PASS eth3_rgmii_td[0] U9 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth3_rgmii_td[3]}]] ne "V8" || [get_property IOSTANDARD [get_ports {eth3_rgmii_td[3]}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth3_rgmii_td[3]"}
puts $f {PASS eth3_rgmii_td[3] V8 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth3_rgmii_td[1]}]] ne "V9" || [get_property IOSTANDARD [get_ports {eth3_rgmii_td[1]}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth3_rgmii_td[1]"}
puts $f {PASS eth3_rgmii_td[1] V9 LVCMOS18}
if {[get_property PACKAGE_PIN [get_ports {eth3_rgmii_tx_ctl}]] ne "Y8" || [get_property IOSTANDARD [get_ports {eth3_rgmii_tx_ctl}]] ne "LVCMOS18"} {error "PIN_MIGRATION_FAIL eth3_rgmii_tx_ctl"}
puts $f {PASS eth3_rgmii_tx_ctl Y8 LVCMOS18}
close $f
report_io -file D:/2026FPGArace/KR260_PL_CAN_FIX_20261103/build_project/delivery/reports/final_io.rpt
puts "PIN_MIGRATION_PASS: 14 remapped, 31 unchanged"
