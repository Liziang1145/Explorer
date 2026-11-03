`timescale 1ns/1ps
module tb_can_owner;
 reg test_pass=0;
 reg clk=0;always #5 clk=~clk;
 reg resetn=0,rx=1,ps=1,pl=1,prepare=0,confirm=0,commit=0,hb=0,clear=0;
 reg [31:0] retry_limit=2;reg [1:0] req=0,pref=2;reg [31:0] token=0,fault=0;
 reg init=1,stopped=1,idle=1,auto_en=0,clear_retries=0;
 wire [1:0] owner,target,action;wire [2:0] phase;wire [31:0] gen,faults,result,retries,quiet,forced;
 wire crst,stop,run,changed,fe,tx,psrx,plrx;
 can_path_owner #(.CLK_HZ(100000)) dut(.clk(clk),.resetn(resetn),.rx_raw(rx),.ps_tx_raw(ps),.pl_tx_raw(pl),
 .prepare(prepare),.requested_owner(req),.confirm(confirm),.commit(commit),.token(token),.heartbeat(hb),
 .fault_in(fault),.clear_faults(clear),.clear_mask(32'hffffffff),.core_operational(1'b1),.lifecycle_timeout_ms(32'd1000),.core_initialized(init),.core_stopped(stopped),.backend_idle(idle),
 .idle_cycles(32'd11),.lease_ms(32'd10),.retry_ms(32'd2),.retry_limit(retry_limit),.auto_enable(auto_en),.preferred_owner(pref),
 .clear_retries(clear_retries),.owner(owner),.phase(phase),.target(target),.generation(gen),.faults(faults),.result(result),
 .retry_count(retries),.action_request(action),.core_resetn(crst),.stop_core(stop),.arm_run(run),.changed(changed),.fault_event(fe),
 .tx_pin(tx),.ps_rx(psrx),.pl_rx(plrx),.quiet_count(quiet),.forced_isolations(forced));
 integer checks=0,k;
 task check(input bit v,input string msg);begin checks++;if(!v)$fatal(1,"FAIL %s owner=%d phase=%d gen=%d",msg,owner,phase,gen);end endtask
 task tick(input integer n);repeat(n)begin @(posedge clk);#1;end endtask
 task prep(input [1:0] own);begin @(negedge clk);req=own;prepare=1;tick(1);@(negedge clk);prepare=0;end endtask
 task ack;begin @(negedge clk);token=gen;confirm=1;tick(1);@(negedge clk);confirm=0;end endtask
 task go;begin @(negedge clk);token=gen;commit=1;tick(1);@(negedge clk);commit=0;end endtask
 task ready;integer n;begin n=0;while(phase!=4&&n<100)begin tick(1);n++;end check(phase==4,"READY bounded");end endtask
 task handover(input [1:0] own);begin prep(own);ack();ready();go();check(owner==own&&phase==0,"handover");end endtask
 initial begin
 tick(3);resetn=1;tick(30);check(owner==0&&tx==ps&&crst,"boot PS");
 prep(2);tick(40);check(owner==0&&phase==1,"no confirmation cannot switch");
 @(negedge clk);token=gen-1;confirm=1;tick(1);@(negedge clk);confirm=0;tick(5);check(result==2&&owner==0,"stale confirmation rejected");
 stopped=0;ack();tick(30);check(owner==0,"wait outstanding transmission");stopped=1;
 rx=0;tick(20);check(owner==0,"dominant bus prevents switching");rx=1;ready();
 @(negedge clk);token=gen-1;commit=1;tick(1);@(negedge clk);commit=0;check(owner==3&&result==2,"stale COMMIT rejected");
 go();check(owner==2&&run,"ARM ownership");
 @(negedge clk);pl=0;ps=1;#1;check(tx==0&&psrx==1,"PL drive only");rx=0;#1;check(plrx==0&&psrx==1,"only owner sees RX");pl=1;rx=1;
 fault=2;tick(1);fault=0;tick(10);check(owner==3&&phase==6&&faults[1]&&action==0,"manual fault isolates");
 tick(250);check(owner==3,"manual does not reconnect PS");
 handover(0);auto_en=1;tick(220);check(action==2,"automatic PL preference request");
 handover(2);check(retries==1,"retry counted");fault=2;tick(1);fault=0;tick(10);check(action==1&&owner==3,"automatic requests fallback but does not release stale PS");
 handover(0);tick(220);check(action==2,"second retry request");handover(2);check(retries==2,"second retry count");
 fault=2;tick(1);fault=0;tick(10);handover(0);tick(250);check(action==0,"retry maximum respected");
 clear_retries=1;tick(1);clear_retries=0;tick(220);check(action==2,"retry reset restarts budget");auto_en=0;tick(1);check(action==0,"AUTO off clears request");
 handover(2);tick(1100);check(owner==3&&faults[0],"heartbeat expiry isolates");

 retry_limit=0;auto_en=1;clear_retries=1;tick(1);clear_retries=0;
 for(k=0;k<5;k++)begin
  handover(0);tick(220);check(action==2,"unlimited policy retries beyond three");
  handover(2);fault=2;tick(1);fault=0;tick(10);check(owner==3&&action==1,"unlimited cycle fallback request");
 end
 check(retries==5,"zero limit permits five retries without cap");auto_en=0;tick(2);check(owner==3&&action==0,"AUTO off preserves isolation");
 handover(2);check(owner==2,"manual PL recovery with AUTO disabled");
 test_pass=1; $display("PASS tb_can_owner checks=%0d",checks);$finish;
 end
 initial begin #1000000;$fatal(1,"watchdog");end
endmodule
