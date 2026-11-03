/* Shared live player: stalled streams reconnect without a keyboard or page reload. */
window.HEVCPlayer=class{
 constructor(video,kind,options={}){this.mime='video/mp4; codecs="'+(options.codec||'hvc1.1.6.L93.B0')+'"';this.path=options.path||'/ui/hevc/'+kind;Object.assign(this,{video,kind,wanted:true,frames:0,fps:0,restarts:0,error:'',createdAt:performance.now(),at:performance.now(),lastProgressAt:performance.now()});this.supported=!!window.MediaSource&&MediaSource.isTypeSupported(this.mime);video.muted=true;video.playsInline=true;video.style.visibility='visible';this.run()}
 async timeout(promise,ms){let timer;try{return await Promise.race([promise,new Promise((_,reject)=>timer=setTimeout(()=>reject(Error('视频数据或解码超时，正在重连')),ms))])}finally{clearTimeout(timer)}}
 async run(){while(this.wanted){let reader,url;try{
  if(!this.supported)throw Error('此浏览器未提供 HEVC 解码');this.abort=new AbortController();const ms=this.ms=new MediaSource();url=URL.createObjectURL(ms);this.video.srcObject=null;this.video.src=url;this.frames=0;this.fps=0;this.at=this.lastProgressAt=performance.now();
  await this.timeout(new Promise(resolve=>ms.addEventListener('sourceopen',resolve,{once:true})),4000);URL.revokeObjectURL(url);url=null;
  const sb=ms.addSourceBuffer(this.mime);const response=await this.timeout(fetch(this.path,{cache:'no-store',signal:this.abort.signal}),8000);if(!response.ok)throw Error('视频服务 HTTP '+response.status);reader=response.body.getReader();let trim=0;
  const change=fn=>this.timeout(new Promise((resolve,reject)=>{const clean=()=>{sb.removeEventListener('updateend',ok);sb.removeEventListener('error',fail)},ok=()=>{clean();resolve()},fail=()=>{clean();reject(Error('HEVC 解码缓存错误'))};sb.addEventListener('updateend',ok,{once:true});sb.addEventListener('error',fail,{once:true});try{fn()}catch(e){clean();reject(e)}}),4000);
  while(this.wanted){const {done,value}=await this.timeout(reader.read(),7000);if(done)throw Error('视频源断开，正在重连');await change(()=>sb.appendBuffer(value));
   if(sb.buffered.length){const end=sb.buffered.end(sb.buffered.length-1),start=sb.buffered.start(0);if(this.video.currentTime<start||end-this.video.currentTime>.45)this.video.currentTime=Math.max(start,end-.12);this.video.playbackRate=end-this.video.currentTime>.22?1.03:1;this.video.play().catch(()=>{});if(start<end-5&&performance.now()-trim>1000){trim=performance.now();await change(()=>sb.remove(start,Math.max(start,end-3)))}}
   const report=this.metrics();if(document.visibilityState==='visible'&&this.video.offsetParent!==null&&report.frame_age_ms>6000)throw Error('视频解码停止，正在重连');this.error='';
  }
 }catch(e){this.error=e.message;if(this.wanted)this.restarts++}
 finally{this.abort?.abort();try{if(reader)await this.timeout(reader.cancel(),1000)}catch{}try{this.ms?.endOfStream()}catch{}if(url)URL.revokeObjectURL(url)}
 if(!this.supported)return;if(this.wanted)await new Promise(r=>setTimeout(r,1500));
 }}
 metrics(){const q=this.video.getVideoPlaybackQuality(),now=performance.now(),elapsed=(now-this.at)/1000;if(q.totalVideoFrames!==this.progressFrames){this.progressFrames=q.totalVideoFrames;this.lastProgressAt=now}if(elapsed>=.5){this.fps=Math.max(0,Math.round((q.totalVideoFrames-this.frames)/elapsed));this.frames=q.totalVideoFrames;this.at=now}return {kind:this.kind,supported:this.supported,ready:this.video.readyState>=2,width:this.video.videoWidth,height:this.video.videoHeight,frames:q.totalVideoFrames,dropped:q.droppedVideoFrames,fps:this.fps,frame_age_ms:Math.round(now-this.lastProgressAt),restarts:this.restarts,buffer:this.video.buffered.length?Math.max(0,this.video.buffered.end(this.video.buffered.length-1)-this.video.currentTime):0,error:this.error}}
 report(){return this.metrics()}
 stop(){this.wanted=false;this.abort?.abort();this.video.pause()}
};
