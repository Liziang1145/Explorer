"""Run the production asset loader with host Android/JSON/JNI adapters and real HTTP sockets."""
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[1];out=root/'vr/build/scene-http-test';out.mkdir(parents=True,exist_ok=True)
files={
'android/content/Context.java':r'''package android.content;import android.content.res.*;import java.io.*;public class Context{
 public String url="";public final File root;public Context(File root){this.root=root;}public AssetManager getAssets(){return new AssetManager(root);}
 public SharedPreferences getSharedPreferences(String n,int m){return new SharedPreferences(this);}
}''',
'android/content/SharedPreferences.java':r'''package android.content;public class SharedPreferences{Context c;SharedPreferences(Context c){this.c=c;}public String getString(String k,String fallback){return k.equals("colored_scene_url")?c.url:fallback;}}''',
'android/content/res/AssetManager.java':r'''package android.content.res;import java.io.*;public class AssetManager{File root;public AssetManager(File f){root=f;}public InputStream open(String n)throws IOException{return new FileInputStream(new File(root,n));}}''',
'com/tanluzhe/controlterminal/vr/ConnectionSettings.java':r'''package com.tanluzhe.controlterminal.vr;import android.content.Context;public class ConnectionSettings{public String token="test-key";public ConnectionSettings(Context c){}}''',
'com/tanluzhe/controlterminal/vr/AppLog.java':r'''package com.tanluzhe.controlterminal.vr;public class AppLog{public static String reason(Throwable e){return e.toString();}public static void info(String a,String b,String c){}public static void warn(String a,String b,String c){}}''',
# Minimal adapter covers only schema/units/counts used here, not the Android JSON parser.
'org/json/JSONObject.java':r'''package org.json;import java.util.regex.*;public class JSONObject{
 String json;public JSONObject(String s){json=s;}public String getString(String key){Matcher m=Pattern.compile("\""+key+"\"\\s*:\\s*\"([^\"]*)\"").matcher(json);if(!m.find())throw new IllegalArgumentException(key);return m.group(1);}
 public int getInt(String key){Matcher m=Pattern.compile("\""+key+"\"\\s*:\\s*(\\d+)").matcher(json);if(!m.find())throw new IllegalArgumentException(key);return Integer.parseInt(m.group(1));}
}''',
'com/tanluzhe/controlterminal/vr/v2/NativeVr.java':r'''package com.tanluzhe.controlterminal.vr.v2;import java.nio.*;public class NativeVr{
 public static volatile int calls;public static String coloredSceneLoad(ByteBuffer p,ByteBuffer c,ByteBuffer i,int n,int f){
 if(n!=410071||f!=780279||p.remaining()!=n*12||c.remaining()!=n*3||i.remaining()!=f*12||!p.isDirect()||p.order()!=ByteOrder.LITTLE_ENDIAN)throw new AssertionError("JNI payload");calls++;return null;}
}''',
}
for name,text in files.items():
 p=out/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf8')
harness=r'''package com.tanluzhe.controlterminal.vr.v2;
import android.content.Context;import com.sun.net.httpserver.*;import java.net.*;import java.io.*;import java.nio.file.*;import java.util.concurrent.atomic.*;
public class SceneHttpTest{
 static void waitFor(ColoredSceneLoader loader)throws Exception{long end=System.nanoTime()+10000000000L;while(loader.busy()&&System.nanoTime()<end)Thread.sleep(5);if(loader.busy())throw new AssertionError("loader timeout");}
 static void check(boolean b,String s){if(!b)throw new AssertionError(s);}
 public static void main(String[] args)throws Exception{
  File root=new File(args[0]);Context context=new Context(root);AtomicInteger requests=new AtomicInteger(),mode=new AtomicInteger();
  HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);
  server.createContext("/bundle/",exchange->{
   try{
    requests.incrementAndGet();if(!"Bearer test-key".equals(exchange.getRequestHeaders().getFirst("Authorization"))){exchange.sendResponseHeaders(401,-1);return;}
    if(mode.get()==2){exchange.getResponseHeaders().set("Location","http://127.0.0.1:1/stolen");exchange.sendResponseHeaders(302,-1);return;}
    String name=exchange.getRequestURI().getPath().substring("/bundle/".length()).replace("assets/","");
    byte[] bytes=Files.readAllBytes(new File(root,"colored_scene/"+name).toPath());if(mode.get()==1&&name.equals("colors.bin"))bytes[0]^=1;
    exchange.sendResponseHeaders(200,bytes.length);exchange.getResponseBody().write(bytes);
   }finally{exchange.close();}
  });server.start();
  try(ColoredSceneLoader loader=new ColoredSceneLoader(context)){
   loader.load(false);waitFor(loader);check(loader.error.isEmpty()&&NativeVr.calls==1,"bundled scan must load with hashes: "+loader.error);
   context.url="http://127.0.0.1:"+server.getAddress().getPort()+"/bundle/assets/manifest.json";
   loader.load(true);waitFor(loader);check(loader.error.isEmpty()&&NativeVr.calls==2&&requests.get()==5,"HTTP manifest/hash/three buffers: "+loader.error);
   mode.set(1);loader.load(true);waitFor(loader);check(!loader.error.isEmpty()&&NativeVr.calls==2,"reject corrupted colour bytes before JNI");
   mode.set(2);loader.load(true);waitFor(loader);check(loader.error.contains("302")&&NativeVr.calls==2,"redirect not followed");
   context.url="";loader.load(true);waitFor(loader);check(!loader.error.isEmpty(),"missing AIPC endpoint explicit error");
  }finally{server.stop(0);}
  System.out.println("PASS: production loader with full real scan, manifest/SHA256SUMS/three buffers over authenticated HTTP, local assets, uint32 JNI lengths, corruption, redirect and missing endpoint; Android/JSON/JNI are host adapters.");
 }
}'''
(out/'SceneHttpTest.java').write_text(harness,encoding='utf8')
java=Path(r'C:\Program Files\Android\Android Studio\jbr\bin')
src=root/'vr/src/main/java/com/tanluzhe/controlterminal/vr/v2/ColoredSceneLoader.java'
subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-d',str(out),*[str(out/n) for n in files],str(src),str(out/'SceneHttpTest.java')],check=True)
subprocess.run([str(java/'java.exe'),'-cp',str(out),'com.tanluzhe.controlterminal.vr.v2.SceneHttpTest',str(root/'vr/src/main/assets')],check=True,timeout=30)
