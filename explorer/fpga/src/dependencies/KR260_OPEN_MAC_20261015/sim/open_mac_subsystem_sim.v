module open_mac_subsystem_sim
   (gtx_clk90,
    axi_rxd_arstn,
    axi_rxs_arstn,
    axi_txc_arstn,
    axi_txd_arstn,
    axis_clk,
    gtx_clk,
    interrupt,
    m_axis_rxd_tdata,
    m_axis_rxd_tkeep,
    m_axis_rxd_tlast,
    m_axis_rxd_tready,
    m_axis_rxd_tvalid,
    m_axis_rxs_tdata,
    m_axis_rxs_tkeep,
    m_axis_rxs_tlast,
    m_axis_rxs_tready,
    m_axis_rxs_tvalid,
    mac_irq,
    mdio_mdc,
    mdio_mdio_i,
    mdio_mdio_o,
    mdio_mdio_t,
    phy_rst_n,
    ref_clk,
    rgmii_rd,
    rgmii_rx_ctl,
    rgmii_rxc,
    rgmii_td,
    rgmii_tx_ctl,
    rgmii_txc,
    s_axi_araddr,
    s_axi_arready,
    s_axi_arvalid,
    s_axi_awaddr,
    s_axi_awready,
    s_axi_awvalid,
    s_axi_bready,
    s_axi_bresp,
    s_axi_bvalid,
    s_axi_lite_clk,
    s_axi_lite_resetn,
    s_axi_rdata,
    s_axi_rready,
    s_axi_rresp,
    s_axi_rvalid,
    s_axi_wdata,
    s_axi_wready,
    s_axi_wstrb,
    s_axi_wvalid,
    s_axis_txc_tdata,
    s_axis_txc_tkeep,
    s_axis_txc_tlast,
    s_axis_txc_tready,
    s_axis_txc_tvalid,
    s_axis_txd_tdata,
    s_axis_txd_tkeep,
    s_axis_txd_tlast,
    s_axis_txd_tready,
    s_axis_txd_tvalid);
    input gtx_clk90;
 input axi_rxd_arstn;
    input axi_rxs_arstn;
    input axi_txc_arstn;
    input axi_txd_arstn;
    input axis_clk;
    input gtx_clk;
    output interrupt;
     output [31:0]m_axis_rxd_tdata;
   output [3:0]m_axis_rxd_tkeep;
   output m_axis_rxd_tlast;
   input m_axis_rxd_tready;
   output m_axis_rxd_tvalid;
     output [31:0]m_axis_rxs_tdata;
   output [3:0]m_axis_rxs_tkeep;
   output m_axis_rxs_tlast;
   input m_axis_rxs_tready;
   output m_axis_rxs_tvalid;
    output mac_irq;
     output mdio_mdc;
   input mdio_mdio_i;
   output mdio_mdio_o;
   output mdio_mdio_t;
    output [0:0]phy_rst_n;
    input ref_clk;
    input [3:0]rgmii_rd;
   input rgmii_rx_ctl;
   input rgmii_rxc;
   output [3:0]rgmii_td;
   output rgmii_tx_ctl;
   output rgmii_txc;
     input [17:0]s_axi_araddr;
   output s_axi_arready;
   input s_axi_arvalid;
   input [17:0]s_axi_awaddr;
   output s_axi_awready;
   input s_axi_awvalid;
   input s_axi_bready;
   output [1:0]s_axi_bresp;
   output s_axi_bvalid;
    input s_axi_lite_clk;
    input s_axi_lite_resetn;
   output [31:0]s_axi_rdata;
   input s_axi_rready;
   output [1:0]s_axi_rresp;
   output s_axi_rvalid;
   input [31:0]s_axi_wdata;
   output s_axi_wready;
   input [3:0]s_axi_wstrb;
   input s_axi_wvalid;
     input [31:0]s_axis_txc_tdata;
   input [3:0]s_axis_txc_tkeep;
   input s_axis_txc_tlast;
   output s_axis_txc_tready;
   input s_axis_txc_tvalid;
     input [31:0]s_axis_txd_tdata;
   input [3:0]s_axis_txd_tkeep;
   input s_axis_txd_tlast;
   output s_axis_txd_tready;
   input s_axis_txd_tvalid;

  wire axi_rxd_arstn;
  wire axi_rxs_arstn;
  wire axi_txc_arstn;
  wire axi_txd_arstn;
  wire axis_clk;
  wire c_counter_binary_0_THRESH0;
  wire eth_buf_RESET2TEMACn;
  wire [11:0]eth_buf_S_AXI_2TEMAC_ARADDR;
  wire eth_buf_S_AXI_2TEMAC_ARREADY;
  wire eth_buf_S_AXI_2TEMAC_ARVALID;
  wire [11:0]eth_buf_S_AXI_2TEMAC_AWADDR;
  wire eth_buf_S_AXI_2TEMAC_AWREADY;
  wire eth_buf_S_AXI_2TEMAC_AWVALID;
  wire eth_buf_S_AXI_2TEMAC_BREADY;
  wire [1:0]eth_buf_S_AXI_2TEMAC_BRESP;
  wire eth_buf_S_AXI_2TEMAC_BVALID;
  wire [31:0]eth_buf_S_AXI_2TEMAC_RDATA;
  wire eth_buf_S_AXI_2TEMAC_RREADY;
  wire [1:0]eth_buf_S_AXI_2TEMAC_RRESP;
  wire eth_buf_S_AXI_2TEMAC_RVALID;
  wire [31:0]eth_buf_S_AXI_2TEMAC_WDATA;
  wire eth_buf_S_AXI_2TEMAC_WREADY;
  wire eth_buf_S_AXI_2TEMAC_WVALID;
  wire [7:0]eth_buf_TX_AXIS_MAC_TDATA;
  wire eth_buf_TX_AXIS_MAC_TLAST;
  wire eth_buf_TX_AXIS_MAC_TREADY;
  wire [0:0]eth_buf_TX_AXIS_MAC_TUSER;
  wire eth_buf_TX_AXIS_MAC_TVALID;
  wire eth_buf_pause_req;
  wire [16:31]eth_buf_pause_val;
  wire [24:31]eth_buf_tx_ifg_delay;
  wire gtx_clk;
  wire [0:0]ilconstant_0_dout;
  wire [0:0]ilvector_logic_0_Res;
  wire interrupt;
  wire [31:0]m_axis_rxd_tdata;
  wire [3:0]m_axis_rxd_tkeep;
  wire m_axis_rxd_tlast;
  wire m_axis_rxd_tready;
  wire m_axis_rxd_tvalid;
  wire [31:0]m_axis_rxs_tdata;
  wire [3:0]m_axis_rxs_tkeep;
  wire m_axis_rxs_tlast;
  wire m_axis_rxs_tready;
  wire m_axis_rxs_tvalid;
  wire mac_irq;
  wire [7:0]mac_m_axis_rx_TDATA;
  wire mac_m_axis_rx_TLAST;
  wire mac_m_axis_rx_TUSER;
  wire mac_m_axis_rx_TVALID;
  wire mac_rx_enable;
  wire mac_rx_mac_aclk;
  wire mac_rx_reset;
  wire mac_rx_statistics_valid;
  wire [27:0]mac_rx_statistics_vector;
  wire mac_speedis10100;
  wire mac_tx_mac_aclk;
  wire mac_tx_reset;
  wire mdio_mdc;
  wire mdio_mdio_i;
  wire mdio_mdio_o;
  wire mdio_mdio_t;
  wire [0:0]phy_rst_n;
  wire ref_clk;
  wire [3:0]rgmii_rd;
  wire rgmii_rx_ctl;
  wire rgmii_rxc;
  wire [3:0]rgmii_td;
  wire rgmii_tx_ctl;
  wire rgmii_txc;
  wire [17:0]s_axi_araddr;
  wire s_axi_arready;
  wire s_axi_arvalid;
  wire [17:0]s_axi_awaddr;
  wire s_axi_awready;
  wire s_axi_awvalid;
  wire s_axi_bready;
  wire [1:0]s_axi_bresp;
  wire s_axi_bvalid;
  wire s_axi_lite_clk;
  wire s_axi_lite_resetn;
  wire [31:0]s_axi_rdata;
  wire s_axi_rready;
  wire [1:0]s_axi_rresp;
  wire s_axi_rvalid;
  wire [31:0]s_axi_wdata;
  wire s_axi_wready;
  wire [3:0]s_axi_wstrb;
  wire s_axi_wvalid;
  wire [31:0]s_axis_txc_tdata;
  wire [3:0]s_axis_txc_tkeep;
  wire s_axis_txc_tlast;
  wire s_axis_txc_tready;
  wire s_axis_txc_tvalid;
  wire [31:0]s_axis_txd_tdata;
  wire [3:0]s_axis_txd_tkeep;
  wire s_axis_txd_tlast;
  wire s_axis_txd_tready;
  wire s_axis_txd_tvalid;

  kr260_open_eth_buffer eth_buf
       (.AXI_STR_RXD_ACLK(axis_clk),
        .AXI_STR_RXD_ARESETN(axi_rxd_arstn),
        .AXI_STR_RXD_DATA(m_axis_rxd_tdata),
        .AXI_STR_RXD_KEEP(m_axis_rxd_tkeep),
        .AXI_STR_RXD_LAST(m_axis_rxd_tlast),
        .AXI_STR_RXD_READY(m_axis_rxd_tready),
        .AXI_STR_RXD_VALID(m_axis_rxd_tvalid),
        .AXI_STR_RXS_ACLK(axis_clk),
        .AXI_STR_RXS_ARESETN(axi_rxs_arstn),
        .AXI_STR_RXS_DATA(m_axis_rxs_tdata),
        .AXI_STR_RXS_KEEP(m_axis_rxs_tkeep),
        .AXI_STR_RXS_LAST(m_axis_rxs_tlast),
        .AXI_STR_RXS_READY(m_axis_rxs_tready),
        .AXI_STR_RXS_VALID(m_axis_rxs_tvalid),
        .AXI_STR_TXC_ACLK(axis_clk),
        .AXI_STR_TXC_ARESETN(axi_txc_arstn),
        .AXI_STR_TXC_TDATA(s_axis_txc_tdata),
        .AXI_STR_TXC_TKEEP(s_axis_txc_tkeep),
        .AXI_STR_TXC_TLAST(s_axis_txc_tlast),
        .AXI_STR_TXC_TREADY(s_axis_txc_tready),
        .AXI_STR_TXC_TVALID(s_axis_txc_tvalid),
        .AXI_STR_TXD_ACLK(axis_clk),
        .AXI_STR_TXD_ARESETN(axi_txd_arstn),
        .AXI_STR_TXD_TDATA(s_axis_txd_tdata),
        .AXI_STR_TXD_TKEEP(s_axis_txd_tkeep),
        .AXI_STR_TXD_TLAST(s_axis_txd_tlast),
        .AXI_STR_TXD_TREADY(s_axis_txd_tready),
        .AXI_STR_TXD_TVALID(s_axis_txd_tvalid),
        .EMAC_CLIENT_AUTONEG_INT(1'b0),
        .EMAC_RESET_DONE_INT(1'b1),
        .EMAC_RX_DCM_LOCKED_INT(1'b1),
        .GTX_CLK(gtx_clk),
        .INTERRUPT(interrupt),
        .PCSPMA_STATUS_VECTOR({1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0,1'b0}),
        .RESET2TEMACn(eth_buf_RESET2TEMACn),
        .RX_CLK_ENABLE_IN(mac_rx_enable),
        .S_AXI_2TEMAC_ARADDR(eth_buf_S_AXI_2TEMAC_ARADDR),
        .S_AXI_2TEMAC_ARREADY(eth_buf_S_AXI_2TEMAC_ARREADY),
        .S_AXI_2TEMAC_ARVALID(eth_buf_S_AXI_2TEMAC_ARVALID),
        .S_AXI_2TEMAC_AWADDR(eth_buf_S_AXI_2TEMAC_AWADDR),
        .S_AXI_2TEMAC_AWREADY(eth_buf_S_AXI_2TEMAC_AWREADY),
        .S_AXI_2TEMAC_AWVALID(eth_buf_S_AXI_2TEMAC_AWVALID),
        .S_AXI_2TEMAC_BREADY(eth_buf_S_AXI_2TEMAC_BREADY),
        .S_AXI_2TEMAC_BRESP(eth_buf_S_AXI_2TEMAC_BRESP),
        .S_AXI_2TEMAC_BVALID(eth_buf_S_AXI_2TEMAC_BVALID),
        .S_AXI_2TEMAC_RDATA(eth_buf_S_AXI_2TEMAC_RDATA),
        .S_AXI_2TEMAC_RREADY(eth_buf_S_AXI_2TEMAC_RREADY),
        .S_AXI_2TEMAC_RRESP(eth_buf_S_AXI_2TEMAC_RRESP),
        .S_AXI_2TEMAC_RVALID(eth_buf_S_AXI_2TEMAC_RVALID),
        .S_AXI_2TEMAC_WDATA(eth_buf_S_AXI_2TEMAC_WDATA),
        .S_AXI_2TEMAC_WREADY(eth_buf_S_AXI_2TEMAC_WREADY),
        .S_AXI_2TEMAC_WVALID(eth_buf_S_AXI_2TEMAC_WVALID),
        .S_AXI_ACLK(s_axi_lite_clk),
        .S_AXI_ARADDR(s_axi_araddr),
        .S_AXI_ARESETN(s_axi_lite_resetn),
        .S_AXI_ARREADY(s_axi_arready),
        .S_AXI_ARVALID(s_axi_arvalid),
        .S_AXI_AWADDR(s_axi_awaddr),
        .S_AXI_AWREADY(s_axi_awready),
        .S_AXI_AWVALID(s_axi_awvalid),
        .S_AXI_BREADY(s_axi_bready),
        .S_AXI_BRESP(s_axi_bresp),
        .S_AXI_BVALID(s_axi_bvalid),
        .S_AXI_RDATA(s_axi_rdata),
        .S_AXI_RREADY(s_axi_rready),
        .S_AXI_RRESP(s_axi_rresp),
        .S_AXI_RVALID(s_axi_rvalid),
        .S_AXI_WDATA(s_axi_wdata),
        .S_AXI_WREADY(s_axi_wready),
        .S_AXI_WSTRB(s_axi_wstrb),
        .S_AXI_WVALID(s_axi_wvalid),
        .mdc_temac(1'b1),
        .mdio_i_top(1'b1),
        .mdio_o_pcspma(1'b0),
        .mdio_o_temac(1'b1),
        .mdio_t_pcspma(1'b0),
        .mdio_t_temac(1'b1),
        .pause_req(eth_buf_pause_req),
        .pause_val(eth_buf_pause_val),
        .rx_axis_mac_tdata(mac_m_axis_rx_TDATA),
        .rx_axis_mac_tlast(mac_m_axis_rx_TLAST),
        .rx_axis_mac_tuser(mac_m_axis_rx_TUSER),
        .rx_axis_mac_tvalid(mac_m_axis_rx_TVALID),
        .rx_mac_aclk(mac_rx_mac_aclk),
        .rx_reset(mac_rx_reset),
        .rx_statistics_valid(mac_rx_statistics_valid),
        .rx_statistics_vector(mac_rx_statistics_vector),
        .speed_is_10_100(mac_speedis10100),
        .tx_axis_mac_tdata(eth_buf_TX_AXIS_MAC_TDATA),
        .tx_axis_mac_tlast(eth_buf_TX_AXIS_MAC_TLAST),
        .tx_axis_mac_tready(eth_buf_TX_AXIS_MAC_TREADY),
        .tx_axis_mac_tuser(eth_buf_TX_AXIS_MAC_TUSER),
        .tx_axis_mac_tvalid(eth_buf_TX_AXIS_MAC_TVALID),
        .tx_ifg_delay(eth_buf_tx_ifg_delay),
        .tx_mac_aclk(mac_tx_mac_aclk),
        .tx_reset(mac_tx_reset));
  assign ilconstant_0_dout = 1'h1;
  assign ilvector_logic_0_Res = ~ s_axi_lite_resetn;
  kr260_open_mac #(.TARGET("XILINX"),.PHY_RESET_CYCLES(32)) mac (
    .glbl_rstn(eth_buf_RESET2TEMACn),
    .gtx_clk(gtx_clk),
    .mac_irq(mac_irq),
    .mdc(mdio_mdc),
    .mdio_i(mdio_mdio_i),
    .mdio_o(mdio_mdio_o),
    .mdio_t(mdio_mdio_t),
    .rgmii_rx_ctl(rgmii_rx_ctl),
    .rgmii_rxc(rgmii_rxc),
    .rgmii_rxd(rgmii_rd),
    .rgmii_tx_ctl(rgmii_tx_ctl),
    .rgmii_txc(rgmii_txc),
    .rgmii_txd(rgmii_td),
    .rx_axis_mac_tdata(mac_m_axis_rx_TDATA),
    .rx_axis_mac_tlast(mac_m_axis_rx_TLAST),
    .rx_axis_mac_tuser(mac_m_axis_rx_TUSER),
    .rx_axis_mac_tvalid(mac_m_axis_rx_TVALID),
    .rx_enable(mac_rx_enable),
    .rx_mac_aclk(mac_rx_mac_aclk),
    .rx_reset(mac_rx_reset),
    .rx_statistics_valid(mac_rx_statistics_valid),
    .rx_statistics_vector(mac_rx_statistics_vector),
    .s_axi_aclk(s_axi_lite_clk),
    .s_axi_araddr(eth_buf_S_AXI_2TEMAC_ARADDR),
    .s_axi_arready(eth_buf_S_AXI_2TEMAC_ARREADY),
    .s_axi_arvalid(eth_buf_S_AXI_2TEMAC_ARVALID),
    .s_axi_awaddr(eth_buf_S_AXI_2TEMAC_AWADDR),
    .s_axi_awready(eth_buf_S_AXI_2TEMAC_AWREADY),
    .s_axi_awvalid(eth_buf_S_AXI_2TEMAC_AWVALID),
    .s_axi_bready(eth_buf_S_AXI_2TEMAC_BREADY),
    .s_axi_bresp(eth_buf_S_AXI_2TEMAC_BRESP),
    .s_axi_bvalid(eth_buf_S_AXI_2TEMAC_BVALID),
    .s_axi_rdata(eth_buf_S_AXI_2TEMAC_RDATA),
    .s_axi_resetn(s_axi_lite_resetn),
    .s_axi_rready(eth_buf_S_AXI_2TEMAC_RREADY),
    .s_axi_rresp(eth_buf_S_AXI_2TEMAC_RRESP),
    .s_axi_rvalid(eth_buf_S_AXI_2TEMAC_RVALID),
    .s_axi_wdata(eth_buf_S_AXI_2TEMAC_WDATA),
    .s_axi_wready(eth_buf_S_AXI_2TEMAC_WREADY),
    .s_axi_wvalid(eth_buf_S_AXI_2TEMAC_WVALID),
    .speedis10100(mac_speedis10100),
    .tx_axis_mac_tdata(eth_buf_TX_AXIS_MAC_TDATA),
    .tx_axis_mac_tlast(eth_buf_TX_AXIS_MAC_TLAST),
    .tx_axis_mac_tready(eth_buf_TX_AXIS_MAC_TREADY),
    .tx_axis_mac_tuser(eth_buf_TX_AXIS_MAC_TUSER),
    .tx_axis_mac_tvalid(eth_buf_TX_AXIS_MAC_TVALID),
    .tx_mac_aclk(mac_tx_mac_aclk),
    .tx_reset(mac_tx_reset),
    .refclk(ref_clk),.gtx_clk90(gtx_clk90),
    .phy_rst_n(phy_rst_n)
  );
endmodule
