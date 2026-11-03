(()=>{
 let pending=false,loaded=null;
 function library(){if(!loaded)loaded=new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='/vendor/mermaid.min.js';script.onload=()=>{mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'neutral',fontFamily:'system-ui, sans-serif',suppressErrorRendering:true});resolve()};script.onerror=()=>reject(Error('图表组件加载失败'));document.head.append(script)});return loaded}
 async function render(){
  if(pending)return;
  const blocks=Array.from(document.querySelectorAll('.article pre > code.language-mermaid')).filter(c=>!c.dataset.diagramHandled);
  if(!blocks.length)return;pending=true;
  try{await library();for(const code of blocks){code.dataset.diagramHandled='true';const container=document.createElement('div');container.className='md-diagram';container.textContent=code.textContent;code.parentElement.replaceWith(container);try{await mermaid.run({nodes:[container]})}catch(e){const pre=document.createElement('pre');pre.append(code);container.replaceWith(pre)}}}catch(e){console.warn('Markdown diagram renderer unavailable')}finally{pending=false}
 }
 new MutationObserver(render).observe(document.getElementById('main'),{childList:true,subtree:true});render();
})();
