"""Exercise production DirectHevcVideo against real HTTP faults; Android/player scheduling are host adapters."""
from pathlib import Path
import subprocess
root=Path(__file__).resolve().parents[1];out=root/'vr/build/video-recovery-tests';src=root/'vr/src/main/java/com/tanluzhe/controlterminal/vr/v2';out.mkdir(parents=True,exist_ok=True)
java=Path(r'C:/Program Files/Android/Android Studio/jbr/bin')
stubs={
'android/content/Context.java':'package android.content;public class Context{}',
'android/net/Uri.java':'package android.net;public class Uri{public final String text;private Uri(String s){text=s;}public static Uri parse(String s){return new Uri(s);}}',
'android/view/Surface.java':'package android.view;public class Surface{}',
'android/os/Looper.java':'package android.os;public class Looper{private static final Looper MAIN=new Looper();public static Looper getMainLooper(){return MAIN;}}',
'android/os/Handler.java':'''package android.os;import java.util.*;import java.util.concurrent.*;public class Handler{
 static final ScheduledExecutorService main=Executors.newSingleThreadScheduledExecutor(r->{Thread t=new Thread(r,"test-main");t.setDaemon(true);return t;});private final Map<Runnable,List<Future<?>>> tasks=new ConcurrentHashMap<>();public Handler(Looper l){}public boolean post(Runnable r){return postDelayed(r,0);}public boolean postDelayed(Runnable r,long delay){tasks.computeIfAbsent(r,k->new CopyOnWriteArrayList<>()).add(main.schedule(r,delay,TimeUnit.MILLISECONDS));return true;}public void removeCallbacks(Runnable r){List<Future<?>> list=tasks.remove(r);if(list!=null)for(Future<?> f:list)f.cancel(false);}public void removeCallbacksAndMessages(Object o){for(Runnable r:tasks.keySet())removeCallbacks(r);}
}''',
'androidx/media3/common/util/UnstableApi.java':'package androidx.media3.common.util;public @interface UnstableApi{}',
'androidx/media3/common/util/TimestampAdjuster.java':'package androidx.media3.common.util;public class TimestampAdjuster{public TimestampAdjuster(long n){}}',
'androidx/media3/common/C.java':'package androidx.media3.common;public class C{public static final long TIME_UNSET=-1;public static final int TRACK_TYPE_AUDIO=1,TRACK_TYPE_TEXT=3;}',
'androidx/media3/common/MimeTypes.java':'package androidx.media3.common;public class MimeTypes{public static final String VIDEO_H265="video/hevc",VIDEO_MP4="video/mp4";}',
'androidx/media3/common/VideoSize.java':'package androidx.media3.common;public class VideoSize{public int width=1280,height=720;public float pixelWidthHeightRatio=1;}',
'androidx/media3/common/PlaybackException.java':'package androidx.media3.common;public class PlaybackException extends Exception{public PlaybackException(Throwable t){super(t);}public String getErrorCodeName(){return "HTTP_ERROR";}}',
'androidx/media3/common/Player.java':'package androidx.media3.common;public interface Player{int STATE_ENDED=4;interface Listener{default void onVideoSizeChanged(VideoSize s){}default void onRenderedFirstFrame(){}default void onPlayerError(PlaybackException e){}default void onPlaybackStateChanged(int state){}}}',
'androidx/media3/common/MediaItem.java':'package androidx.media3.common;public class MediaItem{public android.net.Uri uri;public static class Builder{final MediaItem m=new MediaItem();public Builder setUri(android.net.Uri u){m.uri=u;return this;}public Builder setMimeType(String s){return this;}public MediaItem build(){return m;}}}',
'androidx/media3/datasource/HttpDataSource.java':'package androidx.media3.datasource;public class HttpDataSource{public static class InvalidResponseCodeException extends java.io.IOException{public final int responseCode;public InvalidResponseCodeException(int n){responseCode=n;}}}',
'androidx/media3/datasource/okhttp/OkHttpDataSource.java':'package androidx.media3.datasource.okhttp;import java.util.*;public class OkHttpDataSource{public static class Factory{public Factory(okhttp3.OkHttpClient c){}public Factory setDefaultRequestProperties(Map<String,String> p){return this;}}}',
'androidx/media3/exoplayer/mediacodec/MediaCodecInfo.java':'package androidx.media3.exoplayer.mediacodec;public class MediaCodecInfo{public boolean hardwareAccelerated=true,softwareOnly=false;}',
'androidx/media3/exoplayer/mediacodec/MediaCodecUtil.java':'package androidx.media3.exoplayer.mediacodec;import java.util.*;public class MediaCodecUtil{public static List<MediaCodecInfo> getDecoderInfos(String m,boolean s,boolean t){return Arrays.asList(new MediaCodecInfo());}}',
'androidx/media3/exoplayer/DefaultRenderersFactory.java':'package androidx.media3.exoplayer;import java.util.*;import androidx.media3.exoplayer.mediacodec.*;public class DefaultRenderersFactory{public interface Selector{List<MediaCodecInfo> select(String m,boolean s,boolean t);}public DefaultRenderersFactory(android.content.Context c){}public DefaultRenderersFactory setEnableDecoderFallback(boolean b){return this;}public DefaultRenderersFactory setMediaCodecSelector(Selector s){return this;}}',
'androidx/media3/exoplayer/DefaultLoadControl.java':'package androidx.media3.exoplayer;public class DefaultLoadControl{public static class Builder{public Builder setBufferDurationsMs(int a,int b,int c,int d){return this;}public Builder setTargetBufferBytes(int b){return this;}public Builder setPrioritizeTimeOverSizeThresholds(boolean b){return this;}public DefaultLoadControl build(){return new DefaultLoadControl();}}}',
'androidx/media3/exoplayer/analytics/AnalyticsListener.java':'package androidx.media3.exoplayer.analytics;public interface AnalyticsListener{class EventTime{}default void onDroppedVideoFrames(EventTime t,int c,long e){}default void onVideoDecoderInitialized(EventTime t,String name,long i,long d){}}',
'androidx/media3/exoplayer/upstream/LoadErrorHandlingPolicy.java':'package androidx.media3.exoplayer.upstream;public interface LoadErrorHandlingPolicy{class LoadErrorInfo{}}',
'androidx/media3/exoplayer/upstream/DefaultLoadErrorHandlingPolicy.java':'package androidx.media3.exoplayer.upstream;public class DefaultLoadErrorHandlingPolicy implements LoadErrorHandlingPolicy{public DefaultLoadErrorHandlingPolicy(int n){}public long getRetryDelayMsFor(LoadErrorInfo i){return 0;}}',
'androidx/media3/extractor/Extractor.java':'package androidx.media3.extractor;public interface Extractor{}',
'androidx/media3/extractor/text/SubtitleParser.java':'package androidx.media3.extractor.text;public class SubtitleParser{public static class Factory{public static final Factory UNSUPPORTED=new Factory();}}',
'androidx/media3/extractor/mp4/FragmentedMp4Extractor.java':'package androidx.media3.extractor.mp4;public class FragmentedMp4Extractor implements androidx.media3.extractor.Extractor{public FragmentedMp4Extractor(Object a,int b,Object c,Object d,java.util.List<?> e,Object f){}}',
'androidx/media3/exoplayer/source/ProgressiveMediaSource.java':'package androidx.media3.exoplayer.source;import androidx.media3.common.*;import androidx.media3.extractor.*;public class ProgressiveMediaSource{public MediaItem item;public interface Extractors{Extractor[] create();}public static class Factory{public Factory(Object d,Extractors e){}public Factory setLoadErrorHandlingPolicy(Object p){return this;}public ProgressiveMediaSource createMediaSource(MediaItem i){ProgressiveMediaSource m=new ProgressiveMediaSource();m.item=i;return m;}}}',
'com/tanluzhe/controlterminal/vr/AppLog.java':'package com.tanluzhe.controlterminal.vr;public class AppLog{public static void info(String a,String b,String c){}public static void warn(String a,String b,String c){}public static String reason(Throwable e){return e.toString();}}',
'com/tanluzhe/controlterminal/vr/v2/BaseLink.java':'package com.tanluzhe.controlterminal.vr.v2;public class BaseLink{public static String endpoint(String scheme,String host,int port){return scheme+"://"+host+":"+port;}}',
'androidx/media3/exoplayer/ExoPlayer.java':'''package androidx.media3.exoplayer;
import androidx.media3.common.*;import androidx.media3.exoplayer.source.*;import androidx.media3.exoplayer.analytics.*;import android.os.*;import java.net.*;import java.util.*;
public class ExoPlayer{
 public static class Builder{public Builder(android.content.Context c,Object r){}public Builder setLoadControl(Object o){return this;}public ExoPlayer build(){return new ExoPlayer();}}
 public interface Metadata{void frame(long pts,long release,Object format,Object mediaFormat);}
 public static class TrackSelection{public TrackSelection buildUpon(){return this;}public TrackSelection setTrackTypeDisabled(int t,boolean b){return this;}public TrackSelection build(){return this;}}
 private Metadata metadata;private Player.Listener listener;private ProgressiveMediaSource media;private volatile boolean closed;private final Handler main=new Handler(Looper.getMainLooper());
 public TrackSelection getTrackSelectionParameters(){return new TrackSelection();}public void setTrackSelectionParameters(Object o){}public void setVideoSurface(android.view.Surface s){}public void setVideoFrameMetadataListener(Metadata m){metadata=m;}public void addAnalyticsListener(AnalyticsListener l){}public void addListener(Player.Listener l){listener=l;}public void setMediaSource(ProgressiveMediaSource m){media=m;}public void prepare(){}
 public void play(){Thread t=new Thread(()->{try{HttpURLConnection c=(HttpURLConnection)new URL(media.item.uri.text).openConnection();c.setConnectTimeout(1000);c.setReadTimeout(1000);int status=c.getResponseCode();c.disconnect();main.post(()->{if(closed)return;if(status!=200)listener.onPlayerError(new PlaybackException(new androidx.media3.datasource.HttpDataSource.InvalidResponseCodeException(status)));else{listener.onVideoSizeChanged(new VideoSize());metadata.frame(1,1,null,null);listener.onRenderedFirstFrame();}});}catch(Exception e){main.post(()->{if(!closed)listener.onPlayerError(new PlaybackException(e));});}},"fake-codec-http");t.setDaemon(true);t.start();}
 public void emitEnd(){main.post(()->{if(!closed)listener.onPlaybackStateChanged(Player.STATE_ENDED);});}public long getTotalBufferedDuration(){return 0;}public void release(){closed=true;}
}'''
}
for name,code in stubs.items():
 p=out/'adapters'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(code,encoding='utf8')
