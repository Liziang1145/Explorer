"""Host checks of production framing, AVC fanout and actual HTTP transport.

Android codecs/EGL are not emulated. HTTP uses a deliberately minimal backend/JSON
adapter; this tests sockets/auth/routing/chunks, not Android JSON or MediaCodec.
"""
from pathlib import Path
import subprocess

root=Path(__file__).resolve().parents[1]
out=root/'vr/build/capture-tests-v3';out.mkdir(parents=True,exist_ok=True)
java=Path(r'C:\Program Files\Android\Android Studio\jbr\bin')
src=root/'vr/src/main/java/com/tanluzhe/controlterminal/vr/v2'
adapters={
'org/json/JSONException.java': 'package org.json;public class JSONException extends Exception{public JSONException(String text){super(text);}}',
'org/json/JSONArray.java':'package org.json;public class JSONArray{public String toString(){return "[]";}}',
'org/json/JSONObject.java':r'''package org.json;import java.util.*;public class JSONObject{
 private final Map<String,Object> values=new LinkedHashMap<>();public JSONObject(){}public JSONObject(String text)throws JSONException{if(!text.trim().equals("{}"))throw new JSONException("test adapter accepts only empty JSON");}
 public JSONObject put(String k,Object v)throws JSONException{values.put(k,v);return this;}public String toString(){StringJoiner s=new StringJoiner(",","{","}");for(Map.Entry<String,Object> e:values.entrySet())s.add(quote(e.getKey())+":"+(e.getValue() instanceof String?quote((String)e.getValue()):String.valueOf(e.getValue())));return s.toString();}
 private static String quote(String s){return "\""+s.replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n")+"\"";}
}''',
'com/tanluzhe/controlterminal/vr/AppLog.java':r'''package com.tanluzhe.controlterminal.vr;public class AppLog{public static void info(String a,String b,String c){}public static void warn(String a,String b,String c){}public static String reason(Throwable e){return e.getClass().getSimpleName();}}''',
'com/tanluzhe/controlterminal/vr/v2/ViewCapture.java':r'''package com.tanluzhe.controlterminal.vr.v2;import org.json.*;import java.io.*;public class ViewCapture{
 public final LiveViewBus live=new LiveViewBus();private volatile boolean stream;public boolean streaming(){return stream;}public JSONObject status()throws JSONException{return new JSONObject().put("ready",true).put("streaming",stream);}
 public JSONObject command(String path,JSONObject body)throws Exception{if(path.equals("/v1/view/live/start"))stream=true;if(path.equals("/v1/view/live/stop")){stream=false;live.finish();}return status();}public void requestKeyAsync(){}public JSONArray recordings(){return new JSONArray();}public File recordingFile(String s)throws IOException{throw new FileNotFoundException();}
}''',
}
# Use the real JSON implementation and production recording store/range handler.
jar=root/'tools/v2_deps/json-20240303.jar'
adapters={k:v for k,v in adapters.items() if not k.startswith('org/json/')}
adapters['com/tanluzhe/controlterminal/vr/v2/ViewCapture.java']=r'''package com.tanluzhe.controlterminal.vr.v2;
import org.json.*;import java.io.*;
public class ViewCapture {
 public final LiveViewBus live=new LiveViewBus();public final RecordingStore store=new RecordingStore(new File(System.getProperty("java.io.tmpdir"),"capture-"+java.util.UUID.randomUUID()));private volatile boolean stream;
 public boolean streaming(){return stream;}public JSONObject status(){return new JSONObject().put("ready",true).put("streaming",stream);}
 public JSONObject command(String path,JSONObject body){if(path.equals("/v1/view/live/start"))stream=true;if(path.equals("/v1/view/live/stop")){stream=false;live.finish();}return status();}
 public void requestKeyAsync(){}public void networkCongested(){}public JSONArray recordings()throws Exception{return store.list();}public JSONObject capabilities(){return new JSONObject();}public JSONObject recordStatus(){return new JSONObject();}public void deleteRecording(String name)throws IOException{store.delete(name);}public RecordingStore.Opened openRecording(String name)throws IOException{return store.open(name);}
}
'''
for name,text in adapters.items():
    p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf8')
