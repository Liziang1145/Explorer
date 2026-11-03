/* Single navigation definition for every AIPC page. Loaded before page scripts. */

(()=>{

 const items=[['/','服务总览','Boxes'],['/aipc.html','AIPC 仪表盘','MonitorCog'],['/dashboard.html','KR260 仪表盘','ChartNoAxesCombined'],['/flows.html','通信链路 / 历史','Workflow'],['/simulator.html','机器人控制台','Gamepad2'],['/io.html','IO 状态','Cable'],['/switch.html','交换机配置','Network'],['/docker.html','Docker 管理','Container'],['/remote.html','远程桌面','MonitorUp'],['/ssh.html','SSH 终端','SquareTerminal'],['/files.html','文件管理','FolderOpen'],['/library.html','文档中心','BookOpen'],['/settings.html','设置','Settings2']];



 items.push(['/pose-capture.html','姿态采集','Database']);

 items.splice(items.findIndex(x=>x[0]==='/switch.html')+1,0,['/bridges.html','无线网桥','RadioTower']);

 const aside=document.getElementById('aipc-sidebar');if(!aside)return;document.body.classList.add('aipc-shell');

 const extra=aside.querySelector('[data-shell-extra]');

 const brand=document.createElement('a');brand.className='brand';brand.href='/';brand.innerHTML='<span class="brand-icon">A</span><span>AIPC 工作台<small>LOCAL OPERATIONS</small></span>';

 const nav=document.createElement('nav');nav.className='shell-navigation';nav.setAttribute('aria-label','主导航');

 let path=location.pathname==='/index.html'?'/':location.pathname;if(path==='/docker-help.html')path='/docker.html';if(path==='/pose-viz.html')path='/pose-capture.html';

 for(const [href,label,icon] of items){const a=document.createElement('a');a.className='nav-item'+(path===href?' active':'');a.href=href;if(path===href)a.setAttribute('aria-current','page');const i=document.createElement('i');i.dataset.icon=icon;const text=document.createElement('span');text.textContent=label;a.append(i,text);nav.append(a);}

 const external=document.createElement('a');external.className='nav-item';external.href='http://192.168.254.1:8085/';external.target='_blank';external.rel='noopener noreferrer';external.dataset.kr260ConsoleEntry='1';external.textContent='KR260 本地控制台 ↗';nav.append(external);

 const foot=document.createElement('div');foot.className='side-foot';foot.innerHTML='<span>AIPC · 系统管理</span><code id="local-endpoint"></code>';foot.querySelector('code').textContent=location.host;

 aside.replaceChildren(brand,nav);if(extra)aside.append(extra);aside.append(foot);

 const toggle=document.createElement('button');toggle.className='shell-menu';toggle.type='button';toggle.textContent='☰';toggle.setAttribute('aria-label','展开导航');toggle.setAttribute('aria-controls','aipc-sidebar');toggle.setAttribute('aria-expanded','false');

 const shade=document.createElement('button');shade.className='shell-shade';shade.type='button';shade.setAttribute('aria-label','关闭导航');

 const set=open=>{document.body.classList.toggle('shell-open',open);toggle.setAttribute('aria-expanded',String(open));toggle.setAttribute('aria-label',open?'关闭导航':'展开导航');if(matchMedia('(max-width: 800px)').matches)aside.inert=!open;else aside.inert=false;};

 toggle.onclick=()=>set(!document.body.classList.contains('shell-open'));shade.onclick=()=>{set(false);toggle.focus();};document.addEventListener('keydown',e=>{if(e.key==='Escape'){set(false);toggle.focus();}});nav.addEventListener('click',e=>{if(e.target.closest('a'))set(false);});addEventListener('resize',()=>set(false));document.body.append(toggle,shade);set(false);

 document.addEventListener('DOMContentLoaded',()=>{if(window.lucide?.createElement)nav.querySelectorAll('[data-icon]').forEach(n=>{const icon=lucide.icons[n.dataset.icon];if(icon)n.replaceChildren(lucide.createElement(icon));});});

})();