code=r'''package com.tanluzhe.controlterminal.vr.v2;
import java.util.*;import java.util.concurrent.*;import java.util.concurrent.atomic.*;import java.lang.reflect.*;import com.sun.net.httpserver.*;import java.net.*;import android.os.*;
public class VideoRecoveryTest {
 static int checks;static void check(boolean b,String m){checks++;if(!b)throw new AssertionError(m);}interface Fn{boolean ready()throws Exception;}static void waitFor(Fn condition)throws Exception{long deadline=System.nanoTime()+12_000_000_000L;while(!condition.ready()){if(System.nanoTime()>deadline)throw new AssertionError("timed out");Thread.sleep(20);}}
 static Object field(Object o,String name)throws Exception{Field f=o.getClass().getDeclaredField(name);f.setAccessible(true);return f.get(o);}
 static void old(Object o,String name)throws Exception{Field f=o.getClass().getDeclaredField(name);f.setAccessible(true);f.setLong(o,System.nanoTime()-7_000_000_000L);}
 public static void main(String[] args)throws Exception{
  HttpServer server=HttpServer.create(new InetSocketAddress("127.0.0.1",0),0);Map<String,AtomicInteger> opens=new ConcurrentHashMap<>();Map<String,Set<String>> ids=new ConcurrentHashMap<>();AtomicInteger statusCalls=new AtomicInteger();AtomicInteger rightFailures=new AtomicInteger(2),auth=new AtomicInteger();
  server.createContext("/",e->{String path=e.getRequestURI().getPath();int status=200;String body="{}";
   if(path.equals("/status")){statusCalls.incrementAndGet();body="{\"codec\":\"HEVC\",\"streams\":{\"camera\":{},\"camera1\":{},\"camera2\":{}}}";}
   else if(path.startsWith("/stream/")){String k=path.substring(8);opens.computeIfAbsent(k,x->new AtomicInteger()).incrementAndGet();ids.computeIfAbsent(k,x->ConcurrentHashMap.newKeySet()).add(e.getRequestURI().getQuery());if(k.equals("camera1")){int remain=rightFailures.getAndUpdate(n->Math.max(0,n-1));if(remain>0)status=remain==2?400:503;}if(k.equals("camera2")&&auth.get()!=0)status=auth.get();}
   byte[] b=body.getBytes();e.sendResponseHeaders(status,b.length);e.getResponseBody().write(b);e.close();});server.setExecutor(Executors.newCachedThreadPool(r->{Thread t=new Thread(r);t.setDaemon(true);return t;}));server.start();int port=server.getAddress().getPort();
  DirectHevcVideo rgb=new DirectHevcVideo(new android.content.Context(),"127.0.0.1",port,"1",new android.view.Surface(),new Dashboard(),"camera","720p30");
  DirectHevcVideo right=new DirectHevcVideo(new android.content.Context(),"127.0.0.1",port,"1",new android.view.Surface(),new Dashboard(),"camera1","240p15");
  try{rgb.start();right.start();waitFor(()->rgb.outputReady&&right.outputReady);
   check(opens.get("camera1").get()==3,"400/503 source outage must recover");check(opens.get("camera").get()==1,"other source must stay open");check(ids.get("camera1").size()==3,"each retry must have fresh client id");check(statusCalls.get()>=4,"retry must rediscover status");check(((okhttp3.OkHttpClient)field(right,"http")).callTimeoutMillis()==8000,"HTTP discovery/feedback deadline");
   ((androidx.media3.exoplayer.ExoPlayer)field(right,"player")).emitEnd();waitFor(()->opens.get("camera1").get()>=4&&right.outputReady);check(ids.get("camera1").size()==4,"EOF must create new subscription");
   old(right,"lastFrame");old(right,"consumedAt");new Handler(Looper.getMainLooper()).post((Runnable)field(right,"watchdog"));waitFor(()->opens.get("camera1").get()>=5&&right.outputReady);check(opens.get("camera").get()==1,"stall recovery must stay isolated");
   rightFailures.set(1);int before=opens.get("camera1").get();((androidx.media3.exoplayer.ExoPlayer)field(right,"player")).emitEnd();waitFor(()->opens.get("camera1").get()==before+1&&(Boolean)field(right,"retryPending"));right.foreground(false);Thread.sleep(1300);check(opens.get("camera1").get()==before+1,"pause must cancel pending reconnect");right.foreground(true);waitFor(()->right.outputReady);check(opens.get("camera1").get()==before+2,"resume recovers independently");
   auth.set(401);DirectHevcVideo denied=new DirectHevcVideo(new android.content.Context(),"127.0.0.1",port,"bad",new android.view.Surface(),new Dashboard(),"camera2","240p15");try{denied.start();waitFor(()->(Boolean)field(denied,"fatal"));Thread.sleep(1300);check(opens.get("camera2").get()==1,"unauthorized source must not retry indefinitely");}finally{denied.close();}
   System.out.println("PASS: "+checks+" production DirectHevcVideo recovery assertions with real HTTP 400/503/401, fresh subscriptions, EOF/stall, pause/resume and source isolation; decoder is a host adapter");
  }finally{rgb.close();right.close();server.stop(0);}
 }
}'''
(out/'VideoRecoveryTest.java').write_text(code,encoding='utf8')
jars=[root/'tools/v2_deps'/n for n in ['okhttp-4.12.0.jar','okio-jvm-3.6.0.jar','kotlin-stdlib-1.9.10.jar','annotations-13.0.jar','json-20240303.jar']];cp=';'.join(map(str,[out,*jars,root/'vr/build/v2-contract-tests']))
subprocess.run([str(java/'javac.exe'),'-encoding','UTF-8','-cp',cp,'-d',str(out),*map(str,(out/'adapters').rglob('*.java')),str(src/'VideoReconnect.java'),str(src/'DirectHevcVideo.java'),str(out/'VideoRecoveryTest.java')],check=True)
subprocess.run([str(java/'java.exe'),'-cp',cp,'com.tanluzhe.controlterminal.vr.v2.VideoRecoveryTest'],check=True,timeout=60)
