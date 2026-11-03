`timescale 1ns/1ps
module tb_can_axil;
 reg test_pass=0;integer checks=0,writes=0,reads=0;
 reg clk=0;always #5 clk=~clk;reg resetn=0;
 reg [15:0] aa=0,ra=0;reg [31:0] wd=0;reg [3:0] ws=0;reg av=0,wv=0,br=0,rv=0,rr=0;
 wire ar,wr,bv,rar,rdv;wire [31:0] rd;wire [1:0] bp,rp;
 wire wvalid,rvalid;wire [15:0] wa,raddr;wire [31:0] wdata;wire [3:0] strb;reg backend_write=1,backend_read=1;reg [31:0] answer=32'h1234abcd;
 can_axil_endpoint dut(.clk(clk),.resetn(resetn),.s_axi_awaddr(aa),.s_axi_awprot(3'b0),.s_axi_awvalid(av),.s_axi_awready(ar),.s_axi_wdata(wd),.s_axi_wstrb(ws),.s_axi_wvalid(wv),.s_axi_wready(wr),.s_axi_bresp(bp),.s_axi_bvalid(bv),.s_axi_bready(br),.s_axi_araddr(ra),.s_axi_arprot(3'b0),.s_axi_arvalid(rv),.s_axi_arready(rar),.s_axi_rdata(rd),.s_axi_rresp(rp),.s_axi_rvalid(rdv),.s_axi_rready(rr),.wr_valid(wvalid),.wr_ready(backend_write),.wr_addr(wa),.wr_data(wdata),.wr_strb(strb),.rd_valid(rvalid),.rd_ready(backend_read),.rd_addr(raddr),.rd_data(answer));
 always @(posedge clk)if(resetn)begin if(wvalid&&backend_write)writes<=writes+1;if(rvalid&&backend_read)reads<=reads+1;end
 task ck(input bit v,input string s);begin checks++;if(!v)$fatal(1,"FAIL %s",s);end endtask
 task tick(input integer n);repeat(n)begin @(posedge clk);#1;end endtask
 initial begin
 tick(3);resetn=1;tick(2);
 @(negedge clk);aa='h1234;av=1;tick(1);@(negedge clk);av=0;tick(4);ck(!wvalid&&!bv,"AW alone never executes");
 @(negedge clk);wd='hdeadbeef;ws=5;wv=1;tick(1);@(negedge clk);wv=0;backend_write=0;tick(3);ck(wvalid&&wa=='h1234&&wdata=='hdeadbeef&&strb==5,"split AW W retained during backend stall");
 backend_write=1;tick(1);ck(bv&&writes==1,"one backend write");tick(5);ck(bv&&!ar&&!wr&&writes==1,"B backpressure holds without repeat");br=1;tick(1);ck(!bv,"B accepted");br=0;
 @(negedge clk);wd='h87654321;ws=15;wv=1;tick(1);@(negedge clk);wv=0;tick(2);ck(!wvalid,"W alone waits for AW");
 @(negedge clk);aa='h4004;av=1;ra='h68;rv=1;tick(1);@(negedge clk);av=0;rv=0;tick(2);
 ck(bv&&rdv&&writes==2&&reads==1,"independent read and write complete");ck(rd==32'h1234abcd&&raddr=='h68,"read address and data");
 answer=32'hffffffff;tick(5);ck(rdv&&rd==32'h1234abcd&&!rar&&reads==1,"R response held stable under backpressure");rr=1;br=1;tick(1);ck(!rdv&&!bv,"responses released");
 resetn=0;tick(2);ck(!rdv&&!bv&&!wvalid&&!rvalid,"reset cancels incomplete transactions");
 test_pass=1;$display("PASS tb_can_axil checks=%0d",checks);$finish;
 end
 initial begin #1000000;$fatal(1,"watchdog");end
endmodule