harness=r'''package com.tanluzhe.controlterminal.vr.v2;
import java.net.*;import java.io.*;import java.nio.*;import java.util.*;
public class CaptureHostTest{
 static int checks;static void check(boolean b){checks++;if(!b)throw new AssertionError("check "+checks);}
 static void rejects(Runnable f){try{f.run();throw new AssertionError("accepted invalid input");}catch(IllegalArgumentException expected){checks++;}}
 static String request(int port,String method,String path,String token,String headers,String body)throws Exception{
  try(Socket socket=new Socket("127.0.0.1",port)){socket.setSoTimeout(3000);String wire=method+" "+path+" HTTP/1.1\r\nHost: localhost\r\n"+(token==null?"":"Authorization: Bearer "+token+"\r\n")+headers+"\r\n"+body;socket.getOutputStream().write(wire.getBytes("UTF-8"));return new String(socket.getInputStream().readAllBytes(),"UTF-8");}
 }
 public static void main(String[] args)throws Exception{
  LiveSessionState policy=new LiveSessionState();check(policy.wanted());check(!policy.shouldAutoStart(false,true)&&!policy.shouldAutoStart(true,false)&&policy.shouldAutoStart(true,true));
  policy.start("automatic");check(policy.snapshot().active&&policy.snapshot().startedBy.equals("automatic")&&!policy.shouldAutoStart(true,true));
  policy.stop("app_paused");check(policy.shouldAutoStart(true,true));policy.requestStop();check(!policy.shouldAutoStart(true,true));policy.startRemote();check(policy.wanted()&&policy.snapshot().active&&policy.snapshot().startedBy.equals("backend"));policy.requestStop();policy.stop("vr_menu");check(!policy.shouldAutoStart(true,true));
  CaptureConfig c=CaptureConfig.defaults();check(c.width==1920&&c.height==1080&&c.fps==30);CaptureConfig shifted=new CaptureConfig(720,1280,24,4000000,0,70,.1f,.2f,.05f,.15f,1,0);check(shifted.centerX==.5f&&shifted.centerY==.5f&&shifted.left==shifted.right&&shifted.top==shifted.bottom);check(new CaptureConfig(1920,1080,30,16000000,1,120,0,0,0,0,1,0).height==1080);
  rejects(()->new CaptureConfig(1281,720,24,4000000,0,70,0,0,0,0,.5f,.5f));rejects(()->c.framing(Float.NaN,.1f));rejects(()->c.framing(70,.46f));check(c.sameEncoder(c.framing(80,.1f)));
  byte[] avcc={0,0,0,2,0x65,0x22};check(Arrays.equals(NalUnits.annexB(avcc),new byte[]{0,0,0,1,0x65,0x22}));rejects(()->NalUnits.annexB(new byte[]{0,0,0,5,1}));
  byte[] ambiguous=new byte[361];ambiguous[2]=1;ambiguous[3]=101;ambiguous[4]=0x65;check(NalUnits.annexB(ambiguous)[3]==1&&NalUnits.annexB(ambiguous)[4]==0x65);
  LiveViewBus bus=new LiveViewBus();int[] disconnected={0};LiveViewBus.Client client=bus.subscribe(()->disconnected[0]++);
  bus.publish(new byte[]{1},false,5,1280,720,new byte[]{7,8});check(client.frames.isEmpty());bus.publish(new byte[]{5},true,6,1280,720,new byte[]{7,8});LiveViewBus.Frame frame=client.frames.poll();check(Arrays.equals(frame.bytes,new byte[]{7,8,5}));ByteBuffer header=ByteBuffer.wrap(frame.header());check(header.getInt()==0x544c5a56);check(header.get()==1&&header.get()==1&&header.getShort()==32&&header.getInt()==1&&header.getLong()==6&&header.getShort()==1280&&header.getShort()==720&&header.getInt()==3);
  for(int i=0;i<9;i++)bus.publish(new byte[]{1},false,7+i,1280,720,new byte[0]);check(client.closed&&disconnected[0]==1&&bus.size()==0);
  LiveViewBus.Client a=bus.subscribe(()->{}),b=bus.subscribe(()->{});try{bus.subscribe(()->{});throw new AssertionError();}catch(IllegalStateException expected){checks++;}bus.finish();check(a.closed&&b.closed&&bus.size()==0);
  int port;try(ServerSocket available=new ServerSocket(0)){port=available.getLocalPort();}
  ViewCapture backend=new ViewCapture();try(ViewHttpServer server=new ViewHttpServer(backend,"test-secret",port)){
   server.start();check(request(port,"GET","/v1/view/status",null,"","").startsWith("HTTP/1.1 401"));
   check(request(port,"GET","/v1/view/status","wrong","","").startsWith("HTTP/1.1 401"));
   String response=request(port,"GET","/v1/view/status","test-secret","","");check(response.startsWith("HTTP/1.1 200")&&response.contains("\"ready\":true"));
   check(request(port,"GET","/v1/view/recordings","test-secret","","").contains("\"files\":[]"));
   check(request(port,"GET","/v1/view/live.h264","test-secret","","").startsWith("HTTP/1.1 409"));
   check(request(port,"PUT","/v1/view/config","test-secret","Content-Length: 8193\r\n","").startsWith("HTTP/1.1 400"));
   check(request(port,"PUT","/v1/view/config","test-secret","Content-Length: 2\r\nContent-Length: 2\r\n","{}").startsWith("HTTP/1.1 400"));
   check(request(port,"DELETE","/v1/view/config","test-secret","","").startsWith("HTTP/1.1 405"));
   check(request(port,"GET","/v1/view/no-such-path","test-secret","","").startsWith("HTTP/1.1 404"));
   check(request(port,"POST","/v1/view/live/start","test-secret","Content-Length: 2\r\n","{}").startsWith("HTTP/1.1 200"));
   for(String path:new String[]{"live.h264","live.tlzv"}){
    HttpURLConnection conn=(HttpURLConnection)new URL("http://127.0.0.1:"+port+"/v1/view/"+path).openConnection();conn.setRequestProperty("Authorization","Bearer test-secret");conn.setReadTimeout(3000);
    try(InputStream in=conn.getInputStream()){
     check(conn.getResponseCode()==200&&conn.getHeaderField("Transfer-Encoding").equals("chunked"));backend.live.publish(new byte[]{0,0,0,1,0x65},true,1234567,1280,720,new byte[]{0,0,0,1,0x67});
     if(path.endsWith("tlzv")){byte[] h=in.readNBytes(32);ByteBuffer data=ByteBuffer.wrap(h);check(data.getInt()==0x544c5a56&&data.get(4)==1&&data.getLong(12)==1234567&&data.getInt(24)==10);}
     check(Arrays.equals(in.readNBytes(10),new byte[]{0,0,0,1,0x67,0,0,0,1,0x65}));
    }finally{conn.disconnect();backend.live.finish();}
   }
   check(request(port,"POST","/v1/view/live/stop","test-secret","Content-Length: 2\r\n","{}").startsWith("HTTP/1.1 200"));
  }
  System.out.println("PASS: "+checks+" production config/AVC/fanout and real HTTP auth, limits, routing, chunked H.264/TLZV checks; codec/backend are adapters.");
 }
}'''
(out/'CaptureHostTest.java').write_text(harness,encoding='utf8')
subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-cp',str(jar),'-d',str(out),*[str(out/name) for name in adapters],*[str(src/(n+'.java')) for n in ['CaptureConfig','NalUnits','LiveViewBus','ViewHttpServer','LiveSessionState','RecordingStore','FileByteRange']],str(out/'CaptureHostTest.java')],check=True)
subprocess.run([str(java/'java.exe'),'-cp',str(jar)+';'+str(out),'com.tanluzhe.controlterminal.vr.v2.CaptureHostTest'],check=True,timeout=25)

