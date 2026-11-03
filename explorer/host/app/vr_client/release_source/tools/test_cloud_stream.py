"""Production v1 client against a local fixture server, using real JSON/gzip/Range/cache."""
from pathlib import Path
import subprocess,json,hashlib
root=Path(__file__).resolve().parents[1];out=root/'vr/build/cloud-stream-test';out.mkdir(parents=True,exist_ok=True)
jar=root/'tools/v2_deps/json-20240303.jar'
assert hashlib.sha256(jar.read_bytes()).hexdigest()=='3cf6cd6892e32e2b4c1c39e0f52f5248a2f5b37646fdfbb79a66b46b618414ed'
source=r'''
import com.tanluzhe.cloud.CloudStream;
import com.tanluzhe.controlterminal.mobile.ControllerState;
import org.json.*;import java.util.*;import java.util.concurrent.*;import java.util.concurrent.atomic.*;import java.util.zip.*;import java.io.*;import java.nio.*;import com.sun.net.httpserver.*;import java.net.*;
public class CloudStreamTest{
 static int checks;static void check(boolean b,String reason){checks++;if(!b)throw new AssertionError(reason);}
 interface Condition{boolean get();}static void waitFor(Condition c,String reason)throws Exception{long end=System.nanoTime()+18000000000L;while(!c.get()&&System.nanoTime()<end)Thread.sleep(20);check(c.get(),reason);}
 static byte[] raw(int n){ByteBuffer b=ByteBuffer.allocate(n*15).order(ByteOrder.LITTLE_ENDIAN);Random random=new Random(3100+n);for(int i=0;i<n;i++)b.putFloat(random.nextFloat()).putFloat(random.nextFloat()).putFloat(-random.nextFloat()).put((byte)random.nextInt(256)).put((byte)random.nextInt(256)).put((byte)random.nextInt(256));return b.array();}
 static byte[] gz(byte[] raw)throws Exception{ByteArrayOutputStream out=new ByteArrayOutputStream();try(GZIPOutputStream zip=new GZIPOutputStream(out)){zip.write(raw);}return out.toByteArray();}
 static JSONObject meta(String id,byte[] raw,byte[] gzip)throws Exception{return new JSONObject().put("id",id).put("points",raw.length/15).put("bytes",raw.length).put("sha256",CloudStream.sha(raw)).put("gzip_bytes",gzip.length).put("gzip_sha256",CloudStream.sha(gzip)).put("bounds",new JSONArray(new float[]{0,0,-1,1,1,0}));}
 static final class Sink implements CloudStream.Sink{
  final Set<String> ready=ConcurrentHashMap.newKeySet(),accepted=ConcurrentHashMap.newKeySet();volatile long generation;volatile boolean ackFine;
  public void reset(long g,List<CloudStream.Block> blocks){generation=g;ready.clear();accepted.clear();}
  public boolean offer(long g,CloudStream.Block b,ByteBuffer raw,boolean coarse){check(g==generation,"stale generation");check(raw.isDirect()&&raw.remaining()==b.points*15,"15 byte direct records");accepted.add(b.id);if(coarse||ackFine)ready.add(b.id);return true;}
  public Set<String> resident(long g){if(ackFine)ready.addAll(accepted);return new HashSet<>(ready);}
  public Set<String> pending(long g){return new HashSet<>(accepted);}
  public void retain(long g,Set<String> ids){ready.retainAll(ids);}
 }
 public static void main(String[] args)throws Exception{
  String scene=CloudStream.DENSE;byte[] coarseRaw=raw(40),fineRaw=raw(70000),coarseGz=gz(coarseRaw),fineGz=gz(fineRaw);
  JSONObject coarse=meta("coarse",coarseRaw,coarseGz),fine=meta("t000001",fineRaw,fineGz).put("priority",0);
  AtomicInteger gets=new AtomicInteger(),ranges=new AtomicInteger(),authFailures=new AtomicInteger();AtomicBoolean truncate=new AtomicBoolean(true),sawResume=new AtomicBoolean(),cachedPremature=new AtomicBoolean();
  Sink sink=new Sink();HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);ExecutorService workers=Executors.newFixedThreadPool(4);server.setExecutor(workers);
  server.createContext("/api/v1/",e->{try{
   if(!"Bearer fixture-only".equals(e.getRequestHeaders().getFirst("Authorization"))){authFailures.incrementAndGet();e.sendResponseHeaders(401,-1);return;}
   String path=e.getRequestURI().getPath();if(!path.endsWith("catalog")&&!scene.equals(e.getRequestHeaders().getFirst("X-Cloud-Scene")))throw new AssertionError("explicit scene header");
   if(path.endsWith(".gz")){
    gets.incrementAndGet();byte[] data=path.endsWith("coarse.gz")?coarseGz:fineGz;String hash=CloudStream.sha(data);
    check(("\""+hash+"\"").equals(e.getRequestHeaders().getFirst("If-Match")),"If-Match gzip hash");String[] range=e.getRequestHeaders().getFirst("Range").substring(6).split("-");int start=Integer.parseInt(range[0]),end=Integer.parseInt(range[1]);check(end-start+1<=512*1024,"wifi range limit");
    if(start>0)sawResume.set(true);ranges.incrementAndGet();e.getResponseHeaders().set("ETag","\""+hash+"\"");e.getResponseHeaders().set("Content-Range","bytes "+start+"-"+end+"/"+data.length);e.sendResponseHeaders(206,end-start+1);
    int count=end-start+1;if(path.contains("t000001")&&truncate.compareAndSet(true,false))count/=2;e.getResponseBody().write(data,start,count);return;
   }
   JSONObject response;
   if(path.endsWith("catalog"))response=new JSONObject().put("scenes",new JSONArray().put(new JSONObject().put("id",scene).put("name","fixture dense"))).put("relay_configured",false);
   else if(path.endsWith("manifest"))response=new JSONObject().put("scene_id",scene).put("units","m").put("coarse",coarse).put("bounds",new JSONArray(new float[]{0,0,-1,1,1,0})).put("tiles",new JSONArray().put(fine));
   else{
    JSONObject request=new JSONObject(new String(e.getRequestBody().readAllBytes(),"UTF-8"));check(request.getString("scene_id").equals(scene),"select scene body");check(request.getJSONArray("position_scene_m").length()==3,"scene position");
    boolean cached=request.getJSONArray("cached").toList().contains("t000001");if(cached&&!sink.ready.contains("t000001"))cachedPremature.set(true);
    response=new JSONObject().put("scene_id",scene).put("request_seq",request.getLong("request_seq")).put("retain",new JSONArray().put("t000001")).put("near_required",new JSONArray().put("t000001")).put("prefetch",new JSONArray().put("t000001")).put("requests",cached?new JSONArray():new JSONArray().put(fine));
   }
   byte[] body=response.toString().getBytes("UTF-8");e.sendResponseHeaders(200,body.length);e.getResponseBody().write(body);
  }catch(Exception x){throw new RuntimeException(x);}finally{e.close();}});server.start();
  File cache=new File(args[0],"cache-"+System.nanoTime());String base="http://127.0.0.1:"+server.getAddress().getPort();
  try{
   CloudStream stream=new CloudStream(new CloudStream.Config(base,"fixture-only",scene,"wifi",false),cache,sink);stream.start();
   waitFor(()->sink.accepted.contains("t000001"),"coarse then resumable fine load");check(sawResume.get(),"nonzero Range resumes partial download");check(!cachedPremature.get(),"disk/queued != GPU cached");
   sink.ackFine=true;waitFor(()->stream.nearDone==1&&stream.nearTotal==1,"near GPU ready metrics");int beforeEviction=gets.get();sink.accepted.remove("t000001");sink.ready.remove("t000001");waitFor(()->sink.ready.contains("t000001"),"evicted block offered again");check(gets.get()==beforeEviction,"evicted GPU block restored from disk without network");stream.close();stream.awaitStopped();int downloaded=gets.get();
   Sink second=new Sink();second.ackFine=true;CloudStream cached=new CloudStream(new CloudStream.Config(base,"fixture-only",scene,"wifi",false),cache,second);cached.start();waitFor(()->second.ready.contains("t000001"),"second session uses disk cache");check(gets.get()==downloaded&&cached.downloadedBytes==0,"zero cloud bytes on cache reuse");cached.close();cached.awaitStopped();
   CloudStream bad=new CloudStream(new CloudStream.Config(base,"wrong",scene,"wifi",false),cache,new Sink());bad.start();waitFor(()->bad.error.contains("401"),"independent authentication failure");int failures=authFailures.get();Thread.sleep(600);check(authFailures.get()==failures,"401 does not blind retry");bad.close();bad.awaitStopped();
   for(float p:new float[]{Float.NaN,Float.POSITIVE_INFINITY}){boolean rejected=false;try{cached.position(new float[]{p,0,0});}catch(IllegalArgumentException expected){rejected=true;}check(rejected,"nonfinite position rejection");}
   check(CloudStream.intersects(new float[]{0,0,0,2,2,2},new float[]{5,1,1},3),"AABB sphere tangency");
   check(!CloudStream.intersects(new float[]{0,0,0,2,2,2},new float[]{5.01f,1,1},3),"outside near sphere");
   check(ControllerState.axis(.05f,0)==0&&ControllerState.axis(Float.NaN,0)==0&&ControllerState.axis(2,0)==1,"gamepad deadzone/range");
   ControllerState state=new ControllerState();state.look(.3f,-.2f);check(state.takeLook()[0]==.3f&&state.takeLook()[0]==0,"touch deltas consumed once");state.lx=1;state.buttons=15;state.reset();check(state.lx==0&&state.buttons==0,"disconnect/focus releases input");
   CloudStream.clearCache(cache);check(cache.listFiles().length==0,"explicit owned cache clear");
  }finally{server.stop(0);workers.shutdownNow();}
  System.out.println("PASS: "+checks+" real v1 JSON/Range/gzip/SHA256/cache/late-GPU/auth and camera-input checks. Fixture service only; not AIPC acceptance.");
 }
}
'''
(out/'CloudStreamTest.java').write_text(source,encoding='utf8')
java=Path(r'C:\Program Files\Android\Android Studio\jbr\bin')
subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-cp',str(jar),'-d',str(out),str(root/'shared/src/main/java/com/tanluzhe/cloud/CloudStream.java'),str(root/'mobile/src/main/java/com/tanluzhe/controlterminal/mobile/ControllerState.java'),str(out/'CloudStreamTest.java')],check=True)
subprocess.run([str(java/'java.exe'),'-cp',str(out)+';'+str(jar),'CloudStreamTest',str(out)],check=True,timeout=55)
