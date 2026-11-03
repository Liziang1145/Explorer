// Serialized APB master for the existing CTU CAN 2.2 core.
// ARM completion is reported only after TX_STATUS becomes TXOK/ERROR/ABORTED.
module can_core_service #(parameter CLK_HZ=99999001)(
 input clk,resetn,core_resetn,input [1:0] owner,target,input [2:0] phase,input stop_core,
 input [63:0] cycles,input [31:0] lifecycle_timeout_ms,
 input host_valid,host_write,input [11:0] host_addr,input [31:0] host_wdata,input [3:0] host_strb,
 output host_ready,output reg host_done=0,output reg [31:0] host_rdata=0,output reg host_denied=0,
 input frame_valid,input [10:0] frame_id,input [63:0] frame_data,frame_deadline,
 output frame_ready,output reg frame_done=0,output reg [2:0] frame_result=0,
 output reg initialized=0,output core_stopped,output backend_idle,
 output reg core_operational=0,output reg [31:0] mode_shadow=0,err_status=0,
 output [31:0] debug_state,
 output reg [31:0] fault_bits=0,error_counters=0,device_id=0,tx_status=32'h8888,
 output reg [31:0] apb_addr=0,output reg apb_sel=0,apb_enable=0,apb_write=0,
 output reg [31:0] apb_wdata=0,output reg [3:0] apb_strb=0,output [2:0] apb_prot,
 input [31:0] apb_rdata,input apb_ready,apb_error);
 localparam BTR=(2<<27)|(1<<19)|(25<<13)|(37<<7)|37;
 localparam J_INIT=0,J_HOST=1,J_FILL=2,J_TX=3,J_STOP=4,J_STOP_POLL=5,J_FAULT=6,J_COUNTER=7;
 reg [2:0] bus_state=0,job=0; reg [10:0] bus_wait=0;
 reg [3:0] init_step=0,fill_step=0;
 reg active=0,launched=0,stop_sent=0,stopped=0;
 reg [10:0] id_hold=0; reg [63:0] data_hold=0,deadline_hold=0;
 reg [13:0] poll_div=0; reg poll_pending=0,counter_pending=0;
 reg [3:0] fd_bad=0; reg expired=0;
 reg [31:0] life_div=0,life_age=0;
 wire enabled=mode_shadow[22]; // CTU 2.2 ENA is bit22; bit7 is ACF, not ENA.
 wire in_run=(phase==0&&(owner==1||owner==2));
 assign debug_state={12'b0,apb_error,apb_ready,counter_pending,poll_pending,core_operational,enabled,initialized,stopped,stop_sent,active,launched,expired,job,bus_state,apb_enable,apb_sel};
 wire native_allowed=(owner==1&&phase==0)||(target==1&&phase==4);
 wire probe_allowed=(owner==0&&phase==0);
 wire host_is_fmt=(host_addr==12'h100||host_addr==12'h200||host_addr==12'h300||host_addr==12'h400);
 wire host_fmt_fd=host_is_fmt&&host_strb[0]&&host_wdata[7];
 wire host_enable_fd=host_addr==12'h004&&host_strb[0]&&host_wdata[4];
 wire host_ready_cmd=host_addr==12'h074&&host_strb[0]&&host_wdata[1];
 wire host_bad_ready=host_ready_cmd&&((phase!=0||owner!=1||!core_operational)||(|(fd_bad&host_wdata[11:8])));
 // In PS mode permit identification/status reads only; Linux must acquire PL first to configure.
 wire host_ok=(!host_write&&(native_allowed||probe_allowed))||
              (host_write&&native_allowed&&!host_fmt_fd&&!host_enable_fd&&!host_bad_ready);
 wire can_accept=(bus_state==0&&initialized&&!stop_core&&!active&&!poll_pending&&!counter_pending);
 assign host_ready=can_accept&&host_valid;
 assign frame_ready=can_accept&&!host_valid&&owner==2&&phase==0&&core_operational;
 assign core_stopped=!core_resetn||(stopped&&!active&&bus_state==0);
 assign backend_idle=(bus_state==0&&!active);
 assign apb_prot=0;
 function tx_busy(input [31:0] s);
 integer k; reg [3:0] n; begin tx_busy=0;
 for(k=0;k<4;k=k+1) begin n=(s>>(k*4))&15; if(n==1||n==2||n==3)tx_busy=1;end
 end endfunction
 task start_bus(input [2:0] j,input wr,input [11:0] addr,input [31:0] data,input [3:0] strb);
 begin job<=j;apb_addr<={20'b0,addr};apb_write<=wr;apb_wdata<=data;apb_strb<=strb;
 apb_sel<=1;apb_enable<=0;bus_state<=1;bus_wait<=0;end endtask
 always @(posedge clk)begin
 host_done<=0;host_denied<=0;frame_done<=0;
 if(!resetn||!core_resetn)begin
  bus_state<=0;apb_sel<=0;apb_enable<=0;initialized<=0;init_step<=0;active<=0;
  launched<=0;stop_sent<=0;stopped<=0;poll_div<=0;poll_pending<=0;counter_pending<=0;
  fault_bits<=0;error_counters<=0;device_id<=0;fd_bad<=0;expired<=0;tx_status<=32'h8888;
  mode_shadow<=0;err_status<=0;core_operational<=0;life_div<=0;life_age<=0;
 end else begin
  // Native disable/reset is an explicit expected stop/configuration transaction.
  // Never infer a runtime bus-off from CTU's documented disabled/reset BOF state.
  if(!in_run||stop_core||core_operational)begin life_div<=0;life_age<=0;end
  else if(life_div==CLK_HZ/1000-1)begin
   life_div<=0;
   if(life_age<lifecycle_timeout_ms)life_age<=life_age+1;
   else fault_bits<=fault_bits|(enabled?32'h100:32'h80);
  end else life_div<=life_div+1;
  if(stop_core)core_operational<=0;
  if(poll_div==9999)begin poll_div<=0;poll_pending<=1;end else poll_div<=poll_div+1;
  if(!stop_core&&!expired&&!(active&&cycles>=deadline_hold))begin stop_sent<=0;stopped<=0;end
  if(active&&cycles>=deadline_hold)expired<=1;
  case(bus_state)
   0:begin
    if(!initialized)begin
     case(init_step)
      0:start_bus(J_INIT,1,12'h004,0,15);
      1:start_bus(J_INIT,1,12'h018,32'hffffffff,15);
      2:start_bus(J_INIT,1,12'h01c,32'hffffffff,15);
      3:start_bus(J_INIT,1,12'h024,BTR,15);
      4:start_bus(J_INIT,1,12'h05c,0,15);
      5:start_bus(J_INIT,1,12'h004,target==2?32'h00400080:0,15);
      6:start_bus(J_INIT,0,12'h000,0,0);
      default:initialized<=1;
     endcase
    end else if((stop_core||expired||(active&&cycles>=deadline_hold))&&!stop_sent)begin
     start_bus(J_STOP,1,12'h074,32'hf04,15);stop_sent<=1;
    end else if((stop_core||expired||(active&&cycles>=deadline_hold))&&!stopped)start_bus(J_STOP_POLL,0,12'h070,0,0);
    else if(poll_pending)begin start_bus(J_FAULT,0,12'h02c,0,0);poll_pending<=0;end
    else if(counter_pending)begin start_bus(J_COUNTER,0,12'h030,0,0);counter_pending<=0;end
    else if(active&&!launched)begin
     case(fill_step)
      0:start_bus(J_FILL,1,12'h074,32'h101,15);
      1:start_bus(J_FILL,1,12'h100,8,15);
      2:start_bus(J_FILL,1,12'h104,{3'b0,id_hold,18'b0},15);
      3:start_bus(J_FILL,1,12'h108,0,15);
      4:start_bus(J_FILL,1,12'h10c,0,15);
      5:start_bus(J_FILL,1,12'h110,{data_hold[39:32],data_hold[47:40],data_hold[55:48],data_hold[63:56]},15);
      6:start_bus(J_FILL,1,12'h114,{data_hold[7:0],data_hold[15:8],data_hold[23:16],data_hold[31:24]},15);
      7:start_bus(J_FILL,1,12'h074,32'h102,15);
      default:begin launched<=1;end
     endcase
    end else if(active&&launched)start_bus(J_TX,0,12'h070,0,0);
    else if(host_ready)begin
     if(host_write&&host_is_fmt&&host_strb[0])fd_bad[host_addr[10:8]-1]<=host_wdata[7];
     if(!host_ok)begin host_done<=1;host_denied<=1;host_rdata<=32'hffffffff;end
     else start_bus(J_HOST,host_write,host_addr,host_wdata,host_strb);
    end else if(frame_valid&&frame_ready)begin
     id_hold<=frame_id;data_hold<=frame_data;deadline_hold<=frame_deadline;fill_step<=0;
     if(cycles>=frame_deadline)begin frame_done<=1;frame_result<=3;end
     else begin active<=1;launched<=0;expired<=0;end
    end
   end
   1:begin apb_enable<=1;bus_state<=2;end
   2:begin
    if(apb_ready)begin
     apb_sel<=0;apb_enable<=0;bus_state<=0;
     if(apb_error)fault_bits<=fault_bits|32'h8;
     case(job)
      J_INIT:begin
       init_step<=init_step+1;
       if(init_step==5&&!apb_error)begin mode_shadow<=target==2?32'h00400080:0;core_operational<=0;end
       if(init_step==6)begin device_id<=apb_rdata;initialized<=1;if(apb_rdata!=32'h0202cafd)fault_bits<=fault_bits|32'h10;end
      end
      J_HOST:begin
       host_done<=1;host_rdata<=apb_rdata;host_denied<=apb_error;
       if(apb_write&&apb_addr[11:0]==12'h004&&!apb_error)begin
        if(apb_strb[0]&&apb_wdata[0])begin mode_shadow<=0;core_operational<=0;end
        else begin
         if(apb_strb[0])mode_shadow[7:0]<=apb_wdata[7:0];
         if(apb_strb[1])mode_shadow[15:8]<=apb_wdata[15:8];
         if(apb_strb[2])begin
          mode_shadow[23:16]<=apb_wdata[23:16];
          if(!apb_wdata[22]||!enabled)core_operational<=0;
         end
         if(apb_strb[3])mode_shadow[31:24]<=apb_wdata[31:24];
        end
       end
      end
      J_FILL:fill_step<=fill_step+1;
      J_TX:begin
       tx_status<=apb_rdata;
       if(apb_rdata[3:0]==4||apb_rdata[3:0]==6||apb_rdata[3:0]==7)begin
        active<=0;launched<=0;frame_done<=1;
        frame_result<=apb_rdata[3:0]==4?0:(apb_rdata[3:0]==6?1:2);
       end
      end
      J_STOP:begin end
      J_STOP_POLL:begin
       tx_status<=apb_rdata;
       if(!tx_busy(apb_rdata))begin
        stopped<=1;
        if(active)begin active<=0;frame_done<=1;
         frame_result<=launched&&apb_rdata[3:0]==4?0:(expired?3:2);end
        if(expired&&!stop_core)begin expired<=0;stop_sent<=0;end
       end
      end
      J_FAULT:begin
       err_status<=apb_rdata;counter_pending<=1;
       if(enabled&&!stop_core&&!apb_error)begin
        if(!apb_rdata[18]&&(apb_rdata[16]||apb_rdata[17]))core_operational<=1;
        if(in_run&&core_operational&&apb_rdata[18])begin
         fault_bits<=fault_bits|32'h2;core_operational<=0;
        end
       end
      end
      J_COUNTER:error_counters<=apb_rdata;
     endcase
    end else if(bus_wait==1023)begin
     apb_sel<=0;apb_enable<=0;bus_state<=0;fault_bits<=fault_bits|32'h8;
     if(job==J_HOST)begin host_done<=1;host_denied<=1;host_rdata<=32'hffffffff;end
     if(active)begin active<=0;frame_done<=1;frame_result<=4;end
    end else bus_wait<=bus_wait+1;
   end
   default:begin bus_state<=0;apb_sel<=0;apb_enable<=0;fault_bits<=fault_bits|32'h8;end
  endcase
 end
 end
endmodule
