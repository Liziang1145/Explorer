`timescale 1ns/1ps
module tb_can_service_lifecycle;
reg clk=0;always #5 clk=~clk;
reg resetn=0,crst=0,stop=0,hv=0,hw=0;reg[1:0] owner=0,target=0;reg[2:0] phase=0;
reg[11:0] ha=0;reg[31:0] hd=0;reg[3:0] hs=15;reg[63:0] cycles=0;
reg[31:0] es=32'h40000; wire[31:0] addr,wd,mode,err,dbg,fault;wire sel,en,wr,hr,done,denied,init,op;
wire[31:0] rd=(addr==0)?32'h0202cafd:((addr=='h2c)?es:((addr=='h70)?32'h8888:0));
always @(posedge clk)cycles<=cycles+1;
can_core_service #(.CLK_HZ(100000)) dut(.clk(clk),.resetn(resetn),.core_resetn(crst),.owner(owner),.target(target),.phase(phase),.stop_core(stop),.cycles(cycles),.lifecycle_timeout_ms(32'd200),
.host_valid(hv),.host_write(hw),.host_addr(ha),.host_wdata(hd),.host_strb(hs),.host_ready(hr),.host_done(done),.host_denied(denied),
.frame_valid(1'b0),.frame_id(11'b0),.frame_data(64'b0),.frame_deadline(64'b0),.initialized(init),.core_operational(op),.mode_shadow(mode),.err_status(err),.debug_state(dbg),.fault_bits(fault),
.apb_addr(addr),.apb_sel(sel),.apb_enable(en),.apb_write(wr),.apb_wdata(wd),.apb_rdata(rd),.apb_ready(1'b1),.apb_error(1'b0));
integer checks=0;reg test_pass=0;
task tick(input integer n);repeat(n)begin @(posedge clk);#1;end endtask
task check(input bit v,input string s);begin checks++;if(!v)$fatal(1,"%s fault=%h mode=%h op=%b",s,fault,mode,op);end endtask
task boot;begin resetn=0;crst=0;owner=0;target=0;phase=0;stop=0;hv=0;es='h40000;tick(3);resetn=1;crst=1;tick(100);check(init,"initialized");end endtask
task write_mode(input[31:0] v,input[3:0] mask);integer n;begin @(negedge clk);ha=4;hd=v;hs=mask;hw=1;hv=1;n=0;while(!hr&&n<100)begin tick(1);n++;end tick(1);@(negedge clk);hv=0;n=0;while(!done&&n<100)begin tick(1);n++;end check(done&&!denied,"MODE APB completed");end endtask
initial begin
boot();tick(25000);check(fault==0&&!op,"PS disabled BOF is normal");
owner=3;target=1;phase=4;write_mode('h00400000,15);tick(12000);check(!op&&fault==0,"enabled BOF unqualified in READY");
es='h10000;tick(11000);check(op,"active qualifies");owner=1;phase=0;es='h40000;tick(11000);check(fault==2&&!op,"real runtime BOF faults");
boot();owner=1;target=1;phase=0;tick(21000);check(fault=='h80,"RUN disabled timeout distinct");
boot();owner=3;target=1;phase=4;write_mode('h00400000,15);owner=1;phase=0;tick(21000);check(fault=='h100,"RUN enabled unqualified timeout distinct");
boot();owner=3;target=1;phase=4;write_mode('h00400000,15);es='h10000;tick(11000);check(op,"qualified before native stop");owner=1;phase=0;write_mode(0,1);check(mode[22]&&op,"low-byte write preserves ENA qualification");write_mode(0,4);es='h40000;tick(11000);check(!op&&fault==0,"native disable suppresses expected BOF");
check(dbg[18]&&dbg[15]==op,"APB ready and qualification probe mapping");
test_pass=1;$display("PASS tb_can_service_lifecycle checks=%0d",checks);$finish;
end
initial begin #2000000;$fatal(1,"watchdog");end
endmodule
