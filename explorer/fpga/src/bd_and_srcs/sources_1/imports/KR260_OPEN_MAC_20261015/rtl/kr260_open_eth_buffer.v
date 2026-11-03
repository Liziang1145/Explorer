// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module kr260_open_eth_buffer(
(* X_INTERFACE_INFO="xilinx.com:signal:interrupt:1.0 interrupt INTERRUPT" *)
(* X_INTERFACE_MODE="master interrupt" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME interrupt, SENSITIVITY LEVEL_HIGH, PortWidth 1" *)
output wire INTERRUPT,
(* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 S_AXI_ACLK CLK" *)
(* X_INTERFACE_MODE="slave S_AXI_ACLK" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME S_AXI_ACLK, ASSOCIATED_BUSIF S_AXI:S_AXI_2TEMAC, ASSOCIATED_RESET S_AXI_ARESETN, FREQ_HZ 99999001, FREQ_TOLERANCE_HZ 0, PHASE 0.0, INSERT_VIP 0" *)
input wire S_AXI_ACLK,
(* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 S_AXI_ARESETN RST" *)
(* X_INTERFACE_MODE="slave S_AXI_ARESETN" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME S_AXI_ARESETN, POLARITY ACTIVE_LOW, INSERT_VIP 0" *)
input wire S_AXI_ARESETN,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWADDR" *)
(* X_INTERFACE_MODE="slave S_AXI" *)
input wire [17:0] S_AXI_AWADDR,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWVALID" *)
input wire S_AXI_AWVALID,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWREADY" *)
output wire S_AXI_AWREADY,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WDATA" *)
input wire [31:0] S_AXI_WDATA,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WSTRB" *)
input wire [3:0] S_AXI_WSTRB,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WVALID" *)
input wire S_AXI_WVALID,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WREADY" *)
output wire S_AXI_WREADY,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BRESP" *)
output wire [1:0] S_AXI_BRESP,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BVALID" *)
output wire S_AXI_BVALID,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BREADY" *)
input wire S_AXI_BREADY,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARADDR" *)
input wire [17:0] S_AXI_ARADDR,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARVALID" *)
input wire S_AXI_ARVALID,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARREADY" *)
output wire S_AXI_ARREADY,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RDATA" *)
output wire [31:0] S_AXI_RDATA,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RRESP" *)
output wire [1:0] S_AXI_RRESP,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RVALID" *)
output wire S_AXI_RVALID,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RREADY" *)
input wire S_AXI_RREADY,
(* X_INTERFACE_INFO="xilinx.com:signal:interrupt:1.0 EMAC_CLIENT_AUTONEG_INT INTERRUPT" *)
(* X_INTERFACE_MODE="slave EMAC_CLIENT_AUTONEG_INT" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME EMAC_CLIENT_AUTONEG_INT, SENSITIVITY EDGE_RISING, PortWidth 1" *)
input wire EMAC_CLIENT_AUTONEG_INT,

input wire EMAC_RESET_DONE_INT,

input wire EMAC_RX_DCM_LOCKED_INT,

input wire [15:0] PCSPMA_STATUS_VECTOR,
(* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 AXI_STR_TXD_ACLK CLK" *)
(* X_INTERFACE_MODE="slave AXI_STR_TXD_ACLK" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME AXI_STR_TXD_ACLK, ASSOCIATED_BUSIF AXI_STR_TXD, ASSOCIATED_RESET AXI_STR_TXD_ARESETN, FREQ_HZ 125000000, FREQ_TOLERANCE_HZ 0, PHASE 0.0, INSERT_VIP 0" *)
input wire AXI_STR_TXD_ACLK,
(* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 AXI_STR_TXD_ARESETN RST" *)
(* X_INTERFACE_MODE="slave AXI_STR_TXD_ARESETN" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME AXI_STR_TXD_ARESETN, POLARITY ACTIVE_LOW, INSERT_VIP 0" *)
input wire AXI_STR_TXD_ARESETN,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_TXD TVALID" *)
(* X_INTERFACE_MODE="slave AXI_STR_TXD" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME AXI_STR_TXD, FREQ_HZ 125000000, TDATA_NUM_BYTES 4, TDEST_WIDTH 0, TID_WIDTH 0, TUSER_WIDTH 0, HAS_TREADY 1, HAS_TSTRB 0, HAS_TKEEP 1, HAS_TLAST 1, PHASE 0.0, LAYERED_METADATA undef, INSERT_VIP 0" *)
input wire AXI_STR_TXD_TVALID,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_TXD TREADY" *)
output wire AXI_STR_TXD_TREADY,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_TXD TLAST" *)
input wire AXI_STR_TXD_TLAST,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_TXD TKEEP" *)
input wire [3:0] AXI_STR_TXD_TKEEP,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_TXD TDATA" *)
input wire [31:0] AXI_STR_TXD_TDATA,
(* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 AXI_STR_TXC_ACLK CLK" *)
(* X_INTERFACE_MODE="slave AXI_STR_TXC_ACLK" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME AXI_STR_TXC_ACLK, ASSOCIATED_BUSIF AXI_STR_TXC, ASSOCIATED_RESET AXI_STR_TXC_ARESETN, FREQ_HZ 125000000, FREQ_TOLERANCE_HZ 0, PHASE 0.0, INSERT_VIP 0" *)
input wire AXI_STR_TXC_ACLK,
(* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 AXI_STR_TXC_ARESETN RST" *)
(* X_INTERFACE_MODE="slave AXI_STR_TXC_ARESETN" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME AXI_STR_TXC_ARESETN, POLARITY ACTIVE_LOW, INSERT_VIP 0" *)
input wire AXI_STR_TXC_ARESETN,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_TXC TVALID" *)
(* X_INTERFACE_MODE="slave AXI_STR_TXC" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME AXI_STR_TXC, FREQ_HZ 125000000, TDATA_NUM_BYTES 4, TDEST_WIDTH 0, TID_WIDTH 0, TUSER_WIDTH 0, HAS_TREADY 1, HAS_TSTRB 0, HAS_TKEEP 1, HAS_TLAST 1, PHASE 0.0, LAYERED_METADATA undef, INSERT_VIP 0" *)
input wire AXI_STR_TXC_TVALID,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_TXC TREADY" *)
output wire AXI_STR_TXC_TREADY,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_TXC TLAST" *)
input wire AXI_STR_TXC_TLAST,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_TXC TKEEP" *)
input wire [3:0] AXI_STR_TXC_TKEEP,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_TXC TDATA" *)
input wire [31:0] AXI_STR_TXC_TDATA,
(* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 AXI_STR_RXD_ACLK CLK" *)
(* X_INTERFACE_MODE="slave AXI_STR_RXD_ACLK" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME AXI_STR_RXD_ACLK, ASSOCIATED_BUSIF AXI_STR_RXD, ASSOCIATED_RESET AXI_STR_RXD_ARESETN, FREQ_HZ 125000000, FREQ_TOLERANCE_HZ 0, PHASE 0.0, INSERT_VIP 0" *)
input wire AXI_STR_RXD_ACLK,
(* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 AXI_STR_RXD_ARESETN RST" *)
(* X_INTERFACE_MODE="slave AXI_STR_RXD_ARESETN" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME AXI_STR_RXD_ARESETN, POLARITY ACTIVE_LOW, INSERT_VIP 0" *)
input wire AXI_STR_RXD_ARESETN,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_RXD TVALID" *)
(* X_INTERFACE_MODE="master AXI_STR_RXD" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME AXI_STR_RXD, FREQ_HZ 125000000, TDATA_NUM_BYTES 4, TDEST_WIDTH 0, TID_WIDTH 0, TUSER_WIDTH 0, HAS_TREADY 1, HAS_TSTRB 0, HAS_TKEEP 1, HAS_TLAST 1, PHASE 0.0, LAYERED_METADATA undef, INSERT_VIP 0" *)
output wire AXI_STR_RXD_VALID,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_RXD TREADY" *)
input wire AXI_STR_RXD_READY,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_RXD TLAST" *)
output wire AXI_STR_RXD_LAST,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_RXD TKEEP" *)
output wire [3:0] AXI_STR_RXD_KEEP,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_RXD TDATA" *)
output wire [31:0] AXI_STR_RXD_DATA,
(* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 AXI_STR_RXS_ACLK CLK" *)
(* X_INTERFACE_MODE="slave AXI_STR_RXS_ACLK" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME AXI_STR_RXS_ACLK, ASSOCIATED_BUSIF AXI_STR_RXS, ASSOCIATED_RESET AXI_STR_RXS_ARESETN, FREQ_HZ 125000000, FREQ_TOLERANCE_HZ 0, PHASE 0.0, INSERT_VIP 0" *)
input wire AXI_STR_RXS_ACLK,
(* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 AXI_STR_RXS_ARESETN RST" *)
(* X_INTERFACE_MODE="slave AXI_STR_RXS_ARESETN" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME AXI_STR_RXS_ARESETN, POLARITY ACTIVE_LOW, INSERT_VIP 0" *)
input wire AXI_STR_RXS_ARESETN,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_RXS TVALID" *)
(* X_INTERFACE_MODE="master AXI_STR_RXS" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME AXI_STR_RXS, FREQ_HZ 125000000, TDATA_NUM_BYTES 4, TDEST_WIDTH 0, TID_WIDTH 0, TUSER_WIDTH 0, HAS_TREADY 1, HAS_TSTRB 0, HAS_TKEEP 1, HAS_TLAST 1, PHASE 0.0, LAYERED_METADATA undef, INSERT_VIP 0" *)
output wire AXI_STR_RXS_VALID,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_RXS TREADY" *)
input wire AXI_STR_RXS_READY,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_RXS TLAST" *)
output wire AXI_STR_RXS_LAST,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_RXS TKEEP" *)
output wire [3:0] AXI_STR_RXS_KEEP,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 AXI_STR_RXS TDATA" *)
output wire [31:0] AXI_STR_RXS_DATA,

output wire pause_req,

output wire [16:31] pause_val,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI_2TEMAC AWADDR" *)
(* X_INTERFACE_MODE="master S_AXI_2TEMAC" *)
output wire [11:0] S_AXI_2TEMAC_AWADDR,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI_2TEMAC AWVALID" *)
output wire S_AXI_2TEMAC_AWVALID,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI_2TEMAC AWREADY" *)
input wire S_AXI_2TEMAC_AWREADY,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI_2TEMAC WDATA" *)
output wire [31:0] S_AXI_2TEMAC_WDATA,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI_2TEMAC WVALID" *)
output wire S_AXI_2TEMAC_WVALID,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI_2TEMAC WREADY" *)
input wire S_AXI_2TEMAC_WREADY,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI_2TEMAC BRESP" *)
input wire [1:0] S_AXI_2TEMAC_BRESP,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI_2TEMAC BVALID" *)
input wire S_AXI_2TEMAC_BVALID,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI_2TEMAC BREADY" *)
output wire S_AXI_2TEMAC_BREADY,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI_2TEMAC ARADDR" *)
output wire [11:0] S_AXI_2TEMAC_ARADDR,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI_2TEMAC ARVALID" *)
output wire S_AXI_2TEMAC_ARVALID,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI_2TEMAC ARREADY" *)
input wire S_AXI_2TEMAC_ARREADY,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI_2TEMAC RDATA" *)
input wire [31:0] S_AXI_2TEMAC_RDATA,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI_2TEMAC RRESP" *)
input wire [1:0] S_AXI_2TEMAC_RRESP,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI_2TEMAC RVALID" *)
input wire S_AXI_2TEMAC_RVALID,
(* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI_2TEMAC RREADY" *)
output wire S_AXI_2TEMAC_RREADY,
(* X_INTERFACE_INFO="xilinx.com:signal:clockenable:1.0 RX_CLK_ENABLE_IN CE" *)
(* X_INTERFACE_MODE="slave RX_CLK_ENABLE_IN" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME RX_CLK_ENABLE_IN, POLARITY ACTIVE_LOW" *)
input wire RX_CLK_ENABLE_IN,

input wire [27:0] rx_statistics_vector,

input wire rx_statistics_valid,
(* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 rx_mac_aclk CLK" *)
(* X_INTERFACE_MODE="slave rx_mac_aclk" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME rx_mac_aclk, ASSOCIATED_BUSIF RX_AXIS_MAC, FREQ_HZ 125000000, FREQ_TOLERANCE_HZ 0, PHASE 0.0, INSERT_VIP 0" *)
input wire rx_mac_aclk,
(* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 rx_reset RST" *)
(* X_INTERFACE_MODE="slave rx_reset" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME rx_reset, POLARITY ACTIVE_HIGH, INSERT_VIP 0" *)
input wire rx_reset,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 RX_AXIS_MAC TDATA" *)
(* X_INTERFACE_MODE="slave RX_AXIS_MAC" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME RX_AXIS_MAC, FREQ_HZ 125000000, TDATA_NUM_BYTES 1, TDEST_WIDTH 0, TID_WIDTH 0, TUSER_WIDTH 1, HAS_TREADY 0, HAS_TSTRB 0, HAS_TKEEP 0, HAS_TLAST 1, PHASE 0.0, LAYERED_METADATA undef, INSERT_VIP 0" *)
input wire [7:0] rx_axis_mac_tdata,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 RX_AXIS_MAC TVALID" *)
input wire rx_axis_mac_tvalid,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 RX_AXIS_MAC TLAST" *)
input wire rx_axis_mac_tlast,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 RX_AXIS_MAC TUSER" *)
input wire rx_axis_mac_tuser,

output wire [24:31] tx_ifg_delay,
(* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 tx_mac_aclk CLK" *)
(* X_INTERFACE_MODE="slave tx_mac_aclk" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME tx_mac_aclk, ASSOCIATED_BUSIF TX_AXIS_MAC, FREQ_HZ 125000000, FREQ_TOLERANCE_HZ 0, PHASE 0.0, INSERT_VIP 0" *)
input wire tx_mac_aclk,
(* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 tx_reset RST" *)
(* X_INTERFACE_MODE="slave tx_reset" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME tx_reset, POLARITY ACTIVE_HIGH, INSERT_VIP 0" *)
input wire tx_reset,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 TX_AXIS_MAC TDATA" *)
(* X_INTERFACE_MODE="master TX_AXIS_MAC" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME TX_AXIS_MAC, FREQ_HZ 125000000, TDATA_NUM_BYTES 1, TDEST_WIDTH 0, TID_WIDTH 0, TUSER_WIDTH 1, HAS_TREADY 1, HAS_TSTRB 0, HAS_TKEEP 0, HAS_TLAST 1, PHASE 0.0, LAYERED_METADATA undef, INSERT_VIP 0" *)
output wire [7:0] tx_axis_mac_tdata,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 TX_AXIS_MAC TVALID" *)
output wire tx_axis_mac_tvalid,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 TX_AXIS_MAC TLAST" *)
output wire tx_axis_mac_tlast,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 TX_AXIS_MAC TUSER" *)
output wire [0:0] tx_axis_mac_tuser,
(* X_INTERFACE_INFO="xilinx.com:interface:axis:1.0 TX_AXIS_MAC TREADY" *)
input wire tx_axis_mac_tready,

input wire speed_is_10_100,
(* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 RESET2PCSPMA RST" *)
(* X_INTERFACE_MODE="master RESET2PCSPMA" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME RESET2PCSPMA, POLARITY ACTIVE_HIGH, INSERT_VIP 0" *)
output wire RESET2PCSPMA,
(* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 RESET2TEMACn RST" *)
(* X_INTERFACE_MODE="master RESET2TEMACn" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME RESET2TEMACn, POLARITY ACTIVE_LOW, INSERT_VIP 0" *)
output wire RESET2TEMACn,
(* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 PHY_RST_N RST" *)
(* X_INTERFACE_MODE="master PHY_RST_N" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME PHY_RST_N, BOARD.ASSOCIATED_PARAM PHYRST_BOARD_INTERFACE, POLARITY ACTIVE_LOW, INSERT_VIP 0" *)
output wire PHY_RST_N,
(* X_INTERFACE_INFO="xilinx.com:interface:mdio:1.0 mdio_to_top MDIO_I" *)
(* X_INTERFACE_MODE="master mdio_to_top" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME mdio_to_top, BOARD.ASSOCIATED_PARAM MDIO_BOARD_INTERFACE, CAN_DEBUG false" *)
input wire mdio_i_top,
(* X_INTERFACE_INFO="xilinx.com:interface:mdio:1.0 mdio_to_top MDIO_O" *)
output wire mdio_o_top,
(* X_INTERFACE_INFO="xilinx.com:interface:mdio:1.0 mdio_to_top MDIO_T" *)
output wire mdio_t_top,
(* X_INTERFACE_INFO="xilinx.com:interface:mdio:1.0 mdio_to_top MDC" *)
output wire mdc_top,

input wire mdio_t_pcspma,

input wire mdio_o_pcspma,
(* X_INTERFACE_INFO="xilinx.com:interface:mdio:1.0 mdio_temac MDIO_I" *)
(* X_INTERFACE_MODE="mirroredMaster mdio_temac" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME mdio_temac, CAN_DEBUG false" *)
output wire mdio_i_temac,
(* X_INTERFACE_INFO="xilinx.com:interface:mdio:1.0 mdio_temac MDIO_O" *)
input wire mdio_o_temac,
(* X_INTERFACE_INFO="xilinx.com:interface:mdio:1.0 mdio_temac MDIO_T" *)
input wire mdio_t_temac,
(* X_INTERFACE_INFO="xilinx.com:interface:mdio:1.0 mdio_temac MDC" *)
input wire mdc_temac,
(* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 GTX_CLK CLK" *)
(* X_INTERFACE_MODE="slave GTX_CLK" *)
(* X_INTERFACE_PARAMETER="XIL_INTERFACENAME GTX_CLK, FREQ_HZ 125000000, FREQ_TOLERANCE_HZ 0, PHASE 0.0, INSERT_VIP 0" *)
input wire GTX_CLK
);
assign S_AXI_2TEMAC_AWADDR=S_AXI_AWADDR[11:0];
assign S_AXI_2TEMAC_AWVALID=S_AXI_AWVALID;
assign S_AXI_2TEMAC_WDATA=S_AXI_WDATA;
assign S_AXI_2TEMAC_WVALID=S_AXI_WVALID;
assign S_AXI_2TEMAC_BREADY=S_AXI_BREADY;
assign S_AXI_2TEMAC_ARADDR=S_AXI_ARADDR[11:0];
assign S_AXI_2TEMAC_ARVALID=S_AXI_ARVALID;
assign S_AXI_2TEMAC_RREADY=S_AXI_RREADY;
assign S_AXI_AWREADY=S_AXI_2TEMAC_AWREADY;
assign S_AXI_WREADY=S_AXI_2TEMAC_WREADY;
assign S_AXI_BRESP=S_AXI_2TEMAC_BRESP;
assign S_AXI_BVALID=S_AXI_2TEMAC_BVALID;
assign S_AXI_ARREADY=S_AXI_2TEMAC_ARREADY;
assign S_AXI_RDATA=S_AXI_2TEMAC_RDATA;
assign S_AXI_RRESP=S_AXI_2TEMAC_RRESP;
assign S_AXI_RVALID=S_AXI_2TEMAC_RVALID;
assign INTERRUPT=0;assign RESET2TEMACn=S_AXI_ARESETN;assign RESET2PCSPMA=!S_AXI_ARESETN;assign PHY_RST_N=S_AXI_ARESETN;
assign pause_req=0;assign pause_val=0;assign tx_ifg_delay=0;
assign mdio_o_top=mdio_o_temac;assign mdio_t_top=mdio_t_temac;assign mdc_top=mdc_temac;assign mdio_i_temac=mdio_i_top;
wire txs_async_rst=!AXI_STR_TXD_ARESETN||!AXI_STR_TXC_ARESETN||tx_reset;
wire rxm_async_rst=!AXI_STR_RXD_ARESETN||!AXI_STR_RXS_ARESETN||rx_reset;
(* ASYNC_REG="TRUE" *) reg [3:0] txs_rst_sync=4'hf,rxm_rst_sync=4'hf;
always @(posedge AXI_STR_TXD_ACLK or posedge txs_async_rst)
 if(txs_async_rst)txs_rst_sync<=4'hf;else txs_rst_sync<={txs_rst_sync[2:0],1'b0};
always @(posedge AXI_STR_RXD_ACLK or posedge rxm_async_rst)
 if(rxm_async_rst)rxm_rst_sync<=4'hf;else rxm_rst_sync<={rxm_rst_sync[2:0],1'b0};
wire txs_rst=txs_rst_sync[3];
wire rxm_rst=rxm_rst_sync[3];
reg ctrl_done=0;
assign AXI_STR_TXC_TREADY=!ctrl_done&&!txs_rst;
wire tx_fifo_ready;
assign AXI_STR_TXD_TREADY=tx_fifo_ready&&ctrl_done&&!txs_rst;
always @(posedge AXI_STR_TXD_ACLK) begin
 if(txs_rst)ctrl_done<=0;
 else begin
  if(AXI_STR_TXC_TVALID&&AXI_STR_TXC_TREADY&&AXI_STR_TXC_TLAST)ctrl_done<=1;
  if(AXI_STR_TXD_TVALID&&AXI_STR_TXD_TREADY&&AXI_STR_TXD_TLAST)ctrl_done<=0;
 end
end
axis_async_fifo_adapter #(.DEPTH(16384),.S_DATA_WIDTH(32),.M_DATA_WIDTH(8),.FRAME_FIFO(1),.DROP_BAD_FRAME(1)) tx_fifo(
 .s_clk(AXI_STR_TXD_ACLK),.s_rst(txs_rst),.s_axis_tdata(AXI_STR_TXD_TDATA),.s_axis_tkeep(AXI_STR_TXD_TKEEP),.s_axis_tvalid(AXI_STR_TXD_TVALID&&ctrl_done),.s_axis_tready(tx_fifo_ready),.s_axis_tlast(AXI_STR_TXD_TLAST),.s_axis_tid(8'b0),.s_axis_tdest(8'b0),.s_axis_tuser(1'b0),
 .m_clk(tx_mac_aclk),.m_rst(tx_reset),.m_axis_tdata(tx_axis_mac_tdata),.m_axis_tvalid(tx_axis_mac_tvalid),.m_axis_tready(tx_axis_mac_tready),.m_axis_tlast(tx_axis_mac_tlast),.m_axis_tuser(tx_axis_mac_tuser),.s_pause_req(1'b0),.m_pause_req(1'b0));
wire rx_commit,meta_ready,meta_valid,meta_pop,rx_fifo_valid,rx_fifo_ready;
wire [127:0] meta_out;
reg [127:0] meta_in=0;
reg [15:0] rx_len=0;reg [47:0] rx_dest=0;reg [15:0] rx_type=0,rx_tag=0;
always @(posedge rx_mac_aclk) begin
 if(rx_reset)begin rx_len<=0;rx_dest<=0;rx_type<=0;rx_tag<=0;meta_in<=0;end
 else if(rx_axis_mac_tvalid)begin
  if(rx_len<6)rx_dest[rx_len*8+:8]<=rx_axis_mac_tdata;
  if(rx_len==12)rx_type[15:8]<=rx_axis_mac_tdata;
  if(rx_len==13)rx_type[7:0]<=rx_axis_mac_tdata;
  if(rx_len==14)rx_tag[15:8]<=rx_axis_mac_tdata;
  if(rx_len==15)rx_tag[7:0]<=rx_axis_mac_tdata;
  if(rx_axis_mac_tlast)begin
   meta_in<={16'b0,rx_tag,rx_type,rx_dest,16'b0,(rx_len+16'd1)};rx_len<=0;
  end else rx_len<=rx_len+1'b1;
 end
end
axis_async_fifo_adapter #(.DEPTH(32768),.S_DATA_WIDTH(8),.M_DATA_WIDTH(32),.FRAME_FIFO(1),.DROP_BAD_FRAME(1),.DROP_WHEN_FULL(1)) rx_fifo(
 .s_clk(rx_mac_aclk),.s_rst(rx_reset),.s_axis_tdata(rx_axis_mac_tdata),.s_axis_tkeep(1'b1),.s_axis_tvalid(rx_axis_mac_tvalid),.s_axis_tlast(rx_axis_mac_tlast),.s_axis_tid(8'b0),.s_axis_tdest(8'b0),.s_axis_tuser(rx_axis_mac_tuser),.s_status_good_frame(rx_commit),
 .m_clk(AXI_STR_RXD_ACLK),.m_rst(rxm_rst),.m_axis_tdata(AXI_STR_RXD_DATA),.m_axis_tkeep(AXI_STR_RXD_KEEP),.m_axis_tvalid(rx_fifo_valid),.m_axis_tready(rx_fifo_ready),.m_axis_tlast(AXI_STR_RXD_LAST),.s_pause_req(1'b0),.m_pause_req(1'b0));
// Metadata capacity exceeds maximum number of legal frames in the data FIFO.
axis_async_fifo #(.DEPTH(1024),.DATA_WIDTH(128),.KEEP_ENABLE(0),.KEEP_WIDTH(1),.ID_ENABLE(0),.DEST_ENABLE(0),.USER_ENABLE(0)) metadata_fifo(
 .s_clk(rx_mac_aclk),.s_rst(rx_reset),.s_axis_tdata(meta_in),.s_axis_tkeep(1'b1),.s_axis_tvalid(rx_commit),.s_axis_tready(meta_ready),.s_axis_tlast(1'b1),.s_axis_tid(8'b0),.s_axis_tdest(8'b0),.s_axis_tuser(1'b0),
 .m_clk(AXI_STR_RXD_ACLK),.m_rst(rxm_rst),.m_axis_tdata(meta_out),.m_axis_tvalid(meta_valid),.m_axis_tready(meta_pop),.s_pause_req(1'b0),.m_pause_req(1'b0));
reg [2:0] status_index=0;reg data_phase=0;
wire vlan_frame=meta_out[95:80]==16'h8100||meta_out[95:80]==16'h88a8;
wire multicast=meta_out[32];wire broadcast=&meta_out[79:32];
assign AXI_STR_RXS_KEEP=4'hf;
assign AXI_STR_RXS_VALID=meta_valid&&!data_phase&&!rxm_rst;
assign AXI_STR_RXS_LAST=status_index==5;
assign AXI_STR_RXS_DATA=status_index==0?32'h50000000:
 status_index==1?{16'b0,meta_out[79:64]}:
 status_index==2?meta_out[63:32]:
 status_index==3?{4'b0,vlan_frame,2'b0,meta_out[13:0],multicast,broadcast,2'b0,1'b1,3'b0,broadcast,1'b0,multicast}:
 status_index==4?{meta_out[95:80],16'b0}:{meta_out[111:96],meta_out[15:0]};
assign AXI_STR_RXD_VALID=rx_fifo_valid&&data_phase&&!rxm_rst;
assign rx_fifo_ready=AXI_STR_RXD_READY&&data_phase&&!rxm_rst;
assign meta_pop=AXI_STR_RXD_VALID&&AXI_STR_RXD_READY&&AXI_STR_RXD_LAST;
always @(posedge AXI_STR_RXD_ACLK)begin
 if(rxm_rst)begin status_index<=0;data_phase<=0;end
 else begin
  if(AXI_STR_RXS_VALID&&AXI_STR_RXS_READY)begin
   if(status_index==5)begin status_index<=0;data_phase<=1;end else status_index<=status_index+1'b1;
  end
  if(meta_pop)data_phase<=0;
 end
end
endmodule
