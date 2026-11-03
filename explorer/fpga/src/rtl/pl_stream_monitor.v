// Tap-only 125 MHz DMA AXIS statistics. Never drives READY or RESET.
module pl_stream_monitor(input clk,input resetn,input req_async,
 input [3:0] valid,ready,last,input [15:0] keep,
 output reg ack=0, output reg [1023:0] snapshot=0);
 (* ASYNC_REG="TRUE" *) reg [1:0] req_sync=0;
 (* ASYNC_REG="TRUE" *) reg [1:0] reset_sync=0;
 reg [63:0] count[0:15]; integer i;
 function [2:0] pop4(input [3:0] x); begin pop4={2'b0,x[0]}+x[1]+x[2]+x[3]; end endfunction
 always @(posedge clk) begin
   reset_sync<={reset_sync[0],resetn}; req_sync<={req_sync[0],req_async};
   if(!reset_sync[1]) begin
     ack<=0; snapshot<=0; for(i=0;i<16;i=i+1) count[i]<=0;
   end else begin
     for(i=0;i<4;i=i+1) begin
       if(valid[i] && ready[i]) begin
         count[4*i]<=count[4*i]+1;
         count[4*i+1]<=count[4*i+1]+pop4(keep[4*i+:4]);
         if(last[i]) count[4*i+2]<=count[4*i+2]+1;
       end
       if(valid[i] && !ready[i]) count[4*i+3]<=count[4*i+3]+1;
     end
     if(req_sync[1]!=ack) begin
       for(i=0;i<16;i=i+1) snapshot[64*i+:64]<=count[i];
       ack<=req_sync[1];
     end
   end
 end
endmodule
