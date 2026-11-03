// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module kr260_open_mac #(parameter TARGET="XILINX", parameter PHY_RESET_CYCLES=3145728)(
 input gtx_clk,
 (* X_INTERFACE_IGNORE="TRUE" *) input refclk,
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 gtx_clk90 CLK" *) input gtx_clk90,
 input glbl_rstn,
 (* X_INTERFACE_PARAMETER="ASSOCIATED_BUSIF s_axi, ASSOCIATED_RESET s_axi_resetn" *)
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 s_axi_aclk CLK" *) input s_axi_aclk,
 (* X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *)
 (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 s_axi_resetn RST" *) input s_axi_resetn,
 input [11:0] s_axi_awaddr, input s_axi_awvalid, output s_axi_awready,
 input [31:0] s_axi_wdata, input s_axi_wvalid, output s_axi_wready,
 output [1:0] s_axi_bresp, output s_axi_bvalid, input s_axi_bready,
 input [11:0] s_axi_araddr, input s_axi_arvalid, output s_axi_arready,
 output [31:0] s_axi_rdata, output [1:0] s_axi_rresp, output s_axi_rvalid, input s_axi_rready,
 input [7:0] tx_axis_mac_tdata, input tx_axis_mac_tvalid,output tx_axis_mac_tready,input tx_axis_mac_tlast,input tx_axis_mac_tuser,
 output reg [7:0] rx_axis_mac_tdata,output reg rx_axis_mac_tvalid,rx_axis_mac_tlast,rx_axis_mac_tuser,
 (* X_INTERFACE_PARAMETER="FREQ_HZ 125000000, ASSOCIATED_BUSIF tx_axis_mac, ASSOCIATED_RESET tx_reset" *)
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 tx_mac_aclk CLK" *) output tx_mac_aclk,
 (* X_INTERFACE_PARAMETER="FREQ_HZ 125000000, ASSOCIATED_BUSIF rx_axis_mac, ASSOCIATED_RESET rx_reset" *)
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 rx_mac_aclk CLK" *) output rx_mac_aclk,
 (* X_INTERFACE_PARAMETER="POLARITY ACTIVE_HIGH" *) (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 tx_reset RST" *) output tx_reset,
 (* X_INTERFACE_PARAMETER="POLARITY ACTIVE_HIGH" *) (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 rx_reset RST" *) output rx_reset,
 output rx_enable,speedis10100,
 output reg [27:0] rx_statistics_vector,output reg rx_statistics_valid,
 (* X_INTERFACE_MODE="Master" *) (* X_INTERFACE_INFO="xilinx.com:interface:rgmii:1.0 rgmii RD" *) input [3:0] rgmii_rxd,
 (* X_INTERFACE_INFO="xilinx.com:interface:rgmii:1.0 rgmii RX_CTL" *) input rgmii_rx_ctl,
 (* X_INTERFACE_INFO="xilinx.com:interface:rgmii:1.0 rgmii RXC" *) input rgmii_rxc,
 (* X_INTERFACE_INFO="xilinx.com:interface:rgmii:1.0 rgmii TD" *) output [3:0] rgmii_txd,
 (* X_INTERFACE_INFO="xilinx.com:interface:rgmii:1.0 rgmii TX_CTL" *) output rgmii_tx_ctl,
 (* X_INTERFACE_INFO="xilinx.com:interface:rgmii:1.0 rgmii TXC" *) output rgmii_txc,
 (* X_INTERFACE_INFO="xilinx.com:interface:mdio:1.0 mdio MDC" *) output mdc,
 (* X_INTERFACE_INFO="xilinx.com:interface:mdio:1.0 mdio MDIO_O" *) output mdio_o,
 (* X_INTERFACE_INFO="xilinx.com:interface:mdio:1.0 mdio MDIO_T" *) output mdio_t,
 (* X_INTERFACE_INFO="xilinx.com:interface:mdio:1.0 mdio MDIO_I" *) input mdio_i,
 output mac_irq,output phy_rst_n, output debug_tx_ce
);
 wire [31:0] rcw0,rcw1,tc,emmc,uaw0,uaw1,fmc;
 (* ASYNC_REG="TRUE" *) reg [1:0] speed_meta=0,speed_cpu=0;
 wire soft_reset; wire [1:0] speed;
 wire rx_delay_ready;
 (* ASYNC_REG="TRUE" *) reg [31:0] delay_rst_sync=32'hffffffff;
 always @(posedge refclk or negedge glbl_rstn)
  if(!glbl_rstn)delay_rst_sync<=32'hffffffff;else delay_rst_sync<={delay_rst_sync[30:0],1'b0};
 IDELAYCTRL #(.SIM_DEVICE("ULTRASCALE_PLUS")) rx_delayctrl(.REFCLK(refclk),.RST(delay_rst_sync[31]),.RDY(rx_delay_ready));
 wire [4:0] rx_pad={rgmii_rx_ctl,rgmii_rxd};
 wire [4:0] rx_delayed;
 genvar di;
 generate for(di=0;di<5;di=di+1)begin:rx_delay
  IDELAYE3 #(.DELAY_FORMAT("TIME"),.DELAY_TYPE("FIXED"),.DELAY_VALUE(900),.DELAY_SRC("IDATAIN"),.REFCLK_FREQUENCY(333.333),.SIM_DEVICE("ULTRASCALE_PLUS")) input_delay(
   .IDATAIN(rx_pad[di]),.DATAOUT(rx_delayed[di]),.DATAIN(1'b0),.CLK(1'b0),.CE(1'b0),.INC(1'b0),.LOAD(1'b0),.CNTVALUEIN(9'b0),.RST(1'b0),.EN_VTC(1'b1),.CASC_IN(1'b0),.CASC_RETURN(1'b0));
 end endgenerate
 wire gtx_async_rst=!glbl_rstn||soft_reset||!rx_delay_ready;
 (* ASYNC_REG="TRUE" *) reg [3:0] gtx_rst_sync=4'hf;
 always @(posedge gtx_clk or posedge gtx_async_rst)
  if(gtx_async_rst)gtx_rst_sync<=4'hf;else gtx_rst_sync<={gtx_rst_sync[2:0],1'b0};
 wire [31:0] tx_good_cpu,rx_good_cpu,rx_bad_cpu;
 kr260_mac_csr csr(.clk(s_axi_aclk),.resetn(s_axi_resetn),
 .awaddr(s_axi_awaddr),.awvalid(s_axi_awvalid),.awready(s_axi_awready),
 .wdata(s_axi_wdata),.wvalid(s_axi_wvalid),.wready(s_axi_wready),.bresp(s_axi_bresp),.bvalid(s_axi_bvalid),.bready(s_axi_bready),
 .araddr(s_axi_araddr),.arvalid(s_axi_arvalid),.arready(s_axi_arready),.rdata(s_axi_rdata),.rresp(s_axi_rresp),.rvalid(s_axi_rvalid),.rready(s_axi_rready),
 .rcw0(rcw0),.rcw1(rcw1),.tc(tc),.emmc(emmc),.uaw0(uaw0),.uaw1(uaw1),.fmc(fmc),.soft_reset(soft_reset),
 .tx_good(tx_good_cpu),.rx_good(rx_good_cpu),.rx_bad(rx_bad_cpu),.speed(speed_cpu),.mdc(mdc),.mdio_o(mdio_o),.mdio_t(mdio_t),.mdio_i(mdio_i));
 reg [21:0] phy_count=0;
 always @(posedge s_axi_aclk) if(!s_axi_resetn) phy_count<=0; else if(phy_count<PHY_RESET_CYCLES) phy_count<=phy_count+1'b1;
 assign phy_rst_n=phy_count==PHY_RESET_CYCLES;
 assign mac_irq=1'b0;
 (* ASYNC_REG="TRUE" *) reg [1:0] tx_cfg_sync=0,rx_cfg_sync=0;
 // Multibit configuration changes only with RX disabled; driver waits for synchronization.
 (* ASYNC_REG="TRUE" *) reg [48:0] rx_addr_meta=0,rx_addr_sync=0;
 always @(posedge tx_mac_aclk) if(tx_reset) tx_cfg_sync<=0; else tx_cfg_sync<={tx_cfg_sync[0],tc[28]};
 always @(posedge rx_mac_aclk) begin
  if(rx_reset) begin rx_cfg_sync<=0;rx_addr_meta<=0;rx_addr_sync<=0;end
  else begin rx_cfg_sync<={rx_cfg_sync[0],rcw1[28]};rx_addr_meta<={fmc[31],uaw1[15:0],uaw0};rx_addr_sync<=rx_addr_meta;end
 end
 wire [7:0] raw_data;wire raw_valid,raw_last,raw_user;
 wire tx_error,rx_error,rx_fcs,gmii_en,gmii_er;
 kr260_rgmii_engine #(.TARGET(TARGET),.IODDR_STYLE("IODDRE1"),.CLOCK_INPUT_STYLE("BUFG"),.USE_CLK90("FALSE")) engine(
 .gtx_clk(gtx_clk),.gtx_clk90(gtx_clk90),.gtx_rst(gtx_rst_sync[3]),
 .tx_clk(tx_mac_aclk),.rx_clk(rx_mac_aclk),.tx_rst(tx_reset),.rx_rst(rx_reset),
 .tx_axis_tdata(tx_axis_mac_tdata),.tx_axis_tvalid(tx_axis_mac_tvalid),.tx_axis_tready(tx_axis_mac_tready),.tx_axis_tlast(tx_axis_mac_tlast),.tx_axis_tuser(tx_axis_mac_tuser),
 .rx_axis_tdata(raw_data),.rx_axis_tvalid(raw_valid),.rx_axis_tlast(raw_last),.rx_axis_tuser(raw_user),
 .rgmii_rx_clk(rgmii_rxc),.rgmii_rxd(rx_delayed[3:0]),.rgmii_rx_ctl(rx_delayed[4]),.rgmii_tx_clk(rgmii_txc),.rgmii_txd(rgmii_txd),.rgmii_tx_ctl(rgmii_tx_ctl),
 .cfg_ifg(8'd12),.cfg_tx_enable(tx_cfg_sync[1]),.cfg_rx_enable(rx_cfg_sync[1]),
 .tx_error_underflow(tx_error),.rx_error_bad_frame(rx_error),.rx_error_bad_fcs(rx_fcs),.speed(speed),
 .debug_tx_en(gmii_en),.debug_tx_er(gmii_er),.debug_tx_ce(debug_tx_ce));
 assign speedis10100=speed!=2;
 assign rx_enable=1'b1; // RX AXIS valid is byte-based, already MII-decimated by open MAC.

 always @(posedge s_axi_aclk) begin speed_meta<=speed;speed_cpu<=speed_meta;end
 reg [13:0] rx_len=0;
 reg [47:0] dest=0;reg [15:0] ether_type=0;
 wire addr_match=rx_addr_sync[48] || dest==rx_addr_sync[47:0] || dest[0];
 wire vlan=ether_type==16'h8100 || ether_type==16'h88a8;
 wire frame_bad=raw_user || !addr_match || rx_len<59 || rx_len>(vlan?1517:1513);
 reg [31:0] rx_good_count=0,rx_bad_count=0,tx_good_count=0;
 reg gmii_prev=0,tx_bad_latch=0;
 always @(posedge tx_mac_aclk) begin
  if(tx_reset) begin tx_good_count<=0;gmii_prev<=0;tx_bad_latch<=0;end
  else if(debug_tx_ce) begin
   gmii_prev<=gmii_en;
   if(gmii_en&&!gmii_prev) tx_bad_latch<=gmii_er;
   else if(gmii_en&&gmii_er) tx_bad_latch<=1;
   if(!gmii_en&&gmii_prev) begin if(!tx_bad_latch) tx_good_count<=tx_good_count+1'b1;tx_bad_latch<=0;end
  end
 end
 always @(posedge rx_mac_aclk) begin
  if(rx_reset) begin
   rx_len<=0;dest<=0;ether_type<=0;rx_good_count<=0;rx_bad_count<=0;
   rx_axis_mac_tdata<=0;rx_axis_mac_tvalid<=0;rx_axis_mac_tlast<=0;rx_axis_mac_tuser<=0;rx_statistics_vector<=0;rx_statistics_valid<=0;
  end else begin
   rx_axis_mac_tdata<=raw_data;rx_axis_mac_tvalid<=raw_valid;rx_axis_mac_tlast<=raw_last;rx_axis_mac_tuser<=raw_user||(raw_last&&frame_bad);
   rx_statistics_valid<=raw_valid&&raw_last;
   rx_statistics_vector[22]<=raw_valid;
   if(raw_valid) begin
    if(rx_len<6) dest[rx_len*8+:8]<=raw_data;
    if(rx_len==12) ether_type[15:8]<=raw_data;
    if(rx_len==13) ether_type[7:0]<=raw_data;
    if(raw_last) begin
     rx_statistics_vector<={addr_match,1'b0,1'b0,1'b0,1'b0,1'b1,vlan,(rx_len>(vlan?1517:1513)),(ether_type==16'h8808),(rx_len+14'd5),dest[0],(&dest),raw_user,frame_bad,!frame_bad};
     rx_len<=0;
     if(frame_bad) rx_bad_count<=rx_bad_count+1'b1;else rx_good_count<=rx_good_count+1'b1;
    end else if(rx_len<16360) rx_len<=rx_len+1'b1;
   end
  end
 end
 kr260_stat_cdc tx_cdc(.src_clk(tx_mac_aclk),.count(tx_good_count),.dst_clk(s_axi_aclk),.value(tx_good_cpu));
 kr260_stat_cdc rx_cdc(.src_clk(rx_mac_aclk),.count(rx_good_count),.dst_clk(s_axi_aclk),.value(rx_good_cpu));
 kr260_stat_cdc bad_cdc(.src_clk(rx_mac_aclk),.count(rx_bad_count),.dst_clk(s_axi_aclk),.value(rx_bad_cpu));
endmodule
module kr260_stat_cdc(input src_clk,input [31:0] count,input dst_clk,output reg [31:0] value);
 reg [31:0] gray=0;
 (* ASYNC_REG="TRUE" *) reg [31:0] meta=0,sync=0;
 integer k;
 always @(posedge src_clk) gray<=count^(count>>1);
 always @(posedge dst_clk) begin meta<=gray;sync<=meta;end
 always @* begin value[31]=sync[31];for(k=30;k>=0;k=k-1) value[k]=value[k+1]^sync[k];end
endmodule
