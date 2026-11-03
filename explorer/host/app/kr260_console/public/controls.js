// Styled shared-category selector with keyboard navigation and outside dismissal.
(()=>{
 const select=document.getElementById('category-select');if(!select)return;
 select.hidden=true;select.tabIndex=-1;select.setAttribute('aria-hidden','true');
 const custom=document.createElement('div');custom.className='custom-select';custom.innerHTML='<button type="button" class="select-trigger" aria-haspopup="listbox" aria-expanded="false" aria-controls="category-menu"><span></span><span class="select-arrow" aria-hidden="true">⌄</span></button><div class="select-menu" id="category-menu" role="listbox" aria-label="共享分类" hidden></div>';select.after(custom);
 const trigger=custom.querySelector('button'),menu=custom.querySelector('.select-menu');
 const close=()=>{menu.hidden=true;custom.classList.remove('expanded');trigger.setAttribute('aria-expanded','false')};
 function render(){trigger.firstElementChild.textContent=select.selectedOptions[0]?.textContent||'选择分类';menu.replaceChildren();Array.from(select.options).forEach(o=>{const b=document.createElement('button');b.type='button';b.className='select-option'+(o.selected?' selected':'');b.setAttribute('role','option');b.setAttribute('aria-selected',String(o.selected));const text=document.createElement('span');text.textContent=o.textContent;const tick=document.createElement('span');tick.textContent=o.selected?'✓':'';b.append(text,tick);b.onclick=()=>{select.value=o.value;select.dispatchEvent(new Event('change',{bubbles:true}));render();close();trigger.focus()};menu.append(b)})}
 function open(){render();menu.hidden=false;custom.classList.add('expanded');trigger.setAttribute('aria-expanded','true');(menu.querySelector('.selected')||menu.firstElementChild)?.focus()}
 trigger.onclick=()=>menu.hidden?open():close();trigger.onkeydown=e=>{if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();open()}};
 menu.onkeydown=e=>{const items=Array.from(menu.children),index=items.indexOf(document.activeElement);if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close();trigger.focus()}else if(['ArrowDown','ArrowUp','Home','End'].includes(e.key)){e.preventDefault();const next=e.key==='Home'?0:e.key==='End'?items.length-1:(index+(e.key==='ArrowDown'?1:-1)+items.length)%items.length;items[next]?.focus()}else if(e.key==='Tab')close()};
 document.addEventListener('pointerdown',e=>{if(!custom.contains(e.target))close()});modal.addEventListener('close',close);select.addEventListener('change',render);new MutationObserver(render).observe(select,{childList:true});render();
 // Keep dismissal transitions consistent across confirmation and category dialogs.
 const nativeClose=HTMLDialogElement.prototype.close;
 HTMLDialogElement.prototype.close=function(value){if(!this.open||this.classList.contains('image-viewer')||matchMedia('(prefers-reduced-motion: reduce)').matches)return nativeClose.call(this,value);if(this.dataset.closing)return;this.dataset.closing='true';this.classList.add('dialog-closing');setTimeout(()=>{nativeClose.call(this,value);this.classList.remove('dialog-closing');delete this.dataset.closing},140)};
 document.addEventListener('cancel',e=>{if(e.target.tagName==='DIALOG'&&!e.target.classList.contains('image-viewer')){e.preventDefault();e.target.close()}},true);
 // Avoid browser validation bubbles; show feedback in the page's styled toast.
 const forms=document.querySelectorAll('form');forms.forEach(f=>f.noValidate=true);
 new MutationObserver(()=>{document.querySelectorAll('form').forEach(f=>f.noValidate=true)}).observe(document.body,{childList:true,subtree:true});
})();
