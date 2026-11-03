# KR260 J20 (PMOD4), physical schematic pin numbers; Bank 43, VCCO_HDB=PL_3V3.
set_property -dict {PACKAGE_PIN AC12 IOSTANDARD LVCMOS33 DRIVE 8 SLEW SLOW} [get_ports can0_tx]
set_property -dict {PACKAGE_PIN AD12 IOSTANDARD LVCMOS33 PULLUP true} [get_ports can0_rx]
set_property -dict {PACKAGE_PIN AE10 IOSTANDARD LVCMOS33 DRIVE 8 SLEW SLOW} [get_ports can1_tx]
set_property -dict {PACKAGE_PIN AF10 IOSTANDARD LVCMOS33 PULLUP true} [get_ports can1_rx]
set_property -dict {PACKAGE_PIN AD11 IOSTANDARD LVCMOS33 DRIVE 8 SLEW SLOW} [get_ports can2_tx]
set_property -dict {PACKAGE_PIN AD10 IOSTANDARD LVCMOS33 PULLUP true} [get_ports can2_rx]
