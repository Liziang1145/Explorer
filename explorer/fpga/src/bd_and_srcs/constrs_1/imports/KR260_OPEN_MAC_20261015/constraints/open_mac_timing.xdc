# Worst-case 1Gbps RGMII; PHY RX/TX internal delay 2ns; edge-aligned FPGA TX.
create_clock -name eth2_rx -period 8.000 [get_ports eth2_rgmii_rxc]
create_clock -name eth2_rx_virtual -period 8.000
create_generated_clock -name eth2_tx -source [get_pins VCU_INIT_i/eth_clock/clk_out1] -divide_by 1 [get_ports eth2_rgmii_txc]
set_input_delay -clock eth2_rx_virtual -max -1.000 [get_ports {eth2_rgmii_rd* eth2_rgmii_rx_ctl}]
set_input_delay -clock eth2_rx_virtual -min -3.000 [get_ports {eth2_rgmii_rd* eth2_rgmii_rx_ctl}]
set_input_delay -clock eth2_rx_virtual -clock_fall -add_delay -max -1.000 [get_ports {eth2_rgmii_rd* eth2_rgmii_rx_ctl}]
set_input_delay -clock eth2_rx_virtual -clock_fall -add_delay -min -3.000 [get_ports {eth2_rgmii_rd* eth2_rgmii_rx_ctl}]
set_output_delay -clock eth2_tx -max -0.750 [get_ports {eth2_rgmii_td* eth2_rgmii_tx_ctl}]
set_output_delay -clock eth2_tx -min -3.000 [get_ports {eth2_rgmii_td* eth2_rgmii_tx_ctl}]
set_output_delay -clock eth2_tx -clock_fall -add_delay -max -0.750 [get_ports {eth2_rgmii_td* eth2_rgmii_tx_ctl}]
set_output_delay -clock eth2_tx -clock_fall -add_delay -min -3.000 [get_ports {eth2_rgmii_td* eth2_rgmii_tx_ctl}]
create_clock -name eth3_rx -period 8.000 [get_ports eth3_rgmii_rxc]
create_clock -name eth3_rx_virtual -period 8.000
create_generated_clock -name eth3_tx -source [get_pins VCU_INIT_i/eth_clock/clk_out1] -divide_by 1 [get_ports eth3_rgmii_txc]
set_input_delay -clock eth3_rx_virtual -max -1.000 [get_ports {eth3_rgmii_rd* eth3_rgmii_rx_ctl}]
set_input_delay -clock eth3_rx_virtual -min -3.000 [get_ports {eth3_rgmii_rd* eth3_rgmii_rx_ctl}]
set_input_delay -clock eth3_rx_virtual -clock_fall -add_delay -max -1.000 [get_ports {eth3_rgmii_rd* eth3_rgmii_rx_ctl}]
set_input_delay -clock eth3_rx_virtual -clock_fall -add_delay -min -3.000 [get_ports {eth3_rgmii_rd* eth3_rgmii_rx_ctl}]
set_output_delay -clock eth3_tx -max -0.750 [get_ports {eth3_rgmii_td* eth3_rgmii_tx_ctl}]
set_output_delay -clock eth3_tx -min -3.000 [get_ports {eth3_rgmii_td* eth3_rgmii_tx_ctl}]
set_output_delay -clock eth3_tx -clock_fall -add_delay -max -0.750 [get_ports {eth3_rgmii_td* eth3_rgmii_tx_ctl}]
set_output_delay -clock eth3_tx -clock_fall -add_delay -min -3.000 [get_ports {eth3_rgmii_td* eth3_rgmii_tx_ctl}]

