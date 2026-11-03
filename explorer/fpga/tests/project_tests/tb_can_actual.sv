`timescale 1ns/1ps
module tb_can_actual;
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
 task operational;integer k;begin k=0;while(!dut.core_operational&&k<30000)begin tick(1);k++;end check(dut.core_operational,"CAN enabled and error-active/passive observed");end endtask
 task acquire(input [1:0] o);integer n;reg [31:0] g;begin
 wr('h34,o);rd('h24,g);wr('h30,g);wr('h38,1);n=0;while(dut.phase!=4&&n<10000)begin tick(1);n++;end check(dut.phase==4,"owner READY");
 if(o==1)begin wr('h4004,0);wr('h4024,(2<<27)|(1<<19)|(25<<13)|(37<<7)|37);wr('h4004,32'h00400000);end
 if(o!=0)operational();
 n=0;while(dut.phase==4&&n<200)begin wr('h3c,1);tick(100);n++;end
 check(dut.owner==o&&dut.phase==0,"owner COMMIT");end endtask
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
 expected_id[0]='h151;expected_id[1]='h151;expected_id[2]='h155;expected_id[3]='h156;expected_id[4]='h157;expected_id[5]='h159;
 expected_data[0]=64'h0101640000000000;expected_data[1]=expected_data[0];expected_data[2]=64'h00000064ffffff38;expected_data[3]=64'h0000012cfffffe70;expected_data[4]=64'h000001f4fffffda8;expected_data[5]=64'h000003e800070100;
 tick(10);resetn=1;tick(200);wr('hb4,32'h17);rd('h68,v);check(v==32'h0202cafd,"CTU version verified");
 pwr('h4,0);pwr('h24,(2<<27)|(1<<19)|(25<<13)|(37<<7)|37);pwr('h4,32'h00400000);tick(2000);
 acquire(2);tick(2000);check(dut.initialized,"core initialized");
 for(i=0;i<32;i++)cmd[i]=0;
 cmd[0]=32'h4b434132;cmd[1]=32'h00800002;cmd[2]=dut.generation;cmd[3]=1;cmd[4]=32'habcde123;
 expiry=dut.cycles+1000000;cmd[8]=expiry[31:0];cmd[9]=expiry[63:32];cmd[10]=32'h300;
 cmd[11]=100;cmd[12]=-200;cmd[13]=300;cmd[14]=-400;cmd[15]=500;cmd[16]=-600;cmd[17]=1000;cmd[18]=32'h00010007;cmd[19]=1;
 crc=32'hffffffff;for(i=0;i<128;i++)if(i<92||i>=96)crc=cb(crc,cmd[i/4]>>(8*(i%4)));cmd[23]=~crc;
 for(i=0;i<32;i++)wr('h1000+i*4,cmd[i]);wr('h1080,32'h41524d32);tick(150);rd('h84,v);check(v==0,"command admitted");
 n=0;while(seen<6&&n<300000)begin tick(1);n++;end check(seen==6,"six actual ACKed CAN frames");
 tick(1000);check(!dut.engine_busy,"group completed");check(dut.faults==0,"no path fault");
 prd32('h84,v);check(v==6,"peer received six frames");

 check_arm_frames=0;
 // Drain the six peer RX FIFO records, verifying native APB reads pop exactly once.
 for(i=0;i<6;i++)begin
  for(j=0;j<6;j++)prd32('h6c,bufread[j]);
  check(bufread[1][28:18]==expected_id[i],"peer RX FIFO standard ID");
  check(bufread[4]=={expected_data[i][39:32],expected_data[i][47:40],expected_data[i][55:48],expected_data[i][63:56]},"peer native RX first word");
 end
 acquire(1);wr('h4004,0);wr('h4024,(2<<27)|(1<<19)|(25<<13)|(37<<7)|37);wr('h4004,32'h00400000);operational();tick(2000);
 // Native generic standard CAN transmit; completion comes from CTU register.
 wr('h4100,8);wr('h4104,'h123<<18);wr('h4108,0);wr('h410c,0);wr('h4110,32'h44332211);wr('h4114,32'h88776655);wr('h4074,'h102);
 n=0;v=0;while(v[3:0]!=4&&n<2000)begin rd('h4070,v);tick(100);n++;end check(v[3:0]==4,"generic native TX completed");
 prd32('h84,v);check(v==7,"generic frame reached peer");
 for(j=0;j<6;j++)prd32('h6c,bufread[j]);check(bufread[1][28:18]=='h123&&bufread[4]==32'h44332211&&bufread[5]==32'h88776655,"generic payload native FIFO");
 // Peer sends feedback back to the generic controller, exercise receive and full 2A8 slot.
 pwr('h100,8);pwr('h104,'h2a8<<18);pwr('h108,0);pwr('h10c,0);pwr('h110,32'h78563412);pwr('h114,32'hefcdab90);pwr('h74,'h102);
 n=0;v=0;while(v==0&&n<2000)begin rd('h4084,v);tick(100);n++;end check(v==1,"generic receives peer frame");
 tick(1000);wr('ha0,1);rd('h98,v);check(v[19],"full feedback slot 2A8 valid");
 rd('h230,v);check(v==32'h90abcdef,"2A8 wire bytes low word");rd('h234,v);check(v==32'h12345678,"2A8 wire bytes high word");
 for(j=0;j<6;j++)rd('h406c,bufread[j]);check(bufread[1][28:18]=='h2a8&&bufread[4]==32'h78563412,"generic RX FIFO words");
 // Public Classic CAN interface rejects FD rather than silently changing the frame.
 rd('hb0,crc);wr('h4100,32'h88);rd('hb0,v);check(v==crc+1,"FD frame write rejected");wr('h4074,'h102);rd('hb0,v);check(v==crc+2,"READY for invalid FD buffer rejected");
 // Extended Classic data frame and RTR use the underlying controller unchanged.
 wr('h4074,'h101);wr('h4100,'h48);wr('h4104,29'h1234567);wr('h4110,32'hdeadbeef);wr('h4114,32'h01234567);wr('h4074,'h102);
 n=0;v=0;while(v[3:0]!=4&&n<2000)begin rd('h4070,v);tick(100);n++;end check(v[3:0]==4,"extended Classic TX");
 for(j=0;j<6;j++)prd32('h6c,bufread[j]);check(bufread[0][6]&&bufread[1][28:0]==29'h1234567&&bufread[4]==32'hdeadbeef,"extended peer RX");
 wr('h4074,'h101);wr('h4100,'h28);wr('h4104,'h321<<18);wr('h4074,'h102);
 n=0;v=0;while(v[3:0]!=4&&n<2000)begin rd('h4070,v);tick(100);n++;end check(v[3:0]==4,"Classic RTR TX");
 for(j=0;j<4;j++)prd32('h6c,bufread[j]);check(bufread[0][5]&&bufread[1][28:18]=='h321,"RTR peer RX");

 // Two pending transmitters share a future timestamp and arbitrate on the wire.
 expiry=dut.cycles+10000;
 wr('h4074,'h101);wr('h4100,8);wr('h4104,'h700<<18);wr('h4108,expiry[31:0]);wr('h410c,expiry[63:32]);wr('h4110,32'h11111111);wr('h4114,32'h22222222);
 pwr('h74,'h101);pwr('h100,8);pwr('h104,'h001<<18);pwr('h108,expiry[31:0]);pwr('h10c,expiry[63:32]);pwr('h110,32'h33333333);pwr('h114,32'h44444444);
 wr('h4014,'h20);wr('h4020,'h20);wr('h4010,32'hffffffff);
 wr('h4074,'h102);pwr('h74,'h102);n=0;v=0;
 while(v[3:0]!=4&&n<3000)begin rd('h4070,v);tick(100);n++;end check(v[3:0]==4,"arbitration loser eventually transmits");
 prd32('h70,v);check(v[3:0]==4,"arbitration winner transmits");rd('h4010,v);check(v[5],"actual arbitration-loss status");
 for(j=0;j<6;j++)rd('h406c,bufread[j]);check(bufread[1][28:18]=='h001&&bufread[4]==32'h33333333,"lower ID peer frame received first");
 for(j=0;j<6;j++)prd32('h6c,bufread[j]);check(bufread[1][28:18]=='h700&&bufread[4]==32'h11111111,"higher ID frame received after arbitration");
 acquire(0);check(tx==1&&psrx==bus,"return to PS path");
 // No ACK must never be reported as a successful physical transmission.
 pwr('h4,0);acquire(2);cmd[2]=dut.generation;cmd[3]=2;cmd[10]='h200;
 expiry=dut.cycles+100000;cmd[8]=expiry[31:0];cmd[9]=expiry[63:32];
 crc=32'hffffffff;for(i=0;i<128;i++)if(i<92||i>=96)crc=cb(crc,cmd[i/4]>>(8*(i%4)));cmd[23]=~crc;
 for(i=0;i<32;i++)wr('h1000+i*4,cmd[i]);wr('h1080,32'h41524d32);
 n=0;while(dut.phase!=6&&n<300000)begin tick(1);n++;end check(dut.phase==6&&dut.faults[5],"no ACK deadline faults and isolates");
 check(dut.engine.completed==0,"no ACK never advances completed frame count");check(dut.owner==3&&tx==1,"fault leaves pin recessive");

 // Bus-off is induced with physical data-phase bit errors, not counter register forcing.
 pwr('h4,32'h00400000);acquire(1);wr('h4004,0);wr('h4024,(2<<27)|(1<<19)|(25<<13)|(37<<7)|37);wr('h4004,32'h00410000);operational();tick(2000);
 wr('h4100,8);wr('h4104,'h123<<18);wr('h4108,0);wr('h410c,0);wr('h4110,32'hffffffff);wr('h4114,32'hffffffff);
 inject_errors=1;wr('h4074,'h102);n=0;
 while(dut.phase!=6&&n<10000)begin
  rd('h4070,v);tick(200);n++;
  if(dut.phase==0&&(v[3:0]==4||v[3:0]==6||v[3:0]==7))begin
   tick(1500);wr('h4074,'h101);wr('h4074,'h102);
  end
 end
 inject_errors=0;tick(2);check(dut.phase==6&&dut.faults[1],"real bus-off detected and isolated");check(injected>=32,"bus-off from repeated physical errors");
 acquire(0);check(dut.owner==0,"manual PS recovery after bus-off");
 test_pass=1; $display("PASS tb_can_actual checks=%0d frames=%0d",checks,seen);$finish;
 end
 initial begin #20000000;$fatal(1,"watchdog");end
endmodule
