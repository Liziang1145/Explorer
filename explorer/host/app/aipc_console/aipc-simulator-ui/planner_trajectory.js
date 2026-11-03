/* 双臂坐标规划只读轨迹预览：实体模型仅消费预检六轴轨迹，不发送控制请求。 */
(function(){
'use strict';
const players={};
function valid(result){
 return Array.isArray(result.q)&&result.q.length>0&&Array.isArray(result.times)&&result.times.length===result.q.length&&
 result.q.every(q=>Array.isArray(q)&&q.length===6&&q.every(Number.isFinite))&&result.times.every(Number.isFinite);
}
function create(side){
 const suffix=side==='right'?'-right':'',ID='vla-trajectory-canvas'+suffix;
 const panel=document.getElementById('vla-trajectory-panel'+suffix),replay=document.getElementById('vla-replay'+suffix);
 if(!panel||!replay)return null;
 let data=null,animation=0,playing=false,previewTime=0,waitTimer=0;
 const duration=()=>data?Math.max(0,Number(data.times[data.times.length-1])||0):0;
 function sample(time){
  const ts=data.times,qs=data.q;if(qs.length===1)return qs[0].slice();
  let i=0;while(i<ts.length-2&&ts[i+1]<time)i++;
  const f=Math.max(0,Math.min(1,(time-ts[i])/(ts[i+1]-ts[i]||1)));
  return qs[i].map((v,j)=>v+(qs[i+1][j]-v)*f);
 }
 function render(){if(data)window.SolidArmViewer?.setPose(ID,sample(previewTime),0);}
 function stop(){playing=false;cancelAnimationFrame(animation);clearTimeout(waitTimer);waitTimer=0;replay.textContent='▶ 播放轨迹';}
 function play(){
  if(!data)return;stop();
  if(!window.SolidArmViewer?.isReady?.(ID)){replay.textContent='模型加载中…';waitTimer=setTimeout(play,150);return;}
  if(previewTime>=duration())previewTime=0;render();
  if(duration()<=0)return;
  playing=true;replay.textContent='■ 停止播放';const start=performance.now(),from=previewTime;
  function frame(now){if(!playing)return;previewTime=Math.min(duration(),from+(now-start)/1000);render();if(previewTime<duration())animation=requestAnimationFrame(frame);else stop();}
  animation=requestAnimationFrame(frame);
 }
 function clear(){stop();data=null;previewTime=0;panel.hidden=true;}
 function show(result){
  if(!valid(result))throw Error('预检结果缺少有效的六轴轨迹数据');
  stop();data=result;previewTime=0;panel.hidden=false;
  document.getElementById('vla-metric-time'+suffix).textContent=Number(result.duration_s).toFixed(2)+' s';
  document.getElementById('vla-metric-distance'+suffix).textContent=(Number(result.displacement_norm_m)*1000).toFixed(1)+' mm';
  const margin=Number(result.minimum_mesh_clearance_cm);
  document.getElementById('vla-metric-margin'+suffix).textContent=Number.isFinite(margin)?margin.toFixed(2)+' cm':'—';play();
 }
 replay.onclick=()=>playing?stop():play();
 window.addEventListener('solid-arm-viewer-ready',event=>{if(data&&event.detail===ID)play();});
 return Object.freeze({show,clear,play,stop});
}
for(const side of ['left','right'])players[side]=create(side);
window.PlannerTrajectory=Object.freeze({
 show(result,side='left'){players[side]?.show(result);},
 clear(side='left'){players[side]?.clear();},
 play(side='left'){players[side]?.play();},
 stop(side='left'){players[side]?.stop();}
});
})();
