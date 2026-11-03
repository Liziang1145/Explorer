// Electrical ownership and software-confirmed handover. No CAN payload generation.
module can_path_owner #(parameter CLK_HZ=99999001)(
 input clk,resetn,input rx_raw,ps_tx_raw,pl_tx_raw,
 input prepare,input [1:0] requested_owner,input confirm,input commit,input [31:0] token,
 input heartbeat,input [31:0] fault_in,input clear_faults,input [31:0] clear_mask,
 input core_initialized,core_stopped,backend_idle,input core_operational,input [31:0] lifecycle_timeout_ms,
 input [31:0] idle_cycles,lease_ms,retry_ms,retry_limit,
 input auto_enable,input [1:0] preferred_owner,input clear_retries,
 output reg [1:0] owner=0,output reg [2:0] phase=0,output reg [1:0] target=0,
 output reg [31:0] generation=1,output reg [31:0] faults=0,
 output reg [31:0] result=0,output reg [31:0] retry_count=0,
 output reg [1:0] action_request=0,output reg core_resetn=0,
 output stop_core,output arm_run,output reg changed=0,output reg fault_event=0,
 output tx_pin,output ps_rx,output pl_rx,output [31:0] quiet_count,
 output reg [31:0] forced_isolations=0);
 localparam RUN=0,DRAIN=1,RESET=2,INIT=3,READY=4,FAULT_DRAIN=5,FAULT=6;
 (* ASYNC_REG="TRUE" *) reg [1:0] rx_sync=3,ps_sync=3,pl_sync=3;
 reg [31:0] quiet=0,ms_div=0,lease_age=0,retry_age=0,fault_wait=0;
 reg [31:0] config_age=0;
 reg [4:0] reset_count=0; reg confirmed=0;
 wire ms_tick=(ms_div==CLK_HZ/1000-1);
 wire line_quiet=(quiet>=idle_cycles) && rx_sync[1] && ps_sync[1] && pl_sync[1];
 wire lease_expired=(owner==2 && phase==RUN && lease_age>=lease_ms);
 wire config_expired=(phase==INIT||phase==READY)&&config_age>=lifecycle_timeout_ms;
 wire [31:0] live_fault=fault_in | (lease_expired?32'h1:32'h0) | (config_expired?32'h40:0);
 assign quiet_count=quiet;
 assign tx_pin=(owner==0)?ps_tx_raw:((owner==1||owner==2)?pl_tx_raw:1'b1);
 assign ps_rx=(owner==0)?rx_raw:1'b1;
 assign pl_rx=(owner==1||owner==2)?rx_raw:1'b1;
 assign stop_core=(phase==DRAIN||phase==FAULT_DRAIN||phase==FAULT);
 assign arm_run=(owner==2&&phase==RUN&&live_fault==0);
 always @(posedge clk) begin
  rx_sync<={rx_sync[0],rx_raw};ps_sync<={ps_sync[0],ps_tx_raw};pl_sync<={pl_sync[0],pl_tx_raw};
  changed<=0;fault_event<=0;
  if(!resetn)begin
   owner<=0;phase<=RUN;target<=0;generation<=1;faults<=0;result<=0;retry_count<=0;
   action_request<=0;core_resetn<=0;quiet<=0;ms_div<=0;lease_age<=0;retry_age<=0;
   fault_wait<=0;reset_count<=0;confirmed<=0;forced_isolations<=0;config_age<=0;
  end else begin
   if(phase!=INIT&&phase!=READY)config_age<=0;else if(ms_tick&&config_age!=32'hffffffff)config_age<=config_age+1;
   if(rx_sync[1]&&ps_sync[1]&&pl_sync[1]&&(phase!=DRAIN||(confirmed&&core_stopped&&backend_idle)))begin if(quiet!=32'hffffffff)quiet<=quiet+1;end else quiet<=0;
   if(ms_tick)begin
    ms_div<=0;if(lease_age!=32'hffffffff)lease_age<=lease_age+1;
    if(retry_age!=32'hffffffff)retry_age<=retry_age+1;
   end else ms_div<=ms_div+1;
   if(heartbeat&&token==generation&&owner==2&&phase==RUN)lease_age<=0;
   if(clear_retries)begin retry_count<=0;retry_age<=0;end
   if(clear_faults)faults<=faults&~clear_mask;
   if(!auto_enable)action_request<=0;
   if(phase==RUN&&owner==0&&(preferred_owner==0||preferred_owner==3||(retry_limit!=0&&retry_count>=retry_limit)))action_request<=0;
   if(confirm)begin
    if(token==generation && (phase==DRAIN||phase==INIT||phase==READY||phase==RESET))begin confirmed<=1;result<=0;end
    else result<=2;
   end
   case(phase)
    RUN:begin
     // Keep the disconnected PL core readable for Linux probe, disabled by init.
     if(!core_resetn)begin
      if(reset_count==15)core_resetn<=1;else reset_count<=reset_count+1;
     end
     if(auto_enable&&owner==0&&preferred_owner!=0&&preferred_owner!=3&&retry_age>=retry_ms&&
        (retry_limit==0||retry_count<retry_limit))action_request<=2;
    end
    DRAIN:if(confirmed&&line_quiet&&core_stopped&&backend_idle)begin
      owner<=3;core_resetn<=0;reset_count<=0;phase<=RESET;changed<=1;
    end
    RESET:begin
     if(reset_count==15)begin
      core_resetn<=1;phase<=INIT;
     end else reset_count<=reset_count+1;
    end
    INIT:if(core_initialized)phase<=READY;
    READY:if(commit)begin
     if(token!=generation||!confirmed)result<=2;
     else if(!line_quiet||!backend_idle||(target!=0&&!core_operational))result<=3;
     else begin owner<=target;phase<=RUN;lease_age<=0;retry_age<=0;result<=0;changed<=1;action_request<=0;end
    end
    FAULT_DRAIN:begin
     if(fault_wait<CLK_HZ/500)fault_wait<=fault_wait+1;
     if((pl_tx_raw&&core_stopped&&backend_idle)||fault_wait>=CLK_HZ/500)begin
      if(!(pl_tx_raw&&core_stopped&&backend_idle))forced_isolations<=forced_isolations+1;
      owner<=3;core_resetn<=0;phase<=FAULT;changed<=1;
      if(auto_enable)action_request<=1;
     end
    end
    FAULT:if(auto_enable)action_request<=1;
    default:begin owner<=3;core_resetn<=0;phase<=FAULT;faults<=faults|32'h80000000;end
   endcase
   if(commit&&phase!=READY)result<=4;
   if(prepare)begin
    if(requested_owner==3)result<=1;
    else if(phase!=RUN&&phase!=FAULT&&phase!=READY)result<=4;
    else begin
     target<=requested_owner;generation<=generation+1;confirmed<=0;quiet<=0;phase<=DRAIN;result<=0;retry_age<=0;
     if(auto_enable&&action_request==2&&requested_owner!=0)retry_count<=retry_count+1;
     action_request<=0;changed<=1;
    end
   end
   // Live faults have priority over preparation and may never reconnect PS.
   if(live_fault!=0 && (phase==RUN||phase==INIT||phase==READY) && (owner==1||owner==2||target!=0&&owner==3))begin
    faults<=faults|live_fault;phase<=FAULT_DRAIN;fault_wait<=0;confirmed<=0;
    generation<=generation+1;fault_event<=1;action_request<=0;result<=5;
   end
  end
 end
endmodule
