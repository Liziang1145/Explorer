// ABI 1.0 SHADOW-ONLY: all non-AXI ports are inputs. No physical transmit permission.
module pl_shadow #(parameter CLK_HZ=99999001)(
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 s_axi_aclk CLK", X_INTERFACE_PARAMETER="ASSOCIATED_BUSIF S_AXI, ASSOCIATED_RESET s_axi_aresetn" *) input s_axi_aclk,
 (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 s_axi_aresetn RST", X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) input s_axi_aresetn,
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 eth_clk CLK", X_INTERFACE_PARAMETER="FREQ_HZ 125000000" *) input eth_clk,
 input can0_rx_raw,can0_tx_raw,can1_rx_raw,can1_tx_raw,
 input tx2_valid,tx2_ready,tx2_last,input [3:0] tx2_keep,
 input rx2_valid,rx2_ready,rx2_last,input [3:0] rx2_keep,
 input tx3_valid,tx3_ready,tx3_last,input [3:0] tx3_keep,
 input rx3_valid,rx3_ready,rx3_last,input [3:0] rx3_keep,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWADDR", X_INTERFACE_PARAMETER="PROTOCOL AXI4LITE, DATA_WIDTH 32, ADDR_WIDTH 16, READ_WRITE_MODE READ_WRITE" *) input [15:0] s_axi_awaddr,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWPROT" *) input [2:0] s_axi_awprot,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWVALID" *) input  s_axi_awvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI AWREADY" *) output wire  s_axi_awready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WDATA" *) input [31:0] s_axi_wdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WSTRB" *) input [3:0] s_axi_wstrb,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WVALID" *) input  s_axi_wvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI WREADY" *) output wire  s_axi_wready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BRESP" *) output reg [1:0] s_axi_bresp,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BVALID" *) output reg  s_axi_bvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI BREADY" *) input  s_axi_bready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARADDR" *) input [15:0] s_axi_araddr,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARPROT" *) input [2:0] s_axi_arprot,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARVALID" *) input  s_axi_arvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI ARREADY" *) output wire  s_axi_arready,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RDATA" *) output reg [31:0] s_axi_rdata,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RRESP" *) output reg [1:0] s_axi_rresp,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RVALID" *) output reg  s_axi_rvalid,
 (* X_INTERFACE_INFO="xilinx.com:interface:aximm:1.0 S_AXI RREADY" *) input  s_axi_rready);

 wire clk=s_axi_aclk, resetn=s_axi_aresetn;
 wire [3:0] stream_valid={rx3_valid,tx3_valid,rx2_valid,tx2_valid};
 wire [3:0] stream_ready={rx3_ready,tx3_ready,rx2_ready,tx2_ready};
 wire [3:0] stream_last={rx3_last,tx3_last,rx2_last,tx2_last};
 wire [15:0] stream_keep={rx3_keep,tx3_keep,rx2_keep,tx2_keep};
 localparam BUILD=32'h26110201;
 reg [63:0] cycle=0;
 reg mode=0; reg [31:0] epoch=0, boot_cookie=0;
 reg [31:0] period=CLK_HZ/200, timeout_ticks=CLK_HZ/10, tick_left=CLK_HZ/200;
 reg [31:0] event_mask=0, faults=0, rejected=0, stale=0, accepted=0;
 reg [31:0] last_seq[0:1]; reg [1:0] seq_valid=0;
 reg [63:0] last_accept[0:1]; reg [1:0] timeout_seen=0;
 reg snap_req=0, snap_busy=0; reg [31:0] snap_seq=0;
 reg [63:0] snap_cycle=0;
 wire eth_ack; wire [1023:0] eth_hold;
 (* ASYNC_REG="TRUE" *) reg [1:0] ack_sync=0;
 reg [1023:0] eth_snap=0;
 reg [511:0] can_stats_snap=0;
 pl_stream_monitor streams(.clk(eth_clk),.resetn(resetn),.req_async(snap_req),
 .valid(stream_valid),.ready(stream_ready),.last(stream_last),.keep(stream_keep),.ack(eth_ack),.snapshot(eth_hold));
 wire [1:0] can_valid,can_sof_valid,can_ack,can_local;
 wire [10:0] can_id[0:1]; wire [3:0] can_dlc[0:1];
 wire [63:0] can_data[0:1],can_sof[0:1],can_eof[0:1];
 wire [31:0] can_frames[0:1],can_errors[0:1],can_unsupported[0:1],can_noack[0:1];
 genvar g;
 generate for(g=0;g<2;g=g+1) begin: can_mon
 can_passive_monitor mon(.clk(clk),.resetn(resetn),.cycles(cycle),
 .rx_raw(g==0?can0_rx_raw:can1_rx_raw),.tx_raw(g==0?can0_tx_raw:can1_tx_raw),
 .sof_valid(can_sof_valid[g]),.frame_valid(can_valid[g]),.frame_id(can_id[g]),.frame_dlc(can_dlc[g]),.frame_data(can_data[g]),
 .frame_ack(can_ack[g]),.frame_local(can_local[g]),.sof_cycle(can_sof[g]),.eof_cycle(can_eof[g]),
 .frame_count(can_frames[g]),.error_count(can_errors[g]),.unsupported_count(can_unsupported[g]),.ack_missing_count(can_noack[g]));
 end endgenerate
 // Per feedback ID: raw bytes and PL EOF timestamp, never model-coordinate conversion.
 reg [127:0] feedback[0:27]; reg [27:0] feedback_valid=0;
 reg [127:0] feedback_snap[0:27]; reg [27:0] feedback_valid_snap=0;
 function integer fb_index(input [10:0] id);
 begin
 if(id>=11'h251 && id<=11'h256) fb_index=id-11'h251;
 else if(id>=11'h261 && id<=11'h266) fb_index=6+id-11'h261;
 else if(id==11'h2a1) fb_index=12;
 else if(id==11'h2a8) fb_index=13;
 else fb_index=-1;
 end endfunction
 // Atomic submission staging, locked while validating. No command reaches any CAN controller.
 reg [31:0] stage[0:31]; wire [1023:0] stage_vec;
 generate for(g=0;g<32;g=g+1) begin: stage_pack
 assign stage_vec[g*32+:32]=stage[g];
 end endgenerate
 reg validating=0; reg [7:0] crc_index=0; reg [31:0] crc_work=32'hffffffff;
 reg [31:0] result=0;
 wire command_channel=stage[10][0];
 wire [63:0] command_apply={stage[7],stage[6]}, command_expire={stage[9],stage[8]};
 function [31:0] crc_byte(input [31:0] c,input [7:0] b);
 reg [31:0] x; integer j; begin x=c^b; for(j=0;j<8;j=j+1) x=(x>>1)^((x[0])?32'h82f63b78:0); crc_byte=x; end endfunction
 wire [31:0] crc_next=crc_byte(crc_work,stage_vec[crc_index*8+:8]);
 reg reserved_ok; integer z;
 always @* begin
 reserved_ok=(stage[19][31:16]==0);
 for(z=24;z<32;z=z+1) if(stage[z]!=0) reserved_ok=0;
 end
 wire seq_new= !seq_valid[command_channel] ||
   ((stage[3]-last_seq[command_channel])!=0 && !( (stage[3]-last_seq[command_channel]) & 32'h80000000));
 // Queue storage is 64 records per arm, each 128 bytes.
 (* ram_style="distributed" *) reg [1023:0] queue0[0:63];
 (* ram_style="distributed" *) reg [1023:0] queue1[0:63];
 reg [5:0] qwr[0:1], qrd[0:1]; reg [6:0] qcount[0:1];
 reg [1023:0] qhead0,qhead1;
 reg [5:0] qpref0=0,qpref1=0; reg [1:0] qready=0;
 always @(posedge clk) begin
 qhead0<=queue0[qrd[0]]; qhead1<=queue1[qrd[1]];
 qpref0<=qrd[0]; qpref1<=qrd[1];
 qready[0]<=resetn && qcount[0]!=0 && qpref0==qrd[0];
 qready[1]<=resetn && qcount[1]!=0 && qpref1==qrd[1];
 end
 wire validation_end=validating && crc_index==128;
 reg [31:0] reject_reason;
 always @* begin
 reject_reason=0;
 if(!mode) reject_reason=1;
 else if(stage[0]!=32'h4b504c31 || stage[1]!=32'h00800001) reject_reason=2;
 else if(stage[2]!=epoch) reject_reason=3;
 else if(stage[10][7:0]>1 || (stage[10][15:8]!=1 && stage[10][15:8]!=2) || stage[10][31:16]!=0) reject_reason=4;
 else if(stage[18][31:16]!=1 || stage[19][15:0]!=1 || !reserved_ok) reject_reason=5;
 else if((~crc_work)!=stage[23]) reject_reason=6;
 else if(command_expire<=cycle || command_apply>=command_expire) reject_reason=7;
 else if(!seq_new) reject_reason=8;
 else if(qcount[command_channel]==64) reject_reason=9;
 end
 wire qpush=validation_end && reject_reason==0;
 // Shadow scheduler: samples queues on 200-Hz ticks, serialises only candidate EVENTS.
 reg [3:0] sched=0; reg sched_ch=0; reg [2:0] frame_index=0;
 reg [1023:0] active_record=0; reg qpop=0; reg pop_ch=0;
 reg candidate_valid=0; reg [10:0] candidate_id=0; reg [63:0] candidate_data=0;
 wire [1023:0] head=sched_ch?qhead1:qhead0;
 wire [63:0] head_apply=head[192+:64], head_expire=head[256+:64];
 wire [31:0] active_seq=active_record[96+:32];
 wire [63:0] active_trace=active_record[128+:64];
 // FIFO events are 64 bytes LE. Data bytes at offsets 52..59 are CAN wire order.
 function [63:0] byte_reverse(input [63:0] x); integer b; begin for(b=0;b<8;b=b+1) byte_reverse[b*8+:8]=x[(7-b)*8+:8]; end endfunction
 function [511:0] make_event(input [15:0] kind,input [15:0] channel,input [31:0] flags,input [31:0] seq,
 input [31:0] aux,input [63:0] trace,input [63:0] stamp,input [63:0] data,input [15:0] len);
 reg [511:0] e; begin
 e=0; e[0+:32]=32'h00400001; e[32+:32]=flags; e[64+:32]=BUILD; e[96+:32]=boot_cookie;
 e[128+:16]=1; e[144+:16]=channel; e[160+:16]=kind; e[192+:32]=seq; e[224+:32]=aux;
 e[256+:64]=trace; e[320+:64]=stamp; e[384+:16]=len; e[416+:64]=byte_reverse(data); make_event=e;
 end endfunction
 reg [511:0] event_input; reg [2:0] event_sources;
 always @* begin
 event_input=0; event_sources=0;
 if(can_sof_valid[0] && event_mask[0]) begin
 event_input=make_event(16'h401,0,0,0,0,0,can_sof[0],0,0); event_sources=event_sources+1; end
 if(can_sof_valid[1] && event_mask[1]) begin
 event_input=make_event(16'h401,1,0,0,0,0,can_sof[1],0,0); event_sources=event_sources+1; end
 if(can_valid[0] && event_mask[0]) begin
 event_input=make_event(16'h402,0,{29'd0,can_local[0],can_ack[0],1'b0},0,{21'd0,can_id[0]},0,can_eof[0],can_data[0],{12'd0,can_dlc[0]}); event_sources=event_sources+1; end
 if(can_valid[1] && event_mask[1]) begin
 event_input=make_event(16'h402,1,{29'd0,can_local[1],can_ack[1],1'b0},0,{21'd0,can_id[1]},0,can_eof[1],can_data[1],{12'd0,can_dlc[1]}); event_sources=event_sources+1; end
 if(candidate_valid && event_mask[2]) begin
 event_input=make_event(16'h210,{15'd0,sched_ch},32'h9,active_seq,{21'd0,candidate_id},active_trace,cycle,candidate_data,8); event_sources=event_sources+1; end
 end
 (* ram_style="block" *) reg [511:0] events[0:1023];
 reg [9:0] ewr=0,erd=0; reg [10:0] ecount=0;
 reg [511:0] event_head=0; reg [9:0] epref=0; reg ehead_ready=0; reg [63:0] lost=0, lost_snap=0;
 always @(posedge clk) begin
 event_head<=events[erd]; epref<=erd;
 ehead_ready<=resetn && ecount!=0 && epref==erd;
 end
 // AXI-Lite accepts AW and W independently; holds responses until handshake.
 reg aw_hold=0,w_hold=0; reg [15:0] aw_saved=0; reg [31:0] w_saved=0; reg [3:0] strobe_saved=0;
 assign s_axi_awready=!aw_hold && !s_axi_bvalid;
 assign s_axi_wready=!w_hold && !s_axi_bvalid;
 assign s_axi_arready=!s_axi_rvalid;
 wire write_fire=aw_hold && w_hold && !s_axi_bvalid;
 wire full_write=(strobe_saved==4'hf) && (aw_saved[1:0]==0);
 wire pop_event=write_fire && full_write && aw_saved==16'h844 && w_saved==1 && ecount!=0 && ehead_ready;
 wire mode_change=write_fire && full_write && aw_saved==16'h30 && w_saved<2 && mode!=w_saved[0] && !validating && sched==0;
 reg [31:0] read_value; reg read_bad; integer idx;
 always @* begin
 read_value=0; read_bad=0; idx=0;
 case(s_axi_araddr)
 16'h000:read_value=32'h4b504c31;
 16'h004:read_value=32'h00010000;
 16'h008:read_value=32'h0000016b; // counter,shadow,codec,scheduler,DMA stats,passive CAN; NOT ownership/PL CAN
 16'h00c:read_value=BUILD;
 16'h010:read_value=1;
 16'h014:read_value=boot_cookie;
 16'h018:read_value=CLK_HZ;
 16'h01c:read_value=1;
 16'h024:read_value=snap_seq;
 16'h028:read_value=snap_cycle[31:0]; 16'h02c:read_value=snap_cycle[63:32];
 16'h030:read_value={31'd0,mode};
 16'h034:read_value={27'd0,snap_busy,validating,(sched!=0),1'b0,mode};
 16'h03c:read_value=epoch;
 16'h040:read_value=faults;
 16'h048:read_value=timeout_ticks;
 16'h04c:read_value=period;
 16'h060:read_value=lost_snap[31:0]; 16'h064:read_value=lost_snap[63:32];
 16'h068:read_value=rejected; 16'h06c:read_value=stale;
 16'h070:read_value=result; 16'h074:read_value=boot_cookie;
 16'h078:read_value=event_mask; 16'h07c:read_value=accepted;
 16'h580:read_value={4'd0,feedback_valid_snap};
 16'h840:read_value={21'd0,ecount}; 16'h848:read_value={22'd0,erd};
 16'h850:read_value={25'd0,qcount[0]}; 16'h854:read_value={25'd0,qcount[1]};
 default: begin
 if(s_axi_araddr>=16'h100 && s_axi_araddr<16'h1e0) begin idx=(s_axi_araddr-16'h100)>>4; read_value=feedback_snap[idx][s_axi_araddr[3:2]*32+:32]; end
 else if(s_axi_araddr>=16'h200 && s_axi_araddr<16'h2e0) begin idx=14+((s_axi_araddr-16'h200)>>4); read_value=feedback_snap[idx][s_axi_araddr[3:2]*32+:32]; end
 else if(s_axi_araddr>=16'h300 && s_axi_araddr<16'h380) read_value=eth_snap[(s_axi_araddr-16'h300)*8+:32];
 else if(s_axi_araddr>=16'h600 && s_axi_araddr<16'h640) read_value=can_stats_snap[(s_axi_araddr-16'h600)*8+:32];
 else if(s_axi_araddr>=16'h800 && s_axi_araddr<16'h840 && ecount!=0 && ehead_ready) read_value=event_head[s_axi_araddr[5:2]*32+:32];
 else if(s_axi_araddr>=16'h1000 && s_axi_araddr<16'h1080) read_value=stage[s_axi_araddr[6:2]];
 else read_bad=1;
 end
 endcase
 if(s_axi_araddr[1:0]!=0) read_bad=1;
 end
 integer i,fi;
 always @(posedge clk) begin
  cycle<=cycle+1; ack_sync<={ack_sync[0],eth_ack}; candidate_valid<=0; qpop<=0;
  if(!resetn) begin
   cycle<=0; mode<=0; epoch<=0; boot_cookie<=0; period<=CLK_HZ/200; tick_left<=CLK_HZ/200;
   timeout_ticks<=CLK_HZ/10; event_mask<=0; faults<=0; rejected<=0; stale<=0; accepted<=0;
   seq_valid<=0; timeout_seen<=0; snap_req<=0; snap_busy<=0; snap_seq<=0; snap_cycle<=0; eth_snap<=0;
   lost_snap<=0; can_stats_snap<=0; feedback_valid<=0; feedback_valid_snap<=0;
   validating<=0; crc_index<=0; crc_work<=32'hffffffff; result<=0;
   sched<=0; sched_ch<=0; frame_index<=0; active_record<=0;
   ewr<=0; erd<=0; ecount<=0; lost<=0;
   aw_hold<=0; w_hold<=0; s_axi_bvalid<=0; s_axi_rvalid<=0; s_axi_bresp<=0; s_axi_rresp<=0; s_axi_rdata<=0;
   for(i=0;i<2;i=i+1) begin qwr[i]<=0; qrd[i]<=0; qcount[i]<=0; last_seq[i]<=0; last_accept[i]<=0; end
   for(i=0;i<32;i=i+1) stage[i]<=0;
   for(i=0;i<28;i=i+1) begin feedback[i]<=0; feedback_snap[i]<=0; end
  end else begin
   if(s_axi_awvalid && s_axi_awready) begin aw_hold<=1; aw_saved<=s_axi_awaddr; end
   if(s_axi_wvalid && s_axi_wready) begin w_hold<=1; w_saved<=s_axi_wdata; strobe_saved<=s_axi_wstrb; end
   if(s_axi_bvalid && s_axi_bready) s_axi_bvalid<=0;
   if(s_axi_rvalid && s_axi_rready) s_axi_rvalid<=0;
   if(s_axi_arvalid && s_axi_arready) begin s_axi_rvalid<=1; s_axi_rdata<=read_value; s_axi_rresp<=read_bad?2'b10:0; end
   if(snap_busy && ack_sync[1]==snap_req) begin
    eth_snap<=eth_hold; snap_busy<=0; snap_seq<=snap_seq+1;
   end
   for(i=0;i<2;i=i+1) begin
    if(can_valid[i] && can_dlc[i]==8) begin
      fi=fb_index(can_id[i]);
      if(fi>=0) begin feedback[14*i+fi]<={can_eof[i],byte_reverse(can_data[i])}; feedback_valid[14*i+fi]<=1; end
    end
    if(mode && seq_valid[i] && !timeout_seen[i] && cycle-last_accept[i]>=timeout_ticks) begin faults[i]<=1; timeout_seen[i]<=1; end
    case({qpush && command_channel==i,qpop && pop_ch==i})
    2'b10:qcount[i]<=qcount[i]+1;
    2'b01:qcount[i]<=qcount[i]-1;
    default:;
    endcase
    if(qpop && pop_ch==i) qrd[i]<=qrd[i]+1;
   end
   if(event_sources!=0) begin
    if(ecount<1024) begin events[ewr]<=event_input; ewr<=ewr+1; lost<=lost+event_sources-1; end
    else lost<=lost+event_sources;
   end
   case({event_sources!=0 && ecount<1024,pop_event})
   2'b10:ecount<=ecount+1;
   2'b01:ecount<=ecount-1;
   default:;
   endcase
   if(pop_event) erd<=erd+1;
   if(validating) begin
    if(crc_index<128) begin
      if(crc_index<92 || crc_index>=96) crc_work<=crc_next;
      crc_index<=crc_index+1;
    end else begin
      validating<=0; result<=reject_reason;
      if(qpush) begin
       if(command_channel) queue1[qwr[1]]<=stage_vec; else queue0[qwr[0]]<=stage_vec; qwr[command_channel]<=qwr[command_channel]+1;
       last_seq[command_channel]<=stage[3]; seq_valid[command_channel]<=1;
       last_accept[command_channel]<=cycle; timeout_seen[command_channel]<=0; accepted<=accepted+1;
      end else rejected<=rejected+1;
    end
   end
   if(tick_left==0) tick_left<=period-1; else tick_left<=tick_left-1;
   case(sched)
   0:if(mode && tick_left==0) begin sched<=1; sched_ch<=0; end
   1:begin // queue head has been prefetched; command is used only once
     if(qcount[sched_ch]!=0 && qready[sched_ch] && head_apply<=cycle) begin
       qpop<=1; pop_ch<=sched_ch;
       if(head[64+:32]!=epoch || head_expire<=cycle) begin stale<=stale+1; sched<=3; end
       else begin active_record<=head; frame_index<=0; sched<=2; end
     end else sched<=3;
   end
   2:begin
     if(active_record[256+:64]<=cycle) begin stale<=stale+1; sched<=3; end
     else begin
       candidate_valid<=1;
       if(active_record[328+:8]==2) begin
         candidate_id<=11'h159;
         candidate_data<={active_record[544+:32],active_record[576+:16],16'h0100}; sched<=3;
       end else begin
         case(frame_index)
         0,1:begin candidate_id<=11'h151; candidate_data<=64'h0101640000000000; end
         2:begin candidate_id<=11'h155; candidate_data<={active_record[352+:32],active_record[384+:32]}; end
         3:begin candidate_id<=11'h156; candidate_data<={active_record[416+:32],active_record[448+:32]}; end
         4:begin candidate_id<=11'h157; candidate_data<={active_record[480+:32],active_record[512+:32]}; end
         endcase
         if(frame_index==4) sched<=3; else frame_index<=frame_index+1;
       end
     end
   end
   3:if(!sched_ch) begin sched_ch<=1; sched<=1; end else sched<=0;
   default:sched<=0;
   endcase
   if(write_fire) begin
    aw_hold<=0; w_hold<=0; s_axi_bvalid<=1; s_axi_bresp<=0;
    if(!full_write) s_axi_bresp<=2'b10;
    else case(aw_saved)
    16'h020:if(!snap_busy && w_saved==1) begin
      snap_req<=!snap_req; snap_busy<=1; snap_cycle<=cycle; lost_snap<=lost;
      for(i=0;i<28;i=i+1) feedback_snap[i]<=feedback[i];
      feedback_valid_snap<=feedback_valid;
      for(i=0;i<2;i=i+1) begin
        can_stats_snap[i*256+:32]<=can_frames[i]; can_stats_snap[i*256+32+:32]<=can_errors[i];
        can_stats_snap[i*256+64+:32]<=can_unsupported[i]; can_stats_snap[i*256+96+:32]<=can_noack[i];
        can_stats_snap[i*256+128+:64]<=can_sof[i]; can_stats_snap[i*256+192+:64]<=can_eof[i];
      end
    end else s_axi_bresp<=2'b10;
    16'h030:if(w_saved<2) begin
     // Busy mode requests are acknowledged without a change; software reads back
     // and retries. A scheduler race must never raise an AXI bus exception.
     if(!validating && sched==0) begin
      mode<=w_saved[0];
      if(mode_change) begin
        epoch<=epoch+1; seq_valid<=0; timeout_seen<=0; tick_left<=period-1;
        for(i=0;i<2;i=i+1) begin qcount[i]<=0; qrd[i]<=0; qwr[i]<=0; end
      end
    end
    end else s_axi_bresp<=2'b10;
    16'h044:faults<=faults & ~w_saved;
    16'h048:if(!mode && w_saved>=CLK_HZ/1000) timeout_ticks<=w_saved; else s_axi_bresp<=2'b10;
    16'h04c:if(!mode && w_saved>=CLK_HZ/1000) period<=w_saved; else s_axi_bresp<=2'b10;
    16'h074:if(!mode && !validating && ecount==0) boot_cookie<=w_saved; else s_axi_bresp<=2'b10;
    16'h078:if(w_saved<8) event_mask<=w_saved; else s_axi_bresp<=2'b10;
    16'h844:if(!pop_event) s_axi_bresp<=2'b10;
    16'h1080:if(!validating && mode && w_saved==32'h53484457) begin validating<=1; crc_index<=0; crc_work<=32'hffffffff; result<=32'hffffffff; end else s_axi_bresp<=2'b10;
    default:if(aw_saved>=16'h1000 && aw_saved<16'h1080 && !validating) stage[aw_saved[6:2]]<=w_saved; else s_axi_bresp<=2'b10;
    endcase
   end
  end
 end
endmodule
