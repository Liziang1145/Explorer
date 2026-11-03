if(new URL(location.href).searchParams.has('doc'))location.replace('/library.html'+location.search+location.hash);
const $=id=>document.getElementById(id);let services=[],signedIn=false,busy=false,jobId=null,pendingStop=null,timer;
function icon(name){const s=lucide.createElement(lucide.icons[name]);s.setAttribute('class','ui-icon');s.setAttribute('width','18');s.setAttribute('height','18');s.setAttribute('stroke-width','1.7');s.setAttribute('aria-hidden','true');return s}
function icons(root=document){root.querySelectorAll('[data-icon]').forEach(el=>{const svg=icon(el.dataset.icon);if(el.tagName==='I')el.replaceWith(svg);else{el.removeAttribute('data-icon');el.replaceChildren(svg)}})}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
try{if(localStorage.getItem('aipc-theme')==='dark')document.body.classList.add('dark')}catch(e){}
const sun=icon('Sun'),moon=icon('Moon');sun.classList.add('theme-sun');moon.classList.add('theme-moon');$('theme').append(sun,moon);$('theme').onclick=()=>{document.body.classList.toggle('dark');try{localStorage.setItem('aipc-theme',document.body.classList.contains('dark')?'dark':'light')}catch(e){}};
icons();function toast(s){$('toast').textContent=s;$('toast').classList.add('show');clearTimeout(timer);timer=setTimeout(()=>$('toast').classList.remove('show'),4000)}
async function request(path,data){const r=await fetch('/api/v1/'+path,data?{method:'POST',headers:{'Content-Type':'application/json','X-Hub-Client':'console'},body:JSON.stringify(data)}:{});const result=await r.json();if(!r.ok){if(r.status===401){signedIn=false;account()}throw Error(result.error||'请求失败')}return result}
function account(){$('account').querySelector('span').textContent=signedIn?'apex · 退出':'登录管理';$('auth-status').textContent=signedIn?'apex 已登录':'尚未登录'}
const defaults=[{id:'model',title:'千问 · 本地模型',description:'Strata 推理与对话服务',model:'qwen3.8-flash-next-iq3_s',url:'http://192.168.137.2:8080/',icon:'BrainCircuit'},{id:'dsh',title:'dsh · 智能体工作区',description:'任务编排、工具调用与智能体会话',url:'/api/v1/entry/dsh',icon:'Workflow'},{id:'documents',title:'墨阅 · 文档中心',description:'Markdown、公式、图片与共享分类',url:'/library.html',icon:'BookOpen',ready:true,managed:false}];
let renderSignature='';
function render(){
 const list=services.length?services:defaults;
 $('ready-count').textContent=signedIn?list.filter(s=>s.ready).length+' / 3 已就绪':'等待登录';
 const signature=JSON.stringify([list,signedIn,busy]);if(signature===renderSignature)return;renderSignature=signature;
 $('services').innerHTML=list.map(s=>{
  const state=!signedIn&&s.id!=='documents'?'登录后查看':s.ready?'运行中':s.state==='failed'?'启动失败':s.state==='active'||s.state==='activating'?'加载中':'已停止';
  const cls=s.ready?'ready':s.state==='failed'?'failed':s.state==='active'||s.state==='activating'?'loading':'';
  const details=s.id==='model'?(s.model||s.description):s.id==='dsh'?'智能体框架 · 独立启动与停止':'Markdown、公式、图片与共享分类';
  return `<article class="service-row"><div class="service-identity"><span class="service-icon" data-icon="${s.icon}"></span><div class="service-copy"><h2>${esc(s.title)}</h2><p title="${esc(details)}">${esc(details)}</p></div></div><span class="status-pill ${cls}">${state}</span><span class="service-endpoint">HTTP :${s.id==='model'?'8080':s.id==='dsh'?'3080':'8091'}</span><div class="service-actions">${s.managed===false?'<span class="control-note">文档模块 / 常驻服务</span>':`<button class="button primary" data-action="start" data-service="${s.id}" ${busy||s.ready?'disabled':''}><i data-icon="Play"></i>启动</button><button class="button secondary stop" data-action="stop" data-service="${s.id}" ${busy||signedIn&&s.state==='inactive'?'disabled':''}><i data-icon="Square"></i>停止</button>`}<a class="button entry" data-entry="${s.id}" href="${esc(s.url)}" ${s.id==='documents'?'':'target="_blank" rel="noopener"'} aria-disabled="${s.id!=='documents'&&signedIn&&!s.ready}">打开页面<i data-icon="ArrowUpRight"></i></a></div></article>`;
 }).join('');icons($('services'));
 $('services').querySelectorAll('[data-entry="dsh"]').forEach(a=>a.onclick=e=>{if(!signedIn){e.preventDefault();login()}});
 $('services').querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>{if(!signedIn)return login();if(b.dataset.action==='stop'){pendingStop=b.dataset.service;$('confirm-message').textContent=pendingStop==='model'?'仅停止模型服务，dsh 框架保持当前状态。正在进行的本地推理会中断。':'仅停止 dsh 框架，模型保持当前状态。正在进行的智能体任务会中断。';$('confirm-dialog').showModal()}else operate(b.dataset.service,'start')});
}
async function refresh(){try{const r=await request('services');services=r.services;busy=r.busy;signedIn=true;$('refresh-time').textContent=new Date().toLocaleTimeString('zh-CN',{hour12:false});account();render()}catch(e){if(!signedIn){services=[];busy=false;account();render()}else toast(e.message)}}
function login(){$('login-error').textContent='';$('login-dialog').showModal();$('password').focus()}
$('account').onclick=async()=>{if(!signedIn)return login();try{await request('logout',{});signedIn=false;services=[];account();render()}catch(e){toast(e.message)}};
$('login-cancel').onclick=()=>$('login-dialog').close();$('confirm-cancel').onclick=()=>$('confirm-dialog').close();$('confirm-form').onsubmit=e=>{e.preventDefault();$('confirm-dialog').close();operate(pendingStop,'stop')};
$('login-form').onsubmit=async e=>{e.preventDefault();$('login-submit').disabled=true;try{await request('login',{username:$('username').value,password:$('password').value});$('password').value='';signedIn=true;$('login-dialog').close();await refresh()}catch(e){$('login-error').textContent=e.message}finally{$('login-submit').disabled=false}};
async function operate(service,action){busy=true;render();$('operation').className='running';$('operation').textContent='正在提交操作…';try{const r=await request('services/'+service+'/'+action,{});jobId=r.job_id;pollJob()}catch(e){busy=false;$('operation').className='failed';$('operation').textContent=e.message;render()}}
async function pollJob(){if(!jobId)return;try{const j=await request('jobs/'+jobId);$('operation').className=j.state;$('operation').textContent=j.message;if(j.state==='running')setTimeout(pollJob,1200);else{jobId=null;await refresh()}}catch(e){jobId=null;busy=false;$('operation').textContent=e.message;$('operation').className='failed';render()}}
$('refresh').onclick=()=>signedIn?refresh():login();account();render();refresh();HubRefresh.sync();HubRefresh.start(refresh,()=>signedIn&&!busy);
