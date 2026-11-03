'use strict';
(()=>{
const panel=document.createElement('section');panel.id='drive-panel';
panel.innerHTML=`<h2>底盘导航 · 监督式路线跟踪</h2>
<p class="warn">真实控制入口。导航速度可选 0～0.30 m/s，角速度上限 0.20 rad/s，弯道会按曲率减速；点击开始后自动检查路线。优先边走边转；无法圆滑但旋转空间充足的转角会停车转向，再继续行驶。遇障、定位异常或页面失联会停车，不自动绕障。仅控制底盘。</p>
<button type="button" id="drive-stop" class="drive-stop">■ 停止底盘路线（不停止机械臂）</button>
<p id="drive-state" role="status">读取底盘接口与实时定位…</p>
<details open><summary>现场确认与执行</summary>
<label for="drive-speed">导航巡航速度（m/s）</label>
<input id="drive-speed" type="number" min="0" max="0.3" step="0.01" value="0.20" inputmode="decimal" style="width:9em;padding:9px;font-size:17px">
<p id="drive-speed-note">范围 0～0.30；0 不启动。默认前视距离 0.60 m。弯道和接近终点会减速；行驶中不能改速；每次开始自动按所选速度检查。</p>
<p id="drive-feedback"></p><p id="drive-goal">请在地图选择目标。</p>
<div class="drive-checks"><label><input id="drive-confirm" type="checkbox">已完成现场检查：车辆停稳、地图车位与车头正确、路线畅通、其它控制端已停止，且有人全程看守并能立即按急停。</label></div>
<button id="drive-route" class="drive-execute">开始到目标导航（车辆会动）</button>
<button id="drive-drawn" class="drive-execute">执行手绘路线（车辆会动）</button>
<p>一次点击自动完成路线检查并执行，不再单独点预览。任何检查失败都不会启动。</p>
<details><summary>短步测试</summary><div class="row"><button id="drive-forward">前进短步（车辆会动）</button><button id="drive-right">右转短步（车辆会动）</button></div></details>
<pre id="drive-preview">选择目标或画路线，完成一次现场确认，然后点击开始。</pre>
<button id="drive-refresh">刷新状态（不移动）</button>
<p id="drive-result" role="status">未发送运动命令。</p>
<p>执行时保持此页前台可见。关闭或切换页面会停止续行；软件停止不能代替物理急停。本版本不检测所有低矮物、台阶或传感器盲区。</p>
</details>
<details open class="motion-history"><summary>行车动作日志 · 时间 / 地点 / 转角</summary>
<div class="row"><select id="motion-run" aria-label="选择历史行车记录"></select><button id="motion-refresh">刷新记录</button><button id="motion-download">导出 JSON</button></div>
<p id="motion-summary">正在读取已保存的行车记录…</p>
<p class="muted">点击某个动作，可在地图上定位并查看该段轨迹。转角为定位观察到的车头变化，非转向轮角度。</p>
<div id="motion-events" class="motion-events"></div><pre id="motion-detail"></pre>
</details>`;
document.querySelector('.map-module main aside').prepend(panel);
const dock=document.createElement('div');dock.className='drive-stop-dock';dock.append(document.getElementById('drive-stop'));document.querySelector('.map-module').append(dock);document.querySelector('.map-module').classList.add('with-drive-dock');
const $=id=>document.getElementById(id);let state=null,selection=null,drawnSelection=null,busy=false,statusBusy=false,runId=null,heartBusy=false,previewRevision=0;
const say=(id,v)=>$(id).textContent=String(v);
const runLabel=s=>({accepted:'路线已接受',approaching_turn:'接近必要转角，减速',turn_braking:'转角前停车，等待零速反馈',turn_aligning:'必要转角原地转向',turn_settling:'转向结束，等待零速反馈',aligning:'起步朝向对齐',arc_right:'前进并右转',arc_left:'前进并左转',forward:'前进',checking_stop:'等待零速反馈',arrived_within_10cm:'到达（距目标不超过 10 cm）',arrived_within_15cm:'历史到达判据（15 cm）',checkpoint_after_right_turn:'右转后检查点已停稳',single_pulse_stopped:'短步结束并停稳',stopped:'已停止'}[s]||s);
async function request(kind,data){const ctl=new AbortController(),timer=setTimeout(()=>ctl.abort(),kind==='preview'?45000:12000);try{const r=await fetch('/hub/api/drive/'+kind,{cache:'no-store',signal:ctl.signal,...(data?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}:{})});const d=await r.json();if(!r.ok)throw Error(d.error||r.status);return d;}finally{clearTimeout(timer);}}
function selectedSpeed(){const el=$('drive-speed');if(!el.value.trim()||!el.checkValidity())throw Error('请输入 0～0.30 m/s 的有效速度');const v=Number(el.value);if(!Number.isFinite(v)||v<0||v>.3)throw Error('速度超出 0～0.30 m/s');return v;}
const ACK_KEYS=['observer_at_estop','other_controllers_idle','path_and_envelope_clear','pose_matches_vehicle'];
function ack(){return Object.fromEntries(ACK_KEYS.map(k=>[k,$('drive-confirm').checked]));}
function discard(){previewRevision++;buttons();}
function buttons(){
 const locked=busy||state?.busy===true;
 $('drive-speed').disabled=locked;
 const allowed=$('drive-confirm').checked&&!locked&&!!state&&!document.hidden;
 for(const id of ['drive-forward','drive-right'])$(id).disabled=!allowed;
 $('drive-route').disabled=!allowed||!selection?.goal;
 $('drive-drawn').disabled=!allowed||!(drawnSelection?.points?.length>=2);
 if($('brush-preview')){$('brush-preview').disabled=$('drive-drawn').disabled;$('brush-preview').title='完成左侧一次现场确认后执行；路线检查自动完成';}
 $('drive-refresh').disabled=busy;
 document.dispatchEvent(new CustomEvent('navigation-drive-state',{detail:{busy:locked||state?.busy!==false}}));
}
$('drive-confirm').onchange=discard;
$('drive-speed').addEventListener('input',()=>{discard();say('drive-preview','速度已修改；点击开始后自动检查。0 表示不启动。');});
document.addEventListener('navigation-selection',e=>{selection=e.detail;discard();say('drive-goal',selection.goal?'地图目标：'+selection.goal.map(v=>v.toFixed(2)).join(', ')+' m':'请在地图选择目标。');});
document.addEventListener('navigation-drawn-change',e=>{drawnSelection=e.detail;discard();});
async function refresh(){if(statusBusy||busy||document.hidden)return;statusBusy=true;const refreshTicket=previewRevision;try{const next=await request('status');if(busy||refreshTicket!==previewRevision)return;state=next;say('drive-state',(state.busy?'正在跟踪路线':state.ready?'可以开始（点击后车辆会动）':state.safety?.stopped===true?'原控制台软件停止已锁存，请先在原控制台解除':'等待条件满足；点击开始会自动核对')+'\n'+state.blockers.join('\n'));const b=state.base?.device,fb=b?.feedback;
say('drive-feedback',`软件停止：${state.safety?.stopped===false?'未锁存':'已锁存/未知'}；VR 模式：${state.control?.mode||'未知'}\n底盘反馈：${b?.fresh?'新鲜':'过期'}${fb?'，vx='+fb.vx+' m/s，角速度原字段='+fb.angular_raw:''}\n命令角速度使用 rad/s；反馈角速度保留原值，仅用来判断接近零。`);
if(state.run){document.dispatchEvent(new CustomEvent('navigation-route-run',{detail:state.run}));say('drive-result',`状态：${runLabel(state.run.state)}\n进度：${state.run.progress_m.toFixed(2)} / ${state.run.length_m.toFixed(2)} m\n速度更新 ${state.run.pulses} 次（连续续发，不代表停走次数）\n${state.run.error||''}`);}else if(state.last)say('drive-result',JSON.stringify(state.last,null,2));
if(!state.busy)runId=null;
}catch(e){state=null;say('drive-state','服务不可达：'+e.message+'；若在运动，请观察实车并准备急停。');}finally{statusBusy=false;buttons();}}
// BEGIN CHECKED START: dependency-injected for offline cancellation tests.
async function checkedStart(d,checks,io){
 let submitted=false;
 const valid=()=>{if(!io.valid())throw Error('操作已取消：页面、选点、速度或现场确认已变化。');};
 try{
  valid();const state=await io.request('status');valid();
  if(state.busy)throw Error('车辆任务仍在执行，不能重复启动。');
  if(state.safety?.stopped!==false||state.safety?.pending!==false)throw Error('原控制台软件停止仍锁存或状态未知。请先在原控制台解除软件停止，再回到这里点击开始；现场勾选不会解除停止。');
  if(state.inhibited){await io.request('rearm',{confirm_base_idle:true});valid();}
  // Existing backend still checks source, pose, map, CAN feedback and sweep.
  const plan=await io.request('preview',d);valid();io.plan(plan);
  valid();submitted=true;
  const result=await io.request('execute',{token:plan.token,acknowledgements:checks});
  valid();io.accept(result);return result;
 }catch(e){
  // Never retry execution. If submission may have occurred, cancel the base.
  if(submitted){try{await io.request('stop',{confirm_base_stop:true});}catch(stopError){throw Error(e.message+'；底盘停止未确认，请使用物理急停。');}}
  throw e;
 }
}
// END CHECKED START
async function start(d){
 if(busy||state?.busy||!$('drive-confirm').checked||document.hidden)return;
 discard();const ticket=previewRevision;busy=true;buttons();say('drive-preview','正在自动检查路线、定位、反馈与停止状态…');
 try{
  d=JSON.parse(JSON.stringify({...d,map_revision:d.map_revision||selection?.map_revision||state?.navigation?.map_revision}));
  if(d.kind==='route'||d.kind==='drawn'){d.speed_m_s=selectedSpeed();if(d.speed_m_s===0)throw Error('导航速度为0，不启动。');}
  await checkedStart(d,ack(),{
   request,valid:()=>ticket===previewRevision&&!document.hidden&&$('drive-confirm').checked,
   plan:p=>{say('drive-preview',JSON.stringify({路线长度米:p.length_m,速度上限:p.smoothing?.max_speed_m_s,必要停车转向:p.smoothing?.stop_turns||[],状态:'检查通过，正在提交执行'},null,2));if(p.points?.length)document.dispatchEvent(new CustomEvent('navigation-route-run',{detail:{points:p.points,state:'starting',stop_turns:p.smoothing?.stop_turns||[]}}));},
   accept:r=>{runId=r.run_id;say('drive-result','已开始，请保持页面前台可见并观察车辆。');}
  });
 }catch(e){say('drive-preview','未启动或已中止：'+e.message);}
 finally{busy=false;$('drive-confirm').checked=false;buttons();await refresh();}
}
$('drive-forward').onclick=()=>start({kind:'manual',direction:'forward'});
$('drive-right').onclick=()=>start({kind:'manual',direction:'right_turn'});
$('drive-route').onclick=()=>{if(!selection?.goal)return;start({kind:'route',goal:selection.goal});};
$('drive-drawn').onclick=()=>{if($('drive-drawn').disabled||!drawnSelection?.points?.length)return;start({kind:'drawn',points:drawnSelection.points,map_revision:drawnSelection.map_revision});};
$('drive-stop').onclick=async()=>{discard();runId=null;try{say('drive-result',JSON.stringify(await request('stop',{confirm_base_stop:true}),null,2));}catch(e){say('drive-result','底盘停止未确认：'+e.message+'；请立即使用物理急停。');}await refresh();};
$('drive-refresh').onclick=()=>refresh();

document.addEventListener('visibilitychange',()=>{if(document.hidden){discard();if(runId){runId=null;fetch('/hub/api/drive/stop',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirm_base_stop:true}),keepalive:true}).catch(()=>{});}}else refresh();});
setInterval(async()=>{if(!runId||document.hidden||heartBusy)return;heartBusy=true;try{await request('heartbeat',{run_id:runId});}catch(e){runId=null;say('drive-result','心跳中断，路线将停止：'+e.message);}finally{heartBusy=false;}},500);
setInterval(buttons,250);
setInterval(refresh,1000);buttons();refresh();
let history=[],historyBusy=false,workspaceTab='control';
const localTime=t=>new Date(t*1000).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',hour12:false});
function showHistory(){
 const run=history.find(r=>r.id===$('motion-run').value);$('motion-events').replaceChildren();if(!run)return;
 const stats=run.summary;
 say('motion-summary',`${localTime(run.started_s)} · ${run.status} · ${run.event_count} 个动作段`+(stats?`\n历时 ${stats.duration_s.toFixed(1)} s · 行进转弯 ${stats.combined_turn_segments} 段 · 原地转向 ${stats.in_place_turn_segments} 段\n速度更新 ${stats.command_updates} 次（不等于停车次数）`:'')+(Number.isFinite(run.goal_error_m)?`\n结束时距目标 ${(run.goal_error_m*100).toFixed(1)} cm（定位估计）`:''));
 if(workspaceTab==='logs')document.dispatchEvent(new CustomEvent('navigation-action-trace',{detail:{samples:run.samples}}));
 for(const e of run.events){const b=document.createElement('button');b.className='motion-event';b.type='button';
  const turn=e.observed_yaw_change_deg,xy=e.start_xy;
  b.textContent=`${localTime(e.started_s).split(' ')[1]}　${e.label}\n(${xy[0].toFixed(2)}, ${xy[1].toFixed(2)}) m · ${e.duration_s.toFixed(1)} s · 实际航向 ${turn>=0?'左':'右'}偏 ${Math.abs(turn).toFixed(1)}°`;
  b.onclick=()=>{say('motion-detail',`动作 ${e.index}：${e.label}\n开始：${localTime(e.started_s)}\n结束：${localTime(e.ended_s)}\n起点：${e.start_xy.map(x=>x.toFixed(3)).join(', ')} m\n终点：${e.end_xy.map(x=>x.toFixed(3)).join(', ')} m\n定位航向变化：${turn.toFixed(2)}°（正左负右）\n两端位移：${e.endpoint_displacement_m.toFixed(3)} m\n最大指令：${e.max_vx_mps.toFixed(3)} m/s，${e.max_wz_rads.toFixed(3)} rad/s\n${e.commands} 次有界命令提交记录；RC 同时运动：${e.rc?'是':'否'}`);
   document.dispatchEvent(new CustomEvent('navigation-action-focus',{detail:{event:e,samples:run.samples.filter(p=>p.time_s>=e.started_s&&p.time_s<=e.ended_s)}}));};
  $('motion-events').append(b);
 }
}
async function loadHistory(){if(historyBusy)return;historyBusy=true;try{const d=await request('logs'),chosen=$('motion-run').value;history=d.runs;$('motion-run').replaceChildren();for(const r of history){const o=document.createElement('option');o.value=r.id;o.textContent=`${localTime(r.started_s)} · ${r.status}`;$('motion-run').append(o);}if(history.some(r=>r.id===chosen))$('motion-run').value=chosen;if(history.length)showHistory();else say('motion-summary','尚无真实行车记录。');}catch(e){say('motion-summary','日志读取失败：'+e.message);}finally{historyBusy=false;}}
$('motion-run').onchange=showHistory;$('motion-refresh').onclick=loadHistory;
$('motion-download').onclick=()=>{const r=history.find(r=>r.id===$('motion-run').value);if(!r)return;const a=document.createElement('a'),u=URL.createObjectURL(new Blob([JSON.stringify(r,null,2)],{type:'application/json'}));a.href=u;a.download='navigation-actions-'+r.id+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);};
loadHistory();setInterval(()=>{if(!document.hidden&&state?.busy)loadHistory();},10000);

