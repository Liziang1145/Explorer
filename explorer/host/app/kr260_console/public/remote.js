/* Official Guacamole renderer and input translation. No desktop credentials in JS. */
(()=>{
 const shell=document.getElementById('desktop-shell'),host=document.getElementById('desktop-display'),placeholder=document.getElementById('desktop-placeholder');let client=null,tunnel=null,keyboard=null,mouse=null,connected=false,fit=true,started=0,rx=0,frameTimer=null;
 const node=id=>document.getElementById(id);
 function status(text,cls=''){node('rdp-state').textContent=text;node('rdp-state').className='status-pill '+cls}
 function focused(){return shell===document.activeElement||shell.contains(document.activeElement)}
 function release(){if(keyboard)keyboard.reset();if(mouse)mouse.reset();node('rdp-focus').textContent='键盘未捕获'}
 function scale(){if(!client)return;const display=client.getDisplay(),width=display.getWidth(),height=display.getHeight();if(!width||!height)return;const value=fit?Math.min((shell.clientWidth-4)/width,(shell.clientHeight-4)/height,1):1;display.scale(value);node('rdp-size').textContent=width+' × '+height+' · '+Math.round(value*100)+'%'}
 function disconnect(){release();if(client)client.disconnect();client=null;tunnel=null;connected=false;node('rdp-disconnect').disabled=true;node('rdp-connect').disabled=false;status('已断开');placeholder.hidden=false;host.replaceChildren();clearInterval(frameTimer);node('rdp-size').textContent=''}
 function focus(){shell.focus({preventScroll:true});node('rdp-focus').textContent='键盘已捕获 · 点击工具栏释放'}
 function connect(){if(!state.signedIn){login();return}disconnect();node('rdp-connect').disabled=true;placeholder.hidden=true;status('正在连接','loading');
  const url=(location.protocol==='https:'?'wss://':'ws://')+location.host+'/api/v1/rdp/ws';tunnel=new Guacamole.WebSocketTunnel(url);tunnel.receiveTimeout=45000;tunnel.unstableThreshold=8000;client=new Guacamole.Client(tunnel);const sessionClient=client;host.append(client.getDisplay().getElement());if(!keyboard)keyboard=new Guacamole.Keyboard(shell);mouse=new Guacamole.Mouse(client.getDisplay().getElement());
  keyboard.onkeydown=sym=>{if(connected&&focused()){client.sendKeyEvent(1,sym);return false}return true};keyboard.onkeyup=sym=>{if(connected)client.sendKeyEvent(0,sym)};
  mouse.onEach(['mousedown','mousemove','mouseup'],e=>{if(connected){if(e.type==='mousedown')focus();client.sendMouseState(e.state,true)}});
  const touch=new Guacamole.Mouse.Touchscreen(client.getDisplay().getElement());touch.onEach(['mousedown','mousemove','mouseup'],e=>{if(connected){focus();client.sendMouseState(e.state,true)}});
  client.getDisplay().onresize=scale;client.getDisplay().oncursor=(canvas,x,y)=>{if(!mouse.setCursor(canvas,x,y))client.getDisplay().showCursor(true)};
  client.onstatechange=s=>{if(client!==sessionClient)return;if(s===3){connected=true;node('rdp-disconnect').disabled=false;status('桌面已连接','ready');scale();focus()}else if(s===5){connected=false;release();node('rdp-connect').disabled=false;node('rdp-disconnect').disabled=true;status('连接已结束')}};
  client.onerror=e=>{if(client!==sessionClient)return;status(e.message||'连接失败','failed');node('rdp-connect').disabled=false;node('rdp-disconnect').disabled=true;connected=false;release();toast('远程桌面连接失败，可重新登录后重试')};
  tunnel.onerror=e=>{if(client!==sessionClient)return;status(e.message||'网关连接失败','failed');node('rdp-connect').disabled=false};
  const previous=tunnel.oninstruction;tunnel.oninstruction=(op,args)=>{rx+=op.length+args.reduce((sum,v)=>sum+v.length,0);if(previous)previous(op,args)};
  started=performance.now();rx=0;frameTimer=setInterval(()=>{const seconds=(performance.now()-started)/1000;node('rdp-traffic').textContent='桌面接收 '+(rx/1024).toFixed(1)+' KiB · 平均 '+(rx*8/Math.max(1,seconds)/1e6).toFixed(3)+' Mbit/s'},1000);
  client.connect('');
 }
 node('rdp-connect').onclick=connect;node('rdp-disconnect').onclick=disconnect;node('rdp-fit').onclick=()=>{fit=!fit;node('rdp-fit').textContent=fit?'自适应':'原始尺寸';scale()};node('rdp-fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await shell.requestFullscreen();scale()}catch(e){toast('浏览器无法进入全屏')}};
 node('rdp-text').onclick=()=>{if(!connected)return toast('请先连接桌面');release();node('rdp-text-dialog').showModal();node('rdp-text-value').focus()};node('rdp-text-cancel').onclick=()=>node('rdp-text-dialog').close();
 node('rdp-text-send').onclick=()=>{if(!connected)return;const text=node('rdp-text-value').value;if(new TextEncoder().encode(text).length>65536)return toast('文本最多64 KiB');const stream=client.createClipboardStream('text/plain'),writer=new Guacamole.StringWriter(stream);writer.sendText(text);writer.sendEnd();node('rdp-text-value').value='';node('rdp-text-dialog').close();setTimeout(()=>{if(!connected)return;client.sendKeyEvent(1,0xffe3);client.sendKeyEvent(1,0x76);client.sendKeyEvent(0,0x76);client.sendKeyEvent(0,0xffe3);focus()},250)};
 shell.addEventListener('pointerdown',focus);shell.addEventListener('focusout',e=>{if(!shell.contains(e.relatedTarget))release()});window.addEventListener('blur',release);window.addEventListener('resize',scale);document.addEventListener('fullscreenchange',scale);document.addEventListener('visibilitychange',()=>{if(document.hidden)release()});window.addEventListener('beforeunload',()=>{release();if(client)client.disconnect()});new ResizeObserver(scale).observe(shell);
 document.addEventListener('rdp-status',e=>{if(!client)status(e.detail.ready?'网关就绪，点击连接':'网关未就绪',e.detail.ready?'':'loading')});
})();
