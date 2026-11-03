"""Production Java v2/static and VCL1 adapters against supplied AIPC server source and real assets."""
from pathlib import Path
import sys,threading,importlib.util,subprocess,json,gzip,struct,hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
root=Path(__file__).resolve().parents[1];handoff=root.parent/'VR_SCENE_STREAMING_HANDOFF_20261031';bundle=root.parent/'Quest3_static_cloud_offline_v2_20261031/Quest3_static_cloud_offline_v2'
out=root/'vr/build/scene-stream-v2-test';out.mkdir(parents=True,exist_ok=True);jar=root/'tools/v2_deps/json-20240303.jar';java=Path(r'C:/Program Files/Android/Android Studio/jbr/bin')
sys.path[:0]=[str(handoff/'aipc_sources'),str(bundle)]
spec=importlib.util.spec_from_file_location('aipc_test_static_server',handoff/'aipc_sources/server.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
server=module.Server(('127.0.0.1',0),bundle/'scene','1');threading.Thread(target=server.serve_forever,daemon=True).start()
packet=(handoff/'examples/SYNTHETIC_live_decode.vcl').read_bytes();_,j,p,r=struct.unpack('<4sIII',packet[:16]);raw=gzip.decompress(packet[16+j:]);calls=0
class LiveHandler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  global calls
  if self.path!='/v2/cloud/live/frame' or self.headers.get('Authorization')!='Bearer 1':self.send_error(401);return
  calls+=1
  if calls==2:self.send_response(304);self.end_headers();return
  if calls>=5:self.send_response(503);self.send_header('Content-Length','0');self.end_headers();return
  meta=json.loads(packet[16:16+j]);meta.update(source_epoch='epoch-a'if calls<4 else'epoch-b',cloud_version=2 if calls==3 else 1,source_age_s=.1,units='metre',snapshot_semantics='replace_all_not_append',persistent_cache=False,same_source_as_web_home=True,map_to_vehicle=[[1,0,0,10],[0,1,0,20],[0,0,1,30],[0,0,0,1]])
  meta=json.dumps(meta,separators=(',',':')).encode();payload=struct.pack('<4sIII',b'VCL1',len(meta),p,r)+meta+packet[16+j:]
  self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.send_header('ETag','"snapshot-%s"'%calls);self.end_headers();self.wfile.write(payload)
live=ThreadingHTTPServer(('127.0.0.1',0),LiveHandler);threading.Thread(target=live.serve_forever,daemon=True).start()
code=r"""import com.tanluzhe.cloud.*;import java.nio.*;import java.nio.file.*;import java.io.*;import java.util.*;import java.util.concurrent.*;import org.json.*;
public class SceneV2Test {
 static final Set<String> warm=new HashSet<>();
 static int checks;static void check(boolean b,String message){checks++;if(!b)throw new AssertionError(message);}interface Condition{boolean get();}static void waitFor(Condition c,long ms,String what)throws Exception{long until=System.nanoTime()+ms*1000000;while(!c.get()&&System.nanoTime()<until)Thread.sleep(100);check(c.get(),what);}
 static class Sink implements CloudStream.Sink{Set<String> ready=ConcurrentHashMap.newKeySet();public void reset(long g,List<CloudStream.Block>b){ready.clear();}public boolean offer(long g,CloudStream.Block b,ByteBuffer raw,boolean coarse){if(raw.remaining()!=b.bytes||!raw.isDirect())throw new AssertionError();ready.add(b.id);return true;}public Set<String> resident(long g){return new HashSet<>(ready);}public void retain(long g,Set<String> ids){ready.retainAll(ids);}}
 static void scene(String base,File cache,boolean cached,boolean offline)throws Exception{Sink sink=new Sink();CloudStream c=new CloudStream(new CloudStream.Config(base,"1",CloudStream.DENSE,"wifi"),cache,sink);c.position(new float[]{-4,.8f,1});long start=System.nanoTime();try{if(cached)c.restorePersistent();c.start();waitFor(()->c.coarseReady&&c.nearTotal>0&&c.nearDone==c.nearTotal&&sink.ready.containsAll(warm),100000,"near region incomplete: "+c.summary());waitFor(()->c.cacheProgress.complete&&c.cacheProgress.fraction==1,6000,"combined coarse + near cached progress reaches completion");check(c.nearTotal==88,"actual AIPC near plan");check(c.nearDiskDone==88,"disk and GPU counts distinct but complete");check(c.manifestRevision.matches("[0-9a-f]{64}"),"opaque server manifest revision");if(offline)check(!c.connected,"offline must not claim connected");}finally{c.close();c.awaitStopped();}if(cached)check(c.downloadedBytes==0,"persistent revisit must not download cached region");System.out.println((offline?"OFFLINE":cached?"CACHE":"FIRST")+" near="+c.nearDone+"/"+c.nearTotal+" downloaded="+c.downloadedBytes+" disk="+c.diskBytes+" seconds="+(System.nanoTime()-start)/1e9);}
 static class LiveSink implements LiveCloudStream.Sink{volatile int resets,offers;volatile boolean visible;public void reset(long g){resets++;}public boolean offer(long g,ByteBuffer p,float[]m){check(p.remaining()==32&&p.get(15)==(byte)255&&p.get(31)==(byte)128,"RGBA/stride preserved");check(m[12]==10&&m[13]==30&&m[14]==-20,"A * map_to_vehicle, exactly once");offers++;return true;}public void visible(boolean v){visible=v;}}
 public static void main(String[]args)throws Exception{
  JSONObject manifest=new JSONObject(Files.readString(Path.of(args[4])));JSONArray tiles=manifest.getJSONArray("tiles");for(int i=0;i<tiles.length();i++){JSONObject b=tiles.getJSONObject(i);if(CloudStream.intersects(CloudStream.bounds(b.getJSONArray("bounds")),new float[]{-4,.8f,1},4))warm.add(b.getString("id"));}
  byte[] fixture=Files.readAllBytes(Path.of(args[3]));LiveCloudStream.Frame f=LiveCloudStream.decode(fixture);check(f.points.remaining()==32&&f.points.order()==ByteOrder.LITTLE_ENDIAN,"real supplied VCL1 fixture");check(f.points.getFloat(0)==1&&f.points.getFloat(16)==-1.25f,"float positions");for(int len:new int[]{0,15,fixture.length-1}){boolean rejected=false;try{LiveCloudStream.decode(Arrays.copyOf(fixture,len));}catch(Exception expected){rejected=true;}check(rejected,"truncated packet rejection");}byte[] corrupt=fixture.clone();corrupt[corrupt.length-4]^=1;boolean rejected=false;try{LiveCloudStream.decode(corrupt);}catch(Exception expected){rejected=true;}check(rejected,"gzip/SHA corruption rejection");
  LiveSink ls=new LiveSink();LiveCloudStream lc=new LiveCloudStream(args[1],"1",ls);try{lc.start();waitFor(()->lc.error.contains("503"),10000,"503 must be explicit");check(ls.offers==3&&ls.resets==2,"replace snapshots, 304 skip, epoch reset");check(!lc.available&&!ls.visible,"unavailable live cloud must not show static fallback");}finally{lc.close();}
  File cache=new File(args[2],"run-"+System.nanoTime());scene(args[0],cache,false,false);scene(args[0],cache,true,false);scene("http://127.0.0.1:9",cache,true,true);
  CloudStream.CacheProgress saved=CloudStream.readCacheProgress(cache,CloudStream.DENSE);check(saved.complete&&saved.fraction==1&&saved.bytes>0,"Per-scene completed progress survives offline revisit");JSONObject checkpoint=new JSONObject(Files.readString(new File(new File(cache,CloudStream.DENSE),"progress.json").toPath()));JSONObject target=checkpoint.getJSONArray("files").getJSONObject(1);File targetDir=new File(new File(cache,CloudStream.DENSE),checkpoint.getString("revision"));new File(targetDir,target.getString("name")).delete();CloudStream.CacheProgress missing=CloudStream.readCacheProgress(cache,CloudStream.DENSE);check(!missing.complete&&missing.fraction<1&&missing.fraction>0,"Evicted cached tile revokes completion, preserves coarse contribution");
  File other=new File(cache,"other-scene");other.mkdirs();File sentinel=new File(other,"manifest.json");Files.writeString(sentinel.toPath(),"{}");CloudStream.clearCache(new File(cache,CloudStream.DENSE));check(sentinel.exists(),"per-scene deletion preserves other scene");
  System.out.println("PASS: "+checks+" production v2 persistent/static and VCL1/epoch/304/503/RGBA/matrix checks against supplied AIPC server source. Host acknowledgement sink, not Quest hardware.");
 }
}
"""
(out/'SceneV2Test.java').write_text(code,encoding='utf8')
try:
 subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-cp',str(jar),'-d',str(out),str(root/'shared/src/main/java/com/tanluzhe/cloud/CloudStream.java'),str(root/'shared/src/main/java/com/tanluzhe/cloud/LiveCloudStream.java'),str(out/'SceneV2Test.java')],check=True)
 subprocess.run([str(java/'java.exe'),'-cp',str(jar)+';'+str(out),'SceneV2Test','http://127.0.0.1:'+str(server.server_port),'http://127.0.0.1:'+str(live.server_port),str(out),str(handoff/'examples/SYNTHETIC_live_decode.vcl'),str(handoff/'examples/manifest.json')],check=True,timeout=240)
finally:server.shutdown();server.server_close();live.shutdown();live.server_close()
