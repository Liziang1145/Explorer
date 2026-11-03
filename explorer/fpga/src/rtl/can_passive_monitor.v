// Passive classic CAN observer. No bus-driving ports, no ACK generation.
// Standard data frames only; unsupported frames are counted, never decoded as data.
module can_passive_monitor #(parameter BIT_CYCLES=100, SAMPLE_CYCLE=75)(
 input clk, input resetn, input rx_raw, input tx_raw, input [63:0] cycles,
 output reg sof_valid, output reg frame_valid, output reg [10:0] frame_id, output reg [3:0] frame_dlc,
 output reg [63:0] frame_data, output reg frame_ack, output reg frame_local,
 output reg [63:0] sof_cycle, output reg [63:0] eof_cycle,
 output reg [31:0] frame_count, error_count, unsupported_count, ack_missing_count);
 (* ASYNC_REG="TRUE" *) reg [1:0] rx_sync=3, tx_sync=3;
 reg prev_rx=1;
 reg [15:0] phase=0, idle_count=0;
 reg [3:0] state=0, run_count=0, tail_count=0;
 reg last_bit=1, final_stuff=0;
 reg [7:0] bit_index=0, data_end=19;
 reg [14:0] crc=0;
 reg [10:0] id=0;
 reg [3:0] dlc=0;
 reg [63:0] data=0;
 reg local_candidate=0, ack=0;
 wire falling=prev_rx && !rx_sync[1];
 wire sample=(phase==SAMPLE_CYCLE);
 wire [14:0] crc_next={crc[13:0],1'b0} ^ ((crc[14]^rx_sync[1]) ? 15'h4599 : 15'h0);
 always @(posedge clk) begin
   rx_sync<={rx_sync[0],rx_raw}; tx_sync<={tx_sync[0],tx_raw}; prev_rx<=rx_sync[1];
   frame_valid<=0; sof_valid<=0;
   if(!resetn) begin
     state<=0; idle_count<=0; phase<=0; frame_count<=0; error_count<=0;
     unsupported_count<=0; ack_missing_count<=0; frame_id<=0; frame_dlc<=0;
     frame_data<=0; frame_ack<=0; frame_local<=0; sof_cycle<=0; eof_cycle<=0;
   end else if(state==0) begin
     if(rx_sync[1]) begin if(idle_count<11*BIT_CYCLES) idle_count<=idle_count+1; end
     else idle_count<=0;
     if(falling && idle_count>=11*BIT_CYCLES) begin
       sof_valid<=1; state<=1; phase<=0; bit_index<=0; data_end<=19; crc<=0; run_count<=0;
       last_bit<=1; id<=0; dlc<=0; data<=0; local_candidate<=!tx_sync[1];
       ack<=0; sof_cycle<=cycles; final_stuff<=0;
     end
   end else begin
     // Re-synchronise to recessive-to-dominant edges before sample point.
     // Bounded phase correction (SJW=10 clocks at 100 MHz).
     if(falling && phase< SAMPLE_CYCLE && phase!=0) phase <= (phase>10 ? phase-10 : 0);
     else if(falling && phase>SAMPLE_CYCLE) phase <= (phase+10>=BIT_CYCLES ? 0 : phase+10);
     else if(phase==BIT_CYCLES-1) phase<=0; else phase<=phase+1;
     if(sample) begin
       case(state)
       1: begin
         if(run_count==5) begin
           if(rx_sync[1]==last_bit) begin state<=0; idle_count<=0; error_count<=error_count+1; end
           else begin run_count<=1; last_bit<=rx_sync[1]; if(final_stuff) begin state<=2; final_stuff<=0; end end
         end else begin
           last_bit<=rx_sync[1];
           if(run_count!=0 && rx_sync[1]==last_bit) run_count<=run_count+1; else run_count<=1;
           if(bit_index>=1 && bit_index<=11) begin
             id<={id[9:0],rx_sync[1]};
             if(local_candidate && tx_sync[1] && !rx_sync[1]) local_candidate<=0;
           end
           if(bit_index==12 && rx_sync[1]) begin state<=0; idle_count<=0; unsupported_count<=unsupported_count+1; end
           if(bit_index==13 && rx_sync[1]) begin state<=0; idle_count<=0; unsupported_count<=unsupported_count+1; end
           if(bit_index==14 && rx_sync[1]) begin state<=0; idle_count<=0; error_count<=error_count+1; end
           if(bit_index>=15 && bit_index<=18) dlc<={dlc[2:0],rx_sync[1]};
           if(bit_index==18) begin
             if({dlc[2:0],rx_sync[1]}>8) begin state<=0; idle_count<=0; unsupported_count<=unsupported_count+1; end
             else data_end<=19+({dlc[2:0],rx_sync[1]}*8);
           end
           if(bit_index>=19 && bit_index<data_end) data<={data[62:0],rx_sync[1]};
           crc<=crc_next; bit_index<=bit_index+1;
           if(bit_index==data_end+14) begin
             if(crc_next!=0) begin state<=0; idle_count<=0; error_count<=error_count+1; end
             else if(run_count==4 && rx_sync[1]==last_bit) final_stuff<=1;
             else state<=2;
           end
         end
       end
       2: if(!rx_sync[1]) begin state<=0; idle_count<=0; error_count<=error_count+1; end else state<=3;
       3: begin ack<=!rx_sync[1]; state<=4; end
       4: if(!rx_sync[1]) begin state<=0; idle_count<=0; error_count<=error_count+1; end else begin state<=5; tail_count<=0; end
       5: if(!rx_sync[1]) begin state<=0; idle_count<=0; error_count<=error_count+1; end
          else if(tail_count==6) begin
            frame_valid<=1; frame_id<=id; frame_dlc<=dlc; frame_data<=data << ((8-dlc)*8);
            frame_ack<=ack; frame_local<=local_candidate; eof_cycle<=cycles; frame_count<=frame_count+1;
            if(!ack) ack_missing_count<=ack_missing_count+1;
            state<=6; tail_count<=0;
          end else tail_count<=tail_count+1;
       6: if(!rx_sync[1]) begin state<=0; idle_count<=0; end
          else if(tail_count==2) begin state<=0; idle_count<=11*BIT_CYCLES; end else tail_count<=tail_count+1;
       default: begin state<=0; idle_count<=0; end
       endcase
     end
   end
 end
endmodule
