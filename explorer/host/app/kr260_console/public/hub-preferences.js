/* One account setting, shared by all workbench pages and tabs. */
window.HubRefresh=(()=>{
 const key='aipc-refresh-ms',allowed=[500,1000,2000,5000,10000];let interval=1000,usage={bytes:0,requests:0,started:performance.now()},task=null,timer=null,enabled=()=>true,syncAt=0;
 try{const value=Number(localStorage.getItem(key));if(allowed.includes(value))interval=value}catch(e){}
 function apply(value){if(!allowed.includes(value))return;const changed=interval!==value;interval=value;try{localStorage.setItem(key,String(value))}catch(e){}if(changed){document.dispatchEvent(new CustomEvent('hub-refresh-change',{detail:value}));schedule(0)}label()}
 function label(){const el=document.getElementById('refresh-status');if(el)el.textContent=`每 ${interval/1000} 秒更新 · 请求 ${usage.requests} 次 · 接收 ${(usage.bytes/1024).toFixed(1)} KiB`}
 async function sync(){syncAt=Date.now();try{const r=await fetch('/api/v1/settings',{cache:'no-store'});if(r.ok)apply((await r.json()).refresh_interval_ms)}catch(e){}}
 function schedule(delay=interval){clearTimeout(timer);if(!task)return;timer=setTimeout(tick,delay)}
 async function tick(){const start=performance.now();try{if(enabled()&&!document.hidden)await task()}finally{schedule(Math.max(0,interval-(performance.now()-start)))}}
 function start(fn,isEnabled=()=>true){task=fn;enabled=isEnabled;schedule(interval)}
 function record(response,elapsed){usage.bytes+=Number(response.headers.get('Content-Length'))||0;usage.requests++;usage.last_ms=elapsed;label()}
 function stats(){return {...usage,interval_ms:interval,kib_per_second:usage.bytes/1024/Math.max(.001,(performance.now()-usage.started)/1000)}}
 window.addEventListener('storage',e=>{if(e.key===key)apply(Number(e.newValue))});document.addEventListener('visibilitychange',()=>{if(!document.hidden){sync();schedule(0)}});
 setInterval(()=>{if(!document.hidden&&enabled()&&Date.now()-syncAt>10000)sync()},10000);
 return {get interval(){return interval},apply,sync,start,record,stats};
})();
