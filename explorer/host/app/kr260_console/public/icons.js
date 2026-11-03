(()=>{
 const svg=(name)=>{const node=lucide.icons[name];if(!node)return null;const element=lucide.createElement(node);for(const [key,value] of Object.entries({class:'ui-icon',width:18,height:18,'stroke-width':1.7,'aria-hidden':'true',focusable:'false'}))element.setAttribute(key,value);return element};
 function set(el,name,prefix='',only=false){if(!el)return;const existing=el.querySelector(':scope > .ui-icon');if(existing&&el.dataset.uiIcon===name)return;existing?.remove();const icon=svg(name);if(!icon)return;if(only)el.replaceChildren(icon);else{if(prefix)for(const n of Array.from(el.childNodes)){if(n.nodeType===3){n.textContent=n.textContent.replace(new RegExp('^\\s*'+prefix+'\\s*'),'');break}}el.prepend(icon)}el.dataset.uiIcon=name}
 function decorate(){
  set(document.querySelector('.logo'),'BookOpen','',true);
  document.querySelectorAll('.nav-item').forEach(el=>set(el,el.dataset.category==='全部文档'?'Library':'Folder','[▤◈]'));
  document.querySelectorAll('.doc-icon').forEach(el=>set(el,'FileText','',true));
  document.querySelectorAll('.search-wrap > span').forEach(el=>set(el,'Search','',true));
  set(document.getElementById('upload'),'Upload','＋');
  document.querySelectorAll('.hero-actions button:not(#upload)').forEach(el=>set(el,'Folders','◈'));
  document.querySelectorAll('[data-action="category"]').forEach(el=>set(el,'FolderPen'));
  document.querySelectorAll('[data-action="delete"],[data-remove]').forEach(el=>set(el,'Trash2'));
  document.querySelectorAll('[data-edit]').forEach(el=>set(el,'Pencil'));
  set(document.getElementById('manager-close'),'X','',true);
  set(document.querySelector('#create-category button'),'Plus','＋');
  document.querySelectorAll('.article-head > a,.toc-link[href="/"]').forEach(el=>set(el,'ArrowLeft','←'));
  document.querySelectorAll('.select-arrow').forEach(el=>set(el,'ChevronDown','',true));
  document.querySelectorAll('.select-option > span:last-child').forEach(el=>{if(el.textContent==='✓')set(el,'Check','',true)});
  const tools={minus:'ZoomOut',plus:'ZoomIn',reset:'Scan',close:'X'};
  document.querySelectorAll('[data-tool]').forEach(el=>set(el,tools[el.dataset.tool],'',el.dataset.tool!=='reset'));
 }
 let pending=false;const schedule=()=>{if(pending)return;pending=true;requestAnimationFrame(()=>{pending=false;decorate()})};
 new MutationObserver(schedule).observe(document.body,{childList:true,subtree:true});
 const theme=document.getElementById('theme');
 if(theme){const moon=svg('Moon'),sun=svg('Sun');moon.classList.add('theme-moon');sun.classList.add('theme-sun');theme.replaceChildren(moon,sun);}
 decorate();
})();