math=r'''
#include <cassert>
#include <random>
#include <iostream>
'''+(root/'vr/src/main/cpp/view_capture_math.h').read_text(encoding='utf8')+r'''
int main(){std::mt19937 random(42);std::uniform_real_distribution<float> unit(0,1);int checks=0;
 for(int i=0;i<10000;i++){
  float l=-.7f-unit(random),r=.7f+unit(random),d=-.7f-unit(random),u=.7f+unit(random),aspect=.5625f+unit(random)*1.77f;
  float p[]={20+unit(random)*100,unit(random)*.45f,unit(random)*.45f,unit(random)*.45f,unit(random)*.45f,unit(random),unit(random),0};auto c=viewCrop(l,r,d,u,aspect,p);
  float noMargins[]={p[0],0,0,0,0,p[5],p[6],0};auto base=viewCrop(l,r,d,u,aspect,noMargins);
  float mx=std::max(p[1],p[2]),my=std::max(p[3],p[4]);
  assert(c.x0>=base.x0+(base.x1-base.x0)*mx-.00001f&&c.x1<=base.x1-(base.x1-base.x0)*mx+.00001f&&c.y0>=base.y0+(base.y1-base.y0)*my-.00001f&&c.y1<=base.y1-(base.y1-base.y0)*my+.00001f);checks++;
  float cx=l+(c.x0+c.x1)*.5f*(r-l),cy=d+(c.y0+c.y1)*.5f*(u-d);
  assert(std::abs(cx)<.000001f&&std::abs(cy)<.000001f);checks++;
  assert(c.x0>=0&&c.y0>=0&&c.x1<=1&&c.y1<=1);checks++;
  assert(c.x0<c.x1&&c.y0<c.y1);checks++;
  float tanWidth=(c.x1-c.x0)*(r-l),tanHeight=(c.y1-c.y0)*(u-d);
  assert(std::abs(tanWidth/tanHeight-aspect)<.00005f);checks++;
  assert(c.verticalDegrees>0&&c.verticalDegrees<=p[0]+.001f);checks++;
  // A world-space square at constant depth must have equal pixel side lengths.
  float pixelsX=aspect*720/tanWidth*.1f,pixelsY=720/tanHeight*.1f;assert(std::abs(pixelsX/pixelsY-1)<.00005f);checks++;
 }
 std::cout<<"PASS: "<<checks<<" production tangent-space framing checks: asymmetric eye FOVs, margins, portrait/landscape, optical-axis centering independent of legacy shifts, no perspective stretch.\n";
}
'''
(out/'framing.cpp').write_text(math,encoding='utf8')
vs=Path(r'C:\Program Files\Microsoft Visual Studio\18\Insiders\Common7\Tools\VsDevCmd.bat')
subprocess.run(f'"{vs}" -arch=x64 >nul && cl /nologo /std:c++17 /EHsc framing.cpp /Fe:framing.exe && framing.exe',shell=True,cwd=out,check=True)
