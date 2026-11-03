// SPDX-License-Identifier: MIT
// Independent control plane for the KR260 open MAC. No vendor MAC RTL used.
`timescale 1ns/1ps
module kr260_mac_csr(
 input clk, resetn,
 input [11:0] awaddr, input awvalid, output awready,
 input [31:0] wdata, input wvalid, output wready,
 output [1:0] bresp, output reg bvalid, input bready,
 input [11:0] araddr, input arvalid, output arready,
 output reg [31:0] rdata, output [1:0] rresp, output reg rvalid, input rready,
 output reg [31:0] rcw0,rcw1,tc,emmc,uaw0,uaw1,fmc,
 output wire soft_reset,
 input [31:0] tx_good,rx_good,rx_bad, input [1:0] speed,
 output reg mdc, output mdio_o, output mdio_t, input mdio_i
);
 (* ASYNC_REG="TRUE" *) reg mdio_in_meta=1,mdio_in_sync=1;
 always @(posedge clk) begin mdio_in_meta<=mdio_i;mdio_in_sync<=mdio_in_meta;end
 reg awheld,wheld; reg [11:0] awsave; reg [31:0] wsave;
 reg [7:0] rst_count;
 reg [31:0] mdio_mc,mdio_mcr; reg [15:0] mdio_wd,mdio_rd;
 reg mdio_busy,mdio_read,mdio_end;
 reg [5:0] bit_index; reg [6:0] div_count;
 reg [63:0] frame; reg [15:0] rx_shift;
 assign awready=!awheld&&!bvalid; assign wready=!wheld&&!bvalid;
 assign arready=!rvalid; assign bresp=0; assign rresp=0;
 assign soft_reset=|rst_count;
 assign mdio_o=frame[63];
 assign mdio_t=!mdio_busy || (mdio_read && bit_index>=46);
 always @(posedge clk) begin
  if(!resetn) begin
   awheld<=0; wheld<=0; bvalid<=0; rvalid<=0; rdata<=0;
   rcw0<=0;rcw1<=0;tc<=0;emmc<=32'h80000000;uaw0<=0;uaw1<=0;fmc<=0;rst_count<=0;
   mdio_mc<=32'h68;mdio_mcr<=0;mdio_wd<=0;mdio_rd<=0;
   mdio_busy<=0;mdio_read<=0;mdio_end<=0;mdc<=0;bit_index<=0;div_count<=0;frame<=~64'b0;rx_shift<=0;
  end else begin
   if(rst_count!=0) rst_count<=rst_count-1'b1;
   if(bvalid&&bready) bvalid<=0;
   if(rvalid&&rready) rvalid<=0;
   if(awvalid&&awready) begin awheld<=1;awsave<=awaddr;end
   if(wvalid&&wready) begin wheld<=1;wsave<=wdata;end
   if(awheld&&wheld&&!bvalid) begin
    awheld<=0;wheld<=0;bvalid<=1;
    case(awsave)
     12'h400:rcw0<=wsave;
     12'h404:begin rcw1<=wsave&32'h7fffffff; if(wsave[31]) rst_count<=128;end
     12'h408:begin tc<=wsave&32'h7fffffff; if(wsave[31]) rst_count<=128;end
     // FCC is deliberately read-only zero: v1 has no pause offload.
     12'h410:emmc<=wsave;
     12'h700:uaw0<=wsave;
     12'h704:uaw1<=wsave&32'hffff;
     12'h708:fmc<=wsave;
     12'h500:if(!mdio_busy) mdio_mc<=wsave;
     12'h508:mdio_wd<=wsave[15:0];
     12'h504:if(!mdio_busy && wsave[11] && mdio_mc[6]) begin
       mdio_mcr<=wsave&32'hfffff77f;mdio_busy<=1;mdio_end<=0;mdc<=0;div_count<=0;bit_index<=0;rx_shift<=0;
       mdio_read<=wsave[15:14]==2'b10;
       frame<={32'hffffffff,2'b01,wsave[15:14],wsave[28:24],wsave[20:16],2'b10,mdio_wd};
     end
    endcase
   end
   if(arvalid&&arready) begin
    rvalid<=1;
    case(araddr)
     12'h400:rdata<=rcw0;
     12'h404:rdata<=rcw1|{soft_reset,31'b0};
     12'h408:rdata<=tc|{soft_reset,31'b0};
     12'h40c:rdata<=0;
     12'h410:rdata<=emmc;
     12'h414:rdata<=1518;
     12'h4f8:rdata<=32'h4f4d4143; // "OMAC", never impersonate AMD ID
     12'h500:rdata<=mdio_mc;
     12'h504:rdata<=mdio_mcr|(!mdio_busy?32'h80:0);
     12'h508:rdata<={16'b0,mdio_wd};
     12'h50c:rdata<={16'b0,mdio_rd};
     12'h700:rdata<=uaw0;
     12'h704:rdata<=uaw1;
     12'h708:rdata<=fmc;
     12'h800:rdata<=32'h00010000; // ABI 1.0
     12'h804:rdata<=32'h0000000f; // full duplex, CRC, VLAN pass, multicast pass
     12'h808:rdata<={30'b0,speed};
     12'h810:rdata<=tx_good;
     12'h814:rdata<=rx_good;
     12'h818:rdata<=rx_bad;
     default:rdata<=0;
    endcase
   end
   if(mdio_busy) begin
    if(div_count >= {1'b0,mdio_mc[5:0]}) begin
     div_count<=0;
     if(!mdc) begin
      mdc<=1;
      if(mdio_read&&bit_index>=48) rx_shift<={rx_shift[14:0],mdio_in_sync};
      if(bit_index==63) mdio_end<=1;
     end else begin
      mdc<=0;
      if(mdio_end) begin mdio_busy<=0;mdio_rd<=rx_shift;end
      else begin bit_index<=bit_index+1'b1;frame<={frame[62:0],1'b1};end
     end
    end else div_count<=div_count+1'b1;
   end
  end
 end
endmodule
