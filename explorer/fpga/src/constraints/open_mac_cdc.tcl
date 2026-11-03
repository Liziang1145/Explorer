# Synchronize configuration only while RX/TX is disabled. Do not false-path Gray counters.
set cfg_first [get_cells -hier -regexp {.*mac/inst/(rx_addr_meta_reg\[[0-9]+\]|speed_meta_reg\[[0-9]+\]|[rt]x_cfg_sync_reg\[0\]|engine/(rx_prescale_sync_reg\[0\]|[rt]x_mii_select_sync_reg\[0\])|csr/mdio_in_meta_reg)}]
if {[llength $cfg_first]} {set_false_path -to [get_pins -of_objects $cfg_first -filter {REF_PIN_NAME == D}]}
# Gray-coded packet counters: bound delay and skew to one source clock period (8ns fastest).
foreach inst [get_cells -hier -filter {REF_NAME == kr260_stat_cdc || ORIG_REF_NAME == kr260_stat_cdc}] {
 set src [get_cells -quiet "$inst/gray_reg*"]
 set dst [get_cells -quiet "$inst/meta_reg*"]
 if {[llength $src] && [llength $dst]} {
  set_max_delay -datapath_only -from $src -to $dst 8.000
  set_bus_skew -from $src -to $dst 8.000
 }
}
# Asynchronous assertion, four-stage synchronous release inside rgmii_phy_if.
set async_rst [get_pins -hier -filter {NAME =~ *mac/inst/*rst_reg*/PRE || NAME =~ *mac/inst/*rst_reg*/CLR}]
if {[llength $async_rst]} {set_false_path -to $async_rst}

set buffer_async_rst [get_pins -hier -filter {NAME =~ *eth_buf/inst/*rst_sync_reg*/PRE || NAME =~ *eth_buf/inst/*rst_sync_reg*/CLR}]
if {[llength $buffer_async_rst]} {set_false_path -to $buffer_async_rst}

set gtx_async_pins [get_pins -hier -filter {NAME =~ *mac/inst/gtx_rst_sync_reg*/PRE}]
if {[llength $gtx_async_pins]} {set_false_path -to $gtx_async_pins}

set idelay_async [get_pins -hier -filter {NAME =~ *mac/inst/delay_rst_sync_reg*/PRE}]
if {[llength $idelay_async]} {set_false_path -to $idelay_async}
foreach p {2 3} {
 set dly [get_cells -hier -filter "NAME =~ VCU_INIT_i/pl_eth$p/mac/inst/rx_delay* && (REF_NAME == IDELAYE3 || REF_NAME == IDELAYCTRL)"]
 if {[llength $dly]!=6} {error "Expected five input delays and one controller for eth$p"}
 set_property IODELAY_GROUP open_eth${p}_rx $dly
}

# MDIO changes only at MDC falling edges; DIV>=19 gives >=200ns half periods.
# Bound fabric-to-pad delay to 20ns, leaving ample protocol setup/hold margin.
set_max_delay -datapath_only 20.000 -from [get_clocks clk_pl_0] -to [get_ports {eth2_mdio_mdc eth3_mdio_mdc eth2_mdio_mdio_io eth3_mdio_mdio_io eth2_resetn* eth3_resetn*}]

# Keep the sampling clock root beside the corresponding RGMII input bank.
foreach port {2 3} region {X1Y3 X1Y2} {
    set io_buf [get_cells -hier -filter "NAME =~ *pl_eth${port}*clk_io_bufg"]
    if {[llength $io_buf] != 1} {error "Missing dedicated RGMII IO clock buffer $port"}
    set_property USER_CLOCK_ROOT $region [get_nets -of_objects [get_pins $io_buf/O]]
}

