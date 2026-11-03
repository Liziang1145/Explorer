package com.tanluzhe.controlterminal.vr.v2;

import android.content.*;
import android.media.*;
import android.opengl.*;
import android.os.*;
import android.view.Surface;
import com.tanluzhe.controlterminal.vr.AppLog;
import java.io.*;
import java.nio.*;
import java.util.*;
import java.util.concurrent.*;
import org.json.*;

/** Independent default-on preview and remotely controlled high-quality recording. */
public final class ViewCapture implements AutoCloseable {
  private final Context context;
  private final ScheduledThreadPoolExecutor worker=new ScheduledThreadPoolExecutor(1);
  private final ExecutorService graphics=Executors.newSingleThreadExecutor();
  public final LiveViewBus live=new LiveViewBus();
  private volatile EGLContext shared;
  private CaptureEgl egl;
  private ScheduledFuture<?> drainTask;
  private MediaCodec codec;private Surface input;private MediaFormat format;
  private volatile String lastError="",encoderName="",serviceError="";
  private final Object submissions=new Object();
  private volatile boolean closing,closed,foreground,encoding;
  private final LiveSessionState liveState=new LiveSessionState();
  private volatile long epoch,rendered,encoded,lastFrameNs;
  private volatile float[] effective=new float[0];
  private volatile CaptureConfig config=CaptureConfig.defaults();
  private byte[] codecHeaders=new byte[0];
  private ViewHttpServer server;
  private final ViewRecorder recorder;
  private final AdaptivePreview adaptive=new AdaptivePreview();
  private volatile int appliedBitrate;
  private volatile long congestionAt;
  private final Map<String,Long> feedbackSequence=new HashMap<>();
  public ViewCapture(Context context){
    this.context=context;
    try{config=decode(new JSONObject(context.getSharedPreferences("capture",0).getString("config","{}")),config);}catch(Exception ignored){}
    android.content.SharedPreferences preferences=context.getSharedPreferences("capture",0);
    if(preferences.getInt("preview_profile_revision",0)<3){config=new CaptureConfig(1920,1080,30,6000000,config.eye,config.verticalFov,config.left,config.right,config.top,config.bottom,.5f,.5f);preferences.edit().putInt("preview_profile_revision",3).putString("config",json(config).toString()).apply();}
    if(phone())try{choose(config);}catch(Exception unsupported){for(int[] p:new int[][]{{1280,720,30,4000000},{960,540,30,2000000},{640,360,15,1000000}}){CaptureConfig fallback=new CaptureConfig(p[0],p[1],p[2],p[3],0,70,.02f,.02f,.02f,.02f,.5f,.5f);try{choose(fallback);config=fallback;preferences.edit().putString("config",json(config).toString()).apply();break;}catch(Exception ignored){}}}
    adaptive.reset(config.bitrate);appliedBitrate=config.bitrate;
    File external=context.getExternalFilesDir("recordings");recorder=new ViewRecorder(external==null?new File(context.getFilesDir(),"recordings"):external);
    worker.setRemoveOnCancelPolicy(true);
  }
  public void attach(EGLContext shared){this.shared=shared;try{if(server==null){server=new ViewHttpServer(this,new com.tanluzhe.controlterminal.vr.ConnectionSettings(context).token,8095);server.start();}}catch(Exception e){serviceError=AppLog.reason(e);AppLog.warn("CAPTURE","HTTP_START_FAILED",serviceError);}async(()->{if(liveState.shouldAutoStart(foreground,shared!=null)&&!encoding)startLive("automatic");return null;});}
  public CaptureConfig config(){return config;}
  public boolean recording(){return recorder.active();}
  public boolean streaming(){return liveState.snapshot().active;}
  public String summary(){return (streaming()?"直播已开启":"直播关闭")+" · "+config.width+"×"+config.height+" / "+config.fps+" FPS";}
  public String error(){return serviceError.isEmpty()?lastError:lastError.isEmpty()?serviceError:serviceError+" · "+lastError;}
  public void shutdownService(){if(server!=null)server.close();}
  public void foreground(boolean active){foreground=active;async(()->{if(!foreground){recorder.stop();stopLive("app_paused");stopEncoder();}else if(liveState.shouldAutoStart(foreground,shared!=null)&&!encoding)startLive("automatic");return null;});}
  public void cancelStreamFromMenu(){liveState.requestStop();async(()->{stopLive("vr_menu");stopEncoder();return null;});}
  private void stopLive(String reason){
    LiveSessionState.Snapshot before=liveState.snapshot();liveState.stop(reason);live.finish();
    if(before.active)AppLog.info("CAPTURE","LIVE_STOP","reason="+reason+" revision="+liveState.snapshot().revision);
  }
  private void startLive()throws Exception{startLive("backend");}
  private void startLive(String source)throws Exception{
    if(!foreground||shared==null||closing)throw new IllegalStateException("VR 未处于可渲染前台");
    startEncoder();boolean already=streaming();requestKey();liveState.start(source);
    if(!already)AppLog.info("CAPTURE","LIVE_START","source="+source+"; no confirmation required; revision="+liveState.snapshot().revision);
  }
  public void change(CaptureConfig next){async(()->{configure(next);return null;});}
  private <T> void async(Callable<T> call){if(closed)return;worker.execute(()->{try{call.call();}catch(Exception e){error(e);}});}
  private <T> T call(Callable<T> action)throws Exception{if(closed)throw new IllegalStateException("VR 已退出");try{return worker.submit(action).get(20,TimeUnit.SECONDS);}catch(ExecutionException e){Throwable cause=e.getCause();if(cause instanceof Exception)throw (Exception)cause;throw new IllegalStateException(cause);}catch(TimeoutException e){throw new IllegalStateException("操作仍在处理中，请查询 status，勿重复启动",e);}}
  public JSONObject command(String path,JSONObject body)throws Exception{
    try{return call(()->{
      if(!Arrays.asList("/v1/view/config","/v1/view/record/config","/v1/view/preview/feedback").contains(path)&&body.length()!=0)throw new IllegalArgumentException("启动/停止接口不接受参数，请先PUT /v1/view/config");
      switch(path){
        case "/v1/view/config":configure(decode(body,config));break;
        case "/v1/view/record/config":recorder.configure(decode(body,recorder.config()));break;
        case "/v1/view/record/start":recorder.start(shared,foreground&&!closing);break;
        case "/v1/view/record/stop":recorder.stop();break;
        case "/v1/view/preview/feedback":feedback(body);break;
        case "/v1/view/live/start":liveState.requestStart();startLive();break;
        case "/v1/view/live/stop":liveState.requestStop();stopLive("backend");stopEncoder();break;
        case "/v1/view/keyframe":requestKey();break;
        default:throw new IllegalArgumentException("未知控制接口");
      }
      return status();
    });}catch(Exception e){error(e);throw e;}
  }
  private void configure(CaptureConfig next)throws Exception{
    if(next.width>1920||next.height>1920||(long)next.width*next.height>2073600||next.bitrate>AdaptivePreview.MAX||next.bitrate<AdaptivePreview.MIN)throw new IllegalArgumentException("预览限1080P像素与16Mbps；高分辨率请配置record/config");
    boolean encoderChanged=!config.sameEncoder(next);boolean restart=encoding&&encoderChanged;boolean wasStreaming=streaming();
    if(restart)choose(next);
    if(restart){stopLive("reconfigured");stopEncoder();}
    config=next;if(encoderChanged)adaptive.reset(next.bitrate);context.getSharedPreferences("capture",0).edit().putString("config",json(next).toString()).apply();
    if(restart&&wasStreaming){startLive();}else if(encoding)NativeVr.captureConfigure(next.width,next.height,next.fps,next.nativeValues(),epoch);
    lastError="";AppLog.info("CAPTURE","CONFIG",json(next).toString());
  }
  private void startEncoder()throws Exception{
    if(encoding)return;if(!foreground||shared==null)throw new IllegalStateException("VR 未处于可渲染前台");
    CaptureConfig c=config;adaptive.reset(c.bitrate);appliedBitrate=c.bitrate;lastError="";codecHeaders=new byte[0];format=null;effective=new float[0];lastFrameNs=0;
    try{
      MediaCodecInfo info=choose(c);encoderName=info.getName();codec=MediaCodec.createByCodecName(encoderName);
      MediaFormat f=MediaFormat.createVideoFormat("video/avc",c.width,c.height);f.setInteger(MediaFormat.KEY_COLOR_FORMAT,MediaCodecInfo.CodecCapabilities.COLOR_FormatSurface);f.setInteger(MediaFormat.KEY_BIT_RATE,c.bitrate);f.setInteger(MediaFormat.KEY_FRAME_RATE,c.fps);f.setInteger(MediaFormat.KEY_I_FRAME_INTERVAL,1);f.setInteger(MediaFormat.KEY_COLOR_STANDARD,MediaFormat.COLOR_STANDARD_BT709);f.setInteger(MediaFormat.KEY_COLOR_RANGE,MediaFormat.COLOR_RANGE_LIMITED);f.setInteger(MediaFormat.KEY_COLOR_TRANSFER,MediaFormat.COLOR_TRANSFER_SDR_VIDEO);f.setInteger(MediaFormat.KEY_PROFILE,MediaCodecInfo.CodecProfileLevel.AVCProfileBaseline);
      if(Build.VERSION.SDK_INT>=29)f.setInteger(MediaFormat.KEY_MAX_B_FRAMES,0);
      codec.configure(f,null,null,MediaCodec.CONFIGURE_FLAG_ENCODE);input=codec.createInputSurface();codec.start();Surface surface=input;
      graphics.submit(()->{if(egl==null)egl=new CaptureEgl(shared);egl.attach(surface);}).get(3,TimeUnit.SECONDS);
      encoding=true;epoch++;drainTask=worker.scheduleWithFixedDelay(()->{try{drain();}catch(Exception e){fail(e);}},0,8,TimeUnit.MILLISECONDS);NativeVr.captureConfigure(c.width,c.height,c.fps,c.nativeValues(),epoch);AppLog.info("CAPTURE","ENCODER_START",encoderName+" "+c.width+"x"+c.height+" @"+c.fps);
    }catch(Exception e){stopEncoder();throw e;}
  }
  private static MediaCodecInfo choose(CaptureConfig c){
    for(MediaCodecInfo info:new MediaCodecList(MediaCodecList.REGULAR_CODECS).getCodecInfos()){
      if(!info.isEncoder())continue;String name=info.getName().toLowerCase(Locale.ROOT);
      if(Build.VERSION.SDK_INT>=29?!info.isHardwareAccelerated():name.startsWith("omx.google.")||name.startsWith("c2.android."))continue;
      try{MediaCodecInfo.CodecCapabilities caps=info.getCapabilitiesForType("video/avc");if(caps.getVideoCapabilities().areSizeAndRateSupported(c.width,c.height,c.fps)&&caps.getVideoCapabilities().getBitrateRange().contains(c.bitrate))return info;}catch(Exception ignored){}
    }
    throw new IllegalStateException("没有支持该分辨率/帧率的 H.264 硬件编码器");
  }
  public boolean frame(int texture,int slot,long time,long fence,float[] framing,long version){
    if(slot>=3)return !closed&&!closing&&foreground&&recorder.frame(texture,slot,time,fence,framing,version);
    synchronized(submissions){
    if(closed||closing||!encoding||!foreground||version!=epoch)return false;CaptureConfig captured=config;effective=framing.clone();
    try{graphics.execute(()->{try{
      egl.consume(fence);
      if(encoding&&version==epoch&&foreground){egl.draw(texture,captured.width,captured.height,time);rendered++;lastFrameNs=time;}
    }catch(Exception e){error(e);async(()->{stopLive("encoder_error");stopEncoder();return null;});}
    finally{GLES20.glFinish();NativeVr.captureReleased(slot);}});return true;}catch(RejectedExecutionException e){return false;}
    }
  }
  private void drain()throws Exception{
    if(codec==null)return;MediaCodec.BufferInfo info=new MediaCodec.BufferInfo();
    for(int n=0;n<32;n++){
      int index=codec.dequeueOutputBuffer(info,0);
      if(index==MediaCodec.INFO_TRY_AGAIN_LATER)return;
      if(index==MediaCodec.INFO_OUTPUT_FORMAT_CHANGED){format=codec.getOutputFormat();if(format.getInteger(MediaFormat.KEY_WIDTH)!=config.width||format.getInteger(MediaFormat.KEY_HEIGHT)!=config.height)throw new IllegalStateException("编码器实际画幅与请求不符");codecHeaders=new byte[0];for(String key:new String[]{"csd-0","csd-1"}){ByteBuffer csd=format.getByteBuffer(key);if(csd!=null){ByteBuffer copy=csd.duplicate();byte[] bytes=new byte[copy.remaining()];copy.get(bytes);codecHeaders=NalUnits.join(codecHeaders,NalUnits.annexB(bytes));}}continue;}
      if(index<0)continue;
      try{
        ByteBuffer output=codec.getOutputBuffer(index);if(output==null||info.size==0||(info.flags&MediaCodec.BUFFER_FLAG_CODEC_CONFIG)!=0)continue;
        boolean key=(info.flags&MediaCodec.BUFFER_FLAG_KEY_FRAME)!=0;output.position(info.offset);output.limit(info.offset+info.size);encoded++;
        if(streaming()){byte[] bytes=new byte[info.size];output.duplicate().get(bytes);CaptureConfig c=config;live.publish(NalUnits.annexB(bytes),key,info.presentationTimeUs,c.width,c.height,codecHeaders);}
      }finally{codec.releaseOutputBuffer(index,false);}
    }
  }
  private void stopEncoder(){
    encoding=false;appliedBitrate=0;epoch++;if(drainTask!=null){drainTask.cancel(false);drainTask=null;}try{NativeVr.captureConfigure(0,0,config.fps,config.nativeValues(),epoch);}catch(Throwable ignored){}
    if(codec==null)return;
    try{
      Future<?> detach=graphics.submit(()->{if(egl!=null)egl.detach();});long end=System.nanoTime()+3_000_000_000L;
      while(!detach.isDone()&&System.nanoTime()<end){drain();Thread.sleep(2);}if(!detach.isDone())throw new IllegalStateException("编码器图形队列停止超时");detach.get();
      codec.signalEndOfInputStream();end=System.nanoTime()+150_000_000L;while(System.nanoTime()<end){drain();Thread.sleep(4);}
    }catch(Exception e){error(e);}
    finally{try{codec.stop();}catch(Exception ignored){}try{codec.release();}catch(Exception ignored){}codec=null;if(input!=null){input.release();input=null;}format=null;codecHeaders=new byte[0];AppLog.info("CAPTURE","ENCODER_STOP","released");}
  }
  private void requestKey(){if(codec!=null){Bundle options=new Bundle();options.putInt(MediaCodec.PARAMETER_KEY_REQUEST_SYNC_FRAME,0);codec.setParameters(options);}}
  public void requestKeyAsync(){async(()->{requestKey();return null;});}
  private void error(Exception e){lastError=AppLog.reason(e);AppLog.warn("CAPTURE","ERROR",lastError);}
  private void fail(Exception e){error(e);stopLive("encoder_error");stopEncoder();}
  private boolean phone(){return context.getPackageName().endsWith(".mobile");}
  public JSONObject status()throws JSONException{
    LiveSessionState.Snapshot liveStatus=liveState.snapshot();
    long age=lastFrameNs==0?-1:(System.nanoTime()-lastFrameNs)/1_000_000;
    return new JSONObject().put("version",1).put("ready",shared!=null&&!closed).put("foreground",foreground).put("encoding",encoding).put("recording",recorder.active()).put("record",recorder.status()).put("local_recording_supported",true).put("record_control",phone()?"local_and_backend":"backend_only").put("source",phone()?"phone_viewport":"openxr").put("stereo",!phone()).put("preview",new JSONObject().put("default_width",1920).put("default_height",1080).put("adaptive",true).put("target_bitrate",adaptive.current()).put("applied_bitrate",appliedBitrate).put("min_bitrate",AdaptivePreview.MIN).put("max_bitrate",config.bitrate)).put("live_default_on",true).put("live_wanted",liveState.wanted()).put("framing_center","optical_axis").put("streaming",liveStatus.active).put("live_policy_revision",2).put("live_revision",liveStatus.revision).put("live_started_by",liveStatus.startedBy).put("live_stop_reason",liveStatus.stopReason).put("live_start_requires_confirmation",false).put("live_can_start_locally",phone()).put("live_cancel_menu_only",!phone()).put("config",json(config)).put("effective",new JSONArray(effective)).put("effective_order",new JSONArray(new String[]{"left_uv","bottom_uv","right_uv","top_uv","horizontal_fov_deg","vertical_fov_deg","eye_width","eye_height"})).put("frame_age_ms",age<0?JSONObject.NULL:age).put("exported_frames",rendered).put("encoded_frames",encoded).put("clients",live.size()).put("session_id",epoch).put("last_file",recorder.status().get("last_file")).put("error",error()).put("encoder",encoderName).put("service_port",8095).put("service_running",server!=null&&server.running());
  }
  public JSONArray recordings()throws Exception{return recorder.store.list();}
  public RecordingStore.Opened openRecording(String name)throws IOException{return recorder.store.open(name);}
  public void deleteRecording(String name)throws IOException{recorder.store.delete(name);}
  public JSONObject recordStatus()throws JSONException{return recorder.status();}
  public JSONObject capabilities()throws JSONException{
    JSONArray rows=new JSONArray();int[][] profiles={{1920,1080,30,6000000},{1920,1080,60,20000000},{2048,1080,60,30000000},{2560,1440,60,40000000},{2560,1440,60,80000000}};
    for(int[] p:profiles){JSONObject row=new JSONObject().put("width",p[0]).put("height",p[1]).put("fps",p[2]).put("bitrate",p[3]);try{MediaCodecInfo info=ViewRecorder.choose(new CaptureConfig(p[0],p[1],p[2],p[3],0,70,0,0,0,0,.5f,.5f));row.put("supported",true).put("encoder",info.getName()).put("max_codec_instances",info.getCapabilitiesForType("video/avc").getMaxSupportedInstances());}catch(Exception e){row.put("supported",false);}rows.put(row);}
    return new JSONObject().put("profiles",rows).put("record_default",json(phone()?new CaptureConfig(1920,1080,30,12000000,0,70,.02f,.02f,.02f,.02f,.5f,.5f):CaptureConfig.recordingDefaults())).put("preview_default",json(CaptureConfig.defaults())).put("concurrent_encode_requires_device_test",true).put("resolution_is_encoded_size",true);
  }
  private void feedback(JSONObject body)throws Exception{
    String id=body.getString("client_id");if(!live.hasClient(id))throw new IllegalArgumentException("反馈client_id不是当前预览订阅者");
    Set<String> allowed=new HashSet<>(Arrays.asList("client_id","sequence","window_ms","delivery_bps","buffer_ms","rtt_ms","dropped_frames"));Iterator<String> keys=body.keys();while(keys.hasNext()){String key=keys.next();if(!allowed.contains(key))throw new IllegalArgumentException("未知反馈参数");if(key.equals("client_id"))continue;Object value=body.get(key);if(!(value instanceof Number)||!Double.isFinite(((Number)value).doubleValue()))throw new IllegalArgumentException("反馈须为有限数值");if(Arrays.asList("sequence","window_ms","delivery_bps","dropped_frames").contains(key)&&((Number)value).doubleValue()!=Math.rint(((Number)value).doubleValue()))throw new IllegalArgumentException("反馈整数参数无效");}
    long seq=body.getLong("sequence"),window=body.getLong("window_ms");if(seq<0||seq<=feedbackSequence.getOrDefault(id,-1L)||window<500||window>5000)throw new IllegalArgumentException("反馈过期或窗口无效");
    int target=adaptive.feedback(SystemClock.elapsedRealtime(),body.getLong("delivery_bps"),body.getDouble("buffer_ms"),body.getDouble("rtt_ms"),body.getInt("dropped_frames"));
    applyBitrate(target);feedbackSequence.keySet().removeIf(key->!live.hasClient(key));feedbackSequence.put(id,seq);
  }
  private void applyBitrate(int target){if(codec==null||!encoding||target==appliedBitrate)return;Bundle values=new Bundle();values.putInt(MediaCodec.PARAMETER_KEY_VIDEO_BITRATE,target);codec.setParameters(values);appliedBitrate=target;AppLog.info("CAPTURE","ADAPT_BITRATE","bps="+target);}
  public void networkCongested(){long now=SystemClock.elapsedRealtime();if(now-congestionAt<1000)return;congestionAt=now;async(()->{applyBitrate(adaptive.congested(now));return null;});}
  public static JSONObject json(CaptureConfig c){try{return new JSONObject().put("width",c.width).put("height",c.height).put("fps",c.fps).put("bitrate",c.bitrate).put("eye",c.eye).put("vertical_fov_deg",c.verticalFov).put("margin_left",c.left).put("margin_right",c.right).put("margin_top",c.top).put("margin_bottom",c.bottom).put("center_x",c.centerX).put("center_y",c.centerY);}catch(JSONException impossible){throw new IllegalStateException(impossible);}}
  static CaptureConfig decode(JSONObject j,CaptureConfig c)throws JSONException{
    Set<String> allowed=new HashSet<>(Arrays.asList("width","height","fps","bitrate","eye","vertical_fov_deg","margin_left","margin_right","margin_top","margin_bottom","center_x","center_y"));Iterator<String> keys=j.keys();while(keys.hasNext()){String key=keys.next();if(!allowed.contains(key))throw new IllegalArgumentException("未知参数："+key);Object value=j.get(key);if(!(value instanceof Number)||!Double.isFinite(((Number)value).doubleValue()))throw new IllegalArgumentException("参数须为有限数值："+key);if(Arrays.asList("width","height","fps","bitrate","eye").contains(key)&&((Number)value).doubleValue()!=((Number)value).intValue())throw new IllegalArgumentException("整数参数："+key);}
    return new CaptureConfig(j.optInt("width",c.width),j.optInt("height",c.height),j.optInt("fps",c.fps),j.optInt("bitrate",c.bitrate),j.optInt("eye",c.eye),(float)j.optDouble("vertical_fov_deg",c.verticalFov),(float)j.optDouble("margin_left",c.left),(float)j.optDouble("margin_right",c.right),(float)j.optDouble("margin_top",c.top),(float)j.optDouble("margin_bottom",c.bottom),(float)j.optDouble("center_x",c.centerX),(float)j.optDouble("center_y",c.centerY));
  }
  public void close(){synchronized(submissions){if(closed||closing)return;closing=true;}if(server!=null)server.close();try{call(()->{recorder.close();stopLive("app_exit");stopEncoder();graphics.submit(()->{if(egl!=null){egl.close();egl=null;}}).get(4,TimeUnit.SECONDS);return null;});}catch(Exception e){error(e);}closed=true;worker.shutdown();graphics.shutdown();}
}