// Move existing controls without replacing IDs, event handlers or safety gates.
function arrangeWorkspace(){
 const main=document.querySelector('.map-module[data-module="navigation"] > main'),aside=main.querySelector('aside'),article=main.querySelector('article');
 const originalSections=[...aside.children].filter(e=>e!==panel);
 const bar=document.createElement('div');bar.className='nav-commandbar';bar.setAttribute('aria-label','常用地图操作');
 const modeLabel=$('mode').closest('label'),radiusLabel=$('radius').closest('label');
 modeLabel.className='mode-control';radiusLabel.className='radius-control';
 radiusLabel.firstChild.textContent='安全包络（m）';
 $('mode').options[0].textContent='离线选点';$('mode').options[1].textContent='实时定位';
 bar.append(modeLabel,$('pick-pan'),$('pick-start'),$('pick-goal'),$('plan'),$('clear'),$('zoom-in'),$('zoom-out'),$('fit'),radiusLabel);
 const seedTools=document.createElement('details');seedTools.className='seed-tools';
 const summary=document.createElement('summary');summary.textContent='定位初始化';seedTools.append(summary);
 const pop=document.createElement('div');pop.className='seed-popover';
 pop.append($('seed-help'),$('yaw').closest('label'),$('seed'),$('seed-result'));seedTools.append(pop);bar.append(seedTools);
 main.before(bar);
 const tabs=document.createElement('div');tabs.className='workspace-tabs';tabs.setAttribute('role','tablist');tabs.setAttribute('aria-label','导航侧栏');
 const panes={};
 for(const [id,label] of [['control','实车控制'],['logs','动作日志'],['advanced','高级设置']]){
  const button=document.createElement('button');button.id='workspace-tab-'+id;button.textContent=label;button.type='button';button.setAttribute('role','tab');
  const pane=document.createElement('div');pane.id='workspace-pane-'+id;pane.className='workspace-pane';pane.setAttribute('role','tabpanel');pane.setAttribute('aria-labelledby',button.id);
  button.setAttribute('aria-controls',pane.id);panes[id]=pane;
  button.onclick=()=>{workspaceTab=id;for(const b of tabs.children){const on=b===button;b.classList.toggle('active',on);b.setAttribute('aria-selected',String(on));b.tabIndex=on?0:-1;}for(const [key,p] of Object.entries(panes))p.hidden=key!==id;
   if(id==='logs')showHistory();else document.dispatchEvent(new CustomEvent('navigation-action-trace',{detail:{samples:[]}}));};
  tabs.append(button);
 }
 tabs.onkeydown=e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const bs=[...tabs.children],i=bs.indexOf(document.activeElement);const j=e.key==='Home'?0:e.key==='End'?bs.length-1:(i+(e.key==='ArrowRight'?1:bs.length-1))%bs.length;bs[j].click();bs[j].focus();};
 const historyPanel=panel.querySelector('.motion-history');historyPanel.open=true;panes.logs.append(historyPanel);
 panes.control.append(panel);
 for(const section of originalSections)panes.advanced.append(section);
 const explanation=article.querySelector('.details');if(explanation)panes.advanced.append(explanation);
 aside.replaceChildren(tabs,...Object.values(panes));
 const toolbar=article.querySelector('.toolbar');
 const rawToggle=document.createElement('label');rawToggle.innerHTML='<input id="raw-route" type="checkbox">原始折线';toolbar.append(rawToggle);
 rawToggle.firstElementChild.onchange=()=>document.dispatchEvent(new Event('navigation-redraw'));
 const report=document.createElement('details');report.className='map-results map-popover';
 const reportTitle=document.createElement('summary');reportTitle.textContent='选点 / 规划结果';report.append(reportTitle);
 const reportBody=document.createElement('div');reportBody.className='route-summary map-popover-body';
 reportBody.append($('points'),$('result'),$('download'));report.append(reportBody);toolbar.append(report);
 // Show results on demand beside the map, without taking height from the canvas.
 new MutationObserver(()=>{const result=$('result').textContent;reportTitle.textContent=result.startsWith('未通过')?'规划未通过 · 查看':'选点 / 规划结果';if(/^(计算中|未通过|离线路线候选|基于新鲜定位的路线候选)/.test(result))report.open=true;}).observe($('result'),{childList:true,characterData:true,subtree:true});
 $('map').addEventListener('pointerdown',()=>{report.open=false;});
 const help=document.createElement('details');help.className='map-help map-popover';
 const helpTitle=document.createElement('summary');helpTitle.textContent='图例 / 操作';help.append(helpTitle);
 const helpBody=document.createElement('div');helpBody.className='map-popover-body';
 helpBody.append(article.querySelector('.legend'),article.querySelector('.hint'));help.append(helpBody);toolbar.append(help);
 const focus=document.createElement('button');focus.id='map-focus';focus.type='button';focus.textContent='专注地图';focus.setAttribute('aria-pressed','false');
 focus.onclick=()=>{const on=document.querySelector('.map-module').classList.toggle('map-focused');focus.textContent=on?'显示操作栏':'专注地图';focus.setAttribute('aria-pressed',String(on));};toolbar.append(focus);
 // Surface the full status text on hover even when a compact window truncates it.
 const liveStatus=$('live-status');new MutationObserver(()=>liveStatus.title=liveStatus.textContent).observe(liveStatus,{childList:true,characterData:true,subtree:true});
 document.querySelector('.map-module').classList.add('navigation-workspace');tabs.children[0].click();
 // Workbench shell injects a page title into main: explicit grid areas prevent it
 // from consuming a control/map slot. Keep the legend visible beside the canvas.
 main.classList.add('nav-layout');aside.classList.add('nav-controls');article.classList.add('nav-map-panel');
 const legend=$('map-legend');legend.textContent='浅绿：矩形车心可达　灰绿：已知空地、中心需离边界留距　橙色：障碍　深蓝：未知　蓝线：历史轨迹　黄线：规划';
 article.querySelector('.map-wrap').after(legend);
 $('map-tool-state').className='nav-tool-state';

}
arrangeWorkspace();
})();
