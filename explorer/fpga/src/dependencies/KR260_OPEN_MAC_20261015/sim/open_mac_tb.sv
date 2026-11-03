`timescale 1ns/1ps
module open_mac_tb;
reg clk=0,ctrl=0,refclk=0,rxclk=0,rstn=0,txrstn=0;
always #4 clk=~clk;
always #5 ctrl=~ctrl;
always #1.5 refclk=~refclk;
real rxhalf=4.0; always #(rxhalf) rxclk=~rxclk;
reg clk90=0;initial begin #2;forever #4 clk90=~clk90;end
reg [17:0] awaddr=0,araddr=0;
reg awvalid=0,wvalid=0,bready=0,arvalid=0,rready=0;
reg [31:0] wdata=0;
wire awready,wready,bvalid,arready,rvalid;
wire [1:0] bresp,rresp;
wire [31:0] rdata;
reg [3:0] txkeep=15;reg [31:0] txd=0,txc=0;
reg dv=0,dl=0,cv=0,cl=0;
wire dr,cr,txclk,txctl;
wire [3:0] td;
integer edges=0,stage=0;
always @(posedge txclk) if(txctl===1'b1) edges=edges+1;
wire mdc,mdio_o,mdio_t;reg mdio_i=1;
wire phy_raw;wire local_resetn=rstn;
reg [3:0] rxd=0;reg rxctl=0;reg ready=1;
wire [31:0] outd,outs;wire [3:0] outkeep;wire outv,outl,outsv,outsl;
open_mac_subsystem_sim dut(
.phy_rst_n(phy_raw),.s_axi_lite_resetn(local_resetn),.s_axi_lite_clk(ctrl),.axis_clk(clk),.gtx_clk(clk),.gtx_clk90(clk90),.ref_clk(refclk),
.axi_txd_arstn(local_resetn),.axi_txc_arstn(local_resetn),.axi_rxd_arstn(local_resetn),.axi_rxs_arstn(local_resetn),
.s_axi_awaddr(awaddr),.s_axi_awvalid(awvalid),.s_axi_awready(awready),
.s_axi_wdata(wdata),.s_axi_wstrb(4'hf),.s_axi_wvalid(wvalid),.s_axi_wready(wready),
.s_axi_bready(bready),.s_axi_bvalid(bvalid),.s_axi_bresp(bresp),
.s_axi_araddr(araddr),.s_axi_arvalid(arvalid),.s_axi_arready(arready),
.s_axi_rready(rready),.s_axi_rdata(rdata),.s_axi_rvalid(rvalid),.s_axi_rresp(rresp),
.s_axis_txd_tdata(txd),.s_axis_txd_tkeep(txkeep),.s_axis_txd_tlast(dl),.s_axis_txd_tvalid(dv),.s_axis_txd_tready(dr),
.s_axis_txc_tdata(txc),.s_axis_txc_tkeep(4'hf),.s_axis_txc_tlast(cl),.s_axis_txc_tvalid(cv),.s_axis_txc_tready(cr),
.m_axis_rxd_tready(ready),.m_axis_rxd_tdata(outd),.m_axis_rxd_tkeep(outkeep),.m_axis_rxd_tlast(outl),.m_axis_rxd_tvalid(outv),
.m_axis_rxs_tready(ready),.m_axis_rxs_tdata(outs),.m_axis_rxs_tvalid(outsv),.m_axis_rxs_tlast(outsl),
.rgmii_rd(rxd),.rgmii_rxc(rxclk),.rgmii_rx_ctl(rxctl),.rgmii_td(td),.rgmii_txc(txclk),.rgmii_tx_ctl(txctl),.mdio_mdio_i(mdio_i),.mdio_mdio_o(mdio_o),.mdio_mdio_t(mdio_t),.mdio_mdc(mdc));
task automatic wr(input [17:0] a,input [31:0] d);
 begin
  @(negedge ctrl); awaddr=a;wdata=d;awvalid=1;wvalid=1;bready=1;
  fork
   begin do @(posedge ctrl); while(!awready); @(negedge ctrl);awvalid=0;end
   begin do @(posedge ctrl); while(!wready); @(negedge ctrl);wvalid=0;end
   begin do @(posedge ctrl); while(!bvalid); if(bresp!==0)$fatal(1,"AXI write error %h",a);end
  join
  @(negedge ctrl);bready=0;
  $display("WRITE %h=%h @%t",a,d,$time);
 end
endtask
task automatic rd(input [17:0] a,output [31:0] d);
 begin
  @(negedge ctrl);araddr=a;arvalid=1;rready=1;
  do @(posedge ctrl); while(!arready);
  @(negedge ctrl);arvalid=0;
  do @(posedge ctrl); while(!rvalid);
  d=rdata;if(rresp!==0)$fatal(1,"AXI read error %h",a);
  @(negedge ctrl);rready=0;
  $display("READ %h=%h @%t",a,d,$time);
 end
endtask

byte frame[0:1517];integer len=60,received=0,rxpos=0,statwords=0;integer tx_wire_count=0;byte tx_wire[0:2047];reg [3:0] txlow;reg txnibble=0;reg monitor_tx=0;
reg [31:0] value;
function automatic [31:0] crcbyte(input [31:0] c,input [7:0] b);
 reg [31:0] t;begin t=c^b;for(integer i=0;i<8;i=i+1)t=t[0]?(t>>1)^32'hedb88320:(t>>1);crcbyte=t;end
endfunction
// PHY TX internal delay: sample edge-aligned RGMII 2ns after TXC.
always @(posedge txclk) begin #2; if(monitor_tx) begin
 if(rxhalf==4) txlow=td;
 else if(txctl) begin
  if(!txnibble) txlow=td;else begin tx_wire[tx_wire_count]={td,txlow};tx_wire_count=tx_wire_count+1;end
  txnibble=~txnibble;
 end else txnibble=0;
end end
always @(negedge txclk) begin #2; if(monitor_tx&&rxhalf==4&&txctl) begin tx_wire[tx_wire_count]={td,txlow};tx_wire_count=tx_wire_count+1;end end
always @(posedge clk) begin
 if(outv&&ready) begin
  for(integer b=0;b<4;b=b+1) if(outkeep[b]) begin
   if(outd[b*8+:8]!==frame[rxpos])$fatal(1,"RX byte mismatch pos=%0d got=%h exp=%h",rxpos,outd[b*8+:8],frame[rxpos]);rxpos=rxpos+1;
  end
  if(outl)begin if(rxpos!=len)$fatal(1,"RX length %0d expected %0d",rxpos,len);received=received+1;rxpos=0;end
 end
 if(outsv&&ready) begin if(statwords%6==0&&outs!==32'h50000000)$fatal(1,"STATUS FLAG");if(statwords%6==5&&outs[15:0]!=len)$fatal(1,"STATUS LENGTH"); statwords=statwords+1;if(outsl&&statwords%6!=0)$fatal(1,"RX status not six words");end
end
task automatic makeframe(input integer n,input bit vlan);
 begin len=n;for(integer j=0;j<len;j=j+1)frame[j]=(j*7+3)&255;
 for(integer j=0;j<6;j=j+1)frame[j]=8'hff;
 frame[6]=2;frame[12]=vlan?8'h81:8'h08;frame[13]=0;
 if(vlan)begin frame[14]=0;frame[15]=100;frame[16]=8'h08;frame[17]=0;end
 end
endtask
task automatic send_frame;
 begin
 for(integer j=0;j<6;j=j+1)begin @(negedge clk);cv=1;txc=(j==0)?32'ha0000000:0;cl=(j==5);do @(posedge clk);while(!cr);end
 @(negedge clk);cv=0;cl=0;
 for(integer j=0;j<(len+3)/4;j=j+1)begin @(negedge clk);dv=1;dl=j==(len+3)/4-1;txkeep=(dl&&len%4)?((1<<(len%4))-1):15;txd={frame[j*4+3],frame[j*4+2],frame[j*4+1],frame[j*4]};do @(posedge clk);while(!dr);end
 @(negedge clk);dv=0;dl=0;
 end
endtask
task automatic rxbyte(input [7:0] b);
 begin
 if(rxhalf==4)begin @(negedge rxclk);#2;rxd=b[3:0];rxctl=1;@(posedge rxclk);#2;rxd=b[7:4];end
 else begin
  @(negedge rxclk);#2;rxd=b[3:0];rxctl=1;@(posedge rxclk);#2;rxd=b[3:0];
  @(negedge rxclk);#2;rxd=b[7:4];@(posedge rxclk);#2;rxd=b[7:4];
 end
 end
endtask
task automatic receive_frame(input bit corrupt);
 reg [31:0] c;begin c=32'hffffffff;
 repeat(7)rxbyte(8'h55);rxbyte(8'hd5);
 for(integer j=0;j<len;j=j+1)begin rxbyte(frame[j]);c=crcbyte(c,frame[j]);end
 c=~c;if(corrupt)c=c^1;
 for(integer j=0;j<4;j=j+1)rxbyte(c[j*8+:8]);
 @(negedge rxclk);#2;rxctl=0;rxd=0;
 repeat(30)@(posedge rxclk);
 end
endtask
task automatic txcheck;
 reg [31:0] c;integer start,wirelen;
 begin wirelen=len<60?60:len;tx_wire_count=0;txnibble=0;monitor_tx=1;send_frame();#150000;monitor_tx=0;
 start=-1;for(integer j=0;j<10;j=j+1)if(tx_wire[j]==8'hd5)start=j+1;
 if(start<1||tx_wire_count!=start+wirelen+4)$fatal(1,"TX wire size=%0d start=%0d expected=%0d",tx_wire_count,start,len);
 c=32'hffffffff;
 for(integer j=0;j<wirelen;j=j+1)begin if(tx_wire[start+j]!==((j<len)?frame[j]:8'b0))$fatal(1,"TX payload mismatch %0d",j);c=crcbyte(c,(j<len)?frame[j]:8'b0);end
 c=~c;for(integer j=0;j<4;j=j+1)if(tx_wire[start+wirelen+j]!==c[j*8+:8])$fatal(1,"TX CRC mismatch");
 $display("CASE_PASS wire_TX len=%0d rxhalf=%0f",len,rxhalf);
 end
endtask
task automatic initmac;
 begin wr('h40c,0);wr('h404,'h10000000);wr('h408,'h10000000);wr('h708,'h80000000);#30000;end
endtask

integer mdio_bits=0;reg mdio_active=0,mdio_read_test=0;reg [63:0] mdio_capture=0;reg [15:0] fake_phy=16'h7949;
always @(posedge mdc) if(mdio_active)begin
 if(!mdio_read_test || mdio_bits<46)begin if(mdio_t!==0)$fatal(1,"MDIO unexpected tristate");end
 else if(mdio_t!==1)$fatal(1,"MDIO read bus contention");
 mdio_capture={mdio_capture[62:0],mdio_o};mdio_bits=mdio_bits+1;
end
always @(negedge mdc) if(mdio_active&&mdio_read_test)begin
 if(mdio_bits>=48 && mdio_bits<64)mdio_i=fake_phy[63-mdio_bits];else mdio_i=0;
end
task automatic mdiotest;
 begin
 wr('h500,'h53);wr('h508,'ha55a);mdio_bits=0;mdio_capture=0;mdio_active=1;mdio_read_test=0;
 wr('h504,'h01024800);#40000;rd('h504,value);
 if(!value[7]||mdio_bits!=64||mdio_capture!==64'hffffffff508aa55a)$fatal(1,"MDIO write frame=%h bits=%0d",mdio_capture,mdio_bits);
 mdio_bits=0;mdio_capture=0;mdio_read_test=1;mdio_i=1;
 wr('h504,'h01028800);#40000;rd('h504,value);if(!value[7]||mdio_bits!=64)$fatal(1,"MDIO read incomplete");
 rd('h50c,value);if(value[15:0]!==fake_phy)$fatal(1,"MDIO PHY read mismatch %h",value);
 mdio_active=0;mdio_i=1;$display("CASE_PASS MDIO Clause22 write and PHY read");
 end
endtask
task automatic skew_write(input bit data_first,input [17:0] a,input [31:0] d);
 begin
 @(negedge ctrl);bready=0;
 if(data_first)begin wdata=d;wvalid=1;do @(posedge ctrl);while(!wready);@(negedge ctrl);wvalid=0;repeat(4)@(negedge ctrl);awaddr=a;awvalid=1;do @(posedge ctrl);while(!awready);@(negedge ctrl);awvalid=0;end
 else begin awaddr=a;awvalid=1;do @(posedge ctrl);while(!awready);@(negedge ctrl);awvalid=0;repeat(4)@(negedge ctrl);wdata=d;wvalid=1;do @(posedge ctrl);while(!wready);@(negedge ctrl);wvalid=0;end
 wait(bvalid);repeat(4)begin @(negedge ctrl);if(!bvalid||bresp!=0)$fatal(1,"B response stability");end
 bready=1;@(negedge ctrl);bready=0;
 rd(a,value);if(value!=d)$fatal(1,"skewed write readback");
 end
endtask

integer before_rx;integer qstart;
initial begin
 #1000;@(negedge ctrl);rstn=1;#50000;initmac();rd('h4f8,value);if(value!=32'h4f4d4143)$fatal(1,"OMAC ID mismatch %h",value);
 rd('h808,value);if(value!=2)$fatal(1,"1G speed wrong");
 stage=1;makeframe(60,0);txcheck();before_rx=received;receive_frame(0);#20000;if(received!=before_rx+1)$fatal(1,"RX missing 1G");
 stage=2;before_rx=received;receive_frame(1);#20000;if(received!=before_rx)$fatal(1,"Bad CRC accepted");
 stage=3;makeframe(64,1);txcheck();before_rx=received;ready=0;receive_frame(0);#10000;if(received!=before_rx)$fatal(1,"backpressure violated");ready=1;#20000;if(received!=before_rx+1)$fatal(1,"RX VLAN/backpressure lost");
 stage=4;@(negedge ctrl);rstn=0;#1000;rstn=1;#50000;initmac();rxhalf=20;#50000;rd('h808,value);if(value!=1)$fatal(1,"100M speed wrong %h",value);
 makeframe(60,0);txcheck();before_rx=received;receive_frame(0);#20000;if(received!=before_rx+1)$fatal(1,"RX missing100M");
 stage=5;rxhalf=200;#50000;rd('h808,value);if(value!=0)$fatal(1,"10M speed wrong");txcheck();before_rx=received;receive_frame(0);#30000;if(received!=before_rx+1)$fatal(1,"RX missing10M");
 rd('h810,value);if(value!=2)$fatal(1,"TX complete counter %0d",value);

 stage=6;mdiotest();skew_write(0,'h400,32'h12345678);skew_write(1,'h400,32'h98765432);
 rxhalf=4;#50000;makeframe(61,0);txcheck();before_rx=received;receive_frame(0);#20000;if(received!=before_rx+1)$fatal(1,"odd length RX");
 makeframe(42,0);txcheck();before_rx=received;receive_frame(0);#20000;if(received!=before_rx)$fatal(1,"runt frame accepted");
 stage=7;makeframe(1514,0);txcheck();before_rx=received;receive_frame(0);#20000;if(received!=before_rx+1)$fatal(1,"MTU RX");
 stage=8;wr('h404,0);wr('h708,0);wr('h700,32'h33221102);wr('h704,32'h5544);wr('h404,'h10000000);#10000;
 makeframe(60,0);frame[0]=2;frame[1]='h11;frame[2]='h22;frame[3]='h33;frame[4]='h44;frame[5]='h55;
 before_rx=received;receive_frame(0);#20000;if(received!=before_rx+1)$fatal(1,"unicast match dropped");
 frame[5]='h66;before_rx=received;receive_frame(0);#20000;if(received!=before_rx)$fatal(1,"foreign unicast accepted");
 frame[0]=1;before_rx=received;receive_frame(0);#20000;if(received!=before_rx+1)$fatal(1,"multicast dropped");
 stage=9;makeframe(1514,0);ready=0;qstart=received;repeat(24)receive_frame(0);#10000;ready=1;#100000;
 if(received-qstart<20||received-qstart>=24)$fatal(1,"overflow whole frame policy delivered=%0d",received-qstart);
 before_rx=received;receive_frame(0);#20000;if(received!=before_rx+1)$fatal(1,"no recovery after RX overflow");
 $display("CASE_PASS AXIL skew/stall, 61-byte keep, padding, MTU, unicast/multicast, overflow recovery");
 $display("TEST_PASS OPEN_MAC_BUFFER wire CRC TX/RX 10/100/1000, bad CRC rejected, VLAN, RX backpressure, local reset, completion counters");$finish;
end
initial begin #10000000;$fatal(1,"WATCHDOG stage=%0d rx=%0d",stage,received);end
endmodule
