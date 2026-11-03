// ABI v2: driver-coordinated reset with per-port cooldown and configurable quota.
module eth_recovery_watchdog_v2 #(
 parameter integer TIMEOUT_CYCLES=200000000,
 parameter integer RESET_CYCLES=2000,
 parameter integer SETTLE_CYCLES=2000000,
 parameter integer SECOND_CYCLES=100000000
)(
 (* X_INTERFACE_INFO="xilinx.com:signal:clock:1.0 clk CLK", X_INTERFACE_PARAMETER="ASSOCIATED_RESET resetn:port2_resetn:port3_resetn" *) input wire clk,
 (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 resetn RST", X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) input wire resetn,
 input wire [31:0] command_word,
 output wire [31:0] status_word,
 input wire phy2_raw_n, input wire phy3_raw_n,
 output wire phy2_n, output wire phy3_n,
 (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 port2_resetn RST", X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) output wire port2_resetn,
 (* X_INTERFACE_INFO="xilinx.com:signal:reset:1.0 port3_resetn RST", X_INTERFACE_PARAMETER="POLARITY ACTIVE_LOW" *) output wire port3_resetn,
 input wire [31:0] policy_word,
 output wire [31:0] detail_word
);
 wire [1:0] raw_n={phy3_raw_n,phy2_raw_n};
 wire [1:0] phy_n,local_n;
 wire [31:0] total_counts,cooldown_counts;
 wire [31:0] policies[0:1];
 reg [2:0] detail_page;
 assign {phy3_n,phy2_n}=phy_n;
 assign {port3_resetn,port2_resetn}=local_n;
 assign detail_word=(detail_page==1)?policies[0]:(detail_page==2)?policies[1]:
                    (detail_page==3)?cooldown_counts:(detail_page==4)?32'h57445432:total_counts;
 // One provider serializes command/policy writes and detail-page selection.
 // If both halfwords change in one write, port1 query has priority.
 integer k;
 always @(posedge clk) begin
  if(!resetn) detail_page<=0;
  else for(k=0;k<2;k=k+1) begin
   if(command_word[k*16+8+:8]!=status_word[k*16+8+:8]) begin
    case(command_word[k*16+:8])
     8'h22: detail_page<=k+1;
     8'h23: detail_page<=0;
     8'h24: detail_page<=3;
     8'h25: detail_page<=4;
     default: ;
    endcase
   end
  end
 end
 genvar g;
 generate for(g=0;g<2;g=g+1) begin: port_wdt
  localparam IDLE=0, GUARD=1, RESET=2, SETTLE=3, READY=4;
  reg [2:0] phase;
  reg armed,fault,rejected,guarded,reset_active;
  reg [15:0] total_count,max_resets,cooldown_seconds,cooldown_left;
  reg [31:0] cooldown_tick;
  reg [7:0] last_seq;
  reg [31:0] watchdog_count,phase_count;
  (* ASYNC_REG="TRUE" *) reg phy_meta,phy_sync;
  wire [7:0] seq=command_word[g*16+8+:8];
  wire [7:0] cmd=command_word[g*16+:8];
  wire quota_blocked=(max_resets!=0)&&(total_count>=max_resets);
  wire cooldown_active=(cooldown_left!=0);
  assign phy_n[g]=raw_n[g] | (resetn & guarded);
  assign local_n[g]=resetn & !reset_active;
  assign status_word[g*16+:16]={last_seq,quota_blocked,cooldown_active,rejected,fault,armed,phase};
  assign total_counts[g*16+:16]=total_count;
  assign cooldown_counts[g*16+:16]=cooldown_left;
  assign policies[g]={max_resets,cooldown_seconds};
  always @(posedge clk) begin
   if(!resetn) begin phy_meta<=0;phy_sync<=0;end
   else begin phy_meta<=raw_n[g];phy_sync<=phy_meta;end
  end
  always @(posedge clk) begin
   if(!resetn) begin
    phase<=IDLE;armed<=0;fault<=0;rejected<=0;
    total_count<=0;max_resets<=0;cooldown_seconds<=10;cooldown_left<=0;cooldown_tick<=0;
    last_seq<=0;watchdog_count<=0;phase_count<=0;guarded<=0;reset_active<=0;
   end else begin
    // Each cooldown second is a full SECOND_CYCLES ticks, independent per port.
    if(cooldown_active) begin
     if(cooldown_tick==0) begin cooldown_left<=cooldown_left-1;cooldown_tick<=SECOND_CYCLES-1;end
     else cooldown_tick<=cooldown_tick-1;
    end
    if(armed && !fault && phase==IDLE) begin
     if(watchdog_count>=TIMEOUT_CYCLES-1) begin fault<=1;armed<=0;end
     else watchdog_count<=watchdog_count+1;
    end
    if(phase==RESET) begin
     if(phase_count>=RESET_CYCLES-1) begin phase<=SETTLE;phase_count<=0;reset_active<=0;end
     else phase_count<=phase_count+1;
    end else if(phase==SETTLE) begin
     if(phase_count<SETTLE_CYCLES-1) phase_count<=phase_count+1;
     else if(phy_sync) begin phase<=READY;phase_count<=0;end
    end
    if(seq!=last_seq) begin
     last_seq<=seq;rejected<=0;
     case(cmd)
      8'h01: if(phase==IDLE && !fault) begin armed<=1;watchdog_count<=0;end else rejected<=1;
      8'h02: if(phase==IDLE && !fault) watchdog_count<=0;else rejected<=1;
      8'h03: if(phase==IDLE) begin armed<=0;watchdog_count<=0;end else rejected<=1;
      8'h04: if(phase==IDLE) begin fault<=1;armed<=0;end else rejected<=1;
      8'h10: if(phase==IDLE && fault && phy_sync && !quota_blocked && !cooldown_active) begin
       phase<=GUARD;armed<=0;phase_count<=0;guarded<=1;
      end else rejected<=1;
      8'h11: if(phase==GUARD && !quota_blocked && !cooldown_active) begin
       phase<=RESET;phase_count<=0;reset_active<=1;
       if(total_count!=16'hffff) total_count<=total_count+1;
       cooldown_left<=cooldown_seconds;cooldown_tick<=SECOND_CYCLES-1;
      end else rejected<=1;
      8'h12: if(phase==GUARD && phy_sync) begin phase<=IDLE;guarded<=0;end else rejected<=1;
      8'h13: if(phase==READY && phy_sync) begin
       phase<=IDLE;fault<=0;watchdog_count<=0;armed<=0;guarded<=0;
      end else rejected<=1;
      // Apply staged policy atomically. Zero quota=unlimited; cooldown cannot be zero.
      // Updating policy never shortens an already active cooldown or clears quota usage.
      8'h20: if(phase==IDLE && !armed && policy_word[15:0]!=0) begin
       max_resets<=policy_word[31:16];cooldown_seconds<=policy_word[15:0];
      end else rejected<=1;
      // Explicit quota epoch reset; cooldown and sticky fault are preserved.
      8'h21: if(phase==IDLE && !armed) total_count<=0;else rejected<=1;
      8'h22,8'h23,8'h24,8'h25: ;
      default: rejected<=1;
     endcase
    end
   end
  end
 end endgenerate
endmodule
