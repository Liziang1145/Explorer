"""Real recording file/Range/auth HTTP plus pure adaptive/config checks; no codec emulation."""
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[1];out=root/'vr/build/capture-tests-v3';jar=root/'tools/v2_deps/json-20240303.jar';java=Path(r'C:/Program Files/Android/Android Studio/jbr/bin');src=root/'vr/src/main/java/com/tanluzhe/controlterminal/vr/v2'
code=r"""package com.tanluzhe.controlterminal.vr.v2;
import java.io.*;import java.net.*;import java.util.*;import org.json.*;
public class RecordingProtocolTest {
 static int checks;static void check(boolean b){checks++;if(!b)throw new AssertionError("check "+checks);}
 interface Fn{void run()throws Exception;}static void reject(Fn f)throws Exception{boolean rejected=false;try{f.run();}catch(IllegalArgumentException|IllegalStateException|FileNotFoundException expected){rejected=true;}check(rejected);}
 static byte[] request(int port,String method,String path,String headers)throws Exception{try(Socket s=new Socket("127.0.0.1",port)){s.setSoTimeout(3000);s.getOutputStream().write((method+" "+path+" HTTP/1.1\r\nHost: localhost\r\nAuthorization: Bearer 1\r\n"+headers+"\r\n").getBytes("UTF-8"));return s.getInputStream().readAllBytes();}}
 static String head(byte[] response){return new String(response,java.nio.charset.StandardCharsets.ISO_8859_1).split("\r\n\r\n",2)[0];}
 static byte[] body(byte[] response){for(int i=0;i+3<response.length;i++)if(response[i]==13&&response[i+1]==10&&response[i+2]==13&&response[i+3]==10)return Arrays.copyOfRange(response,i+4,response.length);throw new AssertionError();}
 public static void main(String[]args)throws Exception{
  CaptureConfig c=CaptureConfig.recordingDefaults();check(c.width==2560&&c.height==1440&&c.fps==60&&c.bitrate==40000000);check(CaptureConfig.defaults().width==1920&&CaptureConfig.defaults().height==1080);
  new CaptureConfig(2560,1440,60,80000000,0,70,0,0,0,0,.5f,.5f);reject(()->new CaptureConfig(2560,1440,61,40000000,0,70,0,0,0,0,.5f,.5f));reject(()->new CaptureConfig(2560,1440,60,80000001,0,70,0,0,0,0,.5f,.5f));reject(()->new CaptureConfig(2560,1442,60,40000000,0,70,0,0,0,0,.5f,.5f));
  AdaptivePreview rate=new AdaptivePreview();int low=rate.feedback(0,1000000,400,100,1);check(low==750000);check(rate.feedback(500,1000000,400,100,1)==low);rate.feedback(1000,10000000,0,10,0);int recovered=rate.feedback(5000,10000000,0,10,0);check(recovered>low&&recovered<=6000000);for(int i=0;i<30;i++)rate.congested(6000+i*1000);check(rate.current()==AdaptivePreview.MIN);check(c.bitrate==40000000&&c.fps==60);reject(()->rate.feedback(99999,0,0,0,0));reject(()->rate.feedback(99999,1000000,Double.NaN,0,0));
  ViewCapture backend=new ViewCapture();File partial=backend.store.begin();byte[] bytes=new byte[1000];for(int i=0;i<bytes.length;i++)bytes[i]=(byte)i;try(FileOutputStream f=new FileOutputStream(partial)){f.write(bytes);}check(backend.store.list().length()==0);File complete=backend.store.finish(partial,new JSONObject().put("width",2560).put("fps",60));String name=complete.getName();check(backend.store.list().length()==1&&backend.store.list().getJSONObject(0).getInt("fps")==60);
  try(RecordingStore.Opened lease=backend.store.open(name)){reject(()->backend.store.delete(name));check(lease.length==1000);}reject(()->backend.store.open("../"+name));reject(()->backend.store.delete("..%2F"+name));
  int port;try(ServerSocket available=new ServerSocket(0)){port=available.getLocalPort();}
  try(ViewHttpServer server=new ViewHttpServer(backend,"1",port)){server.start();String path="/v1/view/recordings/"+name;
   byte[] response=request(port,"GET",path,"Range: bytes=200-299\r\n");check(head(response).startsWith("HTTP/1.1 206")&&head(response).contains("Content-Range: bytes 200-299/1000"));check(Arrays.equals(body(response),Arrays.copyOfRange(bytes,200,300)));
   response=request(port,"GET",path,"Range: bytes=-100\r\n");check(Arrays.equals(body(response),Arrays.copyOfRange(bytes,900,1000)));
   response=request(port,"GET",path,"Range: bytes=990-\r\n");check(body(response).length==10);
   response=request(port,"HEAD",path,"");check(head(response).contains("Content-Length: 1000")&&body(response).length==0);
   response=request(port,"GET",path+"/download","");check(head(response).contains("Content-Disposition: attachment")&&Arrays.equals(body(response),bytes));
   response=request(port,"GET",path,"Range: bytes=1000-\r\n");check(head(response).startsWith("HTTP/1.1 416")&&head(response).contains("bytes */1000"));
   for(String invalid:new String[]{"bytes=1-2,4-5","bytes=-","bytes=9999999999999999999999-","bytes=4-2"})check(head(request(port,"GET",path,"Range: "+invalid+"\r\n")).startsWith("HTTP/1.1 416"));
   response=request(port,"GET",path,"Range: bytes=1-2\r\nIf-Range: invalid\r\n");check(head(response).startsWith("HTTP/1.1 200")&&body(response).length==1000);
   check(head(request(port,"DELETE",path,"")).startsWith("HTTP/1.1 200"));check(backend.store.list().length()==0);check(head(request(port,"GET",path,"")).startsWith("HTTP/1.1 404"));
  }
  System.out.println("PASS: "+checks+" 2K60/high-bitrate configs, adaptive preview isolation, durable recording store, leases, Range/HEAD/seek/download/delete and real HTTP assertions; codec not emulated.");
 }
}
"""
(out/'RecordingProtocolTest.java').write_text(code,encoding='utf8')
subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-cp',str(jar)+';'+str(out),'-d',str(out),str(src/'AdaptivePreview.java'),str(src/'RecordingStore.java'),str(src/'FileByteRange.java'),str(out/'RecordingProtocolTest.java')],check=True)
subprocess.run([str(java/'java.exe'),'-cp',str(jar)+';'+str(out),'com.tanluzhe.controlterminal.vr.v2.RecordingProtocolTest'],check=True,timeout=25)
