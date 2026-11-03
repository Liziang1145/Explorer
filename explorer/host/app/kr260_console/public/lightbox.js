(()=>{
 const viewer=document.createElement('dialog');viewer.className='image-viewer';viewer.setAttribute('aria-label','图片放大查看');
 viewer.innerHTML='<div class="image-toolbar"><span class="image-caption"></span><div><button type="button" data-tool="minus" aria-label="缩小">−</button><button type="button" data-tool="reset" aria-label="重置缩放">适应窗口</button><button type="button" data-tool="plus" aria-label="放大">＋</button><button type="button" data-tool="close" aria-label="关闭图片预览">✕</button></div></div><div class="image-stage"><img alt="" draggable="false"></div><div class="image-hint">滚轮缩放 · 拖动查看 · Esc 关闭</div>';
 document.body.append(viewer);const image=viewer.querySelector('img'),stage=viewer.querySelector('.image-stage');let zoom=1,x=0,y=0,drag=null,previousOverflow='',sourceImage=null,sourceVisibility='',fitRect=null,motion=null,closing=false,session=0;
 const paint=()=>{image.style.transform=`translate(${x}px,${y}px) scale(${zoom})`;stage.classList.toggle('zoomed',zoom>1)};
 const reset=()=>{zoom=1;x=y=0;paint()};
 const scale=amount=>{if(closing||viewer.classList.contains('is-opening'))return;zoom=Math.max(1,Math.min(6,zoom*amount));if(zoom===1)x=y=0;paint()};
 const reduced=()=>matchMedia('(prefers-reduced-motion: reduce)').matches;
 const transformFrom=r=>`translate(${r.left+r.width/2-fitRect.left-fitRect.width/2}px,${r.top+r.height/2-fitRect.top-fitRect.height/2}px) scale(${r.width/fitRect.width},${r.height/fitRect.height})`;
 async function open(source){
  if(viewer.open)return;
  const currentSession=++session;sourceImage=source;sourceVisibility=source.style.visibility;
  const origin=source.getBoundingClientRect();
  image.style.visibility='hidden';image.src=source.currentSrc||source.src;image.alt=source.alt;
  viewer.querySelector('.image-caption').textContent=source.alt||'图片预览';
  viewer.classList.add('is-opening');reset();previousOverflow=document.body.style.overflow;document.body.style.overflow='hidden';viewer.showModal();
  try{await image.decode()}catch(e){}
  if(currentSession!==session||!viewer.open||closing)return;
  fitRect=image.getBoundingClientRect();
  if(!fitRect.width||!fitRect.height){image.style.visibility='visible';viewer.classList.remove('is-opening');return}
  source.style.visibility='hidden';
  if(!reduced()){
   const openingMotion=image.animate([{transform:transformFrom(origin),borderRadius:'10px'},{transform:'translate(0px,0px) scale(1)',borderRadius:'0px'}],{duration:360,easing:'cubic-bezier(.22,1,.36,1)',fill:'both'});
   motion=openingMotion;image.style.visibility='visible';
   try{await openingMotion.finished}catch(e){}
   if(currentSession!==session)return;
   if(motion===openingMotion){openingMotion.cancel();motion=null;}
  }else image.style.visibility='visible';
  if(!closing)viewer.classList.remove('is-opening');
 }
 const nativeViewerClose=viewer.close.bind(viewer);
 viewer.close=async function(){
  if(!viewer.open||closing)return;closing=true;++session;
  const currentTransform=getComputedStyle(image).transform;
  image.style.transition='none';image.style.transform=currentTransform;motion?.cancel();drag=null;
  viewer.classList.add('is-closing');const destination=sourceImage?.getBoundingClientRect();let closingMotion=null;
  if(!reduced()&&fitRect&&destination?.width&&image.style.visibility!=='hidden'){
   closingMotion=image.animate([{transform:currentTransform,borderRadius:'0px'},{transform:transformFrom(destination),borderRadius:'10px'}],{duration:280,easing:'cubic-bezier(.4,0,.2,1)',fill:'both'});motion=closingMotion;
   try{await closingMotion.finished}catch(e){}
  }
  image.style.visibility='hidden';if(sourceImage)sourceImage.style.visibility=sourceVisibility;
  nativeViewerClose();closingMotion?.cancel();motion=null;image.style.transition='';closing=false;viewer.classList.remove('is-opening','is-closing');
 };
 viewer.addEventListener('cancel',e=>{e.preventDefault();viewer.close()});
 viewer.addEventListener('close',()=>{document.body.style.overflow=previousOverflow;drag=null;fitRect=null;if(sourceImage)sourceImage.style.visibility=sourceVisibility;image.removeAttribute('src')});
 viewer.querySelectorAll('[data-tool]').forEach(b=>b.onclick=()=>{const t=b.dataset.tool;if(t==='close')viewer.close();else if(t==='reset')reset();else scale(t==='plus'?1.3:1/1.3)});
 stage.onclick=e=>{if(e.target===stage)viewer.close()};
 stage.addEventListener('wheel',e=>{e.preventDefault();scale(e.deltaY<0?1.12:1/1.12)},{passive:false});
 image.ondblclick=()=>zoom===1?scale(2):reset();
 image.onpointerdown=e=>{if(e.button!==0||closing||viewer.classList.contains('is-opening'))return;e.preventDefault();drag={id:e.pointerId,x:e.clientX,y:e.clientY,startX:x,startY:y};image.setPointerCapture(e.pointerId);stage.classList.add('dragging')};
 image.onpointermove=e=>{if(!drag||e.pointerId!==drag.id)return;x=drag.startX+e.clientX-drag.x;y=drag.startY+e.clientY-drag.y;paint()};
 const stop=()=>{drag=null;stage.classList.remove('dragging')};image.onpointerup=image.onpointercancel=stop;
 document.addEventListener('click',e=>{const target=e.target.closest('.article img');if(target){e.preventDefault();open(target)}});
 document.addEventListener('keydown',e=>{if(viewer.open){if(e.key==='+'||e.key==='='){e.preventDefault();scale(1.3)}if(e.key==='-'){e.preventDefault();scale(1/1.3)}}else if((e.key==='Enter'||e.key===' ')&&e.target.matches('.article img')){e.preventDefault();open(e.target)}});
 const enable=()=>document.querySelectorAll('.article img').forEach(img=>{img.tabIndex=0;img.setAttribute('role','button');img.title='点击放大查看';img.setAttribute('aria-label',(img.alt||'图片')+'，点击放大查看')});
 new MutationObserver(enable).observe(document.getElementById('main'),{childList:true,subtree:true});enable();
})();
