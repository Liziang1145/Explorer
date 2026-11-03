/* Shared KR260 views: same session and design system as the service workbench. */
const $=id=>document.getElementById(id),page=document.body.dataset.page,dashboardPage=page==='dashboard'||page==='aipc',target=page==='aipc'?'aipc':'kr260';
const state={signedIn:false,loading:false,resources:{},services:[],comms:{},io:{},list:'processes',sort:'cpu_percent',descending:true,paging:1,query:'',selectedFrame:null,drafts:new Map(),gpioBusy:new Set(),gpioSignature:'',schema:null};let toastTimer;
function esc(v){return String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function icon(name){const el=lucide.createElement(lucide.icons[name]||lucide.icons.Circle);el.setAttribute('class','ui-icon');el.setAttribute('width','18');el.setAttribute('height','18');el.setAttribute('stroke-width','1.7');el.setAttribute('aria-hidden','true');return el}
function icons(root=document){root.querySelectorAll('[data-icon]').forEach(el=>{if(el.tagName==='I')el.replaceWith(icon(el.dataset.icon));else{const name=el.dataset.icon;el.removeAttribute('data-icon');el.replaceChildren(icon(name))}})}
try{document.body.classList.toggle('dark',localStorage.getItem('aipc-theme')==='dark')}catch(e){}
const sun=icon('Sun'),moon=icon('Moon');sun.classList.add('theme-sun');moon.classList.add('theme-moon');$('theme').append(sun,moon);$('theme').onclick=()=>{document.body.classList.toggle('dark');try{localStorage.setItem('aipc-theme',document.body.classList.contains('dark')?'dark':'light')}catch(e){}};icons();
function toast(text){$('toast').textContent=text;$('toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('show'),4500)}
function account(){document.body.classList.toggle('signed-out',!state.signedIn);$('account').querySelector('span').textContent=state.signedIn?'apex · 退出':'登录管理';if(!state.signedIn){$('board-state').textContent='等待登录';$('board-state').className='status-pill'}}
async function request(path,data){const started=performance.now(),r=await fetch('/api/v1/'+path,data===undefined?{cache:'no-store'}:{method:'POST',headers:{'Content-Type':'application/json','X-Hub-Client':'console'},body:JSON.stringify(data)});const result=await r.json();HubRefresh.record(r,performance.now()-started);if(!r.ok){if(r.status===401){state.signedIn=false;account()}throw Error(result.error||'请求失败')}return result}
function login(){$('login-error').textContent='';if(!$('login-dialog').open)$('login-dialog').showModal();$('password').focus()}
$('account').onclick=async()=>{if(!state.signedIn)return login();try{await request('logout',{});state.signedIn=false;state.drafts.clear();account();location.reload()}catch(e){toast(e.message)}};
$('login-cancel').onclick=()=>$('login-dialog').close();$('login-form').onsubmit=async e=>{e.preventDefault();$('login-submit').disabled=true;try{await request('login',{username:$('username').value,password:$('password').value});$('password').value='';state.signedIn=true;account();$('login-dialog').close();await HubRefresh.sync();await refresh()}catch(e){$('login-error').textContent=e.message}finally{$('login-submit').disabled=false}};
const bytes=n=>n==null?'—':n>=1024**3?(n/1024**3).toFixed(2)+' GiB':n>=1024**2?(n/1024**2).toFixed(1)+' MiB':n>=1024?(n/1024).toFixed(1)+' KiB':n+' B';
const pct=n=>n==null?'—':n.toFixed(1)+'%',time=n=>n?new Date(n*1000).toLocaleTimeString('zh-CN',{hour12:false}):'—';
function duration(n){if(n==null)return '—';const d=Math.floor(n/86400),h=Math.floor(n%86400/3600),m=Math.floor(n%3600/60);return `${d?d+' 天 ':''}${h} 小时 ${m} 分钟`}
function pill(text,cls=''){return `<span class="status-pill ${cls}">${esc(text)}</span>`}
function percentBar(n){return `<div class="meter"><span style="width:${Math.min(100,Math.max(0,n||0))}%"></span></div>`}
function empty(text,columns=1){return `<tr><td colspan="${columns}" class="empty-state">${esc(text)}</td></tr>`}
function setBoard(ok,error){$('board-state').textContent=ok?(target==='aipc'||page==='settings'||page==='remote'||page==='ssh'?'AIPC 在线':'板端在线'):'采集不可达';$('board-state').className='status-pill '+(ok?'ready':'failed');$('page-error').hidden=ok;$('page-error').textContent=error||'';if(!ok){$('board-info').textContent='显示内容可能已过期，请以最后采集时间为准';disableGPIO()}}
function disableGPIO(){if(page==='io')$('gpio-lines').querySelectorAll('button').forEach(b=>b.disabled=true)}
async function refresh(){
 if(!state.signedIn)return login();if(state.loading)return;state.loading=true;$('refresh').disabled=true;
 try{
  if(dashboardPage){
   const snapshot=await request(target+'/snapshot'+(page==='dashboard'?'?frames='+($('packet-details').open?'1':'0'):''));
   state.resources=snapshot.resources;state.services=snapshot.services;renderResources();
   if(page==='dashboard'){state.comms=snapshot.communications;renderCommunications()}else renderGPUs();
   renderList();if(state.resources.collector_error)throw Error(state.resources.collector_error);
   $('board-info').textContent=`${state.resources.host?.hostname||'KR260'} · Linux ${state.resources.host?.kernel||'—'} · 运行 ${duration(state.resources.host?.uptime)}`;
   $('sample-time').textContent='采集于 '+time(state.resources.sampled_at);
  }else if(page==='io'){
   state.io=await request('kr260/io');if(state.io.collector_error)throw Error(state.io.collector_error);renderIO();$('board-info').textContent='KR260 · 192.168.137.224 · 内核接口实时采集';$('sample-time').textContent='采集于 '+time(state.io.sampled_at);
  }else if(page==='settings'){
   if(!state.settingsLoaded){state.settingsLoaded=true;await loadSettings();await measureBandwidth()}$('board-info').textContent='AIPC · 共享刷新设置';$('sample-time').textContent='设置已同步';
  }else if(page==='ssh'){
   const r=await request('ssh/hosts');document.dispatchEvent(new CustomEvent('ssh-hosts',{detail:r}));$('board-info').textContent='AIPC / KR260 · 独立 SSH 会话';$('sample-time').textContent='连接时校验 SSH 主机公钥';
  }else if(page==='remote'){
   const r=await request('rdp/status');document.dispatchEvent(new CustomEvent('rdp-status',{detail:r}));$('board-info').textContent='AIPC · '+r.gateway;$('sample-time').textContent=r.ready?'RDP 网关就绪':'RDP 网关待启动';
  }else{
   state.comms=await request('kr260/communications');renderProvider('switch',state.comms.switch);$('sample-time').textContent='同步于 '+new Date().toLocaleTimeString('zh-CN',{hour12:false});
  }
  setBoard(true);
 }catch(e){setBoard(false,e.message)}finally{state.loading=false;$('refresh').disabled=false}
}
function renderResources(){const r=state.resources;
 for(const [key,obj] of [['cpu',r.cpu],['memory',r.memory],['disk',(r.disks||[]).find(d=>d.mount==='/')]]){
  $(key+'-value').textContent=pct(obj?.percent);$(key+'-bar').style.width=(obj?.percent||0)+'%';
  $(key+'-note').textContent=key==='cpu'?`${r.cpu?.cores?.length||0} 个核心 · 按全核归一化`:obj?`${bytes(obj.used)} / ${bytes(obj.total)} · 可用 ${bytes(obj.available)}`:'未发现根分区数据';
 }
 $('cpu-cores').innerHTML=(r.cpu?.cores||[]).map(c=>`<div class="core-item"><div><span>${esc(c.id.toUpperCase())}</span><strong>${pct(c.percent)}</strong></div>${percentBar(c.percent)}</div>`).join('');
 $('cpu-load').textContent='系统负载 1 / 5 / 15 分钟：'+(r.cpu?.load||[]).join(' / ')+` · Swap ${bytes(r.memory?.swap_used)} / ${bytes(r.memory?.swap_total)}`;
 $('disks').innerHTML=(r.disks||[]).map(d=>`<div class="disk-row"><div><span class="mono">${esc(d.mount)}</span><strong>${pct(d.percent)}</strong></div>${percentBar(d.percent)}<small>${esc(d.device)} · ${esc(d.filesystem)} · ${bytes(d.used)} / ${bytes(d.total)} · 可用 ${bytes(d.available)}</small></div>`).join('');
}
function renderGPUs(){const gpus=state.resources.gpus||[];$('gpu-devices').innerHTML=gpus.map(g=>{
 const vram=g.vram_total?g.vram_used/g.vram_total*100:null,gtt=g.gtt_total?g.gtt_used/g.gtt_total*100:null;
 return `<article class="gpu-card"><div class="gpu-heading"><span class="summary-icon" data-icon="Cpu"></span><div><h3>${esc(g.name)}</h3><p>${esc(g.pci)} · ${esc(g.driver)} · ${esc(g.memory_kind)}</p></div>${pill(g.gpu_percent==null?'指标未提供':'可实时采集',g.gpu_percent!=null?'ready':'')}</div><div class="gpu-metrics"><div><span>GPU 使用率</span><strong>${pct(g.gpu_percent)}</strong>${percentBar(g.gpu_percent)}</div><div><span>VRAM 占用</span><strong>${pct(vram)}</strong>${percentBar(vram)}<small>${bytes(g.vram_used)} / ${bytes(g.vram_total)}</small></div><div><span>GTT 共享内存</span><strong>${pct(gtt)}</strong>${percentBar(gtt)}<small>${bytes(g.gtt_used)} / ${bytes(g.gtt_total)}</small></div></div><div class="gpu-extra"><span>显存忙碌 ${pct(g.memory_busy_percent)}</span><span>温度 ${g.temperature_c==null?'—':g.temperature_c.toFixed(1)+' °C'}</span><span>功耗 ${g.power_w==null?'未提供':g.power_w.toFixed(1)+' W'}</span><span>核心频率 ${g.clock_mhz==null?'未提供':Math.round(g.clock_mhz)+' MHz'}</span></div></article>`
 }).join('')||'<div class="empty-state">尚未采集到 GPU 设备</div>';icons($('gpu-devices'))}
async function loadSettings(){const cfg=await request('settings');state.intervalCandidate=cfg.refresh_interval_ms;renderIntervals();$('settings-saved').textContent='当前生效：'+cfg.refresh_interval_ms/1000+' 秒'}
function renderIntervals(){$('interval-options').innerHTML=[500,1000,2000,5000,10000].map(ms=>`<button class="interval-option ${state.intervalCandidate===ms?'selected':''}" data-interval="${ms}" aria-pressed="${state.intervalCandidate===ms}"><strong>${ms/1000}<small>秒</small></strong><span>${ms===500?'最快':ms===1000?'默认':'低频'}</span></button>`).join('');$('interval-options').querySelectorAll('button').forEach(b=>b.onclick=()=>{state.intervalCandidate=Number(b.dataset.interval);renderIntervals();renderBandwidth()})}
async function measureBandwidth(){const b=$('bandwidth-refresh');b.disabled=true;try{state.bandwidth=await request('settings/bandwidth');renderBandwidth()}catch(e){toast(e.message)}finally{b.disabled=false}}
function renderBandwidth(){const data=state.bandwidth;if(!data)return;const interval=state.intervalCandidate||HubRefresh.interval;
 $('bandwidth-rows').innerHTML=data.profiles.map(p=>{if(p.error)return `<tr><td>${esc(p.title)}</td><td colspan="5">${esc(p.error)}</td></tr>`;const rate=p.gzip_bytes*1000/interval;return `<tr><td>${esc(p.title)}</td><td class="mono">${bytes(p.json_bytes)}</td><td class="mono">${bytes(p.gzip_bytes)}</td><td class="mono">${bytes(rate)}/s <span class="subtext">${(rate*8/1e6).toFixed(3)} Mbit/s</span></td><td class="mono">${bytes(rate*3600)}</td><td class="mono">${bytes(p.gzip_bytes*2)}/s <span class="subtext">${(p.gzip_bytes*16/1e6).toFixed(3)} Mbit/s</span></td></tr>`}).join('');$('bandwidth-basis').textContent=data.basis+' · '+time(data.measured_at);$('bandwidth-live').textContent='按 '+interval/1000+' 秒计算；两个仪表盘同时打开时，将对应带宽相加。RDP 使用持续图形流，不受刷新间隔限制。'
}
function renderProvider(name,item){const el=$(name+'-provider');if(!el)return;item=item||{state:'not-integrated',data:{}};
 const label={'not-integrated':'未接入','active':'通信正常','idle':'空闲','error':'通信异常','stale':'上报过期'}[item.state]||item.state;
 el.innerHTML=pill(label,item.state==='active'?'ready':item.state==='error'?'failed':'')+`<p class="muted">${item.updated_at?'最近上报 '+time(item.updated_at):'已预留接入接口 · 尚未收到设备状态'}${item.message?' · '+esc(item.message):''}</p>`+`<div class="provider-data">${Object.entries(item.data||{}).map(([k,v])=>`<div><span>${esc(k)}</span><code>${esc(typeof v==='object'?JSON.stringify(v):v)}</code></div>`).join('')}</div>`;
}
function renderCommunications(){const a=state.comms.aipc||{};const label={'active':'近期有数据','stale':'数据已过期','no-data':'尚无业务数据'}[a.state]||'采集不可用';$('aipc-state').textContent=label;$('aipc-state').className='status-pill '+(a.state==='active'?'ready':'');
 $('aipc-note').textContent=`${a.capture==='active'?'被动采集运行中':a.capture||'采集未启动'} · UDP ${(a.ports||[]).join(' / ')}${a.age_seconds!=null?' · 最近 '+a.age_seconds.toFixed(1)+' 秒前':''}`;
 $('aipc-stats').innerHTML=`<div><span>接收 / 发送帧</span><strong>${a.counts?.rx||0} / ${a.counts?.tx||0}</strong></div><div><span>接收 / 发送 · 帧每秒</span><strong>${a.rx_rate||0} / ${a.tx_rate||0}</strong></div><div><span>无效 / 未识别帧</span><strong>${a.counts?.invalid||0}</strong></div>`;
 $('protocol-revision').textContent=a.revision||'—';renderPacket();renderProvider('lidar',state.comms.lidar);renderProvider('antenna',state.comms.antenna);
 if(a.reload_error)toast('协议更新失败，继续使用有效配置：'+a.reload_error);
}
function frameKey(f){return f.time+':'+f.direction}
function renderPacket(){const frames=state.comms.aipc?.frames||[];if(state.selectedFrame){const updated=frames.find(f=>frameKey(f)===frameKey(state.selectedFrame));if(updated)state.selectedFrame=updated}let f=state.selectedFrame||frames[0];
 $('packet-history').innerHTML=frames.map(item=>`<button data-frame="${esc(frameKey(item))}" class="${f&&frameKey(f)===frameKey(item)?'active':''}">${time(item.time)} · ${item.direction.toUpperCase()} · ${item.size}B</button>`).join('');
 $('packet-history').querySelectorAll('button').forEach(b=>b.onclick=()=>{state.selectedFrame=frames.find(item=>frameKey(item)===b.dataset.frame);renderPacket()});
 $('packet-description').textContent=f?`${state.selectedFrame?'已固定数据帧':'跟随最新帧'} · ${f.source}:${f.source_port} → ${f.destination}:${f.destination_port} · ${f.decoded?.title||'解析失败'}`:'尚未观测到 AIPC 与 KR260 的业务 UDP 数据';
 $('packet-fields').innerHTML=f?.decoded?.fields?.length?f.decoded.fields.map(v=>`<tr><td>${esc(v.label)}</td><td><code>${esc(v.name)}</code></td><td><pre>${esc(typeof v.value==='object'?JSON.stringify(v.value,null,2):v.value)}</pre></td><td>${esc(v.unit||'—')}</td></tr>`).join(''):empty(f?.error||'暂无可解析的字段',4);
 const warning=[f?.error,f?.decoded?.warning,f?.decoded?.checksum==='invalid'?'CRC 校验失败，以下帧数据不可信':''].filter(Boolean).join(' ');$('packet-warning').hidden=!warning;$('packet-warning').textContent=warning;$('packet-hex').textContent=(f?.hex||'').match(/.{1,64}/g)?.join('\n')||'暂无原始数据';
}
function renderList(){const isProc=state.list==='processes',q=state.query.toLowerCase();let rows=isProc?(state.resources.processes||[]):state.services;
 $('process-count').textContent=state.resources.processes?.length||0;$('service-count').textContent=state.services.length;
 rows=rows.filter(p=>(isProc?[p.pid,p.name,p.user,p.state]:[p.unit,p.description,p.active,p.enabled]).some(v=>String(v||'').toLowerCase().includes(q)));
 if(isProc)rows=[...rows].sort((a,b)=>{const av=a[state.sort]??-1,bv=b[state.sort]??-1;return (typeof av==='string'?av.localeCompare(bv):av-bv)*(state.descending?-1:1)});else rows=[...rows].sort((a,b)=>a.unit.localeCompare(b.unit));
 const part=rows,scroll=$('process-scroll'),top=scroll.scrollTop,left=scroll.scrollLeft;
 $('process-table').hidden=!isProc;$('service-table').hidden=isProc;
 if(isProc)$('process-rows').innerHTML=part.map(p=>`<tr><td class="mono">${p.pid}</td><td><strong>${esc(p.name)}</strong></td><td>${esc(p.user)} <span class="subtext">${esc(p.state)}</span></td><td class="numeric">${p.cpu_percent==null?'—':p.cpu_percent.toFixed(1)}</td><td class="numeric">${bytes(p.rss)}<span class="subtext">${p.memory_percent}%</span></td><td class="mono">${p.threads}</td><td><span class="mono">PPID ${p.ppid} · NI ${p.nice}</span><span class="subtext">运行 ${duration(p.age_seconds)}</span></td></tr>`).join('')||empty('没有匹配的进程',7);
 else $('service-rows').innerHTML=part.map(s=>`<tr><td><code>${esc(s.unit)}</code></td><td>${esc(s.description||'—')}</td><td>${pill(s.active,s.active==='active'?'ready':s.active==='failed'?'failed':'')}</td><td>${esc(s.sub)}</td><td>${esc(s.enabled)}</td><td>${esc(s.load)}</td></tr>`).join('')||empty('没有匹配的服务',6);
 scroll.scrollTop=top;scroll.scrollLeft=left;$('list-note').textContent=`共 ${rows.length} 项 · 上下滚动查看全部 · `+(isProc?'进程 CPU 100% 表示一个核心。':'系统服务只读展示；模型和 dsh 启停请返回服务总览。');
}
function stats(item){return `${item.statistics?.rx?.packets||0} / ${item.statistics?.tx?.packets||0}`}
function portData(values){return '<div class="port-data">'+values.map(([k,v])=>`<div><span>${esc(k)}</span><strong>${esc(v)}</strong></div>`).join('')+'</div>'}
function renderIO(){const io=state.io;
 $('ethernet-ports').innerHTML=(io.ethernet||[]).map(n=>`<article class="port-card ${n.link?'connected':''}"><div class="port-heading"><div class="port-identity"><i data-icon="EthernetPort"></i><div><strong>${n.port}${n.management?' · 管理口':''}</strong><small>${esc(n.interface||'未枚举')}</small></div></div>${pill(n.link?'已连接':n.available?'无链路':'未枚举',n.link?'ready':'')}</div>${portData([['协商速率',n.speed_mbps?n.speed_mbps+' Mbps':'—'],['双工',n.duplex==='full'?'全双工':n.duplex==='half'?'半双工':'—'],['状态',n.state||'—'],['收 / 发包',stats(n)]])}</article>`).join('');
 $('can-ports').innerHTML=(io.can||[]).map(n=>`<article class="port-card"><div class="port-heading"><div class="port-identity"><i data-icon="Waypoints"></i><div><strong>${esc(n.interface)}</strong><small>物理接线：待确认</small></div></div>${pill(n.up?'接口已启用':n.available?'接口未启用':'未枚举',n.up?'ready':'')}</div>${portData([['配置速率',n.bitrate?n.bitrate/1000+' kbit/s':'未配置'],['控制器状态',n.state||'—'],['收 / 发帧',stats(n)],['总线错误 TX / RX',(n.bus_error?.tx??'—')+' / '+(n.bus_error?.rx??'—')]])}</article>`).join('');
 $('dp-ports').innerHTML=(io.dp||[]).map(d=>`<div class="device-row"><i data-icon="Monitor"></i><div><h3>${esc(d.connector)}</h3><p>显示输出 ${esc(d.enabled||'—')}<br>支持模式 ${esc(d.modes?.join(' · ')||'无 EDID 模式')}</p></div>${pill(d.status==='connected'?'已连接':'未连接',d.status==='connected'?'ready':'')}</div>`).join('')||'<p class="empty-state">未枚举 DP 接口</p>';
 $('usb-ports').innerHTML=(io.usb||[]).map(d=>`<div class="device-row"><i data-icon="Usb"></i><div><h3>${esc(d.product)}</h3><p>${esc(d.manufacturer)} · ${esc(d.id)} · ${esc(d.vendor)}:${esc(d.product_id)}${d.class==='09'?' · USB Hub':''}<br>协商速率 ${d.speed_mbps!=null?d.speed_mbps+' Mbps':'未知'}</p></div>${pill(d.authorized?'已连接':'未授权',d.authorized?'ready':'')}</div>`).join('')||'<p class="empty-state">暂无 USB 设备</p>';
 icons($('ethernet-ports'));icons($('can-ports'));icons($('dp-ports'));icons($('usb-ports'));renderGPIO(io.gpio);
}
function renderGPIO(g){g=g||{available:false,lines:[]};state.io.gpio=g;$('gpio-chip').textContent=g.chip||'未枚举';$('gpio-unavailable').hidden=g.available;$('gpio-unavailable').textContent=g.message||'J18 GPIO 暂不可用';
 const signature=JSON.stringify([g.available,(g.lines||[]).map(({lease_remaining,...rest})=>rest),[...state.drafts],[...state.gpioBusy]]);if(signature===state.gpioSignature)return;state.gpioSignature=signature;
 $('gpio-lines').innerHTML=(g.lines||[]).map(l=>{const d=state.drafts.get(l.offset)||{direction:l.direction,value:l.value??0};const disabled=!l.editable||state.gpioBusy.has(l.offset);const lock=disabled?'disabled':'';
  return `<tr><td><strong>${esc(l.name)}</strong><span class="subtext">偏移 ${l.offset}</span></td><td>${pill(l.busy?'其他服务占用':l.owned?'工作台独占':'空闲',l.busy?'loading':l.owned?'ready':'')}<span class="subtext">${esc(l.consumer||'无占用者')}</span></td><td>${l.direction==='output'?'输出':'输入'}</td><td><span class="value-level ${l.value===1?'high':''}">${l.value==null?'不可读':l.value?'高 · 1':'低 · 0'}</span></td><td><div class="segmented" role="group" aria-label="${esc(l.name)}方向"><button data-gpio="${l.offset}" data-direction="input" class="${d.direction==='input'?'selected':''}" aria-pressed="${d.direction==='input'}" ${lock}>输入</button><button data-gpio="${l.offset}" data-direction="output" class="${d.direction==='output'?'selected':''}" aria-pressed="${d.direction==='output'}" ${lock}>输出</button></div></td><td><div class="segmented" role="group" aria-label="${esc(l.name)}电平">${[0,1].map(v=>`<button data-gpio="${l.offset}" data-value="${v}" class="${d.value===v?'selected':''}" aria-pressed="${d.value===v}" ${disabled||d.direction==='input'?'disabled':''}>${v?'高':'低'}</button>`).join('')}</div></td><td><button class="button secondary" data-apply="${l.offset}" ${lock}>${state.gpioBusy.has(l.offset)?'提交中':'应用'}</button></td></tr>`;
 }).join('');
 $('gpio-lines').querySelectorAll('[data-gpio]').forEach(b=>b.onclick=()=>{const i=Number(b.dataset.gpio),line=g.lines.find(l=>l.offset===i);const d=state.drafts.get(i)||{direction:line.direction,value:line.value??0};if(b.dataset.direction)d.direction=b.dataset.direction;else d.value=Number(b.dataset.value);state.drafts.set(i,d);renderGPIO(g)});
 $('gpio-lines').querySelectorAll('[data-apply]').forEach(b=>b.onclick=async()=>{const i=Number(b.dataset.apply),line=g.lines.find(l=>l.offset===i),draft=state.drafts.get(i)||{direction:line.direction,value:line.value??0};state.gpioBusy.add(i);renderGPIO(g);try{const result=await request('kr260/gpio',{offset:i,...draft});state.drafts.delete(i);state.io.gpio=result;toast(`J18_${i+1} 已设置为${draft.direction==='input'?'输入并释放':'输出 '+draft.value}`)}catch(e){toast(e.message)}finally{state.gpioBusy.delete(i);state.gpioSignature='';try{renderGPIO(await request('kr260/gpio'))}catch(e){disableGPIO();setBoard(false,e.message)}}});
}
if(dashboardPage){
 for(const type of ['processes','services'])$('tab-'+type).onclick=()=>{state.list=type;state.paging=1;for(const t of ['processes','services']){$('tab-'+t).classList.toggle('active',t===type);$('tab-'+t).setAttribute('aria-selected',t===type)}renderList()};
 $('list-search').oninput=e=>{state.query=e.target.value;$('process-scroll').scrollTop=0;renderList()};
 document.querySelectorAll('[data-sort]').forEach(b=>b.onclick=()=>{state.descending=state.sort===b.dataset.sort?!state.descending:b.dataset.sort!=='name';state.sort=b.dataset.sort;state.paging=1;document.querySelectorAll('[data-sort]').forEach(x=>x.closest('th').setAttribute('aria-sort',x===b?(state.descending?'descending':'ascending'):'none'));renderList()});
}
if(page==='dashboard'){
 $('packet-live').onclick=()=>{state.selectedFrame=null;renderPacket()};$('packet-details').ontoggle=()=>{if(state.signedIn)refresh()};
 $('protocol-edit').onclick=async()=>{try{state.schema=await request('kr260/protocols');$('schema-editor').value=JSON.stringify(state.schema.config,null,2);$('schema-version').textContent=state.schema.revision+' · SHA256 '+state.schema.sha256.slice(0,12);$('schema-error').textContent=state.schema.reload_error||'';$('protocol-dialog').showModal()}catch(e){toast(e.message)}};
 $('schema-close').onclick=()=>$('protocol-dialog').close();$('schema-import').onclick=()=>$('schema-file').click();$('schema-file').onchange=async e=>{const f=e.target.files[0];if(!f)return;if(f.size>65536){$('schema-error').textContent='协议文件最大 64 KiB';return}try{$('schema-editor').value=JSON.stringify(JSON.parse(await f.text()),null,2);$('schema-error').textContent='导入完成，保存后才会生效'}catch(e){$('schema-error').textContent='无效 JSON 文件'}$('schema-file').value=''};
 $('schema-export').onclick=()=>{try{const text=JSON.stringify(JSON.parse($('schema-editor').value),null,2),url=URL.createObjectURL(new Blob([text],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='aipc-protocols.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){$('schema-error').textContent='JSON 格式无效'}};
 $('schema-save').onclick=async()=>{$('schema-save').disabled=true;try{const cfg=JSON.parse($('schema-editor').value);await request('kr260/protocols',cfg);$('protocol-dialog').close();state.selectedFrame=null;toast('协议已热更新');await refresh()}catch(e){$('schema-error').textContent=e.message}finally{$('schema-save').disabled=false}};
}
if(page==='settings'){
 $('settings-save').onclick=async()=>{$('settings-save').disabled=true;try{const cfg=await request('settings',{refresh_interval_ms:state.intervalCandidate});HubRefresh.apply(cfg.refresh_interval_ms);$('settings-saved').textContent='已保存：每 '+cfg.refresh_interval_ms/1000+' 秒更新';renderBandwidth();toast('刷新设置已应用到所有管理页面')}catch(e){toast(e.message)}finally{$('settings-save').disabled=false}};
 $('bandwidth-refresh').onclick=measureBandwidth;
}
$('refresh').onclick=refresh;account();request('session').then(async()=>{state.signedIn=true;account();await HubRefresh.sync();refresh()}).catch(()=>{});
HubRefresh.start(refresh,()=>state.signedIn&&page!=='settings'&&page!=='remote'&&page!=='ssh');
if(page==='io')setInterval(async()=>{if(!state.signedIn||document.hidden)return;const offsets=(state.io.gpio?.lines||[]).filter(l=>l.owned).map(l=>l.offset);if(offsets.length)try{await request('kr260/gpio/renew',{offsets})}catch(e){toast('GPIO 续约失败：'+e.message)}},15000);
document.addEventListener('visibilitychange',()=>{if(!document.hidden&&state.signedIn)refresh()});
