(()=>{
 const $=id=>document.getElementById(id),client=crypto.randomUUID?.()||('tab-'+Date.now()+'-'+Math.random().toString(36).slice(2));let signed=false,active=false,busy=false,media=false,epoch=0;
 const c={vx:0,vy:0,yaw:0,left:[0,0,0],right:[0,0.0561,0.2133],right_rpy:[0,0,0],left_rpy:[0,0,0],left_grip:0,right_grip:0};
 /* 底盘子模式（2026-10-24）：'a'=全向平移+自旋（互斥）；'b'=RC 遥控车（左油门/右转向，可同时）。
    与后端 SENDER.base_sub 同一份状态：VR 端 Y 键循环、网页「切换子模式」按钮都会改它，
    本页通过 /api/base_status 每秒同步一次。 */
 let baseSub='a';
 function applyBaseSub(sub){
  baseSub=(sub==='b')?'b':'a';const rc=baseSub==='b';
  const badge=$('base-sub-badge');if(badge)badge.textContent=rc?'RC 遥控车 · 左油门/右转向 · 松开回中':'全向平移+自旋 · 松开回中';
  const tog=$('base-sub-toggle');if(tog)tog.textContent='切换子模式（当前：'+(rc?'RC':'全向')+'）';
  const note=$('base-drive-note');if(note)note.textContent=rc
   ?'RC 遥控车子模式：左摇杆纵轴=油门（前后），右摇杆横轴=转向，可同时操作边走边转弯。'
   :'当前底盘平移优先：同时操作两个摇杆时只执行平移。转向前请先松开左摇杆。';
  const title=$('base-stick-title');if(title)title.textContent=rc?'左摇杆 · 油门':'左摇杆 · 平移';
  const hint=$('base-stick-hint');if(hint)hint.textContent=rc?'仅纵轴有效：前推前进、后拉倒退':'前后、左右与斜向移动';
  const ro=$('base-stick-readout-hint');if(ro)ro.innerHTML=rc
   ?'↑↓ 前进／后退<br>横向输入在 RC 子模式下无效<br>可与右摇杆转向同时进行'
   :'↑↓ 前进／后退<br>←→ 左右横移<br>斜向推动可斜向平移';
 }
 let safetyEpoch=null,globalStopped=true,operationEpoch=0,stopLocalBase=()=>{},serverRightActive=false,serverLeftActive=false;
 /* 左右网页/VR/关节直驱的 XYZ 均为底盘系 J5 中心。
    默认目标由水平构型 FK+标定修正动态算出，标定更新后自动跟随。 */
 function rightDefaultJ5(){return j5Pos(RIGHT_DEFAULT_DEG.map(v=>v*Math.PI/180),'right');}
 function leftDefaultJ5(){return j5Pos(LQINIT.map(v=>v*Math.PI/180),'left');}
 const ARMSL=[['srx','right',0,1],['sry','right',1,1],['srz','right',2,1],
              ['srroll','right_rpy',0,1],['srpitch','right_rpy',1,1],['sryaw','right_rpy',2,1],
              ['srg','right_grip',null,1]];
 function sliderSync(){for(const [id,key,idx,sgn] of ARMSL){const el=$(id);if(!el)continue;const v=(idx===null?c[key]:c[key][idx])*(sgn||1);el.value=v;const o=$(id+'-v');if(o)o.textContent=key==='right_rpy'?v.toFixed(1)+'°':key.endsWith('grip')?v.toFixed(2):v.toFixed(3);}$('sjg').value=c.right_grip*100;$('sjg-v').textContent=Math.round(c.right_grip*100)+'%';}
 const RIGHT_DEFAULT_DEG=[-40,92,-49,-58.6866,-55.5593,37.7190];
 let rightEntering=false,rightPushBusy=false;
 const OFF=[0,0,0];   /* 底盘中心在机械臂底座系下的坐标（米），与后端 arm_console.py 同步 */
 const FR=[[0,-1,0],[1,0,0],[0,0,1]];
 const _rt=(x,y,z,r,p,yy)=>{const cr=Math.cos(r),sr=Math.sin(r),cp=Math.cos(p),sp=Math.sin(p),cy=Math.cos(yy),sy=Math.sin(yy);
   const Rx=[[1,0,0],[0,cr,-sr],[0,sr,cr]],Ry=[[cp,0,sp],[0,1,0],[-sp,0,cp]],Rz=[[cy,-sy,0],[sy,cy,0],[0,0,1]];
   const m=(a,b)=>a.map((row,i)=>b[0].map((_,j)=>row[0]*b[0][j]+row[1]*b[1][j]+row[2]*b[2][j]));
   return {R:m(m(Rz,Ry),Rx),t:[x,y,z]};};
 const DTF=[_rt(0,0,0.123,0,0,0),_rt(0,0,0,Math.PI/2,-0.1359,-Math.PI),_rt(0.28503,0,0,0,0,-1.7939),_rt(-0.021984,-0.25075,0,Math.PI/2,0,0),_rt(0,0,0,-Math.PI/2,0,0),_rt(0,-0.091,0,Math.PI/2,0,0)];
 const BASE={R:[[1,0,0],[0,1,0],[0,0,1]],t:[0,0,0]};
 const mm=(a,b)=>a.map((row,i)=>b[0].map((_,j)=>row[0]*b[0][j]+row[1]*b[1][j]+row[2]*b[2][j]));
 const mv=(a,v)=>[a[0][0]*v[0]+a[0][1]*v[1]+a[0][2]*v[2],a[1][0]*v[0]+a[1][1]*v[1]+a[1][2]*v[2],a[2][0]*v[0]+a[2][1]*v[1]+a[2][2]*v[2]];
 const TLO=[-0.5,-0.1,-0.25],THI=[0.5,0.55,0.6];
 /* 标定修正（2026-10-25）：与后端 arm_console.py CALIB/_calib_tcp_from_fk 逐字同式。
    对外位置一律为测量点（TCP，两指根转轴连线中点）；s=0 时逐字等价旧法兰行为。
    原值由 /api/status 的 control.calib 下发（conStatus 每 3s 刷新），默认恒等。 */
 const CALIB={right:{t:[0,0,0],yaw:0,s:0},left:{t:[0,0,0],yaw:0,s:0}};
 function fkPose(q){let R=BASE.R,t=BASE.t;for(let i=0;i<6;i++){const tt=mv(R,DTF[i].t);t=[t[0]+tt[0],t[1]+tt[1],t[2]+tt[2]];R=mm(mm(R,DTF[i].R),_rt(0,0,0,0,0,q[i]).R);}return[mv(FR,t),R];}
 function fkPos(q){return fkPose(q)[0];}
 function tcpPos(q,side){
  const [f,R]=fkPose(q),cb=CALIB[side]||{t:[0,0,0],yaw:0,s:0};
  const cw=Math.cos(cb.yaw),sw=Math.sin(cb.yaw);
  let p=[cw*f[0]-sw*f[1]+cb.t[0],sw*f[0]+cw*f[1]+cb.t[1],f[2]+cb.t[2]];
  if(cb.s){const a=mv(FR,[R[0][2],R[1][2],R[2][2]]);
   p=[p[0]+cb.s*(cw*a[0]-sw*a[1]),p[1]+cb.s*(sw*a[0]+cw*a[1]),p[2]+cb.s*a[2]];}
  return[p[0]-OFF[0],p[1]-OFF[1],p[2]-OFF[2]];
 }
 function j5Pos(q,side){
  /* fkAll 已转换到底盘系；此处只叠加安装标定，不能重复减 OFF。 */
  const p=fkAll(q)[5],cb=CALIB[side]||{t:[0,0,0],yaw:0,s:0},cw=Math.cos(cb.yaw),sw=Math.sin(cb.yaw);
  return[cw*p[0]-sw*p[1]+cb.t[0],sw*p[0]+cw*p[1]+cb.t[1],p[2]+cb.t[2]];
 }
 function rightDegrees(){return Array.from({length:6},(_,i)=>Number($('sj'+(i+1)).value));}
 function rightControls(){return $('panel-joint').hidden?{mode:'right_ee',right:c.right.slice(),right_rpy_deg:c.right_rpy.slice(),right_grip:c.right_grip}:{mode:'right_joints',right_joints_deg:rightDegrees(),right_grip:c.right_grip};}
 function jointUpdate(){const degrees=rightDegrees(),q=degrees.map(v=>v*Math.PI/180);
  degrees.forEach((v,i)=>$('sj'+(i+1)+'-v').textContent=v.toFixed(1)+'°');
  c.right=j5Pos(q,'right');sliderSync();readings();a3q=q;a3tgt=c.right.slice();a3tgtPoint='j5';a3draw();}
 async function rightPush(){if(!follow||vrOn||globalStopped||rightEntering||rightPushBusy)return;rightPushBusy=true;
  try{const d=await conReq('/api/control',{action:'update',client,controls:armControls('right')});showEntry(d);if(!d.active){follow=false;syncDefaultButtons();}}
  catch(e){follow=false;conLog('更新失败：'+e.message);syncDefaultButtons();}finally{rightPushBusy=false;}}
 for(let i=1;i<=6;i++){const el=$('sj'+i);if(el){el.oninput=()=>{jointUpdate();rightPush();};el.onchange=rightPush;}}
 $('sjg').oninput=e=>{c.right_grip=Number(e.target.value)/100;sliderSync();readings();rightPush();};
 function setMode(joint){if(rightEntering)return;$('panel-ee').hidden=joint;$('panel-joint').hidden=!joint;
   $('mode-ee').className='button '+(joint?'secondary':'primary')+' sim-mode-btn';
   $('mode-joint').className='button '+(joint?'primary':'secondary')+' sim-mode-btn';}
 $('mode-ee').onclick=()=>setMode(false);$('mode-joint').onclick=()=>setMode(true);
 async function request(path,data){const r=await fetch('/api/v1/'+path,{method:data?'POST':'GET',cache:'no-store',headers:data?{'Content-Type':'application/json','X-Hub-Client':'console'}:{},body:data?JSON.stringify(data):undefined});const d=await r.json();if(!r.ok)throw Error(d.error||'请求失败');return d;}
 const payload=()=>({client,controls:c});
 function readings(){const h=$('hand').value;$('base-value').textContent=`X ${c.vx.toFixed(2)} · Y ${c.vy.toFixed(2)} m/s`;$('yaw-value').textContent=c.yaw.toFixed(2)+' rad/s';$('hand-value').textContent=c[h].map((v,i)=>'XYZ'[i]+' '+v.toFixed(3)).join(' · ')+' m';}
 function frame(d){if(d.hex)$('frame-hex').textContent=d.hex;if(d.decoded)$('frame-json').textContent=JSON.stringify(d.decoded,null,2);}
 function status(d){active=!!d.active&&!!d.owned;$('start').disabled=!signed||!!d.active;$('stop').disabled=!active;$('sent').textContent=d.sent||0;$('remaining').textContent=d.remaining?d.remaining+' s':'—';$('send-state').textContent=active?'正在发送无使能帧 · 20 Hz · mask=0':d.active?'另一个页面正在联调':d.reason||'仅预览 · 未发送';frame(d);}
 function stop(){epoch++;active=false;$('stop').disabled=true;if(signed){request('simulator/stop',payload()).then(status).catch(e=>{$('send-state').textContent=e.message;});}$('start').disabled=!signed;}
 function reset(){Object.assign(c,{vx:0,vy:0,yaw:0,left:[0,0,0],right:rightDefaultJ5(),right_rpy:[0,0,0],left_rpy:[0,0,0],left_grip:0,right_grip:0});for(const id of ['yaw','height','grip'])$(id).value=0;for(let i=1;i<=6;i++){const el=$('sj'+i);if(el){el.value=RIGHT_DEFAULT_DEG[i-1];const o=$('sj'+i+'-v');if(o)o.textContent=RIGHT_DEFAULT_DEG[i-1].toFixed(1)+'°';}}a3tgt=c.right.slice();a3tgtPoint='j5';a3draw();document.querySelectorAll('.stick-knob').forEach(n=>n.style.transform='translate(-50%,-50%)');sliderSync();readings();}
 function joystick(id,fn,horizontal=false){
  const box=$(id),knob=box.querySelector('.stick-knob');let pointer=null;
  const move=(x,y)=>{if(horizontal)y=0;const l=Math.hypot(x,y);if(l>1){x/=l;y/=l;}knob.style.transform=`translate(calc(-50% + ${x*48}px),calc(-50% + ${y*48}px))`;fn(-y,-x);readings();};
  const center=()=>{pointer=null;move(0,0);};
  box.onpointerdown=e=>{if(e.button!==0||pointer!==null)return;e.preventDefault();pointer=e.pointerId;box.setPointerCapture(pointer);box.focus();update(e);};
  function update(e){if(pointer!==e.pointerId)return;const b=box.getBoundingClientRect();move((e.clientX-b.left-b.width/2)/(b.width*.35),(e.clientY-b.top-b.height/2)/(b.height*.35));}
  box.onpointermove=update;box.onpointerup=box.onpointercancel=box.onlostpointercapture=center;
  box.onkeydown=e=>{const keys=horizontal?{ArrowLeft:[-1,0],ArrowRight:[1,0]}:{ArrowUp:[0,-1],ArrowDown:[0,1],ArrowLeft:[-1,0],ArrowRight:[1,0]};if(keys[e.key]){e.preventDefault();move(...keys[e.key]);}};
  box.onkeyup=e=>{if(e.key.startsWith('Arrow'))center();};box.onblur=center;return center;
 }
 const centerBase=joystick('base-stick',(x,y)=>{c.vx=x*.3;c.vy=(baseSub==='b'?0:y*.3);});
 function setYaw(value){c.yaw=value;$('yaw').value=value;$('base-turn-stick').querySelector('.stick-knob').style.transform=`translate(calc(-50% + ${-value/.5*48}px),-50%)`;readings();}
 const centerTurn=joystick('base-turn-stick',(_,turn)=>setYaw(turn*.5),true);
 joystick('hand-stick',(x,y)=>{const h=$('hand').value,n=h==='right'?rightDefaultJ5():leftDefaultJ5();c[h][0]=x*.15;c[h][1]=n[1]+y*.15;sliderSync();});
 $('yaw').oninput=e=>setYaw(Number(e.target.value));for(const event of ['pointerup','pointercancel','blur'])$('yaw').addEventListener(event,centerTurn);
 $('height').oninput=e=>{const h=$('hand').value,n=h==='right'?rightDefaultJ5():leftDefaultJ5();c[h][2]=n[2]+Number(e.target.value);sliderSync();readings();};$('grip').oninput=e=>{c[$('hand').value+'_grip']=Number(e.target.value);sliderSync();};
 $('hand').onchange=()=>{$('height').value=c[$('hand').value][2];$('grip').value=c[$('hand').value+'_grip'];readings();};$('grip-open').onclick=()=>{c[$('hand').value+'_grip']=0;$('grip').value=0;sliderSync();};$('grip-close').onclick=()=>{c[$('hand').value+'_grip']=1;$('grip').value=1;sliderSync();};$('reset').onclick=reset;
 for(const [id,key,idx,sgn] of ARMSL){const el=$(id);if(el)el.oninput=e=>{const v=Number(e.target.value)*(sgn||1);if(idx===null)c[key]=v;else c[key][idx]=v;sliderSync();readings();};}
 $('arm-zero').onclick=()=>{if(defaultBlocked('right'))return; c.right=rightDefaultJ5();c.right_rpy=[0,0,-5];c.right_grip=0;[-40,92,-49,-58.6866,-55.5593,37.7190].forEach((deg,i)=>{const el=$('sj'+(i+1));if(el)el.value=deg;const o=$('sj'+(i+1)+'-v');if(o)o.textContent=deg.toFixed(1)+'°';});sliderSync();readings();a3q=[-40,92,-49,-58.6866,-55.5593,37.7190].map(v=>v*Math.PI/180);a3tgt=c.right.slice();a3tgtPoint='j5';a3draw();setMode(false);conLog('默认目标已设置，仅修改输入；开始跟随后才会下发。');};
 $('start').onclick=async()=>{if(!signed)return;$('start').disabled=true;const stamp=epoch;try{const d=await request('simulator/start',payload());if(stamp!==epoch){stop();return;}status(d);}catch(e){$('send-state').textContent=e.message;$('start').disabled=false;}};$('stop').onclick=stop;
 function attachMedia(){/* 相机与雷达已在独立感知页展示，本页不重复加载。 */}
 $('login').onclick=()=>$('sim-login').showModal();$('login-cancel').onclick=()=>$('sim-login').close();$('login-form').onsubmit=async e=>{e.preventDefault();try{await request('login',{username:$('username').value,password:$('password').value});$('password').value='';signed=true;$('sim-login').close();$('login').textContent='AIPC · 已登录';$('start').disabled=false;attachMedia();}catch(error){$('login-error').textContent=error.message;}};
 async function tick(){if(signed&&!busy&&!document.hidden){busy=true;const stamp=epoch;try{const d=await request('simulator/'+(active?'update':'preview'),payload());if(stamp===epoch){if(active)status(d);else frame(d);}}catch(e){active=false;$('start').disabled=false;$('send-state').textContent=e.message;}finally{busy=false;}}setTimeout(tick,200);}
 addEventListener('blur',()=>{reset();if(active)stop();});document.addEventListener('visibilitychange',()=>{if(document.hidden){reset();stop();}});addEventListener('pagehide',()=>{active=false;fetch('/api/v1/simulator/stop',{method:'POST',headers:{'Content-Type':'application/json','X-Hub-Client':'console'},body:JSON.stringify(payload()),keepalive:true}).catch(()=>{});});
 /* 真机控制台（2026-10-17 v4）：独立服务 http://<aipc>:8092，管理通道 SSH→KR260，数据通道 v2 0xFCFC。 */
 const CON=`http://${location.hostname}:8092`;let follow=false,vrOn=false,conBusy=false,autoBusy=false;
 async function conReq(path,data){const stamp=operationEpoch;const body=data?{...data,safety_epoch:safetyEpoch}:undefined;const r=await fetch(CON+path,{method:data?'POST':'GET',cache:'no-store',headers:data?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});const d=await r.json();if(!r.ok||d.ok===false)throw Error(d.error||'控制台请求失败');if(data&&stamp!==operationEpoch&&!['/api/stop_all','/api/resume'].includes(path))throw Error('操作已被全局停止取消');return d;}
 /* 双臂坐标规划：预检与执行严格分离；目标变化、停止或 60 秒超时均作废旧预检。 */
 const vlaInvalidateAll=[];
 function setupVlaPlanner(side){
  const suffix=side==='right'?'-right':'',prefix='vla-',ids=['x','y','z'].map(x=>prefix+x+suffix);
  const label=side==='right'?'右臂':'左臂';let busy=false,approved=null,targetMode='manual';
  const xyz=()=>ids.map(id=>Number($(id).value));
  function invalidate(message){approved=null;$('vla-execute'+suffix).disabled=true;window.PlannerTrajectory?.clear(side);if(message)$('vla-plan-result'+suffix).textContent=message;}
  function result(text,bad=false){const el=$('vla-plan-result'+suffix);el.textContent=text;el.dataset.state=bad?'error':'ok';}
  async function preview(){
   if(busy)return;if(globalStopped||safetyEpoch===null){result('软件停止已锁定或控制状态未就绪，不能规划。',true);return;}
   if(!xyz().every(Number.isFinite)){invalidate('坐标必须为三个有限数值，请检查后重试。');return;}
   busy=true;invalidate();$('vla-preview'+suffix).disabled=true;result('正在读取双臂真实反馈并检查可达性、碰撞与轨迹，请等待…');
   const target=xyz(),stamp=operationEpoch,mode=targetMode;
   try{
    await collectStage('planning_pregrasp');
    const d=await conReq('/api/vla_motion_execute',{stage:'preview',side,xyz:target,collision_mode:'exact',pregrasp:mode==='pregrasp'});
    await collectStage('pregrasp_ready');
    if(stamp!==operationEpoch||target.some((v,i)=>v!==xyz()[i]))throw Error('目标或控制状态已变化，本次预检已作废');
    window.PlannerTrajectory.show(d,side);
    const executable=d.execution_allowed!==false;approved=executable?{xyz:target,at:Date.now(),moveKey:JSON.stringify(target),mode}:null;$('vla-execute'+suffix).disabled=!executable;
    const margin=Number(d.minimum_mesh_clearance_cm),duration=Number(d.duration_s),maxVelocity=Number(d.max_joint_velocity_rad_s);
    result(`预检通过 · 位移 ${(Number(d.displacement_norm_m)*1000).toFixed(1)} mm · 轨迹 ${duration.toFixed(2)} s · 最小网格余量 ${Number.isFinite(margin)?margin.toFixed(2)+' cm':'见规划结果'} · 最大关节速度 ${maxVelocity.toFixed(3)} rad/s。${executable?'确认机械臂周围安全后，60 秒内可执行。':'暂不允许执行：超过 30 秒或 0.50 rad/s 网页执行上限，仅供轨迹预览。'}`,!executable);
   }catch(e){invalidate();result('预检未通过：'+e.message,true);}finally{busy=false;$('vla-preview'+suffix).disabled=false;}
  }
  async function execute(){
   if(busy||!approved)return;if(Date.now()-approved.at>60000){invalidate('预检已超过 60 秒，请重新预检。');return;}
   const current=approved;if(JSON.stringify(xyz())!==current.moveKey){invalidate('目标已改变，请重新预检。');return;}
   if(!confirm(`确认执行${label}坐标运动？\nJ5 目标：${current.xyz.map(v=>v.toFixed(3)).join(', ')} m\n将按预检轨迹运动，另一臂保持固定。请确保周围安全并靠近实体急停。`))return;
   busy=true;$('vla-preview'+suffix).disabled=$('vla-execute'+suffix).disabled=true;result('正在复核真实反馈并提交轨迹…');
   try{await collectStage('moving_to_pregrasp');const d=await conReq('/api/vla_motion_execute',{stage:'execute',side,xyz:current.xyz,collision_mode:'exact',pregrasp:current.mode==='pregrasp'});approved=null;result(`已接受执行 · 动作号 ${d.move_seq} · 预计 ${Number(d.duration_s).toFixed(2)} s。完成后才可启动其他动作。`);if(side==='left'){llog('✓ 左臂坐标规划已提交：'+current.xyz.join(', ')+' m');lpoll();}else{conLog('✓ 右臂坐标规划已提交：'+current.xyz.join(', ')+' m');poll();}}
   catch(e){approved=null;result('执行未提交：'+e.message+'。如需继续，请重新预检。',true);}finally{busy=false;$('vla-preview'+suffix).disabled=false;}
  }
  $('vla-preview'+suffix).onclick=preview;$('vla-execute'+suffix).onclick=execute;
  for(const id of ids)$(id).addEventListener('input',()=>{targetMode='manual';invalidate('目标已修改，请重新执行规划预检。');});
  $('vla-use-current'+suffix).onclick=async()=>{if(busy)return;try{const d=await conReq('/api/status');const p=d.control&&d.control[side]&&d.control[side].target;if(!Array.isArray(p))throw Error('没有可用的 J5 坐标');ids.forEach((id,i)=>$(id).value=Number(p[i]).toFixed(4));targetMode='manual';invalidate('已填入当前控制目标 J5；执行前请重新预检。');}catch(e){result('读取失败：'+e.message,true);}};
  $('vla-grasp-target'+suffix).onclick=async()=>{if(busy)return;busy=true;const button=$('vla-grasp-target'+suffix);button.disabled=true;result('正在读取实时识别目标并换算预抓 J5…');try{await collectStage('detecting_target');const d=await conReq('/api/grasp_target_preview',{side});await collectStage('target_ready');if(!Array.isArray(d.xyz)||d.xyz.length!==3)throw Error('目标接口未返回有效 J5 坐标');ids.forEach((id,i)=>$(id).value=Number(d.xyz[i]).toFixed(4));targetMode='pregrasp';invalidate();const confidence=Number(d.confidence);result(`已获取 ${d.label} · ${d.source_frame} → ${label} J5 · 水平预抓后退 ${(Number(d.target.pregrasp_retreat_m)*1000).toFixed(0)} mm、左移 10 mm${Number.isFinite(confidence)?' · 置信度 '+confidence.toFixed(2):''}。候选外参，仅填充坐标，请继续规划预检。`);}catch(e){result('获取目标失败：'+e.message,true);}finally{busy=false;button.disabled=false;}};
  vlaInvalidateAll.push(invalidate);
 }
 setupVlaPlanner('left');setupVlaPlanner('right');
 /* 左臂水平夹取试验：识别点修正 → 水平接近 → 末段闭合 → 水平后退。
    每段独立精确预检并等待真实到位；不把 HTTP 受理当成运动完成。 */
 let cupGraspBusy=false,collectBusy=false;
 async function collectSample(phase){
  if(collectBusy)return;collectBusy=true;
  const output=$('collect-status'),buttons=[$('collect-before'),$('collect-after')];buttons.forEach(b=>b.disabled=true);
  try{const sample=$('collect-sample').value.trim(),starting=phase==='before';
   output.textContent=starting?'正在启动连续采集并识别杯子…':'正在停止并整理时序数据…';
   const d=await conReq('/api/vla_dataset',starting?{action:'start',sample}:{action:'stop',result:$('collect-result').value});
   if(starting){output.textContent='● 正在连续采集 '+sample+' · 数据仅保存在 AIPC';}
   else{const m=d.manifest;output.textContent=`✓ 已保存 ${m.sample} · ${m.frames} 帧 · ${m.result} · ${d.directory}`;$('collect-sample').value=sample.replace(/(\d+)(?!.*\d)/,x=>String(Number(x)+1).padStart(x.length,'0'));}
  }catch(e){output.textContent='采集失败：'+e.message;}
  finally{collectBusy=false;buttons.forEach(b=>b.disabled=false);}
 }
 async function collectStage(stage){try{await conReq('/api/vla_dataset',{action:'stage',stage});}catch(e){console.warn('采集阶段记录失败',e);}}
 $('collect-before').onclick=()=>collectSample('before');$('collect-after').onclick=()=>collectSample('after');
 $('cup-gripper-open').onclick=async()=>{
  if(cupGraspBusy)return;
  const button=$('cup-gripper-open'),output=$('vla-plan-result');button.disabled=true;
  try{await conReq('/api/intent',{intent:'gripper',side:'left',open:1.0});output.textContent='左夹爪张开命令已接受；关节保持不动。';output.dataset.state='ok';}
  catch(e){output.textContent='张开夹爪失败：'+e.message;output.dataset.state='error';}
  finally{button.disabled=false;}
 };
 $('cup-grasp-test').onclick=async()=>{
  if(cupGraspBusy)return;
  const output=$('vla-plan-result'),button=$('cup-grasp-test');
  const say=(text,bad=false)=>{output.textContent=text;output.dataset.state=bad?'error':'ok';};
  const base=['vla-x','vla-y','vla-z'].map(id=>Number($(id).value));
  if(!base.every(Number.isFinite)){say('请先获取或填写有效的识别预抓 J5 坐标。',true);return;}
  if(globalStopped||safetyEpoch===null){say('软件停止已锁定或控制状态未就绪，不能夹取。',true);return;}
  const grasp=[base[0],base[1]+0.06,base[2]],lift=[grasp[0],grasp[1],grasp[2]+0.02];
  if(!confirm(`确认执行左臂水平夹取测试？\n水平向前 6 cm，到位后闭合夹爪；等待 1.2 秒后向上抬升 2 cm。\n接近后 J5：${grasp.map(v=>v.toFixed(3)).join(', ')} m\n每段都会重新预检并等待到位。请确保周围安全并靠近实体急停。`))return;
  await collectStage('pregrasp_reached');
  cupGraspBusy=true;button.disabled=true;vlaInvalidateAll.forEach(fn=>fn());
  const sleep=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  async function move(target,label,closeAtTarget=false,closeAtStart=false){
   await collectStage(label.includes('向前')?'approaching':label.includes('抬升')?'lifting':label);
   say(label+'：正在精确预检…');
   const checked=await conReq('/api/vla_motion_execute',{stage:'preview',side:'left',xyz:target,collision_mode:'exact',nearest_orientation:true});
   if(checked.execution_allowed===false)throw Error(label+'轨迹超过网页执行上限');
   const accepted=await conReq('/api/vla_motion_execute',{stage:'execute',side:'left',xyz:target,collision_mode:'exact',nearest_orientation:true});
   const seq=accepted.move_seq;let closed=false;
   if(closeAtStart){await conReq('/api/intent',{intent:'gripper',side:'left',open:0.0});closed=true;say('后退动作已启动：夹爪闭合并保持…');}
   for(let elapsed=0;elapsed<180000;elapsed+=200){
    if(globalStopped)throw Error('全局停止，流程已中断');
    const status=await conReq('/api/status'),result=status.control&&status.control.move_result&&status.control.move_result.left;
    if(closeAtTarget&&!closed&&elapsed>=Number(accepted.duration_s)*750){
     await conReq('/api/intent',{intent:'gripper',side:'left',open:0.0});closed=true;say('接近末段：夹爪闭合，等待到位并稳定…');
    }
    if(result&&result.seq===seq){
     if(result.state==='failed')throw Error(label+'失败：'+result.message);
     if(result.state==='done')return;
    }
    await sleep(200);
   }
   throw Error(label+'等待到位超时');
  }
  async function waitIdle(){
   for(let elapsed=0;elapsed<10000;elapsed+=100){
    const status=await conReq('/api/status');
    if(status.control&&status.control.left&&status.control.left.active===false)return;
    await sleep(100);
   }
   throw Error('上一动作会话未及时释放');
  }
  try{
   await move(grasp,'① 向前 6 cm',true);
   await waitIdle();
   await collectStage('closing_gripper');
   say('② 原地保持：闭合夹爪…');
   await conReq('/api/intent',{intent:'gripper',side:'left',open:0.0});
   await collectStage('holding');
   await sleep(1200);
   await waitIdle();
   await move(lift,'③ 向上抬升 2 cm');
   say('夹取测试流程已到位结束：夹爪保持闭合。请检查是否实际夹稳；识别与夹取精度仍需现场验收。');
   llog('✓ 左臂水平夹取测试两阶段已到位结束');
  }catch(e){say('夹取测试中断：'+e.message,true);llog('✗ 夹取测试中断：'+e.message);}
  finally{cupGraspBusy=false;button.disabled=false;}
 };
 /* 日志：左右臂共用一份实现（2026-10-22 统一 UI）。
   以前右臂 conLog 是"整段替换、无时间戳"，左臂 llog 是"带时间戳追加"，
   同一次操作两边显示风格不同。现在都走 appendLog。 */
 const LOG_MAX_LINES=400;
 const lastLog={};
 function appendLog(id,msg){
  const el=$(id);if(!el)return;
  msg=String(msg==null?'':msg);
  /* 1.5 秒内同一句不重复刷屏（轮询类重复写入会淹没日志）；
     但同一条消息隔一会儿再出现是合法的，必须照写。 */
  const now=Date.now();
  if(lastLog[id]&&lastLog[id].msg===msg&&now-lastLog[id].at<1500)return;
  lastLog[id]={msg,at:now};
  const stamp='['+new Date().toLocaleTimeString()+'] ';
  let text=stamp+msg+'\n'+el.textContent;
  const lines=text.split('\n');
  if(lines.length>LOG_MAX_LINES)text=lines.slice(0,LOG_MAX_LINES).join('\n');
  el.textContent=text;el.scrollTop=0;
 }
 function conLog(t){appendLog('con-log',t);}
 /* 中止原因回显（2026-10-22 v39）：后端 control.error 保留上次中止/停止原因，
    以前页面只显示“已停止/本页发送已停止”，使用者无法判断是心跳过期还是反馈过期。 */
 const lastAbort={con:null,lcon:null};
 function reportAbort(reason,which,latched){
  if(!reason||reason===lastAbort[which])return;
  lastAbort[which]=reason;
  const el=$(which==='lcon'?'llog':'con-log');if(!el)return;
  let msg=null;
  if(/中止/.test(reason)){
   const hint=/心跳/.test(reason)?'页面每 200ms 的心跳断了（切窗口、最小化、失焦或网络抖动都会触发；失焦即停是设计行为）'
             :/反馈过期/.test(reason)?'SSH 读一次关节反馈超过 2s 新鲜度门槛'
             :/deploy/.test(reason)?'KR260 上的控制程序没在运行'
             :'';
   const latch=latched===true?'已锁存全局软件停止，需先点「解除软件停止」'
              :latched===false?'未锁存，可直接重试':'';
   msg='⚠ 上次中止原因：'+reason+(hint?('\n   '+hint):'')+(latch?('\n   '+latch):'');
  } else if(/已完成|已到位/.test(reason)){
   /* 定点移动成功后会释放会话；页面以前只显示“未开始”，
      使用者以为滑块坏了（2026-10-22 反馈）。明确告知后续动作。 */
   msg='✓ '+reason+'\n   会话已释放：拖滑块只改预览；要真正下发请按「开始跟随」';
  } else return;   /* 其它普通状态不刷屏 */
  appendLog(which==='lcon'?'llog':'con-log',msg);
 }
 async function managementAction(action,label,log){if(conBusy){log('已有管理操作进行中，请等待结果。');return false;}conBusy=true;syncDefaultButtons();log(label+' 执行中…');try{const d=await conReq('/api/action',{action});log('✓ '+label+'\n'+(d.output||''));conStatus();lpoll();return true;}catch(e){log('✗ '+label+'：'+e.message+'；后续步骤未执行。');return false;}finally{conBusy=false;syncDefaultButtons();}}
 async function conAction(action,label){return managementAction(action,label,conLog);}
 function defaultBlocked(side){return conBusy||(side==='left'?(lactive||lvrOn||serverLeftActive):(follow||vrOn||serverRightActive));}
 function syncDefaultButtons(){
  $('arm-zero').disabled=$('arm-zpose').disabled=defaultBlocked('right');$('larm-zero').disabled=$('larm-zpose').disabled=defaultBlocked('left');
  for(const id of ['con-prepare','con-enable','con-start','con-exit-teach','lcon-prepare','lcon-enable','lcon-start','lcon-exit-teach'])$(id).disabled=globalStopped||safetyEpoch===null||conBusy||defaultBlocked(id.charAt(0)==='l'?'left':'right');
  /* 取消使能是安全动作：软件停止锁存时仍应可用，只受管理动作进行中限制 */
  for(const id of ['con-disable','lcon-disable'])$(id).disabled=conBusy;
  const locked=globalStopped||safetyEpoch===null;   /* 软件停止锁存 / 状态未就绪时一律不可点 */
  $('con-move-start').disabled=$('con-move-zero').disabled=locked||defaultBlocked('right');
  $('lcon-move-start').disabled=$('lcon-move-zero').disabled=locked||defaultBlocked('left');
  $('follow-start').disabled=$('vr-start').disabled=globalStopped||follow||vrOn||conBusy;
  $('lbtn-start').disabled=$('lvr-start').disabled=globalStopped||lactive||lvrOn||conBusy;
  /* 一键启动：锁存/未就绪/已有会话进行中 时不可点（避免重复跑整条流程） */
  $('auto-vr').disabled=!!(autoBusy||globalStopped||safetyEpoch===null||conBusy
                           ||follow||vrOn||lactive||lvrOn);
  /* 一键返回零位：VR 跟随进行中正是它的用途，所以**不**因会话存在而禁用 */
  $('auto-zero').disabled=!!(autoBusy||globalStopped||safetyEpoch===null||conBusy||follow||lactive);
 }
 function clearLocalMotion(){
  follow=vrOn=lactive=lvrOn=false;serverRightActive=serverLeftActive=false;stopLocalBase();vlaInvalidateAll.forEach(invalidate=>invalidate());
  /* 停止是最高优先级安全操作：不因本地状态、刷新或全局锁存而禁用。 */
  for(const id of ['follow-stop','vr-stop','lbtn-stop','lvr-stop'])$(id).disabled=false;
  $('con-follow').textContent=$('lst-state').textContent='本页发送已停止';
 }
 function applySafety(d){
  if(safetyEpoch!==null&&safetyEpoch!==d.epoch){operationEpoch++;clearLocalMotion();}
  safetyEpoch=d.epoch;globalStopped=!!d.stopped;
  if(globalStopped)clearLocalMotion();
  $('software-stop-state').textContent=d.pending?'停止处理中 · 新运动指令已封锁':globalStopped?'软件停止已锁定':'实车控制 · 操作会驱动设备';
  $('resume-control').disabled=!globalStopped||!!d.pending;
  $('stop-all-result').textContent=Object.entries(d.results||{}).map(([k,v])=>(k==='base'?'底盘：':'双臂／VR：')+v).join('\n')||'软件停止不等同于实体急停；执行结果会分通道显示。';
  syncDefaultButtons();
 }
 let safetyBusy=false;
 async function pollSafety(){if(safetyBusy)return;safetyBusy=true;const stamp=operationEpoch;try{const d=await conReq('/api/safety');if(stamp===operationEpoch)applySafety(d);}catch(e){$('software-stop-state').textContent='控制状态未知：'+e.message;globalStopped=true;clearLocalMotion();syncDefaultButtons();}finally{safetyBusy=false;}}
 $('stop-all').onclick=async()=>{
  operationEpoch++;globalStopped=true;clearLocalMotion();syncDefaultButtons();
  $('stop-results').open=true;
  $('software-stop-state').textContent='正在请求全部停止';$('resume-control').disabled=true;
  try{applySafety(await conReq('/api/stop_all',{}));}catch(e){$('stop-all-result').textContent='停止请求失败，无法确认设备停车：'+e.message+'。请使用实体急停。';}
 };
 $('resume-control').onclick=async()=>{operationEpoch++;clearLocalMotion();try{applySafety(await conReq('/api/resume',{}));}catch(e){$('stop-all-result').textContent=e.message;}};
 function showEntry(d){
  const stages=d.entry||{};rightEntering=!!stages.right;for(const id of ['mode-ee','mode-joint'])$(id).disabled=rightEntering;
  for(const side of ['right','left']){
   const stage=stages[side],ids=side==='right'?['srx','sry','srz','srroll','srpitch','sryaw','srg','sjg','sj1','sj2','sj3','sj4','sj5','sj6']:['llx','lly','llz','llroll','llpitch','llyaw','llg','lgrip','lj1','lj2','lj3','lj4','lj5','lj6'];
   for(const id of ids)$(id).disabled=!!stage;
   if(stage)$(side==='right'?'con-follow':'lst-state').textContent=stage.message;
  }
 }
 async function conStatus(){try{const d=await conReq('/api/status');$('con-can').textContent=d.can2;$('con-deploy').textContent=d.deploy==='STOPPED'?'未运行':'运行中(pid '+d.deploy+')';const ct=d.control;$('vr-scale').textContent='倍率 ×'+Number(ct.vr_motion_scale==null?1:ct.vr_motion_scale);if(ct.calib){for(const sd of ['right','left'])if(ct.calib[sd])CALIB[sd]=ct.calib[sd];}showEntry(ct);serverRightActive=!!ct.active;syncDefaultButtons();reportAbort(ct.error,'con',d.safety&&d.safety.stopped);$('con-follow').textContent=ct.active?(ct.reason||'发送中'):(/已完成|已到位/.test(ct.reason||'')?ct.reason:'未开始');if(ct.vr)$('vr-info').textContent='VR：'+(ct.vr_info||ct.reason);if(vrOn&&!ct.active){vrOn=false;$('vr-start').disabled=false;$('vr-stop').disabled=false;$('con-follow').textContent='未开始';$('vr-info').textContent='VR 已结束：'+(ct.reason||'会话超时，点「VR 跟随」重开');}}catch(e){$('con-can').textContent='控制台离线';$('con-deploy').textContent='—';}}
 $('con-status').onclick=conStatus;
 $('con-prepare').onclick=()=>conAction('prepare','① 拉起 CAN');
 $('con-enable').onclick=()=>conAction('enable','② 使能右臂（不自动移动）');
 $('con-exit-teach').onclick=async()=>{
  if(!confirm('结束右臂普通拖动示教并切入 CAN / MOVE J？\n· 只切换控制模式，不自动运动\n· 必须先停止双臂程序和全部跟随\n· 收到右臂 0x2A1 模式反馈后才算成功'))return;
  await conAction('exit_teach','右臂退出示教并切 CAN');
 };

 /* 取消使能（2026-10-23）：发 0x471 [07 01] 让六轴驱动器断使能。
    必须先停 deploy —— 该固件在 DISABLED 状态下仍执行位置指令，边跑边断既不安全也没用。 */
 $('con-disable').onclick=async()=>{
  if(!confirm('取消使能会让右臂六轴驱动器断使能：\n· 手臂失去保持力矩，会因自重下坠\n· 请先确认手臂下方和线束附近无人\n\n（deploy 运行中会被拒绝，需先「停止双臂程序」）\n\n确认取消使能？'))return;
  await conAction('disable','取消使能右臂');
 }; $('con-start').onclick=async()=>{if(!await conAction('deploy_start','③ 启动双臂控制程序'))return;try{const d=await conReq('/api/deploy_log');conLog($('con-log').textContent+'\n---- deploy 日志 ----\n'+d.log);}catch(e){}};
 $('con-stop').onclick=async()=>{await followStop();await conAction('deploy_stop','停止控制程序');};
 /* 定点移动（2026-10-22）：起始位姿 ↔ 零位 分阶段到位。
    不变量：J2～J6 只在 J1=0 平面内移动，J1 只在伸展态偏航。
    起始→零位先归零 J1 再收拢；零位→起始先展开再偏航。顺序由后端按实际反馈决定。 */
 async function moveArm(side,which){
  const log=side==='right'?conLog:llog;
  const label=(side==='right'?'右臂':'左臂')+(which==='zero'?' → 零位':' → 起始位姿');
  if(conBusy){log('已有管理操作进行中，请等待结果。');return;}
  conBusy=true;syncDefaultButtons();
  log(label+'：正在读取起始角度…');
  try{
   const d=await conReq('/api/control',{action:'move',client,
     controls:{mode:side==='right'?'right_joints':'left_joints',move:which}});
   const stage=d.entry&&d.entry[side];
   log('✓ '+label+' 已开始'+(stage?'：'+stage.message:'')+'\n（分阶段执行；要中止请按「停止全部运动」或「停止双臂程序」，反馈异常/超时会自动中止并锁定软件停止）');
   await (side==='right'?conStatus():lpoll());
  }catch(e){log('✗ '+label+' 失败：'+e.message);}
  finally{conBusy=false;syncDefaultButtons();}
 }
 $('con-move-start').onclick=()=>moveArm('right','start');
 $('con-move-zero').onclick=()=>moveArm('right','zero');
 $('lcon-move-start').onclick=()=>moveArm('left','start');
 $('lcon-move-zero').onclick=()=>moveArm('left','zero');
 async function followStart(){if(follow)return;if(vrOn){conLog('VR 跟随进行中，请先「停止 VR」再开始滑块跟随');return;}try{$('arm-zero').onclick();const d=await conReq('/api/control',{action:'start',client,controls:armControls('right')});showEntry(d);follow=true;$('follow-start').disabled=true;$('follow-stop').disabled=false;$('con-follow').textContent=d.reason||'进入跟随中';conLog('✓ 开始跟随：'+d.reason);}catch(e){conLog('✗ 无法开始跟随：'+e.message);conStatus();}}
 async function followStop(){follow=false;$('follow-start').disabled=false;$('follow-stop').disabled=false;try{await conReq('/api/control',{action:'stop',client,controls:{mode:'right_joints'}});$('con-follow').textContent='已停止';}catch(e){conLog('✗ 停止跟随请求失败：'+e.message);}await conStatus();}
 $('follow-start').onclick=followStart;$('follow-stop').onclick=followStop;
 /* VR 跟随（2026-10-20）：后端离合增量映射，页面切后台不中断；心跳由 VR 数据流维持 */
 async function vrStart(){if(vrOn)return;if(follow){conLog('滑块跟随进行中，请先「停止跟随」再启动 VR');return;}try{const d=await conReq('/api/control',{action:'start',client,controls:{mode:'vr'}});showEntry(d);vrOn=true;$('vr-start').disabled=true;$('vr-stop').disabled=false;$('con-follow').textContent=d.reason||'进入跟随中';$('vr-info').textContent='VR：'+(d.vr_info||d.reason);conLog('✓ VR 跟随已启动：戴上头显，按住右手柄侧键移动，松开保持');}catch(e){conLog('✗ 无法启动 VR 跟随：'+e.message);conStatus();}}
 async function vrStop(){vrOn=false;$('vr-start').disabled=false;$('vr-stop').disabled=false;try{await conReq('/api/control',{action:'stop',client,controls:{mode:'vr'}});$('con-follow').textContent='已停止';$('vr-info').textContent='VR：已停止';}catch(e){conLog('✗ 停止 VR 请求失败：'+e.message);}await conStatus();}
 $('vr-start').onclick=vrStart;$('vr-stop').onclick=vrStop;
 /* 右臂读取当前角度（2026-10-21）：can2 反馈 → 关节滑块（度）+ EE 显示 + 姿态画布 */
 $('rbtn-read').onclick=()=>readActualArm('right');
 async function followTick(){if(vrOn){conStatus();}if(follow&&!document.hidden){try{const d=await conReq('/api/control',{action:'update',client,controls:armControls('right')});if(!d.active){follow=false;$('follow-start').disabled=false;$('follow-stop').disabled=false;$('con-follow').textContent=d.reason||'已停止';}}catch(e){follow=false;$('follow-start').disabled=false;$('follow-stop').disabled=false;$('con-follow').textContent='控制台失联，已停';}}setTimeout(followTick,200);}
 /* 2026-10-23 修：失焦/切标签不再撤销跟随会话。以前这里发 action:'stop'，
   导致操作者一切窗口（看日志/终端）跟随就"自己退出"（现场指纹 reason=用户停止）。
   失焦时只是本页停止推送目标，deploy 的 100ms 看门狗会把手腕冻结在原地；
   会话由 120s deadline 或「停止跟随」结束。pagehide 仍保留 stop 兜底。 */
addEventListener('blur',()=>{});document.addEventListener('visibilitychange',()=>{});addEventListener('pagehide',()=>{follow=false;fetch(CON+'/api/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'stop',client}),keepalive:true}).catch(()=>{});});

 /* ===== 实时姿态画布（2026-10-20）：与 joint_fk_viewer.html 完全同源的 FK/投影/样式 ===== */
 let a3q=[-0.6981,1.6057,-0.8552,-1.0996,-1.0297,0.6981],a3tgt=[0.1514,0.2885,0.2659],a3tgtPoint='j5',a3yaw=0.27,a3pit=0.45,a3dist=2.2;
 function fkAll(q){let R=[[1,0,0],[0,1,0],[0,0,1]],t=[0,0,0];const P=[t.slice()];for(let i=0;i<6;i++){const tt=mv(R,DTF[i].t);t=[t[0]+tt[0],t[1]+tt[1],t[2]+tt[2]];P.push(t.slice());R=mm(mm(R,DTF[i].R),_rt(0,0,0,0,0,q[i]).R);}return P.map(p=>{const u=mv(FR,p);return[u[0]-OFF[0],u[1]-OFF[1],u[2]-OFF[2]];});}
 const a3cv=$('arm3d'),a3ctx=a3cv?a3cv.getContext('2d'):null;
 /* 画布尺寸只在真正变化时才重设。给 canvas.width/height 赋值会清空并重建位图，
    以前每次 draw 都无条件赋值，在 300ms 轮询下表现为整块画面持续闪烁（2026-10-22 排查）。 */
 function fitCanvas(cv){const w=Math.max(1,Math.round(cv.clientWidth)),h=Math.max(1,Math.round(cv.clientHeight));
  if(cv.width===w&&cv.height===h)return false;cv.width=w;cv.height=h;return true;}
 function a3proj(p){const cy=Math.cos(a3yaw),sy=Math.sin(a3yaw),cp=Math.cos(a3pit),sp=Math.sin(a3pit);
  const x1=cy*p[0]-sy*p[1],y1=sy*p[0]+cy*p[1];
  const z2=sp*y1+cp*p[2];const f=1.6/(1.6+z2*0.4);
  return[x1*f*a3dist*300+a3cv.width*0.5,-z2*f*a3dist*300+a3cv.height*0.6];}
 function a3draw(){window.SolidArmViewer?.setPose('arm3d',a3q,c.right_grip);if(!a3ctx)return;const ctx=a3ctx;
  fitCanvas(a3cv);
  ctx.fillStyle='#ffffff';ctx.fillRect(0,0,a3cv.width,a3cv.height);
  /* XY 平面黑色网格 */
  ctx.strokeStyle='#000000';ctx.lineWidth=0.8;
  for(let a=-0.8;a<=0.8;a+=0.2){let s=a3proj([a,-0.8,0]),e=a3proj([a,0.8,0]);
   ctx.beginPath();ctx.moveTo(s[0],s[1]);ctx.lineTo(e[0],e[1]);ctx.stroke();
   s=a3proj([-0.8,a,0]);e=a3proj([0.8,a,0]);
   ctx.beginPath();ctx.moveTo(s[0],s[1]);ctx.lineTo(e[0],e[1]);ctx.stroke();}
  /* 底盘系轴 */
  const AX=[[0.4,0,0],[0,0.4,0],[0,0,0.4]],AC=['#d0342c','#2f9e44','#1971c2'],AL=['+X 右','+Y 前','+Z 上'];
  AX.forEach((a,i)=>{const s=a3proj([0,0,0]),e=a3proj(a);ctx.strokeStyle=AC[i];ctx.lineWidth=2.5;
   ctx.beginPath();ctx.moveTo(s[0],s[1]);ctx.lineTo(e[0],e[1]);ctx.stroke();
   ctx.fillStyle=AC[i];ctx.font='bold 13px sans-serif';ctx.fillText(AL[i],e[0]+4,e[1]);});
  /* 机械臂指令骨架 */
  const Pd=fkAll(a3q);
  ctx.strokeStyle='#e8890c';ctx.lineWidth=4;ctx.lineJoin='round';
  ctx.beginPath();Pd.forEach((p,i)=>{const s=a3proj(p);i?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1]);});ctx.stroke();
  const LB=['底座','J1','J2','J3','J4','J5','J6/法兰'];
  Pd.forEach((p,i)=>{const s=a3proj(p);ctx.fillStyle=i===6?'#ff5a5a':'#1c7ed6';
   ctx.beginPath();ctx.arc(s[0],s[1],i===0?7:5.5,0,7);ctx.fill();
   ctx.fillStyle='#222';ctx.font='12px sans-serif';ctx.fillText(LB[i],s[0]+8,s[1]-6);});
  /* 指令骨架的测量点（含标定修正；与法兰 J6 端点间可见约 7cm 偏移） */
  {const tp=tcpPos(a3q,'right'),s=a3proj(tp);
   ctx.fillStyle='#c92a2a';ctx.beginPath();ctx.arc(s[0],s[1],4.5,0,7);ctx.fill();
   ctx.font='12px sans-serif';ctx.fillText('TCP',s[0]+7,s[1]+10);}
  /* 当前目标点：EE/VR=J5，关节路径=J7，由后端点类型字段区分。 */
  {const s=a3proj(a3tgt);ctx.strokeStyle='#2f9e44';ctx.lineWidth=2;
   ctx.beginPath();ctx.arc(s[0],s[1],8,0,7);ctx.stroke();
   ctx.beginPath();ctx.moveTo(s[0]-13,s[1]);ctx.lineTo(s[0]+13,s[1]);ctx.moveTo(s[0],s[1]-13);ctx.lineTo(s[0],s[1]+13);ctx.stroke();
   ctx.fillStyle='#2f9e44';ctx.font='12px sans-serif';
   ctx.fillText(`目标 ${a3tgtPoint.toUpperCase()} (${a3tgt.map(v=>v.toFixed(3)).join(', ')})`,s[0]+12,s[1]+16);}
 }
 let a3drag=null;
 if(a3cv){a3cv.addEventListener('pointerdown',e=>{a3drag=[e.clientX,e.clientY];a3cv.setPointerCapture(e.pointerId);});
  a3cv.addEventListener('pointermove',e=>{if(!a3drag)return;a3yaw+=(e.clientX-a3drag[0])*0.008;a3pit=Math.max(0,Math.min(1.4,a3pit+(e.clientY-a3drag[1])*0.008));a3drag=[e.clientX,e.clientY];a3draw();});
  a3cv.addEventListener('pointerup',()=>a3drag=null);
  a3cv.addEventListener('wheel',e=>{e.preventDefault();a3dist*=e.deltaY>0?1.1:0.9;a3dist=Math.max(0.2,Math.min(20,a3dist));a3draw();},{passive:false});}
 let a3busy=false;
 async function a3poll(){if(document.hidden||a3busy)return;a3busy=true;
  try{const d=await conReq('/api/status');const ct=d.control;
   if(ct.active&&ct.joints&&ct.joints.length===6)a3q=ct.joints;
   if(ct.active&&ct.right&&ct.right.length===3){a3tgt=ct.right;a3tgtPoint=ct.right_target_point||(ct.vr?'j5':'j7');}
   a3draw();}catch(e){}finally{a3busy=false;}}
 setInterval(a3poll,300);
 /* ===== 左臂控制台（2026-10-21 · can1 · v2 mode=2 关节直达，移植自 left-console.html） ===== */
 const LLIM=[[-150,150],[0,180],[-170,0],[-100,100],[-69.9,69.9],[-120,120]];
 /* 左臂唯一起始位：2026-10-31 03:16 真机实际姿态快照，与 Q_START_LEFT 同源。 */
 const LQINIT=[38.8,93.8,-43.2,57.2,-60.4,-35.8];
 const ldeg=LQINIT.slice();let lgrip=0,lactive=false,llastSend=0;
 function llog(m){appendLog('llog',m);}
 function armControls(side){
  if(side==='right')return rightControls();
  return lmodeEE?{mode:'left_ee',left:leeVals(),left_rpy_deg:c.left_rpy.slice(),left_grip:lgrip/100}:{mode:'left_joints',left_joints_deg:ldeg.slice(),left_grip:lgrip/100};
 }
 function lpush(){if(!lactive)return;const now=Date.now();if(now-llastSend<100)return;llastSend=now;
  conReq('/api/control',{action:'update',client,controls:armControls('left')}).then(d=>{if(d.error)llog('✗ '+d.error);}).catch(e=>llog('✗ 网络错误 '+e.message));}
 /* 左右臂统一：EE 滑块 = 底盘系 J5 绝对坐标 + 固定轴 RPY，关节页改动时 FK 同步 J5。 */
 let lmodeEE=true,l3fb=null;
 const LEE=['llx','lly','llz'],LRPY=['llroll','llpitch','llyaw'];
 function leeVals(){return LEE.map(id=>Number($(id).value));}
 function leeSync(p){c.left=p.slice();LEE.forEach((id,i)=>{const el=$(id);if(!el)return;el.value=p[i];const o=$(id+'-v');if(o)o.textContent=p[i].toFixed(3);});}
 function lrpySync(){LRPY.forEach((id,i)=>{const el=$(id);if(!el)return;el.value=c.left_rpy[i];$(id+'-v').textContent=c.left_rpy[i].toFixed(1)+'°';});}
 function lsyncEEfromJoints(){const q=ldeg.map(d=>d*Math.PI/180);leeSync(j5Pos(q,'left'));}
 function lsetMode(ee){lmodeEE=ee;$('panel-lee').hidden=!ee;$('panel-ljoint').hidden=ee;
  $('lmode-ee').className='button '+(ee?'primary':'secondary')+' sim-mode-btn';
  $('lmode-joint').className='button '+(ee?'secondary':'primary')+' sim-mode-btn';ldraw();}
 $('lmode-ee').onclick=()=>lsetMode(true);$('lmode-joint').onclick=()=>lsetMode(false);
 for(const id of LEE){const el=$(id);if(el)el.oninput=e=>{const o=$(id+'-v');if(o)o.textContent=Number(e.target.value).toFixed(3);c.left=leeVals();lpush();};}
 LRPY.forEach((id,i)=>{const el=$(id);if(el)el.oninput=e=>{c.left_rpy[i]=Number(e.target.value);$(id+'-v').textContent=c.left_rpy[i].toFixed(1)+'°';lpush();};});
 const lge=$('llg');if(lge)lge.oninput=e=>{const v=+e.target.value;lgrip=Math.round(v*100);c.left_grip=lgrip/100;$('llg-v').textContent=v.toFixed(2);const g=$('lgrip');if(g){g.value=lgrip;$('lgrip-v').textContent=lgrip+'%';}lpush();};
 $('larm-zero').onclick=()=>{if(defaultBlocked('left'))return;for(let i=0;i<6;i++){ldeg[i]=LQINIT[i];const s=$('lj'+(i+1));if(s){s.value=LQINIT[i];$('lj'+(i+1)+'-v').textContent=LQINIT[i].toFixed(1)+'°';}}
  lgrip=0;c.left_grip=0;c.left_rpy=[0,0,0];lrpySync();const g=$('lgrip');if(g){g.value=0;$('lgrip-v').textContent='0%';}
  const ge=$('llg');if(ge){ge.value=0;$('llg-v').textContent='0.00';}
  l3fb=null;leeSync(leftDefaultJ5());lsetMode(true);ldraw();llog('默认目标已设置，仅修改输入；开始跟随后才会下发。');};
 for(let i=0;i<6;i++){const el=$('lj'+(i+1));if(!el)continue;el.value=ldeg[i];$('lj'+(i+1)+'-v').textContent=ldeg[i].toFixed(1)+'°';el.oninput=e=>{ldeg[i]=+e.target.value;$('lj'+(i+1)+'-v').textContent=ldeg[i].toFixed(1)+'°';lsyncEEfromJoints();lpush();ldraw();};}
 const lg=$('lgrip');if(lg)lg.oninput=e=>{lgrip=+e.target.value;c.left_grip=lgrip/100;$('lgrip-v').textContent=lgrip+'%';const ge=$('llg');if(ge){ge.value=lgrip/100;$('llg-v').textContent=(lgrip/100).toFixed(2);}lpush();};
 leeSync(leftDefaultJ5());lrpySync();
 /* 与右臂一致的 200ms 控制节拍，页面后台时暂停网页会话心跳。 */
 let lbusy=false;
 setInterval(async()=>{if(!lactive||document.hidden||lbusy)return;lbusy=true;
  try{const d=await conReq('/api/control',{action:'update',client,controls:armControls('left')});
   if(d.error)llog('✗ '+d.error);}catch(e){}finally{lbusy=false;}},200);
 async function lpoll(){if(document.hidden)return;try{const d=await conReq('/api/status');
   $('lcon-can').textContent=d.can1||'UNKNOWN';
   $('lst-deploy').textContent=d.deploy==='STOPPED'?'未运行':'运行中(pid '+d.deploy+')';
   showEntry(d);   /* 双臂进入/移动阶段时同步锁定本侧滑块，避免误以为正在下发 */
   const L=d.control&&d.control.left,on=L&&L.active;serverLeftActive=!!on;syncDefaultButtons();reportAbort(L&&L.error,'lcon',d.safety&&d.safety.stopped);
   if(L&&L.joints_deg){l3fb=L.joints_deg;if(lmodeEE)ldraw();}
   $('lst-state').textContent=on?('跟随中 · '+(L.reason||'')):(/已完成|已到位/.test((L&&L.reason)||'')?L.reason:'未开始');
   if(L&&L.vr){$('lvr-info').textContent='左臂 VR：'+(L.vr_info||L.reason||'');}
   if(lvrOn&&(!on||!L.vr)){lvrOn=false;$('lvr-start').disabled=false;$('lvr-stop').disabled=false;$('lvr-info').textContent='左臂 VR 已结束：'+(L&&L.reason||'会话超时，点「VR 跟随」重开');}
   if(lactive&&!on){lactive=false;$('lbtn-start').disabled=false;$('lbtn-stop').disabled=false;llog('⚠ 左臂会话已结束（'+(L&&L.reason||'心跳过期')+'）');}
  }catch(e){$('lst-deploy').textContent='控制台离线';}}
 setInterval(lpoll,1500);lpoll();
 /* 左臂控制台按钮（与右臂同款流程；deploy 为双臂共用进程） */
 let lconBusy=false;
 async function lconAction(action,label){return managementAction(action,label,llog);}
 $('lcon-status').onclick=lpoll;
 $('lcon-prepare').onclick=()=>lconAction('prepare','① 拉起 CAN');
 $('lcon-enable').onclick=()=>lconAction('enable_left','② 使能左臂（不自动移动）');
 $('lcon-exit-teach').onclick=async()=>{
  if(!confirm('结束左臂普通拖动示教并切入 CAN / MOVE J？\n· 只切换控制模式，不自动运动\n· 必须先停止双臂程序和全部跟随\n· 收到左臂 0x2A1 模式反馈后才算成功'))return;
  await lconAction('exit_teach_left','左臂退出示教并切 CAN');
 };

 /* 取消使能（2026-10-23）：左臂同右臂，先停 deploy。 */
 $('lcon-disable').onclick=async()=>{
  if(!confirm('取消使能会让左臂六轴驱动器断使能：\n· 手臂失去保持力矩，会因自重下坠\n· 请先确认手臂下方和线束附近无人\n\n（deploy 运行中会被拒绝，需先「停止双臂程序」）\n\n确认取消使能？'))return;
  await lconAction('disable_left','取消使能左臂');
 }; $('lcon-start').onclick=async()=>{if(!await lconAction('deploy_start','③ 启动双臂控制程序'))return;try{const d=await conReq('/api/deploy_log');llog($('llog').textContent+'\n---- deploy 日志 ----\n'+d.log);}catch(e){}};
 $('lcon-stop').onclick=async()=>{if(lactive)$('lbtn-stop').onclick();await lconAction('deploy_stop','停止控制程序');};
 /* 左臂 VR 跟随（2026-10-21）：左手柄，镜像右臂 VR 链路，双手可同时 */
 let lvrOn=false;
 async function lvrStart(){if(lvrOn)return;if(lactive){llog('滑块跟随进行中，请先「停止跟随」再启动 VR');return;}
  try{const d=await conReq('/api/control',{action:'start',client,controls:{mode:'vr_left'}});
   if(d.error){llog('✗ '+d.error);return;}
   showEntry(d);lvrOn=true;$('lvr-start').disabled=true;$('lvr-stop').disabled=false;
   $('lvr-info').textContent='左臂 VR：'+((d.left&&(d.left.vr_info||d.left.reason))||'已启动');
   llog('✓ 左臂 VR 跟随已启动：左手柄，按住左侧键移动，松开保持');}catch(e){llog('✗ 无法启动左臂 VR：'+e.message);lpoll();}}
 async function lvrStop(){lvrOn=false;$('lvr-start').disabled=false;$('lvr-stop').disabled=false;
  try{await conReq('/api/control',{action:'stop',client,controls:{mode:'vr_left'}});$('lvr-info').textContent='左臂 VR：已停止';}catch(e){llog('✗ 停止左臂 VR 请求失败：'+e.message);}await lpoll();}
 $('lvr-start').onclick=lvrStart;$('lvr-stop').onclick=lvrStop;
 /* 网页、VR、VLA 共用后端搬运状态；运行期间禁止重复启动 X。 */
 let transferRunning=false,transferBusy=false;
 async function syncTransfer(){if(transferBusy)return;transferBusy=true;try{
  const d=await conReq('/api/transfer/status'),t=d.transfer||{};
  transferRunning=!['idle','done','failed','cancelled'].includes(t.state||'idle');
  $('transfer-badge').textContent=transferRunning?'执行中':({done:'已完成',failed:'失败',cancelled:'已中止'}[t.state]||'空闲');
  $('transfer-stage').textContent=t.stage||'—';
  $('transfer-detail').textContent=(t.task_id?'任务 #'+t.task_id+' · ':'')+(t.message||'尚未启动搬运任务。');
 }catch(e){$('transfer-detail').textContent='搬运状态暂不可读：'+e.message;}
 finally{transferBusy=false;$('lvr-route').disabled=conBusy||transferRunning;}}
 $('lvr-route').onclick=async()=>{
  if(conBusy||transferRunning)return;conBusy=true;$('lvr-route').disabled=true;syncDefaultButtons();
  try{const d=await conReq('/api/vr_route',{action:'left_transfer'});
   transferRunning=true;
   llog('✓ '+(d.message||'左臂搬运流程已启动')+'；状态见左臂控制台，可用 A 键或“停止全部运动”中止。');
   $('lvr-info').textContent='左臂搬运流程：已启动';await Promise.all([lpoll(),syncTransfer()]);
  }catch(e){llog('✗ 无法启动左臂搬运流程：'+e.message);}
  finally{conBusy=false;$('lvr-route').disabled=transferRunning;syncDefaultButtons();}
 };
 syncTransfer();setInterval(syncTransfer,700);
 $('lvr-dual-home').onclick=async()=>{
  if(conBusy)return;conBusy=true;$('lvr-dual-home').disabled=true;syncDefaultButtons();
  try{const d=await conReq('/api/vr_route',{action:'dual_home'});
   llog('✓ '+(d.message||'双臂归位已启动')+'：右臂完成后左臂再归位。');
   $('lvr-info').textContent='双臂返回起始：已启动';await lpoll();
  }catch(e){llog('✗ 无法启动双臂归位：'+e.message);}
  finally{conBusy=false;$('lvr-dual-home').disabled=false;syncDefaultButtons();}
 };

 /* ===== 一键启动 / 一键返回零位（顶部全局条）=====
    2026-10-22 改为**串行**：右臂到位之后左臂才动（两臂同时经过危险构型会夹爪互撞），
    到位判定靠后端 move_result 的 seq/state，而不是靠"睡一会儿再下一步"。 */
 const sleep=ms=>new Promise(r=>setTimeout(r,ms));
 /* C20：整个自动流程共用一个守卫。启动时拍下 safetyEpoch，
    任何等待点发现「已被软件停止」或「epoch 变了」就抛错中止，
    避免停止→解除停止之后旧流程继续用新的 epoch 往下跑。 */
 let autoGuard=null;
 function autoSay(t){conLog(t);llog(t);}
 /* 串行流程里的"稳定等待"。2026-10-22 现场：拉起 CAN 后立刻发使能会丢指令，
    因为总线/驱动还没就绪；deploy 刚起也会报 actuator DISABLED。 */
 const SETTLE={can:2500,enable:2500,deploy:1200};

 async function waitDeployStopped(limitMs){
  /* C21：只有后端明确报 STOPPED 才算停机。
     旧实现把「非数字」一律当成已停机，未知值/空响应/超时都会放行。 */
  const LIMIT=limitMs||12000,t0=Date.now();
  while(Date.now()-t0<LIMIT){
   if(autoGuard)autoGuard();
   let d=null,err=null;
   try{d=await conReq('/api/status');}catch(e){err=e;}
   if(err)throw Error('无法确认 deploy 是否停止（状态查询失败：'+err.message+'）');
   const v=(d&&d.deploy!==undefined&&d.deploy!==null)?String(d.deploy):'';
   if(v==='STOPPED')return '已停机';
   if(!/^\d+$/.test(v))throw Error('deploy 状态未知（'+JSON.stringify(v)+'）：不能证明已停止，自动流程中止');
   await sleep(500);
  }
  throw Error('等待 deploy 停止超时（'+(LIMIT/1000)+' 秒）：未确认停止，自动流程中止');
 }

 async function waitMove(side,seq,label){
  const t0=Date.now(),LIMIT=240000;let last='';
  while(Date.now()-t0<LIMIT){
   if(autoGuard)autoGuard();          /* C20：等待期间被停止就立刻中止 */
   await sleep(500);
   let d;try{d=await conReq('/api/vr_buttons');}catch(e){continue;}
   const mr=(d&&d.move_result)||{};
   const r=side==='right'?mr.right:mr.left;
   if(r&&r.seq===seq&&r.state!=='running'){
    if(r.state==='done')return r.message||'已到位';
    throw Error(label+'失败：'+(r.message||'未知原因'));
   }
   if(r&&r.message&&r.message!==last){last=r.message;autoSay('   … '+r.message);}
  }
  throw Error(label+'等待超时（4 分钟）');
 }

 async function moveTo(side,which,label){
  const d=await conReq('/api/control',{action:'move',client,
   controls:{mode:side==='left'?'left_joints':'right_joints',move:which}});
  const seq=d&&d.move_seq;
  if(typeof seq!=='number')throw Error(label+'：后端未返回移动序号（版本不匹配？）');
  return await waitMove(side,seq,label);
 }

 async function startVrSide(side){
  const mode=side==='left'?'vr_left':'vr';
  const d=await conReq('/api/control',{action:'start',client,controls:{mode}});
  showEntry(d);
  if(side==='right'){
   vrOn=true;$('vr-start').disabled=true;$('vr-stop').disabled=false;
   $('con-follow').textContent=d.reason||'进入跟随中';
   $('vr-info').textContent='右臂 VR：'+((d.control&&(d.control.vr_info||d.control.reason))||'已启动');
  }else{
   lvrOn=true;$('lvr-start').disabled=true;$('lvr-stop').disabled=false;
   $('lvr-info').textContent='左臂 VR：'+((d.left&&(d.left.vr_info||d.left.reason))||'已启动');
  }
  return '已启动';
 }

 async function deployRunning(){
  /* 后端/KR260 的约定：deploy 在运行时 status 里报的是 **PID**（形如 "589919"），
     没跑时报 "STOPPED"。所以这里按"是不是数字"判断，不要找 'RUNNING'。 */
  try{const d=await conReq('/api/status');return !!(d&&/^\d+$/.test(String(d.deploy||'')));}
  catch(e){return false;}
 }

 async function runAuto(btn,LABEL,TOTAL,steps){
  const base=globalStopped;
  if(autoBusy)return;
  if(base){autoSay('⚠ 软件停止已锁定：请先点「解除软件停止」再试');return;}
  if(safetyEpoch===null){autoSay('⚠ 控制状态尚未就绪：等顶部显示正常后再试');return;}
  autoBusy=true;btn.disabled=true;
  const epoch0=safetyEpoch;      /* C20：整段流程绑定启动时的代次 */
  autoGuard=()=>{
   if(globalStopped)throw Error('已被软件停止：自动流程中止，请解除停止后重新点击本按钮');
   if(safetyEpoch!==epoch0)throw Error('控制状态代次已变化（'+epoch0+'→'+safetyEpoch+'）：自动流程中止，请重新点击');
  };
  let n=0;
  try{
   for(const [name,fn,settleMs] of steps){
    autoGuard();               /* 每个步骤开始前核对 */
    n++;btn.textContent='▶ '+name;
    autoSay('('+n+'/'+TOTAL+') '+name+' …');
    try{const r=await fn();autoSay('✓ '+name+(r?(' — '+r):''));}
    catch(e){autoSay('✗ '+name+' 失败：'+e.message+'\n已停止，后续步骤未执行。');throw e;}
    if(settleMs>0){
     btn.textContent='⏳ 等待 '+(settleMs/1000).toFixed(1)+' 秒…';
     autoSay('   ⏳ 等待 '+(settleMs/1000).toFixed(1)+' 秒，让上一步真正生效');
     await sleep(settleMs);
    }
   }
   autoGuard();
   autoSay('=== 「'+LABEL+'」完成 ===');
  }catch(e){
   /* 失败已逐条记录，这里不再重复 */
  }finally{
   autoGuard=null;
   btn.textContent=LABEL;autoBusy=false;btn.disabled=false;
   syncDefaultButtons();conStatus();lpoll();
  }
 }

 function autoStartVr(){
  if(autoBusy)return;
  if(globalStopped){autoSay('⚠ 软件停止已锁定：请先点「解除软件停止」，再一键启动');return;}
  if(safetyEpoch===null){autoSay('⚠ 控制状态尚未就绪：等顶部显示正常后再试');return;}
  if(follow||vrOn||lactive||lvrOn){autoSay('⚠ 已有跟随会话在进行：请先「停止跟随 / 停止 VR」');return;}
  if(!window.confirm('将依次执行（串行：前一步到位后才走下一步）：\n① 拉起 CAN\n② 使能右臂 / 左臂（臂会变硬）\n③ 启动双臂程序\n④ 右臂 → 起始位姿（等到位）\n⑤ 左臂 → 起始位姿（等到位）\n⑥ 右臂 VR 跟随\n⑦ 左臂 VR 跟随\n\n（每步之间会等 1~2.5 秒让上一步真正生效）\n\n确认执行？'))return;
  return runAuto($('auto-vr'),'一键启动 VR 跟随',8,[
   ['① 拉起 CAN',()=>conReq('/api/action',{action:'prepare'}),SETTLE.can],
   ['② 使能右臂',()=>conReq('/api/action',{action:'enable'}),SETTLE.enable],
   ['② 使能左臂',()=>conReq('/api/action',{action:'enable_left'}),SETTLE.enable],
   ['③ 启动双臂程序',()=>conReq('/api/action',{action:'deploy_start'}),SETTLE.deploy],
   ['右臂 → 起始位姿',()=>moveTo('right','start','右臂移动到起始')],
   ['左臂 → 起始位姿',()=>moveTo('left','start','左臂移动到起始')],
   ['右臂 VR 跟随',()=>startVrSide('right')],
   ['左臂 VR 跟随',()=>startVrSide('left')]
  ]).then(()=>{
   autoSay('· 按住侧键才跟随，松开保持；进入期间别切窗口（失焦会停）。');
   autoSay('· Y 切底盘、B 回双臂、X 左臂固定搬运、A 双臂依次回起始位。收工点「一键返回零位」。');
  });
 }

 function autoZero(){
  if(autoBusy)return;
  if(globalStopped){autoSay('⚠ 软件停止已锁定：请先点「解除软件停止」');return;}
  if(safetyEpoch===null){autoSay('⚠ 控制状态尚未就绪：等顶部显示正常后再试');return;}
  if(!window.confirm('将依次执行（串行）：\n① 停止右臂 VR 跟随\n② 停止左臂 VR 跟随\n③ 必要时重新启动双臂程序\n④ 右臂 → 零位（等到位）\n⑤ 左臂 → 零位（等到位）\n\n确认执行？'))return;
  return runAuto($('auto-zero'),'一键返回零位',5,[
   ['① 停止右臂 VR',async()=>{if(vrOn)await vrStop();return '已停止';}],
   ['② 停止左臂 VR',async()=>{if(lvrOn)await lvrStop();return '已停止';}],
   ['③ 启动双臂程序',async()=>{
     if(await deployRunning())return '本来就在运行';
     return await conReq('/api/action',{action:'deploy_start'});},SETTLE.deploy],
   ['右臂 → 零位',()=>moveTo('right','zero','右臂移动到零位')],
   ['左臂 → 零位',()=>moveTo('left','zero','左臂移动到零位')]
  ]);
 }

 $('auto-vr').onclick=autoStartVr;
 $('auto-zero').onclick=autoZero;
 $('lbtn-read').onclick=()=>readActualArm('left');
 $('lbtn-start').onclick=async()=>{if(lvrOn){llog('VR 跟随进行中，请先「停止 VR」再开始滑块跟随');return;}try{$('larm-zero').onclick();const ctl=armControls('left');
   const d=await conReq('/api/control',{action:'update',client,controls:ctl});
   if(d.error){llog('✗ '+d.error);return;}showEntry(d);lactive=true;$('lbtn-start').disabled=true;$('lbtn-stop').disabled=false;llog('✓ 左臂控制已开始（统一起始位，后续只响应新滑块输入）');}catch(e){llog('✗ 网络错误 '+e.message);}};
 $('lbtn-stop').onclick=async()=>{lactive=false;$('lbtn-start').disabled=false;$('lbtn-stop').disabled=false;try{await conReq('/api/control',{action:'stop',client,controls:{mode:'left_joints'}});llog('■ 已停止');}catch(e){llog('✗ 停止跟随请求失败：'+e.message);}await lpoll();};
 addEventListener('pagehide',()=>{if(lactive)fetch(CON+'/api/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'stop',client,controls:{mode:'left_joints'}}),keepalive:true}).catch(()=>{});});
 /* 左臂实时姿态画布：FK 与右臂同源，画滑块指令骨架 */
 const l3cv=$('arm3d-left'),l3ctx=l3cv?l3cv.getContext('2d'):null;
 let l3yaw=0.27,l3pit=0.45,l3dist=2.2,l3drag=null;
 function l3proj(p){const cy=Math.cos(l3yaw),sy=Math.sin(l3yaw),cp=Math.cos(l3pit),sp=Math.sin(l3pit);
  const x1=cy*p[0]-sy*p[1],y1=sy*p[0]+cy*p[1];const z2=sp*y1+cp*p[2];const f=1.6/(1.6+z2*0.4);
  return[x1*f*l3dist*300+l3cv.width*0.5,-z2*f*l3dist*300+l3cv.height*0.6];}
 function ldraw(){window.SolidArmViewer?.setPose('arm3d-left',(lmodeEE&&l3fb?l3fb:ldeg).map(d=>d*Math.PI/180),lgrip/100);if(!l3ctx)return;const ctx=l3ctx;
  fitCanvas(l3cv);
  ctx.fillStyle='#ffffff';ctx.fillRect(0,0,l3cv.width,l3cv.height);
  ctx.strokeStyle='#000000';ctx.lineWidth=0.8;
  for(let a=-0.8;a<=0.8;a+=0.2){let s=l3proj([a,-0.8,0]),e=l3proj([a,0.8,0]);
   ctx.beginPath();ctx.moveTo(s[0],s[1]);ctx.lineTo(e[0],e[1]);ctx.stroke();
   s=l3proj([-0.8,a,0]);e=l3proj([0.8,a,0]);
   ctx.beginPath();ctx.moveTo(s[0],s[1]);ctx.lineTo(e[0],e[1]);ctx.stroke();}
  const AX=[[0.4,0,0],[0,0.4,0],[0,0,0.4]],AC=['#d0342c','#2f9e44','#1971c2'],AL=['+X 右','+Y 前','+Z 上'];
  AX.forEach((a,i)=>{const s=l3proj([0,0,0]),e=l3proj(a);ctx.strokeStyle=AC[i];ctx.lineWidth=2.5;
   ctx.beginPath();ctx.moveTo(s[0],s[1]);ctx.lineTo(e[0],e[1]);ctx.stroke();
   ctx.fillStyle=AC[i];ctx.font='bold 13px sans-serif';ctx.fillText(AL[i],e[0]+4,e[1]);});
  const q=(lmodeEE&&l3fb?l3fb:ldeg).map(d=>d*Math.PI/180),Pd=fkAll(q);
  ctx.strokeStyle='#1971c2';ctx.lineWidth=4;ctx.lineJoin='round';
  ctx.beginPath();Pd.forEach((p,i)=>{const s=l3proj(p);i?ctx.lineTo(s[0],s[1]):ctx.moveTo(s[0],s[1]);});ctx.stroke();
  const LB=['底座','J1','J2','J3','J4','J5','J6/法兰'];
  Pd.forEach((p,i)=>{const s=l3proj(p);ctx.fillStyle=i===6?'#ff5a5a':'#1c7ed6';
   ctx.beginPath();ctx.arc(s[0],s[1],i===0?7:5.5,0,7);ctx.fill();
   ctx.fillStyle='#222';ctx.font='12px sans-serif';ctx.fillText(LB[i],s[0]+8,s[1]-6);});
  {const target=lmodeEE?leeVals():j5Pos(q,'left'),s=l3proj(target);ctx.strokeStyle='#2f9e44';ctx.lineWidth=2;
   ctx.beginPath();ctx.arc(s[0],s[1],8,0,7);ctx.stroke();
   ctx.beginPath();ctx.moveTo(s[0]-13,s[1]);ctx.lineTo(s[0]+13,s[1]);ctx.moveTo(s[0],s[1]-13);ctx.lineTo(s[0],s[1]+13);ctx.stroke();
   ctx.fillStyle='#2f9e44';ctx.font='12px sans-serif';
   ctx.fillText('目标 J5 ('+target.map(v=>v.toFixed(3)).join(', ')+')',s[0]+12,s[1]+16);}
 }
 if(l3cv){l3cv.addEventListener('pointerdown',e=>{l3drag=[e.clientX,e.clientY];l3cv.setPointerCapture(e.pointerId);});
  l3cv.addEventListener('pointermove',e=>{if(!l3drag)return;l3yaw+=(e.clientX-l3drag[0])*0.008;l3pit=Math.max(0,Math.min(1.4,l3pit+(e.clientY-l3drag[1])*0.008));l3drag=[e.clientX,e.clientY];ldraw();});
  l3cv.addEventListener('pointerup',()=>l3drag=null);
  l3cv.addEventListener('wheel',e=>{e.preventDefault();l3dist*=e.deltaY>0?1.1:0.9;l3dist=Math.max(0.2,Math.min(20,l3dist));ldraw();},{passive:false});
  ldraw();}

 // Presets only update local inputs. No enable, tool action or control request.
 $('arm-zpose').onclick=()=>{if(defaultBlocked('right'))return;
  for(let i=1;i<=6;i++)$('sj'+i).value=0;
  c.right_grip=0;setMode(true);jointUpdate();a3q=[0,0,0,0,0,0];a3tgt=c.right.slice();a3draw();
  conLog('Z 字位置已填入：六轴 0°，仅预览，未发送。开始跟随后按关节目标执行。');
 };
 $('larm-zpose').onclick=()=>{if(defaultBlocked('left'))return;
  for(let i=0;i<6;i++){ldeg[i]=0;$('lj'+(i+1)).value=0;$('lj'+(i+1)+'-v').textContent='0.0°';}
  l3fb=null;lgrip=0;$('lgrip').value=0;$('lgrip-v').textContent='0%';$('llg').value=0;$('llg-v').textContent='0.00';
  lsyncEEfromJoints();lsetMode(false);ldraw();llog('Z 字位置已填入：六轴 0°，仅修改输入，未发送；当前为关节模式。');
 };
 // Actual poses are independent snapshots of unrounded, unclamped CAN feedback.
 function actualPreview(side){
  const cv=$('actual-'+side),ctx=cv&&cv.getContext('2d');
  let q=null,yaw=.27,pitch=.45,scale=2.2,drag=null;
  function project(p){const x=Math.cos(yaw)*p[0]-Math.sin(yaw)*p[1],y=Math.sin(yaw)*p[0]+Math.cos(yaw)*p[1],z=Math.sin(pitch)*y+Math.cos(pitch)*p[2],f=1.6/(1.6+z*.4);return[x*f*scale*300+cv.width*.5,-z*f*scale*300+cv.height*.6];}
  function line(a,b,color,width){a=project(a);b=project(b);ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();}
  function draw(){if(!ctx)return;fitCanvas(cv);ctx.fillStyle='#fff';ctx.fillRect(0,0,cv.width,cv.height);
   if(!q){ctx.fillStyle='#64748b';ctx.font='16px sans-serif';ctx.textAlign='center';ctx.fillText('尚未读取实际姿态',cv.width/2,cv.height/2);ctx.textAlign='left';return;}
   for(let a=-.8;a<=.8;a+=.2){line([a,-.8,0],[a,.8,0],'#cbd5e1',.8);line([-.8,a,0],[.8,a,0],'#cbd5e1',.8);}
   [[.4,0,0],[0,.4,0],[0,0,.4]].forEach((a,i)=>{const color=['#d0342c','#2f9e44','#1971c2'][i];line([0,0,0],a,color,2);const pt=project(a);ctx.fillStyle=color;ctx.font='bold 13px sans-serif';ctx.fillText(['+X 右','+Y 前','+Z 上'][i],pt[0]+4,pt[1]);});
   const points=fkAll(q),color=side==='right'?'#e8890c':'#1971c2';
   points.forEach((p,i)=>{if(i)line(points[i-1],p,color,4);const pt=project(p);ctx.fillStyle=i===6?'#ff5a5a':color;ctx.beginPath();ctx.arc(pt[0],pt[1],i?5.5:7,0,7);ctx.fill();ctx.fillStyle='#222';ctx.font='12px sans-serif';ctx.fillText(['底座','J1','J2','J3','J4','J5','J6/法兰'][i],pt[0]+8,pt[1]-6);});
  }
  if(cv){cv.addEventListener('pointerdown',e=>{drag=[e.clientX,e.clientY];cv.setPointerCapture(e.pointerId);});cv.addEventListener('pointermove',e=>{if(!drag)return;yaw+=(e.clientX-drag[0])*.008;pitch=Math.max(0,Math.min(1.4,pitch+(e.clientY-drag[1])*.008));drag=[e.clientX,e.clientY];draw();});for(const ev of ['pointerup','pointercancel','lostpointercapture'])cv.addEventListener(ev,()=>drag=null);cv.addEventListener('wheel',e=>{e.preventDefault();scale=Math.max(.2,Math.min(20,scale*(e.deltaY>0?1.1:.9)));draw();},{passive:false});}
  addEventListener('resize',draw);draw();return {set(degrees){q=degrees.map(v=>v*Math.PI/180);window.SolidArmViewer?.setPose('actual-'+side,q);draw();}};
 }
 const actualArms={right:actualPreview('right'),left:actualPreview('left')};
 const actualTimes={right:null,left:null};
 async function readActualArm(side){
  const right=side==='right',button=$(right?'rbtn-read':'lbtn-read'),state=$('actual-'+side+'-state'),log=right?conLog:llog;
  if(button.disabled)return;button.disabled=true;state.textContent='正在读取 CAN 关节反馈…'+(actualTimes[side]?'图中保留上次快照。':'');
  try{const d=await conReq('/api/'+side+'_read');
   if(d.ok!==true||!Array.isArray(d.joints_deg)||d.joints_deg.length!==6||!d.joints_deg.every(v=>typeof v==='number'&&Number.isFinite(v)))throw Error(d.error||'六轴反馈不完整或无效');
   actualArms[side].set(d.joints_deg);actualTimes[side]=new Date().toLocaleTimeString();
   state.textContent='最近读取：'+actualTimes[side]+' · 手动快照（非实时）';
   $('actual-'+side+'-angles').textContent=d.joints_deg.map((v,i)=>'J'+(i+1)+' '+v.toFixed(1)+'°').join(' · ');
   // Preserve existing idle target alignment, but never change a running follow target.
   if(!defaultBlocked(side)){
    if(right){d.joints_deg.forEach((v,i)=>{const slider=$('sj'+(i+1));if(slider)slider.value=v;});jointUpdate();}
    else{d.joints_deg.forEach((v,i)=>{ldeg[i]=+v.toFixed(1);const slider=$('lj'+(i+1));slider.value=Math.max(LLIM[i][0],Math.min(LLIM[i][1],ldeg[i]));$('lj'+(i+1)+'-v').textContent=ldeg[i].toFixed(1)+'°';});l3fb=ldeg.slice();lsyncEEfromJoints();ldraw();}
   }
   log('✓ 实际姿态快照已更新：'+d.joints_deg.map(v=>v.toFixed(1)+'°').join(', '));
  }catch(e){state.textContent='读取失败：'+e.message+(actualTimes[side]?' · 保留 '+actualTimes[side]+' 的旧快照':' · 尚无实际姿态');log('✗ '+state.textContent);}finally{button.disabled=false;}
 }
 // Independent read-only preview: never writes shared controls c or calls base_cmd.
 async function vrSticksPreview(){
  const state=$('vr-sticks-state');if(!state)return;
  if(!$('vr-sticks-panel').open){setTimeout(vrSticksPreview,500);return;}
  try{
   const d=await conReq('/api/vr_sticks');
   if(!d.intent||!d.relay_preview)throw Error('后端尚未提供摇杆预览');
   const fmt=v=>Array.isArray(v)?v.map(n=>Number(n).toFixed(3)).join(' / '):'字段缺失';
   $('vr-stick-left').textContent=fmt(d.left);$('vr-stick-right').textContent=fmt(d.right);
   state.textContent=d.reason+(d.fresh?'':'（原始数值可能为历史值）');
   const v=d.intent,r=d.relay_preview;
   $('vr-sticks-preview').textContent=`输入意图：前进 ${v.vx.toFixed(3)} m/s · 左移 ${v.vy.toFixed(3)} m/s · 左转 ${v.wz.toFixed(3)} rad/s\n现有底盘规则预览：前进 ${r.vx.toFixed(3)} · 左移 ${r.vy.toFixed(3)} · 左转 ${r.wz.toFixed(3)}`+(d.simultaneous&&baseSub==='a'?'\n当前底盘平移优先：同时推两摇杆时，转向会被忽略。':'')+(baseSub==='b'?'\n当前为 RC 遥控车子模式：左摇杆纵轴油门、右摇杆横轴转向，可同时生效。':'')+'\n未发送到车辆；未接入 B/Y 使能状态。';
  }catch(e){state.textContent='摇杆预览不可用：'+e.message;$('vr-stick-left').textContent='—';$('vr-stick-right').textContent='—';$('vr-sticks-preview').textContent='无有效预览；未发送到车辆。';}
  setTimeout(vrSticksPreview,200);
 }
 vrSticksPreview();
 // Button gating is shared by both arms; the backend interlock is authoritative.
 // 被门控拦下时必须给出明确原因，不能静默 return（否则表现为“点了没反应”）。
 for(const id of ['con-prepare','con-enable','con-start','con-exit-teach','follow-start','vr-start','con-move-start','con-move-zero','lcon-prepare','lcon-enable','lcon-start','lcon-exit-teach','lbtn-start','lvr-start','lcon-move-start','lcon-move-zero']){
  const run=$(id).onclick;$(id).onclick=async e=>{
   const say=id.charAt(0)==='l'?llog:conLog;
   if(globalStopped){say('⚠ 软件停止已锁定：请先按页面顶部「解除软件停止」，再重新开始操作');syncDefaultButtons();return;}
   if(safetyEpoch===null){say('⚠ 控制状态尚未就绪：请稍候或刷新页面');syncDefaultButtons();return;}
   try{await run(e);}finally{syncDefaultButtons();}
  };
 }
 pollSafety();setInterval(pollSafety,1000);
 $('reset').onclick=()=>{if(!defaultBlocked('right')&&!defaultBlocked('left'))reset();};
 conStatus();setInterval(conStatus,3000);followTick();
 /* ===== 顶部全局 VR 指示（2026-10-22）=====
    模式（双臂/底盘）+ A/B/X/Y 三态灯 + 底盘实时速度。
    只读 /api/vr_buttons，不涉及任何控制；放在顶部软件停止条里，任何滚动位置都看得见。 */
 (function(){
  const hud=$('vr-hud');if(!hud)return;
  const modeEl=$('vr-mode'),baseEl=$('vr-base'),stateEl=$('vr-hud-state');
  const lights={};
  const btns=(typeof hud.querySelectorAll==='function')?hud.querySelectorAll('.vr-btn'):[];
  btns.forEach(b=>{if(b&&b.dataset)lights[b.dataset.btn]=b;});
  let busy=false;
  async function hudTick(){
   if(busy||document.hidden)return;busy=true;
   try{
    const d=await conReq('/api/vr_buttons');
    const baseMode=d&&d.mode==='base';
    if(d&&d.base_sub)applyBaseSub(d.base_sub);
    if(modeEl){modeEl.textContent=baseMode?('底盘模式 · '+(baseSub==='b'?'RC 遥控车':'全向平移')):'双臂模式';modeEl.dataset.mode=baseMode?'base':'arms';}
    if(!d||!d.available){                      /* 旧 APK 或解析失败：不猜，全部置灰 */
     for(const k in lights)lights[k].dataset.state='';
     if(baseEl)baseEl.textContent='底盘：未启用';
     if(stateEl){stateEl.textContent=(d&&d.available===false)?'VR 无按键信息':'VR 未连接';stateEl.dataset.stale='1';}
     return;
    }
    for(const k in lights){
     const b=(d.bits&&d.bits[k])||{valid:false,pressed:false};
     lights[k].dataset.state=!b.valid?'':(b.pressed?'pressed':'valid');
    }
    const bb=d.base||{};
    if(baseEl)baseEl.textContent=baseMode
      ?('底盘 vx '+Number(bb.vx||0).toFixed(2)+' vy '+Number(bb.vy||0).toFixed(2)+' wz '+Number(bb.wz||0).toFixed(2))
      :'底盘：未启用';
    if(stateEl){
      stateEl.dataset.stale=d.fresh?'0':'1';
      stateEl.textContent=d.fresh?('VR '+(d.age_ms!=null?d.age_ms+' ms':'在线')):'VR 数据已过期';
    }
   }catch(e){
    if(stateEl){stateEl.textContent='指示条离线';stateEl.dataset.stale='1';}
   }finally{busy=false;}
  }
  setInterval(hudTick,250);hudTick();
 })();

 request('session').then(()=>{signed=true;$('login').textContent='AIPC · 已登录';$('start').disabled=false;$('send-state').textContent='仅预览 · 未发送';attachMedia();}).catch(()=>{});reset();tick();
/* 底盘遥控（2026-10-21）：摇杆 → /api/base_cmd → KR260 chassis_relay.py → can0(YHS)。
   使能才发车；断使能/页面关闭立即发零速；KR260 侧 200ms 看门狗兜底。 */
(function(){
const be=$('base-enable'),bd=$('base-disable');if(!be)return;
let baseEn=false,baseBusy=false,baseEpoch=0;
function baseLog(t){const el=$('base-log');if(el)el.textContent=t;}
function baseReset(){centerBase();centerTurn();}
function baseLocalOff(){baseEn=false;baseEpoch++;baseReset();be.disabled=globalStopped;bd.disabled=true;$('base-state').textContent='网页控制未开启';}
stopLocalBase=baseLocalOff;
function baseStop(reason){
 if(!baseEn)return;
 baseEn=false;const stamp=++baseEpoch;baseReset();be.disabled=globalStopped;bd.disabled=true;$('base-state').textContent='网页控制未开启';baseLog(reason+'；正在发送零速断使能指令…');
 fetch(CON+'/api/base_cmd',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({vx:0,vy:0,wz:0,enable:false}),keepalive:true})
 .then(r=>{if(!r.ok)throw Error('HTTP '+r.status);if(stamp===baseEpoch)baseLog(reason+'；零速断使能指令已提交，实际停车请观察底盘。');})
 .catch(e=>{if(stamp===baseEpoch)baseLog(reason+'；停车请求失败：'+e.message+'。请检查底盘是否停止，必要时按实体急停。');});
}
be.onclick=()=>{if(baseEn||baseBusy||globalStopped||safetyEpoch===null)return;baseReset();baseEpoch++;baseEn=true;be.disabled=true;bd.disabled=false;$('base-state').textContent='网页控制已开启 · 设备状态见反馈';baseLog('网页将发送摇杆指令；车辆是否执行请查看反馈。左平移、右转向，松开回中。');};
bd.onclick=()=>baseStop('已断使能');
const subTog=$('base-sub-toggle');
if(subTog)subTog.onclick=async()=>{
 if(globalStopped||subTog.disabled)return;
 const target=baseSub==='a'?'b':'a';subTog.disabled=true;
 try{
  const d=await conReq('/api/base_sub',{sub:target});
  applyBaseSub(d.sub);
  if(baseEn)baseStop('已切换底盘子模式（'+d.sub_text+'），请重新开启网页控制');
  else{baseReset();baseLog('底盘子模式已切换：'+d.sub_text+'（VR 端 Y 键与本按钮同一份状态）');}
 }catch(e){baseLog('✗ 子模式切换失败：'+e.message);}
 finally{subTog.disabled=globalStopped;}
};
setInterval(async()=>{
 if(!baseEn||baseBusy)return;
 baseBusy=true;const stamp=baseEpoch;
 try{await conReq('/api/base_cmd',{vx:c.vx,vy:c.vy,wz:c.yaw,enable:true,rc:baseSub==='b'});if(stamp===baseEpoch)$('base-link').textContent='AIPC 已接受指令；UDP 下发不代表执行确认';}
 catch(e){if(baseEn&&stamp===baseEpoch)baseStop('底盘链路异常：'+e.message);}
 finally{baseBusy=false;}
},100);
addEventListener('blur',()=>baseStop('页面失焦，已断使能'));
document.addEventListener('visibilitychange',()=>{if(document.hidden)baseStop('页面隐藏，已断使能');});
addEventListener('pagehide',()=>baseStop('页面关闭，已断使能'));
let feedbackBusy=false;
async function baseFeedback(){if(feedbackBusy||document.hidden)return;feedbackBusy=true;try{
 const d=await conReq('/api/base_status'),f=d.device,cmd=d.command;
 if(d.sub)applyBaseSub(d.sub);
 const tog=$('base-sub-toggle');if(tog)tog.disabled=globalStopped;
 be.disabled=baseEn||globalStopped;
 $('base-link').textContent=cmd.error?'指令提交异常：'+cmd.error:cmd.submitted_at?'最近提交：'+new Date(cmd.submitted_at*1000).toLocaleTimeString()+'（非设备确认）':'尚未提交底盘指令';
 $('base-feedback-time').textContent=f.received_at?'最近收到：'+new Date(f.received_at*1000).toLocaleTimeString()+' · '+(f.fresh?'有效':'已过期'):'尚未收到设备反馈';
 $('base-feedback').textContent=f.fresh&&f.feedback?`设备反馈：前进 ${f.feedback.vx.toFixed(3)} m/s · 左移 ${f.feedback.vy.toFixed(3)} m/s · 档位 ${f.feedback.gear}\n转向反馈 ${(f.feedback.angular_raw*0.01).toFixed(1)} °/s`:'实际速度未知 · '+(f.error||'反馈已过期');
}catch(e){$('base-link').textContent='控制服务不可达：'+e.message;$('base-feedback').textContent='实际速度未知';$('base-feedback-time').textContent='反馈状态未知';}finally{feedbackBusy=false;}}
baseFeedback();setInterval(baseFeedback,1000);
})();
})();
