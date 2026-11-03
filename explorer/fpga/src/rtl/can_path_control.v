// v2 actual CAN path. Defaults to unchanged PS electrical ownership.
module can_path_control #(parameter CHANNEL=0,CLK_HZ=99999001)(
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 s_axi_aclk CLK", X_INTERFACE_PARAMETER="ASSOCIATED_BUSIF S_AXI, ASSOCIATED_RESET s_axi_aresetn:core_resetn" *) input s_axi_aclk,
 (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 s_axi_aresetn RST", X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) input s_axi_aresetn,
 input can_rx_raw,ps_tx,pl_tx,output can_tx,ps_rx,pl_rx,
 (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 core_resetn RST", X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) output core_resetn,output [63:0] timestamp,
 input core_irq,
 (* X_INTERFACE_INFO="xilinx.com:signal:interrupt:1.0 irq_native INTERRUPT", X_INTERFACE_PARAMETER="SENSITIVITY LEVEL_HIGH" *) output irq_native,
 (* X_INTERFACE_INFO="xilinx.com:signal:interrupt:1.0 irq_control INTERRUPT", X_INTERFACE_PARAMETER="SENSITIVITY LEVEL_HIGH" *) output irq_control,
 output [511:0] debug_bus,
 output [31:0] apb_addr,output apb_sel,apb_enable,apb_write,
 output [31:0] apb_wdata,output [3:0] apb_strb,output [2:0] apb_prot,
 input [31:0] apb_rdata,input apb_ready,apb_error,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWADDR", X_INTERFACE_PARAMETER="PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 16, READ_WRITE_MODE READ_WRITE" *) input [15:0] s_axi_awaddr,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWPROT" *) input [2:0] s_axi_awprot,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWVALID" *) input  s_axi_awvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWREADY" *) output wire  s_axi_awready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WDATA" *) input [31:0] s_axi_wdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WSTRB" *) input [3:0] s_axi_wstrb,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WVALID" *) input  s_axi_wvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WREADY" *) output wire  s_axi_wready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BRESP" *) output wire [1:0] s_axi_bresp,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BVALID" *) output wire  s_axi_bvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BREADY" *) input  s_axi_bready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARADDR" *) input [15:0] s_axi_araddr,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARPROT" *) input [2:0] s_axi_arprot,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARVALID" *) input  s_axi_arvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARREADY" *) output wire  s_axi_arready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RDATA" *) output wire [31:0] s_axi_rdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RRESP" *) output wire [1:0] s_axi_rresp,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RVALID" *) output wire  s_axi_rvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RREADY" *) input  s_axi_rready);
 wire clk=s_axi_aclk,resetn=s_axi_aresetn;
 localparam BUILD=32'h26110303;
 reg [63:0] cycles=0;assign timestamp=cycles;
 wire wvalid,rvalid;reg wready,rready;wire [15:0] waddr,raddr;wire [31:0] wdata;wire [3:0] wstrb;reg [31:0] rdata;
 can_axil_endpoint endpoint(.clk(clk),.resetn(resetn),
.s_axi_awaddr(s_axi_awaddr),.s_axi_awprot(s_axi_awprot),.s_axi_awvalid(s_axi_awvalid),.s_axi_awready(s_axi_awready),.s_axi_wdata(s_axi_wdata),.s_axi_wstrb(s_axi_wstrb),.s_axi_wvalid(s_axi_wvalid),.s_axi_wready(s_axi_wready),.s_axi_bresp(s_axi_bresp),.s_axi_bvalid(s_axi_bvalid),.s_axi_bready(s_axi_bready),.s_axi_araddr(s_axi_araddr),.s_axi_arprot(s_axi_arprot),.s_axi_arvalid(s_axi_arvalid),.s_axi_arready(s_axi_arready),.s_axi_rdata(s_axi_rdata),.s_axi_rresp(s_axi_rresp),.s_axi_rvalid(s_axi_rvalid),.s_axi_rready(s_axi_rready),
 .wr_valid(wvalid),.wr_ready(wready),.wr_addr(waddr),.wr_data(wdata),.wr_strb(wstrb),
 .rd_valid(rvalid),.rd_ready(rready),.rd_addr(raddr),.rd_data(rdata));
 wire [1:0] owner,target,action;wire [2:0] phase;wire [31:0] generation,faults,owner_result,retries,quiet,forced;
 wire stop_core,arm_run,changed,fault_event,initialized,core_stopped,backend_idle;
 wire [31:0] core_faults,errors,device_id,tx_status,mode_shadow,err_status,service_debug;
 wire core_operational;reg [31:0] lifecycle_timeout_ms=1000;
 reg prepare=0,confirm=0,commit=0,heartbeat=0,clear_faults=0,clear_retries=0;
 reg [1:0] requested=0,preferred=2;reg [31:0] token=0,clear_mask=0;
 reg auto_enable=0;reg [31:0] lease_ms=100,retry_ms=1000,retry_limit=0;
 reg [31:0] irq_status=0,irq_mask=1,event_mask=0;
 reg [31:0] fault_errors=0,fault_tx_status=0;reg [63:0] fault_cycle=0;
 wire group_fault;
 can_path_owner #(.CLK_HZ(CLK_HZ)) ownership(.clk(clk),.resetn(resetn),.rx_raw(can_rx_raw),.ps_tx_raw(ps_tx),.pl_tx_raw(pl_tx),
 .prepare(prepare),.requested_owner(requested),.confirm(confirm),.commit(commit),.token(token),.heartbeat(heartbeat),
 .fault_in(core_faults|(group_fault?32'h20:0)),.clear_faults(clear_faults),.clear_mask(clear_mask),
 .core_initialized(initialized),.core_operational(core_operational),.lifecycle_timeout_ms(lifecycle_timeout_ms),.core_stopped(core_stopped),.backend_idle(backend_idle&&!host_pending),
 .idle_cycles(CLK_HZ/1000000*11+11),.lease_ms(lease_ms),.retry_ms(retry_ms),.retry_limit(retry_limit),
 .auto_enable(auto_enable),.preferred_owner(preferred),.clear_retries(clear_retries),
 .owner(owner),.phase(phase),.target(target),.generation(generation),.faults(faults),.result(owner_result),.retry_count(retries),
 .action_request(action),.core_resetn(core_resetn),.stop_core(stop_core),.arm_run(arm_run),.changed(changed),.fault_event(fault_event),
 .tx_pin(can_tx),.ps_rx(ps_rx),.pl_rx(pl_rx),.quiet_count(quiet),.forced_isolations(forced));
 assign irq_native=core_irq&&owner==1&&phase==0;
 assign irq_control=|(irq_status&irq_mask)||action!=0;
 wire native_w=waddr>=16'h4000&&waddr<16'h5000;
 wire native_r=raddr>=16'h4000&&raddr<16'h5000;
 reg host_pending=0,host_sent=0,host_is_write=0,host_complete=0;
 reg [11:0] host_addr=0;reg [31:0] host_data=0,host_read_hold=0;reg [3:0] host_strb=0;
 reg [12:0] host_wait=0;reg [31:0] denied_count=0,control_result=0;
 wire host_ready,host_done,host_denied;wire [31:0] host_read;
 wire frame_valid,frame_ready,frame_done;wire [2:0] frame_result,frame_index;wire [10:0] frame_id;
 wire [63:0] frame_data,frame_deadline,active_trace;wire [31:0] active_seq,active_generation;
 can_core_service #(.CLK_HZ(CLK_HZ)) service(.clk(clk),.resetn(resetn),.core_resetn(core_resetn),.owner(owner),.target(target),.phase(phase),
 .stop_core(stop_core),.cycles(cycles),.lifecycle_timeout_ms(lifecycle_timeout_ms),.host_valid(host_pending&&!host_sent&&!host_complete),.host_write(host_is_write),
 .host_addr(host_addr),.host_wdata(host_data),.host_strb(host_strb),.host_ready(host_ready),.host_done(host_done),.host_rdata(host_read),.host_denied(host_denied),
 .frame_valid(frame_valid),.frame_ready(frame_ready),.frame_id(frame_id),.frame_data(frame_data),.frame_deadline(frame_deadline),.frame_done(frame_done),.frame_result(frame_result),
 .initialized(initialized),.core_operational(core_operational),.mode_shadow(mode_shadow),.err_status(err_status),.debug_state(service_debug),.core_stopped(core_stopped),.backend_idle(backend_idle),.fault_bits(core_faults),.error_counters(errors),.device_id(device_id),.tx_status(tx_status),
 .apb_addr(apb_addr),.apb_sel(apb_sel),.apb_enable(apb_enable),.apb_write(apb_write),.apb_wdata(apb_wdata),.apb_strb(apb_strb),.apb_prot(apb_prot),
 .apb_rdata(apb_rdata),.apb_ready(apb_ready),.apb_error(apb_error));
 wire full_write=wstrb==15&&waddr[1:0]==0;
 wire write_fire=wvalid&&wready;
 wire stage_write=write_fire&&full_write&&waddr>=16'h1000&&waddr<16'h1080;
 wire submit=write_fire&&full_write&&waddr==16'h1080&&wdata==32'h41524d32;
 wire [31:0] engine_event_lost;
 wire validating,engine_busy,engine_event;wire [31:0] engine_result,stage_read,accepted,rejected,expired_count;
 wire [6:0] queue_count;wire [15:0] engine_kind;wire [31:0] engine_seq,engine_aux;wire [63:0] engine_trace;
 arm_command_engine #(.CHANNEL(CHANNEL),.CLK_HZ(CLK_HZ)) engine(.clk(clk),.resetn(resetn),.run(arm_run),.generation(generation),.cycles(cycles),
 .stage_write(stage_write),.stage_index(waddr[6:2]),.stage_data(wdata),.submit(submit),.validating(validating),.result(engine_result),
 .stage_read(stage_read),.stage_read_index(raddr[6:2]),.queue_count(queue_count),.accepted(accepted),.rejected(rejected),.expired_count(expired_count),
 .frame_valid(frame_valid),.frame_ready(frame_ready),.frame_id(frame_id),.frame_data(frame_data),.frame_deadline(frame_deadline),.frame_done(frame_done),.frame_result(frame_result),
 .active_generation(active_generation),.active_seq(active_seq),.active_trace(active_trace),.active_index(frame_index),.event_valid(engine_event),.event_kind(engine_kind),
 .event_seq(engine_seq),.event_aux(engine_aux),.event_trace(engine_trace),.group_fault(group_fault),.event_lost(engine_event_lost),.busy(engine_busy));
 wire mon_sof,mon_valid,mon_ack,mon_local;wire [10:0] mon_id;wire [3:0] mon_dlc;wire [63:0] mon_data,mon_sof_cycle,mon_eof_cycle;
 can_passive_monitor monitor(.clk(clk),.resetn(resetn),.cycles(cycles),.rx_raw(can_rx_raw),.tx_raw(can_tx),
 .sof_valid(mon_sof),.frame_valid(mon_valid),.frame_id(mon_id),.frame_dlc(mon_dlc),.frame_data(mon_data),.frame_ack(mon_ack),.frame_local(mon_local),
 .sof_cycle(mon_sof_cycle),.eof_cycle(mon_eof_cycle),.frame_count(),.error_count(),.unsupported_count(),.ack_missing_count());
 reg [127:0] feedback[0:19],feedback_snap[0:19];reg [19:0] feedback_valid=0,feedback_valid_snap=0;reg [31:0] snap_seq=0;
 function integer fb_index(input [10:0] id);begin
 if(id>=11'h251&&id<=11'h256)fb_index=id-11'h251;
 else if(id>=11'h261&&id<=11'h266)fb_index=6+id-11'h261;
 else if(id>=11'h2a1&&id<=11'h2a8)fb_index=12+id-11'h2a1;else fb_index=-1;
 end endfunction
 // One serialized event writer. Concurrent event sources and full ring increment loss count.
 (* ram_style="block" *) reg [511:0] events[0:255];
 reg [7:0] event_wr=0,event_rd=0,event_pref=0;reg [8:0] event_count=0;
 reg [511:0] event_head=0;reg event_ready=0;reg [31:0] event_lost=0;
 reg [511:0] event_payload;reg [3:0] event_sources;reg [15:0] selected_kind;
 reg [31:0] selected_seq,selected_aux,selected_generation;reg [63:0] selected_trace,selected_cycle,selected_data;
 wire event_pop=write_fire&&full_write&&waddr==16'h00a8&&wdata==1&&event_count!=0&&event_ready;
 wire event_push=event_sources!=0&&event_count<256;
 always @*begin
  event_sources=0;selected_generation=generation;selected_kind=0;selected_seq=0;selected_trace=0;selected_aux=0;selected_cycle=cycles;selected_data=0;
  if(event_mask[0]&&engine_event)begin event_sources=event_sources+1;selected_kind=engine_kind;selected_seq=engine_seq;selected_trace=engine_trace;selected_aux=engine_aux;end
  if(event_mask[1]&&frame_done)begin event_sources=event_sources+1;selected_kind=16'h0302;selected_generation=active_generation;selected_seq=active_seq;selected_trace=active_trace;selected_aux={16'b0,frame_result,frame_index,10'b0};selected_data=frame_data;end
  if(event_mask[2]&&mon_sof&&engine_busy&&owner==2&&!can_tx)begin event_sources=event_sources+1;selected_kind=16'h0301;selected_generation=active_generation;selected_seq=active_seq;selected_trace=active_trace;selected_cycle=mon_sof_cycle;end
  if(event_mask[3]&&mon_valid)begin event_sources=event_sources+1;selected_kind=16'h0402;selected_generation=generation;selected_seq=0;selected_trace=0;selected_cycle=mon_eof_cycle;selected_aux={14'b0,mon_local,mon_ack,mon_dlc,1'b0,mon_id};selected_data=mon_data;end
  if(event_mask[4]&&changed)begin event_sources=event_sources+1;selected_kind=16'h0500;selected_generation=generation;selected_seq=0;selected_trace=0;selected_aux={25'b0,target,phase,owner};end
  if(event_mask[4]&&fault_event)begin event_sources=event_sources+1;selected_kind=16'h0501;selected_generation=generation;selected_seq=0;selected_trace=0;selected_aux=faults;end
  event_payload=0;event_payload[0+:32]=32'h00400002;event_payload[32+:32]=BUILD;
  event_payload[64+:32]=selected_generation;event_payload[96+:16]=selected_kind;event_payload[112+:16]=CHANNEL;
  event_payload[128+:32]=selected_seq;event_payload[160+:32]=selected_aux;
  event_payload[192+:64]=selected_trace;event_payload[256+:64]=selected_cycle;event_payload[320+:64]=selected_data;
 end
 always @*begin
  wready=!native_w;rready=!native_r;rdata=0;
  if(native_w)wready=host_pending&&host_is_write&&host_complete;
  if(native_r)begin rready=host_pending&&!host_is_write&&host_complete;rdata=host_read_hold;end
  else case(raddr)
   16'h000:rdata=32'h4b434132;16'h004:rdata=32'h00020001;16'h008:rdata=BUILD;16'h00c:rdata=32'h000001ff;
   16'h010:rdata=CLK_HZ;16'h014:rdata=CHANNEL;16'h018:rdata=cycles[31:0];16'h01c:rdata=cycles[63:32];
   16'h0d0:rdata=mode_shadow;16'h0d4:rdata=err_status;16'h0d8:rdata=service_debug;16'h0dc:rdata=lifecycle_timeout_ms;
   16'h020:rdata={23'b0,initialized,core_resetn,target,phase,owner};16'h024:rdata=generation;16'h028:rdata=faults;16'h02c:rdata=owner_result;
   16'h030:rdata=token;16'h048:rdata={22'b0,preferred,7'b0,auto_enable};16'h04c:rdata=lease_ms;16'h050:rdata=retry_ms;16'h054:rdata=retry_limit;
   16'h058:rdata=retries;16'h05c:rdata={30'b0,action};16'h060:rdata=quiet;16'h064:rdata=forced;
   16'h068:rdata=device_id;16'h06c:rdata=errors;16'h070:rdata=tx_status;16'h074:rdata=irq_status;16'h078:rdata=irq_mask;
   16'h080:rdata={25'b0,queue_count};16'h084:rdata=engine_result;16'h088:rdata=accepted;16'h08c:rdata=rejected;16'h090:rdata=expired_count;
   16'h094:rdata={30'b0,validating,engine_busy};16'h098:rdata={12'b0,feedback_valid_snap};16'h09c:rdata=snap_seq;
   16'h0a4:rdata={22'b0,event_ready,event_count};16'h0ac:rdata=event_lost;16'h0b0:rdata=denied_count;16'h0b4:rdata=event_mask;16'h0b8:rdata=control_result;16'h0bc:rdata=engine_event_lost;16'h0c0:rdata=fault_errors;16'h0c4:rdata=fault_tx_status;16'h0c8:rdata=fault_cycle[31:0];16'h0cc:rdata=fault_cycle[63:32];
   default:begin
    if(raddr>=16'h100&&raddr<16'h240)rdata=feedback_snap[(raddr-16'h100)>>4][raddr[3:2]*32+:32];
    if(raddr>=16'h800&&raddr<16'h840&&event_ready&&event_count!=0)rdata=event_head[raddr[5:2]*32+:32];
    if(raddr>=16'h1000&&raddr<16'h1080)rdata=stage_read;
   end
  endcase
 end
 assign debug_bus={
  {14'b0,frame_index,frame_result,frame_done,frame_ready,frame_valid,engine_busy,validating,queue_count},
  service_debug,
  {8'b0,host_pending,host_sent,host_complete,prepare,confirm,commit,heartbeat,stop_core,core_operational,initialized,core_resetn,can_rx_raw,ps_tx,pl_tx,can_tx,backend_idle,core_stopped,owner,phase,target},
  quiet,tx_status,apb_rdata,apb_wdata,apb_addr,mode_shadow,errors,err_status,core_faults,faults,generation,cycles[31:0],32'h43414e33};
 integer i,fbi;
 always @(posedge clk)begin
  prepare<=0;confirm<=0;commit<=0;heartbeat<=0;clear_faults<=0;clear_retries<=0;
  event_head<=events[event_rd];event_pref<=event_rd;event_ready<=event_pref==event_rd;
  if(!resetn)begin
   cycles<=0;lifecycle_timeout_ms<=1000;fault_errors<=0;fault_tx_status<=0;fault_cycle<=0;token<=0;auto_enable<=0;preferred<=2;lease_ms<=100;retry_ms<=1000;retry_limit<=0;
   host_pending<=0;host_sent<=0;host_complete<=0;host_wait<=0;denied_count<=0;control_result<=0;
   irq_status<=0;irq_mask<=1;event_mask<=0;event_count<=0;event_wr<=0;event_rd<=0;event_ready<=0;event_lost<=0;
   feedback_valid<=0;feedback_valid_snap<=0;snap_seq<=0;
   for(i=0;i<20;i=i+1)begin feedback[i]<=0;feedback_snap[i]<=0;end
  end else begin
   cycles<=cycles+1;
   if(!host_pending)begin
    if(wvalid&&native_w||rvalid&&native_r)begin
     host_pending<=1;host_sent<=0;host_complete<=0;host_wait<=0;host_is_write<=wvalid&&native_w;
     host_addr<=(wvalid&&native_w)?waddr[11:0]:raddr[11:0];host_data<=wdata;host_strb<=wstrb;
     if(!core_resetn||!initialized||stop_core)begin host_complete<=1;host_read_hold<=32'hffffffff;denied_count<=denied_count+1;end
    end
   end else begin
    if(host_ready)host_sent<=1;
    if(host_done)begin host_complete<=1;host_read_hold<=host_read;if(host_denied)denied_count<=denied_count+1;end
    if(!host_complete)begin
     if(host_wait==4095)begin host_complete<=1;host_read_hold<=32'hffffffff;denied_count<=denied_count+1;end
     else host_wait<=host_wait+1;
    end
    if(host_complete&&((host_is_write&&write_fire)||(!host_is_write&&rvalid&&rready)))begin host_pending<=0;host_complete<=0;host_sent<=0;end
   end
   if(write_fire)begin
    if(!full_write&&!native_w)control_result<=1;
    else if(!native_w)case(waddr)
     16'h030:token<=wdata;
     16'h034:if(wdata<3)begin requested<=wdata[1:0];prepare<=1;end else control_result<=2;
     16'h038:if(wdata==1)confirm<=1;
     16'h03c:if(wdata==1)commit<=1;
     16'h040:if(wdata==1)heartbeat<=1;
     16'h044:begin clear_faults<=1;clear_mask<=wdata;end
     16'h048:if((wdata&32'hfffffcfe)==0&&wdata[9:8]!=3)begin auto_enable<=wdata[0];preferred<=wdata[9:8];end else control_result<=2;
     16'h04c:if(wdata>=10&&wdata<=60000)lease_ms<=wdata;else control_result<=2;
     16'h050:if(wdata>=1000)retry_ms<=wdata;else control_result<=2;
     16'h054:retry_limit<=wdata;
     16'h058:if(wdata==1)clear_retries<=1;
     16'h078:irq_mask<=wdata;
     16'h07c:irq_status<=irq_status&~wdata;
     16'h0a0:if(wdata==1)begin for(i=0;i<20;i=i+1)feedback_snap[i]<=feedback[i];feedback_valid_snap<=feedback_valid;snap_seq<=snap_seq+1;end
     16'h0b4:event_mask<=wdata;
     16'h0b8:control_result<=0;
     16'h0dc:if(wdata>=100&&wdata<=5000&&owner==0&&phase==0)lifecycle_timeout_ms<=wdata;else control_result<=2;
    endcase
   end
   if(fault_event)begin irq_status[0]<=1;fault_errors<=errors;fault_tx_status<=tx_status;fault_cycle<=cycles;end
   if(event_push)begin if(event_count==0)event_ready<=0;events[event_wr]<=event_payload;event_wr<=event_wr+1;irq_status[1]<=1;end
   if(event_sources!=0)event_lost<=event_lost+event_sources-(event_push?1:0);
   if(event_pop)begin event_rd<=event_rd+1;event_ready<=0;end
   case({event_push,event_pop})2'b10:event_count<=event_count+1;2'b01:event_count<=event_count-1;endcase
   if(mon_valid&&mon_ack&&mon_dlc==8)begin
    fbi=fb_index(mon_id);if(fbi>=0)begin feedback[fbi]<={mon_eof_cycle,mon_data};feedback_valid[fbi]<=1;end
   end
  end
 end
endmodule
