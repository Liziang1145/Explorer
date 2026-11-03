// Independent v2 command queue. Payload has already been converted by PS to wire units.
module arm_command_engine #(parameter CHANNEL=0,CLK_HZ=99999001)(
 input clk,resetn,run,input [31:0] generation,input [63:0] cycles,
 input stage_write,input [4:0] stage_index,input [31:0] stage_data,
 input submit,output reg validating=0,output reg [31:0] result=0,
 output [31:0] stage_read,input [4:0] stage_read_index,
 output reg [6:0] queue_count=0,output reg [31:0] accepted=0,rejected=0,expired_count=0,
 output frame_valid,input frame_ready,output reg [10:0] frame_id,
 output reg [63:0] frame_data,output [63:0] frame_deadline,
 input frame_done,input [2:0] frame_result,
 output [31:0] active_generation,output [31:0] active_seq,output [63:0] active_trace,output [2:0] active_index,
 output reg event_valid=0,output reg [15:0] event_kind=0,
 output reg [31:0] event_seq=0,event_aux=0,output reg [63:0] event_trace=0,
 output reg group_fault=0,output reg [31:0] event_lost=0,output busy);
 reg [31:0] stage[0:31]; wire [1023:0] stage_vec;
 genvar g;generate for(g=0;g<32;g=g+1)begin:pack_stage assign stage_vec[g*32+:32]=stage[g];end endgenerate
 assign stage_read=stage[stage_read_index];
 (* ram_style="distributed" *) reg [1023:0] queue[0:63];
 reg [5:0] qwr=0,qrd=0,pref=0;reg [1023:0] head=0,record=0;reg head_ready=0;
 reg [31:0] epoch_seen=0,last_seq=0,tick_left=0;reg seq_valid=0;
 reg [7:0] crc_index=0;reg [31:0] crc_work=32'hffffffff;
 reg [1:0] state=0;reg [2:0] index=0,completed=0;
 reg reserved_ok;integer z;integer emit_count;
 function [31:0] crc_byte(input [31:0] c,input [7:0] b);
 reg [31:0] x;integer j;begin x=c^b;for(j=0;j<8;j=j+1)x=(x>>1)^(x[0]?32'h82f63b78:0);crc_byte=x;end endfunction
 wire [31:0] seq_diff=stage[3]-last_seq;
 wire [63:0] apply={stage[7],stage[6]},expire={stage[9],stage[8]};
 reg [31:0] reject_reason;
 always @*begin
  reserved_ok=stage[19][31:16]==0;
  for(z=24;z<32;z=z+1)if(stage[z]!=0)reserved_ok=0;
  reject_reason=0;
  if(!run)reject_reason=1;
  else if(stage[0]!=32'h4b434132||stage[1]!=32'h00800002)reject_reason=2;
  else if(stage[2]!=generation)reject_reason=3;
  else if(stage[10][7:0]!=CHANNEL||stage[10][15:8]<1||stage[10][15:8]>3||stage[10][31:16]!=0)reject_reason=4;
  else if(stage[18][31:16]!=1||stage[19][15:0]!=1||!reserved_ok)reject_reason=5;
  else if(~crc_work!=stage[23])reject_reason=6;
  else if(expire<=cycles||apply>=expire)reject_reason=7;
  else if(seq_valid&&(seq_diff==0||seq_diff[31]))reject_reason=8;
  else if(queue_count==64)reject_reason=9;
 end
 wire push=validating&&crc_index==128&&reject_reason==0;
 wire pop=state==0&&run&&(tick_left==0||head[256+:64]<=cycles)&&queue_count!=0&&head_ready&&head[192+:64]<=cycles;
 assign frame_valid=state==1&&run&&cycles<frame_deadline;
 assign frame_deadline=record[256+:64];
 assign active_generation=record[64+:32];assign active_seq=record[96+:32];assign active_trace=record[128+:64];assign active_index=index;
 assign busy=(state!=0);
 wire [7:0] kind=record[328+:8];
 wire last_frame=(kind==2)||(kind==1&&index==4)||(kind==3&&index==5);
 always @*begin
  frame_id=0;frame_data=0;
  if(kind==2||index==5)begin frame_id=11'h159;frame_data={record[544+:32],record[576+:16],16'h0100};end
  else case(index)
   0,1:begin frame_id=11'h151;frame_data=64'h0101640000000000;end
   2:begin frame_id=11'h155;frame_data={record[352+:32],record[384+:32]};end
   3:begin frame_id=11'h156;frame_data={record[416+:32],record[448+:32]};end
   4:begin frame_id=11'h157;frame_data={record[480+:32],record[512+:32]};end
  endcase
 end
 task event_emit(input [15:0] k,input [31:0] s,input [63:0] t,input [31:0] a);
 begin emit_count=emit_count+1;event_valid<=1;event_kind<=k;event_seq<=s;event_trace<=t;event_aux<=a;end endtask
 integer i;
 always @(posedge clk)begin
  event_valid<=0;group_fault<=0;emit_count=0;
  head<=queue[qrd];pref<=qrd;head_ready<=(pref==qrd);
  if(!resetn)begin
   queue_count<=0;qwr<=0;qrd<=0;head_ready<=0;epoch_seen<=generation;seq_valid<=0;
   validating<=0;result<=0;state<=0;event_lost<=0;tick_left<=0;accepted<=0;rejected<=0;expired_count<=0;
   for(i=0;i<32;i=i+1)stage[i]<=0;
  end else begin
   if(tick_left!=0)tick_left<=tick_left-1;
   if(stage_write&&!validating)stage[stage_index]<=stage_data;
   if(submit)begin
    if(!run||validating)begin result<=1;rejected<=rejected+1;end
    else begin validating<=1;crc_index<=0;crc_work<=32'hffffffff;result<=32'hffffffff;end
   end
   if(validating)begin
    if(crc_index<128)begin
     if(crc_index<92||crc_index>=96)crc_work<=crc_byte(crc_work,stage_vec[crc_index*8+:8]);
     crc_index<=crc_index+1;
    end else begin
     validating<=0;result<=reject_reason;
     if(push)begin if(queue_count==0)head_ready<=0;queue[qwr]<=stage_vec;qwr<=qwr+1;last_seq<=stage[3];seq_valid<=1;accepted<=accepted+1;
      event_emit(16'h0100,stage[3],{stage[5],stage[4]},0);end
     else begin rejected<=rejected+1;event_emit(16'h0101,stage[3],{stage[5],stage[4]},reject_reason);end
    end
   end
   case({push,pop}) 2'b10:queue_count<=queue_count+1;2'b01:queue_count<=queue_count-1;endcase
   if(pop)begin
    qrd<=qrd+1;head_ready<=0;record<=head;index<=0;completed<=0;
    if(head[64+:32]!=generation||head[256+:64]<=cycles)begin expired_count<=expired_count+1;event_emit(16'h0203,head[96+:32],head[128+:64],0);end
    else begin tick_left<=CLK_HZ/200-1;state<=1;event_emit(16'h0200,head[96+:32],head[128+:64],head[328+:8]);end
   end
   if(state==1)begin
    if(cycles>=frame_deadline)begin
     state<=0;expired_count<=expired_count+1;group_fault<=completed!=0;
     event_emit(16'h0203,active_seq,active_trace,{24'b0,5'b0,completed});
    end else if(frame_valid&&frame_ready)state<=2;
   end
   if(state==2&&frame_done)begin
    if(frame_result!=0)begin
     state<=0;group_fault<=1;event_emit(16'h0204,active_seq,active_trace,{21'b0,frame_result,5'b0,completed});
    end else begin
     completed<=completed+1;
     if(last_frame)begin state<=0;event_emit(16'h0202,active_seq,active_trace,{29'b0,completed}+1);end
     else begin index<=index+1;state<=1;end
    end
   end
   if(emit_count>1)event_lost<=event_lost+emit_count-1;
   // Generation change or loss of permission cancels every queued target.
   if(!run||epoch_seen!=generation)begin
    epoch_seen<=generation;queue_count<=0;qwr<=0;qrd<=0;head_ready<=0;seq_valid<=0;
    validating<=0;state<=0;tick_left<=0;
   end
  end
 end
endmodule
