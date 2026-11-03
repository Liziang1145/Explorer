/* Shared wording: an HTTP failure does not prove that the AIPC host is powered off. */
window.ConnectionStatus={
 read(source){
  source=source||{};const age=source.age_ms,target=source.target||'192.168.137.2:8097',last=source.last_success_at?new Date(source.last_success_at*1000).toLocaleTimeString():'尚未成功';
  const detail=target+' · 最近成功 '+last;
  if(source.error)return {ok:false,title:source.error,detail,reason:source.error};
  if(typeof age!=='number'||!Number.isFinite(age))return {ok:false,title:'AIPC 尚未连接',detail,reason:'等待首次连接结果'};
  if(age>=2000)return {ok:false,title:'AIPC 状态已过期',detail,reason:'超过 2 秒未收到有效状态'};
  if(!source.data?.health)return {ok:false,title:'AIPC 可达 · 业务状态异常',detail,reason:'观察接口未返回有效业务状态'};
  if(source.data.health.aipc_connected===false)return {ok:false,title:'AIPC 可达 · 业务链路未连接',detail,reason:'AIPC 网关报告业务链路未连接'};
  return {ok:true,title:'AIPC 已连接',detail:target+' · RTT '+(typeof source.rtt_ms==='number'?Math.round(source.rtt_ms)+' ms':'—')+' · 状态年龄 '+Math.round(age)+' ms',reason:''};
 },
 video(snapshot,kind,report){
  const link=this.read(snapshot?.snapshot);if(!link.ok)return {ok:false,text:link.title};
  const status=snapshot?.['media-status'];if(status?.error)return {ok:false,text:'视频状态获取失败 · '+status.error};
  if(typeof status?.age_ms!=='number'||status.age_ms>=3000)return {ok:false,text:'视频状态未更新'};
  const source=status.data?.streams?.[kind];
  if(!source||!(source.source_frames>0))return {ok:false,text:'AIPC 已连接 · 视频源尚无数据'};
  if(source.state!=='active')return {ok:false,text:'视频源未运行'+(source.error?' · '+source.error:'')};
  if(typeof source.source_age_ms!=='number'||source.source_age_ms>=1500)return {ok:false,text:'视频源停止更新'};
  if(report&&!report.ready)return {ok:false,text:report.error?'浏览器解码失败 · '+report.error:'已收到源状态 · 正在连接视频流'};
  if(report&&!(report.fps>0))return {ok:false,text:'视频流暂未解出新帧'};
  return {ok:true,text:'视频正常 · 源年龄 '+Math.round(source.source_age_ms)+' ms'};
 }
};