# Input data precedes the corresponding clock edge; hold checks use the next opposite edge.
set_false_path -rise_from [get_clocks eth2_rx_virtual] -fall_to [get_clocks eth2_rx] -setup
set_false_path -fall_from [get_clocks eth2_rx_virtual] -rise_to [get_clocks eth2_rx] -setup
set_false_path -rise_from [get_clocks eth2_rx_virtual] -rise_to [get_clocks eth2_rx] -hold
set_false_path -fall_from [get_clocks eth2_rx_virtual] -fall_to [get_clocks eth2_rx] -hold
set_multicycle_path -from [get_clocks eth2_rx_virtual] -to [get_clocks eth2_rx] -setup 0
set_multicycle_path -from [get_clocks eth2_rx_virtual] -to [get_clocks eth2_rx] -hold -1

# Input data precedes the corresponding clock edge; hold checks use the next opposite edge.
set_false_path -rise_from [get_clocks eth3_rx_virtual] -fall_to [get_clocks eth3_rx] -setup
set_false_path -fall_from [get_clocks eth3_rx_virtual] -rise_to [get_clocks eth3_rx] -setup
set_false_path -rise_from [get_clocks eth3_rx_virtual] -rise_to [get_clocks eth3_rx] -hold
set_false_path -fall_from [get_clocks eth3_rx_virtual] -fall_to [get_clocks eth3_rx] -hold
set_multicycle_path -from [get_clocks eth3_rx_virtual] -to [get_clocks eth3_rx] -setup 0
set_multicycle_path -from [get_clocks eth3_rx_virtual] -to [get_clocks eth3_rx] -hold -1

# DP83867 receiver budget, TI SNLA243 Table3: setup0.5, hold0.25,
# internal-delay variation0.2, IOskew0.35, PCBskew0.2, internal TXdelay2ns.
# max=0.5+0.2+0.35+0.2-2=-0.75; min=-(0.25+0.2+0.35+0.2+2)=-3.00.
# FPGA clock duty/jitter and rise/fall delays remain in propagated STA.
# Setup pairs same edges, hold checks next opposite; no output timing is waived.
set_false_path -rise_from [get_clocks clk_out1_VCU_INIT_eth_clock_0] -fall_to [get_clocks eth2_tx] -setup
set_false_path -fall_from [get_clocks clk_out1_VCU_INIT_eth_clock_0] -rise_to [get_clocks eth2_tx] -setup
set_false_path -rise_from [get_clocks clk_out1_VCU_INIT_eth_clock_0] -rise_to [get_clocks eth2_tx] -hold
set_false_path -fall_from [get_clocks clk_out1_VCU_INIT_eth_clock_0] -fall_to [get_clocks eth2_tx] -hold
set_multicycle_path -from [get_clocks clk_out1_VCU_INIT_eth_clock_0] -to [get_clocks eth2_tx] -setup 0
set_multicycle_path -from [get_clocks clk_out1_VCU_INIT_eth_clock_0] -to [get_clocks eth2_tx] -hold -1

# DP83867 receiver budget, TI SNLA243 Table3: setup0.5, hold0.25,
# internal-delay variation0.2, IOskew0.35, PCBskew0.2, internal TXdelay2ns.
# max=0.5+0.2+0.35+0.2-2=-0.75; min=-(0.25+0.2+0.35+0.2+2)=-3.00.
# FPGA clock duty/jitter and rise/fall delays remain in propagated STA.
# Setup pairs same edges, hold checks next opposite; no output timing is waived.
set_false_path -rise_from [get_clocks clk_out1_VCU_INIT_eth_clock_0] -fall_to [get_clocks eth3_tx] -setup
set_false_path -fall_from [get_clocks clk_out1_VCU_INIT_eth_clock_0] -rise_to [get_clocks eth3_tx] -setup
set_false_path -rise_from [get_clocks clk_out1_VCU_INIT_eth_clock_0] -rise_to [get_clocks eth3_tx] -hold
set_false_path -fall_from [get_clocks clk_out1_VCU_INIT_eth_clock_0] -fall_to [get_clocks eth3_tx] -hold
set_multicycle_path -from [get_clocks clk_out1_VCU_INIT_eth_clock_0] -to [get_clocks eth3_tx] -setup 0
set_multicycle_path -from [get_clocks clk_out1_VCU_INIT_eth_clock_0] -to [get_clocks eth3_tx] -hold -1
