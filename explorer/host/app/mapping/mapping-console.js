'use strict';
(()=>{
 const module=document.querySelector('.map-module').dataset.module;
 const link=document.querySelector('.shell-navigation a[href="/monitor.html"]');if(link){link.classList.add('active');link.setAttribute('aria-current','page');}
 const icons=()=>{if(window.lucide?.createElement)document.querySelectorAll('.map-tabs [data-icon]').forEach(n=>{const i=lucide.icons[n.dataset.icon];if(i)n.replaceChildren(lucide.createElement(i));});};icons();
 let busy=false;async function health(){if(busy||document.hidden)return;busy=true;const error=document.getElementById('workspace-error');try{
  const r=await fetch('/api/v1/session',{cache:'no-store',signal:AbortSignal.timeout(5000)});if(!r.ok)throw Error('请先通过右上角“管理登录”登录 AIPC 工作台。');document.getElementById('workspace-session').textContent='apex · 已登录';
  const res=await fetch('/hub/api/status',{cache:'no-store',signal:AbortSignal.timeout(10000)});const d=await res.json();if(!res.ok)throw Error(d.error||'后台连接失败');const target=document.getElementById('workspace-health');target.replaceChildren();
  for(const [key,label]of [['mapping','建图'],['semantic','场景融合'],['navigation','导航']]){const s=d.modules?.[key],el=document.createElement('span');el.className=s?.reachable?'':'off';const state={idle:'空闲',offline:'历史快照',no_live_input:'无实时输入',active:'正在运行',stale:'数据过期'}[s?.state]||s?.state||'未知';el.textContent=label+' · '+(s?.reachable?state:'不可达');el.title=s?.message||'服务可访问不等于采集已启动';target.append(el);}error.hidden=true;
 }catch(e){document.getElementById('workspace-session').textContent='连接待确认';error.textContent=e.message;error.hidden=false;document.getElementById('workspace-health').textContent='状态未确认';}finally{busy=false;}}
 health();setInterval(health,5000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)health();});
})();

// Acceptance evidence tab, shared by existing native mapping modules.
(()=>{const nav=document.querySelector('.map-tabs');if(nav&&!nav.querySelector('a[href="/monitor-metrics.html"]')){const a=document.createElement('a');a.className='map-tab';a.href='/monitor-metrics.html';a.textContent='验收测量';nav.append(a);}})();

(()=>{const nav=document.querySelector('.map-tabs');if(nav&&!nav.querySelector('a[href="/monitor-vr-cloud.html"]')){const a=document.createElement('a');a.className='map-tab'+(location.pathname==='/monitor-vr-cloud.html'?' active':'');a.href='/monitor-vr-cloud.html';a.textContent='VR 场景图传';nav.append(a);}})();
