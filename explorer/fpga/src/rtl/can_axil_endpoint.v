// One outstanding transaction in each direction; AW and W are independent.
module can_axil_endpoint(
 input clk, resetn,
 input [15:0] s_axi_awaddr, input [2:0] s_axi_awprot, input s_axi_awvalid, output s_axi_awready,
 input [31:0] s_axi_wdata, input [3:0] s_axi_wstrb, input s_axi_wvalid, output s_axi_wready,
 output [1:0] s_axi_bresp, output reg s_axi_bvalid=0, input s_axi_bready,
 input [15:0] s_axi_araddr, input [2:0] s_axi_arprot, input s_axi_arvalid, output s_axi_arready,
 output reg [31:0] s_axi_rdata=0, output [1:0] s_axi_rresp, output reg s_axi_rvalid=0, input s_axi_rready,
 output wr_valid, input wr_ready, output reg [15:0] wr_addr=0,
 output reg [31:0] wr_data=0, output reg [3:0] wr_strb=0,
 output rd_valid, input rd_ready, output reg [15:0] rd_addr=0, input [31:0] rd_data);
 reg aw_full=0,w_full=0,ar_full=0;
 assign s_axi_awready=!aw_full&&!s_axi_bvalid;
 assign s_axi_wready=!w_full&&!s_axi_bvalid;
 assign s_axi_arready=!ar_full&&!s_axi_rvalid;
 assign wr_valid=aw_full&&w_full&&!s_axi_bvalid;
 assign rd_valid=ar_full&&!s_axi_rvalid;
 // Invalid/busy control operations use explicit status, never an AXI abort.
 assign s_axi_bresp=0; assign s_axi_rresp=0;
 always @(posedge clk) begin
  if(!resetn) begin aw_full<=0;w_full<=0;ar_full<=0;s_axi_bvalid<=0;s_axi_rvalid<=0;s_axi_rdata<=0; end
  else begin
   if(s_axi_awvalid&&s_axi_awready) begin aw_full<=1;wr_addr<=s_axi_awaddr;end
   if(s_axi_wvalid&&s_axi_wready) begin w_full<=1;wr_data<=s_axi_wdata;wr_strb<=s_axi_wstrb;end
   if(wr_valid&&wr_ready) begin aw_full<=0;w_full<=0;s_axi_bvalid<=1;end
   if(s_axi_bvalid&&s_axi_bready)s_axi_bvalid<=0;
   if(s_axi_arvalid&&s_axi_arready)begin ar_full<=1;rd_addr<=s_axi_araddr;end
   if(rd_valid&&rd_ready)begin ar_full<=0;s_axi_rdata<=rd_data;s_axi_rvalid<=1;end
   if(s_axi_rvalid&&s_axi_rready)s_axi_rvalid<=0;
  end
 end
endmodule
