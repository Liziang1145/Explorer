`timescale 1ns/1ps
module tb_can_cold_repro;
 reg test_pass=0;
 reg clk=0;always #5 clk=~clk;reg resetn=0;
 reg [15:0] awaddr=0,araddr=0;reg awvalid=0,wvalid=0,arvalid=0,bready=1,rready=1;
 reg [31:0] wdata=0;reg [3:0] wstrb=15;
 wire awready,wready,bvalid,arready,rvalid;wire [31:0] rdata;wire [1:0] bresp,rresp;
 wire crst,tx,pltx,plrx,psrx,cirq,irqn,irqc;wire [63:0] ts;
 wire [31:0] pa,pwd,prd;wire pe,ps,pw,prdy,perr;wire [3:0] pst;wire [2:0] pp;
 reg [31:0] qa=0,qwd=0;reg qe=0,qs=0,qw=0;wire [31:0] qrd;wire qrdy,qerr,qtx;
 reg jam=0,inject_errors=0;integer jam_state=0,jam_count=0,injected=0;wire bus=tx&qtx&!jam;
 can_path_control dut(.s_axi_aclk(clk),.s_axi_aresetn(resetn),.can_rx_raw(bus),.ps_tx(1'b1),.pl_tx(pltx),.can_tx(tx),.ps_rx(psrx),.pl_rx(plrx),
 .core_resetn(crst),.timestamp(ts),.core_irq(cirq),.irq_native(irqn),.irq_control(irqc),
 .apb_addr(pa),.apb_sel(ps),.apb_enable(pe),.apb_write(pw),.apb_wdata(pwd),.apb_strb(pst),.apb_prot(pp),.apb_rdata(prd),.apb_ready(prdy),.apb_error(perr),
 .s_axi_awaddr(awaddr),.s_axi_awprot(3'b0),.s_axi_awvalid(awvalid),.s_axi_awready(awready),.s_axi_wdata(wdata),.s_axi_wstrb(wstrb),.s_axi_wvalid(wvalid),.s_axi_wready(wready),
 .s_axi_bresp(bresp),.s_axi_bvalid(bvalid),.s_axi_bready(bready),.s_axi_araddr(araddr),.s_axi_arprot(3'b0),.s_axi_arvalid(arvalid),.s_axi_arready(arready),.s_axi_rdata(rdata),.s_axi_rresp(rresp),.s_axi_rvalid(rvalid),.s_axi_rready(rready));
 can_top_apb core(.aclk(clk),.arstn(crst),.irq(cirq),.CAN_tx(pltx),.CAN_rx(plrx),.timestamp(ts),.s_apb_paddr(pa),.s_apb_penable(pe),.s_apb_pprot(pp),.s_apb_prdata(prd),.s_apb_pready(prdy),.s_apb_psel(ps),.s_apb_pslverr(perr),.s_apb_pstrb(pst),.s_apb_pwdata(pwd),.s_apb_pwrite(pw));
 can_top_apb peer(.aclk(clk),.arstn(resetn),.irq(),.CAN_tx(qtx),.CAN_rx(bus),.timestamp(ts),.s_apb_paddr(qa),.s_apb_penable(qe),.s_apb_pprot(3'b0),.s_apb_prdata(qrd),.s_apb_pready(qrdy),.s_apb_psel(qs),.s_apb_pslverr(qerr),.s_apb_pstrb(4'hf),.s_apb_pwdata(qwd),.s_apb_pwrite(qw));
 reg check_arm_frames=1;integer checks=0,seen=0;reg [10:0] expected_id[0:5];reg [63:0] expected_data[0:5];
 task check(input bit v,input string msg);begin checks++;if(!v)$fatal(1,"FAIL %s time=%0t owner=%0d phase=%0d fault=%h core=%h",msg,$time,dut.owner,dut.phase,dut.faults,dut.device_id);end endtask
 task tick(input integer n);repeat(n)begin @(posedge clk);#1;end endtask
 task wr(input [15:0] a,input [31:0] d);integer n;bit ah,wh;begin
 @(negedge clk);awaddr=a;wdata=d;awvalid=1;wvalid=1;ah=0;wh=0;n=0;
 while(!(ah&&wh)&&n<10000)begin @(posedge clk);if(awready)ah=1;if(wready)wh=1;@(negedge clk);if(ah)awvalid=0;if(wh)wvalid=0;n++;end
 check(ah&&wh,"AXI write accepted");n=0;while(!bvalid&&n<10000)begin tick(1);n++;end check(bvalid&&bresp==0,"AXI write response");tick(1);
 end endtask
 task rd(input [15:0] a,output [31:0] d);integer n;begin
 @(negedge clk);araddr=a;arvalid=1;n=0;while(!arready&&n<10000)begin tick(1);n++;end
 @(posedge clk);@(negedge clk);arvalid=0;n=0;while(!rvalid&&n<10000)begin tick(1);n++;end check(rvalid&&rresp==0,"AXI read response");d=rdata;tick(1);
 end endtask
 task pwr(input [31:0] a,input [31:0] d);begin @(negedge clk);qa=a;qwd=d;qw=1;qs=1;qe=0;tick(1);@(negedge clk);qe=1;tick(1);@(negedge clk);qs=0;qe=0;qw=0;tick(1);end endtask
 task prd32(input [31:0] a,output [31:0] d);begin @(negedge clk);qa=a;qw=0;qs=1;qe=0;tick(1);@(negedge clk);qe=1;tick(1);d=qrd;@(negedge clk);qs=0;qe=0;tick(1);end endtask
 task acquire(input [1:0] o);integer n;reg [31:0] g;begin
 wr('h34,o);rd('h24,g);wr('h30,g);wr('h38,1);n=0;while(dut.phase!=4&&n<10000)begin tick(1);n++;end check(dut.phase==4,"owner READY");wr('h3c,1);tick(5);check(dut.owner==o&&dut.phase==0,"owner COMMIT");end endtask
 function [31:0] cb(input [31:0] c,input [7:0] b);reg [31:0] x;integer j;begin x=c^b;for(j=0;j<8;j++)x=(x>>1)^(x[0]?32'h82f63b78:0);cb=x;end endfunction
 reg [31:0] cmd[0:31];reg [31:0] v,crc,bufread[0:5];reg [63:0] expiry;integer i,j,n;
 always @(posedge clk)if(check_arm_frames&&resetn&&dut.mon_valid&&dut.mon_local&&dut.mon_ack&&dut.owner==2)begin
  check(seen<6,"six frames maximum");check(dut.mon_id==expected_id[seen],"wire frame ID");check(dut.mon_data==expected_data[seen],"wire payload");seen=seen+1;
 end
 always @(negedge clk)begin
  if(!inject_errors)begin jam=0;jam_state=0;jam_count=0;end
  else case(jam_state)
   0:if(dut.mon_sof)begin jam_state=1;jam_count=0;end
   1:if(jam_count==2400)begin jam=1;jam_count=0;jam_state=2;injected=injected+1;end else jam_count=jam_count+1;
   2:if(jam_count==200)begin jam=0;jam_count=0;jam_state=0;end else jam_count=jam_count+1;
  endcase
 end
 initial begin
 check_arm_frames=0;tick(10);resetn=1;tick(300);
 wr('h34,1);rd('h24,v);wr('h30,v);wr('h38,1);
 n=0;while(dut.phase!=4&&n<10000)begin tick(1);n++;end
 check(dut.phase==4,"cold generic reached READY before configuration");
 tick(30000);
 check(dut.phase==6&&dut.faults==2,"REPRODUCED: disabled CTU falsely diagnosed as runtime bus-off");
 check(dut.errors==0,"false bus-off without REC/TEC");
 test_pass=1;$display("REPRODUCED_COLD_INIT_RACE checks=%0d fault=%h",checks,dut.faults);$finish;
 end
 initial begin #1000000;$fatal(1,"reproducer watchdog");end
endmodule
