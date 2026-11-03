/* HEVC WebSocket/MSE player: bounded queue, per-viewer adaptation, no JPEG fallback. */
window.NetworkVideoPlayer=class {
 constructor(video,id,options={}){
  Object.assign(this,{video,id,options,wanted:true,frames:0,dropped:0,bytes:0,quality:options.quality||'auto',currentQuality:null,targetFPS:30,queue:[],queueBytes:0,busy:false,generation:0});
  this.client=Array.from(crypto.getRandomValues(new Uint8Array(16)),x=>x.toString(16).padStart(2,'0')).join('');this.sample=this.lastFrame=performance.now();
  this.supported=!!window.MediaSource&&MediaSource.isTypeSupported('video/mp4; codecs="hvc1.1.6.L153.B0"');video.muted=true;video.playsInline=true;
  this.timer=setInterval(()=>this.report(),3000);if(this.supported)this.connect();else options.onError?.('此浏览器未提供H.265解码，请安装系统HEVC解码组件或使用支持HEVC的浏览器');
 }
 connect(){
  if(!this.wanted)return;const generation=++this.generation;this.queue=[];this.queueBytes=0;
  const socket=this.socket=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+(this.options.path||'/api/v1/cameras/'+encodeURIComponent(this.id)+'/video-ws?client_id='+this.client+'&quality='+encodeURIComponent(this.quality)));socket.binaryType='arraybuffer';
  socket.onmessage=e=>{
   if(generation!==this.generation)return;
   if(typeof e.data==='string'){try{const config=JSON.parse(e.data);if(config.type!=='config')return;this.queue.push({config});}catch{return;}}
   else{this.bytes+=e.data.byteLength;this.queueBytes+=e.data.byteLength;this.queue.push({bytes:e.data});}
   if(this.queueBytes>4*1024*1024||this.queue.length>90){this.feedback({stalled:true});this.options.onError?.('客户端解码拥塞，正在降档');socket.close();return;}this.drain(generation);
  };
  socket.onclose=()=>{if(generation!==this.generation)return;if(this.wanted){this.options.onError?.('视频重连中');this.retry=setTimeout(()=>this.connect(),900);}};
  socket.onerror=()=>{if(generation===this.generation)this.options.onError?.('视频连接失败，请检查登录或网络');};
 }
 async configure(config,generation){
  try{if(this.ms?.readyState==='open')this.ms.endOfStream();}catch{}
  if(this.objectURL)URL.revokeObjectURL(this.objectURL);
  const ms=this.ms=new MediaSource();this.currentQuality=config.quality;this.targetFPS=config.fps;this.statsReady=false;this.configuredAt=performance.now();
  this.video.addEventListener('loadedmetadata',()=>{if(this.ms!==ms)return;const q=this.video.getVideoPlaybackQuality();this.frames=q.totalVideoFrames;this.dropped=q.droppedVideoFrames;this.bytes=0;this.sample=this.lastFrame=performance.now();this.statsReady=true;},{once:true});
  this.video.src=this.objectURL=URL.createObjectURL(ms);
  await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('H.265初始化超时')),4000);ms.addEventListener('sourceopen',()=>{clearTimeout(timer);resolve();},{once:true});});
  if(generation!==this.generation)throw Error('旧连接已结束');this.sb=ms.addSourceBuffer(config.mime);this.sample=this.lastFrame=performance.now();this.frames=0;this.dropped=0;this.trim=0;
 }
 async change(fn){
  const sb=this.sb;
  await new Promise((resolve,reject)=>{
   let timer;const clean=()=>{clearTimeout(timer);sb.removeEventListener('updateend',done);sb.removeEventListener('error',fail);};
   const done=()=>{clean();resolve();},fail=()=>{clean();reject(Error('H.265解码失败'));};
   sb.addEventListener('updateend',done,{once:true});sb.addEventListener('error',fail,{once:true});timer=setTimeout(()=>{clean();reject(Error('视频解码超时'));},3000);
   try{fn(sb);}catch(e){clean();reject(e);}
  });
 }
 async drain(generation){
  if(this.busy)return;this.busy=true;
  try{
   while(this.queue.length&&this.wanted&&generation===this.generation){
    const item=this.queue.shift();if(item.config){await this.configure(item.config,generation);continue;}
    this.queueBytes-=item.bytes.byteLength;await this.change(sb=>sb.appendBuffer(item.bytes));const sb=this.sb;
    if(sb.buffered.length){
     const end=sb.buffered.end(sb.buffered.length-1),start=sb.buffered.start(0);
     if(this.video.currentTime<start||end-this.video.currentTime>.55)this.video.currentTime=Math.max(start,end-.15);
     this.video.play().catch(()=>{});if(this.video.readyState>=2)this.options.onLive?.();
     if(end-start>5&&performance.now()-this.trim>1000){this.trim=performance.now();await this.change(s=>s.remove(start,Math.max(start,end-3)));}
    }
   }
  }catch(e){if(generation===this.generation&&this.wanted){this.options.onError?.(e.message);this.feedback({stalled:true});this.socket?.close();}}
  finally{this.busy=false;if(this.queue.length&&this.wanted)this.drain(this.generation);}
 }
 feedback(data){if(this.socket?.readyState===WebSocket.OPEN)this.socket.send(JSON.stringify(data));}
 report(){
  if(!this.wanted)return;const now=performance.now();if(!this.statsReady||now-this.sample<1000){if(now-this.configuredAt>3000&&!this.statsReady)this.feedback({stalled:true});return;}
  const q=this.video.getVideoPlaybackQuality(),seconds=Math.max(.1,(now-this.sample)/1000),delta=Math.max(0,q.totalVideoFrames-this.frames),dropped=Math.max(0,q.droppedVideoFrames-this.dropped);
  if(delta>0)this.lastFrame=now;const buffer=this.video.buffered.length?Math.max(0,this.video.buffered.end(this.video.buffered.length-1)-this.video.currentTime):0;
  const data={stalled:now-this.lastFrame>1800,buffer,drop_ratio:delta>0?Math.max(0,dropped/delta):0,fps:Math.max(0,(delta-dropped)/seconds)};
  this.options.onMetrics?.({...data,width:this.video.videoWidth,height:this.video.videoHeight,quality:this.currentQuality,bitrate:this.bytes*8/seconds});this.bytes=0;this.frames=q.totalVideoFrames;this.dropped=q.droppedVideoFrames;this.sample=now;this.feedback(data);
 }
 stop(){this.wanted=false;this.generation++;clearInterval(this.timer);clearTimeout(this.retry);this.socket?.close();this.queue=[];this.queueBytes=0;try{if(this.ms?.readyState==='open')this.ms.endOfStream();}catch{}if(this.objectURL)URL.revokeObjectURL(this.objectURL);this.video.pause();this.video.removeAttribute('src');this.video.load();}
};
